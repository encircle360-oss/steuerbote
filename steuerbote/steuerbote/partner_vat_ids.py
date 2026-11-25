"""The USt-IdNrn. of customers and suppliers: Steuerbote confirms them at the BZSt when a partner is made or changed,
on the button of its form and every day the confirmation is due, and checks a Sales Invoice behind Kz 41, 42 or 21 on
submit. steuerbote.vatid.partners decides; this module reads the partners and the VAT ID Confirmation records of the
site, asks through steuerbote.vatid in background jobs and keeps each query as a VAT ID Confirmation that names the
partner and what started it.

A confirmation belongs to a company and is asked with its own USt-IdNr. (UStAE 18e.1 Abs. 1). A partner is confirmed
for the companies it deals with, those of its Party Accounts and of its submitted invoices, or for the default
company when it deals with none yet; a company takes part once its VAT Return Settings hold its own German USt-IdNr.
Only a number a service checks leaves the site: a plausible number of another member state with the structure the
BZSt describes goes to the BZSt, and to VIES only when the BZSt cannot answer; a German number whose check digit is
right goes to VIES alone, simply, where the company checks German numbers, since the BZSt confirms no German
numbers. A malformed number and one of a country outside the EU are never sent, and the status of the partner says
why.

may_ask() is the one rule for who may make Steuerbote ask a service; every trigger of this module goes through it.
"""

import time
from collections.abc import Collection, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

import frappe
from frappe import _
from frappe.utils import cint, escape_html, formatdate, getdate
from frappe.utils.background_jobs import is_job_enqueued

from steuerbote import vatid
from steuerbote.steuerbote.doctype.vat_id_confirmation import vat_id_confirmation
from steuerbote.vatid import partners
from steuerbote.vatid.exemption import consequence
from steuerbote.vatid.partners import (
	Answer,
	Asked,
	Candidate,
	Finding,
	Kind,
	Level,
	MappingRule,
	Policy,
	Problem,
	Standing,
	TodayQuery,
)
from steuerbote.vatid.result import Details, Outcome
from steuerbote.vatid.transport import UrllibFetch

CONFIRMATION = vat_id_confirmation.DOCTYPE
SETTINGS = "VAT Return Settings"
CUSTOMER = "Customer"
SUPPLIER = "Supplier"
PARTY_TYPES = (CUSTOMER, SUPPLIER)
NAME_FIELDS = {CUSTOMER: "customer_name", SUPPLIER: "supplier_name"}
ADDRESS_FIELDS = {CUSTOMER: "customer_primary_address", SUPPLIER: "supplier_primary_address"}
INVOICES = {CUSTOMER: ("Sales Invoice", "customer"), SUPPLIER: ("Purchase Invoice", "supplier")}
# What the qualified query sends, and so what makes a partner worth asking again when it changes.
WATCHED_PARTY_FIELDS = ("tax_id", "disabled")
WATCHED_ADDRESS_FIELDS = ("address_line1", "pincode", "city", "country", "disabled")
STATUS_FIELD = "vat_id_status"
CHECKED_ON_FIELD = "vat_id_checked_on"
LATEST_FIELD = "vat_id_confirmation"
RELEASE_FIELD = "vat_id_release_reason"

# The triggers a VAT ID Confirmation names; the Zusammenfassende Meldung and the Voranmeldung name their own.
MANUAL = "Manual"
CHANGED = "Partner Changed"
INVOICE = "Invoice"
RENEWAL = "Renewal"
TRIGGERS = (MANUAL, CHANGED, INVOICE, RENEWAL, "VAT Return", "Recapitulative Statement")

# The status of a partner's number on its form and in its list, from its kind or its latest confirmation.
NOT_CHECKED = "Not Checked"
KIND_STATUS = {
	Kind.MISSING: "",
	Kind.GERMAN: "German VAT ID, Not Checked",
	Kind.NOT_CONFIRMABLE: "Not Confirmable",
	Kind.MALFORMED: "Malformed",
}
# The problems after which the turnover loses what the USt-IdNr. carries, with the sentence of the Voranmeldung and the
# Zusammenfassende Meldung (steuerbote.vatid.exemption).
EXEMPTION_PROBLEMS = frozenset(
	{Problem.NO_VAT_ID, Problem.GERMAN, Problem.NOT_CONFIRMABLE, Problem.MALFORMED, Problem.INVALID}
)
RESULT_STATUS = {"valid": "Valid", "invalid": "Invalid", "unknown": "No Answer"}
VALID_SIMPLE = "Valid (Simple)"
STATUSES = (
	"",
	NOT_CHECKED,
	"Valid",
	VALID_SIMPLE,
	"Invalid",
	"No Answer",
	"German VAT ID, Not Checked",
	"Not Confirmable",
	"Malformed",
)
# The status a partner with a German number had before German numbers were checked; after_migrate gives it anew.
LEGACY_STATUSES = ("German VAT ID",)

