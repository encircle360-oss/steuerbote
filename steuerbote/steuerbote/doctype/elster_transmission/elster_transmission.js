// A check with hints and no errors succeeds, so the form counts the errors and the hints of its messages.
frappe.ui.form.on("ELSTER Transmission", {
	refresh(frm) {
		const messages = frm.doc.messages || [];
		const errors = messages.filter((row) => row.severity === "error").length;
		const hints = messages.filter((row) => row.severity === "hint").length;
		frm.set_intro(
			errors || hints ? __("Errors {0}, hints {1}: see the messages below.", [errors, hints]) : "",
			errors ? "red" : "blue"
		);
	},
});
