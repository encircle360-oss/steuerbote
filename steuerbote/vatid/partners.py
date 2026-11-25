"""The USt-IdNrn. of business partners: which numbers the BZSt confirms, whether a partner's confirmation is current,
when the daily renewal asks again, and what a Sales Invoice behind Kz 41, 42 or 21 needs before it is submitted.
Pure Python; the Frappe layer reads the partners and the VAT ID Confirmation records and passes their facts in.

The law asks for the valid USt-IdNr. at the time of the supply: the customer of an innergemeinschaftliche Lieferung
„hat gegenüber dem Unternehmer eine ihm von einem anderen Mitgliedstaat erteilte gültige
Umsatzsteuer-Identifikationsnummer verwendet“ (§ 6a Abs. 1 Satz 1 Nr. 4 UStG), and a confirmation „zu einem
späteren Zeitpunkt als dem des Umsatzes“ does not show the care of § 6a Abs. 4 UStG (UStAE 6a.8 Abs. 6 Satz 1). For
a sonstige Leistung to a business in another member state the supplier may rely on the USt-IdNr. the customer uses
once he has had „die Gültigkeit einer USt-IdNr. … sowie den Namen und die Anschrift der Person, der diese Nummer
erteilt wurde, durch das BZSt bestätigen“ lassen (UStAE 3a.2 Abs. 9 Satz 5): the qualified confirmation. So
Steuerbote confirms a partner's number when the partner is made or changed, renews the confirmation every day it
is due, and checks a Sales Invoice behind Kz 41, 42 or 21 on submit.

No source names an age: the BZSt confirms for the moment of the query, „Bestätigungen für zurückliegende Zeitpunkte
oder Zeiträume sind nicht möglich.“ (BZSt, "Fragen und Antworten" zur USt-IdNr.). The settings give the age a
confirmation may have, per invoice for goods and for services; an answer after the reference day counts as new.

The services set the limits of the renewal. The BZSt: „Es werden nur Einzelabfragen verarbeitet. Diese werden
nacheinander abgearbeitet.“, „Bitte sehen Sie von einem unmittelbaren Wiederholen der Anfrage ab.“, and „Im
Zeitraum von 23:00 Uhr bis 05:00 Uhr können Wartungsarbeiten durchgeführt werden“ (BZSt, Bestätigung ausländischer
USt-IdNrn). VIES, which answers only when the BZSt cannot, names as abuse „Multiple validation of the same VAT
number per day except for availability tests“ and „High traffic of invalid VAT numbers“ (VIES, FAQ). So the renewal
asks one number after the other with a pause, never about a number twice a day nor about a number the BZSt cannot
confirm, about an invalid number no more often than about a valid one, only between five in the morning and eleven
at night in Germany, at most MAX_PER_RUN numbers a day, and stops at the first service that cannot answer.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from zoneinfo import ZoneInfo

from steuerbote.vatid.result import Details, Outcome
from steuerbote.vatid.ustid import COUNTRY_CODE, MEMBER_STATES, is_german, normalize, problem

GOODS = ("41", "42")
"""Kz 41 and 42: innergemeinschaftliche Lieferungen and Lieferungen des ersten Abnehmers bei Dreiecksgeschäften."""
SERVICES = ("21",)
"""Kz 21: sonstige Leistungen nach § 3a Abs. 2 UStG in another member state."""
KENNZAHLEN = (*GOODS, *SERVICES)
MAX_PER_RUN = 25
"""The numbers one daily run asks about at most; a backlog is worked off over the following days."""
PAUSE_SECONDS = 2
"""The pause between two confirmations of a run, so that the queries of a run never overlap."""
GERMAN_TIME = ZoneInfo("Europe/Berlin")
SERVICE_HOURS = (time(5), time(23))
"""When the BZSt answers outside its maintenance, by German time."""


class Kind(Enum):
	"""What the USt-IdNr. field of a partner holds."""

	MISSING = "missing"
	CONFIRMABLE = "confirmable"
	"""A plausible USt-IdNr. of another member state, which the BZSt confirms."""
	GERMAN = "german"
	"""A German USt-IdNr., which the BZSt does not confirm (§ 18e Nr. 1 UStG)."""
	NOT_CONFIRMABLE = "not_confirmable"
	"""A number with a country code the BZSt does not confirm: GB, GR, or a country outside the EU."""
	MALFORMED = "malformed"
	"""No country code, the wrong length, or a German number that is not DE and nine digits."""

	@property
	def sent(self) -> bool:
		"""Whether Steuerbote sends a number of this kind anywhere."""
		return self is Kind.CONFIRMABLE


def kind(value: str | None) -> Kind:
	"""What kind of number the value is, written in any way ustid.normalize reads."""
	number = normalize(value) if isinstance(value, str) else ""
	if not number:
		return Kind.MISSING
	if is_german(number):
		return Kind.GERMAN
	if problem(number) is None:
		return Kind.CONFIRMABLE
	code = number[:2]
	if not COUNTRY_CODE.fullmatch(code) or code in MEMBER_STATES or code == "DE":
		return Kind.MALFORMED
	return Kind.NOT_CONFIRMABLE


@dataclass(frozen=True, slots=True)
class Answer:
	"""The latest definite answer about a number for a company: the day of its query, valid or invalid, whether the
	BZSt compared name and address, and whether it found one of them different (B)."""

	asked_on: date
	outcome: Outcome
	qualified: bool = False
	differs: bool = False

	def __post_init__(self) -> None:
		if self.outcome is Outcome.UNKNOWN:
			raise ValueError("an answer is valid or invalid; a query without one has no answer")


def age(answer: Answer, reference: date) -> int:
	"""The days from the query of the answer to the reference day; an answer after that day counts as new."""
	return max(0, (reference - answer.asked_on).days)


class Standing(Enum):
	"""Where the confirmation of a partner's number stands, as the worklist shows it."""

	CURRENT = "Current"
	MISSING = "Missing"
	EXPIRED = "Expired"
	INVALID = "Invalid"
	NO_ANSWER = "No Answer"
	NOT_CONFIRMABLE = "Not Confirmable"
	MALFORMED = "Malformed"
	ADDRESS_MISSING = "Address Missing"
	"""Valid, but only simple: the partner lacks the name or the town the qualified query needs."""
	NOT_QUALIFIED = "Not Qualified"
	"""Valid, but only simple although name and town are known now."""
	DETAILS_DIFFER = "Details Differ"
	"""Valid, but the member state has another name or address registered."""

	@property
	def work(self) -> bool:
		"""Whether the partner belongs on the worklist."""
		return self is not Standing.CURRENT