PARTY_JOB = "steuerbote.steuerbote.partner_vat_ids.run_party_confirmation"
PARTY_EVENT = "steuerbote_partner_vat_id"
# Three queries of up to a minute each and a company more for good measure.
PARTY_JOB_TIMEOUT = 600
CONFIRMATION_FIELDS = (
	"name",
	"requested",
	"requested_at",
	"service",
	"outcome",
	"result",
	"qualified",
	"name_match",
	"street_match",
	"postcode_match",
	"city_match",
	"details_name",
	"details_street",
	"details_postcode",
	"details_city",
)
MATCH_FIELDS = ("name_match", "street_match", "postcode_match", "city_match")
SAVEPOINT = "steuerbote_partner_vat_id"
# Who may submit a VAT Return may send data off the site (steuerbote.steuerbote.guards.require_permission_to_send).
SEND_RIGHT = "VAT Return"


def may_ask(doctype: str, name: str, throw: bool = False) -> bool:
	"""Whether the user may make Steuerbote ask the BZSt or VIES about the USt-IdNr. of the document. A confirmation
	sends data off the site, so the rule of steuerbote.steuerbote.guards for that holds: at a document that is booked,
	such as a Sales Invoice, whoever may submit it; at a customer or supplier, which is never submitted, whoever may
	change it and may submit a VAT Return, the right that sends data off the site at the Voranmeldung. Every trigger
	asks here."""
	if frappe.get_meta(doctype).is_submittable:
		allowed = frappe.has_permission(doctype, "submit", name, throw=False)
	else:
		allowed = frappe.has_permission(doctype, "write", name, throw=False) and frappe.has_permission(
			SEND_RIGHT, "submit", throw=False
		)
	if not allowed and throw:
		frappe.throw(
			_(
				"A confirmation sends the USt-IdNr. of {0} off the site, to the BZSt or VIES: it needs the permission to submit a VAT Return, which Accounts Manager and System Manager have by default."
			).format(name),
			frappe.PermissionError,
		)
	return bool(allowed)


# What the site knows about a number


@dataclass(frozen=True, slots=True)
class Known:
	"""What the records of a company say about a number: its latest definite answer, the day of its latest query, the
	record of that answer, or else of the latest query, and the record of the latest query."""

	answer: Answer | None = None
	last_query_on: date | None = None
	record: str | None = None
	latest: str | None = None

	@property
	def asked(self) -> bool:
		return self.last_query_on is not None


def known(company: str, numbers: Collection[str]) -> dict[str, Known]:
	"""What the VAT ID Confirmation records of the company say about each number, normalized as they keep it.

	The result of a record is that of its confirmation up to it, so the newest record with a definite result carries
	the answer. It is qualified when that record is a qualified query of the BZSt that was answered: a qualified
	query that failed after the simple one leaves the number valid but unqualified, and VIES is not the BZSt that
	UStAE 3a.2 Abs. 9 Satz 5 names."""
	wanted = sorted({number for number in numbers if number})
	if not wanted:
		return {}
	found: dict[str, Known] = {}
	answered: set[str] = set()
	for row in frappe.get_all(
		CONFIRMATION,
		filters={"company": company, "requested": ["in", wanted]},
		fields=list(CONFIRMATION_FIELDS),
		order_by="creation desc",
	):
		current = found.get(row.requested)
		if current is None:
			current = found[row.requested] = Known(
				last_query_on=_day(row.requested_at), record=row.name, latest=row.name
			)
		if row.requested in answered or row.result not in ("valid", "invalid"):
			continue
		answered.add(row.requested)
		found[row.requested] = Known(
			Answer(
				_day(row.requested_at),
				Outcome(row.result),
				qualified=bool(cint(row.qualified)) and row.outcome == "valid" and row.service == "bzst",
				differs=any(row.get(field) == "B" for field in MATCH_FIELDS),
			),
			current.last_query_on,
			row.name,
			current.latest,
		)
	return found


def today_queries(company: str, number: str, today: date) -> list[TodayQuery]:
	"""The queries the company made today about the number, with the name and address each asked about."""
	rows = frappe.get_all(
		CONFIRMATION,
		filters={"company": company, "requested": number},
		fields=list(CONFIRMATION_FIELDS),
		order_by="creation desc",
	)
	return [
		TodayQuery(Outcome(row.outcome), _asked_details(row))
		for row in rows
		if _day(row.requested_at) == today
	]


