"""Form USt 2 A, Umsatzsteuererklärung, as ELSTER takes it: one catalogue of fields and rules per year.

2026: BMF letter of 29 December 2025 (GZ III C 3 - S 7344/00040/008/034), Vordruckmuster USt 2 A 2026 and its
Anleitung USt 2 E 2026, and the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/):
Jahresdokumentation_E50_2026.ods (Versionslabel 9.0), cited as JD, with its sheets "USt2A - Felder", "USt2A -
Kennzahlen", "USt2A - Kontexte", "USt2A - Regeln" and "Allg. Information", and the schema E50-2026.xsd. The forms
of the Voranmeldung, USt 1 A and USt 1 E 2026, come from the BMF letter of the same day, GZ III C 3 - S
7344/00039/007/036.

Fields. The JD lists 178 fields of USt2A. Two of them, Informationsteil and HinweisUStBescheid, are an „Internes
ERiC Feld“ that ERiC fills itself and the schema does not know; the other 176 are the leaves of USt2A in
E50-2026.xsd, in the order of the schema, which is the order of the JD. A field is named by its Feldkennung, „E“ and
seven digits, which is the name of its element. 88 fields carry the Kennzahl the form prints (JD sheet "USt2A -
Kennzahlen"); the others, such as the tax of Kz 177, have none. ``line`` is the line of the printed form, and the JD
agrees with it except for the Mitwirkung einer Steuerberatung, which the JD puts in lines 23 and 123: the form
prints it after line 126, the statement in line 127 and the person in the block of lines 128 and 129. ``label`` is
the Beschreibung of the JD, which is also its Drucktext.

Formats. The Formatkennzeichen of the JD (sheet "Allg. Information") say what ELSTER takes: whole euros or cents,
with or without sign, a yes field, a cross, a value of a list, a date, a span of days, or a text.

The Kennzahlen of the Voranmeldung. The annual return is no sum of the Voranmeldungen: its lines split Kennzahlen of
the Voranmeldung further, and it asks for amounts no Voranmeldung holds. Each amount field the ledger feeds names
the Kennzahl of form USt 1 A 2026 whose amounts it takes (``ustva``), so that the annual return reconciles Kennzahl
by Kennzahl with the filed Voranmeldungen: the lines of a Kennzahl together hold its amount. The split follows the
labels of USt 1 A 2026 and the Anleitungen USt 1 E 2026 and USt 2 E 2026:

- Kz 81, 86 and 87, the taxable sales at 19, 7 and 0 %, split into Lieferungen und sonstige Leistungen,
  Lieferungen nach § 3 Absatz 1b UStG and sonstige Leistungen nach § 3 Absatz 9a UStG (lines 24 to 32): the
  unentgeltlichen Wertabgaben are „in der Regel den entgeltlichen Lieferungen“ and „den entgeltlichen sonstigen
  Leistungen gleichgestellt“ (USt 2 E, Zeilen 24 bis 33).
- Kz 43, „Weitere steuerfreie Umsätze mit Vorsteuerabzug (z. B. Ausfuhrlieferungen, Umsätze nach § 4 Nummer 2 bis 7
  UStG, Umsätze nach Verordnungen der EU)“, into the Ausfuhrlieferungen of line 45 (Kz 752) and lines 46 to 49
  (USt 2 E, Zeile 45 and Zeilen 46 bis 50).
- Kz 48, „Steuerfreie Umsätze ohne Vorsteuerabzug (z. B. Umsätze nach § 4 Nummer 8 bis 29 oder § 19 Absatz 1
  UStG)“, into lines 51 to 54, as they do or do not belong to the Gesamtumsatz of § 19 Absatz 2 UStG (Kz 286,
  287, 236 and 240; USt 2 E, Zeilen 51 bis 52, Zeile 53 and Zeile 54).
- Kz 64, the Berichtigung des Vorsteuerabzugs nach § 15a UStG, into lines 105 to 107, each with a column for the
  Vorsteuer nachträglich abziehbar and one for the Vorsteuer zurückzuzahlen (USt 2 E, Zeilen 95 bis 108). Kz 64 is
  negative for a repayment, „Handelt es sich bei den Berichtigungsbeträgen um zurückzuzahlende Vorsteuerbeträge,
  tragen Sie bitte vor dem Betrag ein Minuszeichen ein“ (USt 1 E, Zeile 44), while the columns have no sign: a
  repayment column has ``sign`` -1.
- Kz 65, „Steuer infolge des Wechsels der Besteuerungsform sowie Nachsteuer auf versteuerte Anzahlungen und
  ähnlichem wegen Steuersatzänderung“, into line 39 (Kz 317) and line 40 (Kz 319).
- Kz 66, the Vorsteuer „aus Rechnungen von anderen Unternehmern (§ 15 Absatz 1 Satz 1 Nummer 1 UStG), aus
  Leistungen im Sinne des § 27 Absatz 40a UStG und aus innergemeinschaftlichen Dreiecksgeschäften (§ 25b Absatz 5
  UStG)“, into lines 85, 88 and 92 (Kz 320, 466 and 760).
- Kz 69, the taxes „nach § 14c UStG“, „nach § 6a Absatz 4 Satz 2, § 17 Absatz 1 Satz 7, § 25b Absatz 2 UStG oder
  von einem Auslagerer oder Lagerhalter nach § 27 Absatz 40a UStG“, into lines 119 and 120 (Kz 318 and 331), the
  tax of line 63 (Kz 853), and the taxes the last buyer of an innergemeinschaftliches Dreiecksgeschäft owes, which
  go „in den Zeilen 66, 67 und 69“ (USt 2 E, Zeilen 65 bis 70).
- Kz 45, the übrige nicht steuerbare Umsätze, holds the sales of § 3a Absatz 5 and § 3c Absatz 4 UStG that are
  taxed in another member state, since USt 1 E leaves out only those of „§ 3a Absatz 5 Satz 3 UStG sowie des § 3c
  Absatz 4 Satz 1 UStG“ (Zeile 36). The annual return asks for them in line 78 up to 10,000 euros and in line 81
  beyond (Kz 214 and 205; USt 2 E, Zeilen 77 und 78).

A Kennzahl that splits has a default line (``default``), which its amounts take unless a mapping rule or the role
of an account names another (steuerbote/ustjahr/split.py). Kz 64 has none, because a correction under § 15a UStG
belongs to the line of its kind of asset. Every other amount Kennzahl of the Voranmeldung has one line, which takes
all of its amounts. Kz 39 and Kz 83 have no line; they make the Vorauszahlungssoll of line 125
(steuerbote/ustjahr/soll.py).

Annual-only amounts. Some amounts are in no Kennzahl of the Voranmeldung: the Erwerbe des ersten Abnehmers in an
innergemeinschaftliches Dreiecksgeschäft (Kz 789, line 55, new in 2026), which ERiC takes only together with the
Lieferungen des ersten Abnehmers in Kz 742 (rule 30013); the bases of line 63 and of lines 66 to 69, whose taxes
the Voranmeldung reports in Kz 69; and the ergänzende Angaben of lines 75 to 83 but Kz 209, 214, 721 and 205.

Paragraphs. Lines 46, 52 and 54 print „Umsätze nach § … UStG“, „nach § 4 Nummer … UStG“ and „nach § … UStG“: each
amount comes with a text field of its line that names the paragraph of the exemption (``paragraph``).

Rate lines. The tax of a base at 19 or 7 % has a field of its own, which ERiC checks against the rate times the
base within one euro (rules 30639 to 30644, 30656, 30658 and 30012); ``rate`` and ``base`` name it, and ``tax``
names the tax of a base, which ERiC takes only together with it.

Sums. The form adds its lines up itself: lines 41, 50, 62, 64, 70, 74, 93 and 108, and section K from line 109 to
line 126, each checked by a rule of the JD. ``parts`` names what a sum adds up, each with its sign. Line 125, the
Vorauszahlungssoll, comes from the filed Voranmeldungen (``SOLL``).

Scope. Steuerbote files for a company resident in Germany. ``scope`` marks the fields it does not file: those of a
company resident abroad or of a Fiskalvertreter, with Anlage UN and Anlage FV; the taxable sales under §§ 25 and
25a UStG (lines 37 and 38); and the lines of a Kleinunternehmer (§ 19 UStG; lines 18, 53, 100 and 121), whose
amounts the ledger may still feed and the rules then check.

Rules. The JD lists 175 rules of USt2A, 142 errors (Fehler) and 33 hints (Hinweis), each by its Fehlercode, its name
and its context; steuerbote/ustjahr/rules.py checks those that need no ERiC.

CATALOGUES holds one catalogue for each year of YEARS in steuerbote/ustjahr/years.py. A catalogue that breaks the
rules above is refused when it is built, so a Kennzahl of the Voranmeldung without a line never drops out of the
reconciliation.
"""

import dataclasses
import re
from collections.abc import Iterator
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from steuerbote.ustva.kennzahlen import BALANCE_KENNZAHL, SONDERVORAUSZAHLUNG_KENNZAHL
from steuerbote.ustva.kennzahlen import catalogue_for as ustva_catalogue_for
from steuerbote.ustva.years import UnknownYearError

PLUS, MINUS = 1, -1
RATE_19 = Decimal("19")
RATE_7 = Decimal("7")
# JD sheet "USt2A - Kontexte": Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst, „max. Wiederholbarkeit“ 99.
GRUNDSTUECKE = 99
SOLL = "E3011301"
KZ_816 = "E3011101"
KZ_820 = "E3011401"

_FELDKENNUNG = re.compile(r"E\d{7}")
_AMOUNT_FORMATS = frozenset({"N", "U", "P", "%"})
_WHOLE_EURO_FORMATS = frozenset({"N", "U"})
_SIGNED_FORMATS = frozenset({"N", "P"})

Part = tuple[str, int]


class Format(Enum):
	"""The Formatkennzeichen of the JD (sheet "Allg. Information") that form USt 2 A uses."""

	# „Zahl ohne Nachkommastellen bzw. GeldbetragOhneCent, Mit Vorzeichen, Null erlaubt“
	EUROS = "N"
	# „Zahl ohne Nachkommastellen bzw. GeldbetragOhneCent, Ohne Vorzeichen, Null erlaubt“
	UNSIGNED_EUROS = "U"
	# „Zahl mit 2 Nachkommastellen bzw. GeldbetragMitCent, Mit Vorzeichen, Null erlaubt“
	CENTS = "P"
	# „Zahl mit 2 Nachkommastellen bzw. GeldbetragMitCent, Ohne Vorzeichen, Null ist erlaubt“
	UNSIGNED_CENTS = "%"
	# „JaFeld mit Wert für Ja 1“
	YES = "J"
	# „JaFeld mit Wert für Ja X (Ankreuzfeld)“
	CROSS = "X"
	# „Listenfeld: Textfeld für das eine Auswahlmöglichkeit aus einer Werteliste vorgegeben wird“
	LIST = "H"
	# „Datum mit Format TT.MM.JJJJ“
	DATE = "D"
	# „DatumBereich mit Format TT.MM-TT.MM“
	DAYS = "B"
	# „alle Felder, die kein gesondertes Formatkennzeichen enthalten“
	TEXT = "C"

	@property
	def amount(self) -> bool:
		return self.value in _AMOUNT_FORMATS

	@property
	def whole_euros(self) -> bool:
		return self.value in _WHOLE_EURO_FORMATS

	@property
	def signed(self) -> bool:
		return self.value in _SIGNED_FORMATS


