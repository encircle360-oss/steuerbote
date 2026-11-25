{% include "steuerbote/public/js/elster_transmission.js" %}
{% include "steuerbote/public/js/vat_id_confirmation.js" %}

frappe.ui.form.on("Recapitulative Statement", {
	setup(frm) {
		listen_for_confirmations(frm);
		listen_for_transmissions(frm);
		// Frappe asks to submit a draft, but Buchen alone files nothing: Senden and the filing marks submit it.
		frm.show_submit_message = () => {};
		leave_the_share_without_previous_amount_blank();
	},

	refresh(frm) {
		release_stale_confirmation(frm);
		release_stale_transmission(frm);
		offer_buchen_only_for_an_accepted_send(frm);
		remove_discard_when_locked_as_sent(frm);
		const draft = frm.doc.docstatus === 0 && !frm.is_new();
		const calculated = ["Berechnet", "Bereit"].includes(frm.doc.status);
		const free = draft && !frm.doc.confirmation_in_progress && !transmission_blocked(frm);
		const changeable = free && !locked_as_sent(frm);
		if (changeable) {
			frm.add_custom_button(__("Calculate"), () => frm.call("calculate").then(() => frm.reload_doc()));
		}
		if (changeable && calculated && may_send(frm)) {
			frm.add_custom_button(__("Confirm VAT IDs"), () =>
				confirm_vat_ids(
					frm,
					__(
						"Steuerbote asks the BZSt about each USt-IdNr. of the lines, with the name and town of the customer where they are known, one after the other; VIES answers only when the BZSt cannot. Every answer is kept as a USt-IdNr.-Bestätigung."
					),
					statement_texts()
				)
			);
		}
		if (can_make_csv_file(frm.doc)) {
			frm.add_custom_button(__("CSV for Mein ELSTER"), () => make_csv_file(frm));
		}
		if (frm.doc.docstatus === 1 && frm.doc.status === "Abgegeben") {
			frm.add_custom_button(__("Make Berichtigung"), () => make_correction(frm));
			show_ledger_changes(frm);
		}
		if (free && calculated) {
			const group = __("ELSTER");
			add_transmission_buttons(frm, group, statement_texts());
			frm.add_custom_button(__("Filed in Mein ELSTER"), () => ask_for_filing_note(frm, "mein_elster"), group);
			frm.add_custom_button(__("Mark as Filed Outside"), () => ask_for_filing_note(frm, "other_way"), group);
		}
		show_ready_note(frm);
		show_latest_run(frm);
		show_intro(frm);
	},
});

// What the transmission says about a statement, see elster_transmission.js: it goes to the BZSt, not to a Finanzamt.
function statement_texts() {
	return {
		unsaved: __("Save the statement first."),
		send: __(
			"The statement goes to the BZSt and is filed with it. Afterwards a change goes to the BZSt as a Berichtigung."
		),
		test_send: __(
			"The statement goes to the ELSTER server as a test case with the Testmerker and is deleted there on receipt. It stays a draft."
		),
		sent: __(
			"ELSTER accepted this statement, but it could not be submitted afterwards. Do not send it again; submit it with Buchen once the cause is resolved."
		),
		running: __("A transmission of this statement is running. The form reloads when it has finished."),
		send_label: __("Transmit to the BZSt"),
		simulation: (link) =>
			__(
				"Simulation mode: Prüfen and Testsenden only simulate, nothing reaches the BZSt. Senden needs an installed ERiC runtime and a Hersteller-ID, see {0}.",
				[link]
			),
		simulated_test_send: __(
			"The simulation needs no certificate and no password: Testsenden runs against the simulation, nothing reaches the BZSt."
		),
	};
}

// The conditions of make_csv_file in recapitulative_statement.py: a statement that could be filed, or one filed.
function can_make_csv_file(doc) {
	if (doc.docstatus === 1) {
		return true;
	}
	const explained = doc.ready || (doc.remarks || "").trim();
	return doc.docstatus === 0 && ["Berechnet", "Bereit"].includes(doc.status) && Boolean(explained);
}

