# Courier App — Complete Setup & Demo Guide

This README explains how to set up the Courier application from a blank site and run the complete end-to-end workflow.

The application has three main personas:

| Persona        | Frappe Role        | Primary Access | Purpose                                                           |
| -------------- | ------------------ | -------------- | ----------------------------------------------------------------- |
| Ops / Admin    | `Courier Manager`  | Desk           | Configure hubs, service levels, agents, parcels and exceptions    |
| Customer       | `Courier Customer` | Portal         | Create shipments, make payments, view parcels and request returns |
| Delivery Agent | `Delivery Agent`   | Scanner        | Scan parcels through the delivery lifecycle                       |

The complete workflow is:

```text
Ops creates configuration
        ↓
Customer books parcel
        ↓
Customer completes payment
        ↓
Customer receives label / QR
        ↓
Delivery Agent scans parcel
        ↓
Parcel moves through delivery states
        ↓
Recipient tracks parcel without login
        ↓
Customer requests return
        ↓
New return parcel is created
        ↓
Delivery Agent scans return parcel
        ↓
Ops handles exceptions when required
```

---

# 1. Before You Start

The application is expected to run from the Frappe bench.

If the site is already running, open:

`http://sil.localhost:8000`

If the page loads, continue to the setup section.

If the site is not running:

```bash
cd /home/dheeraj/sil
bench start
```

Keep this terminal running while using or recording the application.

The command starts the required services, including:

* Redis
* Web server
* Background worker
* File watcher

### Recommended setup

Use two windows:

1. Terminal — running `bench start`
2. Browser — used for the actual walkthrough

For persona switching, use separate browser profiles or Incognito/Private windows.

For example:

```text
Browser 1 → Ops / Admin
Browser 2 → Customer
Browser 3 → Delivery Agent
Browser 4 → Guest tracking
```

This avoids accidentally carrying one user's login session into another persona.

---

# 2. Application URLs

The following URLs are used throughout the workflow.

## Authentication

```text
/login
```

All authenticated users sign in through this page.

---

## Ops / Admin

Courier workspace:

```text
/app/courier
```

Create a Hub:

```text
/app/hub/new
```

Create a Service Level:

```text
/app/service-level/new
```

Create a Delivery Agent:

```text
/app/delivery-agent/new
```

Create a User:

```text
/app/user/new
```

Razorpay settings:

```text
/app/courier-razorpay-settings
```

Open a specific Parcel:

```text
/app/parcel/<PARCEL_NAME>
```

---

## Customer

Booking:

```text
/book
```

Payment:

```text
/pay?parcel=<PARCEL_NAME>
```

Label:

```text
/label?parcel=<PARCEL_NAME>
```

Customer's parcels:

```text
/my-parcels
```

Return:

```text
/return
```

---

## Delivery Agent

Scanner:

```text
/scanner
```

---

## Guest

Tracking:

```text
/track?token=<TRACKING_TOKEN>
```

The tracking URL does not require the recipient to log in.

---

# 3. Create the Required Users

The application should be configured with three separate users.

Do **not** use the same user for all three personas.

The three users are:

```text
Ops / Admin
Customer
Delivery Agent
```

Each user has a different role and access path.

---

# 4. User 1 — Ops / Admin

## Purpose

The Ops / Admin user manages the operational configuration of the courier network.

This user is responsible for:

* Creating hubs
* Creating service levels
* Registering delivery agents
* Configuring Razorpay
* Viewing parcels
* Handling exceptions
* Resolving stuck parcels
* Reviewing operational records

The Ops user should access the application through **Desk**.

---

## Create the user

Log in as a System Manager and open:

```text
/app/user/new
```

Create a new user.

Example:

```text
First Name: Ops
Last Name: Manager
Email: ops_manager@example.com
```

Set a password that will be used during the demo.

Make sure the user is enabled.

Assign:

```text
Courier Manager
```

role.

If the application requires standard Frappe Desk access, retain the appropriate Desk/system roles required by the application's permission configuration.

Save the user.

---

## Ops access

After logging in:

```text
/login
```

the Ops user should be able to access:

```text
/app/courier
```

The Courier workspace is the main operational dashboard.

The Ops user should **not** be used for customer booking or delivery-agent scanning during the normal demo.

---

# 5. User 2 — Customer

## Purpose

The Customer represents the person sending a parcel.

The customer can:

* Create a booking
* Enter sender information
* Enter recipient information
* Select a service level
* Enter parcel weight
* Pay for the shipment
* View the generated label
* View their parcels
* Request a return

The Customer should use the **portal/customer-facing pages**, not Desk.

---

## Create the user

From the Ops/System Manager account, open:

```text
/app/user/new
```

Create another user.

Example:

```text
First Name: Customer
Email: customer@example.com
```

Set the desired password.

Assign:

```text
Courier Customer
```

role.

Save the user.

---

## Customer access

The customer signs in at:

```text
/login
```

After authentication, the customer should use:

```text
/book
```

and:

```text
/my-parcels
```

The customer should not need to access:

```text
/app/courier
/app/hub/new
/app/service-level/new
/app/delivery-agent/new
```

Those are operational/admin functions.

---

# 6. User 3 — Delivery Agent

## Purpose

The Delivery Agent is the person physically handling parcels.

The agent uses the scanner to move a parcel through its state machine.

The agent can:

* Scan Pickup
* Scan Hub In
* Scan Hub Out
* Scan Delivered
* Mark a parcel as stuck
* Continue/resume parcels after an exception is resolved

The Delivery Agent should use:

```text
/scanner
```

---

## Step 1 — Create the User

Log in as System Manager/Ops and open:

```text
/app/user/new
```

Create the user.

Example:

```text
First Name: Raju
Email: agent@example.com
```

Set the password.

Assign:

```text
Delivery Agent
```

role.

Save the user.

---

## Step 2 — Create the Delivery Agent record

Creating the User is not enough.

The application also requires a corresponding **Delivery Agent** record.

Open:

```text
/app/delivery-agent/new
```

Create the record.

Example:

| Field      | Value                                         |
| ---------- | --------------------------------------------- |
| Agent Name | Raju                                          |
| User       | [agent@example.com](mailto:agent@example.com) |
| Phone      | 9800000000                                    |

The `User` field must point to the Delivery Agent user created above.

Save the record.

### Important

The Delivery Agent user and Delivery Agent record are two separate things:

```text
Frappe User
    ↓
Delivery Agent role
    +
Delivery Agent record
    ↓
/scanner access
```

If the User exists but the Delivery Agent record does not, the scanner may report that the account is not registered as an agent.

---

# 7. Persona Access Summary

After creating all three users, the setup should look like this:

| User           | Role             | Login    | Main URL       |
| -------------- | ---------------- | -------- | -------------- |
| Ops / Admin    | Courier Manager  | `/login` | `/app/courier` |
| Customer       | Courier Customer | `/login` | `/book`        |
| Delivery Agent | Delivery Agent   | `/login` | `/scanner`     |

Guest users do not need an account.

They use:

```text
/track?token=<TOKEN>
```

---

# 8. Create the Operational Configuration

Before a customer can successfully book a shipment, Ops needs to configure the courier network.

Log in as:

```text
Ops / Admin
```

Go to:

```text
/app/courier
```

---

## 8.1 Create the Origin Hub

Open:

```text
/app/hub/new
```

Create the first hub.

Example:

| Field    | Value             |
| -------- | ----------------- |
| Hub Code | DEL-01            |
| Hub Name | Delhi Central Hub |
| City     | Delhi             |

Save it.

The city is important because the booking flow uses the city information.

Make sure it is exactly:

```text
Delhi
```

---

## 8.2 Create the Destination Hub

Create another Hub:

```text
/app/hub/new
```

Use:

| Field    | Value            |
| -------- | ---------------- |
| Hub Code | PUN-01           |
| Hub Name | Pune Central Hub |
| City     | Pune             |

Save it.

The two hubs now represent:

```text
Delhi → Pune
```

---

# 9. Create the Service Level

Open:

```text
/app/service-level/new
```

Create a service level.

Example:

| Field                  |    Value |
| ---------------------- | -------: |
| Service Level Name     | Standard |
| Base Rate              |       60 |
| Rate Per Kg            |       15 |
| Estimated Transit Days |        2 |

Save it.

The customer will select this service level during booking.

The customer does **not** manually enter the price.

With:

```text
Base Rate = ₹60
Rate Per Kg = ₹15
Weight = 3 kg
```

the application calculates:

```text
₹60 + (₹15 × 3)
= ₹105
```

The price therefore comes from the Ops-managed service-level configuration.

---

# 10. Configure Razorpay

Open:

```text
/app/courier-razorpay-settings
```

Expand the **Webhook** section.

Set:

```text
Webhook Secret
```

to a secret value known to the application configuration.

For a local demonstration, an example is:

```text
demo-webhook-secret
```

Save the settings.

---

## Optional — Configure Razorpay Test Mode

If Razorpay test credentials are available, configure:

```text
API Key
API Secret
Enabled
```

using the application's Razorpay settings.

This allows the payment scene to use the real Razorpay test checkout.

If test credentials are not available, the webhook can be used to demonstrate the payment-confirmation flow.

---

# 11. Complete Customer Booking Flow

Once Ops has created the hubs, service level and delivery agent, switch to the Customer account.

Open:

```text
/login
```

Sign in as:

```text
Customer
```

---

## 11.1 Open the Booking Page

Go to:

```text
/book
```

If `/book` is opened while logged out, the expected behavior is a redirect to login, similar to:

```text
/login?redirect-to=/book
```

After successful login, the customer can continue to the booking page.

---

# 12. Enter Sender and Recipient Details

Use the following example data for the demonstration:

### Sender

```text
Name: Meena Sharma
Phone: 9811111111
Address: 12 MG Road
City: Delhi
Pincode: 110001
```

### Recipient

```text
Name: Arjun Verma
Phone: 9822222222
Address: 45 FC Road
City: Pune
Pincode: 411001
```

Select:

```text
Service Level: Standard
Weight: 3 kg
```

Submit the booking.

---

# 13. Verify the Calculated Price

The booking should redirect to:

```text
/pay?parcel=<PARCEL_NAME>
```

For the example configuration:

```text
Base Rate = ₹60
Weight = 3 kg
Rate Per Kg = ₹15
```

the expected price is:

```text
₹60 + (3 × ₹15)
= ₹105
```

The important point to demonstrate is that:

```text
Customer enters weight
        ↓
Server reads Standard service level
        ↓
Server calculates price
        ↓
Customer sees ₹105
```

The customer does not type `₹105`.

---

# 14. Complete the Payment

On:

```text
/pay?parcel=<PARCEL_NAME>
```

click:

```text
Pay
```

There are two possible environments.

---

## Option A — Razorpay Test Mode

If Razorpay test credentials have been configured, the Razorpay checkout should open.

Use Razorpay's test payment credentials.

The payment should complete through the test checkout.

---

## Option B — Local Webhook Demonstration

If live/test Razorpay checkout is not configured, the payment can be confirmed through the application's webhook endpoint.

First identify the parcel name.

For example:

```text
PARCEL-2026-XXXXX
```

Set the demo Razorpay order ID:

```bash
bench --site sil execute frappe.db.set_value \
  --kwargs '{"dt": "Parcel", "dn": "PARCEL-2026-XXXXX", "field": "razorpay_order_id", "val": "order_demo_1"}'
```

Commit the change:

```bash
bench --site sil execute frappe.db.commit
```

Create the webhook payload:

```bash
BODY='{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_demo_1","order_id":"order_demo_1"}}}}'
```

Generate the signature:

```bash
SIG=$(node -e "console.log(require('crypto').createHmac('sha256','demo-webhook-secret').update(process.argv[1]).digest('hex'))" "$BODY")
```

Send the webhook:

```bash
curl -s -X POST \
  http://sil.localhost:8000/api/method/courier_app.courier_app.api.razorpay_webhook \
  -H "Content-Type: application/json" \
  -H "X-Razorpay-Signature: $SIG" \
  -d "$BODY"
```

Expected response:

```json
{"message":{"status":"ok"}}
```

Reload the payment page.

Once the payment has been confirmed, the application should allow the customer to proceed to the label.

---

# 15. Verify the Label

Open:

```text
/label?parcel=<PARCEL_NAME>
```

The label contains the parcel's QR code.

The QR code contains the tracking/security token used by the scanner and tracking page.

The same token is used for:

```text
Label
   ↓
Scanner
   ↓
Tracking URL
```

The token should be generated for the parcel and should not be manually recreated by the user.

---

# 16. Delivery Agent Flow

Now switch to the Delivery Agent account.

Open:

```text
/login
```

Sign in as:

```text
Delivery Agent
```

Then open:

```text
/scanner
```

The scanner is the primary interface for the delivery agent.

---

# 17. Parcel State Machine

A normal outbound parcel follows this sequence:

```text
Booked & Paid
      ↓
Picked Up
      ↓
In at Origin Hub
      ↓
In Transit
      ↓
In at Destination Hub
      ↓
Out for Delivery
      ↓
Delivered
```

For the Delhi → Pune example:

```text
Delhi Central Hub
        ↓
Pune Central Hub
```

---

# 18. Perform the Six Delivery Scans

Use the parcel token from the label.

The scanner should advance the parcel one legal state at a time.

|  # | Scan Type | Hub               | Result                |
| -: | --------- | ----------------- | --------------------- |
|  1 | Pickup    | Delhi Central Hub | Picked Up             |
|  2 | Hub In    | Delhi Central Hub | In at Origin Hub      |
|  3 | Hub Out   | Delhi Central Hub | In Transit            |
|  4 | Hub In    | Pune Central Hub  | In at Destination Hub |
|  5 | Hub Out   | Pune Central Hub  | Out for Delivery      |
|  6 | Delivered | No hub required   | Delivered             |

For every scan:

1. Select the Scan Type.
2. Select the Hub when required.
3. Enter/scan the parcel token.
4. Submit the scan.
5. Verify the resulting status.

The status should update after each valid scan.

---

# 19. Duplicate Scan Behavior

After the parcel reaches:

```text
Delivered
```

submit another:

```text
Delivered
```

scan.

The application should recognize that the scan has already been recorded.

Expected behavior:

```text
Already recorded
```

The parcel remains:

```text
Delivered
```

This demonstrates idempotency.

A genuine duplicate should not create another state transition.

---

# 20. Out-of-Order Scan Behavior

Now attempt:

```text
Pickup
```

on the already delivered parcel.

This is not a legitimate duplicate.

It is an invalid state transition.

Expected behavior is a rejection similar to:

```text
Scan rejected — 'Pickup' scan is not valid for a parcel currently at status 'Delivered'.
```

The important distinction is:

```text
Duplicate valid state
        → No-op

Invalid state transition
        → Rejected
```

---

# 21. Guest Tracking Flow

Tracking does not require a customer account.

Open a second browser window or private window.

Use:

```text
/track?token=<TRACKING_TOKEN>
```

The token is the same token associated with the parcel label.

The guest can see the parcel's tracking information without logging in.

This demonstrates:

```text
Recipient
   ↓
Tracking link
   ↓
Token authentication
   ↓
Parcel tracking
```

No separate customer account is required for the recipient.

---

# 22. Demonstrate Live Tracking

For the strongest demonstration, open the tracking page **before** scanning the parcel.

Recommended setup:

```text
Window 1
/scanner
Delivery Agent

Window 2
/track?token=<TOKEN>
Guest tracking
```

Perform the six scans in Window 1.

The tracking page should update and show the growing scan history.

This demonstrates that the scanner and tracking experience are connected through the same parcel state.

---

# 23. Customer Return Flow

After the original parcel reaches:

```text
Delivered
```

switch back to the Customer account.

Open:

```text
/my-parcels
```

The delivered parcel should expose the return functionality.

---

## 23.1 Start the Return

Click:

```text
Return
```

Continue to:

```text
/return
```

and confirm:

```text
Confirm Return
```

---

# 24. Verify the Return Parcel

A return should create a **new parcel**.

It should not simply modify the original delivered parcel.

For the original:

```text
Delhi → Pune
```

the return becomes:

```text
Pune → Delhi
```

The sender and recipient are swapped.

The hubs are also swapped.

The return should not create another customer payment.

The new parcel should be created with payment waived.

Conceptually:

```text
Original parcel

Delhi
  ↓
Pune
  ↓
Delivered


Return parcel

Pune
  ↓
Delhi
```

The customer should be redirected to the tracking page for the new return parcel.

---

# 25. Scan the Return Parcel

Switch back to the Delivery Agent.

Open:

```text
/scanner
```

Use the return parcel's token.

Run the same six-step state machine.

This time the hubs are reversed:

|  # | Scan Type | Hub               | Result                |
| -: | --------- | ----------------- | --------------------- |
|  1 | Pickup    | Pune Central Hub  | Picked Up             |
|  2 | Hub In    | Pune Central Hub  | In at Origin Hub      |
|  3 | Hub Out   | Pune Central Hub  | In Transit            |
|  4 | Hub In    | Delhi Central Hub | In at Destination Hub |
|  5 | Hub Out   | Delhi Central Hub | Out for Delivery      |
|  6 | Delivered | No hub required   | Delivered             |

