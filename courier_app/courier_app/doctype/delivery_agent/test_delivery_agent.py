# Copyright (c) 2026, Dheeraj and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from courier_app.courier_app.test_utils import create_test_user

EXTRA_TEST_RECORD_DEPENDENCIES = []
# See test_parcel.py for why core's bundled User fixtures are skipped.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


class IntegrationTestDeliveryAgent(IntegrationTestCase):
	"""Integration tests for Delivery Agent."""

	def test_duplicate_user_rejected(self):
		user = create_test_user("test_delivery_agent_dup@example.com", "Dup")

		agent1 = frappe.get_doc(
			{"doctype": "Delivery Agent", "agent_name": "Agent One", "user": user, "phone": "111"}
		).insert(ignore_permissions=True)

		agent2 = frappe.get_doc(
			{"doctype": "Delivery Agent", "agent_name": "Agent Two", "user": user, "phone": "222"}
		)
		self.assertRaises(frappe.ValidationError, agent2.insert, ignore_permissions=True)

		agent1.delete(ignore_permissions=True)
		frappe.delete_doc("User", user, force=True, ignore_permissions=True)
