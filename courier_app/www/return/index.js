(function () {
	const btn = document.getElementById("return-btn");
	btn.addEventListener("click", function () {
		btn.disabled = true;
		Courier.call("courier_app.courier_app.api.request_return", { parcel: window.PARCEL_NAME })
			.then((result) => {
				Courier.banner("courier-banner", "Return raised! Redirecting to tracking...", "success");
				window.location.href = "/track?parcel=" + encodeURIComponent(result.name);
			})
			.catch((err) => {
				Courier.banner("courier-banner", err.message, "error");
				btn.disabled = false;
			});
	});
})();
