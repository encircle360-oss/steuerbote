// The USt-IdNr. of a customer or supplier: where its confirmation stands for each company that confirms it, and the
// button that confirms it at the BZSt in the background. The server side is steuerbote/steuerbote/partner_vat_ids.py.
// hooks.py loads this file for both forms; the flag keeps it from adding its handlers twice.

if (!window.steuerbote_partner_vat_id) {
	window.steuerbote_partner_vat_id = true;
	const STATE_METHOD = "steuerbote.steuerbote.partner_vat_ids.vat_id_state";
	const CONFIRM_METHOD = "steuerbote.steuerbote.partner_vat_ids.confirm_vat_id";
	const PARTNER_EVENT = "steuerbote_partner_vat_id";
	const INDICATORS = { Current: "green", Invalid: "red", Malformed: "red", "Not Confirmable": "red" };

	const show_vat_id_state = (frm) => {
		frappe.call({ method: STATE_METHOD, args: { party_type: frm.doctype, party: frm.doc.name } }).then((response) => {
			const state = response.message;
			const escape = frappe.utils.escape_html;
			const lines = [];
			if (state.problem) {
				lines.push(escape(__("The USt-IdNr. is never sent: {0}", [state.problem])));
			}
			for (const row of state.companies) {
				const answered = row.asked_on
					? __("latest answer of {0}", [frappe.datetime.str_to_user(row.asked_on)])
					: __("no answer yet");
				const color = INDICATORS[row.standing] || "orange";
				lines.push(
					`<span class="indicator ${color}">${escape(row.company)}: ${escape(row.standing_label)} (${escape(
						answered
					)})</span>`
				);
			}
			const manual = state.companies.filter((row) => !row.automatic).map((row) => row.company);
			if (manual.length) {
				lines.push(
					escape(
						__("The automatic check is off for {0}: Steuerbote confirms only on the button.", [
							manual.join(", "),
						])
					)
				);
			}
			if (state.queued) {
				lines.push(escape(__("A confirmation of the USt-IdNr. is waiting in the queue.")));
			}
			frm.dashboard.set_headline_alert(lines.length ? `<div>${lines.join("<br>")}</div>` : "");
			if (state.can_ask) {
				frm.add_custom_button(__("Confirm VAT ID"), () => confirm_vat_id(frm, state));
			}
		});
	};

	// The dialog names everything that leaves the site.
	const confirm_vat_id = (frm, state) => {
		const escape = frappe.utils.escape_html;
		const companies = state.companies.map((row) => escape(row.company)).join(", ");
		const sent = state.has_details
			? __("its own USt-IdNr., the USt-IdNr. {0} and the name, street, postal code and town of the partner", [
					escape(frm.doc.tax_id),
			  ])
			: __("its own USt-IdNr. and the USt-IdNr. {0}", [escape(frm.doc.tax_id)]);
		const question = __(
			"Steuerbote asks the BZSt in the background for {0}, with {1}. Only when the BZSt cannot answer does the same go to VIES of the European Commission. Every answer is kept as a USt-IdNr.-Bestätigung. The query goes out also while ERiC runs as a simulation: the simulation stands in for ELSTER only.",
			[companies, sent]
		);
		frappe.confirm(question, () =>
			frappe.call({ method: CONFIRM_METHOD, args: { party_type: frm.doctype, party: frm.doc.name } }).then(() => {
				frappe.show_alert(
					{
						message: __("The confirmation runs in the background. A notice follows when it has finished."),
						indicator: "blue",
					},
					10
				);
			})
		);
	};

	const on_partner_confirmed = (frm, data) => {
		if (data.party_type !== frm.doctype || data.party !== frm.doc.name) {
			return;
		}
		const failed = (data.failed || []).length;
		frappe.show_alert(
			{
				message: failed
					? __("The confirmation of the USt-IdNr. failed for {0}; the Error Log has the details.", [
							frappe.utils.escape_html(data.failed.join(", ")),
					  ])
					: __("The confirmation of the USt-IdNr. has finished: {0}.", [__(data.status || "Not Checked")]),
				indicator: failed ? "orange" : "green",
			},
			15
		);
		frm.reload_doc();
	};

	for (const doctype of ["Customer", "Supplier"]) {
		frappe.ui.form.on(doctype, {
			setup(frm) {
				frappe.realtime.on(PARTNER_EVENT, (data) => on_partner_confirmed(frm, data));
			},
			refresh(frm) {
				if (!frm.is_new()) {
					show_vat_id_state(frm);
				}
			},
		});
	}
}
