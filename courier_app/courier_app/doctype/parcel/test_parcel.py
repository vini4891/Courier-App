# Copyright (c) 2026, Dheeraj and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from courier_app.courier_app.api import book_parcel, request_return
from courier_app.courier_app.doctype.parcel.parcel import resolve_exception
from courier_app.courier_app.doctype.scan_event.scan_event import record_scan
from courier_app.courier_app.test_utils import create_test_user

EXTRA_TEST_RECORD_DEPENDENCIES = []
# Frappe's own bundled User test fixtures (test@example.com etc.) fail to
# load in this bench (pre-existing MandatoryError on `last_name`, unrelated
# to this app). Every test here creates its own dedicated test Users
# explicitly, so skip walking into core's User fixtures via the Parcel ->
# booked_by (Link User) dependency.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


def _make_hub(code, city):
	if frappe.db.exists("Hub", code):
		return code
	return frappe.get_doc(
		{"doctype": "Hub", "hub_code": code, "hub_name": f"{city} Hub", "city": city}
	).insert(ignore_permissions=True).name


def _make_service_level(name="Test Parcel SL"):
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


def _make_customer_user(email="test_parcel_customer@example.com"):
	return create_test_user(email, "Customer", roles=["Courier Customer"])


def _make_agent_user(email="test_parcel_agent@example.com"):
	create_test_user(email, "Agent", roles=["Delivery Agent"])
	if not frappe.db.exists("Delivery Agent", {"user": email}):
		frappe.get_doc(
			{"doctype": "Delivery Agent", "agent_name": "Parcel Test Agent", "user": email, "phone": "999"}
		).insert(ignore_permissions=True)
	return email


def _drive_to_delivered(parcel_name, origin, destination, agent_user):
	token = frappe.db.get_value("Parcel", parcel_name, "token")
	record_scan(token=token, scan_type="Pickup", hub=origin, user=agent_user)
	record_scan(token=token, scan_type="Hub In", hub=origin, user=agent_user)
	record_scan(token=token, scan_type="Hub Out", hub=origin, user=agent_user)
	record_scan(token=token, scan_type="Hub In", hub=destination, user=agent_user)
	record_scan(token=token, scan_type="Hub Out", hub=destination, user=agent_user)
	record_scan(token=token, scan_type="Delivered", hub=None, user=agent_user)


