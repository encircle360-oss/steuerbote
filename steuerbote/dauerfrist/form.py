"""Form USt 1 H as ELSTER takes it: the two contexts of the Datenart UStVA for the Dauerfristverlängerung.

Sources are form USt 1 H 2026 of the BMF letter of 29 December 2025 (GZ III C 3 - S 7344/00039/007/036) and the
ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/): UStVA-2026.xsd, cited as JD
Jahresdokumentation_UStVA_2026.ods with its sheets "Anmeldungssteuern - Felder", "Anmeldungssteuern - Regeln"
and "Allg. Information" and its rules by Fehlercode, and as HB the ERiC-Entwicklerhandbuch.

The Datenart UStVA holds form USt 1 H as two contexts next to the Umsatzsteuervoranmeldung, and a filing holds
exactly one of the three (JD 110085099):

- Dauerfristverlaengerung, the Antrag of a company that files quarterly: „Soll eine Dauerfristverlängerung ohne
  Sondervorauszahlung abgegeben werden, ist nur Kz 09 zu füllen. Eine Berichtigung dieser Fallkonstellation
  ist nicht möglich.“ (HB 8.5.1) The schema of 2026 adds Kz 500 with its Begründung.
- Umsatzsteuersondervorauszahlung, the Anmeldung der Sondervorauszahlung of a company that files monthly, which
  is its Antrag as well (§ 48 Absatz 1 Satz 4 UStDV): Kz 38 and the yes fields Kz 10, Kz 26 and Kz 29.

Kz 09 is the Hersteller-ID, which ERiC requires in both contexts (JD 110085045). The XML writer adds it, as it
adds the Steuernummer and the Wirtschafts-Identifikationsnummer of the filer; Ust1H holds what the form itself
says. The fields and rules of a year are data, taken from the JD of that year, and the tests compare them with
it: the JD of 2025 still had Kz 23 where 2026 has Kz 500.
"""

import re
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from steuerbote.ustva.period import Rhythm
from steuerbote.ustva.rounding import ZERO, require_decimal, to_full_euros

YES = "1"
# The JD writes its expressions for Java, whose \Q...\E quotes what Python's re.escape does.
_JAVA_QUOTE = re.compile(r"\\Q(.*?)\\E")

NO_LAYOUT = "Steuerbote does not know form USt 1 H for {0} yet."
NOT_IN_CONTEXT = "The context {0} of form USt 1 H carries no Kennzahl {1}."
SONDERVORAUSZAHLUNG_MISSING = "The Anmeldung der Sondervorauszahlung needs Kennzahl 38, 0 if need be."
NOT_WHOLE_EUROS = "Kennzahl 38 takes whole euros, not {0}."
NEGATIVE = "Kennzahl {0} takes no negative amount: {1}."
TOO_MANY_DIGITS = "Kennzahl {0} has more digits than ELSTER takes: {1}."
OFFSET_WITHOUT_CORRECTION = (
	"Kennzahl 29 is only filed with a corrected Anmeldung der Sondervorauszahlung (Kz 10)."
)
UNKNOWN_CODE = "Kennzahl 500 takes 1, 2, 3 or 4, not {0}."
CODE_WITHOUT_BEGRUENDUNG = "Kennzahl 500 needs a Begründung."
BEGRUENDUNG_WITHOUT_CODE = "A Begründung is only filed with Kennzahl 500."
BEGRUENDUNG_TOO_LONG = "The Begründung of Kennzahl 500 has {0} characters, ELSTER takes at most {1}."
MESSAGES = (
	NO_LAYOUT,
	NOT_IN_CONTEXT,
	SONDERVORAUSZAHLUNG_MISSING,
	NOT_WHOLE_EUROS,
	NEGATIVE,
	TOO_MANY_DIGITS,
	OFFSET_WITHOUT_CORRECTION,
	UNKNOWN_CODE,
	CODE_WITHOUT_BEGRUENDUNG,
	BEGRUENDUNG_WITHOUT_CODE,
	BEGRUENDUNG_TOO_LONG,
)


