"""Compute the fields of the Umsatzsteuererklärung from the ledger of the year.

The input is the general ledger of the year as the Voranmeldung reads it (steuerbote/ustva/calculation.py): one
line per posting and account, without cancelled entries, opening and closing entries, and the entries that clear
the tax accounts against the tax office. The split (steuerbote/ustjahr/split.py) names the line each account feeds.

calculate() leaves the core of the Voranmeldung as it is and runs it in two ways:

1. Once over all lines of the year: the Verprobung, voucher by voucher, and the watched accounts of a year.
2. Once per group of lines whose accounts feed the same line. The amount of the Kennzahl of the group is the exact
   amount of its line. The tax that the rules of the group derive per voucher, for a base with a tax Kennzahl of its
   own such as Kz 46 and 47, is the amount of the tax field of the line, rounded per voucher as in the Voranmeldung.
   The amount of an informational Kennzahl, such as the Kz 50 of a bad debt, goes to the line of that Kennzahl. No
   Kennzahl with a tax Kennzahl of its own splits, so the vouchers round their taxes as in the Voranmeldung, and the
   lines of every Kennzahl add up to its amount over the year.

A base the Voranmeldung derives for a voucher that books the tax of a Verprobung but none of its bases (derived_base
of the mapping) has no account the split could assign. The run over the year derives it as each Voranmeldung does,
and it goes to the default line of its Kennzahl, its tax, rounded per voucher, to the default line of the tax
Kennzahl. A base of § 13b UStG goes to Kz 46 or 84 by the supplier of its voucher, as in the Voranmeldung
(steuerbote/ustva/residence.py), when the caller gives what it knows of the vouchers.

The accounts only the annual return reads add their balance, and the lines by hand their amount.

The form takes the bases in whole euros and the taxes in cents: „Tragen Sie bei den Bemessungsgrundlagen bitte nur
Beträge in vollen Euro ein; bei den Steuer- und Vorsteuerbeträgen ist dagegen stets auch die Eintragung von
Centbeträgen erforderlich“ (USt 2 E 2026, „So werden die Vordrucke ausgefüllt“). A base drops its cents
(to_full_euros), as in the Voranmeldung, but of the exact amount of the year and never as a sum of rounded months.

The tax of a rate line (Kz 177, 178, 179, 275, 195, 196, 781, 793 and the tax of Kz 310) is the rate times the exact
annual base, rounded half up (tax_from_base). ERiC refuses a tax more than one euro away from the rate times the
base as filed in whole euros (rules 30639 to 30644, 30656, 30658 and 30012, with „UngleichMitToleranz1“, true
„falls die beiden verglichenen Werte ungleich mit einer Toleranz von ... 1 sind“, Zusatzinformationen zur
Plausibilitätsprüfung, Kap. 4.5). This
tax is at most 0.19 euros away. The taxes of twelve Voranmeldungen are not: twelve months whose bases end in 99
cents drop 99 cents of base each, and their taxes miss 19 % of the base of the year by 2.09 euros. That the
Finanzverwaltung computes the tax of the annual return so is unverified; the research recommends it as the closest
to § 12 Absatz 1 UStG, and the tests pin it.

entries() turns the amounts of the form, after the corrections of the company, into the amounts the return files:

- A zero is left out, but a base and its tax go together as soon as one of them is not zero, since ERiC takes them
  only together (FelderNichtGemeinsamAngegeben, rules 30649 to 30655 and the like).
- A sum of the form is filed when one of its parts is, as zero too, and it is the sum of its parts as filed (rules
  30314, 30364 and 30900 for line 41, and so on).
- Kz 816, line 125 and Kz 820 are always filed (rules 30070, 30915 and 30620).
- A year without any amount files Kz 177 = 0 with its tax: rule 30449 wants an amount of the form, and the research
  suggests this one, unverified.

Messages are English templates with positional placeholders, as in the other cores.
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from steuerbote.ustjahr.form import KZ_816, KZ_820, SOLL, Catalogue, Field, Finding, Severity, Source
from steuerbote.ustjahr.split import How, Split
from steuerbote.ustva.calculation import (
	TOLERANCE_PER_VOUCHER,
	AccountBalance,
	CheckResult,
	LedgerLine,
	UstvaResult,
	require_cents,
)
from steuerbote.ustva.calculation import calculate as calculate_ustva
from steuerbote.ustva.kennzahlen import BALANCE_KENNZAHL
from steuerbote.ustva.residence import Voucher
from steuerbote.ustva.rounding import HUNDRED, ZERO, require_decimal, tax_from_base, to_cents, to_full_euros

DECEMBER = 12
LAST_OF_DECEMBER = 31
# Kz 177 and its tax, for a year without any amount (rule 30449).
NIL_BASE = "E3003303"
NIL_TAX = "E3003304"
NACHSTEUER_KENNZAHL = "65"
# Kz 319, the Nachsteuer wegen Steuersatzänderung, and Kz 317, the Steuer infolge des Wechsels der Besteuerungsform.
NACHSTEUER_LINE = "E3005901"
CHANGE_OF_TAXATION_LINE = "E3102901"
NACHSTEUER_CODE = "NACHSTEUER-ZEILE"
FILED_ALWAYS = frozenset({KZ_816, SOLL, KZ_820})

MANUAL_WITHOUT_REASON = "The line by hand for field {0} needs a reason."
MANUAL_NOT_FED = (
	"No line by hand can give field {0}: the form computes it, the company states it, or Steuerbote does not "
	"file it."
)
MANUAL_NO_PARAGRAPH = "Field {0} names no paragraph, so its line by hand gives none."
NOT_AN_INPUT = (
	"Field {0} takes no amount of its own: the form computes it, the company states it, or Steuerbote does not "
	"file it."
)
NOT_WHOLE_EUROS = "Field {0} takes whole euros, not {1}."
NOT_CENTS = "Field {0} takes euros and cents, not {1}."
NACHSTEUER = (
	"The Nachsteuer of account {0} goes into Kz 319 (line 40), the Nachsteuer wegen Steuersatzänderung. Steuer "
	"infolge des Wechsels der Besteuerungsform belongs in Kz 317 (line 39): give the mapping rule that annual field "
	"if it applies."
)
MESSAGES = (
	MANUAL_WITHOUT_REASON,
	MANUAL_NOT_FED,
	MANUAL_NO_PARAGRAPH,
	NOT_AN_INPUT,
	NOT_WHOLE_EUROS,
	NOT_CENTS,
	NACHSTEUER,
)


class CalculationError(ValueError):
	"""A line by hand or an amount of the form cannot be filed; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


