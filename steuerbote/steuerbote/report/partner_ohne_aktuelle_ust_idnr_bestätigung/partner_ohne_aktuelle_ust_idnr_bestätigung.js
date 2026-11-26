frappe.query_reports["Partner ohne aktuelle USt-IdNr-Bestätigung"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Select",
			options: ["", "Customer", "Supplier"],
		},
		{
			// Finds a partner by a part of its name or of its ID, since ERPNext names partners by number as well.
			fieldname: "party",
			label: __("Partner"),
			fieldtype: "Data",
		},
	],
};