class Context(Enum):
	"""The two contexts of form USt 1 H, named as their elements in the schema."""

	DAUERFRISTVERLAENGERUNG = "Dauerfristverlaengerung"
	UMSATZSTEUERSONDERVORAUSZAHLUNG = "Umsatzsteuersondervorauszahlung"

	@classmethod
	def for_rhythm(cls, rhythm: Rhythm) -> Context:
		"""A monthly filer files the Sondervorauszahlung, a quarterly one the Antrag alone.

		The Sondervorauszahlung is the condition of the Dauerfristverlängerung for a company „der die
		Voranmeldungen monatlich zu übermitteln hat“ (§ 47 Absatz 1 Satz 1 UStDV). Form USt 1 H says to a
		quarterly filer: „Eine Sondervorauszahlung ist nicht zu berechnen und anzumelden.“
		"""
		if Rhythm(rhythm) is Rhythm.MONTHLY:
			return cls.UMSATZSTEUERSONDERVORAUSZAHLUNG
		return cls.DAUERFRISTVERLAENGERUNG

	@property
	def with_sondervorauszahlung(self) -> bool:
		return self is Context.UMSATZSTEUERSONDERVORAUSZAHLUNG


class Format(Enum):
	"""The Formatkennzeichen of the JD (sheet "Allg. Information") that form USt 1 H uses."""

	# „Steuernummer im ELSTER-Steuernummerformat, nur Ziffern erlaubt, genau dreizehn Stellen“
	STEUERNUMMER = "A"
	# „alle Felder, die kein gesondertes Formatkennzeichen enthalten“
	GENERAL = "C"
	# „Listenfeld: Textfeld für das eine Auswahlmöglichkeit aus einer Werteliste vorgegeben wird“
	LIST = "H"
	# „JaFeld mit Wert für Ja 1“
	YES = "J"
	# „Zahl ohne Nachkommastellen bzw. GeldbetragOhneCent, Ohne Vorzeichen, Null erlaubt“
	WHOLE_EUROS = "U"


@dataclass(frozen=True, slots=True)
class Field:
	"""A field of a context as the JD describes it, ``line`` being the Vordruckzeile of USt 1 H.

	``regex`` is the column "Format als regulärer Ausdruck" as the JD writes it, matched against the whole
	text, and ``min_length`` and ``max_length`` are its columns of the lengths, None where they are empty.
	"""

	element: str
	label: str
	format: Format
	regex: str
	min_length: int | None
	max_length: int | None
	line: int | None = None

	def accepts(self, text: str) -> bool:
		"""Whether ELSTER takes the text in this field."""
		if self.min_length is not None and len(text) < self.min_length:
			return False
		if self.max_length is not None and len(text) > self.max_length:
			return False
		# Java's \d means the digits 0 to 9 only.
		return re.fullmatch(_python_regex(self.regex), text, re.ASCII) is not None


class Severity(Enum):
	"""The Regelart of a rule in the JD: ERiC refuses a filing that breaks a Fehler and notes a Hinweis."""

	ERROR = "Fehler"
	HINT = "Hinweis"


@dataclass(frozen=True, slots=True)
class Rule:
	"""A rule of the JD by its Fehlercode and name; ``context`` is None for a rule on the whole Steuerfall."""

	code: str
	name: str
	severity: Severity
	context: Context | None = None


@dataclass(frozen=True, slots=True)
class Layout:
	"""Form USt 1 H of one year: the fields of each context in the order of the schema, and the rules."""

	year: int
	fields: ReadOnlyMapping[Context, tuple[Field, ...]]
	rules: tuple[Rule, ...]

	def __post_init__(self) -> None:
		object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))

	def elements(self, context: Context) -> tuple[str, ...]:
		return tuple(field.element for field in self.fields[context])

	def field(self, context: Context, element: str) -> Field:
		for field in self.fields[context]:
			if field.element == element:
				return field
		raise KeyError(f"{context.value} has no field {element}")

	def rule(self, context: Context | None, name: str) -> Rule:
		for rule in self.rules:
			if rule.context is context and rule.name == name:
				return rule
		raise KeyError(f"{context} has no rule {name}")


