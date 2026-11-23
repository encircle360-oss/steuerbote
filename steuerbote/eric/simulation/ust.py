"""The simulation of the Umsatzsteuererklärung, Datenart USt (Jahresdokumentation_E50_<Jahr>.ods): the structure of
an Erklärung with the main form USt2A, and the rules of the year in RULES.

steuerbote/eric/simulation/erklaerung.py checks the structure: the root E50 of the year, the Pflichtvordrucke USt2A and
Vorsatz and the fields of the Vorsatz. For a year whose form Steuerbote knows (CATALOGUES in
steuerbote/ustjahr/form.py, from the JD) RULES adds:

- that each field of USt2A is one of the form of the year, in the context the JD names, given once but for the
  Grundstücke of line 95, with a value of its Formatkennzeichen (sheet „USt2A - Felder“), SIM-010 (readable);
- each rule of the sheet „USt2A - Regeln“ of the Regelart Fehler that Steuerbote checks itself (LOCAL_RULES in
  steuerbote/ustjahr/rules.py), on the values of the Nutzdaten as rules.check() takes them (LocalRule). A rule that
  applies reports with its own Fehlercode, as ERiC does, and names the fields it checks. Its text is not that of the
  JD, which the documentation's licence keeps out of the repository: the findings of rules.check() say more, in the
  annual return.

The Hinweise of the JD stay out, since they do not stop ERiC either, and so do the checks of Steuerbote's own, such as
whole euros or the paragraph of lines 46, 52 and 54, which ERiC does not make in this form. The values of the
Grundstücke of line 95 are read for their format only: no rule of the JD reads them.

This module is pure Python and never imports Frappe or lxml.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree

from steuerbote.eric.datenart import Datenart
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import ERROR, Message
from steuerbote.eric.simulation import Rule, erklaerung
from steuerbote.ustjahr.form import CATALOGUES, Field, Format, Severity
from steuerbote.ustjahr.rules import LOCAL_RULES, Check, Reference

TITLE = "Umsatzsteuererklärung"
MAIN_FORM = "USt2A"
READABLE = "SIM-010"
SHEET = f"Jahresdokumentation, {MAIN_FORM} - Felder"

_NUMBERS = {
	Format.EUROS: re.compile(r"-?(0|[1-9][0-9]*)"),
	Format.UNSIGNED_EUROS: re.compile(r"0|[1-9][0-9]*"),
	Format.CENTS: re.compile(r"-?(0|[1-9][0-9]*),[0-9]{2}"),
	Format.UNSIGNED_CENTS: re.compile(r"(0|[1-9][0-9]*),[0-9]{2}"),
}
_YES = {Format.YES: "1", Format.CROSS: "X"}
_DATE = re.compile(r"([0-9]{2})\.([0-9]{2})\.([0-9]{4})")
_DAYS = re.compile(r"([0-9]{2})\.([0-9]{2})-([0-9]{2})\.([0-9]{2})")


class Unreadable(ValueError):
	"""A field of USt2A the simulation cannot read: its German text and the field."""

	def __init__(self, text: str, field: str) -> None:
		super().__init__(text)
		self.text = text
		self.field = field


def values_of(root: ElementTree.Element, kind: Datenart) -> dict[str, object]:
	"""The values of USt2A as rules.check() takes them, by Feldkennung: a Decimal for an amount, True for a yes field
	or a cross, a str for a text or a value of a list, a date, and a pair of dates for a span of the year. The fields
	of the Grundstücke of line 95 are checked and left out. Raises Unreadable for the first field that does not fit."""
	catalogue = CATALOGUES[kind.year]
	form = root.find(f"{{{kind.namespace}}}{MAIN_FORM}")
	values: dict[str, object] = {}
	for context, name, element in _leaves(form, kind.namespace, ()):
		try:
			field = catalogue.field(name)
		except KeyError:
			text = f"Das Feld {name} gibt es im Vordruck {MAIN_FORM} {kind.year} nicht ({SHEET})."
			raise Unreadable(text, name) from None
		if field.context != context:
			text = (
				f"Das Feld {name} steht in {context or MAIN_FORM}, die Jahresdokumentation nennt den Kontext "
				f"{field.context}."
			)
			raise Unreadable(text, name)
		value = _value(field, element.text or "", kind.year)
		if field.repeat > 1:
			continue
		if name in values:
			raise Unreadable(f"Das Feld {name} steht mehr als einmal im Vordruck {MAIN_FORM}.", name)
		values[name] = value
	return values


def readable(root: ElementTree.Element, kind: Datenart, header: EnvelopeHeader) -> Message | None:
	"""SIM-010: a field of USt2A that the form of the year does not have, in another context, twice, or with a value
	its Formatkennzeichen does not take."""
	if kind.year not in CATALOGUES:
		return None
	try:
		values_of(root, kind)
	except Unreadable as error:
		return Message(READABLE, error.text, ERROR, error.field)
	return None


@dataclass(frozen=True, slots=True)
class LocalRule:
	"""A rule of the JD of ``year`` that Steuerbote checks itself (steuerbote/ustjahr/rules.py), as a rule of the
	simulation: its error, with its Fehlercode, for the Nutzdaten of that year it applies to."""

	year: int
	check: Check

	@property
	def code(self) -> str:
		return self.check.code

	def __call__(self, root: ElementTree.Element, kind: Datenart, header: EnvelopeHeader) -> Message | None:
		if kind.year != self.year:
			return None
		try:
			values = values_of(root, kind)
		except Unreadable:
			return None
		if not self.check.violated(values, Reference(self.year)):
			return None
		catalogue = CATALOGUES[self.year]
		_template, _arguments, fields = self.check.message(catalogue, values)
		named = ", ".join(_reference(catalogue.field(element)) for element in fields)
		text = (
			f"Die Regel {self.code} ({catalogue.rule(self.code).name}) der Jahresdokumentation E50 {self.year} "
			f"schlägt an: {named}."
		)
		return Message(self.code, text, ERROR, fields[0])


def local_rules() -> tuple[LocalRule, ...]:
	"""The rules of the Regelart Fehler that Steuerbote checks itself, of every year in the order of its JD."""
	return tuple(
		LocalRule(year, check)
		for year, checks in LOCAL_RULES.items()
		for check in checks
		if CATALOGUES[year].rule(check.code).severity is Severity.ERROR
	)


RULES: tuple[Rule, ...] = (readable, *local_rules())
"""The rules of the sheet „USt2A - Regeln“ that the simulation checks beyond the structure."""

CHECKS = erklaerung.checks(TITLE, MAIN_FORM, RULES)


def _leaves(
	element: ElementTree.Element, namespace: str, path: tuple[str, ...]
) -> Iterator[tuple[str, str, ElementTree.Element]]:
	"""Each element without children below ``element``, with the context of its parent below USt2A and its name."""
	for child in element:
		name = child.tag.removeprefix(f"{{{namespace}}}")
		if len(child):
			yield from _leaves(child, namespace, (*path, name))
		else:
			yield "/".join(path), name, child


def _value(field: Field, text: str, year: int) -> object:
	value = _parsed(field.format, text, year)
	if value is None:
		message = f"Der Wert „{text}“ im Feld {field.element} passt nicht zu seinem Formatkennzeichen {field.format.value}"
		raise Unreadable(f"{message} ({SHEET}).", field.element)
	return value


def _parsed(form: Format, text: str, year: int) -> object:
	"""The value of the text in the format, None for a text the format does not take."""
	if form in _NUMBERS:
		return Decimal(text.replace(",", ".")) if _NUMBERS[form].fullmatch(text) else None
	if form in _YES:
		return True if text == _YES[form] else None
	if form is Format.DATE:
		match = _DATE.fullmatch(text)
		return _date(int(match[3]), int(match[2]), int(match[1])) if match else None
	if form is Format.DAYS:
		match = _DAYS.fullmatch(text)
		if match is None:
			return None
		begin, end = _date(year, int(match[2]), int(match[1])), _date(year, int(match[4]), int(match[3]))
		return None if begin is None or end is None else (begin, end)
	return text or None


def _date(year: int, month: int, day: int) -> date | None:
	try:
		return date(year, month, day)
	except ValueError:
		return None


def _reference(field: Field) -> str:
	"""A field as the messages of the simulation name it: by its Kennzahl or its Feldkennung, with its line."""
	name = f"Kz {field.kennzahl}" if field.kennzahl is not None else field.element
	return f"{name} in Zeile {field.line}"
