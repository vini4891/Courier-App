(function () {
	const scanTypeSelect = document.getElementById("scan-type");
	const hubField = document.getElementById("hub-field");
	const hubSelect = document.getElementById("hub-select");
	const reasonField = document.getElementById("reason-field");
	const failureReasonInput = document.getElementById("failure-reason");
	const startBtn = document.getElementById("start-scan-btn");
	const stopBtn = document.getElementById("stop-scan-btn");
	const manualTokenInput = document.getElementById("manual-token");
	const manualSubmitBtn = document.getElementById("manual-submit-btn");
	const resultEl = document.getElementById("scan-result");

	const HUB_REQUIRED_TYPES = ["Pickup", "Hub In", "Hub Out"];
	const REASON_TYPES = ["Delivery Failed", "Marked Stuck"];

	let html5QrCode = null;
	let lastCameraKey = null;
	let lastCameraAt = 0;

	function syncFieldVisibility() {
		const scanType = scanTypeSelect.value;
		hubField.style.display = HUB_REQUIRED_TYPES.includes(scanType) ? "" : "none";
		reasonField.style.display = REASON_TYPES.includes(scanType) ? "" : "none";
	}
	scanTypeSelect.addEventListener("change", syncFieldVisibility);
	syncFieldVisibility();

	Courier.call("courier_app.courier_app.doctype.hub.hub.get_active_hubs")
		.then((hubs) => {
			hubSelect.innerHTML = hubs.map((h) => `<option value="${h.name}">${h.hub_name} (${h.city})</option>`).join("");
		})
		.catch((err) => Courier.banner("courier-banner", err.message, "error"));

	function showResult(kind, title, detail) {
		resultEl.innerHTML = `
			<div class="courier-banner courier-banner-${kind}" style="display:block; font-size:16px;">
				<b>${title}</b><br>${detail || ""}
			</div>`;
	}

	function submitScan(token) {
		token = (token || "").trim();
		if (!token) return;

		const scanType = scanTypeSelect.value;
		const args = { token: token, scan_type: scanType };
		if (HUB_REQUIRED_TYPES.includes(scanType)) args.hub = hubSelect.value;
		if (REASON_TYPES.includes(scanType)) args.failure_reason = failureReasonInput.value;

		Courier.call("courier_app.courier_app.api.record_scan", args)
			.then((result) => {
				if (result.is_duplicate) {
					showResult("info", "Already recorded", `${result.parcel} is already at "${result.status}".`);
				} else {
					showResult("success", "Scan accepted", `${result.parcel} -> "${result.status}"`);
				}
				manualTokenInput.value = "";
			})
			.catch((err) => showResult("error", "Scan rejected", err.message));
	}

	/**
	 * The camera decoder calls its onScanSuccess callback continuously
	 * (many times a second) for as long as the same QR code stays in
	 * frame, so IT needs a debounce - keyed on token+scan_type (not just
	 * token), since an agent legitimately re-submits the same token for a
	 * different scan_type moments later. Manual "Submit" clicks are
	 * already a single deliberate action and are never debounced - a
	 * genuine accidental double-click is harmless anyway, since the
	 * server itself is idempotent (see scan_event.record_scan).
	 */
	function onCameraDecoded(token) {
		token = (token || "").trim();
		if (!token) return;
		const key = token + "|" + scanTypeSelect.value;
		const now = Date.now();
		if (key === lastCameraKey && now - lastCameraAt < 4000) return;
		lastCameraKey = key;
		lastCameraAt = now;
		submitScan(token);
	}

	manualSubmitBtn.addEventListener("click", () => submitScan(manualTokenInput.value));
	manualTokenInput.addEventListener("keydown", (e) => {
		if (e.key === "Enter") submitScan(manualTokenInput.value);
	});

	startBtn.addEventListener("click", () => {
		frappe.require("/assets/frappe/node_modules/html5-qrcode/html5-qrcode.min.js").then(() => {
			html5QrCode = new Html5Qrcode("courier-scanner-reader"); // eslint-disable-line no-undef
			html5QrCode
				.start(
					{ facingMode: "environment" },
					{ fps: 10, qrbox: 250 },
					(decodedText) => onCameraDecoded(decodedText),
					() => {}
				)
				.then(() => {
					startBtn.style.display = "none";
					stopBtn.style.display = "";
				})
				.catch((err) => showResult("error", "Camera error", String(err)));
		});
	});

	stopBtn.addEventListener("click", () => {
		if (html5QrCode) {
			html5QrCode.stop().then(() => {
				startBtn.style.display = "";
				stopBtn.style.display = "none";
			});
		}
	});
})();