DF = Context.DAUERFRISTVERLAENGERUNG
SVZ = Context.UMSATZSTEUERSONDERVORAUSZAHLUNG

# Both contexts start with these fields (JD sheet "Anmeldungssteuern - Felder").
_FIELDS_OF_THE_FILER_2026 = (
	Field("Jahr", "Jahr", Format.GENERAL, r"\d\d\d\d", None, 4),
	Field("Steuernummer", "Steuernummer", Format.STEUERNUMMER, "([0-9]{4})0[0-9]{8}", 13, 13),
	Field("WIdNr", "Wirtschafts-Identifikationsnummer", Format.GENERAL, "DE[0-9]{9}", 11, 11, line=2),
	Field(
		"Kz09",
		"Hersteller-ID",
		Format.GENERAL,
		r"^(?=.{5,95}$)([0-9]{5})|([0-9]{5}\*.{0,85}\*.{0,85}\*.{0,85}\*.{0,85}\*.{0,85})",
		5,
		95,
		line=6,
	),
)
_SUPPLEMENTARY_FIELDS_2026 = (
	Field("Kz500", "In dieser Steueranmeldung", Format.LIST, r"\Q1\E|\Q2\E|\Q3\E|\Q4\E", None, None, line=12),
	Field(
		"Kz500_Begruendung",
		"Ergänzende Angaben zur Steueranmeldung",
		Format.GENERAL,
		".{1,180}",
		1,
		180,
		line=12,
	),
)
_SONDERVORAUSZAHLUNG_FIELDS_2026 = (
	Field("Kz10", "Berichtigte Anmeldung", Format.YES, "1", None, None, line=7),
	Field(
		"Kz26",
		"Das SEPA-Lastschriftmandat soll ausnahmsweise (z. B. wegen Verrechnungswünschen) für die "
		"Sondervorauszahlung dieses Jahres nicht verwendet werden",
		Format.YES,
		"1",
		None,
		None,
		line=11,
	),
	Field(
		"Kz29",
		"Verrechnung des Erstattungsbetrags erwünscht / Erstattungsbetrag ist abgetreten",
		Format.YES,
		"1",
		None,
		None,
		line=10,
	),
	Field(
		"Kz38",
		"Davon 1/11 = Sondervorauszahlung 2026",
		Format.WHOLE_EUROS,
		r"^(?=.{1,13}$)(?!0\d)\d{1,13}$",
		1,
		13,
		line=9,
	),
)

# The rules of the JD sheet "Anmeldungssteuern - Regeln" on the two contexts, in its order.
_RULES_2026 = (
	Rule("110085099", "UStVA_Df_oder_Svz", Severity.ERROR),
	Rule("110085046", "Df_Kz09_Laenge", Severity.ERROR),
	Rule("110085046", "Svz_Kz09_Laenge", Severity.ERROR),
	Rule("110085044", "Steuernummer_Pflichtfeld", Severity.ERROR, DF),
	Rule("110085045", "Df_Kz09_Pflichtfeld", Severity.ERROR, DF),
	Rule("110085130", "Df_Jahr_gleich_VZ", Severity.ERROR, DF),
	Rule("110085048", "Df_Jahr_Pflichtfeld", Severity.ERROR, DF),
	Rule("11085154", "WIdNr_Hinweis", Severity.HINT, DF),
	Rule("11085137", "Kz500_Begr_Gemeinsam", Severity.ERROR, DF),
	Rule("110085049", "Kz500_Hinweis", Severity.HINT, DF),
	Rule("110085044", "Steuernummer_Pflichtfeld", Severity.ERROR, SVZ),
	Rule("110085045", "Svz_Kz09_Pflichtfeld", Severity.ERROR, SVZ),
	Rule("110085143", "Svz_Kz38_Pflichtfeld", Severity.ERROR, SVZ),
	Rule("110085131", "Svz_Jahr_gleich_VZ", Severity.ERROR, SVZ),
	Rule("110085048", "Svz_Jahr_Pflichtfeld", Severity.ERROR, SVZ),
	Rule("11085150", "Svz_Kz29_ohne_Kz10", Severity.ERROR, SVZ),
	Rule("11085154", "WIdNr_Hinweis", Severity.HINT, SVZ),
	Rule("11085155", "Kz26_Hinweis", Severity.HINT, SVZ),
	Rule("11085137", "Kz500_Begr_Gemeinsam", Severity.ERROR, SVZ),
	Rule("110085049", "Kz500_Hinweis", Severity.HINT, SVZ),
)

