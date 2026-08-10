# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.sessions import get_csrf_token

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/return"
		raise frappe.Redirect

	parcel_name = frappe.form_dict.get("parcel")
	if not parcel_name:
		frappe.throw(_("No parcel specified."), frappe.DoesNotExistError)

	doc = frappe.get_doc("Parcel", parcel_name)
	if not doc.has_permission("read"):
		frappe.throw(_("You do not have access to this parcel."), frappe.PermissionError)
	if doc.status != "Delivered":
		frappe.throw(_("Only a Delivered parcel can be returned."))
	if frappe.db.exists("Parcel", {"original_parcel": doc.name}):
		frappe.throw(_("A return has already been raised for this parcel."))

	context.title = _("Return Parcel")
	context.csrf_token = get_csrf_token()
	context.show_sidebar = False
	context.parcel = doc
