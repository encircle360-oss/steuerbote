frappe.query_reports["UStVA Kennzahlen"] = {
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
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: new Date().getFullYear(),
			reqd: 1,
		},
		{
			fieldname: "rhythm",
			label: __("Rhythm"),
			fieldtype: "Select",
			options: [
				{ value: "monthly", label: __("monthly") },
				{ value: "quarterly", label: __("quarterly") },
			],
			default: "monthly",
			reqd: 1,
		},
		{
			fieldname: "period_index",
			label: __("Period Number"),
			fieldtype: "Int",
			default: new Date().getMonth() + 1,
			reqd: 1,
		},
		{
			fieldname: "only_deviations",
			label: __("Only Deviations"),
			fieldtype: "Check",
			default: 0,
		},
	],
	tree: true,
	name_field: "kennzahl",
	parent_field: "parent_kennzahl",
	initial_depth: 0,
	formatter(value, row, column, data, default_formatter) {
		// Frappe writes a Data cell into the page as HTML; only the link to the print view is meant as such.
		const text = column.fieldtype === "Data" && column.fieldname !== "print_link";
		value = default_formatter(text ? frappe.utils.escape_html(value) : value, row, column, data);
		return data && data.bold ? `<strong>${value}</strong>` : value;
	},
};
