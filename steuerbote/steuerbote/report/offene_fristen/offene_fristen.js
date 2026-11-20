frappe.query_reports["Offene Fristen"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "horizon",
			label: __("Days Ahead"),
			fieldtype: "Int",
			default: 60,
			reqd: 1,
		},
	],
};
