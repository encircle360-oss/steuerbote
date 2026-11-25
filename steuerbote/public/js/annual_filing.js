// The pieces the forms of the annual documents share: Berechnen, the findings, Berichtigung anlegen and the notes of a
// filing in Mein ELSTER or another way, as the base steuerbote/steuerbote/annual_filing.py serves them. A form that
// goes to ELSTER includes elster_transmission.js before this file. Each form calls annual_filing_setup in its setup
// and annual_filing_refresh in its refresh, with the texts that name its document: those of elster_transmission.js,
// and berichtigung, ready and filed_outside_example.

function annual_state(frm) {
	return (frm.doc.__onload && frm.doc.__onload.annual_filing) || {};
}

// Whether the form includes elster_transmission.js, the document going to ELSTER.
function annual_transmits() {
	return typeof elster_state === "function";
}

function annual_filing_setup(frm) {
	if (frm.doctype !== "Annual Accounts") {
		// Buchen alone files no Erklärung and no E-Bilanz, so Frappe's banner that asks for it stays away from the
		// first refresh on, also after a transmission reloads the form.
		frm.show_submit_message = () => {};
	}
	if (annual_transmits()) {
		listen_for_transmissions(frm);
	}
}

function annual_filing_refresh(frm, texts) {
	const state = annual_state(frm);
	const transmits = annual_transmits();
	if (!state.submitted_by_hand) {
		// Frappe asks to submit a draft, but Buchen alone files nothing: Senden and the notes of a filing submit it.
		frm.show_submit_message = () => {};
	}
	if (transmits) {
		release_stale_transmission(frm);
		offer_buchen_only_for_an_accepted_send(frm);
		remove_discard_when_locked_as_sent(frm);
	}
	const draft = frm.doc.docstatus === 0 && !frm.is_new();
	const calculated = (state.calculated || []).includes(frm.doc.status);
	const free = draft && !(transmits && transmission_blocked(frm));
	if (free && !(transmits && locked_as_sent(frm))) {
		frm.add_custom_button(__("Calculate"), () => frm.call("calculate").then(() => frm.reload_doc()));
	}
	if (frm.doc.docstatus === 1 && !state.submitted_by_hand) {
		// A filed Erklärung or E-Bilanz is never cancelled; a change goes to the Finanzamt as a Berichtigung.
		frm.page.clear_secondary_action();
	}
	if (state.can_correct) {
		frm.add_custom_button(__("Make Berichtigung"), () => annual_make_berichtigung(frm, texts));
	}
	if (transmits && free && calculated) {
		annual_transmission_buttons(frm, state, texts);
	}
	annual_findings_note(frm, texts);
	if (!frm.is_new() && (frm.doc.findings || []).some((row) => !row.blocking)) {
		// The printout shows the hints by kind; every hint goes into its annex only on request.
		frm.add_custom_button(__("Print with All Hints"), () => {
			const query = new URLSearchParams({ doctype: frm.doctype, name: frm.doc.name, all_hints: 1 });
			window.open(`/printview?${query.toString()}`);
		});
	}
	const notes = [...annual_filing_notes(frm, state)];
	if (transmits) {
		show_latest_run(frm);
		notes.push(...elster_notes(frm, texts));
	}
	frm.set_intro(notes.join("<br>"), "orange");
}

function annual_transmission_buttons(frm, state, texts) {
	const group = __("ELSTER");
	add_transmission_buttons(frm, group, texts);
	const filed_outside = state.filed_outside || [];
	if (filed_outside.includes("mein_elster")) {
		const label = __("Filed in Mein ELSTER");
		frm.add_custom_button(label, () => annual_filing_note(frm, "mein_elster", texts), group);
	}
	if (filed_outside.includes("other_way")) {
		const label = __("Mark as Filed Outside");
		frm.add_custom_button(label, () => annual_filing_note(frm, "other_way", texts), group);
	}
}

// How and when a filed document went to the authority, from the fields of its filing.
function annual_filing_notes(frm, state) {
	if (!(state.filings || []).includes(frm.doc.status) || !frm.doc.filed_on) {
		return [];
	}
	return [
		__("Filed on {0} ({1}).", [
			frappe.datetime.str_to_user(frm.doc.filed_on),
			__(frm.doc.filed_via || "other_way"),
		]),
	];
}

