const TRANSMISSION_EVENT = "steuerbote_elster_transmission";
const STASH_CERTIFICATE = "steuerbote.steuerbote.doctype.vat_return.vat_return.stash_certificate";

frappe.ui.form.on("VAT Return", {
	setup(frm) {
		frappe.realtime.on(TRANSMISSION_EVENT, (data) => on_transmission_finished(frm, data));
		// Frappe asks to submit a draft, but Buchen alone files nothing: show_ready_note says how to file.
		frm.show_submit_message = () => {};
		leave_unknown_comparison_values_blank();
	},

	refresh(frm) {
		if (elster_state(frm).stale && frm.perm[0] && frm.perm[0].write) {
			frm.call("release_stale_transmission").then(() => frm.reload_doc());
		}
		offer_buchen_only_for_an_accepted_send(frm);
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("Calculate"), () => frm.call("calculate").then(() => frm.reload_doc()));
		}
		if (can_make_import_file(frm.doc)) {
			frm.add_custom_button(__("XML for Mein ELSTER"), () => make_import_file(frm));
		}
		if (!frm.is_new()) {
			frm.add_custom_button(
				__("UStVA Kennzahlen"),
				() =>
					frappe.set_route("query-report", "UStVA Kennzahlen", {
						company: frm.doc.company,
						year: frm.doc.year,
						rhythm: frm.doc.rhythm,
						period_index: frm.doc.period_index,
					}),
				__("View")
			);
		}
		show_ready_note(frm);
		show_elster_intro(frm);
		add_elster_buttons(frm);
	},
});

// The conditions of make_import_file in vat_return.py: a return that could be filed, or the return filed.
function can_make_import_file(doc) {
	if (doc.docstatus === 1) {
		return doc.status === "Abgegeben";
	}
	const explained = doc.ready || (doc.remarks || "").trim();
	return doc.docstatus === 0 && ["Berechnet", "Bereit"].includes(doc.status) && Boolean(explained);
}

function make_import_file(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the return before making the file for Mein ELSTER."));
		return;
	}
	frm.call("make_import_file").then((response) => {
		frm.reload_doc();
		window.open(response.message);
		if (frm.doc.docstatus === 0) {
			frappe.show_alert(
				{
					message: __(
						"Import the file in Mein ELSTER and file the return there, then record the filing with Filed in Mein ELSTER."
					),
					indicator: "blue",
				},
				15
			);
		}
	});
}

function elster_state(frm) {
	return (frm.doc.__onload && frm.doc.__onload.elster) || {};
}

function eric_simulates(frm) {
	const elster = frm.doc.__onload && frm.doc.__onload.elster;
	return !elster || elster.simulation;
}

// Buchen alone files nothing, so a draft gets no Submit button; only a return ELSTER accepted while its
// submission failed is submitted with it.
function offer_buchen_only_for_an_accepted_send(frm) {
	if (frm.doc.docstatus === 0 && !frm.is_new() && !elster_state(frm).sent) {
		frm.page.clear_primary_action();
	}
}

// A Currency or Percent field stores no blank, so the comparison holds 0 for what it does not know: the
// values of a period without a catalogue of Kennzahlen, and the share of a Kennzahl without an earlier amount.
function leave_unknown_comparison_values_blank() {
	const known_with = {
		previous_period: "previous_period_known",
		previous_year: "previous_year_known",
		difference: "previous_period_known",
		difference_percent: "previous_period_known",
	};
	for (const [fieldname, known] of Object.entries(known_with)) {
		frappe.meta.set_formatter("VAT Return Comparison", fieldname, null, (value, df, options, doc) => {
			const without_share = fieldname === "difference_percent" && doc && !flt(doc.previous_period);
			return !doc || !doc[known] || without_share
				? ""
				: frappe.form.formatters[df.fieldtype](value, df, options, doc);
		});
	}
}

