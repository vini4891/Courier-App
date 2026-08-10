# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt
"""Thin wrapper around the `razorpay` SDK client.

This is the ONLY place `razorpay.Client` gets constructed, and therefore
the sole seam unit tests patch (`unittest.mock.patch(
"courier_app.courier_app.razorpay_client.get_client")`) to run fully
offline, without touching Razorpay's network at all.
"""

import frappe
from frappe import _


def get_settings():
	return frappe.get_cached_doc("Courier Razorpay Settings")


def get_client():
	import razorpay

	settings = get_settings()
	if not settings.enabled:
		frappe.throw(_("Razorpay is not enabled. Configure Courier Razorpay Settings first."))
	secret = settings.get_password("api_secret", raise_exception=False)
	if not settings.api_key or not secret:
		frappe.throw(_("Razorpay API Key/Secret are not configured."))
	return razorpay.Client(auth=(settings.api_key, secret))


def get_webhook_secret() -> str:
	secret = get_settings().get_password("webhook_secret", raise_exception=False)
	if not secret:
		frappe.throw(_("Razorpay Webhook Secret is not configured."))
	return secret