// An error of the findings holds a calculated document back from Bereit until it is corrected or, where it may be,
// acknowledged with a reason on the finding itself; the remarks file nothing (steuerbote/jahresmeldung/
// acknowledgements.py).
function annual_findings_note(frm, texts) {
	if (frm.$findings_note) {
		frm.$findings_note.remove();
		frm.$findings_note = null;
	}
	if (frm.is_new() || frm.doc.docstatus !== 0) {
		return;
	}
	const errors = (frm.doc.findings || []).filter((row) => row.blocking);
	const open = errors.filter((row) => !(row.acknowledged && row.acknowledgement_reason));
	if (frm.doc.ready) {
		frm.$findings_note = frm.dashboard.set_headline_alert(texts.ready || __("Ready to file."), "blue");
	} else if (open.length) {
		frm.$findings_note = frm.dashboard.set_headline_alert(
			__(
				"Errors of the findings hold the document: {0}. Correct them and calculate again, or acknowledge those that may be with the reason why it is filed nonetheless.",
				[open.length]
			),
			"red"
		);
	} else if (errors.length) {
		frm.$findings_note = frm.dashboard.set_headline_alert(
			__("Every error of the findings is acknowledged; the document is filed nonetheless."),
			"orange"
		);
	}
	const calculated = (annual_state(frm).calculated || []).includes(frm.doc.status);
	if (calculated && errors.some((row) => row.acknowledgeable)) {
		frm.add_custom_button(__("Acknowledge Errors"), () => annual_acknowledge_errors(frm));
	}
}

function annual_acknowledge_errors(frm) {
	const errors = (frm.doc.findings || []).filter((row) => row.blocking && row.acknowledgeable);
	const escape = frappe.utils.escape_html;
	const fields = [];
	for (const row of errors) {
		fields.push(
			{
				fieldtype: "HTML",
				fieldname: `finding_${row.idx}`,
				options: `<p><b>${escape(row.code)}</b> ${escape(row.text || "")}</p>`,
			},
			{
				fieldtype: "Small Text",
				fieldname: `reason_${row.idx}`,
				label: __("Reason for Filing Nonetheless"),
				default: row.acknowledgement_reason || "",
			}
		);
	}
	const blocked = (frm.doc.findings || []).filter((row) => row.blocking && !row.acknowledgeable);
	if (blocked.length) {
		fields.push({
			fieldtype: "HTML",
			fieldname: "never",
			options: `<p>${__("These errors make the file wrong whatever the reason and are corrected in the books or the mapping: {0}", [blocked.map((row) => escape(row.code)).join(", ")])}</p>`,
		});
	}
	const dialog = new frappe.ui.Dialog({
		title: __("Acknowledge Errors"),
		fields,
		primary_action_label: __("Acknowledge Errors"),
		primary_action: async (values) => {
			for (const row of errors) {
				const reason = (values[`reason_${row.idx}`] || "").trim();
				if (reason !== (row.acknowledgement_reason || "")) {
					await frm.call("acknowledge_finding", { finding: row.name, reason });
				}
			}
			dialog.hide();
			frm.reload_doc();
		},
	});
	dialog.show();
}

function annual_make_berichtigung(frm, texts) {
	const make = () => frm.call("make_correction").then((r) => frappe.set_route("Form", frm.doctype, r.message));
	frappe.confirm(
		texts.berichtigung ||
			__(
				"A Berichtigung is a new and complete document for the same company and year that corrects this one. It starts with its corrections and lines by hand and is calculated at once."
			),
		make
	);
}

function annual_filing_note(frm, filed_via, texts) {
	if (annual_transmits() && !saved(frm, texts)) {
		return;
	}
	const in_mein_elster = filed_via === "mein_elster";
	// A dialog that stays open when the server refuses what was entered, such as a wrong Transferticket, so that
	// nothing typed is lost.
	const dialog = new frappe.ui.Dialog({
		title: in_mein_elster ? __("Filed in Mein ELSTER") : __("Mark as Filed Outside"),
		fields: [
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
				fieldname: "note",
				label: in_mein_elster ? __("Remarks") : __("How and When Filed"),
				description: in_mein_elster ? "" : texts.filed_outside_example || "",
				reqd: in_mein_elster ? 0 : 1,
			},
		],
		primary_action_label: __("Mark as Filed"),
		primary_action: (values) => annual_mark_filed(frm, filed_via, values, dialog),
	});
	dialog.show();
}

function annual_mark_filed(frm, filed_via, values, dialog) {
	const { note, transferticket, filed_on } = values;
	frm.call("mark_filed_outside", { filed_via, note, transferticket, filed_on }).then(() => {
		dialog.hide();
		frm.reload_doc();
	});
}
