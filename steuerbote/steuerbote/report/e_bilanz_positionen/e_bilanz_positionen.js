// The positions of an E-Bilanz as a tree, each opening to the accounts behind it, with the hint on the Umsatzerlöse
// against the Voranmeldungen of the year (rows.py).
frappe.query_reports["E-Bilanz Positionen"] = {
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
		{
			fieldname: "statement_type",
			label: __("Kind of Balance Sheet"),
			fieldtype: "Select",
			options: [
				{ value: "Jahresabschluss", label: __("Jahresabschluss") },
				{ value: "Eröffnungsbilanz", label: __("Eröffnungsbilanz") },
			],
			default: "Jahresabschluss",
			reqd: 1,
		},
	],
	tree: true,
	name_field: "key",
	parent_field: "parent_key",
	initial_depth: 1,
	formatter(value, row, column, data, default_formatter) {
		// Frappe writes a Data cell into the page as HTML; the labels come from the taxonomy and the books.
		const text = column.fieldtype === "Data";
		value = default_formatter(text ? frappe.utils.escape_html(value) : value, row, column, data);
		return data && data.bold ? `<strong>${value}</strong>` : value;
	},
};
