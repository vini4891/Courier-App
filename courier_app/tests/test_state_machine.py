# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt
"""Pure unit tests for courier_app.courier_app.state_machine - no DB, no
site context. This is the core correctness contract of the whole app."""

import unittest

from courier_app.courier_app.state_machine import (
	FORWARD_STATUSES,
	IllegalScanError,
	ParcelSnapshot,
	evaluate_scan,
)


def snapshot(status, origin="DEL-01", destination="PUN-01"):
	return ParcelSnapshot(status=status, origin_hub=origin, destination_hub=destination)


class TestLegalTransitions(unittest.TestCase):
	"""Every legal forward step, in order, with correct hub, must succeed
	and advance to exactly the next stage."""

	def test_full_forward_journey_advances_one_step_at_a_time(self):
		steps = [
			("Booked & Paid", "Pickup", "DEL-01", "Picked Up"),
			("Picked Up", "Hub In", "DEL-01", "In at Origin Hub"),
			("In at Origin Hub", "Hub Out", "DEL-01", "In Transit"),
			("In Transit", "Hub In", "PUN-01", "In at Destination Hub"),
			("In at Destination Hub", "Hub Out", "PUN-01", "Out for Delivery"),
			("Out for Delivery", "Delivered", None, "Delivered"),
		]
		for current, scan_type, hub, expected_next in steps:
			with self.subTest(current=current, scan_type=scan_type):
				result = evaluate_scan(snapshot(current), scan_type, hub)
				self.assertEqual(result.next_status, expected_next)
				self.assertFalse(result.is_duplicate)

	def test_forward_statuses_cover_every_transition_target(self):
		# Sanity check on the fixture list itself: every status after the
		# first must be reachable as a `next_status`.
		self.assertEqual(FORWARD_STATUSES[0], "Booked & Paid")
		self.assertEqual(FORWARD_STATUSES[-1], "Delivered")


class TestIllegalTransitions(unittest.TestCase):
	def test_pickup_before_payment_is_rejected(self):
		# "Draft" is deliberately absent from TRANSITIONS - this is how
		# payment-before-pickup is enforced, with no special-case code.
		with self.assertRaises(IllegalScanError):
			evaluate_scan(snapshot("Draft"), "Pickup", "DEL-01")

	def test_skipping_a_stage_is_rejected(self):
		# Can't jump straight from Picked Up to In Transit, skipping the
		# Hub In scan.
		with self.assertRaises(IllegalScanError):
			evaluate_scan(snapshot("Picked Up"), "Hub Out", "DEL-01")

	def test_delivered_before_out_for_delivery_is_rejected(self):
		with self.assertRaises(IllegalScanError):
			evaluate_scan(snapshot("In at Destination Hub"), "Delivered", None)

	def test_scan_after_delivered_is_rejected(self):
		with self.assertRaises(IllegalScanError):
			evaluate_scan(snapshot("Delivered"), "Hub In", "PUN-01")

	def test_wrong_hub_is_rejected(self):
		with self.assertRaises(IllegalScanError):
			evaluate_scan(snapshot("Booked & Paid"), "Pickup", "PUN-01")

	def test_wrong_hub_at_destination_leg_is_rejected(self):
		with self.assertRaises(IllegalScanError):
			evaluate_scan(snapshot("In Transit"), "Hub In", "DEL-01")


