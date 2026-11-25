// The status Steuerbote sets, not the docstatus of Frappe: a draft may be Berechnet, and a Jahresabschluss goes on to
// Festgestellt, Übermittelt and Eingestellt. The form header takes the same indicator. The status reads the same in
// every language.
frappe.listview_settings["Annual Accounts"] = {
	add_fields: ["status"],
	has_indicator_for_draft: true,

	get_indicator(doc) {
		if (doc.docstatus === 2) {
			return [__("Cancelled"), "red", "docstatus,=,2"];
		}
		const colours = {
			Entwurf: "gray",
			Berechnet: "orange",
			Festgestellt: "blue",
			Übermittelt: "green",
			Eingestellt: "green",
			Ersetzt: "darkgrey",
		};
		return [doc.status, colours[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
