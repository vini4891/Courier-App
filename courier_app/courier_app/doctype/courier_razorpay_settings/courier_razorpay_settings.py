# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CourierRazorpaySettings(Document):
	def validate(self):
		if self.enabled and not (self.api_key and self.get_password("api_secret", raise_exception=False)):
			frappe.throw(frappe._("API Key and API Secret are required to enable Razorpay."))