def standing(
	number: Kind, answer: Answer | None, asked: bool, reference: date, max_age: int, has_details: bool
) -> Standing | None:
	"""Where the confirmation of a partner's number stands on the reference day; None for a partner whose number
	needs none, because it has none or a German one. ``asked`` says whether any query about the number was made,
	``has_details`` whether the partner has the name and town of the qualified query."""
	if number in (Kind.MISSING, Kind.GERMAN):
		return None
	if number is Kind.NOT_CONFIRMABLE:
		return Standing.NOT_CONFIRMABLE
	if number is Kind.MALFORMED:
		return Standing.MALFORMED
	if answer is None:
		return Standing.NO_ANSWER if asked else Standing.MISSING
	if answer.outcome is Outcome.INVALID:
		return Standing.INVALID
	if age(answer, reference) > max_age:
		return Standing.EXPIRED
	if not answer.qualified:
		return Standing.NOT_QUALIFIED if has_details else Standing.ADDRESS_MISSING
	if answer.differs:
		return Standing.DETAILS_DIFFER
	return Standing.CURRENT


@dataclass(frozen=True, slots=True)
class TodayQuery:
	"""A query about a number made today for a company: its outcome and the name and address it asked about."""

	outcome: Outcome
	details: Details | None


def covered_today(queries: Iterable[TodayQuery], details: Details | None) -> bool:
	"""Whether a query of today already answers the question: an invalid answer answers any, a valid one the simple
	question and the qualified one with the same name and address. A query without an answer answers nothing."""
	for query in queries:
		if query.outcome is Outcome.INVALID:
			return True
		if query.outcome is Outcome.VALID and (details is None or query.details == details):
			return True
	return False


