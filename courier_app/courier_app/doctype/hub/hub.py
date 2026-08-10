# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Hub(Document):
	def before_insert(self):
		# autoname (field:hub_code) reads the field value at set_new_name()
		# time, which runs right after before_insert - normalise here so
		# name and hub_code always agree.
		self.hub_code = (self.hub_code or "").strip().upper()

	def validate(self):
		self.hub_code = (self.hub_code or "").strip().upper()


@frappe.whitelist()
def get_hub_for_city(city: str) -> str | None:
	"""Resolve a city name to its active serving Hub. Used by the booking
	portal page so customers pick a city, not an internal hub code."""
	if not city:
		return None
	return frappe.db.get_value("Hub", {"city": city, "is_active": 1}, "name")


@frappe.whitelist()
def get_active_hubs() -> list[dict]:
	"""Scanner-page helper: list active hubs an agent can declare as their
	current location. Bypasses doctype read permission the same way
	Service Level's booking-page helper does - a curated, non-sensitive
	read for an authenticated portal user."""
	return frappe.get_all(
		"Hub",
		filters={"is_active": 1},
		fields=["name", "hub_name", "city"],
		order_by="hub_name asc",
		ignore_permissions=True,
	)
