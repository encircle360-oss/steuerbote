"""The rules of the Jahresdokumentation that Steuerbote checks itself, and its own checks of a return.

ERiC checks a filing against the rules of the Jahresdokumentation of its year (JD; Jahresdokumentation_E50_2026.ods,
sheet "USt2A - Regeln"), written in the rule language of the „ERiC Zusatzinformation zur Plausibilitätsprüfung“ of
the ERiC documentation 44.3.6.0, Kap. 4. Steuerbote checks 169 of the 175 rules of 2026 itself, so that a return
shows its findings before it goes to ERiC, and leaves to ERiC the six on Anlage UN and Anlage FV, which Steuerbote
does not file (LEFT_TO_ERIC).

check() takes the values the return files, by Feldkennung: the amounts of entries() in
steuerbote/ustjahr/calculation.py and the details of the company, a Decimal for an amount, True for a yes field or
a cross, a str for a text or a value of a list, a date, and a pair of dates for the spans of lines 19 and 20. A field
the values do not hold is not given („FeldNichtAngegeben“), and counts as zero in a sum, which is the „Summe aller
Werte der angegebenen Felder“ (Kap. 4.3.2).

Most rules come in a few shapes, each stating its condition in the words of the JD, which the tests compare with
the JD:

- Pattern: fields given or not, and amounts that are not zero („FeldAngegeben“, „FeldNichtAngegeben“,
  „MindestensEinFeldAngegeben“, „KeinFeldAngegeben“, „AlleFelderAngegeben“, „NichtAlleFelderOderKeinFeldAngegeben“
  and „KontextAngegeben“, Kap. 4.2.1).
- Together: fields filed together or not at all („FelderNichtGemeinsamAngegeben“), a base and its tax for instance.
- The three rules of each sum of the form (``parts`` of its field in steuerbote/ustjahr/form.py): the sum differs
  from its lines, it is missing although a line is given, or it is given although no line is; a sum of one line is a
  line brought forward. Kz 816 may differ from its lines by ten euros („UngleichMitToleranz10“).
- Rate: the tax of a base at 19 or 7 % within one euro („UngleichMitToleranz1“, true when the two amounts are more
  than one euro apart, Kap. 4.5).

The other rules, with dates, limits, sums of their own and alternatives („Oder“), are written out one by one with
their condition as the JD gives it. A finding has the severity of its rule, Fehler or Hinweis. The mandatory fields,
the sums, the pairs, the rate lines, the nil return, Kz 133, Kz 742, Kz 129, line 75 and the Kleinunternehmer have
messages of their own; the other rules name their code and their condition (RULE).

Steuerbote adds checks of its own, before the rules: an amount with cents where whole euros belong, a negative amount
in a field without sign (the Formatkennzeichen of the JD), more digits before the decimal comma than the „Format als
regulärer Ausdruck“ of the JD allows, a text longer than its „Max. Länge“, and an amount in lines 46, 52 and 54
without the paragraph its line names.

check() takes one value per field. Line 95 may repeat for up to 99 Grundstücke (``repeat`` in form.py); check() sees
the values of one, which no rule of the JD reads.
"""

from collections.abc import Callable, Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import cast

from steuerbote.ustjahr.form import (
	RATE_7,
	RATE_19,
	Catalogue,
	Field,
	Finding,
	Format,
	Part,
	Severity,
	catalogue_for,
)
from steuerbote.ustva.rounding import HUNDRED, ZERO, to_cents, to_full_euros

Values = ReadOnlyMapping[str, object]

MANDATORY = "{0} in line {1} is mandatory."
TOGETHER = "{0} and {1} go together: give both or neither."
SUM_DIFFERS = "{0} in line {1} does not follow from its lines: {2} instead of {3}."
SUM_TOLERANCE = "{0} in line {1} is more than 10 euros away from what its lines give: {2} instead of {3}."
SUM_MISSING = "{0} in line {1} is missing although one of its lines is given."
SUM_ALONE = "{0} in line {1} is given although none of its lines is."
RATE = "The tax {0} in line {1} is more than one euro away from {2} % of its base: {3} instead of about {4}."
RULE = "ERiC rule {0} applies: {1}."
NIL = (
	"The return fills none of the Kennzahlen the tax is calculated from; a year without amounts files Kz 177 with "
	"zero."
)
KZ_133 = (
	"Kz 133 says whether the tax was calculated nach vereinbarten or nach vereinnahmten Entgelten (§ 16 Absatz 1 "
	"Satz 1 and § 20 UStG); only a Kleinunternehmer for the whole year leaves it out."
)
KZ_742 = (
	"Kz 742, the Lieferungen des ersten Abnehmers, cannot be less than Kz 789, his Erwerbe: {0} against {1}."
)
VERZICHT = (
	"Line 75 holds sales taxed after a Verzicht nach § 9 UStG, which lines 24 to 29 hold as well, but those lines "
	"are empty."
)
VERZICHT_HINT = "Line 75 holds more sales taxed after a Verzicht nach § 9 UStG than lines 24 to 29, which hold them as well."
KU_SWITCH = (
	"Kz 136 dates a switch from the Kleinunternehmer-Regelung during the year, but the return holds no sales, "
	"neither under § 19 UStG in line 53 nor taxed ones."
)
KU_SWITCH_ONLY = (
	"Kz 136 dates a switch from the Kleinunternehmer-Regelung during the year, but the return holds only the sales "
	"under § 19 UStG of line 53 and none taxed after it."
)
KU_LIMIT = (
	"Kz 236 holds {0} euros of sales under § 19 Absatz 1 UStG, more than the 100,000 euros up to which it applies "
	"in the year: the sale that passes the limit is taxed, and Kz 136 dates the switch."
)
KU_BEFORE = (
	"Kz 136 dates a switch from the Kleinunternehmer-Regelung during the year, but line 53 holds no sales under § "
	"19 UStG before it; a Verzicht for the whole year dates the switch 1 January."
)
KU_JANUARY = (
	"Kz 136 dates the switch on 1 January, a Verzicht nach § 19 Absatz 3 UStG for the whole year: the return then "
	"holds taxed sales and none under § 19 UStG in line 53."
)
KU_MIXED = (
	"Line 53 holds sales under § 19 UStG next to taxed sales, but Kz 136 dates no switch from the "
	"Kleinunternehmer-Regelung."
)
OFFSET = "Kz 129 asks to offset a refund, but Kz 820 is no refund."
PARAGRAPH = (
	"Line {0} holds sales whose paragraph it does not name: give it in the mapping rule of the account."
)
SIGN = "{0} in line {1} takes no negative amount: {2}."
DIGITS = "{0} in line {1} takes at most {2} digits before the decimal comma: {3}."
LENGTH = "{0} in line {1} takes at most {2} characters, not {3}."
EUROS = "{0} in line {1} takes whole euros, not {2}."
MESSAGES = (
	MANDATORY,
	TOGETHER,
	SUM_DIFFERS,
	SUM_TOLERANCE,
	SUM_MISSING,
	SUM_ALONE,
	RATE,
	RULE,
	NIL,
	KZ_133,
	KZ_742,
	VERZICHT,
	VERZICHT_HINT,
	KU_SWITCH,
	KU_SWITCH_ONLY,
	KU_LIMIT,
	KU_BEFORE,
	KU_JANUARY,
	KU_MIXED,
	OFFSET,
	PARAGRAPH,
	SIGN,
	DIGITS,
	LENGTH,
	EUROS,
)

