(function () {
	const form = document.getElementById("book-form");
	const select = document.getElementById("service-level-select");
	const submitBtn = document.getElementById("book-submit");

	Courier.call("courier_app.courier_app.doctype.service_level.service_level.get_active_service_levels")
		.then((levels) => {
			select.innerHTML = levels
				.map(
					(l) =>
						`<option value="${l.name}">${l.service_level_name} - Base ₹${l.base_rate} + ₹${l.rate_per_kg}/kg (${l.estimated_transit_days}d)</option>`
				)
				.join("");
		})
		.catch((err) => Courier.banner("courier-banner", err.message, "error"));

	form.addEventListener("submit", function (e) {
		e.preventDefault();
		submitBtn.disabled = true;
		const data = Object.fromEntries(new FormData(form).entries());
		["weight_kg", "length_cm", "width_cm", "height_cm", "declared_value"].forEach((f) => {
			if (data[f] === "") delete data[f];
			else data[f] = parseFloat(data[f]);
		});

		Courier.call("courier_app.courier_app.api.book_parcel", data)
			.then((result) => {
				Courier.banner("courier-banner", "Parcel booked! Redirecting to payment...", "success");
				window.location.href = "/pay?parcel=" + encodeURIComponent(result.name);
			})
			.catch((err) => {
				Courier.banner("courier-banner", err.message, "error");
				submitBtn.disabled = false;
			});
	});
})();
