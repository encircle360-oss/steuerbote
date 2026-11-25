// USt-IdNrn. prüfen, the same for every form whose USt-IdNrn. Steuerbote confirms at the BZSt: the form includes this
// file after elster_transmission.js, whose saved() it uses, and passes the question of its dialog and its texts for
// saved(). The server side is vat_id_confirmation/confirming.py.

const CONFIRMATION_EVENT = "steuerbote_vat_id_confirmation";

function listen_for_confirmations(frm) {
	frappe.realtime.on(CONFIRMATION_EVENT, (data) => {
		if (data.document_type === frm.doctype) {
			on_confirmation_finished(frm, data);
		}
	});
}

// A confirmation whose background job is gone keeps its lock until the form releases it.
function release_stale_confirmation(frm) {
	const confirmation = (frm.doc.__onload && frm.doc.__onload.confirmation) || {};
	if (confirmation.stale && frm.perm[0] && frm.perm[0].write) {
		frm.call("release_stale_confirmation").then(() => frm.reload_doc());
	}
}

// The confirmation asks the BZSt or VIES at once, whether or not ERiC runs as a simulation: the simulation stands in
// for ELSTER alone, and a confirmation is only proof when the service answered it.
function confirm_vat_ids(frm, question, texts) {
	if (!saved(frm, texts)) {
		return;
	}
	const live = __(
		"The query goes to the BZSt or VIES at once, also while ERiC runs as a simulation: the simulation stands in for ELSTER only."
	);
	frappe.confirm(`${question}<br><br>${live}`, () =>
		frm.call("confirm_vat_ids").then((response) => {
			frappe.show_alert(
				{
					message: __(
						"The confirmation of {0} USt-IdNrn. runs in the background. A notice follows when it has finished.",
						[response.message]
					),
					indicator: "blue",
				},
				10
			);
			frm.reload_doc();
		})
	);
}

function on_confirmation_finished(frm, data) {
	const link = frappe.utils.get_form_link(data.document_type, data.document, true);
	let message = __("The confirmation of the USt-IdNrn. of {0} has finished: {1} numbers asked.", [link, data.confirmed]);
	let indicator = "green";
	if (data.error) {
		message = __("The confirmation of the USt-IdNrn. of {0} stopped: {1}", [link, data.error]);
		indicator = "red";
	} else if ((data.failed || []).length) {
		message = __("The confirmation of {0} failed for {1}; the Error Log has the details.", [
			link,
			data.failed.join(", "),
		]);
		indicator = "orange";
	}
	frappe.show_alert({ message, indicator }, 15);
	if (frm.doc && frm.doc.name === data.document) {
		frm.reload_doc();
	}
}