def is_due(
	number: Kind,
	answer: Answer | None,
	last_query_on: date | None,
	today: date,
	max_age: int,
	has_details: bool,
) -> bool:
	"""Whether the renewal asks about the number today: a number the BZSt confirms, not asked about today, without an
	answer, with an answer as old as the settings allow or older, or with a simple answer although name and town are
	known now."""
	if not number.sent or last_query_on == today:
		return False
	if answer is None or age(answer, today) >= max_age:
		return True
	return answer.outcome is Outcome.VALID and not answer.qualified and has_details


@dataclass(frozen=True, slots=True)
class Candidate:
	"""A partner's number the renewal asks about, under a key of the Frappe layer, with its latest answer."""

	key: str
	answer: Answer | None


def renewal_order(candidates: Iterable[Candidate]) -> list[Candidate]:
	"""The numbers never answered first, then the oldest answers, each by key."""
	return sorted(
		candidates,
		key=lambda item: (
			item.answer is not None,
			item.answer.asked_on if item.answer else date.min,
			item.key,
		),
	)


class Asked(Enum):
	"""What came of the confirmation of one number."""

	ANSWERED = "answered"
	"""A record is stored, whatever it says."""
	UNAVAILABLE = "unavailable"
	"""The BZSt could not answer; the record is stored all the same."""
	FAILED = "failed"
	"""Steuerbote could not ask or store, such as for a partner deleted meanwhile; the run goes on."""


class Stop(Enum):
	UNAVAILABLE = "unavailable"
	OUTSIDE_HOURS = "outside_hours"
	LIMIT = "limit"


@dataclass(frozen=True, slots=True)
class RenewalRun:
	stored: tuple[str, ...]
	"""The keys whose confirmation is stored, also that of the service that could not answer."""
	failed: tuple[str, ...]
	stop: Stop | None


def renew(
	candidates: Sequence[Candidate],
	ask: Callable[[Candidate], Asked],
	pause: Callable[[], None],
	clock: Callable[[], datetime],
	limit: int = MAX_PER_RUN,
) -> RenewalRun:
	"""Ask about the candidates in their order, one after the other with a pause between, until the first service
	that cannot answer, the end of the hours of the services or the limit."""
	stored: list[str] = []
	failed: list[str] = []
	stop = None
	for index, candidate in enumerate(candidates):
		if index >= limit:
			stop = Stop.LIMIT
			break
		if not in_service_hours(clock()):
			stop = Stop.OUTSIDE_HOURS
			break
		if index:
			pause()
		outcome = ask(candidate)
		if outcome is Asked.FAILED:
			failed.append(candidate.key)
			continue
		stored.append(candidate.key)
		if outcome is Asked.UNAVAILABLE:
			stop = Stop.UNAVAILABLE
			break
	return RenewalRun(tuple(stored), tuple(failed), stop)


def in_service_hours(moment: datetime) -> bool:
	"""Whether the moment lies between five in the morning and eleven at night by German time."""
	if moment.tzinfo is None:
		raise ValueError("the moment needs a time zone")
	local = moment.astimezone(GERMAN_TIME).time()
	return SERVICE_HOURS[0] <= local < SERVICE_HOURS[1]


@dataclass(frozen=True, slots=True)
class MappingRule:
	"""A rule of the VAT Return Mapping: the Kennzahl an account feeds and the second one it may feed as well."""

	account_number: str
	kennzahl: str
	also_kennzahl: str | None = None


def invoice_kennzahlen(
	account_numbers: Iterable[str | None], rules: Iterable[MappingRule]
) -> tuple[str, ...]:
	"""Kz 41, 42 and 21 that the income accounts of an invoice feed by the mapping, in the order of the form.

	The Voranmeldung puts a Sales Invoice into a Kennzahl by the accounts it posts to and the mapping of the company,
	so the same rules tell before submit where the invoice will go."""
	accounts = {number for number in account_numbers if number}
	fed = {
		kennzahl
		for rule in rules
		if rule.account_number in accounts
		for kennzahl in (rule.kennzahl, rule.also_kennzahl)
		if kennzahl
	}
	return tuple(number for number in KENNZAHLEN if number in fed)


