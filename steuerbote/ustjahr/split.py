"""Which line of the annual return each account feeds: the split of the Kennzahlen of the Voranmeldung.

The VAT Return Mapping maps an account to a Kennzahl of the Voranmeldung (steuerbote/ustva/mapping.py). Most
Kennzahlen have a single line in the annual return, but ten split into several (steuerbote/ustjahr/form.py), so
each mapped account also needs its line, its annual field. split() takes, in this order:

1. the annual field of the mapping rule, which the company sets by hand (Choice);
2. the default for the role the account plays in its chart (``role_defaults``, by account number; the defaults of
   SKR03 and SKR04 live in steuerbote/ustjahr/defaults.py);
3. the default line of the Kennzahl, or its only line.

The line must take the amounts of the Kennzahl of the rule. A role default that does not is left aside, since the
company mapped the account to another Kennzahl than its role suggests; an annual field that does not is refused.
So the lines of a Kennzahl hold exactly its amounts, and the reconciliation with the filed Voranmeldungen holds
Kennzahl by Kennzahl by construction. Kz 64 has no default line: its account needs an annual field or a role.

Lines 46, 52 and 54 print the paragraph of their sales, „Umsätze nach § … UStG“ (form USt 2 A 2026): a rule of an
account on such a line gives it, and only such a rule may.

Some accounts only the annual return reads, „Zuordnung nur für die Umsatzsteuererklärung“ (AnnualRule): an account
that no Kennzahl of the Voranmeldung takes, such as the Erwerb des ersten Abnehmers in an innergemeinschaftliches
Dreiecksgeschäft for Kz 789, feeds its field directly with its balance on its side. A watched account may, since
the annual return now decides where its balance goes; an account the mapping maps or checks as a tax account may
not, or its balance would count twice.

Messages are English templates with positional placeholders: SplitError keeps template and values apart, so that
the Frappe layer can translate the template before formatting it.
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from steuerbote.ustjahr.form import Catalogue, Field, catalogue_for
from steuerbote.ustva.mapping import AccountRule, Mapping, Side, is_account_number

UNKNOWN_FIELD = "Form USt 2 A {0} has no field {1}."
NO_RULE = "Account {0} has an annual field but no mapping rule."
TWO_CHOICES = "Account {0} has two annual fields."
NOT_A_LINE = "Account {0} feeds Kennzahl {1} of the Voranmeldung, which field {2} in line {3} does not take."
NO_DEFAULT = (
	"Account {0} feeds Kennzahl {1} of the Voranmeldung, which splits into lines without a default: "
	"choose its annual field."
)
NO_PARAGRAPH = "Field {1} in line {2} names no paragraph, so account {0} gives none."
ANNUAL_MAPPED = (
	"Account {0} feeds Kennzahl {1} of the Voranmeldung, so its line comes from that mapping rule."
)
ANNUAL_CHECKED = "Account {0} is a tax account of the Verprobung {1} and feeds no line."
ANNUAL_TWICE = "Account {0} has two rules for the annual return only."
NOT_FED = (
	"Account {0} cannot feed field {1} in line {2}: the form computes it, the company states it, or Steuerbote "
	"does not file it."
)
MESSAGES = (
	UNKNOWN_FIELD,
	NO_RULE,
	TWO_CHOICES,
	NOT_A_LINE,
	NO_DEFAULT,
	NO_PARAGRAPH,
	ANNUAL_MAPPED,
	ANNUAL_CHECKED,
	ANNUAL_TWICE,
	NOT_FED,
)


class SplitError(ValueError):
	"""An account cannot feed the line it names; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


class How(Enum):
	"""How an account got its line."""

	RULE = "rule"
	ROLE = "role"
	DEFAULT = "default"
	ANNUAL = "annual"


@dataclass(frozen=True, slots=True)
class Choice:
	"""What a mapping rule says for the annual return: its annual field, a Feldkennung such as E3003405 for Kz 178,
	and the paragraph its line names, such as „4 Nummer 14“ for line 52."""

	account_number: str
	field: str | None = None
	paragraph: str | None = None

	def __post_init__(self) -> None:
		_require_account(self.account_number)


@dataclass(frozen=True, slots=True)
class AnnualRule:
	"""An account only the annual return reads: it feeds ``field`` with its balance on ``side``."""

	account_number: str
	field: str
	side: Side
	paragraph: str | None = None

	def __post_init__(self) -> None:
		_require_account(self.account_number)
		object.__setattr__(self, "side", Side(self.side))


@dataclass(frozen=True, slots=True)
class Assignment:
	"""The line an account feeds, and how it got it.

	``kennzahl`` is the Kennzahl of the Voranmeldung of the mapping rule; an annual rule has none and brings its
	``side`` instead. ``paragraph`` is the paragraph the account names for its line.
	"""

	account_number: str
	field: str
	how: How
	kennzahl: str | None = None
	side: Side | None = None
	paragraph: str | None = None


