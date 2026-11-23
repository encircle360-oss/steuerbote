{% include "steuerbote/public/js/elster_transmission.js" %}
{% include "steuerbote/public/js/annual_filing.js" %}

// The Gewerbesteuererklärung on the pieces every annual document shares (annual_filing.js), with the texts that name
// the return. It builds on the Körperschaftsteuererklärung of its company and year, which the field offers alone.
frappe.ui.form.on("Trade Tax Return", {
	setup(frm) {
		annual_filing_setup(frm);
		frm.set_query("corporate_income_tax_return", () => ({
			filters: { company: frm.doc.company, year: frm.doc.year, docstatus: ["!=", 2] },
		}));
	},

	refresh(frm) {
		annual_filing_refresh(frm, trade_tax_return_texts());
	},
});

function trade_tax_return_texts() {
	return {
		unsaved: __("Save the return before transmitting it."),
		send: __("The Gewerbesteuererklärung goes to the Finanzamt and is filed with it."),
		test_send: __(
			"The Gewerbesteuererklärung goes to the ELSTER server as a test case with the Testmerker and is deleted there on receipt. It stays a draft."
		),
		sent: __(
			"ELSTER accepted this return, but it could not be submitted afterwards. Do not send it again; submit it with Buchen once the cause is resolved."
		),
		running: __("A transmission of this return is running. The return reloads when it has finished."),
		simulation: (link) =>
			__(
				"Simulation mode: Prüfen and Testsenden only simulate, nothing reaches the Finanzamt. Senden needs an installed ERiC runtime with the plugin of the year and a Hersteller-ID, see {0}. Mein ELSTER imports no Gewerbesteuererklärung: type it in there from the print format Gewerbesteuererklärung, then note its filing with Filed in Mein ELSTER.",
				[link]
			),
		berichtigung: __(
			"A Berichtigung is a new and complete Gewerbesteuererklärung for the same company and year, on the Körperschaftsteuererklärung of the year that is filed latest. It is calculated at once."
		),
		ready: __(
			"Ready to file: transmit the return through ELSTER, or type it into Mein ELSTER from the print format, as Mein ELSTER takes no file of it, and note the filing with Filed in Mein ELSTER."
		),
		filed_outside_example: __(
			"For example: on 15 May 2027 by the Steuerberatung, with the Freizeichnungsdokument in the files."
		),
	};
}
