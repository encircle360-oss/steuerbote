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
