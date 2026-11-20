frappe.ui.form.on("VAT Return Extension", {
	setup(frm) {
		// Frappe asks to submit a draft, but Buchen alone files nothing: show_ready_note says how to file.
		frm.show_submit_message = () => {};
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.page.clear_primary_action();
			frm.add_custom_button(__("Calculate"), () => frm.call("calculate").then(() => frm.reload_doc()));
		}
		show_intro(frm);
		show_ready_note(frm);
		add_filing_buttons(frm);
	},
});

function show_intro(frm) {
	const intro =
		frm.doc.docstatus === 0
			? __(
					"Mein ELSTER has no upload for form USt 1 H, and Steuerbote does not transmit it through ERiC yet. Calculate the form, enter it in Mein ELSTER by hand, with Kz 38 as the Sondervorauszahlung if the company files monthly, and then note the filing here with Entered in Mein ELSTER."
			  )
			: "";
	frm.set_intro(intro, "blue");
}

function show_ready_note(frm) {
	if (frm.$ready_note) {
		frm.$ready_note.remove();
		frm.$ready_note = null;
	}
	if (!frm.is_new() && frm.doc.docstatus === 0 && frm.doc.status === "Bereit") {
		frm.$ready_note = frm.dashboard.set_headline_alert(
			__("Ready to file: enter the form in Mein ELSTER, then note it with Entered in Mein ELSTER."),
			"blue"
		);
	}
}

function add_filing_buttons(frm) {
	const calculated = ["Berechnet", "Bereit"].includes(frm.doc.status);
	if (frm.is_new() || frm.doc.docstatus !== 0 || !calculated) {
		return;
	}
	const group = __("ELSTER");
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