@dataclass(frozen=True, slots=True)
class ManualLine:
	"""An amount by hand for a field the ledger feeds, with its reason, and the paragraph of lines 46, 52 and 54.

	A correction under § 15a UStG that the books do not hold is one: up to 6,000 euros per Wirtschaftsgut and year it
	is made „erst im Rahmen der Steuerfestsetzung für den Besteuerungszeitraum“ (§ 44 Absatz 3 Satz 1 UStDV).
	"""

	field: str
	amount: Decimal
	reason: str
	paragraph: str | None = None

	def __post_init__(self) -> None:
		require_cents(self.amount)
		if not isinstance(self.reason, str) or not self.reason.strip():
			raise CalculationError(MANUAL_WITHOUT_REASON, self.field)


@dataclass(frozen=True, slots=True)
class FieldValue:
	"""The amount of a field: what the mapped accounts give (``ledger``), what the accounts only the annual return
	reads give (``annual_only``) and the lines by hand (``manual``), each exact, and the amount the form takes.

	For a rate line the three parts are the rate times those of its base, and ``form`` the tax of the exact base.
	"""

	field: str
	ledger: Decimal
	annual_only: Decimal
	manual: Decimal
	form: Decimal

	@property
	def amount(self) -> Decimal:
		return self.ledger + self.annual_only + self.manual


