# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from courier_app.courier_app.utils.token import get_qr_svg_base64

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/label"
		raise frappe.Redirect

	parcel_name = frappe.form_dict.get("parcel")
	if not parcel_name:
		frappe.throw(_("No parcel specified."), frappe.DoesNotExistError)

	doc = frappe.get_doc("Parcel", parcel_name)
	if not doc.has_permission("read"):
		frappe.throw(_("You do not have access to this parcel."), frappe.PermissionError)

	if doc.payment_status not in ("Paid", "Waived"):
		frappe.local.flags.redirect_location = f"/pay?parcel={parcel_name}"
		raise frappe.Redirect

	context.title = _("Shipping Label")
	context.show_sidebar = False
	context.parcel = doc
	context.qr_base64 = get_qr_svg_base64(doc.token)