def _asked_details(row: frappe._dict) -> Details | None:
	if not cint(row.qualified):
		return None
	try:
		return Details(
			row.details_name or "",
			row.details_city or "",
			row.details_postcode or "",
			row.details_street or "",
		)
	except ValueError:
		return None


def _day(moment: datetime | str | None) -> date | None:
	return getdate(moment) if moment else None


def party_details(party_type: str, party: str) -> Details | None:
	"""Name and address of the partner for the qualified query: its name and its primary address, or else the latest
	of its addresses; None without a name or a town."""
	name = frappe.db.get_value(party_type, party, NAME_FIELDS[party_type])
	address = _primary_address(party_type, party) or _linked_address(party_type, party)
	if address is None or not ((name or "").strip() and (address.city or "").strip()):
		return None
	try:
		return Details(name, address.city, address.pincode or "", address.address_line1 or "")
	except ValueError:
		return None


def _primary_address(party_type: str, party: str) -> frappe._dict | None:
	address = frappe.db.get_value(party_type, party, ADDRESS_FIELDS[party_type])
	if not address:
		return None
	return frappe.db.get_value(
		"Address", {"name": address, "disabled": 0}, ["address_line1", "pincode", "city"], as_dict=True
	)


def _linked_address(party_type: str, party: str) -> frappe._dict | None:
	links = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Address", "link_doctype": party_type, "link_name": party},
		pluck="parent",
	)
	if not links:
		return None
	addresses = frappe.get_all(
		"Address",
		filters={"name": ["in", links], "disabled": 0},
		fields=["address_line1", "pincode", "city"],
		order_by="is_primary_address desc, modified desc",
		limit=1,
	)
	return addresses[0] if addresses else None


# The companies that confirm


@dataclass(frozen=True, slots=True)
class CompanyPolicy:
	"""The VAT Return Settings of a company as the checks of partners read them."""

	company: str
	requester: str
	on_change: bool
	renewal: bool
	suppliers: bool
	max_age: int
	goods: Policy
	services: Policy
	german: bool = False
	"""Whether the company checks German USt-IdNrn. at VIES."""


def company_policy(company: str) -> CompanyPolicy | None:
	"""The policy of the company, None without VAT Return Settings that hold its own German USt-IdNr."""
	settings = frappe.db.get_value(
		SETTINGS,
		company,
		[
			"ust_idnr",
			"max_confirmation_age",
			"vat_id_check_on_change",
			"vat_id_renewal",
			"vat_id_check_suppliers",
			"vat_id_goods_max_age",
			"vat_id_invoice_goods",
			"vat_id_invoice_services",
			"vat_id_check_german",
		],
		as_dict=True,
	)
	if not settings or not vatid.is_german(settings.ust_idnr):
		return None
	max_age = _days(settings.max_confirmation_age, 90)
	return CompanyPolicy(
		company,
		vatid.normalize(settings.ust_idnr),
		bool(cint(settings.vat_id_check_on_change)),
		bool(cint(settings.vat_id_renewal)),
		bool(cint(settings.vat_id_check_suppliers)),
		max_age,
		Policy(_level(settings.vat_id_invoice_goods, Level.BLOCK), _days(settings.vat_id_goods_max_age, 0)),
		Policy(_level(settings.vat_id_invoice_services, Level.WARN), max_age),
		bool(cint(settings.vat_id_check_german)),
	)


def _days(value: object, default: int) -> int:
	return default if value in (None, "") else max(0, cint(value))


def _level(value: object, default: Level) -> Level:
	try:
		return Level(value)
	except ValueError:
		return default


def policies() -> list[CompanyPolicy]:
	"""The policies of every company whose settings hold its own German USt-IdNr., by name."""
	names = frappe.get_all(SETTINGS, pluck="name", order_by="name asc")
	return [policy for policy in (company_policy(name) for name in names) if policy is not None]


def dealings(party_type: str, parties: Collection[str] | None = None) -> dict[str, set[str]]:
	"""The companies each partner deals with: those of its Party Accounts and of its submitted invoices."""
	filters = {"parenttype": party_type}
	if parties is not None:
		filters["parent"] = ["in", sorted(parties) or [""]]
	found: dict[str, set[str]] = {}
	for row in frappe.get_all("Party Account", filters=filters, fields=["parent", "company"]):
		if row.company:
			found.setdefault(row.parent, set()).add(row.company)
	doctype, field = INVOICES[party_type]
	invoice_filters = {"docstatus": 1}
	if parties is not None:
		invoice_filters[field] = ["in", sorted(parties) or [""]]
	for row in frappe.get_all(
		doctype, filters=invoice_filters, fields=[f"{field} as party", "company"], distinct=True
	):
		found.setdefault(row.party, set()).add(row.company)
	return found


