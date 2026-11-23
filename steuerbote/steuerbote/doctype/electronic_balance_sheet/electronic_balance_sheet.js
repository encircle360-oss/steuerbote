{% include "steuerbote/public/js/elster_transmission.js" %}
{% include "steuerbote/public/js/annual_filing.js" %}

// The E-Bilanz on the pieces every annual document shares (annual_filing.js), with the texts that name it. Mein ELSTER
// takes no E-Bilanz, so without the Hersteller-ID it goes as the XBRL file to the Steuerberatung and its filing is
// noted with Mark as Filed Outside. A new E-Bilanz takes the Bilanzierungsstandard of the Annual Filing Settings.
frappe.ui.form.on("Electronic Balance Sheet", {
	setup(frm) {
		annual_filing_setup(frm);
	},

	refresh(frm) {
		annual_filing_refresh(frm, electronic_balance_sheet_texts());
		const state = (frm.doc.__onload && frm.doc.__onload.electronic_balance_sheet) || {};
		if (state.export && !frm.is_new()) {
			frm.add_custom_button(__("Export XBRL"), () => electronic_balance_sheet_export(frm));
		}
	},

	company(frm) {
		if (!frm.is_new() || !frm.doc.company) {
			return;
		}
		frappe.db
			.get_value("Annual Filing Settings", frm.doc.company, "accounting_standard")
			.then((r) => {
				const standard = r.message && r.message.accounting_standard;
				if (standard) {
					frm.set_value("accounting_standard", standard);
				}
			});
	},
});

function electronic_balance_sheet_export(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the E-Bilanz before exporting it."));
		return;
	}
	frm.call("export_xbrl").then((r) => {
		if (r.message) {
			window.open(r.message);
		}
	});
}

function electronic_balance_sheet_texts() {
	return {
		unsaved: __("Save the E-Bilanz before transmitting it."),
		send: __("The E-Bilanz goes to the Finanzamt and is filed with it."),
		test_send: __(
			"The E-Bilanz goes to the ELSTER server as a test case with the Testmerker and is deleted there on receipt. It stays a draft."
		),
		sent: __(
			"ELSTER accepted this E-Bilanz, but it could not be submitted afterwards. Do not send it again; submit it with Buchen once the cause is resolved."
		),
		running: __("A transmission of this E-Bilanz is running. The E-Bilanz reloads when it has finished."),
		simulation: (link) =>
			__(
				"Simulation mode: Prüfen and Testsenden only simulate, nothing reaches the Finanzamt. Senden needs an installed ERiC runtime and a Hersteller-ID, see {0}. Mein ELSTER takes no E-Bilanz: give the Steuerberatung the file of Export XBRL, then note its filing with Mark as Filed Outside.",
				[link]
			),
		berichtigung: __(
			"A Berichtigung is a new and complete E-Bilanz for the same company, year and Bilanzart, which names its Status des Berichts. It starts with the corrections, lines by hand and entries by hand of this E-Bilanz and is calculated at once."
		),
		ready: __(
			"Ready to file: transmit the E-Bilanz through ELSTER, or give the Steuerberatung the file of Export XBRL, as Mein ELSTER takes no E-Bilanz, and note the filing with Mark as Filed Outside."
		),
		filed_outside_example: __(
			"For example: on 15 May 2027 by the Steuerberatung, with the Übertragungsprotokoll in the files."
		),
	};
}