@dataclass(frozen=True, slots=True)
class AnnualResult:
	"""The fields of the year with an amount, in the order of the form, and what the run over the year found.

	``ustva`` is the result of the core of the Voranmeldung over the year, with the Verprobung and the watched
	accounts. ``unmapped`` names the accounts watched at the blocking level with a balance, but for those the annual
	return reads itself. ``paragraphs`` gives, by text field of lines 46, 52 and 54, the paragraphs of the accounts
	with a balance on its line and of the lines by hand, each once. ``findings`` are the hints of the computation.
	"""

	year: int
	values: ReadOnlyMapping[str, FieldValue]
	ustva: UstvaResult
	unmapped: tuple[str, ...]
	paragraphs: ReadOnlyMapping[str, tuple[str, ...]]
	findings: tuple[Finding, ...]
	manual: tuple[ManualLine, ...]

	@property
	def checks(self) -> tuple[CheckResult, ...]:
		return self.ustva.checks

	@property
	def hinted(self) -> tuple[AccountBalance, ...]:
		return self.ustva.hinted

	@property
	def ready(self) -> bool:
		"""Every Verprobung passes and no account watched at the blocking level has a balance."""
		return not self.unmapped and all(check.passed for check in self.checks)

	@property
	def reported(self) -> ReadOnlyMapping[str, Decimal]:
		"""The amount of the form of each field, what entries() takes before the corrections of the company."""
		return MappingProxyType({element: value.form for element, value in self.values.items()})


def calculate(
	lines: Iterable[LedgerLine],
	split: Split,
	manual: Iterable[ManualLine] = (),
	tolerance: Decimal = TOLERANCE_PER_VOUCHER,
	vouchers: ReadOnlyMapping[str, Voucher] | None = None,
) -> AnnualResult:
	"""The fields of the annual return from the ledger lines of the year, the split and the lines by hand.

	``tolerance`` is how far the booked tax of a voucher may differ from the tax of its bases in the Verprobung
	(steuerbote/ustva/calculation.py). ``vouchers`` holds what the caller knows of the suppliers of the vouchers of
	sections C and D, so that a derived base of § 13b UStG goes to Kz 46 or 84 as in the Voranmeldung.
	"""
	lines = tuple(lines)
	manual = tuple(manual)
	catalogue = split.catalogue
	sides = {rule.account_number: rule.side for rule in split.mapping.rules}
	ledger: dict[str, Decimal] = {}
	annual_only: dict[str, Decimal] = {}
	by_hand: dict[str, Decimal] = {}
	balances: dict[str, Decimal] = {}
	groups: dict[str, list[LedgerLine]] = {}
	kennzahlen: dict[str, str | None] = {}
	for line in lines:
		assignment = split.assignment(line.account_number)
		if assignment is None:
			continue
		if assignment.how is How.ANNUAL:
			balance = line.balance(assignment.side)
			_add(annual_only, assignment.field, balance)
		else:
			balance = line.balance(sides[line.account_number])
			groups.setdefault(assignment.field, []).append(line)
			kennzahlen[assignment.field] = assignment.kennzahl
		_add(balances, line.account_number, balance)
	for element, group in groups.items():
		run = calculate_ustva(group, split.mapping, tolerance=tolerance)
		_add_run(ledger, split, _targets(split, element, kennzahlen[element]), run)
	for line_by_hand in manual:
		_add(by_hand, _manual_field(catalogue, line_by_hand).element, line_by_hand.amount)
	year = calculate_ustva(lines, split.mapping, tolerance=tolerance, vouchers=vouchers)
	_add_derived(ledger, split, year)
	return AnnualResult(
		year=catalogue.year,
		values=_values(catalogue, ledger, annual_only, by_hand),
		ustva=year,
		unmapped=tuple(account for account in year.unmapped if split.assignment(account) is None),
		paragraphs=_paragraphs(catalogue, split, balances, manual),
		findings=_nachsteuer(split, balances),
		manual=manual,
	)


