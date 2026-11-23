"""The values, fields, rules and forms of the Erklärungen: USt 2 A (E50), KSt (E30) and GewSt (E20).

Sources are the Jahresdokumentationen of the ERiC documentation 44.3.6.0
(https://download.elster.de/download/eric/eric_44/), cited as JD: Jahresdokumentation_E50_2026.ods,
Jahresdokumentation_E30_2025.ods and Jahresdokumentation_E20_2025.ods, each with its sheet „Allg. Information“
(Zeichensatz Standard_E_V2, Dezimaltrennzeichen „,“, the Vordrucke with their number and whether they are a
Pflichtvordruck, the legend of the Formatkennzeichen) and per Vordruck the sheets „<Vordruck> - Felder“ and
„<Vordruck> - Regeln“; and the schemas of the Nutzdaten, E50-2026.xsd, E30-2025.xsd and E20-2025.xsd.

A field takes its value in the format its Formatkennzeichen names (FORMATS, the legend of the JD), as value_text
writes it:

- Numbers have a decimal comma and, where the format takes a sign, a leading „-“; there is no plus sign, no leading
  zero and no negative zero, and at most 12 digits before the comma (the patterns of GanzzahlOhneFuehrNullBaseCType
  and DezimalzahlOhneFuehrNullBaseCType and the types *_MaxVK12_* of the schemas; the JD names other limits per
  field). Whole euros (N, U, G, M) take no cents and two decimals (P, %, R, S) no fraction of a cent: the caller
  rounds first, with steuerbote/ustva/rounding.py, the only place that rounds.
- J and X write yes as 1 or X and leave the field out otherwise; Y writes 1 for yes and 2 for no.
- Dates are TT.MM.JJJJ (D) or TT.MM. (T), spans TT.MM-TT.MM within one year (B) or TT.MM.JJJJ-TT.MM.JJJJ (Z).
- A Steuernummer (A) has the 13 digits of the ELSTER format, an Identifikationsnummer (I) eleven digits, O digits
  only.
- Every other field (C) is a text in the character set Standard_E_V2 (charset.py), on one line: the pattern
  [^\\n\\r]+ of StringBaseCType refuses a line break.

A Field also carries the „Format als regulärer Ausdruck“ of the JD, which holds the limits of the field; its text is
checked against it. The JD writes the patterns in the syntax of Java, whose quotes \\Q...\\E python_pattern turns into
the escapes of Python.

The catalogues of the modules (steuerbote/ustjahr, steuerbote/kst, steuerbote/gewst) describe the Erklärung of a
year with these types: FormCatalogue holds its Datenart, its Vordrucke (Form), its fields (Field) in the order of
the schema and its rules (Rule).
"""

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from steuerbote.elster.ustva_xml import (
	NOT_A_STEUERNUMMER,
	STEUERNUMMER_PATTERN,
	TEXT_CHARACTERS,
	TEXT_MISSING,
	TEXT_TOO_LONG,
	XmlError,
	elster_text,
)
from steuerbote.eric.datenart import Datenart
from steuerbote.ustva.rounding import CENT, ZERO, require_decimal

DECIMAL_COMMA = ","
INTEGER_DIGITS = 12
VARIABLE_DECIMALS = 4
IDNR_PATTERN = re.compile("[0-9]{11}")
DIGITS_PATTERN = re.compile("[0-9]+")
_JAVA_QUOTE = re.compile(r"\\Q(.*?)\\E", re.DOTALL)

