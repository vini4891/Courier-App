(function () {
	const payBtn = document.getElementById("pay-btn");

	payBtn.addEventListener("click", function () {
		payBtn.disabled = true;
		Courier.call("courier_app.courier_app.api.create_payment_order", { parcel: window.PARCEL_NAME })
			.then((order) => {
				const rzp = new Razorpay({
					key: order.key,
					amount: order.amount,
					currency: order.currency,
					order_id: order.order_id,
					name: order.name,
					description: "Parcel " + window.PARCEL_NAME,
					handler: function (response) {
						Courier.call("courier_app.courier_app.api.verify_payment", {
							parcel: window.PARCEL_NAME,
							razorpay_order_id: response.razorpay_order_id,
							razorpay_payment_id: response.razorpay_payment_id,
							razorpay_signature: response.razorpay_signature,
						})
							.then(() => {
								Courier.banner("courier-banner", "Payment confirmed! Redirecting...", "success");
								window.location.href = "/label?parcel=" + encodeURIComponent(window.PARCEL_NAME);
							})
							.catch((err) => {
								Courier.banner("courier-banner", err.message, "error");
								payBtn.disabled = false;
							});
					},
					modal: {
						ondismiss: function () {
							payBtn.disabled = false;
						},
					},
				});
				rzp.on("payment.failed", function () {
					Courier.banner(
						"courier-banner",
						"Payment failed or was cancelled. You can try again.",
						"error"
					);
					payBtn.disabled = false;
				});
				rzp.open();
			})
			.catch((err) => {
				Courier.banner("courier-banner", err.message, "error");
				payBtn.disabled = false;
			});
	});
})();