def entries(
	catalogue: Catalogue, values: ReadOnlyMapping[str, Decimal], soll: Decimal
) -> ReadOnlyMapping[str, Decimal]:
	"""The amounts the return files, by Feldkennung in the order of the form.

	``values`` are the amounts of the form of the fields the ledger feeds and of the rate lines, after the
	corrections of the company; ``soll`` is the Vorauszahlungssoll of line 125 (steuerbote/ustjahr/soll.py).
	"""
	given: dict[str, Decimal] = {}
	for element, amount in values.items():
		field = _input(catalogue, element)
		_require_format(field, amount)
		if amount:
			given[element] = amount
	_require_format(catalogue.field(SOLL), soll)
	for field in catalogue.fields:
		if field.tax is not None and (field.element in given or field.tax in given):
			given.setdefault(field.element, ZERO)
			given.setdefault(field.tax, ZERO)
	if not given:
		given = {NIL_BASE: ZERO, NIL_TAX: ZERO}
	filed: dict[str, Decimal] = {}
	for field in catalogue.fields:
		if field.element in given:
			filed[field.element] = given[field.element]
		elif field.element == SOLL:
			filed[SOLL] = soll
		elif field.parts and (field.element in FILED_ALWAYS or any(part in filed for part, _ in field.parts)):
			filed[field.element] = sum((sign * filed.get(part, ZERO) for part, sign in field.parts), ZERO)
	return MappingProxyType(filed)


def business_period(year: int, began: date | None) -> tuple[date, date] | None:
	"""Lines 19 and 20, „Dauer der Unternehmereigenschaft (falls nicht vom 1. Januar bis zum 31. Dezember 2026)“: the
	part of the year from the day a company began, if it began during the year.

	§ 16 Absatz 3 UStG: „Hat der Unternehmer seine gewerbliche oder berufliche Tätigkeit nur in einem Teil des
	Kalenderjahres ausgeübt, so tritt dieser Teil an die Stelle des Kalenderjahres.“ Steuerbote files no cessation
	during the year, so the part ends on 31 December.
	"""
	if began is None or began <= date(year, 1, 1):
		return None
	if began.year > year:
		raise ValueError(f"the company began on {began.isoformat()}, after {year}")
	return began, date(year, DECEMBER, LAST_OF_DECEMBER)


def _add(amounts: dict[str, Decimal], key: str, amount: Decimal) -> None:
	amounts[key] = amounts.get(key, ZERO) + amount


def _targets(split: Split, element: str, kennzahl: str | None) -> dict[str | None, Field]:
	"""Where the amounts of the run of a line go: the amount of its Kennzahl to the line, and the tax its rules
	derive to the tax of the line."""
	field = split.catalogue.field(element)
	targets: dict[str | None, Field] = {kennzahl: field}
	tax_kennzahl = split.mapping.catalogue[field.ustva].tax_kennzahl
	if tax_kennzahl is not None and field.tax is not None:
		targets[tax_kennzahl] = split.catalogue.field(field.tax)
	return targets


def _add_run(
	amounts: dict[str, Decimal], split: Split, targets: dict[str | None, Field], run: UstvaResult
) -> None:
	"""The amounts of the run of one line; an informational Kennzahl, such as Kz 50, goes to its default line."""
	for value in run.values.values():
		if value.kennzahl == BALANCE_KENNZAHL:
			continue
		target = targets.get(value.kennzahl)
		if target is None:
			lines = split.catalogue.children(value.kennzahl)
			target = next(line for line in lines if line.default or len(lines) == 1)
		_add(amounts, target.element, target.sign * value.amount)


def _add_derived(amounts: dict[str, Decimal], split: Split, year: UstvaResult) -> None:
	"""The bases the run over the year derives, and their tax, on the default lines of their Kennzahlen."""
	catalogue = split.catalogue
	for derived in year.derived:
		_add_to_line(amounts, catalogue, derived.kennzahl, derived.base)
		tax_kennzahl = split.mapping.catalogue[derived.kennzahl].tax_kennzahl
		if tax_kennzahl is not None:
			_add_to_line(amounts, catalogue, tax_kennzahl, tax_from_base(derived.base, derived.rate))


def _add_to_line(amounts: dict[str, Decimal], catalogue: Catalogue, kennzahl: str, amount: Decimal) -> None:
	lines = catalogue.children(kennzahl)
	line = next(line for line in lines if line.default or len(lines) == 1)
	_add(amounts, line.element, line.sign * amount)


