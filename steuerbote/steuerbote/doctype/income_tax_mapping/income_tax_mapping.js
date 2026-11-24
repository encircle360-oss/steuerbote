{% include "steuerbote/public/js/mapping_differences.js" %}

frappe.ui.form.on("Income Tax Mapping", {
	setup(frm) {
		for (const table of ["rules", "watched"]) {
			frm.set_query("account", table, (doc) => ({
				filters: { company: doc.company, is_group: 0 },
			}));
		}
	},

	refresh(frm) {
		show_defaults_to_load(frm);
		frm.add_custom_button(__("Load Defaults"), () => {
			const has_rows = ["rules", "watched"].some((table) => (frm.doc[table] || []).length);
			if (has_rows) {
				frappe.confirm(
					__("Replace the account rules and watched accounts with the defaults of the chart?"),
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
			frm.add_custom_button(__("Export Mapping"), () => export_mapping(frm), __("Mapping File"));
			frm.add_custom_button(__("Import Mapping"), () => import_mapping(frm), __("Mapping File"));
		}
	},
});

// A trading class belongs to a trading account only; the core refuses it on any other category.
frappe.ui.form.on("Income Tax Mapping Rule", {
	category(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.category !== TRADING_CATEGORY && row.trading_class) {
			frappe.model.set_value(cdt, cdn, "trading_class", "");
		}
	},
});

const OWN_CHART = "Eigener Kontenrahmen";
const TRADING_CATEGORY = "trading_unclassified";

function load_defaults(frm) {
	frm.call("load_defaults").then((r) => {
		frm.dirty();
		show_defaults_to_load(frm);
		const missing = r.message || [];
		if (missing.length) {
			show_missing_accounts(missing);
		} else {
			frappe.show_alert({ message: __("Defaults Loaded"), indicator: "green" });
		}
	});
}

// The DATEV accounts of the defaults the company lacks, with their labels, so that the user can create those it books.
function show_missing_accounts(missing) {
	const escape = frappe.utils.escape_html;
	const rows = missing.map(
		(account) => `<tr><td>${escape(account.account_number)}</td><td>${escape(account.label)}</td></tr>`
	);
	frappe.msgprint({
		title: __("Defaults Loaded"),
		indicator: "blue",
		wide: true,
		message: `
			<p>${escape(
				__(
					"{0} accounts of the defaults do not exist in this company and were left out. Create those the company books on and load the defaults again.",
					[missing.length]
				)
			)}</p>
			<table class="table table-bordered steuerbote-missing-accounts">
				<thead><tr><th>${escape(__("Account Number"))}</th><th>${escape(__("DATEV Label"))}</th></tr></thead>
				<tbody>${rows.join("")}</tbody>
			</table>`,
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
			apply_label: take_over_label(comparison.version),
			apply: (chosen, dialog) => take_over_defaults(frm, chosen, dialog),
		});
	});
}

function take_over_defaults(frm, chosen, dialog) {
	frm.call("update_from_defaults", { chosen, acknowledge: 1 }).then((response) => {
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
