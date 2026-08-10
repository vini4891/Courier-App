# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt
"""Pure-Python parcel state machine.

Deliberately free of any `frappe` import so it can be unit tested in total
isolation (no database, no site context) and reasoned about as a plain
lookup table. All the Frappe-facing orchestration (loading a Parcel,
writing a Scan Event, persisting the result) lives in
`courier_app.courier_app.doctype.scan_event.scan_event`; this module only
answers the question "given this parcel and this scan, what happens?".

Returns are modelled as a brand-new Parcel document (sender/recipient and
origin/destination hub swapped, created directly in "Booked & Paid"), so
the SAME forward stage list and transition table below apply, unmodified,
to both the outbound leg and the return leg of a shipment.
"""

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------

#: The full ordered forward journey. "Draft" (unpaid, just booked) precedes
#: this list but is intentionally NOT part of the scan-driven state machine:
#: the Draft -> Booked & Paid transition is payment-driven only (see
#: courier_app.courier_app.api). Because ("Draft", "Pickup") is absent from
#: TRANSITIONS below, a Pickup scan attempted before payment is rejected by
#: the ordinary "illegal transition" path, with no special-case code needed.
FORWARD_STATUSES = [
	"Booked & Paid",
	"Picked Up",
	"In at Origin Hub",
	"In Transit",
	"In at Destination Hub",
	"Out for Delivery",
	"Delivered",
]

DRAFT_STATUS = "Draft"
EXCEPTION_STATUSES = ("Delivery Failed", "Stuck at Hub")

#: All status values a Parcel.status field may hold.
ALL_STATUSES = [DRAFT_STATUS, *FORWARD_STATUSES, *EXCEPTION_STATUSES]

#: All scan_type values a Scan Event may hold.
SCAN_TYPES = [
	"Pickup",
	"Hub In",
	"Hub Out",
	"Delivered",
	"Delivery Failed",
	"Marked Stuck",
	"Exception Resolved",
]

# ---------------------------------------------------------------------------
# Transition table
# ---------------------------------------------------------------------------

#: (current_status, scan_type) -> next_status
#: This is the single source of truth for "what is a legal scan".
TRANSITIONS: dict[tuple[str, str], str] = {
	("Booked & Paid", "Pickup"): "Picked Up",
	("Picked Up", "Hub In"): "In at Origin Hub",
	("In at Origin Hub", "Hub Out"): "In Transit",
	("In Transit", "Hub In"): "In at Destination Hub",
	("In at Destination Hub", "Hub Out"): "Out for Delivery",
	("Out for Delivery", "Delivered"): "Delivered",
}

#: Reverse index: which (from_status, scan_type) pair produces a given
#: to_status. Used to recognise "this scan just repeats the one that got us
#: here" for idempotent duplicate detection.
PRODUCED_BY: dict[str, tuple[str, str]] = {to: frm for frm, to in TRANSITIONS.items()}

#: (current_status, scan_type) -> callable(parcel) -> hub name the scan must
#: be performed at. Absent from this dict means "no hub check" (e.g. the
#: final Delivered scan, which happens at the recipient's doorstep, not a hub).
EXPECTED_HUB = {
	("Booked & Paid", "Pickup"): lambda p: p.origin_hub,
	("Picked Up", "Hub In"): lambda p: p.origin_hub,
	("In at Origin Hub", "Hub Out"): lambda p: p.origin_hub,
	("In Transit", "Hub In"): lambda p: p.destination_hub,
	("In at Destination Hub", "Hub Out"): lambda p: p.destination_hub,
}

#: Statuses from which a parcel may be marked "Stuck at Hub" - anything
#: already in motion, i.e. picked up but not yet delivered.
STUCK_ELIGIBLE = {
	"Picked Up",
	"In at Origin Hub",
	"In Transit",
	"In at Destination Hub",
	"Out for Delivery",
}

