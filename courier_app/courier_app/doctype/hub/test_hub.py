# Copyright (c) 2026, Dheeraj and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestHub(IntegrationTestCase):
	"""Integration tests for Hub."""

	def test_hub_code_normalised_to_upper(self):
		hub = frappe.get_doc(
			{
				"doctype": "Hub",
				"hub_code": "test-hub-01",
				"hub_name": "Test Hub 01",
				"city": "Testville",
			}
		).insert(ignore_permissions=True)
		self.assertEqual(hub.name, "TEST-HUB-01")
		hub.delete(ignore_permissions=True)