RATE_TOLERANCE = Decimal("1")
KZ_816_TOLERANCE = Decimal("10")
# The „Format als regulärer Ausdruck“ of the JD: an amount takes at most twelve digits before the decimal comma
# („\d{1,12}“), the Umfang der Verwendung im Erstjahr in line 95 fifteen („\d{1,15}“).
DIGITS_BEFORE_THE_COMMA = 12
MORE_DIGITS_BEFORE_THE_COMMA = MappingProxyType({"E3007404": 15})
KLEINUNTERNEHMER_LIMIT = Decimal("100000")
SMALL_SALES_LIMIT = Decimal("10000")
LUF_LIMIT = Decimal("4000")


@dataclass(frozen=True, slots=True)
class Reference:
	"""What a rule may need besides the values: the year of the return (Referenzjahr) and the day of the check
	(Heute), which only rule 30089 reads and which None leaves unchecked."""

	year: int
	today: date | None = None

	@property
	def first_of_january(self) -> date:
		"""„Datum("01", "01")“: the first of January of the year of the return."""
		return date(self.year, 1, 1)


Message = tuple[str, tuple[object, ...], tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class Pattern:
	"""A rule of fields given or not and of amounts that are not zero; all its parts must hold.

	``given``, ``absent`` and ``nonzero`` read one field each, the others a list of fields. ``in_context`` stands for
	„KontextAngegeben(/USt2A)“, a return that holds any field. ``mandatory`` gives the rule of one absent field the
	message MANDATORY instead of RULE.
	"""

	code: str
	given: tuple[str, ...] = ()
	absent: tuple[str, ...] = ()
	any_of: tuple[str, ...] = ()
	none_of: tuple[str, ...] = ()
	all_of: tuple[str, ...] = ()
	not_all_of: tuple[str, ...] = ()
	nonzero: tuple[str, ...] = ()
	in_context: bool = False
	mandatory: bool = False

	def violated(self, values: Values, reference: Reference) -> bool:
		return (
			(not self.in_context or bool(values))
			and all(element in values for element in self.given)
			and not any(element in values for element in self.absent)
			and (not self.any_of or any(element in values for element in self.any_of))
			and not any(element in values for element in self.none_of)
			and all(element in values for element in self.all_of)
			and (not self.not_all_of or not all(element in values for element in self.not_all_of))
			and all(_amount(values, element) != ZERO for element in self.nonzero)
		)

	@property
	def condition(self) -> str:
		parts = ["KontextAngegeben(/USt2A)"] if self.in_context else []
		parts += [f"FeldAngegeben({element})" for element in self.given]
		parts += [f"[{element}] != 0" for element in self.nonzero]
		parts += [f"FeldNichtAngegeben({element})" for element in self.absent]
		for construct, elements in (
			("MindestensEinFeldAngegeben", self.any_of),
			("KeinFeldAngegeben", self.none_of),
			("AlleFelderAngegeben", self.all_of),
			("NichtAlleFelderOderKeinFeldAngegeben", self.not_all_of),
		):
			if elements:
				parts.append(f"{construct}({_list(elements)})")
		return " Und ".join(parts)

	@property
	def fields(self) -> tuple[str, ...]:
		groups = (self.given, self.absent, self.any_of, self.none_of, self.all_of, self.not_all_of)
		return tuple(dict.fromkeys(element for group in groups for element in group))

	def message(self, catalogue: Catalogue, values: Values) -> Message:
		if self.mandatory:
			field = catalogue.field(self.absent[0])
			return MANDATORY, (_ref(field), field.line), (field.element,)
		return RULE, (self.code, self.condition), self.fields


@dataclass(frozen=True, slots=True)
class Together:
	"""Fields filed together or not at all; ``guarded`` writes the condition as the JD does for rules 30013 and 30095."""

	code: str
	elements: tuple[str, ...]
	guarded: bool = False

	def violated(self, values: Values, reference: Reference) -> bool:
		given = [element in values for element in self.elements]
		return any(given) and not all(given)

	@property
	def condition(self) -> str:
		together = f"FelderNichtGemeinsamAngegeben({_list(self.elements)})"
		return (
			f"MindestensEinFeldAngegeben({_list(self.elements)}) Und {together}" if self.guarded else together
		)

	def message(self, catalogue: Catalogue, values: Values) -> Message:
		first, second = (_ref(catalogue.field(element)) for element in self.elements)
		return TOGETHER, (first, second), self.elements


@dataclass(frozen=True, slots=True)
class SumDiffers:
	"""A sum of the form that differs from its lines, by more than ``tolerance``."""

	code: str
	total: str
	parts: tuple[Part, ...]
	tolerance: Decimal = ZERO

	def violated(self, values: Values, reference: Reference) -> bool:
		if self.total not in values or not any(part in values for part, _ in self.parts):
			return False
		return abs(_amount(values, self.total) - self.expected(values)) > self.tolerance

	def expected(self, values: Values) -> Decimal:
		return sum((sign * _amount(values, part) for part, sign in self.parts), ZERO)

	@property
	def condition(self) -> str:
		operator = f"UngleichMitToleranz{self.tolerance}" if self.tolerance else "!="
		if len(self.parts) == 1:
			((part, _sign),) = self.parts
			return f"FeldAngegeben({self.total}) Und FeldAngegeben({part}) Und [{self.total}] {operator} [{part}]"
		elements = _list(part for part, _ in self.parts)
		if all(sign > 0 for _, sign in self.parts):
			expression = f"Summe({elements})"
		else:
			expression = "".join(
				f"{'' if index == 0 else '-' if sign < 0 else '+'}[{part}]"
				for index, (part, sign) in enumerate(self.parts)
			)
		return f"FeldAngegeben({self.total}) Und MindestensEinFeldAngegeben({elements}) Und [{self.total}] {operator} {expression}"

	def message(self, catalogue: Catalogue, values: Values) -> Message:
		field = catalogue.field(self.total)
		template = SUM_TOLERANCE if self.tolerance else SUM_DIFFERS
		amounts = (_euros(_amount(values, self.total)), _euros(self.expected(values)))
		return template, (_ref(field), field.line, *amounts), (self.total,)


@dataclass(frozen=True, slots=True)
class SumMissing:
	"""A sum of the form that is missing although one of its lines is given."""

	code: str
	total: str
	parts: tuple[Part, ...]

	@property
	def pattern(self) -> Pattern:
		elements = tuple(part for part, _ in self.parts)
		if len(elements) == 1:
			return Pattern(self.code, given=elements, absent=(self.total,))
		return Pattern(self.code, absent=(self.total,), any_of=elements)

	def violated(self, values: Values, reference: Reference) -> bool:
		return self.pattern.violated(values, reference)

	@property
	def condition(self) -> str:
		return self.pattern.condition

	def message(self, catalogue: Catalogue, values: Values) -> Message:
		field = catalogue.field(self.total)
		return SUM_MISSING, (_ref(field), field.line), (self.total,)


@dataclass(frozen=True, slots=True)
class SumAlone:
	"""A sum of the form that is given, and with ``nonzero`` not zero, although none of its lines is."""

	code: str
	total: str
	parts: tuple[Part, ...]
	nonzero: bool = False

	@property
	def pattern(self) -> Pattern:
		elements = tuple(part for part, _ in self.parts)
		nonzero = (self.total,) if self.nonzero else ()
		if len(elements) == 1:
			return Pattern(self.code, given=(self.total,), absent=elements, nonzero=nonzero)
		return Pattern(self.code, given=(self.total,), none_of=elements, nonzero=nonzero)

	def violated(self, values: Values, reference: Reference) -> bool:
		return self.pattern.violated(values, reference)

	@property
	def condition(self) -> str:
		return self.pattern.condition

	def message(self, catalogue: Catalogue, values: Values) -> Message:
		field = catalogue.field(self.total)
		return SUM_ALONE, (_ref(field), field.line), (self.total,)


@dataclass(frozen=True, slots=True)
class Rate:
	"""The tax of a base at its rate, within one euro of the rate times the base."""

	code: str
	tax: str
	base: str
	rate: Decimal

	def violated(self, values: Values, reference: Reference) -> bool:
		if self.tax not in values or self.base not in values:
			return False
		return abs(_amount(values, self.tax) - self.expected(values)) > RATE_TOLERANCE

	def expected(self, values: Values) -> Decimal:
		return _amount(values, self.base) * self.rate / HUNDRED

	@property
	def condition(self) -> str:
		factor = format(self.rate / HUNDRED, ".2f")
		return (
			f"FeldAngegeben({self.tax}) Und FeldAngegeben({self.base}) Und [{self.tax}] UngleichMitToleranz1 "
			f"{{{factor} * [{self.base}]}}"
		)

	def message(self, catalogue: Catalogue, values: Values) -> Message:
		field = catalogue.field(self.tax)
		amounts = (_euros(_amount(values, self.tax)), _euros(self.expected(values)))
		return RATE, (_ref(field), field.line, str(self.rate), *amounts), (self.tax, self.base)


@dataclass(frozen=True, slots=True)
class Specific:
	"""A rule written out: its condition as the JD gives it, the test of it, and its message.

	Without a template of its own the rule names its code and its condition (RULE); ``arguments`` gives the values of
	a template of its own.
	"""

	code: str
	condition: str
	test: Callable[[Values, Reference], bool]
	fields: tuple[str, ...] = ()
	template: str = RULE
	arguments: Callable[[Values], tuple[object, ...]] | None = None

	def violated(self, values: Values, reference: Reference) -> bool:
		return self.test(values, reference)

	def message(self, catalogue: Catalogue, values: Values) -> Message:
		if self.template == RULE:
			return RULE, (self.code, self.condition), self.fields
		arguments = () if self.arguments is None else self.arguments(values)
		return self.template, arguments, self.fields


Check = Pattern | Together | SumDiffers | SumMissing | SumAlone | Rate | Specific


def check(year: int, values: Values, today: date | None = None) -> tuple[Finding, ...]:
	"""The findings of the checks of Steuerbote and of the local rules on the values of a return of ``year``.

	``today`` is the day of the check, which rule 30089 compares with the year; without it the rule is not checked.
	A year without a catalogue raises UnknownYearError, a field the form does not have ValueError, and a value of
	the wrong type TypeError.
	"""
	catalogue = catalogue_for(year)
	_require_types(catalogue, values)
	findings = [*_own_checks(catalogue, values)]
	reference = Reference(year, today)
	for rule in LOCAL_RULES[year]:
		if rule.violated(values, reference):
			template, arguments, fields = rule.message(catalogue, values)
			severity = catalogue.rule(rule.code).severity
			findings.append(Finding(rule.code, severity, template, arguments, fields))
	return tuple(findings)


def _own_checks(catalogue: Catalogue, values: Values) -> list[Finding]:
	findings = []
	for field in catalogue.fields:
		if field.element not in values:
			continue
		value = values[field.element]
		if field.format.amount:
			findings += _amount_checks(field, value)
		elif field.format is Format.TEXT and field.length is not None and len(value) > field.length:
			arguments = (_ref(field), field.line, field.length, len(value))
			findings.append(Finding("LAENGE", Severity.ERROR, LENGTH, arguments, (field.element,)))
	for field in catalogue.fields:
		if field.paragraph is not None and _amount(values, field.element) and field.paragraph not in values:
			fields = (field.element, field.paragraph)
			findings.append(Finding("PARAGRAF-FEHLT", Severity.ERROR, PARAGRAPH, (field.line,), fields))
	return findings


def _amount_checks(field: Field, amount: Decimal) -> list[Finding]:
	shown = format(amount, "f")
	digits = MORE_DIGITS_BEFORE_THE_COMMA.get(field.element, DIGITS_BEFORE_THE_COMMA)
	checks = (
		("VOLLE-EURO", EUROS, (shown,), field.format.whole_euros and amount != to_full_euros(amount)),
		("VORZEICHEN", SIGN, (shown,), not field.format.signed and amount < ZERO),
		("STELLEN", DIGITS, (digits, shown), abs(amount) >= Decimal(10) ** digits),
	)
	return [
		Finding(code, Severity.ERROR, template, (_ref(field), field.line, *arguments), (field.element,))
		for code, template, arguments, broken in checks
		if broken
	]


def _require_types(catalogue: Catalogue, values: Values) -> None:
	for element, value in values.items():
		try:
			field = catalogue.field(element)
		except KeyError:
			raise ValueError(f"Form USt 2 A {catalogue.year} has no field {element}") from None
		if field.format.amount:
			_require(isinstance(value, Decimal), f"{element} takes a Decimal, not {type(value).__name__}")
		elif field.format in (Format.TEXT, Format.LIST):
			_require(isinstance(value, str), f"{element} takes a str, not {type(value).__name__}")
		elif field.format is Format.DATE:
			_require(isinstance(value, date), f"{element} takes a date, not {type(value).__name__}")
		elif field.format is Format.DAYS:
			is_span = (
				isinstance(value, tuple) and len(value) == 2 and all(isinstance(day, date) for day in value)
			)
			_require(is_span, f"{element} takes a span of two dates, not {value!r}")
		else:
			_require(value is True, f"{element} takes True, not {value!r}")


def _require(holds: bool, message: str) -> None:
	if not holds:
		raise TypeError(message)


def _amount(values: Values, element: str) -> Decimal:
	value = values.get(element, ZERO)
	return value if isinstance(value, Decimal) else ZERO


def _date(values: Values, element: str) -> date:
	return cast(date, values[element])


def _span(values: Values, element: str) -> tuple[date, date]:
	return cast(tuple[date, date], values[element])


def _list(elements: Iterable[str]) -> str:
	return ", ".join(elements)


def _listed(condition: str, construct: str) -> tuple[str, ...]:
	"""The fields of the first list of ``construct`` in a condition of the JD."""
	start = condition.index(f"{construct}(") + len(construct) + 1
	return tuple(element.strip() for element in condition[start : condition.index(")", start)].split(","))


def _ref(field: Field) -> str:
	"""A field as a message names it: by its Kennzahl, or by its Feldkennung."""
	return f"Kz {field.kennzahl}" if field.kennzahl is not None else field.element


def _euros(amount: Decimal) -> str:
	return format(to_cents(amount), "f")


def _any(values: Values, elements: tuple[str, ...]) -> bool:
	return any(element in values for element in elements)


def _switch_during_the_year(values: Values, reference: Reference) -> bool:
	return "E3001601" in values and _date(values, "E3001601") > reference.first_of_january


def _switch_on_the_first(values: Values, reference: Reference) -> bool:
	return "E3001601" in values and _date(values, "E3001601") == reference.first_of_january


def _resident(values: Values) -> bool:
	"""Kz 125 not given: the company is resident in Germany."""
	return "E3001402" not in values


# The conditions of the rules written out, as the JD gives them with its blanks reduced to one.
_30093 = (
	"( FeldNichtAngegeben(E3002203) Und KeinFeldAngegeben(E3104701, E3001601) ) Oder ( KeinFeldAngegeben(E3002203, "
	"E3001402) und FeldAngegeben (E3001601) )"
)
_30449 = (
	"((FeldAngegeben(E3011101) Und [E3011101] != 0) Oder (FeldAngegeben(E3011401) Und [E3011401] != 0) Oder "
	"FeldNichtAngegeben(E3011101) Oder FeldNichtAngegeben(E3011401)) Und MindestensEinFeldAngegeben(E3000601, "
	"E3001701, E3001401, E3001402, E3001501, E3001801, E3002201, E3002203, E3011101, E3011401) Und "
	"KeinFeldAngegeben(E3104701, E3003303, E3003405, E3003505, E3004401, E3003703, E3003803, E3002801, E3002901, "
	"E3003001, E3005001, E3005002, E3005201, E3005005, E3005006, E3005801, E3005401, E3005402, E3005403, E3102901, "
	"E3005901, E3006201, E3006301, E3006401, E3006503, E3006502, E3006601, E3006701, E3006801, E3007001, E3007301, "
	"E3007601, E3008501, E3008601, E3008901, E3008902, E3010301, E3010401, E3010501, E3100801, E3100901, E3100902, "
	"E3101301, E3101305, E3101303, E3101304, E3101401, E3101402, E3101801, E3101701, E3102301, E3102305, E3102303, "
	"E3102304, E3102205, E3102206, E3102307, E3102308, E3102503, E3102504, E3102804, E3102805, E3103301, E3103401, "
	"E3103501, E3103801, E3104201, E3104401, E3104502, E3104902, E3105301, E3105101, E3105102, E3105602, E3105702, "
	"E3105801, E3105901, E3106001, E3106101, E3201101, E3201902, E3201901)"
)
_REGULAR_SALES = (
	"E3003303, E3003304, E3003405, E3003406, E3003505, E3003506, E3004401, E3004402, E3003703, E3003704, E3003803, "
	"E3003804, E3002801, E3002901, E3003001, E3005001, E3005002, E3005401, E3005402, E3005403, E3005404, E3102901, "
	"E3103301, E3103801, E3103902, E3104001, E3104002, E3104101, E3104201, E3104902"
)
_30007 = (
	'FeldNichtAngegeben(E3001402) Und FeldAngegeben(E3001601) Und [E3001601] > Datum("01", "01") Und '
	"KeinFeldAngegeben(E3104701, E3003303, E3003304, E3003405, E3003406, E3003505, E3003506, E3004401, E3004402, "
	"E3003703, E3003704, E3003803, E3003804, E3002801, E3002901, E3003001, E3005001, E3005002, E3005401,E3005402, "
	"E3005403, E3005404, E3102901, E3103301, E3103801, E3103902, E3104001, E3104002, E3104101, E3104201, E3104902)"
)
_30412 = (
	'FeldNichtAngegeben(E3001402) Und FeldAngegeben(E3001601) Und [E3001601] > Datum("01", "01") Und '
	"FeldAngegeben(E3104701) Und KeinFeldAngegeben(E3003303, E3003304, E3003405, E3003406, E3003505, E3003506, "
	"E3004401, E3004402, E3003703, E3003704, E3003803, E3003804, E3002801, E3002901, E3003001, E3005001, E3005002, "
	"E3005401, E3005402, E3005403, E3005404, E3102901, E3103301, E3103801, E3103902, E3104001, E3104101, E3104002, "
	"E3104201, E3104902)"
)
_30414 = (
	'FeldNichtAngegeben(E3001402) Und FeldAngegeben(E3001601) Und [E3001601] > Datum("01", "01") Und '
	f"FeldNichtAngegeben(E3104701) Und MindestensEinFeldAngegeben({_REGULAR_SALES})"
)
_30422 = (
	'FeldNichtAngegeben(E3001402) Und FeldAngegeben(E3001601) Und [E3001601] == Datum("01", "01") Und '
	f"FeldAngegeben(E3104701) Und MindestensEinFeldAngegeben({_REGULAR_SALES})"
)
_30423 = (
	'FeldNichtAngegeben(E3001402) Und FeldAngegeben(E3001601) Und [E3001601] == Datum("01", "01") Und '
	f"FeldAngegeben(E3104701) Und KeinFeldAngegeben({_REGULAR_SALES})"
)
_30424 = (
	"FeldNichtAngegeben(E3001402) Und FeldNichtAngegeben(E3001601) Und FeldAngegeben(E3104701) Und "
	f"MindestensEinFeldAngegeben({_REGULAR_SALES})"
)
_VERZICHT_SALES = "E3003303, E3003405, E3003505, E3004401, E3003703, E3003803"
_30015 = f"FeldAngegeben(E3105201) Und [E3105201] > 0 Und KeinFeldAngegeben({_VERZICHT_SALES})"
_30016 = (
	f"FeldAngegeben(E3105201) Und [E3105201] > 0 Und MindestensEinFeldAngegeben({_VERZICHT_SALES}) Und "
	f"Summe({_VERZICHT_SALES}) < [E3105201]"
)
_SMALL_SALES = "E3003303, E3003405, E3003505, E3004401, E3003703, E3003803, E3104701"
_30816 = (
	"FeldAngegeben (E3105101) und [E3105101] != 0 und [E3105101] <= 10000 und "
	f"MindestensEinFeldAngegeben({_SMALL_SALES}) und Summe({_SMALL_SALES}) < [E3105101]"
)
_30017 = (
	"FeldAngegeben(E3105101) Und [E3105101] > 0 Und [E3105101] <= 10000 Und "
	f"KeinFeldAngegeben({_SMALL_SALES})"
)
_NEGATIVE_BASES = (
	"E3003303",
	"E3003304",
	"E3004401",
	"E3004402",
	"E3002801",
	"E3005001",
	"E3005002",
	"E3005005",
	"E3005006",
	"E3005801",
	"E3005401",
	"E3005402",
	"E3005403",
	"E3005404",
)
_30941 = (
	f"FeldNichtAngegeben(E3106101) Und MindestensEinFeldAngegeben({_list(_NEGATIVE_BASES)}) Und( "
	+ " Oder ".join(f"(FeldAngegeben({element}) Und [{element}] < 0)" for element in _NEGATIVE_BASES)
	+ ")"
)
_NEGATIVE_VORSTEUER = ("E3006201", "E3006601", "E3006701")
_30943 = (
	f"FeldNichtAngegeben(E3007001) Und MindestensEinFeldAngegeben({_list(_NEGATIVE_VORSTEUER)}) Und ( "
	+ " Oder ".join(f"(FeldAngegeben({element}) Und [{element}] < 0)" for element in _NEGATIVE_VORSTEUER)
	+ " )"
)
_WITHOUT_KLEINUNTERNEHMER = (
	"( FeldNichtAngegeben(E3104701) oder ( FeldAngegeben(E3104701) und FeldAngegeben(E3001601) und [E3001601] > "
	'Datum("01","01") ) )'
)
_30675 = (
	"MindestensEinFeldAngegeben(E3001101, E3001203, E3001204, E3001205, E3001206, E3001208, E3001207, E3001209) Und "
	"((KeinFeldAngegeben(E3001208, E3001209) Und FelderNichtGemeinsamAngegeben(E3001101, E3001206, E3001207)) Oder "
	"(MindestensEinFeldAngegeben(E3001208, E3001209) Und FelderNichtGemeinsamAngegeben(E3001101, E3001208, "
	"E3001207, E3001209)))"
)


def _nil(values: Values, reference: Reference) -> bool:
	kz816, kz820 = "E3011101" in values, "E3011401" in values
	owed = (
		(kz816 and _amount(values, "E3011101") != ZERO)
		or (kz820 and _amount(values, "E3011401") != ZERO)
		or not kz816
		or not kz820
	)
	general = _listed(_30449, "MindestensEinFeldAngegeben")
	return owed and _any(values, general) and not _any(values, _listed(_30449, "KeinFeldAngegeben"))


def _kz133(values: Values, reference: Reference) -> bool:
	return ("E3002203" not in values and not _any(values, ("E3104701", "E3001601"))) or (
		not _any(values, ("E3002203", "E3001402")) and "E3001601" in values
	)


def _section_19_sales(values: Values) -> bool:
	return "E3104701" in values


def _regular_sales(values: Values) -> bool:
	return _any(values, _listed(_30424, "MindestensEinFeldAngegeben"))


def _30007_test(values: Values, reference: Reference) -> bool:
	sales = _listed(_30007, "KeinFeldAngegeben")
	return _resident(values) and _switch_during_the_year(values, reference) and not _any(values, sales)


def _30412_test(values: Values, reference: Reference) -> bool:
	return (
		_resident(values)
		and _switch_during_the_year(values, reference)
		and _section_19_sales(values)
		and not _any(values, _listed(_30412, "KeinFeldAngegeben"))
	)


def _30413_test(values: Values, reference: Reference) -> bool:
	return (
		_resident(values)
		and _section_19_sales(values)
		and _amount(values, "E3104701") > KLEINUNTERNEHMER_LIMIT
	)


def _30414_test(values: Values, reference: Reference) -> bool:
	return (
		_resident(values)
		and _switch_during_the_year(values, reference)
		and not _section_19_sales(values)
		and _regular_sales(values)
	)


def _30422_test(values: Values, reference: Reference) -> bool:
	return (
		_resident(values)
		and _switch_on_the_first(values, reference)
		and _section_19_sales(values)
		and _regular_sales(values)
	)


def _30423_test(values: Values, reference: Reference) -> bool:
	return (
		_resident(values)
		and _switch_on_the_first(values, reference)
		and _section_19_sales(values)
		and not _regular_sales(values)
	)


def _30424_test(values: Values, reference: Reference) -> bool:
	return (
		_resident(values)
		and "E3001601" not in values
		and _section_19_sales(values)
		and _regular_sales(values)
	)


def _30014_test(values: Values, reference: Reference) -> bool:
	both = "E3100801" in values and "E3101801" in values
	return both and _amount(values, "E3101801") < _amount(values, "E3100801")


def _verzicht(values: Values) -> bool:
	return "E3105201" in values and _amount(values, "E3105201") > ZERO


def _30015_test(values: Values, reference: Reference) -> bool:
	return _verzicht(values) and not _any(values, _listed(_30015, "KeinFeldAngegeben"))


def _30016_test(values: Values, reference: Reference) -> bool:
	sales = _listed(_30016, "MindestensEinFeldAngegeben")
	total = sum((_amount(values, element) for element in sales), ZERO)
	return _verzicht(values) and _any(values, sales) and total < _amount(values, "E3105201")


def _30011_test(values: Values, reference: Reference) -> bool:
	offset = "E3001701" in values and "E3011401" in values
	return offset and _amount(values, "E3011401") >= ZERO and "E3000601" not in values


def _30006_test(values: Values, reference: Reference) -> bool:
	return "E3001601" in values and _date(values, "E3001601").year != reference.year


def _30081_test(values: Values, reference: Reference) -> bool:
	both = "E3001501" in values and "E3001401" in values
	return both and _span(values, "E3001501")[0] < _span(values, "E3001401")[1]


def _30089_test(values: Values, reference: Reference) -> bool:
	early = reference.today is not None and reference.today.year <= reference.year
	return bool(values) and early and not _any(values, ("E3001401", "E3001501"))


def _30676_test(values: Values, reference: Reference) -> bool:
	if "E3001401" not in values:
		return False
	start, end = _span(values, "E3001401")
	return (start.day, start.month, end.day, end.month) == (1, 1, 31, 12)


def _30675_test(values: Values, reference: Reference) -> bool:
	if not _any(values, _listed(_30675, "MindestensEinFeldAngegeben")):
		return False
	abroad = _any(values, ("E3001208", "E3001209"))
	address = (
		("E3001101", "E3001208", "E3001207", "E3001209") if abroad else ("E3001101", "E3001206", "E3001207")
	)
	given = [element in values for element in address]
	return any(given) and not all(given)


def _30916_test(values: Values, reference: Reference) -> bool:
	both = "E3005001" in values and "E3005002" in values
	return both and _amount(values, "E3005001") != ZERO and _amount(values, "E3005002") == ZERO


def _30946_test(values: Values, reference: Reference) -> bool:
	both = "E3005005" in values and "E3005801" in values
	return both and _amount(values, "E3005005") + _amount(values, "E3005801") <= LUF_LIMIT


def _above_small_sales(element: str) -> Callable[[Values, Reference], bool]:
	def test(values: Values, reference: Reference) -> bool:
		return element in values and _amount(values, element) > SMALL_SALES_LIMIT

	return test


def _30815_test(values: Values, reference: Reference) -> bool:
	return "E3105602" in values and _amount(values, "E3105602") == ZERO


def _30816_test(values: Values, reference: Reference) -> bool:
	sales = _listed(_30816, "MindestensEinFeldAngegeben")
	amount = _amount(values, "E3105101")
	total = sum((_amount(values, element) for element in sales), ZERO)
	small = "E3105101" in values and amount != ZERO and amount <= SMALL_SALES_LIMIT
	return small and _any(values, sales) and total < amount


def _30017_test(values: Values, reference: Reference) -> bool:
	amount = _amount(values, "E3105101")
	small = "E3105101" in values and ZERO < amount <= SMALL_SALES_LIMIT
	return small and not _any(values, _listed(_30017, "KeinFeldAngegeben"))


def _negative_without(minderung: str, elements: tuple[str, ...]) -> Callable[[Values, Reference], bool]:
	def test(values: Values, reference: Reference) -> bool:
		negative = any(element in values and _amount(values, element) < ZERO for element in elements)
		return minderung not in values and negative

	return test


def _without_kleinunternehmer(values: Values, reference: Reference) -> bool:
	return not _section_19_sales(values) or _switch_during_the_year(values, reference)


def _reasons(
	given: tuple[str, ...], absent: tuple[str, ...], any_of: bool = False
) -> Callable[[Values, Reference], bool]:
	"""The rules 30933 to 30936 on the reasons of section 15a: some reason given, another absent."""

	def test(values: Values, reference: Reference) -> bool:
		reason = _any(values, given) if any_of else all(element in values for element in given)
		return _without_kleinunternehmer(values, reference) and reason and not _any(values, absent)

	return test


_KU = ("E3001601", "E3104701")
_SPECIFICS_2026 = (
	Specific("30093", _30093, _kz133, ("E3002203",), KZ_133),
	Specific("30449", _30449, _nil, ("E3003303",), NIL),
	Specific("30007", _30007, _30007_test, _KU, KU_SWITCH),
	Specific("30412", _30412, _30412_test, _KU, KU_SWITCH_ONLY),
	Specific(
		"30413",
		"FeldNichtAngegeben(E3001402) Und FeldAngegeben(E3104701) Und [E3104701] > 100000",
		_30413_test,
		("E3104701",),
		KU_LIMIT,
		lambda values: (format(_amount(values, "E3104701"), "f"),),
	),
	Specific("30414", _30414, _30414_test, _KU, KU_BEFORE),
	Specific("30422", _30422, _30422_test, _KU, KU_JANUARY),
	Specific("30423", _30423, _30423_test, _KU, KU_JANUARY),
	Specific("30424", _30424, _30424_test, ("E3104701", "E3001601"), KU_MIXED),
	Specific(
		"30014",
		"AlleFelderAngegeben(E3100801, E3101801) Und [E3101801] < [E3100801]",
		_30014_test,
		("E3101801", "E3100801"),
		KZ_742,
		lambda values: (format(_amount(values, "E3101801"), "f"), format(_amount(values, "E3100801"), "f")),
	),
	Specific("30015", _30015, _30015_test, ("E3105201",), VERZICHT),
	Specific("30016", _30016, _30016_test, ("E3105201",), VERZICHT_HINT),
	Specific(
		"30011",
		"AlleFelderAngegeben(E3001701, E3011401) und [E3011401] >=0 und FeldNichtAngegeben(E3000601)",
		_30011_test,
		("E3001701",),
		OFFSET,
	),
	Specific(
		"30006",
		"FeldAngegeben(E3001601) und JahrAusDatum(E3001601) != JahrAusDatum(Referenzjahr)",
		_30006_test,
		("E3001601",),
	),
	Specific(
		"30081",
		"AlleFelderAngegeben(E3001501, E3001401) Und StartAusDatumBereich(E3001501) < EndeAusDatumBereich(E3001401)",
		_30081_test,
		("E3001501", "E3001401"),
	),
	Specific(
		"30089",
		"KontextAngegeben(/USt2A) und (JahrAusDatum (Heute) <= Referenzjahr ) und KeinFeldAngegeben (E3001401, "
		"E3001501)",
		_30089_test,
		("E3001401", "E3001501"),
	),
	Specific(
		"30676",
		'FeldAngegeben(E3001401) und StartAusDatumBereich(E3001401) == "01.01." und EndeAusDatumBereich(E3001401) '
		'== "31.12."',
		_30676_test,
		("E3001401",),
	),
	Specific("30675", _30675, _30675_test, ("E3001101", "E3001206", "E3001207")),
	Specific(
		"30916",
		"AlleFelderAngegeben(E3005001, E3005002) und [E3005001] != 0 und [E3005002] == 0",
		_30916_test,
		("E3005001", "E3005002"),
	),
	Specific(
		"30946",
		"AlleFelderAngegeben(E3005005, E3005801) Und Summe(E3005005, E3005801) <= 4000",
		_30946_test,
		("E3005005", "E3005801"),
	),
	Specific(
		"30809",
		"FeldAngegeben (E3105101) und [E3105101] > 10000",
		_above_small_sales("E3105101"),
		("E3105101",),
	),
	Specific(
		"30812",
		"FeldAngegeben (E3105102) und [E3105102] > 10000",
		_above_small_sales("E3105102"),
		("E3105102",),
	),
	Specific("30815", "FeldAngegeben(E3105602) Und [E3105602] == 0", _30815_test, ("E3105602",)),
	Specific("30816", _30816, _30816_test, ("E3105101",)),
	Specific("30017", _30017, _30017_test, ("E3105101",)),
	Specific("30941", _30941, _negative_without("E3106101", _NEGATIVE_BASES), ("E3106101",)),
	Specific("30943", _30943, _negative_without("E3007001", _NEGATIVE_VORSTEUER), ("E3007001",)),
	Specific(
		"30933",
		f"{_WITHOUT_KLEINUNTERNEHMER} Und FeldAngegeben(E3007901) Und KeinFeldAngegeben(E3008001, E3008202, E3008401)",
		_reasons(("E3007901",), ("E3008001", "E3008202", "E3008401")),
		("E3007901",),
	),
	Specific(
		"30934",
		f"{_WITHOUT_KLEINUNTERNEHMER} Und MindestensEinFeldAngegeben(E3008001, E3008202, E3008401) Und "
		"FeldNichtAngegeben(E3007901)",
		_reasons(("E3008001", "E3008202", "E3008401"), ("E3007901",), any_of=True),
		("E3007901",),
	),
	Specific(
		"30935",
		f"{_WITHOUT_KLEINUNTERNEHMER} Und FeldAngegeben(E3008401) Und FeldNichtAngegeben(E3008402)",
		_reasons(("E3008401",), ("E3008402",)),
		("E3008402",),
	),
	Specific(
		"30936",
		f"{_WITHOUT_KLEINUNTERNEHMER} Und FeldAngegeben(E3008402) Und FeldNichtAngegeben(E3008401)",
		_reasons(("E3008402",), ("E3008401",)),
		("E3008401",),
	),
)

# Sales and Vorsteuer that a Kleinunternehmer without a switch cannot have next to line 53 (rules 307xx).
_KLEINUNTERNEHMER = ("E3001601", "E3001402")
_PATTERNS_2026 = (
	Pattern("30002", given=("E3000601",)),
	Pattern("30096", in_context=True, absent=("E3000901",), mandatory=True),
	Pattern("30008", absent=("E3000401",)),
	Pattern("30092", given=("E3001204",), absent=("E3001203",)),
	Pattern(
		"30094", none_of=("E3001101", "E3001206", "E3001208", "E3001207", "E3001403", "E3001404", "E3001209")
	),
	Pattern("30097", given=("E3001101",), absent=("E3001203",)),
	Pattern("30677", any_of=("E3001208", "E3001209"), absent=("E3001402",)),
	Pattern("30086", given=("E3001501",), absent=("E3001401",)),
	Pattern("30098", given=("E3104701", "E3002203"), none_of=("E3001402", "E3001601")),
	Pattern("30937", all_of=("E3002201", "E3002202")),
	Pattern("30944", any_of=("E3002506",), not_all_of=("E3002501", "E3002503", "E3002504")),
	Pattern("30945", any_of=("E3002506",), absent=("E3002602",)),
	Pattern(
		"30705",
		given=("E3104701",),
		none_of=_KLEINUNTERNEHMER,
		any_of=("E3006201", "E3006301", "E3006401", "E3006503", "E3006502", "E3006601", "E3006801"),
	),
	Pattern(
		"30720",
		given=("E3104701",),
		none_of=_KLEINUNTERNEHMER,
		any_of=("E3007901", "E3008001", "E3008202", "E3008401", "E3008402"),
	),
	Pattern(
		"30725",
		given=("E3104701",),
		none_of=_KLEINUNTERNEHMER,
		any_of=("E3008701", "E3008801", "E3008803", "E3008901"),
	),
	Pattern("30730", given=("E3104701", "E3010001"), none_of=_KLEINUNTERNEHMER),
	Pattern("30740", given=("E3104701", "E3105201"), none_of=_KLEINUNTERNEHMER),
	Pattern("30745", given=("E3104701", "E3105301"), none_of=_KLEINUNTERNEHMER),
	Pattern("30755", given=("E3104701", "E3106001"), none_of=_KLEINUNTERNEHMER),
	Pattern(
		"30710", given=("E3104701",), none_of=_KLEINUNTERNEHMER, any_of=("E3007801", "E3007802", "E3007803")
	),
	Pattern("30807", given=("E3105602",)),
	Pattern("30813", given=("E3105101", "E3105102"), nonzero=("E3105101", "E3105102")),
	Pattern("30940", given=("E3106101",), nonzero=("E3106101",), none_of=_NEGATIVE_BASES),
	Pattern("30948", given=("E3006503",), nonzero=("E3006503",), none_of=("E3102804", "E3102805")),
	Pattern(
		"30949",
		given=("E3006502",),
		nonzero=("E3006502",),
		none_of=("E3102205", "E3102206", "E3102307", "E3102308", "E3102503", "E3102504"),
	),
	Pattern(
		"30951",
		given=("E3006801",),
		nonzero=("E3006801",),
		none_of=("E3101701", "E3101702", "E3102301", "E3102302", "E3102305", "E3102303", "E3102304"),
	),
	Pattern(
		"30312",
		given=("E3006301",),
		nonzero=("E3006301",),
		none_of=(
			"E3100902",
			"E3100903",
			"E3101301",
			"E3101302",
			"E3101303",
			"E3101304",
			"E3101401",
			"E3101402",
		),
	),
	Pattern("30942", given=("E3007001",), nonzero=("E3007001",), none_of=_NEGATIVE_VORSTEUER),
	Pattern("30925", given=("E3007601",), none_of=("E3008701", "E3008702")),
	Pattern("30926", any_of=("E3008701", "E3008702"), absent=("E3007601",)),
	Pattern("30927", given=("E3008501",), none_of=("E3008801", "E3008802")),
	Pattern("30928", any_of=("E3008801", "E3008802"), absent=("E3008501",)),
	Pattern("30929", given=("E3008601",), none_of=("E3008803", "E3008804")),
	Pattern("30930", any_of=("E3008803", "E3008804"), absent=("E3008601",)),
	Pattern(
		"30932",
		any_of=("E3007801", "E3007802", "E3007803", "E3007804", "E3007901"),
		none_of=("E3007601", "E3008501", "E3008601"),
	),
	Pattern(
		"30931",
		any_of=("E3007601", "E3008501", "E3008601"),
		none_of=("E3007801", "E3007802", "E3007803", "E3007804", "E3007901"),
	),
	Pattern("30070", absent=("E3011101",), mandatory=True),
	Pattern("30915", absent=("E3011301",), mandatory=True),
	Pattern("30620", absent=("E3011401",), mandatory=True),
)

# Each sum of the form with the codes of its three rules: differs, missing, given alone.
_SUMS_2026 = (
	("E3006001", "30314", "30364", "30900"),
	("E3104201", "30345", "30415", "30804"),
	("E3101501", "30342", "30392", "30800"),
	("E3102904", "30354", "30404", "30801"),
	("E3102401", "30356", "30406", "30802"),
	("E3102601", "30358", "30408", "30803"),
	("E3006901", "30317", "30367", "30901"),
	("E3008901", "30321", "30371", "30902"),
	("E3008902", "30331", "30381", "30903"),
	("E3009201", "30232", "30142", "30452"),
	("E3009401", "30270", "30180", "30490"),
	("E3009602", "30311", "30193", "30540"),
	("E3009501", "30280", "30190", "30500"),
	("E3009502", "30283", "30146", "30503"),
	("E3009801", "30630", "30912", "30905"),
	("E3009901", "30240", "30150", "30460"),
	("E3010001", "30250", "30160", "30470"),
	("E3010201", "30632", "30913", "30907"),
	("E3009701", "30260", "30170", "30480"),
	("E3010601", "30634", "30914", "30909"),
)
# Kz 816 and Kz 820 are mandatory (rules 30070 and 30620) rather than missing; Kz 816 may differ by ten euros.
_KZ_816 = ("E3011101", "30636", "30910")
_KZ_820 = ("E3011401", "30638", "30911")

_PAIRS_2026 = (
	("30649", "E3003303", "E3003304"),
	("30650", "E3003405", "E3003406"),
	("30651", "E3003505", "E3003506"),
	("30652", "E3004401", "E3004402"),
	("30653", "E3003703", "E3003704"),
	("30654", "E3003803", "E3003804"),
	("30091", "E3005001", "E3005002"),
	("30655", "E3005005", "E3005006"),
	("30009", "E3005401", "E3005402"),
	("30010", "E3005403", "E3005404"),
	("30115", "E3101303", "E3101304"),
	("30120", "E3101401", "E3101402"),
	("30669", "E3100902", "E3100903"),
	("30670", "E3101301", "E3101302"),
	("30131", "E3102804", "E3102805"),
	("30125", "E3102303", "E3102304"),
	("30671", "E3101701", "E3101702"),
	("30672", "E3102301", "E3102302"),
	("30137", "E3102205", "E3102206"),
	("30139", "E3102307", "E3102308"),
	("30147", "E3102503", "E3102504"),
	("30917", "E3002201", "E3002202"),
)
_RATES_2026 = (
	("30639", "E3003304", "E3003303", RATE_19),
	("30640", "E3003406", "E3003405", RATE_19),
	("30641", "E3003506", "E3003505", RATE_19),
	("30642", "E3004402", "E3004401", RATE_7),
	("30643", "E3003704", "E3003703", RATE_7),
	("30644", "E3003804", "E3003803", RATE_7),
	("30012", "E3005404", "E3005403", RATE_19),
	("30656", "E3100903", "E3100902", RATE_19),
	("30658", "E3101302", "E3101301", RATE_7),
	("30660", "E3101702", "E3101701", RATE_19),
	("30661", "E3102302", "E3102301", RATE_7),
)
LEFT_TO_ERIC_2026 = MappingProxyType(
	{
		"30087": "Kz 125 and Anlage UN: Steuerbote files for a company resident in Germany",
		"30088": "Anlage UN: Steuerbote files for a company resident in Germany",
		"30938": "Kz 126 and Anlage FV: Steuerbote files no return of a Fiskalvertreter",
		"30939": "Anlage FV: Steuerbote files no return of a Fiskalvertreter",
		"30225": "line 18 of Anlage UN, which Steuerbote does not file",
		"30313": "line 18 of Anlage UN, which Steuerbote does not file",
	}
)


def _rules_2026(catalogue: Catalogue) -> tuple[Check, ...]:
	"""The local rules of 2026 in the order of the JD."""
	rules: dict[str, Check] = {rule.code: rule for rule in (*_PATTERNS_2026, *_SPECIFICS_2026)}
	for total, differs, missing, alone in _SUMS_2026:
		parts = catalogue.field(total).parts
		rules[differs] = SumDiffers(differs, total, parts)
		rules[missing] = SumMissing(missing, total, parts)
		rules[alone] = SumAlone(alone, total, parts)
	for (total, differs, alone), tolerance, nonzero in (
		(_KZ_816, KZ_816_TOLERANCE, True),
		(_KZ_820, ZERO, False),
	):
		parts = catalogue.field(total).parts
		rules[differs] = SumDiffers(differs, total, parts, tolerance)
		rules[alone] = SumAlone(alone, total, parts, nonzero)
	for code, base, tax in _PAIRS_2026:
		rules[code] = Together(code, (base, tax))
	rules["30095"] = Together("30095", ("E3001403", "E3001404"), guarded=True)
	rules["30013"] = Together("30013", ("E3100801", "E3101801"), guarded=True)
	for code, tax, base, rate in _RATES_2026:
		rules[code] = Rate(code, tax, base, rate)
	return tuple(rules[rule.code] for rule in catalogue.rules if rule.code in rules)


LOCAL_RULES: MappingProxyType[int, tuple[Check, ...]] = MappingProxyType(
	{2026: _rules_2026(catalogue_for(2026))}
)
LEFT_TO_ERIC: MappingProxyType[int, MappingProxyType[str, str]] = MappingProxyType({2026: LEFT_TO_ERIC_2026})
