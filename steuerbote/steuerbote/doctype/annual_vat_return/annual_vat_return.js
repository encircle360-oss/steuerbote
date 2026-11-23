{% include "steuerbote/public/js/elster_transmission.js" %}
{% include "steuerbote/public/js/annual_filing.js" %}

// The Umsatzsteuererklärung on the pieces every annual document shares (annual_filing.js), with the texts that name
// the return. Mein ELSTER imports no Umsatzsteuererklärung, so the notes of the simulation and of a ready return say
// that it is typed in there from the print format.
frappe.ui.form.on("Annual VAT Return", {
	setup(frm) {
		annual_filing_setup(frm);
	},

	refresh(frm) {
		annual_filing_refresh(frm, annual_vat_return_texts());
	},
});

function annual_vat_return_texts() {
	return {
		unsaved: __("Save the return before transmitting it."),
		send: __("The Umsatzsteuererklärung goes to the Finanzamt and is filed with it."),
		test_send: __(
			"The Umsatzsteuererklärung goes to the ELSTER server as a test case with the Testmerker and is deleted there on receipt. It stays a draft."
		),
		sent: __(
			"ELSTER accepted this return, but it could not be submitted afterwards. Do not send it again; submit it with Buchen once the cause is resolved."
		),
		running: __("A transmission of this return is running. The return reloads when it has finished."),
		simulation: (link) =>
			__(
				"Simulation mode: Prüfen and Testsenden only simulate, nothing reaches the Finanzamt. Senden needs an installed ERiC runtime and a Hersteller-ID, see {0}. Mein ELSTER imports no Umsatzsteuererklärung: type it in there from the print format Umsatzsteuererklärung, then note its filing with Filed in Mein ELSTER.",
				[link]
			),
		berichtigung: __(
			"A Berichtigung is a new and complete Umsatzsteuererklärung for the same company and year with Kz 110, whose Vorauszahlungssoll is the Kz 816 of this return. It starts with the corrections, lines by hand and statements of this return and is calculated at once."
		),
		ready: __(
			"Ready to file: transmit the return through ELSTER, or type it into Mein ELSTER from the print format, as Mein ELSTER takes no file of it, and note the filing with Filed in Mein ELSTER."
		),
		filed_outside_example: __(
			"For example: on 15 May 2027 by the Steuerberatung, with the Freizeichnungsdokument in the files."
		),
	};
}
