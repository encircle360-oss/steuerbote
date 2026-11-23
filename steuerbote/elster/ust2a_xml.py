"""The Umsatzsteuererklärung as ELSTER XML: the element E50 of the schema of its year, with form USt2A and the Vorsatz.

Sources are the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/), cited as HB for
ERiC-Entwicklerhandbuch.pdf and JD for Jahresdokumentation_E50_2026.ods (Versionslabel 9.0) with its sheets „Allg.
Information“, „USt2A - Felder“ and „USt2A - Kontexte“, the schema E50-2026.xsd and the example
Beispiele/USt_2026.xml; and the ELSTER help „Benutzeranleitung zum Hochladen von Formulardaten“
(https://www.elster.de/eportal/helpGlobal?themaGlobal=ustva_upload, read 23 November 2026).

ERiC takes the tree as the Nutzdaten of a DatenTeil, in UTF-8 (HB 5.3.2), in the Datenart USt of its year
(steuerbote.eric.datenart.ust): to_nutzdaten writes it, steuerbote/eric/header.py puts it into the DatenTeil, and
EricCreateTH adds the TransferHeader. The whole envelope of envelope.py (envelope_for) serves the schema tests only.
There is no import file: Mein ELSTER takes uploads only „für alle angebotenen Jahresversionen der
Umsatzsteuer-Voranmeldung ( UStVA ) und der Mitteilung nach § 146a Abs. 4 AO“ (help, „Allgemeines“), so the
Umsatzsteuererklärung goes into its form there by hand, from the print format.

The rules:

- E50 in the namespace and the version of its year holds form USt2A and then the Vorsatz, the two Pflichtvordrucke of
  „Allg. Information“ (FORMS). Anlage UN and Anlage FV stay out: Steuerbote files for a company resident in Germany,
  so the fields of a company resident abroad and of a Fiskalvertreter are not filed either, nor the sales under §§ 25
  and 25a UStG of lines 37 and 38 (Scope in steuerbote/ustjahr/form.py).
- The fields of USt2A follow the xs:sequence of the schema, which is the order of the catalogue of the year
  (steuerbote/ustjahr/form.py), each in its context. A context without a value is left out, since the schema
  requires none.
- A value is written by its Formatkennzeichen (value_text in steuerbote/elster/erklaerung.py): a decimal comma, a
  leading minus where the format takes one, no negative zero, whole euros or exactly two decimals, 1 for yes and X
  for a cross, TT.MM.JJJJ for a date, TT.MM-TT.MM for a span within the year, a value of its list, and a text in the
  character set Standard_E_V2 on one line of at most its length. The digits before the comma are those of the
  „Format als regulärer Ausdruck“ of the JD (DIGITS_BEFORE_THE_COMMA and MORE_DIGITS_BEFORE_THE_COMMA in
  steuerbote/ustjahr/rules.py), and every value has to match that pattern itself (SCHEMAS): the house number and the
  Postfach take digits only, a Postleitzahl five German digits, the W-IdNr. DE and nine digits.
- The writer files what it is given, the values rules.check() takes (steuerbote/ustjahr/rules.py): the amounts of
  calculation.entries(), which leaves out the zeros the return does not file, always files Kz 816, line 125 and Kz
  820 (rules 30070, 30915 and 30620) and a base with its tax, and files Kz 177 = 0 with its tax for a year without
  amounts (rule 30449, unverified), and the details of the company. entries() takes the amounts as the form takes
  them, so this writer rounds nothing.
- Line 95 repeats for up to 99 Grundstücke (JD „USt2A - Kontexte“, Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst, „max.
  Wiederholbarkeit“ 99): each Grundstück is a context Ang_Grdst of its own, after the question of Kz 370.
- The Vorsatz comes last, with the Unterfallart 50 and the year of the Datenart (steuerbote/elster/vorsatz.py).

A year is the catalogue of its form with the patterns and lists of its JD: SCHEMAS holds one FormCatalogue
(steuerbote/elster/erklaerung.py) per year of the catalogues.
"""