FORMATS: MappingProxyType[str, str] = MappingProxyType(
	{
		"%": "Zahl mit 2 Nachkommastellen bzw. GeldbetragMitCent Ohne Vorzeichen, Null ist erlaubt",
		"A": (
			"Steuernummer im ELSTER-Steuernummerformat, nur Ziffern erlaubt, genau dreizehn Stellen, fünfte Stelle "
			"muss per Definition 0 sein"
		),
		"B": "DatumBereich mit Format TT.MM-TT.MM",
		"C": "alle Felder, die kein gesondertes Formatkennzeichen enthalten",
		"D": "Datum mit Format TT.MM.JJJJ",
		"F": "Zahl mit variablen Nachkommastellen (0-4) ohne Vorzeichen",
		"G": "Zahl ohne Nachkommastellen bzw. GeldbetragOhneCent Ohne Vorzeichen, Null nicht erlaubt",
		"H": "Listenfeld: Textfeld für das eine Auswahlmöglichkeit aus einer Werteliste vorgegeben wird",
		"I": "einheitliche Identifikationsnummer nach § 139 AO; nur Ziffern erlaubt, genau elf Stellen",
		"J": "JaFeld mit Wert für Ja 1",
		"M": "Zahl ohne Nachkommastellen bzw. GeldbetragOhneCent Mit Vorzeichen, Null nicht erlaubt",
		"N": "Zahl ohne Nachkommastellen bzw. GeldbetragOhneCent Mit Vorzeichen, Null erlaubt",
		"O": (
			"optionales Formatkennzeichen für Strings, die nur aus Ziffern bestehen dürfen und für Datum mit Format "
			"JJJJ"
		),
		"P": "Zahl mit 2 Nachkommastellen bzw. GeldbetragMitCent Mit Vorzeichen , Null erlaubt",
		"R": "Zahl mit 2 Nachkommastellen bzw. GeldbetragMitCent Ohne Vorzeichen, Null nicht erlaubt",
		"S": "Zahl mit 2 Nachkommastellen bzw. GeldbetragMitCent Mit Vorzeichen, Null nicht erlaubt",
		"T": "Datum mit Format TT.MM.",
		"U": "Zahl ohne Nachkommastellen bzw. GeldbetragOhneCent Ohne Vorzeichen, Null erlaubt",
		"V": "Zahl mit variablen Nachkommastellen (0-4) mit Vorzeichen",
		"X": "JaFeld mit Wert für Ja X (Ankreuzfeld)",
		"Y": "JaNeinFeld mit Wert für Ja 1 und Wert für Nein 2",
		"Z": "Datumsbereich mit Format TT.MM.JJJJ-TT.MM.JJJJ",
	}
)
"""The Formatkennzeichen of the fields of USt, KSt and GewSt, with their legend in the JD."""


class _Number:
	"""How a Formatkennzeichen of a number writes it: the decimals it takes, whether it takes a sign and a zero."""

	def __init__(self, decimals: int | None, signed: bool, zero: bool) -> None:
		self.decimals = decimals
		"""Exactly this many decimals, or None for those of the value, up to four."""
		self.signed = signed
		self.zero = zero


_NUMBERS = MappingProxyType(
	{
		"N": _Number(0, signed=True, zero=True),
		"U": _Number(0, signed=False, zero=True),
		"G": _Number(0, signed=False, zero=False),
		"M": _Number(0, signed=True, zero=False),
		"P": _Number(2, signed=True, zero=True),
		"%": _Number(2, signed=False, zero=True),
		"R": _Number(2, signed=False, zero=False),
		"S": _Number(2, signed=True, zero=False),
		"F": _Number(None, signed=False, zero=True),
		"V": _Number(None, signed=True, zero=True),
	}
)
_YES = MappingProxyType({"J": ("1", None), "X": ("X", None), "Y": ("1", "2")})

NOT_WHOLE = "{label} takes whole euros, not {0}."
TOO_MANY_DECIMALS = "{label} takes at most {1} decimals, not {0}."
TOO_MANY_DIGITS = "{label} takes at most {1} digits before the decimal comma, not {0}."
NEGATIVE = "{label} takes no negative value: {0}."
ZERO_VALUE = "{label} takes no zero; it is left out instead."
NOT_AN_OPTION = "{label} takes one of {1}, not {0}."
NOT_A_SPAN = "{label} begins on {0}, after it ends on {1}."
NOT_IN_ONE_YEAR = "{label} runs from {0} to {1}; this field takes days of one year."
NOT_AN_IDNR = "{0} is not an Identifikationsnummer of eleven digits."
NOT_DIGITS = "{label} takes digits only, not {0}."
NOT_IN_FORMAT = "{label}: ELSTER does not take {0} in this field."
MESSAGES = (
	NOT_WHOLE,
	TOO_MANY_DECIMALS,
	TOO_MANY_DIGITS,
	NEGATIVE,
	ZERO_VALUE,
	NOT_AN_OPTION,
	NOT_A_SPAN,
	NOT_IN_ONE_YEAR,
	NOT_AN_IDNR,
	NOT_DIGITS,
	NOT_IN_FORMAT,
	NOT_A_STEUERNUMMER,
	TEXT_MISSING,
	TEXT_TOO_LONG,
	TEXT_CHARACTERS,
)


