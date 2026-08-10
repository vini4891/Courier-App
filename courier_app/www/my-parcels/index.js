(function () {
	const tbody = document.getElementById("parcels-tbody");

	function actionsFor(p) {
		const actions = [`<a href="/track?parcel=${encodeURIComponent(p.name)}">Track</a>`];
		if (p.status === "Draft") {
			actions.push(`<a href="/pay?parcel=${encodeURIComponent(p.name)}">Pay</a>`);
		}
		if (p.payment_status === "Paid" || p.payment_status === "Waived") {
			actions.push(`<a href="/label?parcel=${encodeURIComponent(p.name)}">Label</a>`);
		}
		if (p.status === "Delivered" && !p.is_return) {
			actions.push(`<a href="/return?parcel=${encodeURIComponent(p.name)}">Return</a>`);
		}
		return actions.join(" &middot; ");
	}

	Courier.call("courier_app.courier_app.api.my_parcels")
		.then((rows) => {
			if (!rows.length) {
				tbody.innerHTML = '<tr><td colspan="6">No parcels booked yet.</td></tr>';
				return;
			}
			tbody.innerHTML = rows
				.map(
					(p) => `
					<tr>
						<td>${p.name}${p.is_return ? " <small>(Return)</small>" : ""}</td>
						<td>${p.sender_city}</td>
						<td>${p.recipient_city}</td>
						<td><span class="courier-badge">${p.status}</span></td>
						<td>${p.payment_status}</td>
						<td>${actionsFor(p)}</td>
					</tr>`
				)
				.join("");
		})
		.catch((err) => Courier.banner("courier-banner", err.message, "error"));
})();
