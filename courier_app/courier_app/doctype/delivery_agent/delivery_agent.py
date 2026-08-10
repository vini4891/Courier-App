# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DeliveryAgent(Document):
	def validate(self):
		if self.user and frappe.db.exists(
			"Delivery Agent", {"user": self.user, "name": ("!=", self.name)}
		):
			frappe.throw(frappe._("Another Delivery Agent record already exists for this User."))


def get_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user) or "Courier Manager" in frappe.get_roles(user):
		return ""
	return f"`tabDelivery Agent`.user = {frappe.db.escape(user)}"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user) or "Courier Manager" in frappe.get_roles(user):
		return True
	return doc.user == user


def is_active_agent(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return bool(frappe.db.exists("Delivery Agent", {"user": user, "is_active": 1}))
