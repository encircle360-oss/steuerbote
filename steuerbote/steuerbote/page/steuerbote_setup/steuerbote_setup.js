// Steuerbote einrichten: Einrichten sets up the company chosen, and the table says what each step did. Before that,
// choosing a company shows what the setup would make and what the company has. The server side is
// steuerbote/steuerbote/setup.py; ?company= in the address chooses the company.

const SETUP_METHOD = "steuerbote.steuerbote.setup.set_up";
const STATUS_METHOD = "steuerbote.steuerbote.setup.setup_status";
// The block Über Steuerbote, the same as at the bottom of the workspace Steuern.
const ABOUT_METHOD = "steuerbote.steuerbote.about_block.render";
const OUTCOMES = {
	created: { label: __("Made"), indicator: "green" },
	skipped: { label: __("Skipped"), indicator: "gray" },
	undecided: { label: __("Open"), indicator: "orange" },
	failed: { label: __("Failed"), indicator: "red" },
	blocked: { label: __("Not Run"), indicator: "red" },
};
// The same outcomes before the setup runs: what a step would make is missing.
const STATUS_OUTCOMES = {
	created: { label: __("Missing"), indicator: "orange" },
	skipped: { label: __("Present"), indicator: "green" },
	undecided: { label: __("Open"), indicator: "orange" },
	failed: { label: __("Failed"), indicator: "red" },
	blocked: { label: __("Not Run"), indicator: "gray" },
};

frappe.pages["steuerbote-setup"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Set Up Steuerbote"),
		single_column: true,
	});
	const company = page.add_field({
		fieldname: "company",
		label: __("Company"),
		fieldtype: "Link",
		options: "Company",
		reqd: 1,
		change: () => show_status(company.get_value(), report),
	});
	const report = $('<div class="steuerbote-setup-report"></div>');
	const about = $('<div class="steuerbote-about-block" style="margin-top: var(--margin-xl, 2rem);"></div>');
	$(page.main).append(
		$('<p class="text-muted steuerbote-setup-intro"></p>').text(
			__(
				"Makes what a company needs for the Umsatzsteuer-Voranmeldung and leaves what it has: the VAT Return Settings, the VAT Return Mapping with the defaults of SKR03 or SKR04 and, where § 18 Absatz 2 UStG decides it, the first Voranmeldungszeitraum. A second run changes nothing."
			)
		),
		report,
		about
	);
	frappe.call({ method: ABOUT_METHOD }).then((response) => about.html(response.message));
	page.set_primary_action(__("Set Up"), () => set_up(company.get_value(), report));
	wrapper.steuerbote_setup = { company };
};

frappe.pages["steuerbote-setup"].on_page_show = function (wrapper) {
	const chosen = frappe.route_options && frappe.route_options.company;
	if (chosen && wrapper.steuerbote_setup) {
		frappe.route_options = null;
		wrapper.steuerbote_setup.company.set_value(chosen);
	}
};

function set_up(company, report) {
	if (!company) {
		frappe.msgprint(__("Choose the company to set up."));
		return;
	}
	frappe
		.call({ method: SETUP_METHOD, args: { company }, freeze: true, freeze_message: __("Setting up …") })
		.then((response) => show_report(report, response.message));
}

function show_status(company, report) {
	if (!company) {
		report.empty();
		return;
	}
	frappe
		.call({ method: STATUS_METHOD, args: { company } })
		.then((response) => show_report(report, response.message));
}

// An action a step offers, such as relabelling a field of ERPNext: it runs only on the click of the user, and the
// setup runs again afterwards to show what changed.
function run_action(company, method, report) {
	frappe
		.call({ method, args: { company }, freeze: true, freeze_message: __("Setting up …") })
		.then(() => set_up(company, report));
}

function show_report(report, result) {
	const escape = frappe.utils.escape_html;
	const rows = result.steps.map((step) => {
		const outcome = (result.before ? STATUS_OUTCOMES : OUTCOMES)[step.outcome];
		const notes = step.notes.map(
			(note) =>
				`<li class="${note.open ? "steuerbote-setup-open" : ""}">${
					note.open ? `<b>${__("Open")}:</b> ` : ""
				}${escape(note.text)}</li>`
		);
		// Before the setup, an action would run the setup, and what a step would make does not exist yet.
		const action = step.action && !result.before
			? `<button class="btn btn-xs btn-default steuerbote-setup-action" data-method="${escape(
					step.action.method
			  )}">${escape(step.action.label)}</button>`
			: "";
		const document = step.doctype && !(result.before && step.outcome === "created")
			? `<a href="${escape(frappe.utils.get_form_link(step.doctype, step.name))}">${escape(
					step.document_label
			  )}</a>`
			: "";
		return `<tr data-step="${escape(step.key)}">
			<td>${escape(step.label)}</td>
			<td><span class="indicator-pill ${outcome.indicator}">${escape(outcome.label)}</span></td>
			<td><ul class="list-unstyled">${notes.join("")}</ul>${action}</td>
			<td>${document}</td>
		</tr>`;
	});
	const company = escape(result.company);
	const open = result.steps.some(
		(step) => !["created", "skipped"].includes(step.outcome) || step.notes.some((note) => note.open)
	);
	let summary = result.changed
		? __("Steuerbote is set up for {0}.", [company])
		: __("Nothing changed: {0} was set up already.", [company]);
	if (result.before) {
		summary = result.changed
			? __("Before the setup: Set Up makes what is missing for {0}.", [company])
			: __("{0} has everything the setup makes.", [company]);
	}
	if (open) {
		summary += " " + __("The open points below are still to do.");
	}
	report.html(`
		<p class="steuerbote-setup-summary">${summary}</p>
		<table class="table table-bordered">
			<thead><tr><th>${__("Step")}</th><th>${__("Step Outcome")}</th><th>${__("Step Notes")}</th><th>${__(
				"Document"
			)}</th></tr></thead>
			<tbody>${rows.join("")}</tbody>
		</table>
	`);
	report.find(".steuerbote-setup-action").on("click", (event) =>
		run_action(result.company, $(event.currentTarget).attr("data-method"), report)
	);
}
