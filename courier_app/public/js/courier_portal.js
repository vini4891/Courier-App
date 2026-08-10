/**
 * Shared helpers for courier_app's server-rendered portal pages.
 * Loaded via an explicit <script src> tag (not colocated JS) so every
 * page can use the same fetch/CSRF/toast utilities without duplication.
 */
window.Courier = (function () {
	function call(method, args) {
		return fetch("/api/method/" + method, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": window.CSRF_TOKEN || "",
			},
			body: JSON.stringify(args || {}),
		}).then(async (res) => {
			let body = {};
			try {
				body = await res.json();
			} catch (e) {
				/* no body */
			}
			if (!res.ok) {
				const message = (body && (body._server_messages || body.exception || body.message)) || res.statusText;
				throw new Error(stripServerMessage(message));
			}
			return body.message;
		});
	}

	function stripServerMessage(message) {
		if (typeof message !== "string") return "Something went wrong.";
		try {
			const parsed = JSON.parse(message);
			if (Array.isArray(parsed) && parsed.length) {
				const inner = JSON.parse(parsed[0]);
				return inner.message || message;
			}
		} catch (e) {
			/* not a _server_messages blob, use as-is */
		}
		return message.replace(/^.*Error:\s*/, "");
	}

	function banner(elementId, text, kind) {
		const el = document.getElementById(elementId);
		if (!el) return;
		el.textContent = text;
		el.className = "courier-banner courier-banner-" + (kind || "info");
		el.style.display = "block";
	}

	return { call, banner };
})();
