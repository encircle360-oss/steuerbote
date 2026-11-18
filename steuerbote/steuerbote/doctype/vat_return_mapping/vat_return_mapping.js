frappe.ui.form.on("VAT Return Mapping", {
	setup(frm) {
		for (const table of ["rules", "watched"]) {
			frm.set_query("account", table, (doc) => ({
				filters: { company: doc.company, is_group: 0 },
			}));
		}
		// A Float field stores no blank, so a rule without a rate holds 0, which mapping_sync reads as no rate.
		frappe.meta.set_formatter("VAT Return Mapping Rule", "tax_rate", null, (value, df, options, doc) =>
			flt(value) ? frappe.form.formatters.Float(value, df, options, doc) : ""
		);
	},

	refresh(frm) {
		frm.add_custom_button(__("Load Defaults"), () => {
			const has_rows = ["rules", "checks", "watched"].some((table) => (frm.doc[table] || []).length);
			if (has_rows) {
				frappe.confirm(
					__("Replace the account rules, tax checks and watched accounts with the defaults of the chart?"),
					() => load_defaults(frm)
				);
			} else {
				load_defaults(frm);
			}
		});
	},
});

function load_defaults(frm) {
	frm.call("load_defaults").then((r) => {
		frm.dirty();
		const missing = r.message || [];
		if (missing.length) {
			frappe.msgprint({
				title: __("Defaults Loaded"),
				indicator: "blue",
				message: __("{0} accounts of the defaults do not exist in this company and were left out: {1}", [
					missing.length,
					missing.join(", "),
				]),
			});
		} else {
			frappe.show_alert({ message: __("Defaults Loaded"), indicator: "green" });
		}
	});
}