// A Percent field stores no blank, so a line without an amount in the previous period holds 0 as its share.
function leave_the_share_without_previous_amount_blank() {
	frappe.meta.set_formatter(
		"Recapitulative Statement Comparison",
		"difference_percent",
		null,
		(value, df, options, doc) =>
			!doc || !flt(doc.previous) ? "" : frappe.form.formatters.Percent(value, df, options, doc)
	);
}

function make_csv_file(frm) {
	if (!saved(frm, statement_texts())) {
		return;
	}
	frm.call("make_csv_file").then((response) => {
		frm.reload_doc();
		window.open(response.message);
		if (frm.doc.docstatus === 0) {
			frappe.show_alert(
				{
					message: __(
						"Import the file in the form Zusammenfassende Meldung of Mein ELSTER and file it there, then note the filing with Filed in Mein ELSTER."
					),
					indicator: "blue",
				},
				15
			);
		}
	});
}

function make_correction(frm) {
	frappe.confirm(
		__(
			"A Berichtigung reports, for the same Meldezeitraum, each line that changed against what was filed, with its new sum, and cancels a line filed wrongly with 0."
		),
		() => frm.call("make_correction").then((response) => frappe.set_route("Form", frm.doctype, response.message))
	);
}

function ask_for_filing_note(frm, filed_via) {
	if (!saved(frm, statement_texts())) {
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
					: __("For example: on 25 April 2026 by the Steuerberatung in the BZSt-Online-Portal."),
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

// Without the immutable ledger of the Accounts Settings, a cancellation changes the ledger of a month filed already.
function show_ledger_changes(frm) {
	const name = frm.doc.name;
	frm.call("ledger_changes_since_filing").then((response) => {
		const changes = response.message || [];
		if (!changes.length || frm.doc.name !== name) {
			return;
		}
		frm.dashboard.set_headline_alert(
			[
				__("The ledger of these months has changed since the filing; make a Berichtigung"),
				...changes.map((change) => frappe.utils.escape_html(change)),
			].join("<br>"),
			"orange"
		);
	});
}

function show_ready_note(frm) {
	if (frm.$ready_note) {
		frm.$ready_note.remove();
		frm.$ready_note = null;
	}
	const ready = frm.doc.docstatus === 0 && frm.doc.status === "Bereit" && !frm.doc.confirmation_in_progress;
	if (!frm.is_new() && ready && !transmission_blocked(frm)) {
		frm.$ready_note = frm.dashboard.set_headline_alert(
			__(
				"Ready to file: transmit the statement through ELSTER, or make the CSV for Mein ELSTER and import it in the form there."
			),
			"blue"
		);
	}
}

function show_intro(frm) {
	const notes = [];
	if (!frm.is_new() && frm.doc.docstatus === 0) {
		if (frm.doc.confirmation_in_progress) {
			notes.push(__("The USt-IdNrn. are being confirmed. The form reloads when the confirmation has finished."));
		} else if (!locked_as_sent(frm)) {
			notes.push(
				__(
					"Calculate reads the ledger of the months of the Meldezeitraum. Confirm VAT IDs asks the BZSt about each USt-IdNr. of the lines. The CSV file goes into the form Zusammenfassende Meldung of Mein ELSTER; note the filing afterwards with Filed in Mein ELSTER."
				)
			);
		}
		if (frm.doc.meldeart === "Berichtigung") {
			notes.push(
				__(
					"Berichtigung of {0}: the file holds the lines that change what was filed, a cancelled line with 0.",
					[frm.doc.corrects]
				)
			);
		}
	}
	const transmission = elster_notes(frm, statement_texts());
	frm.set_intro([...notes, ...transmission].join("<br>"), transmission.length ? "orange" : "blue");
}
