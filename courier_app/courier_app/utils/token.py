# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt
"""Signed, non-guessable parcel tokens.

A token is generated exactly once, in Parcel.before_insert, and stored on
Parcel.token. The SAME stored value is what gets encoded into the QR code
on the printed label AND what the scanner app reads back - it is never
regenerated or derived a second time. `resolve_token` is the single choke
point both the scanner and the tracking page go through, and it rejects
anything that isn't a valid, unmodified signature over a token we actually
issued.
"""

import base64
import hashlib
import hmac
import io

import frappe

TOKEN_NONCE_LENGTH = 32
TOKEN_SIGNATURE_LENGTH = 32


def get_token_secret() -> str:
	secret = frappe.get_cached_doc("Courier Settings").get_password(
		"token_signing_secret", raise_exception=False
	)
	if not secret:
		frappe.throw(frappe._("Courier Settings: Token Signing Secret is not configured."))
	return secret


def _sign(nonce: str, secret: str) -> str:
	return hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()[:TOKEN_SIGNATURE_LENGTH]


def generate_token() -> str:
	"""Called exactly once, from Parcel.before_insert(). Never regenerated."""
	secret = get_token_secret()
	nonce = frappe.generate_hash(length=TOKEN_NONCE_LENGTH)
	return f"{nonce}.{_sign(nonce, secret)}"


def resolve_token(token: str) -> str | None:
	"""Verify a token's signature, then resolve it to a Parcel name.

	Returns None (never raises) for a tampered, forged, malformed, or
	unknown token - callers decide how to surface that to the user.
	"""
	if not token or "." not in token:
		return None
	nonce, _, signature = token.partition(".")
	if not nonce or not signature:
		return None
	try:
		secret = get_token_secret()
	except Exception:
		return None
	expected = _sign(nonce, secret)
	if not hmac.compare_digest(expected, signature):
		return None
	return frappe.db.get_value("Parcel", {"token": token}, "name")


def get_qr_svg_base64(data: str) -> str:
	"""Render `data` as a QR code SVG, base64-encoded for inline embedding
	(<img src="data:image/svg+xml;base64,...">). Mirrors the pattern used
	by frappe.twofactor.get_qr_svg_code."""
	import pyqrcode

	qr = pyqrcode.create(data)
	buffer = io.BytesIO()
	qr.svg(buffer, scale=4, module_color="#000000", background="#ffffff")
	return base64.b64encode(buffer.getvalue()).decode()
