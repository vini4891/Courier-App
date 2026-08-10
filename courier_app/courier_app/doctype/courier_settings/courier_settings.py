# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CourierSettings(Document):
	def before_insert(self):
		self._ensure_token_secret()

	def validate(self):
		self._ensure_token_secret()

	def _ensure_token_secret(self):
		if not self.get_password("token_signing_secret", raise_exception=False):
			self.token_signing_secret = frappe.generate_hash(length=50)
