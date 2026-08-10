# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt
"""Post-install provisioning so `bench install-app courier_app` is fully
self-contained: no manual role creation, no manual secret setup."""

import frappe

#: role_name -> desk_access. Desk access matters: Courier Manager is
#: ops/admin staff and needs it; Delivery Agent and Courier Customer are
#: portal-only personas by design ("no desk access" per the product spec)
#: and must NOT have it.
CUSTOM_ROLES = {
	"Courier Manager": 1,
	"Delivery Agent": 0,
	"Courier Customer": 0,
}


def after_install():
	_create_roles()
	_ensure_courier_settings()
	_ensure_razorpay_settings()
	frappe.db.commit()


def _create_roles():
	for role_name, desk_access in CUSTOM_ROLES.items():
		# DocType sync (which runs before after_install) auto-creates any
		# Role referenced in a doctype's permissions that doesn't exist yet
		# - always with desk_access=1. So these roles may already exist by
		# the time we get here; always enforce our intended values rather
		# than skip-if-exists, or that auto-created default silently wins.
		if frappe.db.exists("Role", role_name):
			frappe.db.set_value("Role", role_name, {"desk_access": desk_access, "is_custom": 1})
		else:
			frappe.get_doc(
				{"doctype": "Role", "role_name": role_name, "desk_access": desk_access, "is_custom": 1}
			).insert(ignore_permissions=True)


def _ensure_courier_settings():
	settings = frappe.get_single("Courier Settings")
	if not settings.get_password("token_signing_secret", raise_exception=False):
		settings.token_signing_secret = frappe.generate_hash(length=50)
		settings.save(ignore_permissions=True)


def _ensure_razorpay_settings():
	# Just make sure the single document row exists so Desk doesn't 404 on
	# first visit; keys are left blank for the user to fill in later.
	if not frappe.db.exists("Courier Razorpay Settings", "Courier Razorpay Settings"):
		frappe.get_doc({"doctype": "Courier Razorpay Settings"}).insert(ignore_permissions=True)
