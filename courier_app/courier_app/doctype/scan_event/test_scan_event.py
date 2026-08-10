# Copyright (c) 2026, Dheeraj and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from courier_app.courier_app.doctype.scan_event.scan_event import record_scan
from courier_app.courier_app.test_utils import create_test_user

EXTRA_TEST_RECORD_DEPENDENCIES = []
# See test_parcel.py for why core's bundled User fixtures are skipped.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


def _make_hub(code, city):
	if frappe.db.exists("Hub", code):
		return code
	return frappe.get_doc(
		{"doctype": "Hub", "hub_code": code, "hub_name": f"{city} Hub", "city": city}
	).insert(ignore_permissions=True).name


def _make_service_level(name="Test Standard"):
	if frappe.db.exists("Service Level", name):
		return name
	return frappe.get_doc(
		{
			"doctype": "Service Level",
			"service_level_name": name,
			"base_rate": 50,
			"rate_per_kg": 10,
			"estimated_transit_days": 3,
		}
	).insert(ignore_permissions=True).name


def _make_agent_user(email="test_scan_agent@example.com"):
	create_test_user(email, "Scan", roles=["Delivery Agent"])
	if not frappe.db.exists("Delivery Agent", {"user": email}):
		frappe.get_doc(
			{"doctype": "Delivery Agent", "agent_name": "Scan Test Agent", "user": email, "phone": "999"}
		).insert(ignore_permissions=True)
	return email


def _make_paid_parcel(origin, destination, agent_user):
	parcel = frappe.get_doc(
		{
			"doctype": "Parcel",
			"booked_by": agent_user,
			"sender_name": "Sender",
			"sender_phone": "1",
			"sender_address_line1": "Addr",
			"sender_city": "Delhi",
			"sender_pincode": "110001",
			"recipient_name": "Recipient",
			"recipient_phone": "2",
			"recipient_address_line1": "Addr",
			"recipient_city": "Pune",
			"recipient_pincode": "411001",
			"origin_hub": origin,
			"destination_hub": destination,
			"service_level": _make_service_level(),
			"weight_kg": 1,
		}
	)
	parcel.insert(ignore_permissions=True)
	frappe.db.set_value("Parcel", parcel.name, {"payment_status": "Paid", "status": "Booked & Paid"})
	return parcel.name


class IntegrationTestScanEvent(IntegrationTestCase):
	def setUp(self):
		self.origin = _make_hub("TEST-DEL", "Delhi")
		self.destination = _make_hub("TEST-PUN", "Pune")
		self.agent_user = _make_agent_user()

	def test_record_scan_advances_parcel_status(self):
		parcel = _make_paid_parcel(self.origin, self.destination, self.agent_user)
		token = frappe.db.get_value("Parcel", parcel, "token")

		result = record_scan(token=token, scan_type="Pickup", hub=self.origin, user=self.agent_user)
		self.assertFalse(result["is_duplicate"])
		self.assertEqual(result["status"], "Picked Up")
		self.assertEqual(frappe.db.get_value("Parcel", parcel, "status"), "Picked Up")
		self.assertEqual(frappe.db.get_value("Parcel", parcel, "current_hub"), self.origin)

	def test_duplicate_scan_persists_row_without_state_change(self):
		parcel = _make_paid_parcel(self.origin, self.destination, self.agent_user)
		token = frappe.db.get_value("Parcel", parcel, "token")

		record_scan(token=token, scan_type="Pickup", hub=self.origin, user=self.agent_user)
		before_count = frappe.db.count("Scan Event", {"parcel": parcel})

		result = record_scan(token=token, scan_type="Pickup", hub=self.origin, user=self.agent_user)
		self.assertTrue(result["is_duplicate"])
		self.assertEqual(result["status"], "Picked Up")
		self.assertEqual(frappe.db.get_value("Parcel", parcel, "status"), "Picked Up")

		after_count = frappe.db.count("Scan Event", {"parcel": parcel})
		self.assertEqual(after_count, before_count + 1, "duplicate scan should still be logged")

	def test_illegal_scan_is_rejected_and_not_logged(self):
		parcel = _make_paid_parcel(self.origin, self.destination, self.agent_user)
		token = frappe.db.get_value("Parcel", parcel, "token")
		before_count = frappe.db.count("Scan Event", {"parcel": parcel})

		with self.assertRaises(frappe.ValidationError):
			record_scan(token=token, scan_type="Delivered", hub=None, user=self.agent_user)

		after_count = frappe.db.count("Scan Event", {"parcel": parcel})
		self.assertEqual(after_count, before_count, "illegal scan must not be logged")
		self.assertEqual(frappe.db.get_value("Parcel", parcel, "status"), "Booked & Paid")

	def test_invalid_token_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			record_scan(token="not-a-real-token.abc123", scan_type="Pickup", hub=self.origin, user=self.agent_user)

	def test_inactive_or_non_agent_user_cannot_scan(self):
		parcel = _make_paid_parcel(self.origin, self.destination, self.agent_user)
		token = frappe.db.get_value("Parcel", parcel, "token")
		with self.assertRaises(frappe.PermissionError):
			record_scan(token=token, scan_type="Pickup", hub=self.origin, user="Administrator")

	def test_append_only_update_is_blocked(self):
		parcel = _make_paid_parcel(self.origin, self.destination, self.agent_user)
		token = frappe.db.get_value("Parcel", parcel, "token")
		record_scan(token=token, scan_type="Pickup", hub=self.origin, user=self.agent_user)

		event_name = frappe.db.get_value("Scan Event", {"parcel": parcel}, "name")
		doc = frappe.get_doc("Scan Event", event_name)
		doc.hub = self.destination
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_append_only_delete_is_blocked(self):
		parcel = _make_paid_parcel(self.origin, self.destination, self.agent_user)
		token = frappe.db.get_value("Parcel", parcel, "token")
		record_scan(token=token, scan_type="Pickup", hub=self.origin, user=self.agent_user)

		event_name = frappe.db.get_value("Scan Event", {"parcel": parcel}, "name")
		doc = frappe.get_doc("Scan Event", event_name)
		with self.assertRaises(frappe.PermissionError):
			doc.delete(ignore_permissions=True)
