"""Rules of the VAT Return Settings: Voranmeldungszeitraum per month, Dauerfristverlängerung per year.

§ 18 Absatz 2 UStG makes the Kalendervierteljahr or the Kalendermonat the Voranmeldungszeitraum, and lets
the Finanzamt exempt a company from the Voranmeldungen altogether. A company records each change as a
rule: from a year and month on, it files monthly, quarterly or not at all. A rule holds until the next
one starts, across years. A change takes effect with a Kalendervierteljahr, in month 1, 4, 7 or 10, so a
quarter never starts in its middle. The Finanzamt sets the Voranmeldungszeitraum, so a month before the
first rule has none, and asking for it is an error rather than a silent default.

The Dauerfristverlängerung moves the deadlines by one month (§ 46 UStDV). A company that files monthly
gets it only with a Sondervorauszahlung: „Die Fristverlängerung ist bei einem Unternehmer, der die
Voranmeldungen monatlich zu übermitteln hat, unter der Auflage zu gewähren, dass dieser eine
Sondervorauszahlung auf die Steuer eines jeden Kalenderjahres entrichtet“ (§ 47 Absatz 1 UStDV), so a
Sondervorauszahlung without the Dauerfristverlängerung is refused. Each year has its own row; a year
without one keeps the deadlines without the extension, which is the earlier of the two.

Messages are English templates with positional placeholders. SettingsError keeps the template and its
values apart, so the Frappe layer can translate the template before formatting it. This module is pure
Python and never imports Frappe.
"""

from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from steuerbote.ustva.period import Rhythm
from steuerbote.ustva.rounding import CENT, ZERO, require_decimal

QUARTER_START_MONTHS = (1, 4, 7, 10)

NOT_A_YEAR = "{0} is not a four-digit year."
NOT_A_FILING_PERIOD = "{0} is not a filing period: choose monthly, quarterly or none."
NOT_A_QUARTER_START = "The filing period of {0} can only change in month 1, 4, 7 or 10, not in month {1}."
DUPLICATE_RULE = "The filing period of {0} from month {1} is entered twice."
NO_VORANMELDUNG_DUE = "No Voranmeldung is due for month {1} of {0}."
NO_RULE_YET = (
	"No filing period is set for month {1} of {0}: enter the Voranmeldungszeitraum the Finanzamt set."
)
DUPLICATE_PREPAYMENT = "The Dauerfristverlängerung of {0} is entered twice."
NOT_IN_CENTS = "The Sondervorauszahlung of {0} must be an amount in cents, not {1}."
SONDERVORAUSZAHLUNG_WITHOUT_DAUERFRIST = (
	"The Sondervorauszahlung of {0} requires the Dauerfristverlängerung of that year."
)
MESSAGES = (
	NOT_A_YEAR,
	NOT_A_FILING_PERIOD,
	NOT_A_QUARTER_START,
	DUPLICATE_RULE,
	NO_VORANMELDUNG_DUE,
	NO_RULE_YET,
	DUPLICATE_PREPAYMENT,
	NOT_IN_CENTS,
	SONDERVORAUSZAHLUNG_WITHOUT_DAUERFRIST,
)


class SettingsError(ValueError):
	"""A rule of the settings is broken; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


class NoVoranmeldungError(SettingsError):
	"""The month falls under a rule that exempts the company from the Voranmeldungen."""


class FilingRhythm(Enum):
	"""The options of a rule: one of the two Voranmeldungszeiträume, or no Voranmeldung."""

	MONTHLY = "monthly"
	QUARTERLY = "quarterly"
	NONE = "none"


@dataclass(frozen=True, slots=True)
class PeriodRule:
	"""From ``valid_from_month`` of ``year`` on, the company files in ``rhythm``."""

	year: int
	rhythm: FilingRhythm
	valid_from_month: int = 1

	def __post_init__(self) -> None:
		_require_year(self.year)
		object.__setattr__(self, "rhythm", _filing_rhythm(self.rhythm))
		if not _is_int(self.valid_from_month) or self.valid_from_month not in QUARTER_START_MONTHS:
			raise SettingsError(NOT_A_QUARTER_START, self.year, self.valid_from_month)

	@property
	def start(self) -> tuple[int, int]:
		return (self.year, self.valid_from_month)


@dataclass(frozen=True, slots=True)
class Prepayment:
	"""The Dauerfristverlängerung of a year and the Sondervorauszahlung that comes with it."""

	year: int
	dauerfristverlaengerung: bool = False
	sondervorauszahlung: Decimal = ZERO

	def __post_init__(self) -> None:
		_require_year(self.year)
		if not isinstance(self.dauerfristverlaengerung, bool):
			raise TypeError(
				f"dauerfristverlaengerung must be a bool, not {type(self.dauerfristverlaengerung).__name__}"
			)
		amount = require_decimal(self.sondervorauszahlung)
		if not amount.is_finite() or amount != amount.quantize(CENT):
			raise SettingsError(NOT_IN_CENTS, self.year, amount)
		if amount and not self.dauerfristverlaengerung:
			raise SettingsError(SONDERVORAUSZAHLUNG_WITHOUT_DAUERFRIST, self.year)


def rhythm_for(rules: Iterable[PeriodRule], year: int, month: int) -> Rhythm:
	"""The Voranmeldungszeitraum of a month: that of the latest rule starting in or before it."""
	_require_year(year)
	if not _is_int(month) or not 1 <= month <= 12:
		raise ValueError(f"month must be between 1 and 12, not {month!r}")
	started = [rule for rule in rules if rule.start <= (year, month)]
	if not started:
		raise SettingsError(NO_RULE_YET, year, month)
	rule = max(started, key=lambda rule: rule.start)
	if rule.rhythm is FilingRhythm.NONE:
		raise NoVoranmeldungError(NO_VORANMELDUNG_DUE, year, month)
	return Rhythm(rule.rhythm.value)


def has_dauerfrist(prepayments: Iterable[Prepayment], year: int) -> bool:
	return any(prepayment.year == year and prepayment.dauerfristverlaengerung for prepayment in prepayments)


def sondervorauszahlung(prepayments: Iterable[Prepayment], year: int) -> Decimal:
	return next(
		(prepayment.sondervorauszahlung for prepayment in prepayments if prepayment.year == year), ZERO
	)


def check_period_rules(rules: Iterable[PeriodRule]) -> None:
	"""Two rules with the same start would leave the rhythm of their months to the order of the rows."""
	duplicate = _first_duplicate(rule.start for rule in rules)
	if duplicate is not None:
		raise SettingsError(DUPLICATE_RULE, *duplicate)


def check_prepayments(prepayments: Iterable[Prepayment]) -> None:
	duplicate = _first_duplicate(prepayment.year for prepayment in prepayments)
	if duplicate is not None:
		raise SettingsError(DUPLICATE_PREPAYMENT, duplicate)


def _filing_rhythm(value: FilingRhythm | str) -> FilingRhythm:
	with suppress(ValueError):
		return FilingRhythm(value)
	raise SettingsError(NOT_A_FILING_PERIOD, value)


def _require_year(year: object) -> None:
	if not _is_int(year) or not 1000 <= year <= 9999:
		raise SettingsError(NOT_A_YEAR, year)


def _is_int(value: object) -> bool:
	"""True is an int to Python, but neither a year nor a month."""
	return isinstance(value, int) and not isinstance(value, bool)


def _first_duplicate[T](keys: Iterable[T]) -> T | None:
	seen: set[T] = set()
	for key in keys:
		if key in seen:
			return key
		seen.add(key)
	return None
