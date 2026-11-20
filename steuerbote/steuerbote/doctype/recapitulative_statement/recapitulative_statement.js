const CONFIRMATION_EVENT = "steuerbote_vat_id_confirmation";

frappe.ui.form.on("Recapitulative Statement", {
	setup(frm) {
		frappe.realtime.on(CONFIRMATION_EVENT, (data) => on_confirmation_finished(frm, data));
		// Frappe asks to submit a draft, but Buchen alone files nothing: the filing marks submit it.
		frm.show_submit_message = () => {};
		leave_the_share_without_previous_amount_blank();
	},

	refresh(frm) {
		if (confirmation_state(frm).stale && frm.perm[0] && frm.perm[0].write) {
			frm.call("release_stale_confirmation").then(() => frm.reload_doc());
		}
		const draft = frm.doc.docstatus === 0 && !frm.is_new();
		const calculated = ["Berechnet", "Bereit"].includes(frm.doc.status);
		const free = draft && !frm.doc.confirmation_in_progress;
		if (draft) {
			frm.page.clear_primary_action();
		}
		if (free) {
			frm.add_custom_button(__("Calculate"), () => frm.call("calculate").then(() => frm.reload_doc()));
		}
		if (free && calculated) {
			frm.add_custom_button(__("Confirm VAT IDs"), () => confirm_vat_ids(frm));
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
			frm.add_custom_button(__("Filed in Mein ELSTER"), () => ask_for_filing_note(frm, "mein_elster"), group);
			frm.add_custom_button(__("Mark as Filed Outside"), () => ask_for_filing_note(frm, "other_way"), group);
		}
		show_ready_note(frm);
		show_intro(frm);
	},
});

function confirmation_state(frm) {
	return (frm.doc.__onload && frm.doc.__onload.confirmation) || {};
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

function saved(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the statement first."));
		return false;
	}
	return true;
}

function confirm_vat_ids(frm) {
	if (!saved(frm)) {
		return;
	}
	frappe.confirm(
		__(
			"Steuerbote asks the BZSt about each USt-IdNr. of the lines, with the name and town of the customer where they are known, one after the other; VIES answers only when the BZSt cannot. Every answer is kept as a USt-IdNr.-Bestätigung."
		),
		() =>
			frm.call("confirm_vat_ids").then((response) => {
				frappe.show_alert(
					{
						message: __(
							"The confirmation of {0} USt-IdNrn. runs in the background. A notice follows when it has finished.",
							[response.message]
						),
						indicator: "blue",
					},
					10
				);
				frm.reload_doc();
			})
	);
}

function make_csv_file(frm) {
	if (!saved(frm)) {
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
	if (!frm.is_new() && frm.doc.docstatus === 0 && frm.doc.status === "Bereit" && !frm.doc.confirmation_in_progress) {
		frm.$ready_note = frm.dashboard.set_headline_alert(
			__("Ready to file: make the CSV for Mein ELSTER and import it in the form there."),
			"blue"
		);
	}
}

function show_intro(frm) {
	const notes = [];
	if (!frm.is_new() && frm.doc.docstatus === 0) {
		if (frm.doc.confirmation_in_progress) {
			notes.push(__("The USt-IdNrn. are being confirmed. The form reloads when the confirmation has finished."));
		} else {
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
	frm.set_intro(notes.join("<br>"), "blue");
}

function on_confirmation_finished(frm, data) {
	const link = frappe.utils.get_form_link("Recapitulative Statement", data.statement, true);
	let message = __("The confirmation of the USt-IdNrn. of {0} has finished: {1} numbers asked.", [link, data.confirmed]);
	let indicator = "green";
	if (data.error) {
		message = __("The confirmation of the USt-IdNrn. of {0} stopped: {1}", [link, data.error]);
		indicator = "red";
	} else if ((data.failed || []).length) {
		message = __("The confirmation of {0} failed for {1}; the Error Log has the details.", [
			link,
			data.failed.join(", "),
		]);
		indicator = "orange";
	}
	frappe.show_alert({ message, indicator }, 15);
	if (frm.doc && frm.doc.name === data.statement) {
		frm.reload_doc();
	}
}
