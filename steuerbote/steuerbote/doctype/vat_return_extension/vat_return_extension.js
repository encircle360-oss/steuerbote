{% include "steuerbote/public/js/elster_transmission.js" %}
{% include "steuerbote/public/js/timeline_values.js" %}

frappe.ui.form.on("VAT Return Extension", {
	timeline_refresh(frm) {
		translate_select_values_in_timeline(frm);
	},

	setup(frm) {
		listen_for_transmissions(frm);
		// Frappe asks to submit a draft, but Buchen alone files nothing: show_ready_note says how to file.
		frm.show_submit_message = () => {};
	},

	refresh(frm) {
		release_stale_transmission(frm);
		offer_buchen_only_for_an_accepted_send(frm);
		remove_discard_when_locked_as_sent(frm);
		if (frm.doc.docstatus === 0 && !frm.is_new() && !locked_as_sent(frm)) {
			frm.add_custom_button(__("Calculate"), () => frm.call("calculate").then(() => frm.reload_doc()));
		}
		show_intro(frm);
		show_ready_note(frm);
		show_latest_run(frm);
		add_filing_buttons(frm);
	},
});

// What the transmission says about a form, see elster_transmission.js.
function form_texts() {
	return {
		unsaved: __("Save the form before transmitting it."),
		send: __("The form goes to the Finanzamt and is filed with it."),
		test_send: __(
			"The form goes to the ELSTER server as a test case with the Testmerker and is deleted there on receipt. It stays a draft."
		),
		sent: __(
			"ELSTER accepted this form, but it could not be submitted afterwards. Do not send it again; submit it with Buchen once the cause is resolved."
		),
		running: __("A transmission of this form is running. The form reloads when it has finished."),
	};
}

// Without ERiC, Senden is not possible, and Mein ELSTER takes no file for form USt 1 H. A form locked as sent is
// neither calculated nor entered again. A draft past its due date says so (onload of the controller).
function show_intro(frm) {
	const notes = elster_notes(frm, form_texts());
	const overdue = frm.doc.__onload && frm.doc.__onload.overdue;
	if (overdue) {
		notes.push(frappe.utils.escape_html(overdue));
	}
	if (!frm.is_new() && frm.doc.docstatus === 0 && eric_simulates(frm) && !locked_as_sent(frm)) {
		notes.push(
			__(
				"Mein ELSTER has no upload for form USt 1 H. Until Senden runs with an installed ERiC runtime and a Hersteller-ID, calculate the form, enter it in Mein ELSTER by hand, with Kz 38 as the Sondervorauszahlung if the company files monthly, and then note the filing here with Entered in Mein ELSTER."
			)
		);
	}
	frm.set_intro(notes.join("<br>"), "orange");
}

function show_ready_note(frm) {
	if (frm.$ready_note) {
		frm.$ready_note.remove();
		frm.$ready_note = null;
	}
	const ready = frm.doc.docstatus === 0 && frm.doc.status === "Bereit" && !transmission_blocked(frm);
	if (!frm.is_new() && ready) {
		frm.$ready_note = frm.dashboard.set_headline_alert(
			__(
				"Ready to file: transmit the form through ELSTER, or enter it in Mein ELSTER and note it with Entered in Mein ELSTER."
			),
			"blue"
		);
	}
}

function add_filing_buttons(frm) {
	const calculated = ["Berechnet", "Bereit"].includes(frm.doc.status);
	if (frm.is_new() || frm.doc.docstatus !== 0 || transmission_blocked(frm) || !calculated) {
		return;
	}
	const group = __("ELSTER");
	add_transmission_buttons(frm, group, form_texts());
	frm.add_custom_button(__("Entered in Mein ELSTER"), () => ask_for_filing_note(frm, "mein_elster"), group);
	frm.add_custom_button(__("Mark as Filed Outside"), () => ask_for_filing_note(frm, "other_way"), group);
}

function ask_for_filing_note(frm, filed_via) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the form before noting its filing."));
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
				fieldname: "note",
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
					filed_via,
					note: values.note,
					transferticket: values.transferticket,
					filed_on: values.filed_on,
				})
				.then(() => frm.reload_doc()),
		in_mein_elster ? __("Entered in Mein ELSTER") : __("Mark as Filed Outside"),
		__("Mark as Filed")
	);
}