import re
from collections.abc import Mapping as ReadOnlyMapping
from collections.abc import Sequence
from types import MappingProxyType

from lxml import etree

from steuerbote.elster.erklaerung import NOT_IN_FORMAT, Field, Form, FormCatalogue, python_pattern, value_text
from steuerbote.elster.ustva_xml import XmlError, serialized
from steuerbote.elster.vorsatz import Vorsatz, append_to
from steuerbote.eric.datenart import Datenart, ust
from steuerbote.ustjahr.form import CATALOGUES, Catalogue, Format, Scope
from steuerbote.ustjahr.form import Field as AnnualField
from steuerbote.ustjahr.rules import DIGITS_BEFORE_THE_COMMA, MORE_DIGITS_BEFORE_THE_COMMA

MAIN_FORM = "USt2A"
FORMS = (Form(MAIN_FORM, mandatory=True), Form("UN"), Form("FV"), Form("Vorsatz", mandatory=True))
"""The Vordrucke of „Allg. Information“, each at most once: „USt2A - max. lfd. Nr. Vordruck: 1 - Pflichtvordruck“, UN,
FV, „Vorsatz - max. lfd. Nr. Vordruck: 1 - Pflichtvordruck“."""
NOT_FILED = frozenset({Scope.FOREIGN, Scope.TRAVEL_AND_MARGIN})
"""The fields Steuerbote does not file; a Kleinunternehmer's are filed when the ledger feeds them."""
YEAR_PLACEHOLDER = "$VZ$"
"""The JD writes the year of the return as $VZ$ into some labels, such as that of line 125."""

NO_SCHEMA = "Steuerbote cannot write the ELSTER XML of the Umsatzsteuererklärung {0} yet."
TOO_MANY_GRUNDSTUECKE = "Line 95 takes at most {0} Grundstücke, not {1}."
MESSAGES = (NO_SCHEMA, TOO_MANY_GRUNDSTUECKE)

# The „Format als regulärer Ausdruck“ of the JD by Formatkennzeichen, for the fields with 12 digits before the comma.
FORMAT_PATTERNS: MappingProxyType[str, str] = MappingProxyType(
	{
		"N": r"^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$",
		"U": r"^(?=.{1,12}$)(?!0\d)\d{1,12}$",
		"P": r"^(?=-?.{4,15}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}(,\d{2,2})$",
		"%": r"^(?=.{4,15}$)(?!0\d)\d{1,12}(,\d{2,2})$",
		"J": "1",
		"X": "X",
		"D": r"\d\d\.\d\d\.\d\d\d\d",
		"B": r"\d\d\.\d\d-\d\d\.\d\d",
	}
)
POSTLEITZAHL = r"^(?=.{5,5}$)([0]{1}[1-9]{1}[0-9]{3})|([1-9]{1}[0-9]{4})"
"""Postleitzahl (Inland) and Postleitzahl zum Postfach: five digits that do not begin with 00."""


def text_pattern(length: int) -> str:
	"""The pattern of the JD for a text without a pattern of its own: one to ``length`` characters."""
	return f".{{1,{length}}}"


def list_pattern(options: Sequence[str]) -> str:
	"""The pattern of the JD for a Listenfeld: its values, each quoted as Java quotes them."""
	return "|".join(rf"\Q{option}\E" for option in options)


