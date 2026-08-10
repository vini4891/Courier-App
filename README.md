## Courier App

A custom [Frappe](https://frappeframework.com) app for a courier/parcel delivery business: customers book and pay for shipments, delivery agents move parcels through hubs via camera scans that drive a strict status state machine, and ops manage hubs, rates, and exceptions from Desk.

### What it does

- **Customer portal** (`/book`, `/pay`, `/label`, `/track`, `/my-parcels`, `/return`) — book a parcel, pay via Razorpay, print a shipping label with a signed QR code, track a shipment live, and raise a return on a delivered parcel.
- **Delivery agent scanner** (`/scanner`) — a camera-based scanning console (backed by `html5-qrcode`) that advances a parcel exactly one legal step per scan: Pickup → Hub In/Out at origin → Hub In/Out at destination → Delivered. Scans are idempotent (a genuine re-scan is a no-op) and hop-validated (a wrong hub or out-of-order scan is rejected).
- **Ops / Desk** — manage Hubs, Delivery Agents, and Service Levels (rates); monitor all in-flight parcels via a dedicated report; resolve exceptions (failed delivery, stuck at hub).

### Design highlights

- **Parcel status is derived, never edited.** Every legitimate status change flows through a scan or a payment confirmation — the field itself is guarded against direct edits, in Desk or via the API.
- **One state machine, run twice.** A return is a brand-new Parcel with sender/recipient and origin/destination hubs swapped, driven through the exact same transition table as the outbound leg.
- **Append-only audit log.** `Scan Event` records can't be created, edited, or deleted by anyone through the UI or API — enforced at the permission layer, the field layer, and the controller layer.
- **Idempotent Razorpay payment confirmation.** The client-side checkout callback and the signature-verified webhook both funnel into one idempotent "mark paid" step — whichever fires first wins, a retry or race in either direction is a guaranteed no-op.
- **Signed, non-guessable tracking tokens.** Generated once at booking, HMAC-verified on every read — the same token drives both the label's QR code and the scanner.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app courier_app
```

### Tests

```bash
bench --site your-site set-config allow_tests true
bench --site your-site run-tests --app courier_app
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/courier_app
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