class Scope(Enum):
	"""Whether Steuerbote files a field, and if not, why.

	FOREIGN: a company resident abroad states it (Kz 125, a foreign address, Anlage UN with line 123) and so does a
	Fiskalvertreter (Kz 126, Anlage FV); the settings of Steuerbote describe a company resident in Germany.
	TRAVEL_AND_MARGIN: the taxable sales under § 25 and § 25a UStG, new in lines 37 and 38 for 2026 (BMF letter,
	Tz. 6 and 7), which the Voranmeldung of Steuerbote holds back on watched accounts.
	KLEINUNTERNEHMER: the lines of a Kleinunternehmer (§ 19 UStG), who files no return in the first place,
	„Kleinunternehmer sind von der Übermittlung von Umsatzsteuererklärungen befreit“ (USt 2 E, Zeile 53).
	"""

	IN = "in"
	FOREIGN = "foreign"
	TRAVEL_AND_MARGIN = "travel and margin"
	KLEINUNTERNEHMER = "Kleinunternehmer"


class Source(Enum):
	"""Where the value of a field comes from."""

	# an amount the ledger feeds, through a Kennzahl of the Voranmeldung or an annual-only rule, or a line by hand
	LEDGER = "ledger"
	# the tax of a base at the rate of its line
	RATE = "rate"
	# a sum or difference of other fields of the form
	SUM = "sum"
	# the Vorauszahlungssoll of line 125, from the filed Voranmeldungen
	SOLL = "soll"
	# what the company states: its name and address, flags, dates, texts, the Grundstücke of § 15a UStG
	DETAIL = "detail"


class Severity(Enum):
	"""The Regelart of a rule in the JD: ERiC refuses a filing that breaks a Fehler and notes a Hinweis."""

	ERROR = "Fehler"
	HINT = "Hinweis"


@dataclass(frozen=True, slots=True)
class Field:
	"""A field of USt2A: its Feldkennung, its context below USt2A, its line and label, and how ELSTER takes it.

	``kennzahl`` is the Kennzahl the form prints, ``ustva`` the Kennzahl of the Voranmeldung whose amounts the field
	takes, with ``sign`` -1 where it takes them negated, and ``default`` marks the line a split Kennzahl defaults to.
	``rate`` and ``base`` make a tax that follows from its base; ``tax`` names the tax of a base. ``parts`` are the
	fields a sum adds up, each with its sign. ``paragraph`` is the text field of the line that names the paragraph of
	the amount. ``length`` is the most characters a text takes, ``mandatory`` the Pflichtfeld of the JD, and
	``repeat`` how often the context of the field may repeat.
	"""

	element: str
	context: str
	line: int
	format: Format
	label: str
	kennzahl: str | None = None
	ustva: str | None = None
	sign: int = PLUS
	default: bool = False
	rate: Decimal | None = None
	base: str | None = None
	tax: str | None = None
	parts: tuple[Part, ...] = ()
	paragraph: str | None = None
	scope: Scope = Scope.IN
	length: int | None = None
	mandatory: bool = False
	repeat: int = 1

	def __post_init__(self) -> None:
		if not isinstance(self.element, str) or not _FELDKENNUNG.fullmatch(self.element):
			raise ValueError(f"{self.element!r} is no Feldkennung")
		if self.sign not in (PLUS, MINUS):
			raise ValueError(f"{self.element}: sign must be 1 or -1, not {self.sign}")
		if self.rate is not None and self.format is not Format.CENTS:
			raise ValueError(f"{self.element}: only a tax in cents takes a rate")
		if self.rate is not None and self.base is None:
			raise ValueError(f"{self.element}: a rate needs its base")
		if self.parts and not self.format.amount:
			raise ValueError(f"{self.element}: only an amount is a sum")

	@property
	def source(self) -> Source:
		if self.parts:
			return Source.SUM
		if self.rate is not None:
			return Source.RATE
		if self.element == SOLL:
			return Source.SOLL
		if self.format.amount and self.repeat == 1:
			return Source.LEDGER
		return Source.DETAIL

	@property
	def fed(self) -> bool:
		"""Whether the ledger, or a line by hand, gives the field an amount in a return Steuerbote files."""
		return self.source is Source.LEDGER and self.scope in (Scope.IN, Scope.KLEINUNTERNEHMER)


@dataclass(frozen=True, slots=True)
class Rule:
	"""A rule of the JD by its Fehlercode, its name and its context below USt2A."""

	code: str
	name: str
	context: str
	severity: Severity


@dataclass(frozen=True, slots=True)
class Catalogue:
	"""Form USt 2 A of one year: its fields in the order of the schema, and the rules of its Jahresdokumentation."""

	year: int
	fields: tuple[Field, ...]
	rules: tuple[Rule, ...]
	_fields: ReadOnlyMapping[str, Field] = dataclasses.field(init=False, repr=False, compare=False)
	_kennzahlen: ReadOnlyMapping[str, Field] = dataclasses.field(init=False, repr=False, compare=False)
	_children: ReadOnlyMapping[str, tuple[Field, ...]] = dataclasses.field(
		init=False, repr=False, compare=False
	)
	_rules: ReadOnlyMapping[str, Rule] = dataclasses.field(init=False, repr=False, compare=False)
	_effects: ReadOnlyMapping[str, int] = dataclasses.field(init=False, repr=False, compare=False)

	def __post_init__(self) -> None:
		object.__setattr__(self, "fields", tuple(self.fields))
		object.__setattr__(self, "rules", tuple(self.rules))
		fields: dict[str, Field] = {}
		kennzahlen: dict[str, Field] = {}
		children: dict[str, list[Field]] = {}
		for field in self.fields:
			if field.element in fields:
				raise ValueError(f"{field.element} is listed twice")
			fields[field.element] = field
			if field.kennzahl is not None:
				if field.kennzahl in kennzahlen:
					raise ValueError(f"Kennzahl {field.kennzahl} is listed twice")
				kennzahlen[field.kennzahl] = field
			if field.ustva is not None:
				children.setdefault(field.ustva, []).append(field)
		object.__setattr__(self, "_fields", MappingProxyType(fields))
		object.__setattr__(self, "_kennzahlen", MappingProxyType(kennzahlen))
		object.__setattr__(
			self, "_children", MappingProxyType({number: tuple(lines) for number, lines in children.items()})
		)
		object.__setattr__(self, "_rules", MappingProxyType(_rules(self.rules)))
		self._validate_parts()
		self._validate_paragraphs()
		self._validate_pairs()
		self._validate_defaults()
		self._validate_ustva()
		object.__setattr__(self, "_effects", MappingProxyType(dict(self._expand(KZ_816, PLUS))))

	@property
	def kennzahlen(self) -> ReadOnlyMapping[str, Field]:
		"""The fields with a Kennzahl, by Kennzahl."""
		return self._kennzahlen

	@property
	def split(self) -> tuple[str, ...]:
		"""The Kennzahlen of the Voranmeldung whose amounts go into more than one line."""
		return tuple(number for number, lines in self._children.items() if len(lines) > 1)

	def field(self, element: str) -> Field:
		return self._fields[element]

	def kennzahl(self, number: str) -> Field:
		return self._kennzahlen[number]

	def children(self, ustva: str) -> tuple[Field, ...]:
		"""The lines that take the amounts of a Kennzahl of the Voranmeldung, in the order of the form."""
		return self._children.get(ustva, ())

	def default_child(self, ustva: str) -> Field | None:
		"""The line the amounts of a Kennzahl of the Voranmeldung take by default: its only line, or the marked
		one of a Kennzahl that splits; None for Kz 64 and for a Kennzahl without a line."""
		lines = self.children(ustva)
		if len(lines) == 1:
			return lines[0]
		return next((line for line in lines if line.default), None)

	def rule(self, code: str) -> Rule:
		return self._rules[code]

	def effect(self, element: str) -> int:
		"""How an amount of the field enters Kz 816, the verbleibende Umsatzsteuer: 1, -1, or 0 for none."""
		return self._effects.get(element, 0)

	def _expand(self, element: str, sign: int) -> Iterator[tuple[str, int]]:
		yield element, sign
		for part, part_sign in self.field(element).parts:
			yield from self._expand(part, sign * part_sign)

	def _validate_parts(self) -> None:
		for field in self.fields:
			for part, _sign in field.parts:
				if part not in self._fields or not self._fields[part].format.amount:
					raise ValueError(f"{field.element}: {part} is no amount of the form")

	def _validate_paragraphs(self) -> None:
		for field in self.fields:
			if field.paragraph is None:
				continue
			text = self._fields.get(field.paragraph)
			if text is None or text.format is not Format.TEXT or text.line != field.line:
				raise ValueError(f"{field.element}: {field.paragraph} is no text of line {field.line}")

	def _validate_pairs(self) -> None:
		"""A base and its tax name each other, so that a writer never files one without the other."""
		for field in self.fields:
			if field.tax is not None and self._partner(field.tax, "base") != field.element:
				raise ValueError(f"{field.element} and {field.tax} do not name each other")
			if field.base is not None and self._partner(field.base, "tax") != field.element:
				raise ValueError(f"{field.base} and {field.element} do not name each other")

	def _partner(self, element: str, attribute: str) -> str | None:
		other = self._fields.get(element)
		return None if other is None else getattr(other, attribute)

	def _validate_defaults(self) -> None:
		for number, lines in self._children.items():
			defaults = [line.element for line in lines if line.default]
			if len(lines) == 1 and defaults:
				raise ValueError(
					f"{defaults[0]} is the only line of Kennzahl {number} and needs no default mark"
				)
			if len(defaults) > 1:
				raise ValueError(f"Kennzahl {number} has two default lines: {defaults[0]} and {defaults[1]}")

	def _validate_ustva(self) -> None:
		"""Every amount of the Voranmeldung but Kz 39 and Kz 83 has a line, and a line takes nothing else."""
		ustva = ustva_catalogue_for(self.year)
		amounts = {
			number
			for number, kennzahl in ustva.items()
			if kennzahl.holds_amount and number not in (BALANCE_KENNZAHL, SONDERVORAUSZAHLUNG_KENNZAHL)
		}
		for field in self.fields:
			if field.ustva is not None and field.ustva not in amounts:
				raise ValueError(
					f"{field.element}: Kennzahl {field.ustva} is no amount of the Voranmeldung {self.year} "
					"that a line takes"
				)
		missing = sorted(amounts - self._children.keys(), key=int)
		if missing:
			raise ValueError(f"Kennzahl {missing[0]} of the Voranmeldung {self.year} has no line")