def value_text(
	value: object,
	formatkennzeichen: str,
	*,
	label: str,
	length: int | None = None,
	options: Collection[str] = (),
	integer_digits: int = INTEGER_DIGITS,
) -> str | None:
	"""The value as the field of the Formatkennzeichen takes it, None to leave the field out.

	``label`` names the field in an XmlError, ``length`` is the greatest length of a text (C), ``options`` the values
	of a Listenfeld (H) and ``integer_digits`` the digits a number takes before the comma.
	"""
	if formatkennzeichen not in FORMATS:
		raise ValueError(f"steuerbote writes no Formatkennzeichen {formatkennzeichen!r}")
	if value is None:
		return None
	if formatkennzeichen in _NUMBERS:
		return _number(require_decimal(value), _NUMBERS[formatkennzeichen], label, integer_digits)
	if formatkennzeichen in _YES:
		if not isinstance(value, bool):
			raise TypeError(f"a yes field takes True or False, not {type(value).__name__}")
		yes, no = _YES[formatkennzeichen]
		return yes if value else no
	if formatkennzeichen in ("D", "T"):
		return _date(value).strftime("%d.%m.%Y" if formatkennzeichen == "D" else "%d.%m.")
	if formatkennzeichen in ("B", "Z"):
		return _span(value, formatkennzeichen == "B", label)
	return _text(str(value), formatkennzeichen, label, length, options)


def python_pattern(pattern: str) -> str:
	"""A pattern of the JD in the syntax of Python: the quotes \\Q...\\E of Java become escapes."""
	return _JAVA_QUOTE.sub(lambda match: re.escape(match[1]), pattern)


def _number(value: Decimal, number: _Number, label: str, integer_digits: int) -> str:
	shown = format(value, "f")
	if not value.is_finite():
		raise ValueError(f"{label}: {shown} is no number")
	if number.decimals == 0 and value != value.to_integral_value():
		raise XmlError(NOT_WHOLE, shown, label=label)
	most = VARIABLE_DECIMALS if number.decimals is None else number.decimals
	if value != value.quantize(Decimal(1).scaleb(-most)):
		raise XmlError(TOO_MANY_DECIMALS, shown, most, label=label)
	if value < ZERO and not number.signed:
		raise XmlError(NEGATIVE, shown, label=label)
	if value == ZERO and not number.zero:
		raise XmlError(ZERO_VALUE, label=label)
	if len(format(abs(value).to_integral_value(rounding="ROUND_DOWN"), "f")) > integer_digits:
		raise XmlError(TOO_MANY_DIGITS, shown, integer_digits, label=label)
	if number.decimals == 0:
		written = value.to_integral_value()
	elif number.decimals is None:
		written = value
	else:
		written = value.quantize(CENT)
	return format(written + ZERO, "f").replace(".", DECIMAL_COMMA)


def _date(value: object) -> date:
	if not isinstance(value, date):
		raise TypeError(f"a date field takes a date, not {type(value).__name__}")
	return value


def _span(value: object, in_one_year: bool, label: str) -> str:
	begin, end = value
	begin, end = _date(begin), _date(end)
	shown = (begin.strftime("%d.%m.%Y"), end.strftime("%d.%m.%Y"))
	if begin > end:
		raise XmlError(NOT_A_SPAN, *shown, label=label)
	if not in_one_year:
		return f"{shown[0]}-{shown[1]}"
	if begin.year != end.year:
		raise XmlError(NOT_IN_ONE_YEAR, *shown, label=label)
	return f"{begin:%d.%m}-{end:%d.%m}"


def _text(
	value: str, formatkennzeichen: str, label: str, length: int | None, options: Collection[str]
) -> str | None:
	if formatkennzeichen == "A":
		if not STEUERNUMMER_PATTERN.fullmatch(value):
			raise XmlError(NOT_A_STEUERNUMMER, value)
		return value
	if formatkennzeichen == "I":
		if not IDNR_PATTERN.fullmatch(value):
			raise XmlError(NOT_AN_IDNR, value)
		return value
	if formatkennzeichen == "O":
		if not DIGITS_PATTERN.fullmatch(value):
			raise XmlError(NOT_DIGITS, value, label=label)
		return value
	if formatkennzeichen == "H":
		if not options:
			raise ValueError(f"{label}: a Listenfeld needs the values of its list")
		if value not in options:
			raise XmlError(NOT_AN_OPTION, value, ", ".join(options), label=label)
		return value
	if length is None:
		raise ValueError(f"{label}: a text needs the length of its field")
	return elster_text(value, label, length)


