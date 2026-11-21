"""The deadlines of a company within a horizon, and whether each is filed.

A deadline is filed when a document of its period carries the filing mark, open while a document of it does not,
and missing without a document. The filing mark is the day the document was filed, which the caller reads from the
document: a VAT Return, a Recapitulative Statement and a VAT Return Extension are filed once they are submitted, or
sent through Steuerbote with an outcome that ELSTER accepted or that is unknown, even if they were cancelled or
discarded since (transmission.filings), and an extension cancelled for its correction stays filed with the
Finanzamt.

A Zusammenfassende Meldung is owed only for a Meldezeitraum with something to report: „Sog. „Nullmeldungen“ sind
nicht abzugeben“ (Anleitung zur ZM, III.1; steuerbote.zm.lines). Without a document the rules alone cannot tell,
so the caller decides from the ledger of the Meldezeitraum whether it is due.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from types import MappingProxyType

from steuerbote.deadlines.obligations import Kind, Obligation, obligations
from steuerbote.steuerbote.doctype.vat_return_settings import rules
from steuerbote.ustva.period import Period
from steuerbote.zm import rhythm as zm_rhythm
from steuerbote.zm.period import Kind as ReportingKind
from steuerbote.zm.period import ReportingPeriod

# The DocType that files each kind of deadline.
DOCUMENT_TYPES = MappingProxyType(
	{
		Kind.VORANMELDUNG: "VAT Return",
		Kind.ZUSAMMENFASSENDE_MELDUNG: "Recapitulative Statement",
		Kind.SONDERVORAUSZAHLUNG: "VAT Return Extension",
	}
)
KIND_ORDER = MappingProxyType({kind: index for index, kind in enumerate(Kind)})


class Status(Enum):
	"""Where a deadline stands. The names read the same in every language, like the status of a VAT Return."""

	FILED = "Abgegeben"
	OPEN = "Offen"
	MISSING = "Fehlt"


@dataclass(frozen=True, slots=True)
class CompanyRules:
	"""What the VAT Return Settings of a company say about its deadlines.

	``since`` is the day Steuerbote began to keep the filings of the company, the day its settings were made.
	Whether a deadline before it was met outside Steuerbote cannot be known here, so one without a document is
	left out once it is overdue.
	"""

	company: str
	period_rules: tuple[rules.PeriodRule, ...] = ()
	prepayments: tuple[rules.Prepayment, ...] = ()
	zm_rules: tuple[zm_rhythm.Rule, ...] = ()
	since: date | None = None

	def __post_init__(self) -> None:
		for name in ("period_rules", "prepayments", "zm_rules"):
			object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class Filing:
	"""A document of the company for the period of a deadline, and the day it was filed, None while it is not."""

	kind: Kind
	period: Period | ReportingPeriod | int
	name: str
	filed_on: date | None = None


@dataclass(frozen=True, slots=True)
class Deadline:
	"""A deadline of a company: what is due for which period and when, the document that files it or would, and
	its status. ``period`` is the Voranmeldungszeitraum, the Meldezeitraum or the year of the Sondervorauszahlung.
	"""

	kind: Kind
	company: str
	period_label: str
	due: date
	document_type: str
	document_name: str | None
	status: Status
	period: Period | ReportingPeriod | int

	def days_left(self, today: date) -> int:
		"""The days from ``today`` to the deadline, negative once it has passed."""
		return (self.due - today).days


def upcoming(
	company_rules: CompanyRules,
	filings: Iterable[Filing],
	today: date,
	horizon_days: int,
	holidays: Collection[date] = (),
	reportable: Callable[[zm_rhythm.Coverage], bool] | None = None,
) -> list[Deadline]:
	"""The deadlines of the company due on or before ``horizon_days`` days after ``today``, by due date.

	A deadline due from ``today`` on is listed whatever its status. An earlier one stays while it is not filed:
	always with a document, and without one if it fell due on or after ``company_rules.since``. ``filings`` lists
	the documents of the company, the latest first: the first one filed files its period, else the first one keeps
	it open. ``reportable`` tells for the coverage of a Meldezeitraum without a document whether it has anything
	to report; without it, every Meldezeitraum counts. Deadlines due on the same day follow the order of Kind.
	"""
	if not isinstance(horizon_days, int) or isinstance(horizon_days, bool) or horizon_days < 0:
		raise ValueError(f"the horizon is a whole number of days from 0 on, not {horizon_days!r}")
	until = today + timedelta(days=horizon_days)
	documents: dict[tuple[Kind, object], list[Filing]] = {}
	for filing in filings:
		documents.setdefault((filing.kind, filing.period), []).append(filing)
	found = []
	for owed in obligations(
		company_rules.period_rules, company_rules.prepayments, company_rules.zm_rules, until, holidays
	):
		status, name = _status(documents.get((owed.kind, owed.period), []))
		if owed.due < today and not _still_open(status, owed.due, company_rules.since):
			continue
		if status is Status.MISSING and not _owed_at_all(owed, reportable):
			continue
		found.append(
			Deadline(
				owed.kind,
				company_rules.company,
				owed.label,
				owed.due,
				DOCUMENT_TYPES[owed.kind],
				name,
				status,
				owed.period,
			)
		)
	return sorted(found, key=lambda item: (item.due, KIND_ORDER[item.kind]))


def new_document_values(deadline: Deadline) -> dict[str, str | int]:
	"""The fields a new document for the deadline starts with, as its form takes them."""
	values: dict[str, str | int] = {"company": deadline.company}
	period = deadline.period
	if isinstance(period, Period):
		values.update(year=period.year, rhythm=period.rhythm.value, period_index=period.index)
	elif isinstance(period, ReportingPeriod):
		values.update(year=period.year, period_kind=period.kind.value)
		if period.kind is ReportingKind.MONTH:
			values["period_index"] = period.first_month
		elif period.kind is not ReportingKind.YEAR:
			values["period_index"] = (period.first_month - 1) // 3 + 1
	else:
		values["year"] = period
	return values


def _status(documents: list[Filing]) -> tuple[Status, str | None]:
	filed = next((document for document in documents if document.filed_on is not None), None)
	if filed is not None:
		return Status.FILED, filed.name
	if documents:
		return Status.OPEN, documents[0].name
	return Status.MISSING, None


def _owed_at_all(owed: Obligation, reportable: Callable[[zm_rhythm.Coverage], bool] | None) -> bool:
	"""Whether a deadline without a document is owed: a Meldezeitraum only with something to report."""
	return owed.coverage is None or reportable is None or reportable(owed.coverage)


def _still_open(status: Status, due: date, since: date | None) -> bool:
	"""Whether an overdue deadline stays in the list."""
	if status is Status.OPEN:
		return True
	return status is Status.MISSING and (since is None or due >= since)