LAYOUTS: MappingProxyType[int, Layout] = MappingProxyType(
	{
		2026: Layout(
			year=2026,
			fields={
				DF: (*_FIELDS_OF_THE_FILER_2026, *_SUPPLEMENTARY_FIELDS_2026),
				SVZ: (
					*_FIELDS_OF_THE_FILER_2026,
					*_SONDERVORAUSZAHLUNG_FIELDS_2026,
					*_SUPPLEMENTARY_FIELDS_2026,
				),
			},
			rules=_RULES_2026,
		)
	}
)
LATEST_YEAR = max(LAYOUTS)


class FormError(ValueError):
	"""Form USt 1 H cannot be filed as it is.

	``template`` and ``values`` make the message, so that a caller can translate the template before formatting
	it; ``rule`` is the rule of the JD that the form breaks, if the error is one.
	"""

	def __init__(self, template: str, *values: object, rule: Rule | None = None) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values
		self.rule = rule


def layout_for(year: int) -> Layout:
	"""The layout of the form of ``year``.

	ELSTER takes form USt 1 H only in the schema of its own year (JD 110085130 and 110085131).
	"""
	if not isinstance(year, int) or isinstance(year, bool):
		raise TypeError(f"year must be an int, not {type(year).__name__}")
	try:
		return LAYOUTS[year]
	except KeyError:
		raise FormError(NO_LAYOUT, year) from None


