// The timeline of a form shows the values a version stored; Frappe writes a select field as its stored option, which
// in Steuerbote is English, such as "By Service Date". The forms that include this file show the old and the new value
// of each select field translated, as the field itself shows them.

function translate_select_values_in_timeline(frm) {
	const versions = (frm.get_docinfo() || {}).versions || [];
	let translated = false;
	for (const version of versions) {
		if (version.steuerbote_translated) {
			continue;
		}
		version.steuerbote_translated = true;
		let data;
		try {
			data = JSON.parse(version.data);
		} catch (error) {
			continue;
		}
		for (const change of data.changed || []) {
			const df = frappe.meta.get_docfield(frm.doctype, change[0], frm.docname);
			if (df && df.fieldtype === "Select") {
				change[1] = change[1] ? __(change[1]) : change[1];
				change[2] = change[2] ? __(change[2]) : change[2];
				translated = true;
			}
		}
		version.data = JSON.stringify(data);
	}
	if (translated && frm.timeline) {
		frm.timeline.render_timeline_items();
	}
}