#: Statuses from which a delivery attempt can be marked failed - only the
#: final leg, once an agent is actually out with the parcel.
FAILED_ELIGIBLE = {"Out for Delivery"}


class IllegalScanError(Exception):
	"""Raised for any scan that is out-of-order, at the wrong hub, or
	otherwise not a legal move for the parcel's current status.

	Callers (courier_app.doctype.scan_event.record_scan) catch this and
	turn it into a rejected request WITHOUT inserting a Scan Event row -
	an illegal scan never happened, so it doesn't belong in the append-only
	log."""


@dataclass
class ParcelSnapshot:
	"""Just enough of a Parcel to evaluate a scan against. Deliberately not
	the real Frappe document - keeps this module DB-free and trivially
	constructible in tests."""

	status: str
	origin_hub: str
	destination_hub: str


@dataclass
class ScanResult:
	next_status: str
	is_duplicate: bool
	pre_exception_status: str | None = None


def evaluate_scan(parcel: ParcelSnapshot, scan_type: str, hub: str | None) -> ScanResult:
	"""Evaluate a single scan against a parcel's current state.

	Returns a ScanResult describing what should happen. Raises
	IllegalScanError for anything that must be rejected outright (wrong
	stage, wrong hub, wrong status for an exception report).
	"""
	current = parcel.status

	# --- Exception-report scans: not part of the linear TRANSITIONS table,
	# not hub-checked (an agent reports "stuck"/"failed" from wherever they
	# are), and idempotent against themselves. --------------------------
	if scan_type == "Marked Stuck":
		if current in STUCK_ELIGIBLE:
			return ScanResult("Stuck at Hub", is_duplicate=False, pre_exception_status=current)
		if current == "Stuck at Hub":
			return ScanResult("Stuck at Hub", is_duplicate=True)
		raise IllegalScanError(f"Cannot mark parcel stuck from status '{current}'.")

	if scan_type == "Delivery Failed":
		if current in FAILED_ELIGIBLE:
			return ScanResult("Delivery Failed", is_duplicate=False, pre_exception_status=current)
		if current == "Delivery Failed":
			return ScanResult("Delivery Failed", is_duplicate=True)
		raise IllegalScanError(f"Cannot mark delivery failed from status '{current}'.")

	if scan_type == "Exception Resolved":
		# Handled entirely by courier_app.doctype.parcel.parcel.resolve_exception,
		# which does not call evaluate_scan at all (it knows the exact
		# pre_exception_status to resume to). Reject here defensively so a
		# stray scan of this type through the normal scan path is refused.
		raise IllegalScanError("Exception Resolved cannot be applied via a scan.")

	# --- Normal forward progress -----------------------------------------
	key = (current, scan_type)
	if key in TRANSITIONS:
		expected_hub_fn = EXPECTED_HUB.get(key)
		expected_hub = expected_hub_fn(parcel) if expected_hub_fn else None
		if expected_hub and hub != expected_hub:
			raise IllegalScanError(
				f"Expected this parcel at hub '{expected_hub}' for a '{scan_type}' scan, "
				f"but it was scanned at '{hub}'."
			)
		return ScanResult(TRANSITIONS[key], is_duplicate=False)

	# --- Idempotent duplicate: the scan_type/hub matches the transition
	# that produced the CURRENT status - i.e. this is a re-scan of the
	# same physical event, not a new one. --------------------------------
	produced = PRODUCED_BY.get(current)
	if produced:
		prior_status, prior_scan_type = produced
		if prior_scan_type == scan_type:
			expected_hub_fn = EXPECTED_HUB.get(produced)
			expected_hub = expected_hub_fn(parcel) if expected_hub_fn else None
			if not expected_hub or hub == expected_hub:
				return ScanResult(current, is_duplicate=True)

	# --- Everything else: illegal / out-of-order -------------------------
	raise IllegalScanError(f"'{scan_type}' scan is not valid for a parcel currently at status '{current}'.")