def default_company() -> str | None:
	return frappe.db.get_single_value("Global Defaults", "default_company") or None


def companies_asking(
	party_type: str, party: str, trigger: str, source: tuple[str, str] | None, number: Kind = Kind.CONFIRMABLE
) -> list[CompanyPolicy]:
	"""The companies that confirm the partner's number of the kind ``number`` for the trigger: for an invoice its
	company, else those of companies_for."""
	if source and source[0] == "Sales Invoice":
		company = frappe.db.get_value("Sales Invoice", source[1], "company")
		policy = company_policy(company) if company else None
		return [policy] if policy and number.checked(policy.german) else []
	return companies_for(party_type, party, trigger, number)


def companies_for(
	party_type: str, party: str, trigger: str, number: Kind = Kind.CONFIRMABLE
) -> list[CompanyPolicy]:
	"""The companies that confirm the partner's number for the trigger: those it deals with, or the default company
	when it deals with none, each with its own German USt-IdNr.; a change asks only where the settings confirm on a
	change, and a supplier only where they confirm suppliers, unless someone pressed the button; a German number only
	where the company checks German numbers, whatever the trigger."""
	companies = dealings(party_type, [party]).get(party) or {default_company()}
	chosen = []
	for company in sorted(name for name in companies if name):
		policy = company_policy(company)
		if policy is None or not number.checked(policy.german):
			continue
		if trigger != MANUAL and (
			(trigger == CHANGED and not policy.on_change) or (party_type == SUPPLIER and not policy.suppliers)
		):
			continue
		chosen.append(policy)
	return chosen


# The status of a partner


def refresh_status(party_type: str, party: str) -> dict:
	"""Set the status of the partner's number from its kind or from the newest confirmation of the number of any
	company, the day of that confirmation and its record; returns these values. A German number valid at VIES is
	„Valid (Simple)“: VIES confirms its validity without any comparison of name or address."""
	tax_id = frappe.db.get_value(party_type, party, "tax_id")
	number_kind = partners.kind(tax_id)
	values = {
		STATUS_FIELD: KIND_STATUS.get(number_kind, NOT_CHECKED),
		CHECKED_ON_FIELD: None,
		LATEST_FIELD: None,
	}
	if number_kind in (Kind.CONFIRMABLE, Kind.GERMAN):
		newest = frappe.get_all(
			CONFIRMATION,
			filters={"requested": vatid.normalize(tax_id)},
			fields=["name", "result", "requested_at"],
			order_by="creation desc",
			limit=1,
		)
		if newest:
			result = RESULT_STATUS[newest[0].result]
			values = {
				STATUS_FIELD: VALID_SIMPLE if number_kind is Kind.GERMAN and result == "Valid" else result,
				CHECKED_ON_FIELD: _day(newest[0].requested_at),
				LATEST_FIELD: newest[0].name,
			}
	frappe.db.set_value(party_type, party, values, update_modified=False)
	return values


# The triggers


def on_party_update(doc, method: str | None = None) -> None:
	"""doc_events on_update of Customer and Supplier: the status follows the number, and a new partner, a new number, a
	new name or a new primary address is confirmed in the background."""
	doc.update(refresh_status(doc.doctype, doc.name))
	before = doc.get_doc_before_save()
	if (before is None or before.get("tax_id") != doc.get("tax_id")) and partners.kind(
		doc.get("tax_id")
	) is Kind.MALFORMED:
		frappe.msgprint(
			_("The USt-IdNr. {0} is malformed and is not checked: {1}").format(
				escape_html(doc.get("tax_id") or ""), escape_html(partners.reason(doc.get("tax_id")) or "")
			),
			title=_("USt-IdNr."),
			indicator="orange",
		)
	watched = (*WATCHED_PARTY_FIELDS, NAME_FIELDS[doc.doctype], ADDRESS_FIELDS[doc.doctype])
	if before is not None and all(before.get(field) == doc.get(field) for field in watched):
		return
	request(doc.doctype, doc.name, CHANGED)


def on_address_update(doc, method: str | None = None) -> None:
	"""doc_events on_update of Address: a new or changed address of a partner asks the qualified query anew."""
	before = doc.get_doc_before_save()
	if before is not None and all(before.get(field) == doc.get(field) for field in WATCHED_ADDRESS_FIELDS):
		return
	for link in doc.get("links") or ():
		if link.link_doctype in PARTY_TYPES and link.link_name:
			request(link.link_doctype, link.link_name, CHANGED)


