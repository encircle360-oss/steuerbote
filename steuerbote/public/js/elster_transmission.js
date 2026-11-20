// Prüfen, Testsenden and Senden through ERiC, the same for every form that goes to ELSTER this way: the VAT Return
// and the Dauerfristverlängerung include this file. Each form passes the texts that name its document:
// unsaved, send, test_send, sent and running. The server side is elster_transmission/transmission.py.

const TRANSMISSION_EVENT = "steuerbote_elster_transmission";
const STASH_CERTIFICATE = "steuerbote.steuerbote.doctype.elster_transmission.transmission.stash_certificate";

function listen_for_transmissions(frm) {
	frappe.realtime.on(TRANSMISSION_EVENT, (data) => {
		if (data.document_type === frm.doctype) {
			on_transmission_finished(frm, data);
		}
	});
}

function elster_state(frm) {
	return (frm.doc.__onload && frm.doc.__onload.elster) || {};
}

function eric_simulates(frm) {
	const elster = frm.doc.__onload && frm.doc.__onload.elster;
	return !elster || elster.simulation;
}

function transmission_blocked(frm) {
	return frm.doc.transmission_in_progress || elster_state(frm).sent;
}

// A run whose background job is gone keeps its lock until the form closes it.
function release_stale_transmission(frm) {
	if (elster_state(frm).stale && frm.perm[0] && frm.perm[0].write) {
		frm.call("release_stale_transmission").then(() => frm.reload_doc());
	}
}

// Buchen alone files nothing, so a draft gets no Submit button; only a document ELSTER accepted while its
// submission failed is submitted with it.
function offer_buchen_only_for_an_accepted_send(frm) {
	if (frm.doc.docstatus === 0 && !frm.is_new() && !elster_state(frm).sent) {
		frm.page.clear_primary_action();
	}
}

function elster_notes(frm, texts) {
	const notes = [];
	if (!frm.is_new() && frm.doc.docstatus === 0) {
		if (elster_state(frm).sent) {
			notes.push(texts.sent);
		}
		if (frm.doc.transmission_in_progress) {
			notes.push(texts.running);
		}
		if (eric_simulates(frm)) {
			const link = `<a href="/app/${frappe.router.slug("ERiC Settings")}">${__("ERiC Settings")}</a>`;
			notes.push(
				__(
					"Simulation mode: Prüfen and Testsenden only simulate, nothing reaches the Finanzamt. Senden needs an installed ERiC runtime and a Hersteller-ID, see {0}.",
					[link]
				)
			);
		}
	}
	return notes;
}

function add_transmission_buttons(frm, group, texts) {
	if (eric_simulates(frm)) {
		frm.add_custom_button(__("Validate with ERiC (Simulation)"), () => start(frm, "validate", texts), group);
		const label = __("Test Transmission (Simulation)");
		frm.add_custom_button(label, () => ask_for_certificate(frm, "test_send", label, texts), group);
	} else {
		frm.add_custom_button(__("Validate with ERiC"), () => start(frm, "validate", texts), group);
		const test_label = __("Test Transmission");
		frm.add_custom_button(test_label, () => ask_for_certificate(frm, "test_send", test_label, texts), group);
		const send_label = __("Transmit to the Finanzamt");
		frm.add_custom_button(send_label, () => ask_for_certificate(frm, "send", send_label, texts), group);
	}
}

function saved(frm, texts) {
	if (frm.is_dirty()) {
		frappe.msgprint(texts.unsaved);
		return false;
	}
	return true;
}

function start(frm, operation, texts, token) {
	if (!saved(frm, texts)) {
		return;
	}
	frm.call("transmit", token ? { operation, token } : { operation }).then(() => {
		frappe.show_alert({
			message: __("The transmission runs in the background. A notice follows when it has finished."),
			indicator: "blue",
		});
		frm.reload_doc();
	});
}

function ask_for_certificate(frm, operation, title, texts) {
	if (!saved(frm, texts)) {
		return;
	}
	if (eric_simulates(frm)) {
		frappe.confirm(
			__(
				"The simulation needs no certificate and no password: Testsenden runs against the simulation, nothing reaches the Finanzamt."
			),
			() => start(frm, operation, texts)
		);
		return;
	}
	const notice = operation === "send" ? texts.send : texts.test_send;
	const dialog = new frappe.ui.Dialog({
		title,
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "notice",
				options: `<p>${notice}</p><p class="text-muted">${__(
					"Certificate and password serve this transmission only. Steuerbote does not keep them."
				)}</p>`,
			},
			{
				fieldtype: "HTML",
				fieldname: "certificate_file",
				options: `<div class="form-group"><label class="control-label reqd">${__(
					"Certificate File (.pfx)"
				)}</label><input type="file" class="form-control" accept=".pfx,.p12"></div>`,
			},
			{
				fieldtype: "Password",
				fieldname: "certificate_password",
				label: __("Certificate Password"),
				reqd: 1,
			},
		],
		primary_action_label: title,
		primary_action(values) {
			const input = dialog.fields_dict.certificate_file.$wrapper.find("input[type=file]").get(0);
			const file = input.files[0];
			if (!file) {
				frappe.msgprint(__("Choose the certificate file."));
				return;
			}
			const certificate_password = values.certificate_password;
			input.value = "";
			dialog.fields_dict.certificate_password.$input.val("");
			dialog.hide();
			frappe.dom
				.file_to_base64(file)
				.then((data_url) =>
					frappe.call({
						method: STASH_CERTIFICATE,
						args: { certificate_secret: data_url.split(",")[1] || "", certificate_password },
						freeze: true,
					})
				)
				.then((r) => start(frm, operation, texts, r.message));
		},
	});
	// The password control of Frappe rates every keystroke on the server; a certificate password stays here.
	dialog.fields_dict.certificate_password.disable_password_checks();
	dialog.show();
}

function on_transmission_finished(frm, data) {
	const procedure = data.simulated ? __("{0} (Simulation)", [__(data.operation)]) : __(data.operation);
	const link = frappe.utils.get_form_link("ELSTER Transmission", data.transmission, true);
	const notices = {
		Erfolgreich: [__("{0} for {1} succeeded, see {2}.", [procedure, data.document, link]), "green"],
		Unbekannt: [
			__(
				"Whether {0} for {1} reached ELSTER is unknown, see {2}. Check in Mein ELSTER before sending again.",
				[procedure, data.document, link]
			),
			"orange",
		],
	};
	const [message, indicator] = notices[data.status] || [
		__("{0} for {1} failed, see {2}.", [procedure, data.document, link]),
		"red",
	];
	frappe.show_alert({ message, indicator }, 15);
	if (frm.doc && frm.doc.name === data.document) {
		frm.reload_doc();
	}
}
