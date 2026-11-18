frappe.listview_settings["ELSTER Transmission"] = {
	add_fields: ["status", "simulated"],

	get_indicator(doc) {
		const colours = { Erfolgreich: "green", Fehlgeschlagen: "red", Unbekannt: "orange", Läuft: "yellow" };
		return [__(doc.status), colours[doc.status] || "gray", `status,=,${doc.status}`];
	},

	formatters: {
		simulated(value) {
			return value ? `<span class="indicator-pill gray">${__("Simulated")}</span>` : "";
		},
	},
};
