frappe.ui.form.on("ERiC Settings", {
	setup(frm) {
		frappe.realtime.on("steuerbote_eric_installation", (data) => {
			if (data.ok) {
				frappe.show_alert(
					{ message: __("ERiC {0} is installed.", [data.version]), indicator: "green" },
					10
				);
			} else {
				frappe.msgprint({
					title: __("Installation of ERiC failed"),
					message: frappe.utils.escape_html(data.error || ""),
					indicator: "red",
				});
			}
			if (frm.doc && frm.doc.doctype === "ERiC Settings") {
				frm.reload_doc();
			}
		});
		frappe.realtime.on("steuerbote_taxonomy_installation", (data) => {
			if (data.ok) {
				frappe.show_alert(
					{
						message: __("The HGB-Taxonomie {0} is installed.", [data.versions.join(", ")]),
						indicator: "green",
					},
					10
				);
			} else {
				frappe.msgprint({
					title: __("Installation of the taxonomy failed"),
					message: frappe.utils.escape_html(data.error || ""),
					indicator: "red",
				});
			}
			if (frm.doc && frm.doc.doctype === "ERiC Settings") {
				frm.reload_doc();
			}
		});
	},

	refresh(frm) {
		frm.set_intro(
			frm.doc.simulation
				? __(
						"Simulation mode: until an ERiC runtime is installed and a Hersteller-ID is entered, Prüfen and Testsenden only simulate and nothing reaches the Finanzamt."
				  )
				: "",
			"orange"
		);
		show_version_check(frm);
		frm.add_custom_button(__("Install Runtime"), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__("Save the settings before installing."));
				return;
			}
			frm.call("install_runtime").then(() =>
				frappe.show_alert({
					message: __("The installation of ERiC runs in the background."),
					indicator: "blue",
				})
			);
		});
		frm.add_custom_button(__("Install Taxonomy"), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__("Save the settings before installing."));
				return;
			}
			frm.call("install_taxonomy").then(() =>
				frappe.show_alert({
					message: __("The installation of the taxonomy runs in the background."),
					indicator: "blue",
				})
			);
		});
		frm.add_custom_button(__("Check Runtime"), () =>
			frm.call("check_runtime").then((response) => show_status(response.message || []))
		);
	},
});

// The weekly check of the versions and the notice of its findings in the head of the form, each with its own
// state; the next refresh replaces the message.
function show_version_check(frm) {
	if (frm.$version_check) {
		frm.$version_check.remove();
		frm.$version_check = null;
	}
	const doc = frm.doc;
	if (!doc.versions_checked_on) {
		return;
	}
	const checked_on = frappe.datetime.str_to_user(doc.versions_checked_on);
	const lines = [
		doc.versions_check_failed
			? __("Last checked: {0} (failed). The Error Log names the reason.", [checked_on])
			: __("Last checked: {0} (succeeded).", [checked_on]),
	];
	const notice = notice_line(doc);
	if (notice) {
		lines.push(notice);
	}
	const failed = doc.versions_check_failed || doc.version_notice_status === "Not Delivered";
	const partly = ["Notification Only", "No Recipients"].includes(doc.version_notice_status);
	frm.$version_check = frm.dashboard.set_headline_alert(
		lines.map((line) => `<div>${frappe.utils.escape_html(line)}</div>`).join(""),
		failed ? "red" : partly ? "orange" : "green"
	);
}

// How the System Managers heard of the latest new findings, as the weekly check records it.
function notice_line(doc) {
	if (!doc.version_notice_status || !doc.version_notified_on) {
		return "";
	}
	const on = frappe.datetime.str_to_user(doc.version_notified_on);
	const lines = {
		"E-Mail and Notification": __(
			"Notice: the System Managers got an e-mail and a notification on {0}.",
			[on]
		),
		"Notification Only": __(
			"Notice: the System Managers got a notification only on {0}, as no outgoing e-mail account is set up.",
			[on]
		),
		"No Recipients": __(
			"Notice: nobody heard of the findings on {0}, as there is no enabled System Manager besides Administrator.",
			[on]
		),
		"Not Delivered": __(
			"Notice: not delivered on {0}. The Error Log names the reason; the next weekly check sends it.",
			[on]
		),
	};
	return lines[doc.version_notice_status] || "";
}

// The checks of steuerbote.eric.runtime.status, the plugin of the year and that of the Zusammenfassende Meldung
// among them, then those of steuerbote.eric.releases and of each version of the HGB-Taxonomie; their texts are
// German, as the runtime and the taxonomy write them for the operator.
function show_status(checks) {
	const lines = checks.map(
		(check) =>
			`<p><span class="indicator ${check.ok ? "green" : "red"}">${frappe.utils.escape_html(check.detail)}</span></p>`
	);
	frappe.msgprint({
		title: __("Status of the ERiC Runtime"),
		message: lines.join(""),
		indicator: checks.every((check) => check.ok) ? "green" : "orange",
	});
}
