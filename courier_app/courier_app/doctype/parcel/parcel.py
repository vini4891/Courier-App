# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from courier_app.courier_app.state_machine import EXCEPTION_STATUSES
from courier_app.courier_app.utils.token import generate_token

#: Fields that are derived exclusively from scan history / payment
#: confirmation and must never be hand-edited by any human, in Desk or
#: otherwise. All legitimate mutation of these fields happens via
#: `frappe.db.set_value` (which never calls `validate()`), so this guard
#: costs the real code paths nothing while closing off `doc.save()` as a
#: back door.
IMMUTABLE_FIELDS = (
	"status",
	"payment_status",
	"token",
	"current_hub",
	"razorpay_order_id",
	"razorpay_payment_id",
)


class Parcel(Document):
	def validate(self):
		if not self.is_new():
			self._block_immutable_field_edits()
			self._block_hub_edits_after_draft()
		else:
			self.booked_by = self.booked_by or frappe.session.user
			if not self.is_return:
				self.status = "Draft"
				self.payment_status = "Pending"
			self.shipping_charge = self.compute_shipping_charge()

		if self.origin_hub and self.destination_hub and not frappe.db.get_value(
			"Hub", self.destination_hub, "is_active"
		):
			frappe.throw(_("Destination Hub {0} is not active.").format(self.destination_hub))
		if self.origin_hub and not frappe.db.get_value("Hub", self.origin_hub, "is_active"):
			frappe.throw(_("Origin Hub {0} is not active.").format(self.origin_hub))

	def before_insert(self):
		self.booked_on = now_datetime()
		# Generated once, here, before set_new_name() runs - the token is
		# never derived from / dependent on self.name.
		self.token = generate_token()

	def _block_immutable_field_edits(self):
		for fieldname in IMMUTABLE_FIELDS:
			if self.has_value_changed(fieldname):
				frappe.throw(
					_("{0} is derived from scan and payment history and cannot be edited directly.").format(
						self.meta.get_label(fieldname)
					),
					frappe.PermissionError,
				)

	def _block_hub_edits_after_draft(self):
		previous_status = self.get_doc_before_save().status if self.get_doc_before_save() else self.status
		if previous_status == "Draft":
			return
		if self.has_value_changed("origin_hub") or self.has_value_changed("destination_hub"):
			frappe.throw(
				_("Origin/Destination Hub cannot be changed once the parcel is booked and paid."),
				frappe.PermissionError,
			)

	def compute_shipping_charge(self) -> float:
		rates = frappe.db.get_value(
			"Service Level", self.service_level, ["base_rate", "rate_per_kg"], as_dict=True
		)
		if not rates:
			frappe.throw(_("Select a valid Service Level."))
		weight = frappe.utils.flt(self.weight_kg)
		return frappe.utils.flt(rates.base_rate) + frappe.utils.flt(rates.rate_per_kg) * weight


def get_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	roles = frappe.get_roles(user)
	if user == "Administrator" or "System Manager" in roles or "Courier Manager" in roles:
		return ""
	if "Delivery Agent" in roles:
		return ""
	return f"`tabParcel`.booked_by = {frappe.db.escape(user)}"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	user = user or frappe.session.user
	roles = frappe.get_roles(user)
	if user == "Administrator" or "System Manager" in roles or "Courier Manager" in roles:
		return True
	if "Delivery Agent" in roles:
		return True
	return doc.booked_by == user


@frappe.whitelist()
def resolve_exception(parcel: str, resume_status: str):
	"""Desk-only recovery path for a parcel stuck in an exception state.
	The ONLY legal target is the status the parcel held right before the
	exception was raised - never an arbitrary manager-chosen status. The
	parcel then requires a fresh, ordinary scan to progress any further."""
	frappe.only_for(["Courier Manager", "System Manager"])
	doc = frappe.get_doc("Parcel", parcel)
	if doc.status not in EXCEPTION_STATUSES:
		frappe.throw(_("Parcel is not in an exception state."))
	if not doc.pre_exception_status or resume_status != doc.pre_exception_status:
		frappe.throw(
			_("Can only resume to the status held before the exception ({0}).").format(
				doc.pre_exception_status
			)
		)
	frappe.db.set_value(
		"Parcel", parcel, {"status": resume_status, "pre_exception_status": None}, update_modified=True
	)
	frappe.get_doc(
		{
			"doctype": "Scan Event",
			"parcel": parcel,
			"scan_type": "Exception Resolved",
			"resolved_by_user": frappe.session.user,
			"resulting_status": resume_status,
			"is_duplicate": 0,
		}
	).insert(ignore_permissions=True)
	return {"status": resume_status}