def _manual_field(catalogue: Catalogue, line: ManualLine) -> Field:
	try:
		field = catalogue.field(line.field)
	except KeyError:
		raise CalculationError(MANUAL_NOT_FED, line.field) from None
	if not field.fed:
		raise CalculationError(MANUAL_NOT_FED, line.field)
	if line.paragraph is not None and field.paragraph is None:
		raise CalculationError(MANUAL_NO_PARAGRAPH, line.field)
	return field


def _values(
	catalogue: Catalogue,
	ledger: dict[str, Decimal],
	annual_only: dict[str, Decimal],
	by_hand: dict[str, Decimal],
) -> MappingProxyType[str, FieldValue]:
	values: dict[str, FieldValue] = {}
	for field in catalogue.fields:
		if field.rate is not None:
			base = values.get(field.base)
			if base is not None:
				values[field.element] = _rate_value(field, field.rate, base)
			continue
		parts = (
			ledger.get(field.element, ZERO),
			annual_only.get(field.element, ZERO),
			by_hand.get(field.element, ZERO),
		)
		if any(parts):
			amount = sum(parts, ZERO)
			form = to_full_euros(amount) if field.format.whole_euros else to_cents(amount)
			values[field.element] = FieldValue(field.element, *parts, form)
	return MappingProxyType(values)


def _rate_value(field: Field, rate: Decimal, base: FieldValue) -> FieldValue:
	return FieldValue(
		field.element,
		base.ledger * rate / HUNDRED,
		base.annual_only * rate / HUNDRED,
		base.manual * rate / HUNDRED,
		tax_from_base(base.amount, rate),
	)


def _paragraphs(
	catalogue: Catalogue, split: Split, balances: dict[str, Decimal], manual: tuple[ManualLine, ...]
) -> MappingProxyType[str, tuple[str, ...]]:
	found: dict[str, list[str]] = {}
	named = [
		(assignment.field, assignment.paragraph)
		for assignment in split.assignments.values()
		if balances.get(assignment.account_number)
	]
	named += [(line.field, line.paragraph) for line in manual]
	for element, paragraph in named:
		text = catalogue.field(element).paragraph
		if paragraph is not None and text is not None and paragraph not in found.setdefault(text, []):
			found[text].append(paragraph)
	return MappingProxyType({text: tuple(paragraphs) for text, paragraphs in found.items()})


def _nachsteuer(split: Split, balances: dict[str, Decimal]) -> tuple[Finding, ...]:
	"""A hint for the accounts of Kz 65 that went into Kz 319 without a choice of the company."""
	accounts = [
		assignment.account_number
		for assignment in split.assignments.values()
		if assignment.kennzahl == NACHSTEUER_KENNZAHL
		and assignment.field == NACHSTEUER_LINE
		and assignment.how is not How.RULE
		and balances.get(assignment.account_number)
	]
	if not accounts:
		return ()
	return (
		Finding(
			NACHSTEUER_CODE,
			Severity.HINT,
			NACHSTEUER,
			(", ".join(accounts),),
			(NACHSTEUER_LINE, CHANGE_OF_TAXATION_LINE),
		),
	)


def _input(catalogue: Catalogue, element: str) -> Field:
	"""A field that takes an amount of its own: one the ledger feeds, or a rate line of such a base."""
	try:
		field = catalogue.field(element)
	except KeyError:
		raise CalculationError(NOT_AN_INPUT, element) from None
	fed = field.fed or (field.source is Source.RATE and catalogue.field(field.base).fed)
	if not fed:
		raise CalculationError(NOT_AN_INPUT, element)
	return field


def _require_format(field: Field, amount: Decimal) -> None:
	require_decimal(amount)
	if field.format.whole_euros:
		if not amount.is_finite() or amount != to_full_euros(amount):
			raise CalculationError(NOT_WHOLE_EUROS, field.element, format(amount, "f"))
	elif not amount.is_finite() or amount != to_cents(amount):
		raise CalculationError(NOT_CENTS, field.element, format(amount, "f"))