def _rules(rules: tuple[Rule, ...]) -> dict[str, Rule]:
	by_code: dict[str, Rule] = {}
	for rule in rules:
		if rule.code in by_code:
			raise ValueError(f"rule {rule.code} is listed twice")
		by_code[rule.code] = rule
	return by_code


def _sum(*elements: str) -> tuple[Part, ...]:
	return tuple((element, PLUS) for element in elements)


# The fields of USt2A in the order of E50-2026.xsd, as the JD describes them.
_FIELDS_2026 = (
	Field("E3000601", "Ber_Erkl", 3, Format.YES, "Berichtigte Steuererklärung", kennzahl="110"),
	Field("E3000401", "Allg/Unternehmen", 4, Format.TEXT, "Wirtschafts-Identifikationsnummer", length=11),
	Field(
		"E3000901", "Allg/Unternehmen", 5, Format.TEXT, "Name des Unternehmers", length=999, mandatory=True
	),
	Field("E3000902", "Allg/Unternehmen", 6, Format.TEXT, "ggf. abweichender Firmenname", length=999),
	Field("E3001001", "Allg/Unternehmen", 7, Format.TEXT, "Art des Unternehmens", length=999),
	Field("E3001101", "Allg/Unternehmen/Adr", 8, Format.TEXT, "Straße", length=999),
	Field("E3001203", "Allg/Unternehmen/Adr", 9, Format.TEXT, "Hausnummer", length=4),
	Field("E3001204", "Allg/Unternehmen/Adr", 9, Format.TEXT, "Hausnummerzusatz", length=6),
	Field("E3001205", "Allg/Unternehmen/Adr", 9, Format.TEXT, "Adressergänzung", length=25),
	Field("E3001206", "Allg/Unternehmen/Adr", 10, Format.TEXT, "Postleitzahl (Inland)", length=5),
	Field(
		"E3001208",
		"Allg/Unternehmen/Adr",
		10,
		Format.TEXT,
		"Postleitzahl (Ausland)",
		scope=Scope.FOREIGN,
		length=12,
	),
	Field("E3001207", "Allg/Unternehmen/Adr", 11, Format.TEXT, "Ort", length=72),
	Field("E3001403", "Allg/Unternehmen/Adr", 12, Format.TEXT, "Postleitzahl zum Postfach", length=5),
	Field("E3001404", "Allg/Unternehmen/Adr", 12, Format.TEXT, "Postfach", length=6),
	Field(
		"E3001209",
		"Allg/Unternehmen/Adr",
		13,
		Format.TEXT,
		"Staat (falls Anschrift im Ausland)",
		scope=Scope.FOREIGN,
		length=50,
	),
	Field("E3001202", "Allg/Unternehmen/Kontakt", 14, Format.TEXT, "Telefon", length=999),
	Field("E3001301", "Allg/Unternehmen/Kontakt", 15, Format.TEXT, "E-Mail-Adresse", length=999),
	Field(
		"E3001402",
		"Allg/Im_Ausl_ans_Unt",
		16,
		Format.YES,
		"Im Ausland ansässiger Unternehmer Bitte tätigen Sie in diesem Fall auch Angaben auf der Anlage UN.",
		kennzahl="125",
		scope=Scope.FOREIGN,
	),
	Field(
		"E3001801",
		"Allg/Fiskalvertr",
		17,
		Format.YES,
		"Fiskalvertreter Bitte tätigen Sie in diesem Fall auch Angaben auf der Anlage FV.",
		kennzahl="126",
		scope=Scope.FOREIGN,
	),
	Field(
		"E3001601",
		"Allg/Kleinunternehmer",
		18,
		Format.DATE,
		"Wechsel von der Kleinunternehmer-Regelung (§ 19 UStG) zur Regelbesteuerung Datum des Wechsels",
		kennzahl="136",
		scope=Scope.KLEINUNTERNEHMER,
	),
	Field("E3001401", "Allg/Dauer_Unt_Eig", 19, Format.DAYS, "1. Zeitraum"),
	Field("E3001501", "Allg/Dauer_Unt_Eig", 20, Format.DAYS, "2. Zeitraum"),
	Field("E3002203", "Allg/Best_Art", 21, Format.LIST, "Die Steuer wurde berechnet nach", kennzahl="133"),
	Field(
		"E3001701",
		"Allg/Verrech",
		22,
		Format.YES,
		"Verrechnung des Erstattungsbetrages erwünscht / Erstattungsbetrag ist abgetreten (Teilen Sie bitte die Verrechnungswünsche dem Finanzamt gesondert mit).",
		kennzahl="129",
	),
	Field("E3002201", "Allg/Erg_Ang_Erkl", 23, Format.LIST, "In dieser Steuererklärung", kennzahl="500"),
	Field(
		"E3002202",
		"Allg/Erg_Ang_Erkl",
		23,
		Format.TEXT,
		"Ergänzende Angaben in der Steuererklärung",
		length=999,
	),
	Field("E3002509", "Mitwirk/Kanzlei", 128, Format.TEXT, "Bearbeiterkennzeichen", length=55),
	Field("E3002506", "Mitwirk/Kanzlei", 128, Format.TEXT, "Mandantennummer", length=60),
	Field(
		"E3002507",
		"Mitwirk/Kanzlei",
		128,
		Format.TEXT,
		"(Feld wird nicht gedruckt) Ihr Zeichen/gegebenenfalls Zuordnungskriterium für Bescheiddatenübermittlung",
		length=60,
	),
	Field("E3002501", "Mitwirk/Bearb", 128, Format.TEXT, "Name", length=55),
	Field("E3002502", "Mitwirk/Bearb", 128, Format.TEXT, "Vorname", length=55),
	Field("E3002503", "Mitwirk/Adr", 128, Format.TEXT, "Straße, Hausnummer", length=55),
	Field("E3002504", "Mitwirk/Adr", 128, Format.TEXT, "Postleitzahl, Wohnort", length=55),
	Field("E3002505", "Mitwirk/Kontakt", 128, Format.TEXT, "Telefon", length=55),
	Field("E3002508", "Mitwirk/Kontakt", 128, Format.TEXT, "zusätzliche Angaben", length=55),
	Field(
		"E3002602",
		"Mitwirk/Mitwirk_Erkl",
		127,
		Format.YES,
		"Die Steuererklärung wurde unter Mitwirkung einer selbständig und eigenverantwortlich tätigen und zur Hilfeleistung in Steuersachen nach §§ 3 und 4 des Steuerberatungsgesetzes befugten Person oder Vereinigung angefertigt.",
	),
	Field(
		"E3003303",
		"Umsaetze/Tabelle/Ums_allg",
		24,
		Format.EUROS,
		"Lieferungen und sonstige Leistungen zu 19 %",
		kennzahl="177",
		ustva="81",
		default=True,
		tax="E3003304",
	),
	Field(
		"E3003304",
		"Umsaetze/Tabelle/Ums_allg",
		24,
		Format.CENTS,
		"Lieferungen und sonstige Leistungen zu 19 %",
		rate=RATE_19,
		base="E3003303",
	),
	Field(
		"E3003405",
		"Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben",
		25,
		Format.EUROS,
		"Lieferungen nach § 3 Absatz 1b UStG zu 19 %",
		kennzahl="178",
		ustva="81",
		tax="E3003406",
	),
	Field(
		"E3003406",
		"Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben",
		25,
		Format.CENTS,
		"Lieferungen nach § 3 Absatz 1b UStG zu 19 %",
		rate=RATE_19,
		base="E3003405",
	),
	Field(
		"E3003505",
		"Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben",
		26,
		Format.EUROS,
		"Sonstige Leistungen nach § 3 Absatz 9a UStG zu 19 %",
		kennzahl="179",
		ustva="81",
		tax="E3003506",
	),
	Field(
		"E3003506",
		"Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben",
		26,
		Format.CENTS,
		"Sonstige Leistungen nach § 3 Absatz 9a UStG zu 19 %",
		rate=RATE_19,
		base="E3003505",
	),
	Field(
		"E3004401",
		"Umsaetze/Tabelle/Ums_erm",
		27,
		Format.EUROS,
		"Lieferungen und sonstige Leistungen zu 7 %",
		kennzahl="275",
		ustva="86",
		default=True,
		tax="E3004402",
	),
	Field(
		"E3004402",
		"Umsaetze/Tabelle/Ums_erm",
		27,
		Format.CENTS,
		"Lieferungen und sonstige Leistungen zu 7 %",
		rate=RATE_7,
		base="E3004401",
	),
	Field(
		"E3003703",
		"Umsaetze/Tabelle/Ums_erm/Unent_Wertabgaben",
		28,
		Format.EUROS,
		"Lieferungen nach § 3 Absatz 1b UStG zu 7 %",
		kennzahl="195",
		ustva="86",
		tax="E3003704",
	),
	Field(
		"E3003704",
		"Umsaetze/Tabelle/Ums_erm/Unent_Wertabgaben",
		28,
		Format.CENTS,
		"Lieferungen nach § 3 Absatz 1b UStG zu 7 %",
		rate=RATE_7,
		base="E3003703",
	),
	Field(
		"E3003803",
		"Umsaetze/Tabelle/Ums_erm/Unent_Wertabgaben",
		29,
		Format.EUROS,
		"Sonstige Leistungen nach § 3 Absatz 9a UStG zu 7 %",
		kennzahl="196",
		ustva="86",
		tax="E3003804",
	),
	Field(
		"E3003804",
		"Umsaetze/Tabelle/Ums_erm/Unent_Wertabgaben",
		29,
		Format.CENTS,
		"Sonstige Leistungen nach § 3 Absatz 9a UStG zu 7 %",
		rate=RATE_7,
		base="E3003803",
	),
	Field(
		"E3002801",
		"Umsaetze/Tabelle/Ums_erm0",
		30,
		Format.EUROS,
		"Lieferungen und sonstige Leistungen zu 0 %",
		kennzahl="157",
		ustva="87",
		default=True,
	),
	Field(
		"E3002901",
		"Umsaetze/Tabelle/Ums_erm0/Unent_Wertabgaben",
		31,
		Format.EUROS,
		"Lieferungen nach § 3 Absatz 1b UStG zu 0 %",
		kennzahl="158",
		ustva="87",
	),
	Field(
		"E3003001",
		"Umsaetze/Tabelle/Ums_erm0/Unent_Wertabgaben",
		32,
		Format.EUROS,
		"Sonstige Leistungen nach § 3 Absatz 9a UStG zu 0 %",
		kennzahl="159",
		ustva="87",
	),
	Field(
		"E3005001",
		"Umsaetze/Tabelle/Ums_and",
		33,
		Format.EUROS,
		"Umsätze zu anderen Steuersätzen",
		kennzahl="155",
		ustva="35",
		tax="E3005002",
	),
	Field(
		"E3005002",
		"Umsaetze/Tabelle/Ums_and",
		33,
		Format.CENTS,
		"Umsätze zu anderen Steuersätzen",
		kennzahl="156",
		ustva="36",
		base="E3005001",
	),
	Field(
		"E3005201",
		"Umsaetze/Tabelle/Ums_LuF",
		34,
		Format.EUROS,
		"Lieferungen in das übrige Gemeinschaftsgebiet an Abnehmer mit Umsatzsteuer-Identifikationsnummer",
		kennzahl="777",
		ustva="77",
	),
	Field(
		"E3005005",
		"Umsaetze/Tabelle/Ums_LuF",
		35,
		Format.EUROS,
		"Steuerpflichtige Umsätze (einschließlich unentgeltlicher Wertabgaben), für die eine Steuer nach § 24 UStG zu entrichten ist (Sägewerkserzeugnisse, Getränke und alkoholische Flüssigkeiten, z. B. Wein)",
		kennzahl="346",
		ustva="76",
		tax="E3005006",
	),
	Field(
		"E3005006",
		"Umsaetze/Tabelle/Ums_LuF",
		35,
		Format.CENTS,
		"Steuerpflichtige Umsätze (einschließlich unentgeltlicher Wertabgaben), für die eine Steuer nach § 24 UStG zu entrichten ist (Sägewerkserzeugnisse, Getränke und alkoholische Flüssigkeiten, z. B. Wein)",
		kennzahl="347",
		ustva="80",
		base="E3005005",
	),
	Field(
		"E3005801",
		"Umsaetze/Tabelle/Ums_LuF",
		36,
		Format.EUROS,
		"Übrige steuerpflichtige Umsätze land- und forstwirtschaftlicher Betriebe, für die keine Steuer zu entrichten ist",
		kennzahl="361",
	),
	Field(
		"E3005401",
		"Umsaetze/Tabelle/Reiseleistungen",
		37,
		Format.EUROS,
		"Steuerpflichtige Umsätze nach § 25 UStG",
		kennzahl="308",
		tax="E3005402",
		scope=Scope.TRAVEL_AND_MARGIN,
	),
	Field(
		"E3005402",
		"Umsaetze/Tabelle/Reiseleistungen",
		37,
		Format.CENTS,
		"Steuerpflichtige Umsätze nach § 25 UStG",
		kennzahl="309",
		base="E3005401",
		scope=Scope.TRAVEL_AND_MARGIN,
	),
	Field(
		"E3005403",
		"Umsaetze/Tabelle/Differenzbesteuerung",
		38,
		Format.EUROS,
		"Steuerpflichtige Umsätze nach § 25a UStG",
		kennzahl="310",
		tax="E3005404",
		scope=Scope.TRAVEL_AND_MARGIN,
	),
	Field(
		"E3005404",
		"Umsaetze/Tabelle/Differenzbesteuerung",
		38,
		Format.CENTS,
		"Steuerpflichtige Umsätze nach § 25a UStG",
		rate=RATE_19,
		base="E3005403",
		scope=Scope.TRAVEL_AND_MARGIN,
	),
	Field(
		"E3102901",
		"Umsaetze/Tabelle/Wechs_Best_form",
		39,
		Format.UNSIGNED_CENTS,
		"Steuer (Nachsteuer) auf vereinnahmte Anzahlungen infolge des Wechsels der Besteuerungsform",
		kennzahl="317",
		ustva="65",
	),
	Field(
		"E3005901",
		"Umsaetze/Tabelle/Nachst_St_satz_Aend",
		40,
		Format.UNSIGNED_CENTS,
		"Nachsteuer auf versteuerte Anzahlungen und ähnlichem wegen Steuersatzänderung",
		kennzahl="319",
		ustva="65",
		default=True,
	),
	Field(
		"E3006001",
		"Umsaetze/Tabelle/Ums_Sum",
		41,
		Format.CENTS,
		"Summe der Steuer (zu übertragen in Zeile 109)",
		parts=_sum(
			"E3003304",
			"E3003406",
			"E3003506",
			"E3004402",
			"E3003704",
			"E3003804",
			"E3005002",
			"E3005006",
			"E3005402",
			"E3005404",
			"E3102901",
			"E3005901",
		),
	),
	Field(
		"E3103301",
		"Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ig_Lfg",
		42,
		Format.EUROS,
		"an Abnehmer mit Umsatzsteuer-Identifikationsnummer",
		kennzahl="741",
		ustva="41",
	),
	Field(
		"E3103401",
		"Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ig_Lfg",
		43,
		Format.EUROS,
		"neuer Fahrzeuge an Abnehmer ohne Umsatzsteuer-Identifikationsnummer",
		kennzahl="744",
		ustva="44",
	),
	Field(
		"E3103501",
		"Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ig_Lfg",
		44,
		Format.EUROS,
		"neuer Fahrzeuge außerhalb eines Unternehmens (§ 2a UStG)",
		kennzahl="749",
		ustva="49",
	),
	Field(
		"E3103801",
		"Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ums_stfrei_weit",
		45,
		Format.EUROS,
		"Ausfuhrlieferungen (§ 4 Nummer 1 Buchstabe a UStG)",
		kennzahl="752",
		ustva="43",
	),
	Field(
		"E3103901",
		"Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ums_stfrei_weit",
		46,
		Format.TEXT,
		"Umsätze nach §",
		length=999,
	),
	Field(
		"E3103902",
		"Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ums_stfrei_weit",
		46,
		Format.EUROS,
		"Umsätze nach §",
		ustva="43",
		default=True,
		paragraph="E3103901",
	),
	Field(
		"E3104001",
		"Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ums_stfrei_weit",
		47,
		Format.EUROS,
		"Umsätze im Sinne des Offshore-Steuerabkommens, des Zusatzabkommens zum NATO-Truppenstatut und des Ergänzungsabkommens zum Protokoll über die NATO-Hauptquartiere",
		ustva="43",
	),
	Field(
		"E3104002",
		"Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ums_stfrei_weit",
		48,
		Format.EUROS,
		"Umsätze nach Verordnungen der EU",
		ustva="43",
	),
	Field(
		"E3104101",
		"Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ums_stfrei_weit",
		49,
		Format.EUROS,
		"Reiseleistungen nach § 25 Absatz 2 UStG",
		ustva="43",
	),
	Field(
		"E3104201",
		"Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ums_stfrei_weit",
		50,
		Format.EUROS,
		"Summe der Zeilen 46 bis 49",
		kennzahl="237",
		parts=_sum("E3103902", "E3104001", "E3104002", "E3104101"),
	),
	Field(
		"E3104401",
		"Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Nicht_Ges_Ums",
		51,
		Format.EUROS,
		"nach § 4 Nummer 12 UStG (Vermietung und Verpachtung von Grundstücken)",
		kennzahl="286",
		ustva="48",
	),
	Field(
		"E3104501",
		"Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Nicht_Ges_Ums",
		52,
		Format.TEXT,
		"nach § 4 Nummer",
		length=999,
	),
	Field(
		"E3104502",
		"Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Nicht_Ges_Ums",
		52,
		Format.EUROS,
		"nach § 4 Nummer",
		kennzahl="287",
		ustva="48",
		default=True,
		paragraph="E3104501",
	),
	Field(
		"E3104701",
		"Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums",
		53,
		Format.EUROS,
		"nach § 19 Absatz 1 UStG",
		kennzahl="236",
		ustva="48",
		scope=Scope.KLEINUNTERNEHMER,
	),
	Field("E3104901", "Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums", 54, Format.TEXT, "nach §", length=999),
	Field(
		"E3104902",
		"Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums",
		54,
		Format.EUROS,
		"nach §",
		kennzahl="240",
		ustva="48",
		paragraph="E3104901",
	),
	Field(
		"E3100801",
		"Ig_Erw/Tabelle/Erwerbe_25b",
		55,
		Format.EUROS,
		"Innergemeinschaftliche Erwerbe des ersten Abnehmers im Rahmen eines Dreiecksgeschäfts nach § 25b Absatz 3 UStG",
		kennzahl="789",
	),
	Field(
		"E3100901",
		"Ig_Erw/Tabelle/Stfrei",
		56,
		Format.EUROS,
		"von bestimmten Gegenständen und Anlagegold nach §§ 4b und 25c UStG",
		kennzahl="791",
		ustva="91",
	),
	Field(
		"E3100902",
		"Ig_Erw/Tabelle/Stpfl",
		57,
		Format.EUROS,
		"zum Steuersatz von 19 %",
		kennzahl="781",
		ustva="89",
		tax="E3100903",
	),
	Field(
		"E3100903",
		"Ig_Erw/Tabelle/Stpfl",
		57,
		Format.CENTS,
		"zum Steuersatz von 19 %",
		rate=RATE_19,
		base="E3100902",
	),
	Field(
		"E3101301",
		"Ig_Erw/Tabelle/Stpfl",
		58,
		Format.EUROS,
		"zum Steuersatz von 7 %",
		kennzahl="793",
		ustva="93",
		tax="E3101302",
	),
	Field(
		"E3101302",
		"Ig_Erw/Tabelle/Stpfl",
		58,
		Format.CENTS,
		"zum Steuersatz von 7 %",
		rate=RATE_7,
		base="E3101301",
	),
	Field(
		"E3101305",
		"Ig_Erw/Tabelle/Stpfl",
		59,
		Format.EUROS,
		"zum Steuersatz von 0 %",
		kennzahl="780",
		ustva="90",
	),
	Field(
		"E3101303",
		"Ig_Erw/Tabelle/Stpfl",
		60,
		Format.EUROS,
		"zu anderen Steuersätzen",
		kennzahl="798",
		ustva="95",
		tax="E3101304",
	),
	Field(
		"E3101304",
		"Ig_Erw/Tabelle/Stpfl",
		60,
		Format.CENTS,
		"zu anderen Steuersätzen",
		kennzahl="799",
		ustva="98",
		base="E3101303",
	),
	Field(
		"E3101401",
		"Ig_Erw/Tabelle/Stpfl",
		61,
		Format.EUROS,
		"neuer Fahrzeuge (§ 1b Absatz 2 und 3 UStG) von Lieferern ohne Umsatzsteuer-Identifikationsnummer zum allgemeinen Steuersatz",
		kennzahl="794",
		ustva="94",
		tax="E3101402",
	),
	Field(
		"E3101402",
		"Ig_Erw/Tabelle/Stpfl",
		61,
		Format.CENTS,
		"neuer Fahrzeuge (§ 1b Absatz 2 und 3 UStG) von Lieferern ohne Umsatzsteuer-Identifikationsnummer zum allgemeinen Steuersatz",
		kennzahl="796",
		ustva="96",
		base="E3101401",
	),
	Field(
		"E3101501",
		"Ig_Erw/Tabelle/Ig_Erw_Sum",
		62,
		Format.CENTS,
		"Summe der Steuer (zu übertragen in Zeile 110)",
		parts=_sum("E3100903", "E3101302", "E3101304", "E3101402"),
	),
	Field(
		"E3102804",
		"Auslag_13a/Tabelle",
		63,
		Format.EUROS,
		"Lieferungen, die der Auslagerung vorangegangen sind (§ 27 Absatz 40a UStG)",
		kennzahl="852",
		tax="E3102805",
	),
	Field(
		"E3102805",
		"Auslag_13a/Tabelle",
		63,
		Format.CENTS,
		"Lieferungen, die der Auslagerung vorangegangen sind (§ 27 Absatz 40a UStG)",
		kennzahl="853",
		ustva="69",
		base="E3102804",
	),
	Field(
		"E3102904",
		"Auslag_13a/Tabelle/Auslag_13a_Sum",
		64,
		Format.CENTS,
		"Summe der Steuer (zu übertragen in Zeile 111)",
		parts=_sum("E3102805"),
	),
	Field(
		"E3101801",
		"Ig_Drei/Tabelle/Lfg_erst_Abn",
		65,
		Format.EUROS,
		"Lieferungen des ersten Abnehmers",
		kennzahl="742",
		ustva="42",
	),
	Field(
		"E3101701",
		"Ig_Drei/Tabelle/Lfg_letzt_Abn",
		66,
		Format.EUROS,
		"zum Steuersatz von 19 %",
		kennzahl="751",
		tax="E3101702",
	),
	Field(
		"E3101702",
		"Ig_Drei/Tabelle/Lfg_letzt_Abn",
		66,
		Format.CENTS,
		"zum Steuersatz von 19 %",
		ustva="69",
		base="E3101701",
	),
	Field(
		"E3102301",
		"Ig_Drei/Tabelle/Lfg_letzt_Abn",
		67,
		Format.EUROS,
		"zum Steuersatz von 7 %",
		kennzahl="746",
		tax="E3102302",
	),
	Field(
		"E3102302",
		"Ig_Drei/Tabelle/Lfg_letzt_Abn",
		67,
		Format.CENTS,
		"zum Steuersatz von 7 %",
		ustva="69",
		base="E3102301",
	),
	Field(
		"E3102305",
		"Ig_Drei/Tabelle/Lfg_letzt_Abn",
		68,
		Format.EUROS,
		"zum Steuersatz von 0 %",
		kennzahl="750",
	),
	Field(
		"E3102303",
		"Ig_Drei/Tabelle/Lfg_letzt_Abn",
		69,
		Format.EUROS,
		"zu anderen Steuersätzen",
		kennzahl="747",
		tax="E3102304",
	),
	Field(
		"E3102304",
		"Ig_Drei/Tabelle/Lfg_letzt_Abn",
		69,
		Format.CENTS,
		"zu anderen Steuersätzen",
		kennzahl="748",
		ustva="69",
		base="E3102303",
	),
	Field(
		"E3102401",
		"Ig_Drei/Tabelle/Ig_Drei_Sum",
		70,
		Format.CENTS,
		"Summe der Steuer (zu übertragen in Zeile 112)",
		parts=_sum("E3101702", "E3102302", "E3102304"),
	),
	Field(
		"E3102205",
		"Ums_13b/Tabelle",
		71,
		Format.EUROS,
		"Sonstige Leistungen nach § 3a Absatz 2 UStG eines im übrigen Gemeinschaftsgebiet ansässigen Unternehmers (§ 13b Absatz 1 UStG)",
		kennzahl="846",
		ustva="46",
		tax="E3102206",
	),
	Field(
		"E3102206",
		"Ums_13b/Tabelle",
		71,
		Format.CENTS,
		"Sonstige Leistungen nach § 3a Absatz 2 UStG eines im übrigen Gemeinschaftsgebiet ansässigen Unternehmers (§ 13b Absatz 1 UStG)",
		kennzahl="847",
		ustva="47",
		base="E3102205",
	),
	Field(
		"E3102307",
		"Ums_13b/Tabelle",
		72,
		Format.EUROS,
		"Umsätze, die unter das GrEStG fallen (§ 13b Absatz 2 Nummer 3 UStG)",
		kennzahl="873",
		ustva="73",
		tax="E3102308",
	),
	Field(
		"E3102308",
		"Ums_13b/Tabelle",
		72,
		Format.CENTS,
		"Umsätze, die unter das GrEStG fallen (§ 13b Absatz 2 Nummer 3 UStG)",
		kennzahl="874",
		ustva="74",
		base="E3102307",
	),
	Field(
		"E3102503",
		"Ums_13b/Tabelle",
		73,
		Format.EUROS,
		"Andere Leistungen (§ 13b Absatz 2 Nummer 1, 2, 4 bis 12 UStG)",
		kennzahl="877",
		ustva="84",
		tax="E3102504",
	),
	Field(
		"E3102504",
		"Ums_13b/Tabelle",
		73,
		Format.CENTS,
		"Andere Leistungen (§ 13b Absatz 2 Nummer 1, 2, 4 bis 12 UStG)",
		kennzahl="878",
		ustva="85",
		base="E3102503",
	),
	Field(
		"E3102601",
		"Ums_13b/Tabelle/Ums_13b_Sum",
		74,
		Format.CENTS,
		"Summe der Steuer (zu übertragen in Zeile 113)",
		parts=_sum("E3102206", "E3102308", "E3102504"),
	),
	Field(
		"E3105201",
		"Erg_Ang_Ums/Tabelle",
		75,
		Format.EUROS,
		"Umsätze, die auf Grund eines Verzichts auf Steuerbefreiung (§ 9 UStG) als steuerpflichtig behandelt worden sind (in Abschnitt B enthalten)",
	),
	Field(
		"E3105301",
		"Erg_Ang_Ums/Tabelle",
		76,
		Format.EUROS,
		"Steuerpflichtige Umsätze des leistenden Unternehmers, für die der Leistungsempfänger die Steuer nach § 13b Absatz 5 UStG schuldet",
		kennzahl="209",
		ustva="60",
	),
	Field(
		"E3105101",
		"Erg_Ang_Ums/Tabelle",
		77,
		Format.EUROS,
		"Telekommunikations-, Rundfunk- und Fernsehdienstleistungen sowie auf elektronischem Weg erbrachte sonstige Leistungen an im übrigen Gemeinschaftsgebiet ansässige Nichtunternehmer sowie innergemeinschaftliche Fernverkäufe in das übrige Gemeinschaftsgebiet unter der Voraussetzung des § 3a Absatz 5 Sätze 3 und 4 UStG und § 3c Absatz 4 Sätze 1 und 2 UStG (in Abschnitt B oder C enthalten)",
		kennzahl="213",
	),
	Field(
		"E3105102",
		"Erg_Ang_Ums/Tabelle",
		78,
		Format.EUROS,
		"Telekommunikations-, Rundfunk- und Fernsehdienstleistungen sowie auf elektronischem Weg erbrachte sonstige Leistungen an im übrigen Gemeinschaftsgebiet ansässige Nichtunternehmer sowie innergemeinschaftliche Fernverkäufe in das übrige Gemeinschaftsgebiet unter der Voraussetzung des § 3a Absatz 5 Sätze 3 und 4 UStG und § 3c Absatz 4 Sätze 1 und 2 UStG (in anderen EU-Mitgliedstaaten zu versteuern)",
		kennzahl="214",
		ustva="45",
	),
	Field(
		"E3105602",
		"Erg_Ang_Ums/Tabelle",
		79,
		Format.EUROS,
		"Nicht steuerbare Geschäftsveräußerung im Ganzen gemäß § 1 Absatz 1a UStG",
		kennzahl="211",
	),
	Field(
		"E3105702",
		"Erg_Ang_Ums/Tabelle",
		80,
		Format.EUROS,
		"Nicht steuerbare sonstige Leistungen gemäß § 18b Satz 1 Nummer 2 UStG",
		kennzahl="721",
		ustva="21",
	),
	Field(
		"E3105801",
		"Erg_Ang_Ums/Tabelle",
		81,
		Format.EUROS,
		"Übrige nicht steuerbare Umsätze (Leistungsort nicht im Inland)",
		kennzahl="205",
		ustva="45",
		default=True,
	),
	Field(
		"E3105901",
		"Erg_Ang_Ums/Tabelle",
		82,
		Format.EUROS,
		"In den Zeilen 78, 80 und 81 enthaltene Umsätze, die nach § 15 Absatz 2 und 3 UStG den Vorsteuerabzug ausschließen",
		kennzahl="204",
	),
	Field(
		"E3106001",
		"Erg_Ang_Ums/Tabelle",
		83,
		Format.EUROS,
		"Auf den inländischen Streckenanteil entfallende Umsätze grenzüberschreitender Personenbeförderungen im Luftverkehr (§ 26 Absatz 3 UStG)",
		kennzahl="212",
	),
	Field(
		"E3106101",
		"Erg_Ang_Ums/Tabelle",
		84,
		Format.UNSIGNED_EUROS,
		"Minderung der Bemessungsgrundlage nach § 17 Absatz 1 Satz 1 in Verbindung mit Absatz 2 Nummer 1 Satz 1 UStG für uneinbringliche Forderungsentgelte (in Abschnitt B enthalten)",
		kennzahl="650",
		ustva="50",
	),
	Field(
		"E3006201",
		"Abz_VoSt/Tabelle",
		85,
		Format.CENTS,
		"Vorsteuerbeträge aus Rechnungen von anderen Unternehmern (§ 15 Absatz 1 Satz 1 Nummer 1 UStG)",
		kennzahl="320",
		ustva="66",
		default=True,
	),
	Field(
		"E3006301",
		"Abz_VoSt/Tabelle",
		86,
		Format.CENTS,
		"Vorsteuerbeträge aus innergemeinschaftlichen Erwerben von Gegenständen (§ 15 Absatz 1 Satz 1 Nummer 3 UStG)",
		kennzahl="761",
		ustva="61",
	),
	Field(
		"E3006401",
		"Abz_VoSt/Tabelle",
		87,
		Format.CENTS,
		"Entstandene Einfuhrumsatzsteuer (§ 15 Absatz 1 Satz 1 Nummer 2 UStG)",
		kennzahl="762",
		ustva="62",
	),
	Field(
		"E3006503",
		"Abz_VoSt/Tabelle",
		88,
		Format.CENTS,
		"Vorsteuerabzug für die Steuer, die der Abnehmer als Auslagerer schuldet (§ 27 Absatz 40a UStG)",
		kennzahl="466",
		ustva="66",
	),
	Field(
		"E3006502",
		"Abz_VoSt/Tabelle",
		89,
		Format.CENTS,
		"Vorsteuerbeträge aus Leistungen im Sinne des § 13b UStG (§ 15 Absatz 1 Satz 1 Nummer 4 UStG)",
		kennzahl="467",
		ustva="67",
	),
	Field(
		"E3006601",
		"Abz_VoSt/Tabelle",
		90,
		Format.CENTS,
		"Vorsteuerbeträge nach dem Durchschnittssatz für bestimmte Körperschaften, Personenvereinigungen und Vermögensmassen (§ 23a UStG)",
		kennzahl="334",
		ustva="63",
	),
	Field(
		"E3006701",
		"Abz_VoSt/Tabelle",
		91,
		Format.CENTS,
		"Vorsteuerabzug für innergemeinschaftliche Lieferungen neuer Fahrzeuge außerhalb eines Unternehmens (§ 2a UStG) sowie von Kleinunternehmern im Sinne des § 19 Absatz 1 UStG (§ 15 Absatz 4a UStG)",
		kennzahl="759",
		ustva="59",
	),
	Field(
		"E3006801",
		"Abz_VoSt/Tabelle",
		92,
		Format.CENTS,
		"Vorsteuerbeträge aus innergemeinschaftlichen Dreiecksgeschäften (§ 25b Absatz 5 UStG)",
		kennzahl="760",
		ustva="66",
	),
	Field(
		"E3006901",
		"Abz_VoSt/Tabelle/Abz_VoSt_Sum",
		93,
		Format.CENTS,
		"Summe der Vorsteuerbeträge (zu übertragen in Zeile 115)",
		parts=_sum(
			"E3006201", "E3006301", "E3006401", "E3006503", "E3006502", "E3006601", "E3006701", "E3006801"
		),
	),
	Field(
		"E3007001",
		"Abz_VoSt/Tabelle/Erg_Ang",
		94,
		Format.UNSIGNED_CENTS,
		"Minderung der abziehbaren Vorsteuerbeträge nach § 17 Absatz 1 Satz 2 in Verbindung mit Absatz 2 Nummer 1 Satz 1 UStG (in den Zeilen 85, 90 und 91 enthalten)",
		kennzahl="637",
		ustva="37",
	),
	Field(
		"E3007301",
		"Ber_VoSt_15a/Grdst_erstm_Verw",
		95,
		Format.YES,
		"Sind im Kalenderjahr $VZ$ Grundstücke, Grundstücksteile, Gebäude oder Gebäudeteile, für die Vorsteuer abgezogen worden ist, erstmals tatsächlich verwendet worden?",
		kennzahl="370",
	),
	Field(
		"E3007401",
		"Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst",
		95,
		Format.TEXT,
		"Lage des Grundstücks oder Gebäudes",
		length=999,
		repeat=GRUNDSTUECKE,
	),
	Field(
		"E3007402",
		"Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst",
		95,
		Format.DATE,
		"Zeitpunkt der erstmaligen tatsächlichen Verwendung",
		repeat=GRUNDSTUECKE,
	),
	Field(
		"E3007403",
		"Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst",
		95,
		Format.TEXT,
		"Art der Verwendung im Erstjahr",
		length=999,
		repeat=GRUNDSTUECKE,
	),
	Field(
		"E3007404",
		"Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst",
		95,
		Format.UNSIGNED_CENTS,
		"Umfang der Verwendung im Erstjahr",
		repeat=GRUNDSTUECKE,
	),
	Field(
		"E3007405",
		"Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst",
		95,
		Format.EUROS,
		"insgesamt angefallene Vorsteuer",
		repeat=GRUNDSTUECKE,
	),
	Field(
		"E3007406",
		"Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst",
		95,
		Format.EUROS,
		"in den Vorjahren - Investitionsphase - bereits abgezogene Vorsteuer",
		repeat=GRUNDSTUECKE,
	),
	Field(
		"E3007601",
		"Ber_VoSt_15a/Aend_Verh",
		96,
		Format.YES,
		"1. Grundstücken, Grundstücksteilen, Gebäuden oder Gebäudeteilen, die innerhalb der letzten 10 Jahre erstmals tatsächlich und nicht nur einmalig zur Ausführung von Umsätzen verwendet worden sind?",
		kennzahl="371",
	),
	Field(
		"E3008501",
		"Ber_VoSt_15a/Aend_Verh",
		97,
		Format.YES,
		"2. anderen Wirtschaftsgütern und sonstigen Leistungen, die innerhalb der letzten 5 Jahre erstmals tatsächlich und nicht nur einmalig zur Ausführung von Umsätzen verwendet worden sind?",
		kennzahl="372",
	),
	Field(
		"E3008601",
		"Ber_VoSt_15a/Aend_Verh",
		98,
		Format.YES,
		"3. Wirtschaftsgütern und sonstigen Leistungen, die nur einmalig zur Ausführung von Umsätzen verwendet worden sind?",
		kennzahl="369",
	),
	Field("E3007801", "Ber_VoSt_15a/Grund_Aend_Verh", 99, Format.CROSS, "Veräußerung"),
	Field(
		"E3007802",
		"Ber_VoSt_15a/Grund_Aend_Verh",
		99,
		Format.CROSS,
		"Lieferung im Sinne des § 3 Absatz 1b UStG",
	),
	Field(
		"E3007803",
		"Ber_VoSt_15a/Grund_Aend_Verh",
		99,
		Format.CROSS,
		"Wechsel der Besteuerungsform, § 15a Absatz 7 UStG",
	),
	Field(
		"E3007804",
		"Ber_VoSt_15a/Grund_Aend_Verh",
		100,
		Format.CROSS,
		"Wechsel der Besteuerungsform im Rahmen der Kleinunternehmer-Regelung",
		scope=Scope.KLEINUNTERNEHMER,
	),
	Field(
		"E3007901", "Ber_VoSt_15a/Grund_Aend_Verh/Nutz_aend", 101, Format.CROSS, "Nutzungsänderung, und zwar"
	),
	Field(
		"E3008001",
		"Ber_VoSt_15a/Grund_Aend_Verh/Nutz_aend",
		102,
		Format.CROSS,
		"Übergang von steuerpflichtiger zu steuerfreier Vermietung oder umgekehrt beziehungsweise Änderung des Verwendungsschlüssels bei gemischt genutzten Grundstücken (insbesondere bei Mieterwechsel).",
	),
	Field(
		"E3008202",
		"Ber_VoSt_15a/Grund_Aend_Verh/Nutz_aend",
		103,
		Format.CROSS,
		"steuerfreie Vermietung bisher eigengewerblich genutzter Räume oder umgekehrt; Übergang von einer Vermietung für NATO- oder ähnliche Zwecke zu einer nach § 4 Nummer 12 UStG steuerfreien Vermietung.",
	),
	Field(
		"E3008401",
		"Ber_VoSt_15a/Grund_Aend_Verh/Nutz_aend",
		104,
		Format.CROSS,
		"Andere Gründe für die geänderte Beurteilung des Vorsteuerabzugs:",
	),
	Field("E3008402", "Ber_VoSt_15a/Grund_Aend_Verh/Nutz_aend", 104, Format.TEXT, "Begründung", length=999),
	Field(
		"E3008701",
		"Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle",
		105,
		Format.UNSIGNED_CENTS,
		"zu 1. (z. B. Grundstücke, § 15a Absatz 1 Satz 2 UStG)",
		ustva="64",
	),
	Field(
		"E3008702",
		"Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle",
		105,
		Format.UNSIGNED_CENTS,
		"zu 1. (z. B. Grundstücke, § 15a Absatz 1 Satz 2 UStG)",
		ustva="64",
		sign=MINUS,
	),
	Field(
		"E3008801",
		"Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle",
		106,
		Format.UNSIGNED_CENTS,
		"zu 2. (z. B. andere Wirtschaftsgüter, § 15a Absatz 1 Satz 1 UStG)",
		ustva="64",
	),
	Field(
		"E3008802",
		"Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle",
		106,
		Format.UNSIGNED_CENTS,
		"zu 2. (z. B. andere Wirtschaftsgüter, § 15a Absatz 1 Satz 1 UStG)",
		ustva="64",
		sign=MINUS,
	),
	Field(
		"E3008803",
		"Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle",
		107,
		Format.UNSIGNED_CENTS,
		"zu 3. (z. B. Wirtschaftsgüter, § 15a Absatz 2 UStG)",
		ustva="64",
	),
	Field(
		"E3008804",
		"Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle",
		107,
		Format.UNSIGNED_CENTS,
		"zu 3. (z. B. Wirtschaftsgüter, § 15a Absatz 2 UStG)",
		ustva="64",
		sign=MINUS,
	),
	Field(
		"E3008901",
		"Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum",
		108,
		Format.UNSIGNED_CENTS,
		"Summe",
		kennzahl="357",
		parts=_sum("E3008701", "E3008801", "E3008803"),
	),
	Field(
		"E3008902",
		"Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum",
		108,
		Format.UNSIGNED_CENTS,
		"Summe",
		kennzahl="359",
		parts=_sum("E3008702", "E3008802", "E3008804"),
	),
	Field(
		"E3009201",
		"Berech_USt/Tabelle",
		109,
		Format.CENTS,
		"Umsatzsteuer auf steuerpflichtige Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben (aus Zeile 41)",
		parts=_sum("E3006001"),
	),
	Field(
		"E3009401",
		"Berech_USt/Tabelle",
		110,
		Format.CENTS,
		"Umsatzsteuer auf innergemeinschaftliche Erwerbe (aus Zeile 62)",
		parts=_sum("E3101501"),
	),
	Field(
		"E3009602",
		"Berech_USt/Tabelle",
		111,
		Format.CENTS,
		"Umsatzsteuer, die vom Auslagerer oder Lagerhalter geschuldet wird (§ 27 Absatz 40a UStG) (aus Zeile 64)",
		parts=_sum("E3102904"),
	),
	Field(
		"E3009501",
		"Berech_USt/Tabelle",
		112,
		Format.CENTS,
		"Umsatzsteuer, die vom letzten Abnehmer im innergemeinschaftlichen Dreiecksgeschäft geschuldet wird (§ 25b Absatz 2 UStG) (aus Zeile 70)",
		parts=_sum("E3102401"),
	),
	Field(
		"E3009502",
		"Berech_USt/Tabelle",
		113,
		Format.CENTS,
		"Umsatzsteuer, die vom Leistungsempfänger nach § 13b UStG geschuldet wird (aus Zeile 74)",
		parts=_sum("E3102601"),
	),
	Field(
		"E3009801",
		"Berech_USt/Tabelle",
		114,
		Format.CENTS,
		"Zwischensumme",
		parts=_sum("E3009201", "E3009401", "E3009501", "E3009502", "E3009602"),
	),
	Field(
		"E3009901",
		"Berech_USt/Tabelle",
		115,
		Format.CENTS,
		"Abziehbare Vorsteuerbeträge (aus Zeile 93)",
		parts=_sum("E3006901"),
	),
	Field(
		"E3010001",
		"Berech_USt/Tabelle",
		116,
		Format.UNSIGNED_CENTS,
		"Vorsteuerbeträge, die auf Grund des § 15a UStG nachträglich abziehbar sind (aus Zeile 108)",
		parts=_sum("E3008901"),
	),
	Field(
		"E3010201",
		"Berech_USt/Tabelle",
		117,
		Format.CENTS,
		"Verbleibender Betrag",
		parts=(("E3009801", PLUS), ("E3009901", MINUS), ("E3010001", MINUS)),
	),
	Field(
		"E3009701",
		"Berech_USt/Tabelle",
		118,
		Format.UNSIGNED_CENTS,
		"Vorsteuerbeträge, die auf Grund des § 15a UStG zurückzuzahlen sind (aus Zeile 108)",
		parts=_sum("E3008902"),
	),
	Field(
		"E3010301",
		"Berech_USt/Tabelle",
		119,
		Format.CENTS,
		"In Rechnungen unrichtig oder unberechtigt ausgewiesene Steuerbeträge (§ 14c UStG) sowie Steuerbeträge, die nach § 6a Absatz 4 Satz 2 UStG geschuldet werden",
		kennzahl="318",
		ustva="69",
		default=True,
	),
	Field(
		"E3010401",
		"Berech_USt/Tabelle",
		120,
		Format.CENTS,
		"Steuerbeträge, die nach § 17 Absatz 1 Satz 7 UStG geschuldet werden",
		kennzahl="331",
		ustva="69",
	),
	Field(
		"E3010501",
		"Berech_USt/Tabelle",
		121,
		Format.CENTS,
		"Steuer- und Vorsteuerbeträge, die auf frühere Besteuerungszeiträume entfallen (nur für Kleinunternehmer, die § 19 Absatz 1 UStG anwenden)",
		kennzahl="391",
		scope=Scope.KLEINUNTERNEHMER,
	),
	Field(
		"E3010601",
		"Berech_USt/Tabelle",
		122,
		Format.CENTS,
		"Umsatzsteuer Überschuss",
		parts=_sum("E3010201", "E3009701", "E3010301", "E3010401", "E3010501"),
	),
	Field(
		"E3010602",
		"Berech_USt/Tabelle",
		123,
		Format.CENTS,
		"Anrechenbare Beträge (aus Zeile 18 der Anlage UN)",
		scope=Scope.FOREIGN,
	),
	Field(
		"E3011101",
		"Berech_USt/Tabelle/Verbl_USt",
		124,
		Format.CENTS,
		"Verbleibende Umsatzsteuer Verbleibender Überschuss",
		kennzahl="816",
		parts=(("E3010601", PLUS), ("E3010602", MINUS)),
		mandatory=True,
	),
	Field(
		"E3011301",
		"Berech_USt/Tabelle/Verbl_USt",
		125,
		Format.CENTS,
		"Vorauszahlungssoll $VZ$ (einschließlich Sondervorauszahlung)",
		mandatory=True,
	),
	Field(
		"E3011401",
		"Berech_USt/Tabelle/Zahl_Erstatt",
		126,
		Format.CENTS,
		"Noch an die Finanzkasse zu entrichten – Abschlusszahlung - Erstattungsanspruch",  # noqa: RUF001 - the JD
		kennzahl="820",
		parts=(("E3011101", PLUS), ("E3011301", MINUS)),
		mandatory=True,
	),
)

