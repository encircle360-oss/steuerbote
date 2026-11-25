// The status Steuerbote sets, not the docstatus of Frappe: a draft may be Berechnet or Bereit, and a filed document
// Abgegeben or Ersetzt. The status reads the same in every language.
frappe.listview_settings["VAT Return"] = {
	add_fields: ["status"],
	has_indicator_for_draft: true,

	get_indicator(doc) {
		if (doc.docstatus === 2) {
			return [__("Cancelled"), "red", "docstatus,=,2"];
		}
		const colours = { Entwurf: "gray", Berechnet: "orange", Bereit: "blue", Abgegeben: "green", Ersetzt: "darkgrey" };
		return [doc.status, colours[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
