frappe.ui.form.on("Parcel", {
	refresh(frm) {
		if (["Delivery Failed", "Stuck at Hub"].includes(frm.doc.status) && frappe.user_roles.some((r) =>
			["Courier Manager", "System Manager"].includes(r)
		)) {
			frm.add_custom_button(__("Resolve Exception"), () => {
				frappe.confirm(
					__("Resume this parcel to its status before the exception ({0})?", [frm.doc.pre_exception_status]),
					() => {
						frappe.call({
							method: "courier_app.courier_app.doctype.parcel.parcel.resolve_exception",
							args: { parcel: frm.doc.name, resume_status: frm.doc.pre_exception_status },
							freeze: true,
							callback: () => frm.reload_doc(),
						});
					}
				);
			}).addClass("btn-danger");
		}

		if (frm.doc.token) {
			frm.add_custom_button(__("Track"), () => {
				window.open(`/track?token=${encodeURIComponent(frm.doc.token)}`, "_blank");
			});
		}
		if (frm.doc.payment_status === "Paid" || frm.doc.payment_status === "Waived") {
			frm.add_custom_button(__("Download Label"), () => {
				window.open(
					`/api/method/courier_app.courier_app.api.download_label_pdf?parcel=${encodeURIComponent(frm.doc.name)}`,
					"_blank"
				);
			});
		}
	},
});
