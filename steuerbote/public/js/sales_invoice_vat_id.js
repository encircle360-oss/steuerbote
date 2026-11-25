// A draft Sales Invoice confirms the USt-IdNr. of its customer at the BZSt in the background, so that the check on
// submit (steuerbote/steuerbote/partner_vat_ids.py, check_invoice) finds a current confirmation.

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		const number = (frm.doc.tax_id || "").replace(/[^A-Za-z0-9+*]/g, "").toUpperCase();
		const foreign = /^[A-Z]{2}/.test(number) && !number.startsWith("DE");
		if (frm.is_new() || frm.doc.docstatus !== 0 || !frm.doc.customer || !foreign) {
			return;
		}
		frm.add_custom_button(__("Confirm VAT ID of the Customer"), () => {
			const question = __(
				"Steuerbote asks the BZSt in the background with the own USt-IdNr. of the company about the USt-IdNr. {0} and, where they are known, the name, street, postal code and town of the customer. Only when the BZSt cannot answer does the same go to VIES of the European Commission. Every answer is kept as a USt-IdNr.-Bestätigung that names this invoice.",
				[frappe.utils.escape_html(number)]
			);
			frappe.confirm(question, () =>
				frappe
					.call({
						method: "steuerbote.steuerbote.partner_vat_ids.confirm_invoice_customer",
						args: { sales_invoice: frm.doc.name },
					})
					.then(() =>
						frappe.show_alert(
							{
								message: __("The confirmation runs in the background. Submit once it has finished."),
								indicator: "blue",
							},
							10
						)
					)
			);
		});
	},
});
