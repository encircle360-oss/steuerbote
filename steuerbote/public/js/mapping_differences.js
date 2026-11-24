// The differences between a mapping and its defaults or a file, each with a box to take it over: Vorgaben
// aktualisieren and Zuordnung importieren of the VAT Return Mapping, the Income Tax Mapping and the Balance Sheet
// Mapping include this file, which also names the defaults a mapping waits for above its fields. The server gives
// every difference in the words of the user (presented in the controller of each mapping); the dialog only escapes
// them, and apply gets the ids of the differences checked. subject_label heads the column of what a difference
// concerns, for a mapping without tax checks. apply_label is the label of the button, or a function that words it for
// the number of differences checked, which the dialog asks again whenever a box changes.

function show_mapping_differences({ title, intro, differences, unchanged, subject_label, proposed_label, show_origin, apply_label, apply }) {
	const escape = frappe.utils.escape_html;
	const label_for = (checked) => (typeof apply_label === "function" ? apply_label(checked) : apply_label);
	const dialog = new frappe.ui.Dialog({
		title,
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "differences" }],
		primary_action_label: label_for(differences.filter((difference) => difference.proposes).length),
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
	const boxes = dialog.$wrapper.find("input.steuerbote-difference");
	const relabel = () => dialog.set_primary_action(label_for(boxes.filter(":checked").length));
	boxes.on("change", relabel);
	dialog.$wrapper.find("input.steuerbote-all-differences").on("change", (event) => {
		boxes.prop("checked", event.target.checked);
		relabel();
	});
	dialog.show();
	return dialog;
}

// The button of Vorgaben aktualisieren says what a click does: take over the differences checked, or with none checked
// note the defaults of today as seen, after which every difference left counts as the user's own.
function take_over_label(version) {
	return (checked) => {
		if (!checked) {
			return __("Take Over None and Note the Defaults {0} as Seen", [version]);
		}
		return checked === 1 ? __("Take Over 1 Difference") : __("Take Over {0} Differences", [checked]);
	};
}

// A mapping without rows that has not taken over the defaults of today, as one made while they were empty, waits for
// them; the server names their version (onload of the controller) until the mapping has taken them over.
function show_defaults_to_load(frm) {
	const version = frm.doc.__onload && frm.doc.__onload.defaults_to_load;
	frm.set_intro(
		version && frm.doc.defaults_version !== version
			? frappe.utils.escape_html(
					__("This mapping has no rows. Load Defaults fetches the defaults {0}.", [version])
			  )
			: "",
		"orange"
	);
}