def request(
	party_type: str, party: str, trigger: str, source: tuple[str, str] | None = None, throw: bool = False
) -> bool:
	"""Put the confirmation of the partner's number into the background, if a company confirms it and the user may
	ask; returns whether it is queued. A confirmation of the same partner that waits in the queue takes this one in."""
	values = frappe.db.get_value(party_type, party, ["tax_id", "disabled"], as_dict=True)
	if not values or (cint(values.disabled) and trigger != MANUAL):
		return False
	number_kind = partners.kind(values.tax_id)
	if not number_kind.checked(german=True):
		if throw:
			frappe.throw(
				_("{0} has no USt-IdNr. that a service checks: {1}").format(
					party, partners.reason(values.tax_id) or _("The USt-IdNr. is missing.")
				)
			)
		return False
	if not companies_asking(party_type, party, trigger, source, number_kind):
		if throw and number_kind is Kind.GERMAN and companies_asking(party_type, party, trigger, source):
			frappe.throw(
				_(
					"{0} has a German USt-IdNr., and the company checks no German USt-IdNrn.: switch on „Check German VAT IDs“ in the VAT Return Settings."
				).format(party)
			)
		if throw:
			frappe.throw(
				_(
					"No company confirms USt-IdNrn. yet: enter the own USt-IdNr. of the company in the VAT Return Settings."
				)
			)
		return False
	if not may_ask(*(source or (party_type, party)), throw=throw):
		return False
	job_id = party_job_id(party_type, party)
	if is_job_enqueued(job_id):
		return True
	frappe.enqueue(
		PARTY_JOB,
		queue="long",
		timeout=PARTY_JOB_TIMEOUT,
		job_id=job_id,
		enqueue_after_commit=True,
		party_type=party_type,
		party=party,
		trigger=trigger,
		source_doctype=source[0] if source else None,
		source_name=source[1] if source else None,
		user=frappe.session.user,
	)
	return True


def party_job_id(party_type: str, party: str) -> str:
	return f"steuerbote:ustid:{party_type}:{party}"


@frappe.whitelist(methods=["POST"])
def confirm_vat_id(party_type: str, party: str) -> bool:
	"""The button „USt-IdNr. bestätigen“ of Customer and Supplier."""
	if party_type not in PARTY_TYPES:
		frappe.throw(_("Only the USt-IdNr. of a customer or a supplier is confirmed here."))
	return request(party_type, party, MANUAL, throw=True)


@frappe.whitelist(methods=["POST"])
def confirm_invoice_customer(sales_invoice: str) -> bool:
	"""The button „USt-IdNr. bestätigen“ of a draft Sales Invoice: the confirmation names the invoice."""
	customer, docstatus = frappe.db.get_value("Sales Invoice", sales_invoice, ["customer", "docstatus"]) or (
		None,
		None,
	)
	if not customer or cint(docstatus) != 0:
		frappe.throw(_("Only the customer of a saved draft invoice is confirmed here."))
	return request(CUSTOMER, customer, INVOICE, source=("Sales Invoice", sales_invoice), throw=True)


def run_party_confirmation(
	party_type: str,
	party: str,
	trigger: str,
	source_doctype: str | None = None,
	source_name: str | None = None,
	user: str | None = None,
) -> None:
	"""The background job of request(): confirm the partner's number for each company that confirms it, unless a
	query of today answers the question already, each confirmation committed at once as the proof of queries the
	service received; then the status of the partner, which the end of the job commits, and a notice to the user who
	started it."""
	stored, failed = 0, []
	try:
		tax_id = frappe.db.get_value(party_type, party, "tax_id")
		number_kind = partners.kind(tax_id)
		if number_kind.checked(german=True):
			number = vatid.normalize(tax_id)
			details = party_details(party_type, party) if number_kind is Kind.CONFIRMABLE else None
			source = (source_doctype, source_name) if source_doctype and source_name else None
			for policy in companies_asking(party_type, party, trigger, source, number_kind):
				outcome = _confirm(policy, number, details, (party_type, party), trigger, source)
				if outcome is Asked.FAILED:
					failed.append(policy.company)
				elif outcome is not None:
					stored += 1
	finally:
		status = (
			refresh_status(party_type, party)[STATUS_FIELD] if frappe.db.exists(party_type, party) else ""
		)
	frappe.publish_realtime(
		PARTY_EVENT,
		{"party_type": party_type, "party": party, "status": status, "asked": stored, "failed": failed},
		user=user,
		after_commit=True,
	)


