# Copyright (c) 2026, Dheeraj and Contributors
# See license.txt
"""Payment flow tests. All Razorpay SDK calls are mocked at the
`courier_app.courier_app.razorpay_client` boundary - no network I/O."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from courier_app.courier_app.api import (
	create_payment_order,
	process_webhook_payload,
	verify_payment,
)
from courier_app.courier_app.test_utils import create_test_user

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []
# Note: this file lives under doctype/parcel/, so the test framework
# resolves its doctype as "Parcel" and reads dependency overrides from the
# canonical test_parcel.py (see IGNORE_TEST_RECORD_DEPENDENCIES there),
# not from this module - declared here too only for clarity.


def _make_hub(code, city):
	if frappe.db.exists("Hub", code):
		return code
	return frappe.get_doc(
		{"doctype": "Hub", "hub_code": code, "hub_name": f"{city} Hub", "city": city}
	).insert(ignore_permissions=True).name


def _make_service_level(name="Test Payment SL"):
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


def _make_customer_user(email="test_payment_customer@example.com"):
	return create_test_user(email, "Payer", roles=["Courier Customer"])


class IntegrationTestParcelPayment(IntegrationTestCase):
	def setUp(self):
		self.origin = _make_hub("TEST-PAY-DEL", "Delhi")
		self.destination = _make_hub("TEST-PAY-PUN", "Pune")
		self.service_level = _make_service_level()
		self.customer = _make_customer_user()

	def tearDown(self):
		# _mark_parcel_paid deliberately calls frappe.db.commit() (payment
		# confirmation must be durable immediately) - which means these
		# rows survive the test framework's end-of-class rollback. Clean
		# them up explicitly so the tests don't leave residue on the site.
		for parcel_name in getattr(self, "_created_parcels", []):
			frappe.db.delete("Integration Request", {"reference_docname": parcel_name})
			frappe.db.delete("Scan Event", {"parcel": parcel_name})
			frappe.db.delete("Parcel", {"name": parcel_name})
		frappe.db.commit()
		super().tearDown()

	def _make_draft_parcel(self):
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
		self._created_parcels = getattr(self, "_created_parcels", [])
		self._created_parcels.append(doc.name)
		return doc.name

	def test_create_payment_order_logs_integration_request(self):
		parcel_name = self._make_draft_parcel()
		mock_client = MagicMock()
		mock_client.order.create.return_value = {"id": "order_test_001"}

		with patch("courier_app.courier_app.razorpay_client.get_client", return_value=mock_client):
			frappe.set_user(self.customer)
			try:
				result = create_payment_order(parcel_name)
			finally:
				frappe.set_user("Administrator")

		self.assertEqual(result["order_id"], "order_test_001")
		mock_client.order.create.assert_called_once()
		self.assertEqual(frappe.db.get_value("Parcel", parcel_name, "razorpay_order_id"), "order_test_001")

		ir_name = frappe.db.get_value(
			"Integration Request", {"reference_docname": parcel_name, "request_id": "order_test_001"}
		)
		self.assertTrue(ir_name)

	def test_verify_payment_marks_parcel_paid_and_is_idempotent_on_replay(self):
		parcel_name = self._make_draft_parcel()
		frappe.db.set_value("Parcel", parcel_name, "razorpay_order_id", "order_test_002")
		frappe.get_doc(
			{
				"doctype": "Integration Request",
				"integration_request_service": "Courier Razorpay",
				"reference_doctype": "Parcel",
				"reference_docname": parcel_name,
				"request_id": "order_test_002",
				"status": "Queued",
			}
		).insert(ignore_permissions=True)

		mock_client = MagicMock()
		mock_client.utility.verify_payment_signature.return_value = True

		with patch("courier_app.courier_app.razorpay_client.get_client", return_value=mock_client):
			frappe.set_user(self.customer)
			try:
				verify_payment(parcel_name, "order_test_002", "pay_test_002", "sig_002")
				# Replay: same call again must be a no-op, not a second charge/side-effect.
				verify_payment(parcel_name, "order_test_002", "pay_test_002", "sig_002")
			finally:
				frappe.set_user("Administrator")

		self.assertEqual(mock_client.utility.verify_payment_signature.call_count, 1)
		doc = frappe.get_doc("Parcel", parcel_name)
		self.assertEqual(doc.payment_status, "Paid")
		self.assertEqual(doc.status, "Booked & Paid")
		self.assertEqual(doc.razorpay_payment_id, "pay_test_002")

		ir_name = frappe.db.get_value(
			"Integration Request", {"reference_docname": parcel_name, "request_id": "order_test_002"}
		)
		self.assertEqual(frappe.db.get_value("Integration Request", ir_name, "status"), "Completed")

	def test_verify_payment_rejects_bad_signature(self):
		import razorpay.errors

		parcel_name = self._make_draft_parcel()
		frappe.db.set_value("Parcel", parcel_name, "razorpay_order_id", "order_test_003")

		mock_client = MagicMock()
		mock_client.utility.verify_payment_signature.side_effect = razorpay.errors.SignatureVerificationError(
			"bad signature"
		)

		with patch("courier_app.courier_app.razorpay_client.get_client", return_value=mock_client):
			frappe.set_user(self.customer)
			try:
				with self.assertRaises(frappe.ValidationError):
					verify_payment(parcel_name, "order_test_003", "pay_test_003", "bad-sig")
			finally:
				frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Parcel", parcel_name, "payment_status"), "Pending")

	def test_webhook_payment_captured_is_idempotent_on_retry(self):
		parcel_name = self._make_draft_parcel()
		frappe.db.set_value("Parcel", parcel_name, "razorpay_order_id", "order_test_004")

		body, signature = self._signed_webhook_body("order_test_004", "pay_test_004")

		with patch("courier_app.courier_app.razorpay_client.get_webhook_secret", return_value="test-secret"):
			result1 = process_webhook_payload(body, signature)
			result2 = process_webhook_payload(body, signature)

		self.assertEqual(result1["status"], "ok")
		self.assertEqual(result2["status"], "ok")
		doc = frappe.get_doc("Parcel", parcel_name)
		self.assertEqual(doc.payment_status, "Paid")
		self.assertEqual(doc.razorpay_payment_id, "pay_test_004")

	def test_webhook_rejects_bad_signature(self):
		parcel_name = self._make_draft_parcel()
		frappe.db.set_value("Parcel", parcel_name, "razorpay_order_id", "order_test_005")
		body, _ = self._signed_webhook_body("order_test_005", "pay_test_005")

		with patch("courier_app.courier_app.razorpay_client.get_webhook_secret", return_value="test-secret"):
			result = process_webhook_payload(body, "not-the-right-signature")

		self.assertEqual(result["status"], "invalid signature")
		self.assertEqual(frappe.db.get_value("Parcel", parcel_name, "payment_status"), "Pending")

	def test_client_verify_then_webhook_race_is_safe(self):
		parcel_name = self._make_draft_parcel()
		frappe.db.set_value("Parcel", parcel_name, "razorpay_order_id", "order_test_006")

		mock_client = MagicMock()
		mock_client.utility.verify_payment_signature.return_value = True
		with patch("courier_app.courier_app.razorpay_client.get_client", return_value=mock_client):
			frappe.set_user(self.customer)
			try:
				verify_payment(parcel_name, "order_test_006", "pay_test_006", "sig_006")
			finally:
				frappe.set_user("Administrator")

		body, signature = self._signed_webhook_body("order_test_006", "pay_test_006")
		with patch("courier_app.courier_app.razorpay_client.get_webhook_secret", return_value="test-secret"):
			result = process_webhook_payload(body, signature)

		self.assertEqual(result["status"], "ok")
		self.assertEqual(frappe.db.get_value("Parcel", parcel_name, "payment_status"), "Paid")

	def test_webhook_then_client_verify_race_is_safe(self):
		parcel_name = self._make_draft_parcel()
		frappe.db.set_value("Parcel", parcel_name, "razorpay_order_id", "order_test_007")

		body, signature = self._signed_webhook_body("order_test_007", "pay_test_007")
		with patch("courier_app.courier_app.razorpay_client.get_webhook_secret", return_value="test-secret"):
			process_webhook_payload(body, signature)

		mock_client = MagicMock()
		mock_client.utility.verify_payment_signature.return_value = True
		with patch("courier_app.courier_app.razorpay_client.get_client", return_value=mock_client):
			frappe.set_user(self.customer)
			try:
				result = verify_payment(parcel_name, "order_test_007", "pay_test_007", "sig_007")
			finally:
				frappe.set_user("Administrator")

		# already Paid by the webhook - verify_payment must short-circuit
		# without re-checking the (now irrelevant) signature.
		mock_client.utility.verify_payment_signature.assert_not_called()
		self.assertEqual(result["status"], "Paid")

	@staticmethod
	def _signed_webhook_body(order_id, payment_id):
		payload = {
			"event": "payment.captured",
			"payload": {"payment": {"entity": {"id": payment_id, "order_id": order_id}}},
		}
		body = json.dumps(payload).encode()
		signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
		return body, signature
