// Ertragsteuer-Kontennachweis: the ledger entries behind each line of the Körperschaftsteuer- and the
// Gewerbesteuererklärung of the company and year, as a tree of lines, accounts and vouchers.
frappe.query_reports["Ertragsteuer-Kontennachweis"] = {
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
			default: new Date().getFullYear() - 1,
			reqd: 1,
		},
	],
	tree: true,
	name_field: "node",
	parent_field: "parent_node",
	initial_depth: 0,
	formatter(value, row, column, data, default_formatter) {
		// Frappe writes a Data cell into the page as HTML; the labels and field codes are text.
		value = default_formatter(column.fieldtype === "Data" ? frappe.utils.escape_html(value) : value, row, column, data);
		return data && data.bold ? `<strong>${value}</strong>` : value;
	},
};
