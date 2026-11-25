{% include "steuerbote/public/js/timeline_values.js" %}

frappe.ui.form.on("VAT Return Settings", {
	timeline_refresh(frm) {
		translate_select_values_in_timeline(frm);
	},

	period_basis(frm) {
		warn_of_filed_periods(frm);
	},

	late_documents(frm) {
		warn_of_filed_periods(frm);
	},
});

// Both rules decide where every booking goes, the bookings of filed periods as well (vat_periods.py): a change shows
// in the filed returns as changed after the filing.
function warn_of_filed_periods(frm) {
	const filed = (frm.doc.__onload || {}).filed_periods || [];
	if (!filed.length) {
		return;
	}
	frappe.msgprint({
		title: __("Filed Periods"),
		indicator: "orange",
		message: __(
			"This rule decides where the bookings of the filed periods go as well: {0}. Where their amounts change, the filed returns show it as changed after the filing and need a corrected return. Change the rule only at the turn of the year and with the Steuerberatung.",
			[filed.map(frappe.utils.escape_html).join(", ")]
		),
	});
}
