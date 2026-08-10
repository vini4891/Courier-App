# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.sessions import get_csrf_token

from courier_app.courier_app.doctype.delivery_agent.delivery_agent import is_active_agent

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/scanner"
		raise frappe.Redirect

	if not is_active_agent():
		frappe.local.response["http_status_code"] = 403
		context.error_message = _(
			"Your account is not registered as an active Delivery Agent. Contact Courier Ops."
		)
		frappe.throw(context.error_message, frappe.PermissionError)

	context.title = _("Scanner")
	context.csrf_token = get_csrf_token()
	context.show_sidebar = False