function transmission_blocked(frm) {
	return frm.doc.transmission_in_progress || elster_state(frm).sent;
}

function ready_to_file(frm) {
	return (
		!frm.is_new() &&
		frm.doc.docstatus === 0 &&
		frm.doc.status === "Bereit" &&
		!transmission_blocked(frm)
	);
}

function show_ready_note(frm) {
	if (frm.$ready_note) {
		frm.$ready_note.remove();
		frm.$ready_note = null;
	}
	if (ready_to_file(frm)) {
		frm.$ready_note = frm.dashboard.set_headline_alert(
			__("Ready to file: make the XML for Mein ELSTER or transmit through ELSTER."),
			"blue"
		);
	}
}

function show_elster_intro(frm) {
	const notes = [];
	if (!frm.is_new() && frm.doc.docstatus === 0) {
		if (elster_state(frm).sent) {
			notes.push(
				__(
					"ELSTER accepted this return, but it could not be submitted afterwards. Do not send it again; submit it with Buchen once the cause is resolved."
				)
			);
		}
		if (frm.doc.transmission_in_progress) {
			notes.push(__("A transmission of this return is running. The form reloads when it has finished."));
		}
		if (eric_simulates(frm)) {
			const link = `<a href="/app/${frappe.router.slug("ERiC Settings")}">${__("ERiC Settings")}</a>`;
			notes.push(
				__(
					"Simulation mode: Prüfen and Testsenden only simulate, nothing reaches the Finanzamt. Senden needs an installed ERiC runtime and a Hersteller-ID, see {0}.",
					[link]
				)
			);
		}
	}
	frm.set_intro(notes.join("<br>"), "orange");
}

function add_elster_buttons(frm) {
	const calculated = ["Berechnet", "Bereit"].includes(frm.doc.status);
	if (frm.is_new() || frm.doc.docstatus !== 0 || transmission_blocked(frm) || !calculated) {
		return;
	}
	const group = __("ELSTER");
	if (eric_simulates(frm)) {
		frm.add_custom_button(__("Validate with ERiC (Simulation)"), () => start(frm, "validate"), group);
		const label = __("Test Transmission (Simulation)");
		frm.add_custom_button(label, () => ask_for_certificate(frm, "test_send", label), group);
	} else {
		frm.add_custom_button(__("Validate with ERiC"), () => start(frm, "validate"), group);
		const test_label = __("Test Transmission");
		frm.add_custom_button(test_label, () => ask_for_certificate(frm, "test_send", test_label), group);
		const send_label = __("Transmit to the Finanzamt");
		frm.add_custom_button(send_label, () => ask_for_certificate(frm, "send", send_label), group);
	}
	frm.add_custom_button(__("Filed in Mein ELSTER"), () => ask_for_filing_note(frm, "mein_elster"), group);
	frm.add_custom_button(__("Mark as Filed Outside"), () => ask_for_filing_note(frm, "other_way"), group);
}

function saved(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the return before transmitting it."));
		return false;
	}
	return true;
}

function start(frm, operation, token) {
	if (!saved(frm)) {
		return;
	}
	frm.call("transmit", token ? { operation, token } : { operation }).then(() => {
		frappe.show_alert({
			message: __("The transmission runs in the background. A notice follows when it has finished."),
			indicator: "blue",
		});
		frm.reload_doc();
	});
}

