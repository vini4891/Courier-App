# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt
"""Functions exposed to Jinja templates (Print Formats) via the `jinja`
hook in hooks.py. Kept in a dedicated module, separate from utils.token,
so only what a template should ever call is exposed as a global."""

from courier_app.courier_app.utils.token import get_qr_svg_base64


def parcel_label_qr(token: str) -> str:
	return get_qr_svg_base64(token)
