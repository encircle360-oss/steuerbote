// Prüfen, Testsenden and Senden through ERiC, the same for every form that goes to ELSTER this way: the VAT Return,
// the Dauerfristverlängerung and the Zusammenfassende Meldung include this file, and so do the annual documents
// before annual_filing.js. Each form passes the texts that name its document: unsaved, send, test_send, sent and
// running, and a document that goes to another recipient than the Finanzamt its send_label, simulation and
// simulated_test_send. The server side is elster_transmission/transmission.py.

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

// After a Senden that ELSTER accepted or whose outcome is unknown, the Finanzamt or the BZSt has the draft, or may
// have it, as it was sent: the server refuses every change but the remarks (refuse_if_sent in transmission.py).
function locked_as_sent(frm) {
	return Boolean(elster_state(frm).locked);
}

// Frappe offers Discard in the menu of every draft (add_discard in its toolbar.js), which the server refuses for a
// draft locked as sent; the toolbar has built the menu by the time the form refreshes.
function remove_discard_when_locked_as_sent(frm) {
	if (locked_as_sent(frm)) {
		frm.page.menu.find(`[data-label="${encodeURIComponent(__("Discard"))}"]`).closest("li").remove();
	}
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
		if (locked_as_sent(frm)) {
			notes.push(locked_as_sent_note(frm));
		}
		if (frm.doc.transmission_in_progress) {
			notes.push(texts.running);
		}
		if (eric_simulates(frm)) {
			const link = `<a href="/app/${frappe.router.slug("ERiC Settings")}">${__("ERiC Settings")}</a>`;
			notes.push(
				texts.simulation
					? texts.simulation(link)
					: __(
							"Simulation mode: Prüfen and Testsenden only simulate, nothing reaches the Finanzamt. Senden needs an installed ERiC runtime and a Hersteller-ID, see {0}.",
							[link]
					  )
			);
		}
	}
	return notes;
}

// What is left of a draft locked as sent, after an unknown outcome in the words of refuse_if_sent in transmission.py.
function locked_as_sent_note(frm) {
	const { transmission, status, transferticket } = elster_state(frm).locked;
	if (status === "Unbekannt") {
		return __(
			"Whether {0} reached ELSTER is unknown, so {1} stays as it was sent. Check in Mein ELSTER whether it arrived: if it did, note its filing; if not, a System Manager deletes {0}, then it can change again. Only its remarks can change meanwhile.",
			[
				frappe.utils.get_form_link("ELSTER Transmission", transmission, true),
				frappe.utils.escape_html(frm.doc.name),
			]
		);
	}
	return __(
		"Transmitted with Transferticket {0}: only Buchen or a correction is left; the remarks can still change.",
		[frappe.utils.escape_html(transferticket)]
	);
}

// A check with hints and no errors succeeds, so the form names the errors and hints of the latest finished run,
// which latest_run in transmission.py reads; its ELSTER Transmission holds them all.
function show_latest_run(frm) {
	if (frm.$run_note) {
		frm.$run_note.remove();
		frm.$run_note = null;
	}
	const run = frm.doc.__onload && frm.doc.__onload.elster_run;
	if (!run || !(run.errors || run.hints)) {
		return;
	}
	const procedure = run.simulated ? __("{0} (Simulation)", [__(run.operation)]) : __(run.operation);
	const link = frappe.utils.get_form_link("ELSTER Transmission", run.name, true);
	const lines = [
		__("Latest run {0}, {1}, {2}: errors {3}, hints {4}.", [
			link,
			procedure,
			frappe.utils.escape_html(run.status),
			run.errors,
			run.hints,
		]),
		...run.first_errors.map((message) => message_line(__("error"), message)),
		...run.first_hints.map((message) => message_line(__("hint"), message)),
	];
	frm.$run_note = frm.dashboard.set_headline_alert(lines.join("<br>"), run.errors ? "red" : "blue");
}

function message_line(kind, message) {
	const code = message.code ? `${frappe.utils.escape_html(message.code)}: ` : "";
	return `${kind} ${code}${frappe.utils.escape_html(message.text)}`;
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
		const send_label = texts.send_label || __("Transmit to the Finanzamt");
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
			texts.simulated_test_send ||
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
				options: `<p>${notice}</p>${printout_note(frm)}<p class="text-muted">${__(
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
				.then((data_url) => stash_certificate(frm, data_url.split(",")[1] || "", certificate_password))
				.then((r) => start(frm, operation, texts, r.message));
		},
	});
	// The password control of Frappe rates every keystroke on the server; a certificate password stays here.
	dialog.fields_dict.certificate_password.disable_password_checks();
	dialog.show();
}

// What ERiC prints after the send, the Übertragungsprotokoll or the Freizeichnungsdokument of an Erklärung, which
// printout in transmission.py names.
function printout_note(frm) {
	const printout = elster_state(frm).printout;
	if (!printout) {
		return "";
	}
	return `<p>${__("After the transmission, ERiC prints the {0}, which the ELSTER Transmission keeps.", [
		frappe.utils.escape_html(printout),
	])}</p>`;
}

// The server keeps both for this user and this document only. Both go under names with "password": the report of a
// server error copies the arguments of its request, and Frappe masks those, and only those, there.
function stash_certificate(frm, password_protected_certificate, certificate_password) {
	return frappe.call({
		method: STASH_CERTIFICATE,
		args: {
			document_type: frm.doctype,
			document: frm.doc.name,
			password_protected_certificate,
			certificate_password,
		},
		freeze: true,
		always: forget_the_last_request,
	});
}

// Frappe keeps the arguments of the latest request in frappe.last_request for the console.
function forget_the_last_request() {
	if (frappe.last_request && "password_protected_certificate" in frappe.last_request) {
		frappe.last_request = null;
	}
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
