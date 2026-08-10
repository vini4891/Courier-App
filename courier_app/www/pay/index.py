# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.sessions import get_csrf_token

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/pay"
		raise frappe.Redirect

	parcel_name = frappe.form_dict.get("parcel")
	if not parcel_name:
		frappe.throw(_("No parcel specified."), frappe.DoesNotExistError)

	doc = frappe.get_doc("Parcel", parcel_name)
	if not doc.has_permission("read"):
		frappe.throw(_("You do not have access to this parcel."), frappe.PermissionError)

	if doc.payment_status in ("Paid", "Waived"):
		frappe.local.flags.redirect_location = f"/label?parcel={parcel_name}"
		raise frappe.Redirect

	context.title = _("Pay for Shipment")
	context.csrf_token = get_csrf_token()
	context.show_sidebar = False
	context.parcel = doc