class IntegrationTestParcel(IntegrationTestCase):
	def setUp(self):
		self.origin = _make_hub("TEST-P-DEL", "Delhi")
		self.destination = _make_hub("TEST-P-PUN", "Pune")
		self.service_level = _make_service_level()
		self.customer = _make_customer_user()
		self.agent_user = _make_agent_user()

	def test_book_parcel_creates_draft_unpaid(self):
		frappe.set_user(self.customer)
		try:
			result = book_parcel(
				sender_name="A",
				sender_phone="1",
				sender_address_line1="Addr",
				sender_city="Delhi",
				sender_pincode="110001",
				recipient_name="B",
				recipient_phone="2",
				recipient_address_line1="Addr",
				recipient_city="Pune",
				recipient_pincode="411001",
				service_level=self.service_level,
				weight_kg=2,
			)
		finally:
			frappe.set_user("Administrator")

		doc = frappe.get_doc("Parcel", result["name"])
		self.assertEqual(doc.status, "Draft")
		self.assertEqual(doc.payment_status, "Pending")
		self.assertEqual(doc.booked_by, self.customer)
		self.assertTrue(doc.token)
		self.assertEqual(doc.shipping_charge, 50 + 10 * 2)

	def test_booking_rejected_for_unserved_city(self):
		frappe.set_user(self.customer)
		try:
			with self.assertRaises(frappe.ValidationError):
				book_parcel(
					sender_name="A",
					sender_phone="1",
					sender_address_line1="Addr",
					sender_city="Nowhereville",
					sender_pincode="000000",
					recipient_name="B",
					recipient_phone="2",
					recipient_address_line1="Addr",
					recipient_city="Pune",
					recipient_pincode="411001",
					service_level=self.service_level,
					weight_kg=1,
				)
		finally:
			frappe.set_user("Administrator")

	def test_status_field_is_immutable_via_direct_save(self):
		doc = frappe.get_doc(
			{
				"doctype": "Parcel",
				"booked_by": self.customer,
				"sender_name": "A",
				"sender_phone": "1",
				"sender_address_line1": "Addr",
				"sender_city": "Delhi",
				"sender_pincode": "110001",
				"recipient_name": "B",
				"recipient_phone": "2",
				"recipient_address_line1": "Addr",
				"recipient_city": "Pune",
				"recipient_pincode": "411001",
				"origin_hub": self.origin,
				"destination_hub": self.destination,
				"service_level": self.service_level,
				"weight_kg": 1,
			}
		).insert(ignore_permissions=True)

		doc.status = "Delivered"
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_full_reverse_flow_creates_swapped_return_parcel(self):
		frappe.set_user(self.customer)
		try:
			booked = book_parcel(
				sender_name="Meena",
				sender_phone="1",
				sender_address_line1="Addr",
				sender_city="Delhi",
				sender_pincode="110001",
				recipient_name="Raju",
				recipient_phone="2",
				recipient_address_line1="Addr",
				recipient_city="Pune",
				recipient_pincode="411001",
				service_level=self.service_level,
				weight_kg=1,
			)
		finally:
			frappe.set_user("Administrator")

		parcel_name = booked["name"]
		frappe.db.set_value("Parcel", parcel_name, {"payment_status": "Paid", "status": "Booked & Paid"})
		_drive_to_delivered(parcel_name, self.origin, self.destination, self.agent_user)
		self.assertEqual(frappe.db.get_value("Parcel", parcel_name, "status"), "Delivered")

		frappe.set_user(self.customer)
		try:
			returned = request_return(parcel_name)
		finally:
			frappe.set_user("Administrator")

		return_doc = frappe.get_doc("Parcel", returned["name"])
		self.assertTrue(return_doc.is_return)
		self.assertEqual(return_doc.original_parcel, parcel_name)
		self.assertEqual(return_doc.payment_status, "Waived")
		self.assertEqual(return_doc.status, "Booked & Paid")
		# hubs and parties are swapped
		self.assertEqual(return_doc.origin_hub, self.destination)
		self.assertEqual(return_doc.destination_hub, self.origin)
		self.assertEqual(return_doc.sender_name, "Raju")
		self.assertEqual(return_doc.recipient_name, "Meena")

		# the return leg can be driven through the exact same state machine,
		# back to the original sender
		_drive_to_delivered(return_doc.name, self.destination, self.origin, self.agent_user)
		self.assertEqual(frappe.db.get_value("Parcel", return_doc.name, "status"), "Delivered")

	def test_cannot_return_a_parcel_twice(self):
		frappe.set_user(self.customer)
		try:
			booked = book_parcel(
				sender_name="A",
				sender_phone="1",
				sender_address_line1="Addr",
				sender_city="Delhi",
				sender_pincode="110001",
				recipient_name="B",
				recipient_phone="2",
				recipient_address_line1="Addr",
				recipient_city="Pune",
				recipient_pincode="411001",
				service_level=self.service_level,
				weight_kg=1,
			)
		finally:
			frappe.set_user("Administrator")
		parcel_name = booked["name"]
		frappe.db.set_value("Parcel", parcel_name, {"payment_status": "Paid", "status": "Booked & Paid"})
		_drive_to_delivered(parcel_name, self.origin, self.destination, self.agent_user)

		frappe.set_user(self.customer)
		try:
			request_return(parcel_name)
			with self.assertRaises(frappe.ValidationError):
				request_return(parcel_name)
		finally:
			frappe.set_user("Administrator")

	def test_resolve_exception_only_allows_pre_exception_status(self):
		parcel_name = book_parcel_as_admin(self)
		frappe.db.set_value("Parcel", parcel_name, {"payment_status": "Paid", "status": "Booked & Paid"})
		token = frappe.db.get_value("Parcel", parcel_name, "token")
		record_scan(token=token, scan_type="Pickup", hub=self.origin, user=self.agent_user)
		record_scan(token=token, scan_type="Hub In", hub=self.origin, user=self.agent_user)
		record_scan(token=token, scan_type="Marked Stuck", hub=None, user=self.agent_user, failure_reason="Test")
		self.assertEqual(frappe.db.get_value("Parcel", parcel_name, "status"), "Stuck at Hub")

		with self.assertRaises(frappe.ValidationError):
			resolve_exception(parcel_name, "Delivered")

		resolve_exception(parcel_name, "In at Origin Hub")
		self.assertEqual(frappe.db.get_value("Parcel", parcel_name, "status"), "In at Origin Hub")
		self.assertIsNone(frappe.db.get_value("Parcel", parcel_name, "pre_exception_status"))


def book_parcel_as_admin(test_case):
	doc = frappe.get_doc(
		{
			"doctype": "Parcel",
			"booked_by": test_case.customer,
			"sender_name": "A",
			"sender_phone": "1",
			"sender_address_line1": "Addr",
			"sender_city": "Delhi",
			"sender_pincode": "110001",
			"recipient_name": "B",
			"recipient_phone": "2",
			"recipient_address_line1": "Addr",
			"recipient_city": "Pune",
			"recipient_pincode": "411001",
			"origin_hub": test_case.origin,
			"destination_hub": test_case.destination,
			"service_level": test_case.service_level,
			"weight_kg": 1,
		}
	).insert(ignore_permissions=True)
	return doc.name
