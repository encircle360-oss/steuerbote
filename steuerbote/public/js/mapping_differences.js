// The differences between a mapping and its defaults or a file, each with a box to take it over: Vorgaben
// aktualisieren and Zuordnung importieren of the VAT Return Mapping, the Income Tax Mapping and the Balance Sheet
// Mapping include this file. The server gives every difference in the words of the user (presented in the controller
// of each mapping); the dialog only escapes them, and apply gets the ids of the differences checked. subject_label
// heads the column of what a difference concerns, for a mapping without tax checks.

function show_mapping_differences({ title, intro, differences, unchanged, subject_label, proposed_label, show_origin, apply_label, apply }) {
	const escape = frappe.utils.escape_html;
	const dialog = new frappe.ui.Dialog({
		title,
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "differences" }],
		primary_action_label: apply_label,
		primary_action() {
			const chosen = dialog.$wrapper
				.find("input.steuerbote-difference:checked")
				.map((index, box) => box.value)
				.get();
			apply(chosen, dialog);
		},
	});
	const rows = differences.map(
		(difference) => `<tr>
			<td><input type="checkbox" class="steuerbote-difference" value="${escape(difference.id)}"${
				difference.proposes ? " checked" : ""
			}></td>
			<td>${escape(difference.subject)}</td>
			<td>${escape(difference.change)}${
				difference.fields ? `<br><span class="text-muted">${escape(difference.fields)}</span>` : ""
			}</td>
			<td>${escape(difference.current)}</td>
			<td>${escape(difference.proposed)}</td>
			${show_origin ? `<td>${escape(difference.origin)}</td>` : ""}
		</tr>`
	);
	dialog.fields_dict.differences.$wrapper.html(`
		<p>${escape(intro)}</p>
		<table class="table table-bordered steuerbote-differences">
			<thead><tr>
				<th><input type="checkbox" class="steuerbote-all-differences" title="${escape(__("Choose All"))}"></th>
				<th>${escape(subject_label || __("Account or Tax Check"))}</th>
				<th>${escape(__("What Changes"))}</th>
				<th>${escape(__("In the Mapping"))}</th>
				<th>${escape(proposed_label)}</th>
				${show_origin ? `<th>${escape(__("Comes From"))}</th>` : ""}
			</tr></thead>
			<tbody>${rows.join("")}</tbody>
		</table>
		<p class="text-muted">${escape(__("Rows the same on both sides: {0}.", [unchanged]))}</p>
	`);
	dialog.$wrapper.find("input.steuerbote-all-differences").on("change", (event) => {
		dialog.$wrapper.find("input.steuerbote-difference").prop("checked", event.target.checked);
	});
	dialog.show();
	return dialog;
}
