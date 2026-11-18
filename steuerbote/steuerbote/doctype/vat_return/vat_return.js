frappe.ui.form.on("VAT Return", {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("Calculate"), () => frm.call("calculate").then(() => frm.reload_doc()));
		}
		if (can_make_import_file(frm.doc)) {
			frm.add_custom_button(__("XML for Mein ELSTER"), () => make_import_file(frm));
		}
	},
});

// The conditions of make_import_file in vat_return.py: a return that could be filed, or the return filed.
function can_make_import_file(doc) {
	if (doc.docstatus === 1) {
		return doc.status === "Abgegeben";
	}
	const explained = doc.ready || (doc.remarks || "").trim();
	return doc.docstatus === 0 && ["Berechnet", "Bereit"].includes(doc.status) && Boolean(explained);
}

function make_import_file(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the return before making the file for Mein ELSTER."));
		return;
	}
	frm.call("make_import_file").then((response) => {
		frm.reload_doc();
		window.open(response.message);
	});
}