function ask_for_certificate(frm, operation, title) {
	if (!saved(frm)) {
		return;
	}
	if (eric_simulates(frm)) {
		frappe.confirm(
			__(
				"The simulation needs no certificate and no password: Testsenden runs against the simulation, nothing reaches the Finanzamt."
			),
			() => start(frm, operation)
		);
		return;
	}
	const notice =
		operation === "send"
			? __(
					"The return goes to the Finanzamt and is filed with it. Afterwards it can only be changed by a corrected return (Kz 10)."
			  )
			: __(
					"The return goes to the ELSTER server as a test case with the Testmerker and is deleted there on receipt. It stays a draft."
			  );
	const dialog = new frappe.ui.Dialog({
		title,
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "notice",
				options: `<p>${notice}</p><p class="text-muted">${__(
					"Certificate and password serve this transmission only. Steuerbote does not keep them."
				)}</p>`,
			},
			{
				fieldtype: "HTML",
				fieldname: "certificate_file",
				options: `<div class="form-group"><label class="control-label reqd">${__(
					"Certificate File (.pfx)"
				)}</label><input type="file" class="form-control" accept=".pfx,.p12"></div>`,
			},
			{
				fieldtype: "Password",
				fieldname: "certificate_password",
				label: __("Certificate Password"),
				reqd: 1,
			},
		],
		primary_action_label: title,
		primary_action(values) {
			const input = dialog.fields_dict.certificate_file.$wrapper.find("input[type=file]").get(0);
			const file = input.files[0];
			if (!file) {
				frappe.msgprint(__("Choose the certificate file."));
				return;
			}
			const certificate_password = values.certificate_password;
			input.value = "";
			dialog.fields_dict.certificate_password.$input.val("");
			dialog.hide();
			frappe.dom
				.file_to_base64(file)
				.then((data_url) =>
					frappe.call({
						method: STASH_CERTIFICATE,
						args: { certificate_secret: data_url.split(",")[1] || "", certificate_password },
						freeze: true,
					})
				)
				.then((r) => start(frm, operation, r.message));
		},
	});
	// The password control of Frappe rates every keystroke on the server; a certificate password stays here.
	dialog.fields_dict.certificate_password.disable_password_checks();
	dialog.show();
}

function ask_for_filing_note(frm, filed_via) {
	if (!saved(frm)) {
		return;
	}
	const in_mein_elster = filed_via === "mein_elster";
	frappe.prompt(
		[
			{
				fieldtype: "Data",
				fieldname: "transferticket",
				label: __("Transferticket"),
				description: __("32 characters, as the protocol of ELSTER shows them. Optional."),
			},
			{
				fieldtype: "Date",
				fieldname: "filed_on",
				label: __("Filed On"),
				default: frappe.datetime.get_today(),
			},
			{
				fieldtype: "Small Text",
				fieldname: "remarks",
				label: in_mein_elster ? __("Remarks") : __("How and When Filed"),
				description: in_mein_elster
					? ""
					: __("For example: on 10 April 2026 by the Steuerberatung, with the protocol in the files."),
				reqd: in_mein_elster ? 0 : 1,
			},
		],
		(values) =>
			frm
				.call("mark_filed_outside", {
					remarks: values.remarks,
					filed_via,
					transferticket: values.transferticket,
					filed_on: values.filed_on,
				})
				.then(() => frm.reload_doc()),
		in_mein_elster ? __("Filed in Mein ELSTER") : __("Mark as Filed Outside"),
		__("Mark as Filed")
	);
}

function on_transmission_finished(frm, data) {
	const procedure = data.simulated ? __("{0} (Simulation)", [__(data.operation)]) : __(data.operation);
	const link = frappe.utils.get_form_link("ELSTER Transmission", data.transmission, true);
	const notices = {
		Erfolgreich: [__("{0} for {1} succeeded, see {2}.", [procedure, data.vat_return, link]), "green"],
		Unbekannt: [
			__(
				"Whether {0} for {1} reached ELSTER is unknown, see {2}. Check in Mein ELSTER before sending again.",
				[procedure, data.vat_return, link]
			),
			"orange",
		],
	};
	const [message, indicator] = notices[data.status] || [
		__("{0} for {1} failed, see {2}.", [procedure, data.vat_return, link]),
		"red",
	];
	frappe.show_alert({ message, indicator }, 15);
	if (frm.doc && frm.doc.name === data.vat_return) {
		frm.reload_doc();
	}
}
