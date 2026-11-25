// A record Steuerbote keeps as proof: nobody changes it, the Administrator, who holds every permission, included.
frappe.ui.form.on("VAT ID Confirmation", {
	onload(frm) {
		frm.set_read_only();
	},
	refresh(frm) {
		frm.disable_save();
	},
});
