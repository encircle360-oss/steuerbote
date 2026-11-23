{% include "steuerbote/public/js/mapping_differences.js" %}

frappe.ui.form.on("VAT Return Mapping", {
	setup(frm) {
		for (const table of ["rules", "watched"]) {
			frm.set_query("account", table, (doc) => ({
				filters: { company: doc.company, is_group: 0 },
			}));
		}
		// A Float field stores no blank, so a rule without a rate holds 0, which mapping_sync reads as no rate. The
		// grid formats a cell whose text is empty once more with the document of the form, which has no rate and
		// shows 0, so the cell gets an empty element instead.
		frappe.meta.set_formatter("VAT Return Mapping Rule", "tax_rate", null, (value, df, options, doc) =>
			flt(value) ? frappe.form.formatters.Float(value, df, options, doc) : "<span></span>"
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
		if (!frm.is_new()) {
			if (frm.doc.chart !== OWN_CHART) {
				frm.add_custom_button(__("Update Defaults"), () => update_defaults(frm));
			}
			frm.add_custom_button(__("Check Tax Templates"), () => check_tax_templates(frm));
			frm.add_custom_button(__("Export Mapping"), () => export_mapping(frm), __("Mapping File"));
			frm.add_custom_button(__("Import Mapping"), () => import_mapping(frm), __("Mapping File"));
		}
	},
});

const OWN_CHART = "Eigener Kontenrahmen";

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

// Vorgaben aktualisieren: the differences to the defaults of today, those the defaults made checked, the user's own not.
function update_defaults(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the mapping before updating it from the defaults."));
		return;
	}
	frm.call("compare_with_defaults").then((response) => {
		const comparison = response.message;
		if (!comparison.differences.length) {
			if (comparison.taken_over === comparison.version) {
				frappe.msgprint({
					title: __("Update Defaults"),
					indicator: "green",
					message: __("The mapping holds the defaults {0}.", [comparison.version]),
				});
			} else {
				frappe.confirm(
					__("The mapping holds the defaults {0}, row by row. Note them as taken over?", [comparison.version]),
					() => take_over_defaults(frm, [])
				);
			}
			return;
		}
		show_mapping_differences({
			title: __("Update Defaults"),
			intro: comparison.base_known
				? __(
						"These rows differ from the defaults {0}. Checked are the changes of the defaults since {1}, in rows the mapping kept as the defaults gave them; unchecked are your own changes, which taking over would undo. What stays unchecked, stays as it is.",
						[comparison.version, comparison.taken_over]
				  )
				: __(
						"These rows differ from the defaults {0}. The mapping does not know the defaults it was made from, so each difference counts as your own and none is checked. What stays unchecked, stays as it is.",
						[comparison.version]
				  ),
			differences: comparison.differences,
			unchanged: comparison.unchanged,
			proposed_label: __("Defaults {0}", [comparison.version]),
			show_origin: true,
			apply_label: __("Take Over the Checked"),
			apply: (chosen, dialog) => take_over_defaults(frm, chosen, dialog),
		});
	});
}

function take_over_defaults(frm, chosen, dialog) {
	frm.call("update_from_defaults", { chosen }).then((response) => {
		if (dialog) {
			dialog.hide();
		}
		frm.reload_doc();
		frappe.show_alert({
			message: __("Differences taken over: {0}.", [response.message]),
			indicator: "green",
		});
	});
}

// Zuordnung exportieren: the server attaches the file privately and hands its text back, which the browser saves.
function export_mapping(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the mapping before exporting it."));
		return;
	}
	frm.call("export_mapping").then((response) => {
		const file = response.message;
		const link = document.createElement("a");
		link.href = URL.createObjectURL(new Blob([file.content], { type: "application/json" }));
		link.download = file.file_name;
		document.body.appendChild(link);
		link.click();
		link.remove();
		setTimeout(() => URL.revokeObjectURL(link.href), 1000);
		frm.reload_doc();
	});
}

// Zuordnung importieren: a file uploaded privately to the mapping, or its content pasted; the server checks it, and
// the dialog of the differences shows what it would change, every difference checked.
function import_mapping(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the mapping before importing a file into it."));
		return;
	}
	const dialog = new frappe.ui.Dialog({
		title: __("Import Mapping"),
		fields: [
			{ fieldtype: "HTML", fieldname: "intro" },
			{
				fieldtype: "Button",
				fieldname: "upload",
				label: __("Upload the File"),
				click: () => upload_mapping_file(frm, dialog),
			},
			{ fieldtype: "Data", fieldname: "file_url", label: __("Uploaded File"), read_only: 1 },
			{ fieldtype: "Long Text", fieldname: "content", label: __("Or Paste Its Content") },
		],
		primary_action_label: __("Show Differences"),
		primary_action(values) {
			compare_with_file(frm, { file_url: values.file_url, content: values.content }, dialog);
		},
	});
	dialog.fields_dict.intro.$wrapper.html(
		`<p>${frappe.utils.escape_html(
			__(
				"A file of Zuordnung exportieren, of this chart. Steuerbote checks its checksum, its chart and that the company has each of its accounts, then shows what it would change."
			)
		)}</p>`
	);
	dialog.show();
}