def _confirm(
	policy: CompanyPolicy,
	number: str,
	details: Details | None,
	party: tuple[str, str],
	trigger: str,
	source: tuple[str, str] | None,
) -> Asked | None:
	"""Confirm the number for the company and keep each query; None when a query of today answers it already."""
	if partners.covered_today(today_queries(policy.company, number, getdate()), details):
		return None
	frappe.db.savepoint(SAVEPOINT)
	try:
		answer = vatid.confirm(number, policy.requester, details, UrllibFetch(), _clock)
		vat_id_confirmation.store(answer, policy.company, source, party=party, started_by=trigger)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback(save_point=SAVEPOINT)
		frappe.log_error(title=_("Confirmation of a USt-IdNr. failed"))
		return Asked.FAILED
	return Asked.UNAVAILABLE if answer.queries()[0].unavailable else Asked.ANSWERED


# The daily renewal


def renew_confirmations() -> None:
	"""The daily renewal (scheduler_events): for each company that renews, the partners it deals with whose number is
	due (partners.is_due), the oldest first, one after the other, until the first service that cannot answer, the
	end of the hours of the services or partners.MAX_PER_RUN; the status of every partner follows its number. A
	company without its own German USt-IdNr. renews nothing."""
	today = getdate()
	targets: dict[str, tuple[CompanyPolicy, str, tuple[str, str]]] = {}
	candidates: list[Candidate] = []
	for policy in policies():
		if not policy.renewal:
			continue
		chosen: dict[str, tuple[str, str]] = {}
		for party_type, party, tax_id in partners_of(policy):
			if partners.kind(tax_id).checked(policy.german):
				chosen.setdefault(vatid.normalize(tax_id), (party_type, party))
		facts = known(policy.company, chosen)
		for number, party in sorted(chosen.items()):
			fact = facts.get(number, Known())
			number_kind = partners.kind(number)
			has_details = number_kind is Kind.CONFIRMABLE and party_details(*party) is not None
			if partners.is_due(
				number_kind,
				fact.answer,
				fact.last_query_on,
				today,
				policy.max_age,
				has_details,
				german=policy.german,
			):
				key = f"{policy.company}\x1f{number}"
				targets[key] = (policy, number, party)
				candidates.append(Candidate(key, fact.answer))

	def ask(candidate: Candidate) -> Asked:
		policy, number, party = targets[candidate.key]
		try:
			details = party_details(*party) if partners.kind(number) is Kind.CONFIRMABLE else None
		except Exception:
			frappe.log_error(title=_("Confirmation of a USt-IdNr. failed"))
			return Asked.FAILED
		return _confirm(policy, number, details, party, RENEWAL, None) or Asked.ANSWERED

	run = partners.renew(
		partners.renewal_order(candidates), ask, lambda: time.sleep(partners.PAUSE_SECONDS), _clock
	)
	for _policy, _number, party in (targets[key] for key in (*run.stored, *run.failed)):
		if frappe.db.exists(*party):
			refresh_status(*party)
	refresh_statuses()


def partners_of(policy: CompanyPolicy) -> list[tuple[str, str, str]]:
	"""The enabled partners with a number whose confirmation the company renews, as (party type, party, number)."""
	types = PARTY_TYPES if policy.suppliers else (CUSTOMER,)
	fallback = default_company()
	found = []
	for party_type in types:
		rows = frappe.get_all(
			party_type,
			filters={"disabled": 0, "tax_id": ["is", "set"]},
			fields=["name", "tax_id"],
			order_by="name asc",
		)
		if not rows:
			continue
		companies = dealings(party_type, [row.name for row in rows])
		for row in rows:
			dealt = companies.get(row.name)
			if (policy.company in dealt) if dealt else policy.company == fallback:
				found.append((party_type, row.name, row.tax_id))
	return found


def fill_statuses() -> None:
	"""after_migrate: give every partner with a USt-IdNr. but no status yet, or a status of an earlier version, its
	status, and every partner whose number no service checks the status that says why, without asking anyone. The
	status fields come with the fixtures, which bench migrate loads after the patches."""
	for party_type in PARTY_TYPES:
		if not frappe.db.has_column(party_type, STATUS_FIELD):
			continue
		for status in (["is", "not set"], ["in", list(LEGACY_STATUSES)]):
			for name in frappe.get_all(
				party_type, filters={"tax_id": ["is", "set"], STATUS_FIELD: status}, pluck="name"
			):
				refresh_status(party_type, name)
	refresh_statuses()


def refresh_statuses() -> None:
	"""Set the status of every partner whose number no service checks, so that a malformed number shows on its form and
	in the worklist without a query."""
	for party_type in PARTY_TYPES:
		for row in frappe.get_all(party_type, filters={"tax_id": ["is", "set"]}, fields=["name", "tax_id"]):
			if partners.kind(row.tax_id) in (Kind.MALFORMED, Kind.NOT_CONFIRMABLE):
				refresh_status(party_type, row.name)


# The Sales Invoice