@dataclass(frozen=True, slots=True)
class Ust1H:
	"""One form USt 1 H as filed: the Antrag of a quarterly filer or the Anmeldung of a monthly one.

	``sondervorauszahlung`` is Kz 38 in whole euros, which the Anmeldung needs, 0 if need be (JD 110085143).
	``corrected``, ``no_sepa_mandate`` and ``offset_requested`` are the yes fields Kz 10, Kz 26 and Kz 29; Kz 29
	goes only with Kz 10 (JD 11085150). The Antrag alone carries none of these four. ``supplementary_code`` and
	``begruendung`` are Kz 500 and its Begründung, which both contexts take and which go together (JD
	11085137); the Begründung is kept on one line without blanks at either end, and an empty key or Begründung
	counts as none.
	"""

	year: int
	context: Context
	sondervorauszahlung: Decimal | None = None
	corrected: bool = False
	no_sepa_mandate: bool = False
	offset_requested: bool = False
	supplementary_code: str | None = None
	begruendung: str | None = None

	def __post_init__(self) -> None:
		layout = layout_for(self.year)
		context = Context(self.context)
		object.__setattr__(self, "context", context)
		for name in ("corrected", "no_sepa_mandate", "offset_requested"):
			if not isinstance(getattr(self, name), bool):
				raise TypeError(f"{name} must be a bool, not {type(getattr(self, name)).__name__}")
		elements = layout.elements(context)
		for element, given in (
			("Kz10", self.corrected),
			("Kz26", self.no_sepa_mandate),
			("Kz29", self.offset_requested),
			("Kz38", self.sondervorauszahlung is not None),
		):
			if given and element not in elements:
				raise FormError(NOT_IN_CONTEXT, context.value, element.removeprefix("Kz"))
		if "Kz38" in elements:
			object.__setattr__(self, "sondervorauszahlung", _kz38(layout, context, self.sondervorauszahlung))
		if self.offset_requested and not self.corrected:
			raise FormError(OFFSET_WITHOUT_CORRECTION, rule=layout.rule(context, "Svz_Kz29_ohne_Kz10"))
		code, begruendung = _supplementary(layout, context, self.supplementary_code, self.begruendung)
		object.__setattr__(self, "supplementary_code", code)
		object.__setattr__(self, "begruendung", begruendung)

	def texts(self) -> dict[str, str]:
		"""What the form fills itself, by element and as ELSTER takes it, in the order of the schema.

		Steuernummer, WIdNr and Kz 09 come from the filer and the Hersteller-ID; the XML writer adds them.
		"""
		values = {
			"Jahr": str(self.year),
			"Kz10": YES if self.corrected else None,
			"Kz26": YES if self.no_sepa_mandate else None,
			"Kz29": YES if self.offset_requested else None,
			"Kz38": None if self.sondervorauszahlung is None else format(self.sondervorauszahlung, "f"),
			"Kz500": self.supplementary_code,
			"Kz500_Begruendung": self.begruendung,
		}
		elements = layout_for(self.year).elements(self.context)
		return {element: text for element in elements if (text := values.get(element)) is not None}

	@property
	def hints(self) -> tuple[Rule, ...]:
		"""The rules of kind Hinweis that the form sets off in ERiC.

		The hint on a missing Wirtschafts-Identifikationsnummer (JD 11085154) depends on the filer.
		"""
		triggered = {
			"Kz26_Hinweis": self.no_sepa_mandate,
			"Kz500_Hinweis": self.supplementary_code is not None,
		}
		rules = layout_for(self.year).rules
		return tuple(
			rule for rule in rules if rule.context is self.context and triggered.get(rule.name, False)
		)


def _kz38(layout: Layout, context: Context, amount: Decimal | None) -> Decimal:
	if amount is None:
		raise FormError(SONDERVORAUSZAHLUNG_MISSING, rule=layout.rule(context, "Svz_Kz38_Pflichtfeld"))
	if not require_decimal(amount).is_finite():
		raise ValueError(f"Kennzahl 38 is not an amount: {amount}")
	euros = to_full_euros(amount)
	if euros != amount:
		raise FormError(NOT_WHOLE_EUROS, format(amount, "f"))
	if euros < ZERO:
		raise FormError(NEGATIVE, "38", format(euros, "f"))
	if not layout.field(context, "Kz38").accepts(format(euros, "f")):
		raise FormError(TOO_MANY_DIGITS, "38", format(euros, "f"))
	return euros


def _supplementary(
	layout: Layout, context: Context, code: str | None, begruendung: str | None
) -> tuple[str | None, str | None]:
	key = _text(code, "Kennzahl 500") or None
	text = " ".join(_text(begruendung, "The Begründung of Kennzahl 500").split()) or None
	together = layout.rule(context, "Kz500_Begr_Gemeinsam")
	if key is None:
		if text is not None:
			raise FormError(BEGRUENDUNG_WITHOUT_CODE, rule=together)
		return None, None
	if not layout.field(context, "Kz500").accepts(key):
		raise FormError(UNKNOWN_CODE, key)
	if text is None:
		raise FormError(CODE_WITHOUT_BEGRUENDUNG, rule=together)
	field = layout.field(context, "Kz500_Begruendung")
	if not field.accepts(text):
		raise FormError(BEGRUENDUNG_TOO_LONG, len(text), field.max_length)
	return key, text


def _text(value: str | None, name: str) -> str:
	if value is None:
		return ""
	if not isinstance(value, str):
		raise TypeError(f"{name} must be text, not {type(value).__name__}")
	return value


def _python_regex(regex: str) -> str:
	return _JAVA_QUOTE.sub(lambda match: re.escape(match.group(1)), regex)
