frappe.ui.form.on("Annual Filing Settings", {
	setup(frm) {
		frm.set_query("closing_account", (doc) => ({
			filters: {
				company: doc.company,
				is_group: 0,
				disabled: 0,
				root_type: ["in", ["Liability", "Equity"]],
			},
		}));
	},

	refresh(frm) {
		if (frm.has_perm("write")) {
			frm.add_custom_button(__("Take Address"), () => take_address(frm, false));
		}
	},

	company(frm) {
		// The proposal shows before the first save, so that the user checks the split house number.
		const address = ["street", "house_number", "postal_code", "city"];
		if (frm.is_new() && frm.doc.company && address.every((field) => !frm.doc[field])) {
			take_address(frm, true);
		}
	},
});

function take_address(frm, quiet) {
	frm.call("fill_address", { quiet }).then(() => frm.dirty());
}