@dataclass(frozen=True, slots=True)
class Split:
	"""The line of every mapped account and of every account only the annual return reads."""

	catalogue: Catalogue
	mapping: Mapping
	assignments: ReadOnlyMapping[str, Assignment]
	annual_rules: tuple[AnnualRule, ...]

	def assignment(self, account_number: str) -> Assignment | None:
		return self.assignments.get(account_number)

	def field_of(self, account_number: str) -> str | None:
		assignment = self.assignments.get(account_number)
		return None if assignment is None else assignment.field

	def accounts(self, element: str) -> tuple[str, ...]:
		"""The accounts that feed a field, in the order of the mapping and then of the annual rules."""
		return tuple(number for number, assignment in self.assignments.items() if assignment.field == element)


def split(
	mapping: Mapping,
	choices: Iterable[Choice] = (),
	role_defaults: ReadOnlyMapping[str, str] | None = None,
	annual_rules: Iterable[AnnualRule] = (),
) -> Split:
	"""The line of each account of the mapping and of each annual rule, in the catalogue of the year of the mapping.

	``choices`` carry the annual fields of the mapping rules, ``role_defaults`` the field the role of an account
	suggests, by account number.
	"""
	catalogue = catalogue_for(mapping.year)
	by_account = _choices(mapping, choices)
	roles = role_defaults or {}
	assignments: dict[str, Assignment] = {}
	for rule in mapping.rules:
		choice = by_account.get(rule.account_number, Choice(rule.account_number))
		field, how = _line(catalogue, rule, choice, roles.get(rule.account_number))
		paragraph = _paragraph(field, rule.account_number, choice.paragraph)
		assignments[rule.account_number] = Assignment(
			rule.account_number, field.element, how, kennzahl=rule.kennzahl, paragraph=paragraph
		)
	rules = tuple(annual_rules)
	for annual in rules:
		_check_annual(mapping, assignments, annual)
		field = _field(catalogue, annual.field)
		if not field.fed:
			raise SplitError(NOT_FED, annual.account_number, field.element, field.line)
		paragraph = _paragraph(field, annual.account_number, annual.paragraph)
		assignments[annual.account_number] = Assignment(
			annual.account_number, field.element, How.ANNUAL, side=annual.side, paragraph=paragraph
		)
	return Split(catalogue, mapping, MappingProxyType(assignments), rules)


def _choices(mapping: Mapping, choices: Iterable[Choice]) -> dict[str, Choice]:
	by_account: dict[str, Choice] = {}
	for choice in choices:
		if mapping.rule_for(choice.account_number) is None:
			raise SplitError(NO_RULE, choice.account_number)
		if choice.account_number in by_account:
			raise SplitError(TWO_CHOICES, choice.account_number)
		by_account[choice.account_number] = choice
	return by_account


def _line(catalogue: Catalogue, rule: AccountRule, choice: Choice, role: str | None) -> tuple[Field, How]:
	if choice.field is not None:
		field = _field(catalogue, choice.field)
		if field.ustva != rule.kennzahl:
			raise SplitError(NOT_A_LINE, rule.account_number, rule.kennzahl, field.element, field.line)
		return field, How.RULE
	lines = catalogue.children(rule.kennzahl)
	by_role = next((line for line in lines if line.element == role), None)
	if by_role is not None:
		return by_role, How.ROLE
	default = catalogue.default_child(rule.kennzahl)
	if default is None:
		raise SplitError(NO_DEFAULT, rule.account_number, rule.kennzahl)
	return default, How.DEFAULT


def _paragraph(field: Field, account_number: str, paragraph: str | None) -> str | None:
	"""The paragraph on one line without blanks at either end; a blank paragraph is none."""
	text = " ".join((paragraph or "").split()) or None
	if text is not None and field.paragraph is None:
		raise SplitError(NO_PARAGRAPH, account_number, field.element, field.line)
	return text


def _check_annual(
	mapping: Mapping, assignments: ReadOnlyMapping[str, Assignment], annual: AnnualRule
) -> None:
	rule = mapping.rule_for(annual.account_number)
	if rule is not None:
		raise SplitError(ANNUAL_MAPPED, annual.account_number, rule.kennzahl)
	for check in mapping.checks:
		if annual.account_number in check.tax_accounts:
			raise SplitError(ANNUAL_CHECKED, annual.account_number, check.label)
	if annual.account_number in assignments:
		raise SplitError(ANNUAL_TWICE, annual.account_number)


def _field(catalogue: Catalogue, element: str) -> Field:
	try:
		return catalogue.field(element)
	except KeyError:
		raise SplitError(UNKNOWN_FIELD, catalogue.year, element) from None


def _require_account(account_number: object) -> None:
	if not is_account_number(account_number):
		raise ValueError(f"{account_number!r} is not an account number")