# The fields of 2026 whose pattern in the JD is neither that of their Formatkennzeichen nor that of their length.
_PATTERNS_2026 = {
	# Wirtschafts-Identifikationsnummer, DE and nine digits without the five-digit suffix
	"E3000401": "DE[0-9]{9}",
	# Hausnummer
	"E3001203": r"^(?=.{1,4}$)[0-9]+",
	"E3001206": POSTLEITZAHL,
	"E3001403": POSTLEITZAHL,
	# Postfach
	"E3001404": r"^(?=.{1,6}$)[0-9]+",
	# Umfang der Verwendung im Erstjahr, line 95
	"E3007404": r"^(?=.{4,16}$)(?!0\d)\d{1,15}(,\d{2,2})$",
}
# The values of the Listenfelder of 2026, as E50-2026.xsd enumerates them.
_OPTIONS_2026 = {
	# Kz 133: vereinbarte Entgelte (§ 16 Absatz 1 Satz 1 UStG), vereinnahmte Entgelte (§ 20 UStG), vereinnahmte Entgelte
	# nur für einzelne Unternehmensteile
	"E3002203": ("1", "2", "3"),
	# Kz 500: steuererhebliche Sachverhalte nicht erklärt, abweichende Rechtsauffassung, vertiefte Prüfung, mehrere
	"E3002201": ("1", "2", "3", "4"),
}


def form_catalogue(
	catalogue: Catalogue,
	source: str,
	patterns: ReadOnlyMapping[str, str],
	options: ReadOnlyMapping[str, tuple[str, ...]],
) -> FormCatalogue:
	"""The Erklärung of the year of the catalogue of form USt 2 A, with the patterns and lists of its JD."""
	year = catalogue.year
	fields = []
	for field in catalogue.fields:
		values = options.get(field.element, ())
		if field.element in patterns:
			pattern = patterns[field.element]
		elif field.format is Format.TEXT:
			pattern = text_pattern(field.length or 0)
		elif field.format is Format.LIST:
			pattern = list_pattern(values)
		else:
			pattern = FORMAT_PATTERNS[field.format.value]
		fields.append(
			Field(
				form=MAIN_FORM,
				context=field.context,
				feldkennung=field.element,
				label=field.label.replace(YEAR_PLACEHOLDER, str(year)),
				format=field.format.value,
				line=field.line,
				kennzahl=field.kennzahl,
				length=field.length,
				required=field.mandatory,
				pattern=pattern,
				options=values,
			)
		)
	return FormCatalogue(datenart=ust(year), source=source, forms=FORMS, fields=tuple(fields))


SCHEMAS: MappingProxyType[int, FormCatalogue] = MappingProxyType(
	{
		2026: form_catalogue(
			CATALOGUES[2026],
			"Jahresdokumentation_E50_2026.ods (Versionslabel 9.0)",
			_PATTERNS_2026,
			_OPTIONS_2026,
		)
	}
)


def schema_for(year: int) -> FormCatalogue:
	try:
		return SCHEMAS[year]
	except KeyError:
		raise XmlError(NO_SCHEMA, year) from None


def to_nutzdaten(
	year: int,
	values: ReadOnlyMapping[str, object],
	vorsatz: Vorsatz,
	grundstuecke: Sequence[ReadOnlyMapping[str, object]] = (),
) -> str:
	"""The Nutzdaten for ERiC: the tree of build() as text, without a declaration."""
	return serialized(build(year, values, vorsatz, grundstuecke))


def build(
	year: int,
	values: ReadOnlyMapping[str, object],
	vorsatz: Vorsatz,
	grundstuecke: Sequence[ReadOnlyMapping[str, object]] = (),
) -> etree._Element:
	"""The element E50 of the Umsatzsteuererklärung of ``year``.

	``values`` are the values rules.check() takes, by Feldkennung: a Decimal for an amount, True for a yes field or a
	cross, a str for a text or a value of a list, a date, and a pair of dates for the spans of lines 19 and 20; None or
	False leaves a field out. ``grundstuecke`` holds the fields of each Grundstück of line 95, in the same way.

	Raises XmlError for a value ELSTER does not take and for more Grundstücke than line 95 takes, ValueError for a
	field the form of the year does not have, one Steuerbote does not file, or one of a Grundstück among ``values``,
	and TypeError for a value of the wrong type.
	"""
	schema = schema_for(year)
	repeated = {field.context: field.repeat for field in CATALOGUES[year].fields if field.repeat > 1}
	_require_fields(year, values, grundstuecke, repeated)
	kind = schema.datenart
	root = etree.Element(_tag(kind, kind.root), nsmap={None: kind.namespace})
	root.set("version", kind.root_version)
	contexts = {"": _append(root, kind, MAIN_FORM)}
	for field in schema.fields:
		if field.context not in repeated:
			text = _text(field, values.get(field.feldkennung))
			if text is not None:
				_append(_context(contexts, kind, field.context), kind, field.feldkennung, text)
		elif field.feldkennung == _first(schema, field.context):
			_write_repeated(contexts, kind, schema, field.context, grundstuecke)
	append_to(root, kind, vorsatz)
	return root


