(function () {
	const summaryEl = document.getElementById("track-summary");
	const timelineEl = document.getElementById("track-timeline");
	const POLL_MS = 15000;

	const STATUS_LABELS = {
		"Draft": "Booking not yet paid",
		"Booked & Paid": "Booked & Paid",
		"Picked Up": "Picked Up",
		"In at Origin Hub": "In at Origin Hub",
		"In Transit": "In Transit",
		"In at Destination Hub": "In at Destination Hub",
		"Out for Delivery": "Out for Delivery",
		"Delivered": "Delivered",
		"Delivery Failed": "Delivery Attempt Failed",
		"Stuck at Hub": "Stuck at Hub",
	};

	function renderSummary(parcel) {
		summaryEl.innerHTML = `
			<table class="courier-table">
				<tr><td>Parcel</td><td><b>${parcel.name}</b>${parcel.is_return ? " (Return)" : ""}</td></tr>
				<tr><td>Status</td><td><span class="courier-badge">${STATUS_LABELS[parcel.status] || parcel.status}</span></td></tr>
				<tr><td>From</td><td>${parcel.sender_city}</td></tr>
				<tr><td>To</td><td>${parcel.recipient_city}</td></tr>
				<tr><td>Current Hub</td><td>${parcel.current_hub || "-"}</td></tr>
			</table>`;
	}

	function renderTimeline(events) {
		if (!events.length) {
			timelineEl.innerHTML = "<li>No scans recorded yet.</li>";
			return;
		}
		timelineEl.innerHTML = events
			.map(
				(e) => `
				<li>
					<div class="courier-timeline-status">${STATUS_LABELS[e.resulting_status] || e.resulting_status}</div>
					<div class="courier-timeline-meta">${e.scan_type}${e.hub ? " @ " + e.hub : ""} - ${e.scanned_at}</div>
					${e.failure_reason ? `<div class="courier-timeline-meta">${e.failure_reason}</div>` : ""}
				</li>`
			)
			.reverse()
			.join("");
	}

	function refresh() {
		Courier.call("courier_app.courier_app.api.get_tracking_timeline", {
			token: window.TRACK_TOKEN || undefined,
			parcel: window.TRACK_PARCEL || undefined,
		})
			.then((result) => {
				renderSummary(result.parcel);
				renderTimeline(result.events);
			})
			.catch((err) => Courier.banner("courier-banner", err.message, "error"));
	}

	refresh();
	setInterval(refresh, POLL_MS);
})();
