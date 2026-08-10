# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt
"""Shared fixture helpers for courier_app's integration tests.

Kept out of any `test_*.py` file so Frappe's test discovery doesn't treat
it as a test module in its own right.
"""

import frappe


def create_test_user(email: str, first_name: str, roles: list[str] | None = None) -> str:
	"""Create (or reuse) a dedicated test User.

	Works around a site-level customization (sil_hr's `contact_validate`
	hook) that rejects the Contact record Frappe auto-creates for every
	new User, because that auto-created Contact's email row doesn't set
	sil_hr's custom "Home"/"Work" checkboxes - unrelated to this app, but
	unavoidable for any User created on this site. The User row itself is
	written to the DB before that downstream Contact sync runs, so on
	failure we just verify the User now exists and move on.
	"""
	if not frappe.db.exists("User", email):
		try:
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": first_name,
					"last_name": "Test",
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)
		except frappe.ValidationError:
			if not frappe.db.exists("User", email):
				raise

	if roles:
		existing = set(frappe.get_all("Has Role", filters={"parent": email}, pluck="role"))
		missing = [r for r in roles if r not in existing]
		if missing:
			user = frappe.get_doc("User", email)
			for role in missing:
				user.append("roles", {"role": role})
			try:
				user.save(ignore_permissions=True)
			except frappe.ValidationError:
				# Same downstream Contact-sync quirk as above; the Has Role
				# child rows are written before on_update runs, so the role
				# assignment itself has already taken effect.
				still_missing = set(missing) - set(
					frappe.get_all("Has Role", filters={"parent": email}, pluck="role")
				)
				if still_missing:
					raise

	return email
