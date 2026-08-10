# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ServiceLevel(Document):
	pass


@frappe.whitelist()
def get_active_service_levels() -> list[dict]:
	"""Booking-page helper: list active service levels with their rates.
	Deliberately bypasses doctype-level read permission (Courier Customer
	has none) since this is a curated, non-sensitive read used to populate
	a public booking form."""
	return frappe.get_all(
		"Service Level",
		filters={"is_active": 1},
		fields=["name", "service_level_name", "description", "base_rate", "rate_per_kg", "estimated_transit_days"],
		order_by="base_rate asc",
		ignore_permissions=True,
	)