function upload_mapping_file(frm, dialog) {
	new frappe.ui.FileUploader({
		doctype: frm.doctype,
		docname: frm.doc.name,
		folder: "Home/Attachments",
		restrictions: { allowed_file_types: [".json"] },
		allow_multiple: false,
		allow_toggle_private: false,
		allow_web_link: false,
		allow_take_photo: false,
		allow_google_drive: false,
		disable_file_browser: true,
		on_success(file) {
			dialog.set_value("file_url", file.file_url);
		},
	});
}

function compare_with_file(frm, source, import_dialog) {
	if (!source.file_url && !(source.content || "").trim()) {
		frappe.msgprint(__("Upload the file or paste its content."));
		return;
	}
	frm.call("compare_with_file", source).then((response) => {
		const comparison = response.message;
		if (!comparison.differences.length) {
			frappe.msgprint({
				title: __("Import Mapping"),
				indicator: "green",
				message: __("The file holds this mapping, row by row."),
			});
			return;
		}
		import_dialog.hide();
		show_mapping_differences({
			title: __("Import Mapping"),
			intro: __(
				"The file of {0}, exported on {1} with the defaults {2}, would change these rows. Each difference is checked; what stays unchecked, stays as it is. Importing notes the defaults of the file as taken over.",
				[comparison.company, comparison.exported_on, comparison.defaults_version || "–"]
			),
			differences: comparison.differences,
			unchanged: comparison.unchanged,
			proposed_label: __("In the File"),
			show_origin: false,
			apply_label: __("Import the Checked"),
			apply: (chosen, dialog) =>
				frm.call("import_file", { ...source, chosen }).then((answer) => {
					dialog.hide();
					frm.reload_doc();
					frappe.show_alert({
						message: __("Differences imported: {0}.", [answer.message]),
						indicator: "green",
					});
				}),
		});
	});
}

// Steuervorlagen prüfen: the accounts of the tax templates without a place in the mapping, which one step watches at
// the level Sperrt.
function check_tax_templates(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the mapping before checking the tax templates."));
		return;
	}
	frm.call("check_tax_templates").then((r) => {
		const accounts = r.message || [];
		if (!accounts.length) {
			frappe.msgprint({
				title: __("Check Tax Templates"),
				indicator: "green",
				message: __("Every account of the tax templates has a place in the mapping."),
			});
			return;
		}
		show_template_accounts(frm, accounts);
	});
}

function show_template_accounts(frm, accounts) {
	const watchable = accounts.filter((account) => account.account_number);
	const dialog = new frappe.ui.Dialog({
		title: __("Check Tax Templates"),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "accounts" }],
		primary_action_label: __("Watch at the Level Blocking"),
		primary_action() {
			frm.call("watch_template_accounts").then((response) => {
				dialog.hide();
				frm.reload_doc();
				frappe.show_alert({
					message: __("{0} accounts are watched at the level Blocking now.", [(response.message || []).length]),
					indicator: "green",
				});
			});
		},
	});
	const escape = frappe.utils.escape_html;
	const rows = accounts.map(
		(account) => `<tr>
			<td>${escape(account.account_number || __("without account number"))}</td>
			<td>${escape(account.account_name)}</td>
			<td>${account.templates.map(escape).join("<br>")}</td>
		</tr>`
	);
	dialog.fields_dict.accounts.$wrapper.html(`
		<p>${__(
			"These accounts of the tax templates have no place in the mapping: no rule, no Verprobung and not watched. What the templates book on them goes into no Kennzahl."
		)}</p>
		<table class="table table-bordered">
			<thead><tr><th>${__("Account Number")}</th><th>${__("Account")}</th><th>${__("Tax Templates")}</th></tr></thead>
			<tbody>${rows.join("")}</tbody>
		</table>
		<p class="text-muted">${__(
			"Watching them at the level Blocking holds every return with a balance on one of them until the account has a rule. An account without account number cannot be watched; give it a number first."
		)}</p>
	`);
	if (!watchable.length) {
		dialog.get_primary_btn().hide();
	}
	dialog.show();
}