class Level(Enum):
	"""What submitting a Sales Invoice does with a finding."""

	BLOCK = "Block"
	WARN = "Warn"
	OFF = "Off"


@dataclass(frozen=True, slots=True)
class Policy:
	"""The level and the age in days a confirmation may have, for goods or for services."""

	level: Level
	max_age: int

	def __post_init__(self) -> None:
		if self.max_age < 0:
			raise ValueError(f"the age of a confirmation is a number of days from 0 on, not {self.max_age}")


class Problem(Enum):
	NO_VAT_ID = "no_vat_id"
	GERMAN = "german"
	NOT_CONFIRMABLE = "not_confirmable"
	MALFORMED = "malformed"
	UNCONFIRMED = "unconfirmed"
	NO_ANSWER = "no_answer"
	INVALID = "invalid"
	STALE = "stale"
	NOT_QUALIFIED = "not_qualified"


RELEASABLE = frozenset(
	{Problem.UNCONFIRMED, Problem.NO_ANSWER, Problem.INVALID, Problem.STALE, Problem.NOT_QUALIFIED}
)
"""What a written reason on the invoice releases, as a release of the number lifts an unconfirmed or invalid number on
a line of the Zusammenfassende Meldung (steuerbote.zm.lines.RELEASABLE): a confirmation may lie outside Steuerbote. A
missing, German, non-confirmable or malformed number is wrong on the invoice and has to be corrected there."""

KIND_PROBLEMS = {
	Kind.MISSING: Problem.NO_VAT_ID,
	Kind.GERMAN: Problem.GERMAN,
	Kind.NOT_CONFIRMABLE: Problem.NOT_CONFIRMABLE,
	Kind.MALFORMED: Problem.MALFORMED,
}


@dataclass(frozen=True, slots=True)
class Finding:
	"""What is missing for the invoice, the level of the policy it falls under, the Kennzahlen it concerns and, for an
	answer, its age and the age the policy allows."""

	problem: Problem
	level: Level
	kennzahlen: tuple[str, ...]
	age: int | None = None
	max_age: int | None = None

	@property
	def releasable(self) -> bool:
		"""Whether a written reason on the invoice lifts the finding."""
		return self.problem in RELEASABLE


def invoice_finding(
	kennzahlen: Sequence[str],
	number: Kind,
	answer: Answer | None,
	asked: bool,
	posting_date: date,
	goods: Policy,
	services: Policy,
) -> Finding | None:
	"""What the USt-IdNr. of the customer lacks for an invoice behind the Kennzahlen, None when nothing does.

	Goods need a valid confirmation within the age of their policy; services a valid qualified one within theirs. An
	invoice with goods and services is held to the goods first and then asked for the qualified confirmation."""
	found_goods = tuple(number_ for number_ in kennzahlen if number_ in GOODS)
	found_services = tuple(number_ for number_ in kennzahlen if number_ in SERVICES)
	if found_goods:
		finding = _finding(found_goods, number, answer, asked, posting_date, goods, qualified=False)
		if finding is not None or not found_services:
			return finding
	if found_services:
		return _finding(found_services, number, answer, asked, posting_date, services, qualified=True)
	return None


def _finding(
	kennzahlen: tuple[str, ...],
	number: Kind,
	answer: Answer | None,
	asked: bool,
	posting_date: date,
	policy: Policy,
	qualified: bool,
) -> Finding | None:
	if policy.level is Level.OFF:
		return None
	if number in KIND_PROBLEMS:
		return Finding(KIND_PROBLEMS[number], policy.level, kennzahlen)
	if answer is None:
		return Finding(Problem.NO_ANSWER if asked else Problem.UNCONFIRMED, policy.level, kennzahlen)
	days = age(answer, posting_date)
	if answer.outcome is Outcome.INVALID:
		problem_found = Problem.INVALID
	elif days > policy.max_age:
		problem_found = Problem.STALE
	elif qualified and not answer.qualified:
		problem_found = Problem.NOT_QUALIFIED
	else:
		return None
	return Finding(problem_found, policy.level, kennzahlen, days, policy.max_age)
