// A check with hints and no errors succeeds, so the form counts the errors and the hints of its messages. The record is
// kept as proof: nobody changes it, the Administrator, who holds every permission, included.
frappe.ui.form.on("ELSTER Transmission", {
	onload(frm) {
		frm.set_read_only();
	},
	refresh(frm) {
		frm.disable_save();
		const messages = frm.doc.messages || [];
		const errors = messages.filter((row) => row.severity === "error").length;
		const hints = messages.filter((row) => row.severity === "hint").length;
		frm.set_intro(
			errors || hints ? __("Errors {0}, hints {1}: see the messages below.", [errors, hints]) : "",
			errors ? "red" : "blue"
		);
	},
});
