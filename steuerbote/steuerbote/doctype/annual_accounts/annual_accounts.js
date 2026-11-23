{% include "steuerbote/public/js/annual_filing.js" %}

// The Jahresabschluss on the pieces every annual document shares (annual_filing.js), with the steps after Berechnen:
// the Vorschau der Offenlegung and the XBRL for the Unternehmensregister of a calculated or festgestellter
// Jahresabschluss, and after the Feststellung, which Buchen is, Ergebnisverwendung buchen, Übermittlung festhalten and
// Einstellung festhalten. The Jahresabschluss goes to no authority through Steuerbote: a person uploads its file.
frappe.ui.form.on("Annual Accounts", {
	setup(frm) {
		annual_filing_setup(frm);
	},

	refresh(frm) {
		annual_filing_refresh(frm, annual_accounts_texts());
		annual_accounts_buttons(frm);
	},
});

const ANNUAL_ACCOUNTS_CHANNELS = ["XBRL-Upload", "Webformular", "Steuerberatung"];

function annual_accounts_buttons(frm) {
	const state = (frm.doc.__onload && frm.doc.__onload.annual_filing) || {};
	const calculated = [...(state.calculated || []), ...(state.filings || [])].includes(frm.doc.status);
	if (frm.is_new() || frm.doc.docstatus === 2 || !calculated) {
		return;
	}
	const group = __("Offenlegung");
	frm.add_custom_button(__("Preview of the Offenlegung"), () => annual_accounts_preview(frm), group);
	frm.add_custom_button(__("XBRL for the Unternehmensregister"), () => annual_accounts_xbrl(frm), group);
	if (frm.doc.docstatus !== 1) {
		return;
	}
	if (frm.doc.status === "Festgestellt") {
		frm.add_custom_button(__("Record Übermittlung"), () => annual_accounts_transmission(frm), group);
	}
	if (frm.doc.status === "Übermittelt") {
		frm.add_custom_button(__("Record Einstellung"), () => annual_accounts_publication(frm), group);
	}
	if (frm.doc.appropriation_reserve || frm.doc.appropriation_dividend) {
		frm.add_custom_button(__("Post Ergebnisverwendung"), () => annual_accounts_appropriation(frm));
	}
}

// A step reads the Jahresabschluss as saved.
function annual_accounts_saved(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the Jahresabschluss first."));
		return false;
	}
	return true;
}

function annual_accounts_link(url) {
	const name = url.split("/").pop();
	return `<a href="${encodeURI(url)}" target="_blank" rel="noopener">${frappe.utils.escape_html(name)}</a>`;
}

function annual_accounts_preview(frm) {
	if (!annual_accounts_saved(frm)) {
		return;
	}
	frm.call("make_disclosure_preview").then((r) => {
		frm.reload_doc();
		frappe.msgprint(__("The Preview of the Offenlegung is attached: {0}", [annual_accounts_link(r.message)]));
	});
}

function annual_accounts_xbrl(frm) {
	if (!annual_accounts_saved(frm)) {
		return;
	}
	frm.call("make_xbrl").then((r) => {
		const result = r.message || {};
		frm.reload_doc();
		if (result.file_url) {
			frappe.msgprint(
				__(
					"The XBRL file is attached: {0}. Before the first real upload, try it on the Testplattform of the Bundesanzeiger Verlag.",
					[annual_accounts_link(result.file_url)]
				)
			);
			return;
		}
		const held = (result.held_back || []).map((text) => `<li>${frappe.utils.escape_html(text)}</li>`);
		frappe.msgprint({
			title: __("XBRL for the Unternehmensregister"),
			indicator: "red",
			message: `${__("These findings hold the file back; the table Findings lists them.")}<ul>${held.join("")}</ul>`,
		});
	});
}

function annual_accounts_transmission(frm) {
	const deposits = frm.doc.size_class === "Kleinst" && frm.doc.disclosure_mode === "Hinterlegung";
	const upload = { doctype: frm.doctype, docname: frm.doc.name };
	frappe.prompt(
		[
			{
				fieldtype: "Date",
				fieldname: "transmitted_on",
				label: __("Transmitted On"),
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{
				fieldtype: "Data",
				fieldname: "transmitted_by",
				label: __("Transmitted By"),
				description: __("The person who identified herself and uploaded the file."),
				reqd: 1,
			},
			{
				fieldtype: "Data",
				fieldname: "order_number",
				label: __("Order Number"),
				description: __("As Meine Daten, Aufträge & Abrufe shows it."),
				reqd: 1,
			},
			{
				fieldtype: "Select",
				fieldname: "channel",
				label: __("Channel"),
				options: ANNUAL_ACCOUNTS_CHANNELS.join("\n"),
				default: ANNUAL_ACCOUNTS_CHANNELS[0],
			},
			{
				fieldtype: "Check",
				fieldname: "kleinst_notice",
				label: __("Hinterlegung Box Ticked"),
				description: __(
					"The box of the order that the company meets the conditions of a Kleinstkapitalgesellschaft; without it the order is no Hinterlegung."
				),
				hidden: deposits ? 0 : 1,
			},
			{
				fieldtype: "Attach",
				fieldname: "confirmation_file",
				label: __("Order Confirmation"),
				options: upload,
			},
			{ fieldtype: "Currency", fieldname: "fees", label: __("Fees") },
		],
		(values) => frm.call("record_transmission", values).then(() => frm.reload_doc()),
		__("Record Übermittlung"),
		__("Record")
	);
}

function annual_accounts_publication(frm) {
	frappe.prompt(
		[
			{
				fieldtype: "Date",
				fieldname: "published_on",
				label: __("Published On"),
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{
				fieldtype: "Attach",
				fieldname: "receipt_file",
				label: __("Receipt"),
				options: { doctype: frm.doctype, docname: frm.doc.name },
			},
			{ fieldtype: "Currency", fieldname: "fees", label: __("Fees"), default: frm.doc.fees },
		],
		(values) => frm.call("record_publication", values).then(() => frm.reload_doc()),
		__("Record Einstellung"),
		__("Record")
	);
}

function annual_accounts_appropriation(frm) {
	frappe.confirm(
		__(
			"Steuerbote makes a draft Journal Entry of the Ergebnisverwendung on the day of the Feststellung. Check it and submit it yourself."
		),
		() =>
			frm.call("make_appropriation_entry").then((r) => {
				if (r.message) {
					frappe.set_route("Form", "Journal Entry", r.message);
				}
			})
	);
}

function annual_accounts_texts() {
	return {
		ready: __(
			"Ready for the Feststellung: once the shareholders have adopted the Jahresabschluss on the day entered, Buchen records the Feststellung."
		),
	};
}