@dataclass(frozen=True, slots=True)
class Field:
	"""A field of a Vordruck, as the sheet „<Vordruck> - Felder“ of the JD describes it."""

	form: str
	"""The Vordruck, such as USt2A."""
	context: str
	"""The Kontext below the Vordruck, such as Umsaetze/Tabelle/Ums_allg, empty for a field directly below it."""
	feldkennung: str
	"""The Name of the field, such as E3003405."""
	label: str
	"""The Beschreibung of the field."""
	format: str
	"""The Formatkennzeichen."""
	line: int | str | None = None
	"""The Vordruckzeile of the printed form, such as 40, or 75c where the JD letters a line."""
	kennzahl: str | None = None
	"""The Kennzahl of the sheet „<Vordruck> - Kennzahlen“."""
	length: int | None = None
	"""The Max. Länge of a text."""
	required: bool = False
	"""Pflichtfeld."""
	pattern: str | None = None
	"""The Format als regulärer Ausdruck."""
	options: tuple[str, ...] = ()
	"""The values of a Listenfeld."""
	rows: int = 1
	"""The max. Zeilen."""

	def __post_init__(self) -> None:
		object.__setattr__(self, "options", tuple(self.options))
		if self.format not in FORMATS:
			raise ValueError(f"{self.feldkennung}: steuerbote writes no Formatkennzeichen {self.format!r}")
		if self.format == "H" and not self.options:
			raise ValueError(f"{self.feldkennung}: a Listenfeld needs the values of its list")
		if self.format == "C" and self.length is None:
			raise ValueError(f"{self.feldkennung}: a text needs the length of its field")

	@property
	def path(self) -> tuple[str, ...]:
		"""The elements from the root of the Nutzdaten down to the field."""
		return (self.form, *(part for part in self.context.split("/") if part), self.feldkennung)

	def text(self, value: object) -> str | None:
		"""The value as the field takes it, None to leave it out; XmlError for one its pattern refuses."""
		text = value_text(value, self.format, label=self.label, length=self.length, options=self.options)
		if text is not None and self.pattern and not re.fullmatch(python_pattern(self.pattern), text):
			raise XmlError(NOT_IN_FORMAT, text, label=self.label)
		return text


@dataclass(frozen=True, slots=True)
class Rule:
	"""A rule of a Vordruck, as the sheet „<Vordruck> - Regeln“ of the JD describes it."""

	code: str
	"""The Fehlercode."""
	name: str
	text: str
	"""The Fehler- /Hinweistext."""
	fields: tuple[str, ...] = ()
	"""The Geprüfte Felder, by their path."""
	hint: bool = False
	"""Whether the Regelart is Hinweis rather than Fehler."""

	def __post_init__(self) -> None:
		object.__setattr__(self, "fields", tuple(self.fields))


@dataclass(frozen=True, slots=True)
class Form:
	"""A Vordruck of the Erklärung, as the sheet „Allg. Information“ of the JD lists it."""

	name: str
	count: int = 1
	"""The max. lfd. Nr. Vordruck."""
	mandatory: bool = False
	"""Pflichtvordruck."""


@dataclass(frozen=True, slots=True)
class FormCatalogue:
	"""The Erklärung of a Datenart of a year: its Vordrucke, its fields in the order of the schema and its rules."""

	datenart: Datenart
	source: str
	"""The JD the catalogue comes from, with its Versionslabel."""
	forms: tuple[Form, ...]
	fields: tuple[Field, ...]
	rules: tuple[Rule, ...] = ()

	def __post_init__(self) -> None:
		for name in ("forms", "fields", "rules"):
			object.__setattr__(self, name, tuple(getattr(self, name)))
		if self.datenart.unterfallart is None:
			raise ValueError(f"the Datenart {self.datenart.name} is no Erklärung with a Vorsatz")
		names = [form.name for form in self.forms]
		if len(set(names)) != len(names):
			raise ValueError(f"{self.source}: a Vordruck stands twice")
		feldkennungen = [field.feldkennung for field in self.fields]
		if len(set(feldkennungen)) != len(feldkennungen):
			raise ValueError(f"{self.source}: a field stands twice")
		strangers = sorted({field.form for field in self.fields} - set(names))
		if strangers:
			raise ValueError(f"{self.source}: fields of Vordrucke it does not have: {', '.join(strangers)}")

	def field(self, feldkennung: str) -> Field:
		"""The field of the Feldkennung; KeyError for one the catalogue does not have."""
		for field in self.fields:
			if field.feldkennung == feldkennung:
				return field
		raise KeyError(feldkennung)

	@property
	def kennzahlen(self) -> Mapping[str, Field]:
		"""The fields with a Kennzahl, by it."""
		return MappingProxyType({field.kennzahl: field for field in self.fields if field.kennzahl})

	@property
	def mandatory_forms(self) -> tuple[str, ...]:
		"""The Pflichtvordrucke."""
		return tuple(form.name for form in self.forms if form.mandatory)