# The rules of the JD sheet "USt2A - Regeln", in its order.
_RULES_2026 = (
	Rule("30002", "USt_2024_30002", "Ber_Erkl", Severity.HINT),
	Rule("30096", "USt_30096", "Allg/Unternehmen", Severity.ERROR),
	Rule("30008", "USt_2025_30008", "Allg/Unternehmen", Severity.HINT),
	Rule("30092", "USt_30092", "Allg/Unternehmen/Adr", Severity.ERROR),
	Rule("30094", "USt_30094", "Allg/Unternehmen/Adr", Severity.ERROR),
	Rule("30095", "USt_30095", "Allg/Unternehmen/Adr", Severity.ERROR),
	Rule("30097", "USt_30097", "Allg/Unternehmen/Adr", Severity.HINT),
	Rule("30675", "USt_30675", "Allg/Unternehmen/Adr", Severity.ERROR),
	Rule("30677", "USt_2026_30677", "Allg/Unternehmen/Adr", Severity.HINT),
	Rule("30087", "USt_30087", "Allg/Im_Ausl_ans_Unt", Severity.ERROR),
	Rule("30088", "USt_30088", "Allg/Im_Ausl_ans_Unt", Severity.ERROR),
	Rule("30938", "USt_2020_30938", "Allg/Fiskalvertr", Severity.ERROR),
	Rule("30939", "USt_2020_30939", "Allg/Fiskalvertr", Severity.ERROR),
	Rule("30006", "USt_2025_30006", "Allg/Kleinunternehmer", Severity.ERROR),
	Rule("30007", "USt_2026_30007", "Allg/Kleinunternehmer", Severity.ERROR),
	Rule("30081", "USt_30081", "Allg/Dauer_Unt_Eig", Severity.ERROR),
	Rule("30086", "USt_30086", "Allg/Dauer_Unt_Eig", Severity.ERROR),
	Rule("30089", "USt_30089", "Allg/Dauer_Unt_Eig", Severity.HINT),
	Rule("30676", "USt_30676", "Allg/Dauer_Unt_Eig", Severity.HINT),
	Rule("30093", "USt_30093", "Allg/Best_Art", Severity.ERROR),
	Rule("30098", "USt_2019_30098", "Allg/Best_Art", Severity.HINT),
	Rule("30011", "USt_2022_30011", "Allg/Verrech", Severity.ERROR),
	Rule("30917", "USt_30917", "Allg/Erg_Ang_Erkl", Severity.ERROR),
	Rule("30937", "USt_2020_30937", "Allg/Erg_Ang_Erkl", Severity.HINT),
	Rule("30944", "USt_2021_30944", "Mitwirk/Bearb", Severity.ERROR),
	Rule("30945", "USt_2021_30945", "Mitwirk/Bearb", Severity.HINT),
	Rule("30639", "USt_30639", "Umsaetze/Tabelle/Ums_allg", Severity.ERROR),
	Rule("30649", "USt_30649", "Umsaetze/Tabelle/Ums_allg", Severity.ERROR),
	Rule("30640", "USt_30640", "Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben", Severity.ERROR),
	Rule("30641", "USt_30641", "Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben", Severity.ERROR),
	Rule("30650", "USt_30650", "Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben", Severity.ERROR),
	Rule("30651", "USt_30651", "Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben", Severity.ERROR),
	Rule("30642", "USt_30642", "Umsaetze/Tabelle/Ums_erm", Severity.ERROR),
	Rule("30652", "USt_30652", "Umsaetze/Tabelle/Ums_erm", Severity.ERROR),
	Rule("30643", "USt_30643", "Umsaetze/Tabelle/Ums_erm/Unent_Wertabgaben", Severity.ERROR),
	Rule("30644", "USt_30644", "Umsaetze/Tabelle/Ums_erm/Unent_Wertabgaben", Severity.ERROR),
	Rule("30653", "USt_30653", "Umsaetze/Tabelle/Ums_erm/Unent_Wertabgaben", Severity.ERROR),
	Rule("30654", "USt_30654", "Umsaetze/Tabelle/Ums_erm/Unent_Wertabgaben", Severity.ERROR),
	Rule("30091", "USt_30091", "Umsaetze/Tabelle/Ums_and", Severity.ERROR),
	Rule("30916", "USt_30916", "Umsaetze/Tabelle/Ums_and", Severity.HINT),
	Rule("30655", "USt_30655", "Umsaetze/Tabelle/Ums_LuF", Severity.ERROR),
	Rule("30946", "USt_2019_30946", "Umsaetze/Tabelle/Ums_LuF", Severity.HINT),
	Rule("30009", "USt_2026_30009", "Umsaetze/Tabelle/Reiseleistungen", Severity.ERROR),
	Rule("30010", "USt_2026_30010", "Umsaetze/Tabelle/Differenzbesteuerung", Severity.ERROR),
	Rule("30012", "USt_2026_30012", "Umsaetze/Tabelle/Differenzbesteuerung", Severity.ERROR),
	Rule("30142", "USt_30142", "Umsaetze/Tabelle/Ums_Sum", Severity.ERROR),
	Rule("30232", "USt_30232", "Umsaetze/Tabelle/Ums_Sum", Severity.ERROR),
	Rule("30314", "USt_30314", "Umsaetze/Tabelle/Ums_Sum", Severity.ERROR),
	Rule("30364", "USt_30364", "Umsaetze/Tabelle/Ums_Sum", Severity.ERROR),
	Rule("30900", "USt_30900", "Umsaetze/Tabelle/Ums_Sum", Severity.ERROR),
	Rule("30345", "USt_30345", "Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ums_stfrei_weit", Severity.ERROR),
	Rule("30415", "USt_30415", "Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ums_stfrei_weit", Severity.ERROR),
	Rule("30804", "USt_30804", "Ums_stfrei/Tabelle/Mit_VoSt_Abz/Ums_stfrei_weit", Severity.ERROR),
	Rule("30705", "USt_30705", "Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums", Severity.ERROR),
	Rule("30720", "USt_30720", "Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums", Severity.ERROR),
	Rule("30725", "USt_30725", "Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums", Severity.ERROR),
	Rule("30730", "USt_30730", "Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums", Severity.ERROR),
	Rule("30412", "USt_2025_30412", "Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums", Severity.ERROR),
	Rule("30413", "USt_2025_30413", "Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums", Severity.ERROR),
	Rule("30414", "USt_2025_30414", "Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums", Severity.ERROR),
	Rule("30422", "USt_2025_30422", "Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums", Severity.ERROR),
	Rule("30423", "USt_2025_30423", "Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums", Severity.ERROR),
	Rule("30424", "USt_2025_30424", "Ums_stfrei/Tabelle/Ohne_VoSt_Abz/Ges_Ums", Severity.ERROR),
	Rule("30013", "USt_2026_30013", "Ig_Erw/Tabelle/Erwerbe_25b", Severity.ERROR),
	Rule("30014", "USt_2026_30014", "Ig_Erw/Tabelle/Erwerbe_25b", Severity.ERROR),
	Rule("30115", "USt_30115", "Ig_Erw/Tabelle/Stpfl", Severity.ERROR),
	Rule("30120", "USt_30120", "Ig_Erw/Tabelle/Stpfl", Severity.ERROR),
	Rule("30656", "USt_30656", "Ig_Erw/Tabelle/Stpfl", Severity.ERROR),
	Rule("30658", "USt_30658", "Ig_Erw/Tabelle/Stpfl", Severity.ERROR),
	Rule("30669", "USt_30669", "Ig_Erw/Tabelle/Stpfl", Severity.ERROR),
	Rule("30670", "USt_30670", "Ig_Erw/Tabelle/Stpfl", Severity.ERROR),
	Rule("30342", "USt_30342", "Ig_Erw/Tabelle/Ig_Erw_Sum", Severity.ERROR),
	Rule("30392", "USt_30392", "Ig_Erw/Tabelle/Ig_Erw_Sum", Severity.ERROR),
	Rule("30800", "USt_30800", "Ig_Erw/Tabelle/Ig_Erw_Sum", Severity.ERROR),
	Rule("30131", "USt_30131", "Auslag_13a", Severity.ERROR),
	Rule("30354", "USt_30354", "Auslag_13a/Tabelle/Auslag_13a_Sum", Severity.ERROR),
	Rule("30404", "USt_30404", "Auslag_13a/Tabelle/Auslag_13a_Sum", Severity.ERROR),
	Rule("30801", "USt_30801", "Auslag_13a/Tabelle/Auslag_13a_Sum", Severity.ERROR),
	Rule("30125", "USt_30125", "Ig_Drei/Tabelle/Lfg_letzt_Abn", Severity.ERROR),
	Rule("30660", "USt_30660", "Ig_Drei/Tabelle/Lfg_letzt_Abn", Severity.ERROR),
	Rule("30661", "USt_30661", "Ig_Drei/Tabelle/Lfg_letzt_Abn", Severity.ERROR),
	Rule("30671", "USt_30671", "Ig_Drei/Tabelle/Lfg_letzt_Abn", Severity.ERROR),
	Rule("30672", "USt_30672", "Ig_Drei/Tabelle/Lfg_letzt_Abn", Severity.ERROR),
	Rule("30356", "USt_30356", "Ig_Drei/Tabelle/Ig_Drei_Sum", Severity.ERROR),
	Rule("30406", "USt_30406", "Ig_Drei/Tabelle/Ig_Drei_Sum", Severity.ERROR),
	Rule("30802", "USt_30802", "Ig_Drei/Tabelle/Ig_Drei_Sum", Severity.ERROR),
	Rule("30137", "USt_30137", "Ums_13b", Severity.ERROR),
	Rule("30139", "USt_30139", "Ums_13b", Severity.ERROR),
	Rule("30147", "USt_30147", "Ums_13b", Severity.ERROR),
	Rule("30358", "USt_30358", "Ums_13b/Tabelle/Ums_13b_Sum", Severity.ERROR),
	Rule("30408", "USt_30408", "Ums_13b/Tabelle/Ums_13b_Sum", Severity.ERROR),
	Rule("30803", "USt_30803", "Ums_13b/Tabelle/Ums_13b_Sum", Severity.ERROR),
	Rule("30807", "USt_30807", "Erg_Ang_Ums", Severity.HINT),
	Rule("30809", "USt_30809", "Erg_Ang_Ums", Severity.ERROR),
	Rule("30812", "USt_30812", "Erg_Ang_Ums", Severity.ERROR),
	Rule("30813", "USt_30813", "Erg_Ang_Ums", Severity.ERROR),
	Rule("30940", "USt_2021_30940", "Erg_Ang_Ums", Severity.ERROR),
	Rule("30941", "USt_2021_30941", "Erg_Ang_Ums", Severity.HINT),
	Rule("30815", "USt_2024_30815", "Erg_Ang_Ums", Severity.HINT),
	Rule("30740", "USt_30740", "Erg_Ang_Ums", Severity.ERROR),
	Rule("30745", "USt_30745", "Erg_Ang_Ums", Severity.ERROR),
	Rule("30755", "USt_30755", "Erg_Ang_Ums", Severity.ERROR),
	Rule("30816", "USt_2025_30816", "Erg_Ang_Ums", Severity.HINT),
	Rule("30015", "USt_2026_30015", "Erg_Ang_Ums/Tabelle", Severity.ERROR),
	Rule("30016", "USt_2026_30016", "Erg_Ang_Ums/Tabelle", Severity.HINT),
	Rule("30017", "USt_2025_30017", "Erg_Ang_Ums/Tabelle", Severity.ERROR),
	Rule("30948", "USt_2024_30948", "Abz_VoSt/Tabelle", Severity.HINT),
	Rule("30949", "USt_2024_30949", "Abz_VoSt/Tabelle", Severity.HINT),
	Rule("30951", "USt_2024_30951", "Abz_VoSt/Tabelle", Severity.HINT),
	Rule("30150", "USt_30150", "Abz_VoSt/Tabelle/Abz_VoSt_Sum", Severity.ERROR),
	Rule("30240", "USt_30240", "Abz_VoSt/Tabelle/Abz_VoSt_Sum", Severity.ERROR),
	Rule("30317", "USt_30317", "Abz_VoSt/Tabelle/Abz_VoSt_Sum", Severity.ERROR),
	Rule("30367", "USt_30367", "Abz_VoSt/Tabelle/Abz_VoSt_Sum", Severity.ERROR),
	Rule("30901", "USt_30901", "Abz_VoSt/Tabelle/Abz_VoSt_Sum", Severity.ERROR),
	Rule("30312", "USt_2022_30312", "Abz_VoSt/Tabelle/Abz_VoSt_Sum", Severity.HINT),
	Rule("30942", "USt_2021_30942", "Abz_VoSt/Tabelle/Erg_Ang", Severity.ERROR),
	Rule("30943", "USt_2021_30943", "Abz_VoSt/Tabelle/Erg_Ang", Severity.HINT),
	Rule("30925", "USt_30925", "Ber_VoSt_15a/Aend_Verh", Severity.HINT),
	Rule("30926", "USt_30926", "Ber_VoSt_15a/Aend_Verh", Severity.HINT),
	Rule("30927", "USt_30927", "Ber_VoSt_15a/Aend_Verh", Severity.HINT),
	Rule("30928", "USt_30928", "Ber_VoSt_15a/Aend_Verh", Severity.HINT),
	Rule("30929", "USt_30929", "Ber_VoSt_15a/Aend_Verh", Severity.HINT),
	Rule("30930", "USt_30930", "Ber_VoSt_15a/Aend_Verh", Severity.HINT),
	Rule("30932", "USt_30932", "Ber_VoSt_15a/Aend_Verh", Severity.HINT),
	Rule("30931", "USt_30931", "Ber_VoSt_15a/Grund_Aend_Verh", Severity.HINT),
	Rule("30710", "USt_30710", "Ber_VoSt_15a/Grund_Aend_Verh", Severity.ERROR),
	Rule("30933", "USt_30933", "Ber_VoSt_15a/Grund_Aend_Verh/Nutz_aend", Severity.HINT),
	Rule("30934", "USt_30934", "Ber_VoSt_15a/Grund_Aend_Verh/Nutz_aend", Severity.HINT),
	Rule("30935", "USt_30935", "Ber_VoSt_15a/Grund_Aend_Verh/Nutz_aend", Severity.HINT),
	Rule("30936", "USt_30936", "Ber_VoSt_15a/Grund_Aend_Verh/Nutz_aend", Severity.HINT),
	Rule("30160", "USt_30160", "Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum", Severity.ERROR),
	Rule("30170", "USt_30170", "Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum", Severity.ERROR),
	Rule("30250", "USt_30250", "Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum", Severity.ERROR),
	Rule("30260", "USt_30260", "Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum", Severity.ERROR),
	Rule("30321", "USt_30321", "Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum", Severity.ERROR),
	Rule("30331", "USt_30331", "Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum", Severity.ERROR),
	Rule("30371", "USt_30371", "Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum", Severity.ERROR),
	Rule("30381", "USt_30381", "Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum", Severity.ERROR),
	Rule("30902", "USt_30902", "Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum", Severity.ERROR),
	Rule("30903", "USt_30903", "Ber_VoSt_15a/VoSt_Ber_Betr/Tabelle/VoSt_Ber_Betr_Sum", Severity.ERROR),
	Rule("30225", "USt_30225", "Berech_USt", Severity.ERROR),
	Rule("30313", "USt_30313", "Berech_USt", Severity.ERROR),
	Rule("30452", "USt_30452", "Berech_USt", Severity.ERROR),
	Rule("30460", "USt_30460", "Berech_USt", Severity.ERROR),
	Rule("30470", "USt_30470", "Berech_USt", Severity.ERROR),
	Rule("30480", "USt_30480", "Berech_USt", Severity.ERROR),
	Rule("30630", "USt_30630", "Berech_USt", Severity.ERROR),
	Rule("30632", "USt_30632", "Berech_USt", Severity.ERROR),
	Rule("30634", "USt_30634", "Berech_USt", Severity.ERROR),
	Rule("30905", "USt_30905", "Berech_USt", Severity.ERROR),
	Rule("30907", "USt_30907", "Berech_USt", Severity.ERROR),
	Rule("30909", "USt_30909", "Berech_USt", Severity.ERROR),
	Rule("30912", "USt_30912", "Berech_USt", Severity.ERROR),
	Rule("30913", "USt_30913", "Berech_USt", Severity.ERROR),
	Rule("30914", "USt_30914", "Berech_USt", Severity.ERROR),
	Rule("30180", "USt_30180", "Berech_USt", Severity.ERROR),
	Rule("30270", "USt_30270", "Berech_USt", Severity.ERROR),
	Rule("30490", "USt_30490", "Berech_USt", Severity.ERROR),
	Rule("30190", "USt_30190", "Berech_USt", Severity.ERROR),
	Rule("30280", "USt_30280", "Berech_USt", Severity.ERROR),
	Rule("30500", "USt_30500", "Berech_USt", Severity.ERROR),
	Rule("30146", "USt_30146", "Berech_USt", Severity.ERROR),
	Rule("30283", "USt_30283", "Berech_USt", Severity.ERROR),
	Rule("30503", "USt_30503", "Berech_USt", Severity.ERROR),
	Rule("30193", "USt_30193", "Berech_USt", Severity.ERROR),
	Rule("30311", "USt_30311", "Berech_USt", Severity.ERROR),
	Rule("30540", "USt_30540", "Berech_USt", Severity.ERROR),
	Rule("30070", "USt_30070", "Berech_USt/Tabelle/Verbl_USt", Severity.ERROR),
	Rule("30636", "USt_30636", "Berech_USt/Tabelle/Verbl_USt", Severity.ERROR),
	Rule("30910", "USt_30910", "Berech_USt/Tabelle/Verbl_USt", Severity.ERROR),
	Rule("30915", "USt_30915", "Berech_USt/Tabelle/Verbl_USt", Severity.ERROR),
	Rule("30449", "USt_30449", "Berech_USt/Tabelle/Verbl_USt", Severity.ERROR),
	Rule("30620", "USt_30620", "Berech_USt/Tabelle/Zahl_Erstatt", Severity.ERROR),
	Rule("30638", "USt_30638", "Berech_USt/Tabelle/Zahl_Erstatt", Severity.ERROR),
	Rule("30911", "USt_30911", "Berech_USt/Tabelle/Zahl_Erstatt", Severity.ERROR),
)

CATALOGUES: MappingProxyType[int, Catalogue] = MappingProxyType(
	{2026: Catalogue(2026, _FIELDS_2026, _RULES_2026)}
)


def catalogue_for(year: int) -> Catalogue:
	"""The catalogue of form USt 2 A for the given year."""
	try:
		return CATALOGUES[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in sorted(CATALOGUES))
		raise UnknownYearError(f"no catalogue of form USt 2 A for {year}; known years: {known}") from None