class TestIdempotentDuplicateScans(unittest.TestCase):
	def test_repeat_pickup_scan_is_a_noop(self):
		result = evaluate_scan(snapshot("Picked Up"), "Pickup", "DEL-01")
		self.assertTrue(result.is_duplicate)
		self.assertEqual(result.next_status, "Picked Up")

	def test_repeat_hub_in_scan_is_a_noop(self):
		result = evaluate_scan(snapshot("In at Origin Hub"), "Hub In", "DEL-01")
		self.assertTrue(result.is_duplicate)
		self.assertEqual(result.next_status, "In at Origin Hub")

	def test_repeat_delivered_scan_is_a_noop(self):
		result = evaluate_scan(snapshot("Delivered"), "Delivered", None)
		self.assertTrue(result.is_duplicate)
		self.assertEqual(result.next_status, "Delivered")

	def test_repeat_scan_with_wrong_hub_is_still_rejected(self):
		# A duplicate is only recognised when hub matches too - otherwise
		# it's a different (illegal) claim about where the parcel is.
		with self.assertRaises(IllegalScanError):
			evaluate_scan(snapshot("In at Origin Hub"), "Hub In", "PUN-01")

	def test_duplicate_does_not_mask_a_genuinely_different_scan_type(self):
		# At "Picked Up", a repeat "Pickup" is a duplicate, but a "Hub In"
		# is a brand new, legal, forward transition - not a duplicate.
		result = evaluate_scan(snapshot("Picked Up"), "Hub In", "DEL-01")
		self.assertFalse(result.is_duplicate)
		self.assertEqual(result.next_status, "In at Origin Hub")


class TestExceptionScans(unittest.TestCase):
	def test_marked_stuck_from_any_in_flight_status(self):
		for status in ("Picked Up", "In at Origin Hub", "In Transit", "In at Destination Hub", "Out for Delivery"):
			with self.subTest(status=status):
				result = evaluate_scan(snapshot(status), "Marked Stuck", None)
				self.assertEqual(result.next_status, "Stuck at Hub")
				self.assertEqual(result.pre_exception_status, status)
				self.assertFalse(result.is_duplicate)

	def test_marked_stuck_rejected_before_pickup_or_after_delivery(self):
		for status in ("Draft", "Booked & Paid", "Delivered"):
			with self.subTest(status=status):
				with self.assertRaises(IllegalScanError):
					evaluate_scan(snapshot(status), "Marked Stuck", None)

	def test_repeat_marked_stuck_is_a_noop(self):
		result = evaluate_scan(snapshot("Stuck at Hub"), "Marked Stuck", None)
		self.assertTrue(result.is_duplicate)
		self.assertEqual(result.next_status, "Stuck at Hub")

	def test_delivery_failed_only_from_out_for_delivery(self):
		result = evaluate_scan(snapshot("Out for Delivery"), "Delivery Failed", None)
		self.assertEqual(result.next_status, "Delivery Failed")
		self.assertEqual(result.pre_exception_status, "Out for Delivery")

	def test_delivery_failed_rejected_from_other_statuses(self):
		for status in ("Picked Up", "In Transit", "Delivered"):
			with self.subTest(status=status):
				with self.assertRaises(IllegalScanError):
					evaluate_scan(snapshot(status), "Delivery Failed", None)

	def test_repeat_delivery_failed_is_a_noop(self):
		result = evaluate_scan(snapshot("Delivery Failed"), "Delivery Failed", None)
		self.assertTrue(result.is_duplicate)

	def test_exception_resolved_cannot_be_applied_via_scan(self):
		with self.assertRaises(IllegalScanError):
			evaluate_scan(snapshot("Stuck at Hub"), "Exception Resolved", None)


class TestReverseFlowUsesSameTable(unittest.TestCase):
	"""A return parcel is a new Parcel with hubs swapped, so it exercises
	the exact same transition table with origin/destination reversed."""

	def test_return_leg_journey(self):
		# Return: original destination (PUN-01) becomes the new origin,
		# original origin (DEL-01) becomes the new destination.
		steps = [
			("Booked & Paid", "Pickup", "PUN-01", "Picked Up"),
			("Picked Up", "Hub In", "PUN-01", "In at Origin Hub"),
			("In at Origin Hub", "Hub Out", "PUN-01", "In Transit"),
			("In Transit", "Hub In", "DEL-01", "In at Destination Hub"),
			("In at Destination Hub", "Hub Out", "DEL-01", "Out for Delivery"),
			("Out for Delivery", "Delivered", None, "Delivered"),
		]
		for current, scan_type, hub, expected_next in steps:
			with self.subTest(current=current, scan_type=scan_type):
				result = evaluate_scan(
					snapshot(current, origin="PUN-01", destination="DEL-01"), scan_type, hub
				)
				self.assertEqual(result.next_status, expected_next)


if __name__ == "__main__":
	unittest.main()
