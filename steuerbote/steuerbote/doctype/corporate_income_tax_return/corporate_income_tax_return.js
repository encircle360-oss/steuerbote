{% include "steuerbote/public/js/elster_transmission.js" %}
{% include "steuerbote/public/js/annual_filing.js" %}

// The Körperschaftsteuererklärung on the pieces every annual document shares (annual_filing.js), with the texts that
// name the return, and Propose Provisions, which makes the draft Journal Entry of the provisions for the taxes on
// income. Mein ELSTER imports no Körperschaftsteuererklärung, so the notes of the simulation and of a ready return say
// that it is typed in there from the print format. The E-Bilanz of Anlage GK line 11 is one of the Jahresabschluss of
// the company and year, which the field offers alone.
frappe.ui.form.on("Corporate Income Tax Return", {
	setup(frm) {
		annual_filing_setup(frm);
		frm.set_query("electronic_balance_sheet", () => ({
			filters: {
				company: frm.doc.company,
				year: frm.doc.year,
				statement_type: "Jahresabschluss",
				docstatus: ["!=", 2],
			},
		}));
	},

	refresh(frm) {
		annual_filing_refresh(frm, corporate_income_tax_return_texts());
		income_tax_provisions_button(frm);
	},
});

// A calculated or filed return proposes the provisions of its year; the Journal Entry stays a draft for the company to
// check and submit.
function income_tax_provisions_button(frm) {
	const state = (frm.doc.__onload && frm.doc.__onload.annual_filing) || {};
	const calculated = [...(state.calculated || []), ...(state.filings || [])].includes(frm.doc.status);
	if (frm.is_new() || frm.doc.docstatus === 2 || !calculated) {
		return;
	}
	frm.add_custom_button(__("Propose Provisions"), () =>
		frm.call("propose_provisions").then((r) => {
			if (r.message) {
				frappe.set_route("Form", "Journal Entry", r.message);
			}
		})
	);
}

function corporate_income_tax_return_texts() {
	return {
		unsaved: __("Save the return before transmitting it."),
		send: __("The Körperschaftsteuererklärung goes to the Finanzamt and is filed with it."),
		test_send: __(
			"The Körperschaftsteuererklärung goes to the ELSTER server as a test case with the Testmerker and is deleted there on receipt. It stays a draft."
		),
		sent: __(
			"ELSTER accepted this return, but it could not be submitted afterwards. Do not send it again; submit it with Buchen once the cause is resolved."
		),
		running: __("A transmission of this return is running. The return reloads when it has finished."),
		simulation: (link) =>
			__(
				"Simulation mode: Prüfen and Testsenden only simulate, nothing reaches the Finanzamt. Senden needs an installed ERiC runtime with the plugin of the year and a Hersteller-ID, see {0}. Mein ELSTER imports no Körperschaftsteuererklärung: type it in there from the print format Körperschaftsteuererklärung, then note its filing with Filed in Mein ELSTER.",
				[link]
			),
		berichtigung: __(
			"A Berichtigung is a new and complete Körperschaftsteuererklärung for the same company and year. It starts with the corrections, lines by hand, statements and tables of this return and is calculated at once."
		),
		ready: __(
			"Ready to file: transmit the return through ELSTER, or type it into Mein ELSTER from the print format, as Mein ELSTER takes no file of it, and note the filing with Filed in Mein ELSTER."
		),
		filed_outside_example: __(
			"For example: on 15 May 2027 by the Steuerberatung, with the Freizeichnungsdokument in the files."
		),
	};
}
