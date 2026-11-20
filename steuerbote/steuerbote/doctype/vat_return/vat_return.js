{% include "steuerbote/public/js/elster_transmission.js" %}

frappe.ui.form.on("VAT Return", {
	setup(frm) {
		listen_for_transmissions(frm);
		// Frappe asks to submit a draft, but Buchen alone files nothing: show_ready_note says how to file.
		frm.show_submit_message = () => {};
		leave_unknown_comparison_values_blank();
	},

	refresh(frm) {
		release_stale_transmission(frm);
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
		frm.set_intro(elster_notes(frm, return_texts()).join("<br>"), "orange");
		add_elster_buttons(frm);
	},
});

// What the transmission says about a return, see elster_transmission.js.
function return_texts() {
	return {
		unsaved: __("Save the return before transmitting it."),
		send: __(
			"The return goes to the Finanzamt and is filed with it. Afterwards it can only be changed by a corrected return (Kz 10)."
		),
		test_send: __(
			"The return goes to the ELSTER server as a test case with the Testmerker and is deleted there on receipt. It stays a draft."
		),
		sent: __(
			"ELSTER accepted this return, but it could not be submitted afterwards. Do not send it again; submit it with Buchen once the cause is resolved."
		),
		running: __("A transmission of this return is running. The form reloads when it has finished."),
	};
}

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

function add_elster_buttons(frm) {
	const calculated = ["Berechnet", "Bereit"].includes(frm.doc.status);
	if (frm.is_new() || frm.doc.docstatus !== 0 || transmission_blocked(frm) || !calculated) {
		return;
	}
	const group = __("ELSTER");
	add_transmission_buttons(frm, group, return_texts());
	frm.add_custom_button(__("Filed in Mein ELSTER"), () => ask_for_filing_note(frm, "mein_elster"), group);
	frm.add_custom_button(__("Mark as Filed Outside"), () => ask_for_filing_note(frm, "other_way"), group);
}

function ask_for_filing_note(frm, filed_via) {
	if (!saved(frm, return_texts())) {
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
