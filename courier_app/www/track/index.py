# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.sessions import get_csrf_token

from courier_app.courier_app.utils.token import resolve_token

no_cache = 1


def get_context(context):
	token = frappe.form_dict.get("token")
	parcel_name = frappe.form_dict.get("parcel")

	if token:
		parcel_name = resolve_token(token)
		if not parcel_name:
			frappe.throw(_("Invalid or unrecognised tracking token."), frappe.DoesNotExistError)
	elif parcel_name:
		if frappe.session.user == "Guest":
			frappe.local.flags.redirect_location = f"/login?redirect-to=/track?parcel={parcel_name}"
			raise frappe.Redirect
		doc = frappe.get_doc("Parcel", parcel_name)
		if not doc.has_permission("read"):
			frappe.throw(_("You do not have access to this parcel."), frappe.PermissionError)
	else:
		frappe.throw(_("Provide a tracking token or parcel name."), frappe.DoesNotExistError)

	context.title = _("Track Parcel")
	context.show_sidebar = False
	context.csrf_token = get_csrf_token()
	context.token = token or ""
	context.parcel_name = parcel_name
