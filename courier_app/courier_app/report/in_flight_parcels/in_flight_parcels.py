# Copyright (c) 2026, Dheeraj and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Parcel"), "fieldname": "name", "fieldtype": "Link", "options": "Parcel", "width": 130},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 150},
		{"label": _("Origin Hub"), "fieldname": "origin_hub", "fieldtype": "Link", "options": "Hub", "width": 110},
		{
			"label": _("Destination Hub"),
			"fieldname": "destination_hub",
			"fieldtype": "Link",
			"options": "Hub",
			"width": 130,
		},
		{"label": _("Current Hub"), "fieldname": "current_hub", "fieldtype": "Link", "options": "Hub", "width": 110},
		{
			"label": _("Service Level"),
			"fieldname": "service_level",
			"fieldtype": "Link",
			"options": "Service Level",
			"width": 110,
		},
		{"label": _("Booked On"), "fieldname": "booked_on", "fieldtype": "Datetime", "width": 160},
		{"label": _("Is Return"), "fieldname": "is_return", "fieldtype": "Check", "width": 80},
	]


def get_data(filters):
	conditions = {"status": ["not in", ["Draft", "Delivered"]]}
	if filters.get("status"):
		conditions["status"] = filters["status"]
	if filters.get("origin_hub"):
		conditions["origin_hub"] = filters["origin_hub"]
	if filters.get("destination_hub"):
		conditions["destination_hub"] = filters["destination_hub"]

	return frappe.get_all(
		"Parcel",
		filters=conditions,
		fields=[
			"name",
			"status",
			"origin_hub",
			"destination_hub",
			"current_hub",
			"service_level",
			"booked_on",
			"is_return",
		],
		order_by="booked_on asc",
	)
