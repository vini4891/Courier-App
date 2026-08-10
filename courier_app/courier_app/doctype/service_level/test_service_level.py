# Copyright (c) 2026, Dheeraj and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestServiceLevel(IntegrationTestCase):
	"""Integration tests for Service Level."""

	def test_get_active_service_levels_excludes_inactive(self):
		from courier_app.courier_app.doctype.service_level.service_level import (
			get_active_service_levels,
		)

		active = frappe.get_doc(
			{
				"doctype": "Service Level",
				"service_level_name": "Test Active SL",
				"base_rate": 50,
				"rate_per_kg": 10,
				"estimated_transit_days": 2,
			}
		).insert(ignore_permissions=True)
		inactive = frappe.get_doc(
			{
				"doctype": "Service Level",
				"service_level_name": "Test Inactive SL",
				"base_rate": 40,
				"rate_per_kg": 8,
				"estimated_transit_days": 3,
				"is_active": 0,
			}
		).insert(ignore_permissions=True)

		names = {row["name"] for row in get_active_service_levels()}
		self.assertIn(active.name, names)
		self.assertNotIn(inactive.name, names)

		active.delete(ignore_permissions=True)
		inactive.delete(ignore_permissions=True)
