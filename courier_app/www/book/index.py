# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.sessions import get_csrf_token

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/book"
		raise frappe.Redirect

	context.title = _("Book a Parcel")
	context.csrf_token = get_csrf_token()
	context.show_sidebar = False
