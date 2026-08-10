# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt
"""Cross-cutting whitelisted API surface: booking, payment (incl. the
Razorpay webhook), tracking, returns, and the scanner's record-scan call.

Every mutating endpoint that touches Parcel field like status/payment_status
goes through either the Parcel controller's own guarded `validate()` (for
creation) or `frappe.db.set_value` from a single idempotent helper
(`_mark_parcel_paid`) - never an ad-hoc `doc.save()` - so this module is the
complete, auditable set of ways those fields can change.
"""

import hashlib
import hmac
import json

import frappe
from frappe import _
from frappe.integrations.utils import create_request_log

from courier_app.courier_app import razorpay_client
from courier_app.courier_app.doctype.hub.hub import get_hub_for_city
from courier_app.courier_app.doctype.scan_event.scan_event import record_scan as _record_scan

# ---------------------------------------------------------------------------
# Booking
# ---------------------------------------------------------------------------


@frappe.whitelist()
def book_parcel(
	sender_name: str,
	sender_phone: str,
	sender_address_line1: str,
	sender_city: str,
	sender_pincode: str,
	recipient_name: str,
	recipient_phone: str,
	recipient_address_line1: str,
	recipient_city: str,
	recipient_pincode: str,
	service_level: str,
	weight_kg: float,
	sender_email: str | None = None,
	sender_address_line2: str | None = None,
	sender_state: str | None = None,
	recipient_email: str | None = None,
	recipient_address_line2: str | None = None,
	recipient_state: str | None = None,
	length_cm: float | None = None,
	width_cm: float | None = None,
	height_cm: float | None = None,
	declared_value: float | None = None,
) -> dict:
	"""Create a Draft, unpaid Parcel. This is the ONLY legitimate way a
	Courier Customer's booking turns into a Parcel row - the doctype's own
	permissions deny customers `create` outright, so nothing can bypass the
	server-side computed fields (shipping_charge, token, status) this
	endpoint sets up."""
	origin_hub = get_hub_for_city(sender_city)
	if not origin_hub:
		frappe.throw(_("Sorry, we do not yet serve pickups from {0}.").format(sender_city))
	destination_hub = get_hub_for_city(recipient_city)
	if not destination_hub:
		frappe.throw(_("Sorry, we do not yet deliver to {0}.").format(recipient_city))

	parcel = frappe.get_doc(
		{
			"doctype": "Parcel",
			"booked_by": frappe.session.user,
			"sender_name": sender_name,
			"sender_phone": sender_phone,
			"sender_email": sender_email,
			"sender_address_line1": sender_address_line1,
			"sender_address_line2": sender_address_line2,
			"sender_city": sender_city,
			"sender_state": sender_state,
			"sender_pincode": sender_pincode,
			"recipient_name": recipient_name,
			"recipient_phone": recipient_phone,
			"recipient_email": recipient_email,
			"recipient_address_line1": recipient_address_line1,
			"recipient_address_line2": recipient_address_line2,
			"recipient_city": recipient_city,
			"recipient_state": recipient_state,
			"recipient_pincode": recipient_pincode,
			"origin_hub": origin_hub,
			"destination_hub": destination_hub,
			"service_level": service_level,
			"weight_kg": weight_kg,
			"length_cm": length_cm,
			"width_cm": width_cm,
			"height_cm": height_cm,
			"declared_value": declared_value,
		}
	)
	parcel.insert(ignore_permissions=True)
	return {"name": parcel.name, "shipping_charge": parcel.shipping_charge}


@frappe.whitelist()
def my_parcels() -> list[dict]:
	return frappe.get_all(
		"Parcel",
		filters={"booked_by": frappe.session.user},
		fields=[
			"name",
			"status",
			"payment_status",
			"sender_city",
			"recipient_city",
			"service_level",
			"is_return",
			"booked_on",
		],
		order_by="booked_on desc",
	)


# ---------------------------------------------------------------------------
# Payment (Razorpay)
# ---------------------------------------------------------------------------


def _load_own_draft_parcel(parcel: str):
	doc = frappe.get_doc("Parcel", parcel)
	if not doc.has_permission("read"):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	return doc


