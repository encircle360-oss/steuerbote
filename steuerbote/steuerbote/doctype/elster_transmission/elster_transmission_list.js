frappe.listview_settings["ELSTER Transmission"] = {
	get_indicator(doc) {
		if (doc.simulated) {
			return [__("Simulated"), "blue", "simulated,=,1"];
		}
		const colours = { Erfolgreich: "green", Fehlgeschlagen: "red", Läuft: "orange" };
		return [__(doc.status), colours[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
