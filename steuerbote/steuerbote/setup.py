"""Steuerbote einrichten: the setup of a company in one step, from the page steuerbote-setup.

set_up() runs the setup steps of steuerbote.setup.steps for a company: the three steps of this module, which make
the VAT Return Settings, the VAT Return Mapping and the first Voranmeldungszeitraum, and every step that a module
or app names in the hook steuerbote_setup_steps of its hooks.py:

	steuerbote_setup_steps = [
		{
			"key": "balance_sheet_mapping",
			"label": "Balance Sheet Mapping",
			"order": 50,
			"needs": ["vat_return_settings"],
			"run": "steuerbote.steuerbote.doctype.balance_sheet_mapping.setup.run",
		},
	]

The function a step names takes the SetupContext of the run and returns a StepResult. A step makes only what is
missing and skips what exists, so a second run changes nothing; a step that needs another runs only once that one
created or found its document. A mapping that exists without rows and waits for the defaults of today
(waits_for_defaults of its controller) lacks them: its step loads them into it as into a new one. Each step runs in a
savepoint of its own: a step that fails is rolled back and reported, and the others go on. Only a System Manager or an
Accounts Manager sets up a company, and every document is made with their permissions.

A rollback to a savepoint undoes the database alone (frappe.db.savepoint). What Frappe queues on the transaction while a
step saves, the background jobs, realtime messages, webhooks and clearings of the cache that wait for its commit or
rollback, stays queued and would run with the commit of the request; so a step that is rolled back takes that back
with it (Pending), and the status of the page runs inert (inert). A step acts through the documents it saves alone: it
enqueues no job, publishes no message and writes no cache entry at once, which no rollback could take back.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from types import MappingProxyType

import frappe
from frappe import _
from frappe.utils import escape_html, fmt_money, formatdate, getdate, safe_decode

from steuerbote import dauerfrist_sources, ledger, prior_filings, ustjahr_sources
from steuerbote.mapping_sync import rows_to_mapping
from steuerbote.setup import chart as charts
from steuerbote.setup import rhythm, steps
from steuerbote.setup import start as first_year
from steuerbote.setup.steps import Note, Outcome, Step, StepResult
from steuerbote.steuerbote.doctype.annual_filing_settings.annual_filing_settings import settings_of
from steuerbote.steuerbote.doctype.annual_vat_return import bridge as annual_vat_return_bridge
from steuerbote.steuerbote.doctype.vat_return.bridge import statutory_tax_of
from steuerbote.ustva import CATALOGUES, DEFAULTS, MappingError, UnknownYearError, calculate
from steuerbote.ustva.period import MONTH_NAMES
from steuerbote.vat_periods import VatLedger
from steuerbote.zm import rhythm as zm_rhythm
from steuerbote.zm.errors import ZmError

STEPS_HOOK = "steuerbote_setup_steps"
ROLES = ("System Manager", "Accounts Manager")
SETTINGS = "VAT Return Settings"
MAPPING = "VAT Return Mapping"
OWN_CHART = "Eigener Kontenrahmen"
EXISTING_COMPANY = "Existing Company"
SAVEPOINT = "steuerbote_setup_step"
STATUS_SAVEPOINT = "steuerbote_setup_status"
# The callbacks Frappe runs at the commit or the rollback of the transaction, and the queues of realtime messages and
# webhooks it flushes at the commit (frappe.realtime.publish_realtime, frappe.integrations.doctype.webhook).
CALLBACKS = ("before_commit", "after_commit", "before_rollback", "after_rollback")
LOCAL_QUEUES = ("_realtime_log", "_webhook_queue")
DOCUMENT_CACHE = "document_cache::"
# The parts of the Datenlieferant that saving the settings fills from the company, with their labels.
DATENLIEFERANT_LABELS = (
	("filer_name", "Name"),
	("street", "Street and House Number"),
	("postal_code", "Postal Code"),
	("city", "Town"),
	("phone", "Phone"),
	("email", "Email"),
)

# The parts of the Datenlieferant that the file for Mein ELSTER and ERiC require (steuerbote/elster/ustva_xml.py).
REQUIRED_DATENLIEFERANT = tuple(
	(field, label)
	for field, label in DATENLIEFERANT_LABELS
	if field in ("filer_name", "street", "postal_code", "city")
)

BUILT_IN_STEPS = (
	{
		"key": "vat_return_settings",
		"label": "VAT Return Settings",
		"order": 10,
		"run": "steuerbote.steuerbote.setup.make_vat_return_settings",
	},
	{
		"key": "vat_return_mapping",
		"label": "VAT Return Mapping",
		"order": 20,
		"run": "steuerbote.steuerbote.setup.make_vat_return_mapping",
	},
	{
		"key": "filing_period",
		"label": "Filing Period",
		"order": 30,
		"needs": ["vat_return_settings", "vat_return_mapping"],
		"run": "steuerbote.steuerbote.setup.propose_filing_period",
	},
)

NOT_A_COMPANY = "There is no company {0}."
NEEDS_STEPS = "Not run: it needs {0}, which did not create or find its document."
STEP_FAILED = "The step stopped: {0}"
STEP_BROKE = "The step stopped with an error; the Error Log names it."
SETTINGS_EXIST = "The VAT Return Settings of {0} exist already; the setup leaves them as they are."
SETTINGS_MADE = "Made the VAT Return Settings of {0} with the chart {1}, Soll-Versteuerung, the Voranmeldungszeitraum by service date, a corrected return for bookings of a filed period and no Dauerfristverlängerung."
VAT_ID_TAKEN = "USt-IdNr. {0} taken from the Tax ID of the company."
DATENLIEFERANT_TAKEN = "Datenlieferant taken from the company and its address: {0}."
STATE_AND_TAX_NUMBER = "Enter the Bundesland and the Steuernummer the Finanzamt issued in the VAT Return Settings: Steuerbote cannot take them from the company."
MAPPING_EXISTS = (
	"The VAT Return Mapping of {0} exists already with the chart {1}; the setup leaves it as it is."
)
MAPPING_FILLED = "The VAT Return Mapping of {0} had no rows and now holds the defaults {1}: account rules {2}, tax checks {3}, watched accounts {4}."
MAPPING_WITH_DEFAULTS = "Made the VAT Return Mapping with the defaults of {0}: account rules {1}, tax checks {2}, watched accounts {3}."
CHART_FROM_TEMPLATE = (
	"The chart {0} follows from the template {1} the chart of accounts of the company was made from."
)
CHART_FROM_ACCOUNTS = "The chart {0} follows from the accounts {1} of the company."
DEFAULTS_MISSING = "{0} accounts of the defaults do not exist in the company and were left out."
OWN_CHART_EMPTY = "Neither the template of its chart of accounts nor its accounts show SKR03 or SKR04, so the mapping of {0} has no rules yet: give each account of the Voranmeldung a rule or watch it."
AMBIGUOUS_CHART = "The template or the accounts of {0} point to SKR03 and SKR04 at once, so the mapping has no rules yet: choose the chart in the mapping and load its defaults."
PERIODS_EXIST = "The VAT Return Settings have a Voranmeldungszeitraum already; the setup leaves it as it is."
PROPOSED_FROM_TAX = "Proposed: {0} from {1}, because the tax of {2} comes to {3} by the ledger (§ 18 Absatz 2 Sätze 1 and 2 UStG)."
PROPOSED_FROM_START = "Proposed: monthly from {0}, because the company began on {1}, and in the year it begins and the next the month is the Voranmeldungszeitraum (§ 18 Absatz 2 Satz 4 UStG)."
EXEMPTION_POSSIBLE = "With a tax of at most 2,000 € the Finanzamt may exempt the company from the Voranmeldungen (§ 18 Absatz 2 Satz 3 UStG)."
MONTH_POSSIBLE = (
	"With a surplus of more than 9,000 € the company may choose the month instead (§ 18 Absatz 2a UStG)."
)
CHECK_WITH_FINANZAMT = "The Finanzamt sets the Voranmeldungszeitraum: compare the proposal with what it set."
STARTED_THIS_YEAR = "No proposal: the company began on {0}, and until 2026 its expected tax of {1} decides (§ 18 Absatz 2 Satz 6 UStG), which Steuerbote does not know."
STARTED_LAST_YEAR = "No proposal: the company began on {0}, and until 2026 its tax of {1} turned into the tax of a whole year decides (§ 18 Absatz 2 Satz 6 UStG), which Steuerbote does not compute."
NOT_STARTED = "No proposal: the company begins on {0}, after {1}."
NO_CATALOGUE = "No proposal: the tax of {0} decides (§ 18 Absatz 2 UStG), and Steuerbote does not know the Kennzahlen of {0} to compute it from the ledger."
NO_DEFAULTS = "No proposal: the tax of {0} decides (§ 18 Absatz 2 UStG), and a mapping without the defaults of SKR03 or SKR04 cannot compute it from the ledger yet."
MAPPING_UNFIT = "No proposal: the tax of {0} decides (§ 18 Absatz 2 UStG), and the mapping does not fit the form of {0}: {1}"
NO_POSTINGS = (
	"No proposal: the tax of {0} decides (§ 18 Absatz 2 UStG), and the ledger holds no postings of {0}."
)
NOT_READY = "No proposal: the tax of {0} decides (§ 18 Absatz 2 UStG), and in the ledger of {0} an account watched at the level Blocking has a balance or a Verprobung has a difference."
ENTER_FILING_PERIOD = "Enter the Voranmeldungszeitraum the Finanzamt set in the VAT Return Settings."
PROPOSED_FROM_PRIOR = "Proposed: {0} from {1}, because the tax of {2} comes to {3} by its Voranmeldungen filed before Steuerbote (§ 18 Absatz 2 Sätze 1 and 2 UStG)."
NO_PRIOR_FILINGS = "No proposal: the tax of {0} decides (§ 18 Absatz 2 UStG), and the books in ERPNext begin after the start of {0}. Enter the Voranmeldungen of {0} filed before Steuerbote as VAT Return Prior Filings and run the setup again."
TEMPLATES_PLACED = (
	"Check Tax Templates finds every account of the tax templates of the company placed in the mapping."
)
TEMPLATES_UNPLACED = "Check Tax Templates finds accounts of the tax templates without a place in the mapping: {0}. A chart of accounts copied from another company may point a template to another account: correct the template, or give the account its place in the mapping."
DATENLIEFERANT_MISSING = "Enter the missing parts of the Datenlieferant in the VAT Return Settings, which the file for Mein ELSTER and ERiC need: {0}."
START_PROPOSED = "Books Start set to {0}: the books of the company begin that day with opening entries only. Check the day; the Voranmeldungen before it count as filed outside Steuerbote."
MESSAGES = (
	NOT_A_COMPANY,
	NEEDS_STEPS,
	STEP_FAILED,
	STEP_BROKE,
	SETTINGS_EXIST,
	SETTINGS_MADE,
	VAT_ID_TAKEN,
	DATENLIEFERANT_TAKEN,
	STATE_AND_TAX_NUMBER,
	MAPPING_EXISTS,
	MAPPING_FILLED,
	MAPPING_WITH_DEFAULTS,
	CHART_FROM_TEMPLATE,
	CHART_FROM_ACCOUNTS,
	DEFAULTS_MISSING,
	OWN_CHART_EMPTY,
	AMBIGUOUS_CHART,
	PERIODS_EXIST,
	PROPOSED_FROM_TAX,
	PROPOSED_FROM_START,
	EXEMPTION_POSSIBLE,
	MONTH_POSSIBLE,
	CHECK_WITH_FINANZAMT,
	STARTED_THIS_YEAR,
	STARTED_LAST_YEAR,
	NOT_STARTED,
	NO_CATALOGUE,
	NO_DEFAULTS,
	MAPPING_UNFIT,
	NO_POSTINGS,
	NOT_READY,
	ENTER_FILING_PERIOD,
	PROPOSED_FROM_PRIOR,
	NO_PRIOR_FILINGS,
	START_PROPOSED,
	TEMPLATES_PLACED,
	TEMPLATES_UNPLACED,
	DATENLIEFERANT_MISSING,
)


@dataclass(frozen=True)
class SetupContext:
	"""What a step works with: the company, the day of the run, the chart the company books in, and the results of
	the steps that ran before it, by key."""

	company: str
	today: date
	chart: charts.Detection
	results: Mapping[str, StepResult]


@dataclass
class Pending:
	"""What the transaction holds for its commit and rollback at a moment, and the messages shown until then."""

	callbacks: dict[str, tuple]
	queues: dict[str, list | None]
	shown: int

	@classmethod
	def now(cls) -> Pending:
		return cls(
			{name: tuple(getattr(frappe.db, name)._functions) for name in CALLBACKS},
			{
				name: None if (queue := getattr(frappe.local, name, None)) is None else list(queue)
				for name in LOCAL_QUEUES
			},
			len(frappe.local.message_log),
		)

	def restore(self) -> None:
		"""Drop what was queued and shown since."""
		for name, functions in self.callbacks.items():
			manager = getattr(frappe.db, name)._functions
			manager.clear()
			manager.extend(functions)
		for name, queue in self.queues.items():
			if queue is not None:
				setattr(frappe.local, name, queue)
			elif hasattr(frappe.local, name):
				delattr(frappe.local, name)
		del frappe.local.message_log[self.shown :]


@contextmanager
def inert() -> Iterator[None]:
	"""Run the block for its results alone. The database rolls back to before it, and so does what a rollback leaves:
	what the block queued for the commit or the rollback of the transaction and the messages it showed are dropped,
	the documents it cached are dropped from the cache and those it cleared from the cache are cached again as the
	database holds them, and the global search queues nothing meanwhile."""
	pending = Pending.now()
	cached = set(frappe.cache.get_keys(DOCUMENT_CACHE))
	conf = frappe.local.conf
	searching = conf.get("disable_global_search")
	conf.disable_global_search = 1
	frappe.db.savepoint(STATUS_SAVEPOINT)
	try:
		yield
	finally:
		frappe.db.rollback(save_point=STATUS_SAVEPOINT)
		conf.disable_global_search = searching
		_restore_document_cache(cached)
		pending.restore()


def _restore_document_cache(cached: set) -> None:
	"""Back to the documents of ``cached``, the keys of the document cache before: the keys added since go, and the
	documents cleared since are read again from the database, as frappe.get_cached_doc caches them."""
	keys = set(frappe.cache.get_keys(DOCUMENT_CACHE))
	if added := keys - cached:
		frappe.cache.delete_value(list(added), make_keys=False)
	for key in cached - keys:
		doctype, _sep, name = safe_decode(key).partition(DOCUMENT_CACHE)[2].partition("::")
		try:
			frappe.get_cached_doc(doctype, name)
		except frappe.DoesNotExistError:
			continue


@frappe.whitelist(methods=["POST"])
def set_up(company: str | None = None) -> dict:
	"""Steuerbote einrichten for the company: run every step and report what each did."""
	_require_company(company)
	return report(company, run(company, getdate()))


@frappe.whitelist(methods=["POST"])
def setup_status(company: str | None = None) -> dict:
	"""What Steuerbote einrichten would do for the company, which the page shows before the setup runs: every step runs
	as in set_up, inert, so that nothing it makes, queues or caches stays and its messages are not shown. A step that
	would make its document reports it as made, ``before`` tells the page that nothing was made."""
	_require_company(company)
	with inert():
		done = run(company, getdate())
	return {**report(company, done), "before": True}


def _require_company(company: str | None) -> None:
	frappe.only_for(ROLES, message=True)
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_(NOT_A_COMPANY).format(frappe.bold(escape_html(company or ""))))
	frappe.has_permission("Company", "read", company, throw=True)


def setup_steps() -> tuple[Step, ...]:
	"""The steps of this module and those of the hook, in the order they run."""
	try:
		return steps.plan(Step.from_hook(entry) for entry in (*BUILT_IN_STEPS, *frappe.get_hooks(STEPS_HOOK)))
	except steps.SetupError as error:
		frappe.throw(_(error.template).format(*error.values), title=_("Set Up Steuerbote"))


def run(company: str, today: date) -> list[tuple[Step, StepResult]]:
	"""Run the steps for the company, each in a savepoint of its own; returns each step with its result."""
	planned = setup_steps()
	results: dict[str, StepResult] = {}
	context = SetupContext(company, today, company_chart(company), MappingProxyType(results))
	labels = {step.key: step.label for step in planned}
	done = []
	for step in planned:
		result = run_step(step, context, labels)
		results[step.key] = result
		done.append((step, result))
	return done


def run_step(step: Step, context: SetupContext, labels: Mapping[str, str]) -> StepResult:
	if missing := steps.missing_needs(step, context.results):
		names = ", ".join(_(labels[need]) for need in missing)
		return StepResult(Outcome.BLOCKED, (Note(NEEDS_STEPS, (names,)),))
	pending = Pending.now()
	frappe.db.savepoint(SAVEPOINT)
	try:
		result = frappe.get_attr(step.run)(context)
	except frappe.ValidationError as error:
		frappe.db.rollback(save_point=SAVEPOINT)
		pending.restore()
		return StepResult(Outcome.FAILED, (Note(STEP_FAILED, (str(error),)),))
	except Exception:
		frappe.db.rollback(save_point=SAVEPOINT)
		pending.restore()
		frappe.log_error(title=_("The setup step {0} of {1} failed").format(step.key, context.company))
		return StepResult(Outcome.FAILED, (Note(STEP_BROKE),))
	frappe.db.release_savepoint(SAVEPOINT)
	return result


def report(company: str, done: list[tuple[Step, StepResult]]) -> dict:
	"""What the page shows: each step with its label, outcome, notes and document, and whether the run changed
	anything."""
	return {
		"company": company,
		"changed": steps.changed(result for _step, result in done),
		"steps": [
			{
				"key": step.key,
				"label": _(step.label),
				"outcome": result.outcome.value,
				"notes": [{"text": text_of(note), "open": note.open} for note in result.notes],
				"doctype": result.document[0] if result.document else None,
				"document_label": _(result.document[0]) if result.document else None,
				"name": result.document[1] if result.document else None,
				"action": {"label": _(result.action.label), "method": result.action.method}
				if result.action
				else None,
			}
			for step, result in done
		],
	}


def text_of(note: Note) -> str:
	"""The note in the language of the user, amounts in euros and days in the date format of the site."""
	return _(note.template).format(*(_value(value) for value in note.values))


def _value(value: object) -> object:
	if isinstance(value, Decimal):
		return fmt_money(value, currency="EUR")
	if isinstance(value, date):
		return formatdate(value)
	return value


def company_chart(company: str) -> charts.Detection:
	"""The chart the company books in, from the template of its chart of accounts and its account numbers."""
	numbers = frappe.get_all("Account", filters={"company": company, "is_group": 0}, pluck="account_number")
	return charts.detect(chart_template(company), [number.strip() for number in numbers if number])


def chart_template(company: str) -> str | None:
	"""The template the chart of accounts of the company was made from, through the companies it was copied from."""
	seen = set()
	while company and company not in seen:
		seen.add(company)
		values = frappe.db.get_value(
			"Company",
			company,
			["chart_of_accounts", "create_chart_of_accounts_based_on", "existing_company"],
			as_dict=True,
		)
		if not values:
			return None
		if values.create_chart_of_accounts_based_on != EXISTING_COMPANY:
			return values.chart_of_accounts or None
		company = values.existing_company
	return None


def make_vat_return_settings(context: SetupContext) -> StepResult:
	"""The VAT Return Settings, if the company has none: the chart of the company, Soll-Versteuerung and the
	defaults of the DocType, among them the assignment by service date and the corrected return for bookings of a
	filed period (steuerbote.ustva.assignment); saving fills the own USt-IdNr. from the Tax ID of the company and the Datenlieferant
	from the company and its address. The Bundesland and the Steuernummer stay for the user, and so does the
	Voranmeldungszeitraum unless the step filing_period proposes one."""
	company = context.company
	if frappe.db.exists(SETTINGS, company):
		settings = frappe.get_doc(SETTINGS, company)
		notes = [Note(SETTINGS_EXIST, (company,))]
		if not (settings.state and settings.tax_number):
			notes.append(Note(STATE_AND_TAX_NUMBER, open=True))
		return StepResult(Outcome.SKIPPED, tuple(notes), (SETTINGS, settings.name))
	settings = frappe.new_doc(SETTINGS)
	settings.company = company
	settings.chart = context.chart.chart or OWN_CHART
	settings.insert(ignore_mandatory=True)
	notes = [Note(SETTINGS_MADE, (company, settings.chart))]
	if settings.ust_idnr:
		notes.append(Note(VAT_ID_TAKEN, (settings.ust_idnr,)))
	if taken := [_(label) for field, label in DATENLIEFERANT_LABELS if settings.get(field)]:
		notes.append(Note(DATENLIEFERANT_TAKEN, (", ".join(taken),)))
	if lacking := [_(label) for field, label in REQUIRED_DATENLIEFERANT if not settings.get(field)]:
		notes.append(Note(DATENLIEFERANT_MISSING, (", ".join(lacking),), open=True))
	notes.append(Note(STATE_AND_TAX_NUMBER, open=True))
	return StepResult(Outcome.CREATED, tuple(notes), (SETTINGS, settings.name))


def make_vat_return_mapping(context: SetupContext) -> StepResult:
	"""The VAT Return Mapping, if the company has none: with the defaults of SKR03 or SKR04 for the accounts the
	company has (load_defaults), or without rules for a chart of its own or an ambiguous one. A mapping the company has
	stays as it is, unless it waits for the defaults of today (waits_for_defaults): then it gets them as a new one
	does."""
	company = context.company
	if frappe.db.exists(MAPPING, company):
		mapping = frappe.get_doc(MAPPING, company)
		if not mapping.waits_for_defaults():
			return StepResult(
				Outcome.SKIPPED, (Note(MAPPING_EXISTS, (company, mapping.chart)),), (MAPPING, company)
			)
		missing = mapping.load_defaults()
		mapping.save()
		counted = (len(mapping.rules), len(mapping.checks), len(mapping.watched))
		notes = [Note(MAPPING_FILLED, (company, mapping.defaults_version, *counted))]
		if missing:
			notes.append(Note(DEFAULTS_MISSING, (len(missing),)))
		notes.append(tax_template_note(mapping))
		return StepResult(Outcome.CREATED, tuple(notes), (MAPPING, company))
	detection = context.chart
	mapping = frappe.new_doc(MAPPING)
	mapping.company = company
	if detection.chart not in DEFAULTS:
		mapping.chart = OWN_CHART
		mapping.insert()
		template = AMBIGUOUS_CHART if detection.basis is charts.Basis.AMBIGUOUS else OWN_CHART_EMPTY
		return StepResult(Outcome.CREATED, (Note(template, (company,), open=True),), (MAPPING, mapping.name))
	mapping.chart = detection.chart
	missing = mapping.load_defaults()
	mapping.insert()
	notes = [
		Note(
			MAPPING_WITH_DEFAULTS,
			(mapping.chart, len(mapping.rules), len(mapping.checks), len(mapping.watched)),
		),
		_basis_note(detection, company),
	]
	if missing:
		notes.append(Note(DEFAULTS_MISSING, (len(missing),)))
	notes.append(tax_template_note(mapping))
	return StepResult(Outcome.CREATED, tuple(notes), (MAPPING, mapping.name))


def tax_template_note(mapping) -> Note:
	"""What Steuervorlagen prüfen finds in the mapping the step made: the accounts of the tax templates without a place,
	which a copied chart of accounts or template may have pointed to another account, or that there are none."""
	unplaced = mapping.check_tax_templates()
	if not unplaced:
		return Note(TEMPLATES_PLACED)
	accounts = "; ".join(
		f"{account['account_number'] or account['account']} ({', '.join(account['templates'])})"
		for account in unplaced
	)
	return Note(TEMPLATES_UNPLACED, (accounts,), open=True)


def _basis_note(detection: charts.Detection, company: str) -> Note:
	if detection.basis is charts.Basis.TEMPLATE:
		return Note(CHART_FROM_TEMPLATE, (detection.chart, chart_template(company)))
	signature = ", ".join(sorted(charts.SIGNATURES[detection.chart]))
	return Note(CHART_FROM_ACCOUNTS, (detection.chart, signature))


def propose_filing_period(context: SetupContext) -> StepResult:
	"""The first Voranmeldungszeitraum of the settings, from the year of the run on, if the settings have none and
	§ 18 Absatz 2 UStG decides it from the start of the company or the tax of the previous year (steuerbote.setup.
	rhythm). The tax comes from the ledger of that year with the mapping of the company, as Berechnen computes Kz 83.
	"""
	company, year = context.company, context.today.year
	settings = frappe.get_doc(SETTINGS, company)
	if settings.period_rules:
		return StepResult(Outcome.SKIPPED, (Note(PERIODS_EXIST),), (SETTINGS, settings.name))
	began = dauerfrist_sources.date_of_establishment(company)
	tax, no_tax, from_prior = None, None, False
	if rhythm.needs_tax(year, began):
		tax = first_year.year_tax(prior_filings.prior_filings(company, {year - 1}), year - 1)
		from_prior = tax is not None
		if tax is None and first_year.before_start(date(year - 1, 1, 1), prior_filings.books_start(company)):
			no_tax = Note(NO_PRIOR_FILINGS, (year - 1,))
		elif tax is None:
			tax, no_tax = previous_year_tax(company, year - 1)
	proposal = rhythm.propose(year, began, tax)
	if proposal.rhythm is None:
		reason = no_tax or _undecided(proposal.reason, year, began)
		return StepResult(
			Outcome.UNDECIDED, (reason, Note(ENTER_FILING_PERIOD, open=True)), (SETTINGS, settings.name)
		)
	month = rhythm.first_month(year, began)
	settings.append(
		"period_rules", {"year": year, "rhythm": proposal.rhythm.value, "valid_from_month": month}
	)
	# The settings the setup made lack the Bundesland and the Steuernummer until the user enters them.
	settings.flags.ignore_mandatory = True
	settings.save()
	start = f"{MONTH_NAMES[month - 1]} {year}"
	if proposal.reason is rhythm.Reason.STARTED:
		notes = [Note(PROPOSED_FROM_START, (start, began))]
	else:
		template = PROPOSED_FROM_PRIOR if from_prior else PROPOSED_FROM_TAX
		notes = [Note(template, (_(proposal.rhythm.value), start, year - 1, proposal.tax))]
	if proposal.exemption_possible:
		notes.append(Note(EXEMPTION_POSSIBLE))
	if proposal.month_possible:
		notes.append(Note(MONTH_POSSIBLE))
	notes.append(Note(CHECK_WITH_FINANZAMT, open=True))
	return StepResult(Outcome.CREATED, tuple(notes), (SETTINGS, settings.name))


def _undecided(reason: rhythm.Reason, year: int, began: date | None) -> Note:
	"""Why a company that began in the year, the year before or later gets no proposal."""
	if reason is rhythm.Reason.STARTED_THIS_YEAR:
		return Note(STARTED_THIS_YEAR, (began, year))
	if reason is rhythm.Reason.STARTED_LAST_YEAR:
		return Note(STARTED_LAST_YEAR, (began, year - 1))
	return Note(NOT_STARTED, (began, year))


def check_books_start(context: SetupContext) -> StepResult:
	"""Start in Steuerbote (steuerbote/setup/start.py): set the start of the books where the ledger shows it plainly, and
	show or check what a start with opening balances needs, in the order a user works through it."""
	company = context.company
	settings = frappe.get_doc(SETTINGS, company)
	outcome, notes = Outcome.SKIPPED, []
	if not settings.books_start:
		proposed = proposed_books_start(company)
		if proposed is None:
			return StepResult(Outcome.SKIPPED, (Note(first_year.START_MISSING),), (SETTINGS, settings.name))
		settings.books_start = proposed
		# The settings the setup made lack the Bundesland and the Steuernummer until the user enters them.
		settings.flags.ignore_mandatory = True
		settings.save()
		outcome = Outcome.CREATED
		notes.append(Note(START_PROPOSED, (proposed,), open=True))
	facts = start_facts(company, getdate(settings.books_start))
	checks = first_year.checklist(facts)
	for check in checks:
		values = check.values
		if check.template == first_year.CARRY_FORWARDS_MISSING:
			values = (values[0], ", ".join(_(str(kind)) for kind in facts.missing_carry_forwards))
		notes.append(Note(check.template, values, open=check.done is False))
	if outcome is Outcome.SKIPPED and any(check.done is False for check in checks):
		outcome = Outcome.UNDECIDED
	return StepResult(outcome, tuple(notes), (SETTINGS, settings.name))


def proposed_books_start(company: str) -> date | None:
	"""The day the books of the company begin, where its first entries are opening entries alone, on the first day of a
	month or on the last day of the month before it; None where they are not, or where the company was founded then and
	so has every period in its books."""
	first = frappe.get_all(
		"GL Entry",
		filters={"company": company, "is_cancelled": 0},
		fields=["posting_date"],
		order_by="posting_date asc",
		limit=1,
	)
	if not first:
		return None
	day = getdate(first[0].posting_date)
	if frappe.db.exists(
		"GL Entry", {"company": company, "is_cancelled": 0, "posting_date": day, "is_opening": "No"}
	):
		return None
	following = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
	if day.day == 1:
		books_start = day
	elif following - timedelta(days=1) == day:
		books_start = following
	else:
		return None
	began = dauerfrist_sources.date_of_establishment(company)
	if began is not None and began >= books_start - timedelta(days=31):
		return None
	return books_start


def start_facts(company: str, books_start: date) -> first_year.Facts:
	"""What the site says about the start of the books for the checklist."""
	began = dauerfrist_sources.date_of_establishment(company)
	annual = settings_of(company)
	missing = ()
	if annual is not None:
		year_end = date(first_year.first_annual_year(books_start) - 1, 12, 31)
		missing = first_year.missing_carry_forwards(annual.get_carry_forwards(), year_end)
	filed = prior_filings.prior_filings(company)
	return first_year.Facts(
		books_start,
		unflagged=unflagged_opening_entries(company, books_start),
		missing_prior=first_year.missing_months(books_start, began, filed),
		annual_settings=annual is not None,
		missing_carry_forwards=missing,
		prior_payments=paid_before_start(company, books_start),
		zm_rhythm=has_zm_rhythm(company, books_start),
		eu_turnover=any(filing.kz41 or filing.kz42 or filing.kz21 for filing in filed),
	)


def has_zm_rhythm(company: str, day: date) -> bool:
	"""Whether the VAT Return Settings record a rhythm of the Zusammenfassende Meldung for the month of the day."""
	rules = frappe.get_doc(SETTINGS, company).get_zm_rules()
	try:
		zm_rhythm.rule_for(rules, day.year, day.month)
	except ZmError:
		return False
	return True


def paid_before_start(company: str, books_start: date) -> tuple[str, ...]:
	"""The vouchers of the year of the start on the accounts of the Vorauszahlungen that pay a Voranmeldung filed
	before Steuerbote (steuerbote/setup/start.py), by name."""
	chart = frappe.db.get_value(MAPPING, company, "chart")
	accounts = tuple(ledger.account_names(company, annual_vat_return_bridge.payment_accounts(chart or "")))
	if not accounts:
		return ()
	lines = ustjahr_sources.payment_lines(company, books_start.year, accounts)
	found = first_year.prior_payments(lines, prior_filings.prior_filings(company))
	return tuple(payment.voucher.partition(":")[2] for payment in found)


def unflagged_opening_entries(company: str, books_start: date) -> tuple[str, ...]:
	"""The Journal Entries of the start of the books and the day before that the Voranmeldung counts: no opening entry,
	without the flag Exclude from VAT Return, on an account of the VAT Return Mapping."""
	numbers = set(
		frappe.get_all(
			"VAT Return Mapping Rule",
			filters={"parent": company, "parenttype": MAPPING},
			pluck="account_number",
		)
	) | set(
		frappe.get_all(
			"VAT Return Watched Account",
			filters={"parent": company, "parenttype": MAPPING},
			pluck="account_number",
		)
	)
	numbers.discard(None)
	if not numbers:
		return ()
	accounts = frappe.get_all(
		"Account", filters={"company": company, "account_number": ["in", sorted(numbers)]}, pluck="name"
	)
	vouchers = frappe.get_all(
		"GL Entry",
		filters={
			"company": company,
			"is_cancelled": 0,
			"is_opening": "No",
			"voucher_type": "Journal Entry",
			"posting_date": ["between", [books_start - timedelta(days=1), books_start]],
			"account": ["in", accounts or [""]],
		},
		pluck="voucher_no",
		distinct=True,
	)
	if not vouchers:
		return ()
	flagged = set(
		frappe.get_all(
			"Journal Entry",
			filters={"name": ["in", vouchers], ledger.EXCLUDE_FIELD: 1},
			pluck="name",
		)
	)
	return tuple(sorted(set(vouchers) - flagged))


def previous_year_tax(company: str, year: int) -> tuple[Decimal | None, Note | None]:
	"""Kz 83 of the year by the ledger, placed by the settings as for the Voranmeldung (steuerbote.vat_periods), with
	the mapping of the company and the tax of the bases at a statutory rate as the settings choose it, as Berechnen
	computes it for a period; or
	None and the note why it is unknown: Steuerbote does not know the Kennzahlen of the year, the mapping has no
	defaults or does not fit the form of the year, the ledger holds nothing of the year, or what it holds is not
	ready to file."""
	if year not in CATALOGUES:
		return None, Note(NO_CATALOGUE, (year,))
	doc = frappe.get_doc(MAPPING, company)
	if doc.chart not in DEFAULTS:
		return None, Note(NO_DEFAULTS, (year,))
	try:
		mapping = rows_to_mapping(
			doc.chart,
			[row.as_dict() for row in doc.rules],
			[row.as_dict() for row in doc.checks],
			[row.as_dict() for row in doc.watched],
			year,
		)
	except (MappingError, UnknownYearError) as error:
		return None, Note(MAPPING_UNFIT, (year, str(error)))
	start, end = date(year, 1, 1), date(year, 12, 31)
	lines = VatLedger(company, start, end).lines_between(start, end)
	if not lines:
		return None, Note(NO_POSTINGS, (year,))
	result = calculate(
		lines,
		mapping,
		statutory_tax=statutory_tax_of(frappe.db.get_value("VAT Return Settings", company, "statutory_tax")),
	)
	if not result.ready:
		return None, Note(NOT_READY, (year,))
	return result.kz83, None