def _require_fields(
	year: int,
	values: ReadOnlyMapping[str, object],
	grundstuecke: Sequence[ReadOnlyMapping[str, object]],
	repeated: ReadOnlyMapping[str, int],
) -> None:
	catalogue = CATALOGUES[year]
	for element in values:
		field = _field(catalogue, element)
		if field.context in repeated:
			raise ValueError(
				f"{element} is a field of a Grundstück of line {field.line}: give it in grundstuecke"
			)
		if field.scope in NOT_FILED and values[element] is not None:
			raise ValueError(f"Steuerbote does not file {element} of form USt 2 A: {field.scope.value}")
	for grundstueck in grundstuecke:
		for element in grundstueck:
			if _field(catalogue, element).context not in repeated:
				raise ValueError(f"{element} is no field of a Grundstück of line 95")
	for limit in repeated.values():
		if len(grundstuecke) > limit:
			raise XmlError(TOO_MANY_GRUNDSTUECKE, limit, len(grundstuecke))


def _field(catalogue: Catalogue, element: str) -> AnnualField:
	try:
		return catalogue.field(element)
	except KeyError:
		raise ValueError(f"Form USt 2 A {catalogue.year} has no field {element}") from None


def _first(schema: FormCatalogue, context: str) -> str:
	"""The first field of the context, where the schema begins the contexts of a repeated one."""
	return next(field.feldkennung for field in schema.fields if field.context == context)


def _write_repeated(
	contexts: dict[str, etree._Element],
	kind: Datenart,
	schema: FormCatalogue,
	context: str,
	rows: Sequence[ReadOnlyMapping[str, object]],
) -> None:
	"""Write a context of its own for each row that holds a value, after what its parent holds so far."""
	parent, _, name = context.rpartition("/")
	fields = [field for field in schema.fields if field.context == context]
	for row in rows:
		texts = [(field, text) for field in fields if (text := _text(field, row.get(field.feldkennung)))]
		if texts:
			element = _append(_context(contexts, kind, parent), kind, name)
			for field, text in texts:
				_append(element, kind, field.feldkennung, text)


def _text(field: Field, value: object) -> str | None:
	"""The value as the field takes it, or None to leave it out; XmlError for one its pattern refuses."""
	text = value_text(
		value,
		field.format,
		label=field.label,
		length=field.length,
		options=field.options,
		integer_digits=MORE_DIGITS_BEFORE_THE_COMMA.get(field.feldkennung, DIGITS_BEFORE_THE_COMMA),
	)
	if text is not None and field.pattern and not re.fullmatch(python_pattern(field.pattern), text):
		raise XmlError(NOT_IN_FORMAT, text, label=field.label)
	return text


def _context(contexts: dict[str, etree._Element], kind: Datenart, path: str) -> etree._Element:
	"""The element of the context below USt2A, appended to its parent the first time a field needs it."""
	if path not in contexts:
		parent, _, name = path.rpartition("/")
		contexts[path] = _append(_context(contexts, kind, parent), kind, name)
	return contexts[path]


def _tag(kind: Datenart, name: str) -> str:
	return f"{{{kind.namespace}}}{name}"


def _append(parent: etree._Element, kind: Datenart, name: str, text: str | None = None) -> etree._Element:
	child = etree.SubElement(parent, _tag(kind, name))
	child.text = text
	return child
