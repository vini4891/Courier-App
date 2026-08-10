# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt
"""Scan Event: the append-only log that drives Parcel.status.

Append-only is enforced three independent ways:
  1. Permissions (see scan_event.json) - nobody gets create/write/delete;
     all inserts happen server-side with ignore_permissions=True from
     `record_scan()` (this module) / `parcel.resolve_exception()`.
  2. `on_update` below throws unless the call is the insert itself
     (`self.flags.in_insert` is only True during that one call).
  3. `on_trash` below unconditionally throws - even for Administrator;
     genuine corrections require direct database access, by design.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from courier_app.courier_app.doctype.delivery_agent.delivery_agent import is_active_agent
from courier_app.courier_app.state_machine import (
	IllegalScanError,
	ParcelSnapshot,
	evaluate_scan,
)
from courier_app.courier_app.utils.token import resolve_token

HUB_REQUIRED_SCAN_TYPES = ("Pickup", "Hub In", "Hub Out")


class ScanEvent(Document):
	def validate(self):
		if self.scan_type in HUB_REQUIRED_SCAN_TYPES and not self.hub:
			frappe.throw(_("Hub is required for a '{0}' scan.").format(self.scan_type))

		if self.scan_type == "Exception Resolved":
			if not self.resolved_by_user:
				frappe.throw(_("Exception Resolved events must record who resolved them."))
			self.scanned_by_agent = None
		else:
			if not self.scanned_by_agent:
				frappe.throw(_("Scan events must record the scanning Delivery Agent."))
			self.resolved_by_user = None

		if not self.scanned_at:
			self.scanned_at = now_datetime()

	def on_update(self):
		if not self.flags.in_insert:
			frappe.throw(
				_("Scan Event records are append-only and cannot be modified."), frappe.PermissionError
			)

	def on_trash(self):
		frappe.throw(
			_("Scan Event records are append-only and cannot be deleted."), frappe.PermissionError
		)


def record_scan(
	token: str,
	scan_type: str,
	hub: str | None = None,
	user: str | None = None,
	failure_reason: str | None = None,
) -> dict:
	"""Single orchestration entry point for every scan coming off the
	scanner page. Resolves the token, evaluates the scan against the pure
	state machine, and only then writes the (append-only) Scan Event and
	applies the resulting Parcel state - via `frappe.db.set_value`, never
	`doc.save()`, so Parcel's own immutability guard never gets in the way
	of this, the one legitimate path for these fields to change.

	Illegal / out-of-order / wrong-hub scans raise before anything is
	written - they are rejected, not logged. A duplicate scan (a genuine
	re-scan of the step that just happened) DOES get logged, flagged
	`is_duplicate`, but causes no state change.
	"""
	user = user or frappe.session.user
	if not is_active_agent(user):
		frappe.throw(
			_("Only an active Delivery Agent may record a scan."), frappe.PermissionError
		)
	agent_name = frappe.db.get_value("Delivery Agent", {"user": user, "is_active": 1}, "name")

	parcel_name = resolve_token(token)
	if not parcel_name:
		frappe.throw(_("This barcode/QR token is not valid or has been tampered with."))

	snapshot_data = frappe.db.get_value(
		"Parcel", parcel_name, ["status", "origin_hub", "destination_hub"], as_dict=True
	)
	if not snapshot_data:
		frappe.throw(_("Parcel not found."))
	snapshot = ParcelSnapshot(**snapshot_data)

	try:
		result = evaluate_scan(snapshot, scan_type, hub)
	except IllegalScanError as e:
		frappe.throw(str(e))

	scan_event = frappe.get_doc(
		{
			"doctype": "Scan Event",
			"parcel": parcel_name,
			"scan_type": scan_type,
			"hub": hub,
			"scanned_by_agent": agent_name,
			"resulting_status": result.next_status,
			"is_duplicate": 1 if result.is_duplicate else 0,
			"failure_reason": failure_reason if scan_type in ("Delivery Failed", "Marked Stuck") else None,
		}
	)
	scan_event.insert(ignore_permissions=True)

	if not result.is_duplicate:
		update_fields = {"status": result.next_status}
		if hub:
			update_fields["current_hub"] = hub
		if result.pre_exception_status:
			update_fields["pre_exception_status"] = result.pre_exception_status
			update_fields["exception_reason"] = failure_reason
		frappe.db.set_value("Parcel", parcel_name, update_fields, update_modified=True)

	return {
		"parcel": parcel_name,
		"status": result.next_status,
		"is_duplicate": result.is_duplicate,
		"scan_event": scan_event.name,
	}