def check_invoice(doc, method: str | None = None) -> None:
	"""doc_events before_submit of Sales Invoice: an invoice whose income accounts feed Kz 41, 42 or 21 by the mapping
	of the company needs a current confirmation of the customer's USt-IdNr. (partners.invoice_finding). The settings
	block, warn or let it pass; a written reason in the field of the invoice submits a blocked one all the same and
	stays on it. The invoice keeps the confirmation it was checked against."""
	if cint(doc.get("is_return")) or doc.get("is_opening") == "Yes":
		return
	policy = company_policy(doc.company)
	if policy is None:
		return
	kennzahlen = invoice_kennzahlen(doc)
	if not kennzahlen:
		return
	vat_id = doc.get("tax_id") or frappe.db.get_value(CUSTOMER, doc.customer, "tax_id")
	number_kind = partners.kind(vat_id)
	number = vatid.normalize(vat_id or "")
	fact = known(doc.company, [number]).get(number, Known())
	doc.set(LATEST_FIELD, fact.record)
	finding = partners.invoice_finding(
		kennzahlen,
		number_kind,
		fact.answer,
		fact.asked,
		getdate(doc.posting_date),
		policy.goods,
		policy.services,
	)
	if finding is None:
		return
	text = finding_text(finding, vat_id, doc.customer_name or doc.customer, fact.answer)
	if finding.problem in EXEMPTION_PROBLEMS:
		text = f"{text} {consequence(finding.kennzahlen[0])}"
	title = _("USt-IdNr. of the Customer")
	if finding.level is Level.WARN:
		next_step = (
			_(
				"The invoice is submitted all the same. Next: press „Confirm VAT ID“ on the customer; for a service the qualified confirmation, with name and address, shows the customer a Unternehmer (UStAE 3a.2 Abs. 9)."
			)
			if finding.releasable
			else _("The invoice is submitted all the same. Correct the USt-IdNr. of the customer.")
		)
		frappe.msgprint(f"{text} {next_step}", title=title, indicator="orange")
		return
	reason = (doc.get(RELEASE_FIELD) or "").strip()
	if finding.releasable and reason:
		frappe.msgprint(
			_("{0} The USt-IdNr. is released for this invoice; reason: {1}").format(
				text, escape_html(reason)
			),
			title=title,
			indicator="orange",
		)
		return
	if not finding.releasable:
		frappe.throw(
			_(
				"{0} Correct the USt-IdNr. of the customer and of the invoice, or book the invoice on a revenue account that the mapping does not put into Kz 41, 42 or 21."
			).format(text),
			title=title,
		)
	frappe.throw(
		_(
			"{0} Next: press „Confirm VAT ID of the Customer“ on this invoice, or „Confirm VAT ID“ on the customer, wait for the notice that the confirmation has finished, and submit again. If a confirmation of the day of the supply lies outside Steuerbote, give it in „Reason for Releasing the VAT ID“."
		).format(text),
		title=title,
	)


def invoice_kennzahlen(doc) -> tuple[str, ...]:
	"""Kz 41, 42 and 21 the income accounts of the invoice feed by the VAT Return Mapping of its company."""
	accounts = sorted({item.income_account for item in doc.get("items") or () if item.get("income_account")})
	if not accounts:
		return ()
	rules = frappe.get_all(
		"VAT Return Mapping Rule",
		filters={"parent": doc.company, "parenttype": "VAT Return Mapping"},
		fields=["account_number", "kennzahl", "also_kennzahl"],
	)
	numbers = frappe.get_all("Account", filters={"name": ["in", accounts]}, pluck="account_number")
	return partners.invoice_kennzahlen(
		numbers,
		[
			MappingRule(row.account_number, row.kennzahl, row.also_kennzahl or None)
			for row in rules
			if row.account_number and row.kennzahl
		],
	)


def finding_text(finding: Finding, vat_id: str | None, customer: str, answer: Answer | None) -> str:
	"""The finding in the language of the user."""
	kennzahlen = ", ".join(finding.kennzahlen)
	number = escape_html(vatid.normalize(vat_id) if vat_id else "")
	customer = escape_html(customer or "")
	subject = _("The USt-IdNr. {0} of the customer {1} (Kz {2})").format(number, customer, kennzahlen)
	match finding.problem:
		case Problem.NO_VAT_ID:
			return _("The invoice goes to Kz {0}, but the customer {1} has no USt-IdNr.").format(
				kennzahlen, customer
			)
		case Problem.GERMAN:
			return _("{0} is German; Kz {1} needs one that another member state issued.").format(
				subject, kennzahlen
			)
		case Problem.NOT_CONFIRMABLE | Problem.MALFORMED:
			return _("{0} cannot be confirmed: {1}").format(
				subject, escape_html(partners.reason(vat_id) or "")
			)
		case Problem.UNCONFIRMED:
			return _("{0} has no confirmation.").format(subject)
		case Problem.NO_ANSWER:
			return _("{0} has no confirmation: no query about it was answered.").format(subject)
		case Problem.INVALID:
			return _("{0} is invalid by the confirmation of {1}.").format(
				subject, formatdate(answer.asked_on)
			)
		case Problem.STALE:
			return _(
				"{0} was last confirmed on {1}, {2} days before the posting date; the settings allow {3}."
			).format(subject, formatdate(answer.asked_on), finding.age, finding.max_age)
	return _(
		"{0} was confirmed without name and address; for a service the qualified confirmation counts (UStAE 3a.2 Abs. 9)."
	).format(subject)