@frappe.whitelist()
def create_payment_order(parcel: str) -> dict:
	doc = _load_own_draft_parcel(parcel)
	if doc.payment_status == "Paid":
		frappe.throw(_("This parcel has already been paid for."))
	if doc.status != "Draft":
		frappe.throw(_("This parcel is not awaiting payment."))

	client = razorpay_client.get_client()
	amount_paise = int(round(doc.shipping_charge * 100))
	order = client.order.create(
		{
			"amount": amount_paise,
			"currency": "INR",
			"receipt": doc.name,
			"notes": {"parcel": doc.name},
		}
	)
	create_request_log(
		data={"amount": amount_paise, "currency": "INR", "receipt": doc.name},
		service_name="Courier Razorpay",
		reference_doctype="Parcel",
		reference_docname=doc.name,
		request_id=order["id"],
		output=order,
		status="Queued",
	)
	frappe.db.set_value("Parcel", doc.name, "razorpay_order_id", order["id"])
	settings = razorpay_client.get_settings()
	return {
		"order_id": order["id"],
		"amount": amount_paise,
		"currency": "INR",
		"key": settings.api_key,
		"name": frappe.db.get_single_value("Courier Settings", "company_display_name") or "Courier App",
	}


@frappe.whitelist()
def verify_payment(
	parcel: str, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str
) -> dict:
	"""Client-side checkout success callback. Fast, but NOT the sole source
	of truth - the webhook below is authoritative and idempotent against
	this in either firing order."""
	doc = _load_own_draft_parcel(parcel)
	if doc.payment_status == "Paid":
		return {"status": "Paid"}

	import razorpay.errors

	client = razorpay_client.get_client()
	try:
		client.utility.verify_payment_signature(
			{
				"razorpay_order_id": razorpay_order_id,
				"razorpay_payment_id": razorpay_payment_id,
				"razorpay_signature": razorpay_signature,
			}
		)
	except razorpay.errors.SignatureVerificationError:
		_log_integration_failure(doc.name, razorpay_order_id, _("Signature verification failed"))
		frappe.throw(_("Payment verification failed."))

	_mark_parcel_paid(doc.name, razorpay_payment_id, razorpay_order_id)
	return {"status": "Paid"}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def razorpay_webhook():
	"""Authoritative, idempotent payment confirmation path. Razorpay calls
	this directly (no browser session involved), and may retry delivery on
	anything but a 2xx response - so every recognised-but-already-processed
	event must still return success, not re-apply side effects."""
	body = frappe.request.get_data()
	signature = frappe.get_request_header("X-Razorpay-Signature")
	return process_webhook_payload(body, signature)


def process_webhook_payload(body: bytes, signature: str | None) -> dict:
	"""The actual webhook logic, split out from `razorpay_webhook` so it can
	be unit tested with a raw body/signature pair, without needing a real
	HTTP request context."""
	if not _verify_webhook_signature(body, signature):
		frappe.local.response.http_status_code = 400
		return {"status": "invalid signature"}

	payload = json.loads(body)
	event = payload.get("event")

	if event != "payment.captured":
		# Acknowledge anything we don't act on so Razorpay stops retrying it.
		return {"status": "ignored"}

	payment_entity = payload["payload"]["payment"]["entity"]
	order_id = payment_entity["order_id"]
	payment_id = payment_entity["id"]

	parcel_name = frappe.db.get_value("Parcel", {"razorpay_order_id": order_id}, "name")
	if not parcel_name:
		create_request_log(
			data=payload,
			service_name="Courier Razorpay",
			request_id=order_id,
			is_remote_request=1,
			status="Failed",
			error=f"No Parcel found for Razorpay order {order_id}",
		)
		frappe.local.response.http_status_code = 200
		return {"status": "no matching parcel"}

	_mark_parcel_paid(parcel_name, payment_id, order_id)
	return {"status": "ok"}


def _verify_webhook_signature(body: bytes, signature: str | None) -> bool:
	if not signature:
		return False
	secret = razorpay_client.get_webhook_secret()
	expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected, signature)


def _log_integration_failure(parcel: str, order_id: str, error: str):
	ir_name = frappe.db.get_value("Integration Request", {"reference_docname": parcel, "request_id": order_id})
	if ir_name:
		frappe.db.set_value("Integration Request", ir_name, {"status": "Failed", "error": error})


def _mark_parcel_paid(parcel_name: str, payment_id: str, order_id: str):
	"""The single source of truth for 'payment confirmed'. Called from both
	the client-side verify callback and the webhook - whichever fires
	first wins, the other is a guaranteed no-op. This is what makes a
	retry (of either path, or both, in any order) unable to double-charge
	or create a duplicate shipment side effect."""
	payment_status = frappe.db.get_value("Parcel", parcel_name, "payment_status")
	if payment_status == "Paid":
		return

	frappe.db.set_value(
		"Parcel",
		parcel_name,
		{
			"payment_status": "Paid",
			"razorpay_payment_id": payment_id,
			"status": "Booked & Paid",
		},
		update_modified=True,
	)
	ir_name = frappe.db.get_value("Integration Request", {"reference_docname": parcel_name, "request_id": order_id})
	if ir_name:
		frappe.db.set_value(
			"Integration Request",
			ir_name,
			{"status": "Completed", "output": frappe.as_json({"payment_id": payment_id})},
		)
	frappe.db.commit()


