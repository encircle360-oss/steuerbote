// The status Steuerbote sets, which says more than whether the document is a draft: calculated, ready or filed.
frappe.listview_settings["VAT Return"] = {
	add_fields: ["status"],

	get_indicator(doc) {
		const colours = { Entwurf: "gray", Berechnet: "orange", Bereit: "blue", Abgegeben: "green", Ersetzt: "darkgrey" };
		return [__(doc.status), colours[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