The important design point is that a return does not require a separate return state machine.

It is another parcel using the same delivery state machine with reversed routing.

---

# 26. Exception Flow

The exception workflow demonstrates what happens when a parcel cannot continue normally.

Create a fresh parcel using the normal:

```text
Customer
    ↓
/book
    ↓
/pay
    ↓
Payment confirmation
    ↓
/label
```

Then switch to the Delivery Agent.

Open:

```text
/scanner
```

Perform only the first two scans:

```text
Pickup
    ↓
Hub In
```

The parcel should now be:

```text
In at Origin Hub
```

---

# 27. Mark the Parcel as Stuck

On:

```text
/scanner
```

select:

```text
Scan Type → Marked Stuck
```

A reason field should appear.

Enter a realistic reason, for example:

```text
Vehicle breakdown near hub
```

Submit the scan.

The parcel should move to:

```text
Stuck at Hub
```

The exception reason should be stored with the parcel/scan history.

---

# 28. Resolve the Exception from Desk

Now switch to the Ops / Admin account.

Open:

```text
/app/parcel/<PARCEL_NAME>
```

The parcel should expose a:

```text
Resolve Exception
```

action.

Click it and confirm the resolution.

The important behavior is that the application does **not** let the manager arbitrarily select a new status.

Instead, it remembers the parcel's previous operational state.

For example:

```text
Before exception:
In at Origin Hub

       ↓
Marked Stuck

       ↓
Stuck at Hub

       ↓
Resolve Exception

       ↓
In at Origin Hub
```

The parcel resumes from the state it was in before the exception.

---

# 29. Recommended Complete Demo Order

For a complete walkthrough, use this order.

## Phase 1 — Setup

Log in as Ops:

```text
/login
```

Create:

```text
1. Ops User
2. Customer User
3. Delivery Agent User
4. Delivery Agent Record
5. Delhi Hub
6. Pune Hub
7. Standard Service Level
8. Razorpay configuration
```

---

## Phase 2 — Booking

Switch to Customer.

```text
/login
    ↓
/book
    ↓
Enter sender
    ↓
Enter recipient
    ↓
Select Standard
    ↓
Enter 3 kg
    ↓
Submit
```

Verify:

```text
/pay?parcel=<PARCEL_NAME>
```

and the calculated price.

---

## Phase 3 — Payment

Complete payment through:

```text
Razorpay test checkout
```

or the signed webhook flow.

Then open:

```text
/label?parcel=<PARCEL_NAME>
```

---

## Phase 4 — Tracking

Before scanning, open:

```text
/track?token=<TOKEN>
```

in a guest/private browser.

Keep this window visible.

---

## Phase 5 — Delivery

Switch to Delivery Agent:

```text
/scanner
```

Perform:

```text
Pickup
↓
Hub In
↓
Hub Out
↓
Hub In
↓
Hub Out
↓
Delivered
```

Watch the tracking window update.

---

## Phase 6 — State Validation

Try:

```text
Delivered again
```

Verify that it is treated as a duplicate/no-op.

Then try:

```text
Pickup
```

Verify that the invalid transition is rejected.

---

## Phase 7 — Return

Switch to Customer:

```text
/my-parcels
    ↓
Return
    ↓
/return
    ↓
Confirm Return
```

Verify that a new parcel is created:

```text
Pune → Delhi
```

with payment waived.

---

## Phase 8 — Return Delivery

Switch to Delivery Agent:

```text
/scanner
```

Run the same six scans with the hubs reversed.

---

## Phase 9 — Exception

Create another fresh parcel.

Scan:

```text
Pickup
↓
Hub In
```

Then:

```text
Marked Stuck
```

with a reason.

Switch to Ops:

```text
/app/parcel/<PARCEL_NAME>
```

Resolve the exception.

Verify that the parcel returns to its previous status.

---

# 30. Final Access Matrix

Use this table as the quick reference when performing the demo.