@frappe.whitelist(methods=["GET"])
def download_label_pdf(parcel: str):
	from frappe.utils.print_format import download_pdf

	doc = frappe.get_doc("Parcel", parcel)
	if not doc.has_permission("read"):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	if doc.payment_status not in ("Paid", "Waived"):
		frappe.throw(_("The shipping label can only be printed after payment is confirmed."))
	download_pdf(doctype="Parcel", name=parcel, format="Courier Shipping Label", doc=doc)


# ---------------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def get_tracking_timeline(token: str | None = None, parcel: str | None = None) -> dict:
	"""Public (token-bearer) or authenticated-owner tracking lookup. The
	unguessable, signed token IS the credential for guest access - anyone
	holding it (e.g. the recipient, who never logged in) can track the
	parcel; anyone else must be its logged-in owner."""
	from courier_app.courier_app.utils.token import resolve_token

	if token:
		parcel_name = resolve_token(token)
		if not parcel_name:
			frappe.throw(_("Invalid or unrecognised tracking token."))
	elif parcel:
		doc = frappe.get_doc("Parcel", parcel)
		if not doc.has_permission("read"):
			frappe.throw(_("Not permitted."), frappe.PermissionError)
		parcel_name = doc.name
	else:
		frappe.throw(_("Provide a tracking token or parcel name."))

	parcel_doc = frappe.db.get_value(
		"Parcel",
		parcel_name,
		[
			"name",
			"status",
			"payment_status",
			"origin_hub",
			"destination_hub",
			"current_hub",
			"sender_city",
			"recipient_city",
			"is_return",
			"original_parcel",
			"booked_on",
			"token",
		],
		as_dict=True,
	)
	events = frappe.get_all(
		"Scan Event",
		filters={"parcel": parcel_name, "is_duplicate": 0},
		fields=["scan_type", "hub", "resulting_status", "scanned_at", "failure_reason"],
		order_by="scanned_at asc",
		ignore_permissions=True,
	)
	return {"parcel": parcel_doc, "events": events}


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------


@frappe.whitelist()
def request_return(parcel: str) -> dict:
	original = frappe.get_doc("Parcel", parcel)
	if not original.has_permission("read"):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	if original.status != "Delivered":
		frappe.throw(_("Only a Delivered parcel can be returned."))
	if frappe.db.exists("Parcel", {"original_parcel": original.name}):
		frappe.throw(_("A return has already been raised for this parcel."))

	return_doc = frappe.get_doc(
		{
			"doctype": "Parcel",
			"booked_by": frappe.session.user,
			"is_return": 1,
			"original_parcel": original.name,
			"status": "Booked & Paid",
			"payment_status": "Waived",
			# sender/recipient swapped: the original recipient now ships back
			# to the original sender.
			"sender_name": original.recipient_name,
			"sender_phone": original.recipient_phone,
			"sender_email": original.recipient_email,
			"sender_address_line1": original.recipient_address_line1,
			"sender_address_line2": original.recipient_address_line2,
			"sender_city": original.recipient_city,
			"sender_state": original.recipient_state,
			"sender_pincode": original.recipient_pincode,
			"sender_country": original.recipient_country,
			"recipient_name": original.sender_name,
			"recipient_phone": original.sender_phone,
			"recipient_email": original.sender_email,
			"recipient_address_line1": original.sender_address_line1,
			"recipient_address_line2": original.sender_address_line2,
			"recipient_city": original.sender_city,
			"recipient_state": original.sender_state,
			"recipient_pincode": original.sender_pincode,
			"recipient_country": original.sender_country,
			# hubs swapped: origin of the return leg is the original destination.
			"origin_hub": original.destination_hub,
			"destination_hub": original.origin_hub,
			"service_level": original.service_level,
			"weight_kg": original.weight_kg,
			"length_cm": original.length_cm,
			"width_cm": original.width_cm,
			"height_cm": original.height_cm,
			"declared_value": original.declared_value,
		}
	)
	return_doc.insert(ignore_permissions=True)
	return {"name": return_doc.name}


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


@frappe.whitelist()
def record_scan(token: str, scan_type: str, hub: str | None = None, failure_reason: str | None = None) -> dict:
	return _record_scan(
		token=token, scan_type=scan_type, hub=hub, user=frappe.session.user, failure_reason=failure_reason
	)
