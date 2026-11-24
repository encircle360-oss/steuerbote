{% include "steuerbote/public/js/mapping_differences.js" %}

frappe.ui.form.on("Balance Sheet Mapping", {
	setup(frm) {
		for (const table of ["rules", "watched", "excluded"]) {
			frm.set_query("account", table, (doc) => ({
				filters: { company: doc.company, is_group: 0 },
			}));
		}
	},

	refresh(frm) {
		show_defaults_to_load(frm);
		frm.add_custom_button(__("Load Defaults"), () => {
			const has_rows = ["rules", "watched", "excluded"].some((table) => (frm.doc[table] || []).length);
			if (has_rows) {
				frappe.confirm(
					__(
						"Replace the account rules, watched accounts and accounts outside the Bilanz and the GuV with the defaults of the chart?"
					),
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
			frm.add_custom_button(__("Check Accounts"), () => check_accounts(frm));
			frm.add_custom_button(__("Export Mapping"), () => export_mapping(frm), __("Mapping File"));
			frm.add_custom_button(__("Import Mapping"), () => import_mapping(frm), __("Mapping File"));
			const versions = frm.get_docfield("taxonomy_version").options.split("\n");
			const latest = versions[versions.length - 1];
			if (frm.doc.taxonomy_version !== latest) {
				frm.add_custom_button(__("Lift to New Taxonomy"), () => lift_taxonomy(frm, latest));
			}
			if (frm.doc.previous_rows) {
				frm.add_custom_button(
					__("Export Mapping before the Lift"),
					() => export_previous_mapping(frm),
					__("Mapping File")
				);
			}
		}
	},
});

const OWN_CHART = "Eigener Kontenrahmen";

function load_defaults(frm) {
	frm.call("load_defaults").then((r) => {
		frm.dirty();
		show_defaults_to_load(frm);
		const without_place = r.message || [];
		if (without_place.length) {
			frappe.msgprint({
				title: __("Defaults Loaded"),
				indicator: "blue",
				message: __("{0} accounts of the company have no place in the defaults: {1}", [
					without_place.length,
					without_place.join(", "),
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
			subject_label: __("Account"),
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
				"A file of Zuordnung exportieren of a Balance Sheet Mapping of this chart and this taxonomy. Steuerbote checks its checksum, its chart, its taxonomy and that the company has each of its accounts, then shows what it would change."
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
			intro:
				__(
					"The file of {0}, exported on {1} with the defaults {2}, would change these rows. Each difference is checked; what stays unchecked, stays as it is. Importing notes the defaults of the file as taken over.",
					[comparison.company, comparison.exported_on, comparison.defaults_version || "–"]
				) +
				(comparison.lifted_from
					? " " +
					  __("The file names the positions of the HGB-Taxonomie {0}; Steuerbote has lifted its rows to {1}.", [
							comparison.lifted_from,
							frm.doc.taxonomy_version,
					  ])
					: ""),
			differences: comparison.differences,
			unchanged: comparison.unchanged,
			subject_label: __("Account"),
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

// Konten prüfen: the ledger accounts of the company without a place in the mapping, which one step watches at the
// level Sperrt.
function check_accounts(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the mapping before checking its accounts."));
		return;
	}
	frm.call("accounts_without_place").then((r) => {
		const accounts = r.message || [];
		if (!accounts.length) {
			frappe.msgprint({
				title: __("Check Accounts"),
				indicator: "green",
				message: __("Every account of the company has a place in the Balance Sheet Mapping."),
			});
			return;
		}
		show_accounts_without_place(frm, accounts);
	});
}

function show_accounts_without_place(frm, accounts) {
	const watchable = accounts.filter((account) => account.account_number);
	const dialog = new frappe.ui.Dialog({
		title: __("Check Accounts"),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "accounts" }],
		primary_action_label: __("Watch at the Level Blocking"),
		primary_action() {
			frm.call("watch_accounts_without_place").then((response) => {
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
			<td>${escape(__(account.root_type))}</td>
		</tr>`
	);
	dialog.fields_dict.accounts.$wrapper.html(`
		<p>${escape(
			__(
				"These accounts of the company have no place in the Balance Sheet Mapping: no position, not watched and not outside the Bilanz and the GuV. A balance on one of them holds the E-Bilanz and the Jahresabschluss back."
			)
		)}</p>
		<table class="table table-bordered">
			<thead><tr><th>${escape(__("Account Number"))}</th><th>${escape(__("Account"))}</th><th>${escape(
				__("Root Type")
			)}</th></tr></thead>
			<tbody>${rows.join("")}</tbody>
		</table>
		<p class="text-muted">${escape(
			__(
				"Watching them at the level Blocking keeps them in sight until each has a position. An account without account number can have no place; give it a number first."
			)
		)}</p>
	`);
	if (!watchable.length) {
		dialog.get_primary_btn().hide();
	}
	dialog.show();
}

// Auf neue Taxonomie heben: the rows on the positions of the latest version, a rule the lift cannot carry watched at
// the level Blocking; the rows before stay with the mapping as a file of their version.
function lift_taxonomy(frm, latest) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the mapping before lifting it to a new taxonomy."));
		return;
	}
	frappe.confirm(
		__(
			"Lift the mapping from the positions of the HGB-Taxonomie {0} to those of {1}? The rows of {0} stay available as a file.",
			[frm.doc.taxonomy_version, latest]
		),
		() =>
			frm.call("lift_taxonomy", { target: latest }).then((response) => {
				frm.reload_doc();
				show_lifted(response.message);
			})
	);
}

function show_lifted(lifted) {
	const escape = frappe.utils.escape_html;
	const parts = [
		`<p>${escape(__("The mapping names the positions of the HGB-Taxonomie {0} now.", [lifted.version]))}</p>`,
	];
	if (lifted.renamed.length) {
		const items = lifted.renamed.map(
			(renamed) => `<li>${escape(renamed.account)}: ${escape(renamed.old)} → ${escape(renamed.new)}</li>`
		);
		parts.push(`<p>${escape(__("Renamed positions:"))}</p><ul>${items.join("")}</ul>`);
	}
	if (lifted.to_decide.length) {
		const items = lifted.to_decide.map(
			(decision) =>
				`<li>${escape(decision.account)}, ${escape(decision.position)}: ${escape(decision.text)}</li>`
		);
		parts.push(
			`<p>${escape(
				__("Rows to decide, watched at the level Blocking until each has a position again:")
			)}</p><ul>${items.join("")}</ul>`
		);
	}
	if (lifted.mussfelder.length) {
		const items = lifted.mussfelder.map(
			(mussfeld) => `<li>${escape(mussfeld.label)} (${escape(mussfeld.position)})</li>`
		);
		parts.push(
			`<p>${escape(
				__(
					"New Mussfelder of {0}, on which accounts of the books may belong; Update Defaults shows what the defaults of {0} map otherwise:",
					[lifted.version]
				)
			)}</p><ul>${items.join("")}</ul>`
		);
	}
	frappe.msgprint({
		title: __("Lift to New Taxonomy"),
		indicator: lifted.to_decide.length ? "orange" : "green",
		message: parts.join(""),
	});
}

// The rows before Auf neue Taxonomie heben, as the file of Zuordnung exportieren of their version.
function export_previous_mapping(frm) {
	frm.call("export_previous_mapping").then((response) => {
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