| Feature               | Ops | Customer | Delivery Agent | Guest |
| --------------------- | :-: | :------: | :------------: | :---: |
| Login                 |  ✓  |     ✓    |        ✓       |   —   |
| Courier Desk          |  ✓  |     —    |        —       |   —   |
| Create Hub            |  ✓  |     —    |        —       |   —   |
| Create Service Level  |  ✓  |     —    |        —       |   —   |
| Create Delivery Agent |  ✓  |     —    |        —       |   —   |
| Configure Razorpay    |  ✓  |     —    |        —       |   —   |
| Book Parcel           |  —  |     ✓    |        —       |   —   |
| Pay                   |  —  |     ✓    |        —       |   —   |
| View Label            |  —  |     ✓    |        —       |   —   |
| Scan Parcel           |  —  |     —    |        ✓       |   —   |
| Mark Stuck            |  —  |     —    |        ✓       |   —   |
| View Own Parcels      |  —  |     ✓    |        —       |   —   |
| Request Return        |  —  |     ✓    |        —       |   —   |
| Track Parcel          |  —  |     ✓    |        —       |   ✓   |
| Resolve Exception     |  ✓  |     —    |        —       |   —   |

---

# 31. Troubleshooting

## `/book` redirects to login

This is expected when the customer is not authenticated.

Sign in as the Customer and return to:

```text
/book
```

---

## Scanner says the agent is not registered

Check both of these:

1. The Frappe User has the:

```text
Delivery Agent
```

role.

2. A Delivery Agent record exists at:

```text
/app/delivery-agent/new
```

and its User field points to the same user.

---

## Booking price is incorrect

Check the Service Level:

```text
/app/service-level/new
```

Verify:

```text
Base Rate
Rate Per Kg
```

For the example:

```text
Base Rate = 60
Rate Per Kg = 15
Weight = 3
```

expected price:

```text
₹105
```

---

## Payment page does not unlock the label

Verify:

1. The parcel has a Razorpay order ID.
2. The webhook secret matches the configured secret.
3. The webhook signature is calculated using the exact request body.
4. The webhook endpoint is reachable.
5. The webhook response is:

```json
{"message":{"status":"ok"}}
```

---

## Tracking does not require login

This is intentional.

The tracking page:

```text
/track?token=<TOKEN>
```

uses the parcel's tracking token rather than a Frappe user session.

---

# 32. Key Concepts Demonstrated

The complete walkthrough demonstrates the following application capabilities:

### Role-based access

Different users have different responsibilities:

```text
Ops
Customer
Delivery Agent
Guest
```

### Server-side pricing

The customer does not control the shipping price.

```text
Service Level
    +
Weight
    ↓
Server-side calculation
    ↓
Final price
```

### Payment verification

The label becomes available only after payment is confirmed.

### Signed tracking token

The same secure token connects:

```text
Label
Scanner
Tracking
```

### State-machine enforcement

Only legal parcel transitions are accepted.

### Idempotency

A duplicate valid scan does not create another transition.

### Invalid-transition protection

An impossible scan is rejected.

### Guest tracking

Recipients can track parcels without creating accounts.

### Returns

A return creates a new parcel with reversed routing.

### Exception handling

Stuck parcels can be marked, audited and resolved.

### State restoration

Resolving an exception returns the parcel to its previous operational state.

---

# 33. One-Page Flow Summary

```text
                    ┌──────────────────┐
                    │   OPS / ADMIN    │
                    │ Courier Manager  │
                    └────────┬─────────┘
                             │
             ┌───────────────┼────────────────┐
             ↓               ↓                ↓
          Hubs          Service Level    Delivery Agent
             │               │                │
             └───────────────┼────────────────┘
                             ↓
                    ┌──────────────────┐
                    │    CUSTOMER      │
                    │ Courier Customer │
                    └────────┬─────────┘
                             │
                           /book
                             ↓
                         /pay
                             ↓
                          /label
                             │
                             ↓
                    ┌──────────────────┐
                    │ DELIVERY AGENT   │
                    │    /scanner      │
                    └────────┬─────────┘
                             │
        Pickup → Hub In → Hub Out → Hub In
                             ↓
                      Hub Out → Delivered
                             │
                             ├───────────────┐
                             ↓               ↓
                         /track          /my-parcels
                             │               │
                           Guest           Return
                                             ↓
                                      New Return Parcel
                                             ↓
                                        /scanner
                                             ↓
                                      Pune → Delhi
                                             │
                                             ↓
                                         Delivered


Exception path:

Parcel
  ↓
Pickup
  ↓
Hub In
  ↓
Marked Stuck
  ↓
Ops / Desk
  ↓
Resolve Exception
  ↓
Previous operational state
```

This is the complete setup and demonstration flow for the Courier application.