# The forms of the partners


def customer_dashboard(data: dict) -> dict:
	"""override_doctype_dashboards: the confirmations of a customer under its connections."""
	return _with_confirmations(data, CUSTOMER)


def supplier_dashboard(data: dict) -> dict:
	"""override_doctype_dashboards: the confirmations of a supplier under its connections."""
	return _with_confirmations(data, SUPPLIER)


def _with_confirmations(data: dict, party_type: str) -> dict:
	data.setdefault("non_standard_fieldnames", {})[CONFIRMATION] = "party"
	data.setdefault("dynamic_links", {}).setdefault("party", [party_type, "party_type"])
	data.setdefault("transactions", []).append({"label": _("Tax"), "items": [CONFIRMATION]})
	return data


@frappe.whitelist()
def vat_id_state(party_type: str, party: str) -> dict:
	"""For the form of a partner: the kind of its number and, per company that confirms it, where its confirmation
	stands, with the day and the record of the latest answer."""
	if party_type not in PARTY_TYPES:
		frappe.throw(_("Only the USt-IdNr. of a customer or a supplier is confirmed here."))
	frappe.has_permission(party_type, "read", party, throw=True)
	tax_id = frappe.db.get_value(party_type, party, "tax_id")
	number_kind = partners.kind(tax_id)
	has_details = party_details(party_type, party) is not None
	rows = []
	if number_kind.checked(german=True):
		number = vatid.normalize(tax_id)
		for policy in companies_for(party_type, party, MANUAL, number_kind):
			fact = known(policy.company, [number]).get(number, Known())
			standing = partners.standing(
				number_kind,
				fact.answer,
				fact.asked,
				getdate(),
				policy.max_age,
				has_details,
				german=policy.german,
			)
			rows.append(
				{
					"company": policy.company,
					"standing": standing.value if standing else None,
					"standing_label": _(standing.value) if standing else "",
					"asked_on": fact.answer.asked_on if fact.answer else None,
					"record": fact.record,
					"automatic": policy.on_change or policy.renewal,
				}
			)
	return {
		"kind": number_kind.value,
		"sent": bool(rows),
		"problem": partners.reason(tax_id) if number_kind in (Kind.NOT_CONFIRMABLE, Kind.MALFORMED) else None,
		"has_details": has_details and number_kind is Kind.CONFIRMABLE,
		"companies": rows,
		"can_ask": bool(rows) and may_ask(party_type, party),
		"queued": is_job_enqueued(party_job_id(party_type, party)),
	}


def worklist(company: str, party_types: Iterable[str] = PARTY_TYPES, today: date | None = None) -> list[dict]:
	"""The partners of the company whose confirmation is not current, for the report: per partner its number, where
	its confirmation stands, and its latest answer."""
	policy = company_policy(company)
	if policy is None:
		return []
	today = today or getdate()
	rows = []
	for party_type, party, tax_id in partners_of(replace(policy, suppliers=SUPPLIER in party_types)):
		if party_type not in party_types:
			continue
		number_kind = partners.kind(tax_id)
		number = vatid.normalize(tax_id)
		fact = known(company, [number]).get(number, Known()) if number else Known()
		has_details = party_details(party_type, party) is not None
		standing = partners.standing(
			number_kind, fact.answer, fact.asked, today, policy.max_age, has_details, german=policy.german
		)
		if standing is None or not standing.work:
			continue
		rows.append(
			{
				"party_type": party_type,
				"party": party,
				"tax_id": tax_id,
				"standing": standing,
				"answer": fact.answer,
				"record": fact.record,
				"age": partners.age(fact.answer, today) if fact.answer else None,
				"problem": partners.reason(tax_id)
				if standing in (Standing.NOT_CONFIRMABLE, Standing.MALFORMED)
				else None,
			}
		)
	return rows


def _clock() -> datetime:
	return datetime.now(UTC)
