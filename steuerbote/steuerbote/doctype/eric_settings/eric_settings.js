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
		frm.add_custom_button(__("Check Runtime"), () =>
			frm.call("check_runtime").then((response) => show_status(response.message || []))
		);
	},
});

// A failed weekly check of the versions in the head of the form; the next refresh replaces the message.
function show_version_check(frm) {
	if (frm.$version_check) {
		frm.$version_check.remove();
		frm.$version_check = null;
	}
	if (frm.doc.versions_check_failed && frm.doc.versions_checked_on) {
		frm.$version_check = frm.dashboard.set_headline_alert(
			__("Last checked: {0} (failed). The Error Log names the reason.", [
				frappe.datetime.str_to_user(frm.doc.versions_checked_on),
			]),
			"red"
		);
	}
}

// The checks of steuerbote.eric.runtime.status, the plugin of the year and that of the Zusammenfassende Meldung
// among them, then those of steuerbote.eric.releases; their texts are German, as the runtime writes them for the
// operator.
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
