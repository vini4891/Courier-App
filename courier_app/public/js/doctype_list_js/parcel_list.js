frappe.listview_settings["Parcel"] = {
	add_fields: ["status", "payment_status"],
	get_indicator(doc) {
		const colors = {
			"Draft": "grey",
			"Booked & Paid": "blue",
			"Picked Up": "orange",
			"In at Origin Hub": "orange",
			"In Transit": "orange",
			"In at Destination Hub": "yellow",
			"Out for Delivery": "yellow",
			"Delivered": "green",
			"Delivery Failed": "red",
			"Stuck at Hub": "red",
		};
		return [__(doc.status), colors[doc.status] || "grey", "status,=," + doc.status];
	},
};
