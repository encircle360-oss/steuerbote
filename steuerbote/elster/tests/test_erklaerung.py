"""The values, fields and catalogues of the Erklärungen, also against the Jahresdokumentationen and the schema of the
ERiC documentation 44.3.6.0, which has KSt and GewSt up to 2025."""

import csv
import re
import zipfile
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path
from unittest import TestCase

from lxml import etree

from steuerbote.elster import charset, erklaerung, ustva_xml
from steuerbote.elster.erklaerung import (
	FORMATS,
	Field,
	Form,
	FormCatalogue,
	Rule,
	python_pattern,
	value_text,
)
from steuerbote.elster.tests import eric_schema
from steuerbote.elster.ustva_xml import XmlError
from steuerbote.eric.datenart import Datenart, bilanz, gewst, kst, ust, ustva

TRANSLATIONS = Path(__file__).resolve().parents[2] / "translations" / "de.csv"
LABEL = "Zeile 9"


def refused(value: object, formatkennzeichen: str, **options: object) -> XmlError:
	"""The error of a value the format does not take."""
	with TestCase().assertRaises(XmlError) as raised:
		value_text(value, formatkennzeichen, label=LABEL, **options)
	return raised.exception


class WholeEurosTest(TestCase):
	"""N, U, G and M: „Zahl ohne Nachkommastellen bzw. GeldbetragOhneCent“, with or without a sign, zero allowed or
	not (sheet „Allg. Information“); at most 12 digits (GanzzahlOhneFuehrNull_MaxVK12 of the schemas)."""

	def test_writes_whole_euros_with_a_leading_minus_and_without_a_negative_zero(self):
		for value, text in (
			(Decimal("1234"), "1234"),
			(Decimal("-1234"), "-1234"),
			(Decimal("1234.00"), "1234"),
			(Decimal("0"), "0"),
			(Decimal("-0"), "0"),
			(Decimal("999999999999"), "999999999999"),
		):
			with self.subTest(value=value):
				self.assertEqual(value_text(value, "N", label=LABEL), text)

	def test_refuses_cents_which_the_caller_rounds_first(self):
		error = refused(Decimal("12.50"), "N")
		self.assertEqual(
			(error.template, error.values, error.label), (erklaerung.NOT_WHOLE, ("12.50",), LABEL)
		)

	def test_refuses_more_than_12_digits(self):
		error = refused(Decimal("-1000000000000"), "N")
		self.assertEqual((error.template, error.values), (erklaerung.TOO_MANY_DIGITS, ("-1000000000000", 12)))

	def test_u_and_g_take_no_sign_g_and_m_no_zero(self):
		self.assertEqual(value_text(Decimal("0"), "U", label=LABEL), "0")
		self.assertEqual(value_text(Decimal("-5"), "M", label=LABEL), "-5")
		for value, formatkennzeichen, template in (
			(Decimal("-1"), "U", erklaerung.NEGATIVE),
			(Decimal("-1"), "G", erklaerung.NEGATIVE),
			(Decimal("0"), "G", erklaerung.ZERO_VALUE),
			(Decimal("0"), "M", erklaerung.ZERO_VALUE),
		):
			with self.subTest(value=value, formatkennzeichen=formatkennzeichen):
				self.assertEqual(refused(value, formatkennzeichen).template, template)

	def test_takes_more_or_fewer_digits_where_the_field_says_so(self):
		self.assertEqual(value_text(Decimal("1000000"), "U", label=LABEL, integer_digits=7), "1000000")
		self.assertEqual(refused(Decimal("10000000"), "U", integer_digits=7).values, ("10000000", 7))


class CentsTest(TestCase):
	"""P, %, R and S: „Zahl mit 2 Nachkommastellen bzw. GeldbetragMitCent“ with a decimal comma, with or without a
	sign, zero allowed or not."""

	def test_writes_two_decimals_with_a_decimal_comma(self):
		for value, text in (
			(Decimal("1002.44"), "1002,44"),
			(Decimal("-1000.44"), "-1000,44"),
			(Decimal("-0.5"), "-0,50"),
			(Decimal("902"), "902,00"),
			(Decimal("0"), "0,00"),
			(Decimal("-0.00"), "0,00"),
		):
			with self.subTest(value=value):
				self.assertEqual(value_text(value, "P", label=LABEL), text)

	def test_refuses_fractions_of_a_cent(self):
		error = refused(Decimal("1.005"), "P")
		self.assertEqual((error.template, error.values), (erklaerung.TOO_MANY_DECIMALS, ("1.005", 2)))

	def test_refuses_more_than_12_digits_before_the_comma(self):
		self.assertEqual(refused(Decimal("1000000000000.00"), "P").template, erklaerung.TOO_MANY_DIGITS)

	def test_percent_and_r_take_no_sign_r_and_s_no_zero(self):
		self.assertEqual(value_text(Decimal("0"), "%", label=LABEL), "0,00")
		self.assertEqual(value_text(Decimal("-1.5"), "S", label=LABEL), "-1,50")
		for value, formatkennzeichen, template in (
			(Decimal("-1"), "%", erklaerung.NEGATIVE),
			(Decimal("-1"), "R", erklaerung.NEGATIVE),
			(Decimal("0"), "R", erklaerung.ZERO_VALUE),
			(Decimal("0.00"), "S", erklaerung.ZERO_VALUE),
		):
			with self.subTest(value=value, formatkennzeichen=formatkennzeichen):
				self.assertEqual(refused(value, formatkennzeichen).template, template)


class VariableDecimalsTest(TestCase):
	"""F and V: „Zahl mit variablen Nachkommastellen (0-4)“, without or with a sign."""

	def test_writes_the_decimals_of_the_value_up_to_four(self):
		for value, text in (
			(Decimal("12.5"), "12,5"),
			(Decimal("12.5000"), "12,5000"),
			(Decimal("100"), "100"),
			(Decimal("33.3333"), "33,3333"),
		):
			with self.subTest(value=value):
				self.assertEqual(value_text(value, "F", label=LABEL), text)
		self.assertEqual(value_text(Decimal("-0.25"), "V", label=LABEL), "-0,25")

	def test_refuses_a_fifth_decimal_and_a_sign_where_the_format_has_none(self):
		self.assertEqual(refused(Decimal("33.33333"), "F").values, ("33.33333", 4))
		self.assertEqual(refused(Decimal("-1"), "F").template, erklaerung.NEGATIVE)


class NumbersTest(TestCase):
	def test_every_number_is_a_decimal(self):
		for formatkennzeichen in ("N", "P", "F"):
			with self.subTest(formatkennzeichen=formatkennzeichen), self.assertRaises(TypeError):
				value_text(1.5, formatkennzeichen, label=LABEL)

	def test_refuses_a_decimal_that_is_no_number(self):
		for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
			with self.subTest(value=value), self.assertRaises(ValueError):
				value_text(value, "N", label=LABEL)


class YesFieldsTest(TestCase):
	"""J „JaFeld mit Wert für Ja 1“, X „JaFeld mit Wert für Ja X (Ankreuzfeld)“, Y „JaNeinFeld mit Wert für Ja 1 und
	Wert für Nein 2“."""

	def test_writes_yes_and_leaves_a_yes_field_out_otherwise(self):
		self.assertEqual(
			[value_text(True, formatkennzeichen, label=LABEL) for formatkennzeichen in ("J", "X", "Y")],
			["1", "X", "1"],
		)
		self.assertEqual(
			[value_text(False, formatkennzeichen, label=LABEL) for formatkennzeichen in ("J", "X", "Y")],
			[None, None, "2"],
		)

	def test_takes_only_true_and_false(self):
		for value in ("1", 1, "X"):
			with self.subTest(value=value), self.assertRaises(TypeError):
				value_text(value, "J", label=LABEL)


class ListTest(TestCase):
	"""H: „Listenfeld: Textfeld für das eine Auswahlmöglichkeit aus einer Werteliste vorgegeben wird“."""

	def test_takes_a_value_of_its_list(self):
		self.assertEqual(value_text("2", "H", label=LABEL, options=("1", "2", "3")), "2")
		error = refused("4", "H", options=("1", "2", "3"))
		self.assertEqual((error.template, error.values), (erklaerung.NOT_AN_OPTION, ("4", "1, 2, 3")))

	def test_needs_its_list(self):
		with self.assertRaises(ValueError):
			value_text("2", "H", label=LABEL)


class DatesTest(TestCase):
	"""D „Datum mit Format TT.MM.JJJJ“, T „Datum mit Format TT.MM.“, B „DatumBereich mit Format TT.MM-TT.MM“, Z
	„Datumsbereich mit Format TT.MM.JJJJ-TT.MM.JJJJ“."""

	def test_writes_dates_and_spans(self):
		self.assertEqual(value_text(date(2026, 1, 5), "D", label=LABEL), "05.01.2026")
		self.assertEqual(value_text(date(2026, 3, 1), "T", label=LABEL), "01.03.")
		self.assertEqual(value_text((date(2026, 1, 1), date(2026, 12, 31)), "B", label=LABEL), "01.01-31.12")
		self.assertEqual(
			value_text((date(2025, 7, 1), date(2026, 6, 30)), "Z", label=LABEL), "01.07.2025-30.06.2026"
		)

	def test_a_span_ends_after_it_begins_and_tt_mm_spans_lie_in_one_year(self):
		self.assertEqual(refused((date(2026, 12, 31), date(2026, 1, 1)), "B").template, erklaerung.NOT_A_SPAN)
		self.assertEqual(refused((date(2026, 2, 1), date(2025, 1, 1)), "Z").template, erklaerung.NOT_A_SPAN)
		error = refused((date(2025, 7, 1), date(2026, 6, 30)), "B")
		self.assertEqual(
			(error.template, error.values), (erklaerung.NOT_IN_ONE_YEAR, ("01.07.2025", "30.06.2026"))
		)

	def test_takes_only_dates(self):
		for value, formatkennzeichen in (("2026-01-05", "D"), ((date(2026, 1, 1), "2026-12-31"), "B")):
			with self.subTest(formatkennzeichen=formatkennzeichen), self.assertRaises(TypeError):
				value_text(value, formatkennzeichen, label=LABEL)


class NumbersAsTextTest(TestCase):
	"""A „Steuernummer im ELSTER-Steuernummerformat“, I „einheitliche Identifikationsnummer nach § 139 AO; nur Ziffern
	erlaubt, genau elf Stellen“, O „Strings, die nur aus Ziffern bestehen dürfen und Datum mit Format JJJJ“."""

	def test_writes_steuernummer_idnr_and_digits(self):
		self.assertEqual(value_text("9198011310010", "A", label=LABEL), "9198011310010")
		self.assertEqual(value_text("01234567890", "I", label=LABEL), "01234567890")
		self.assertEqual(value_text("2026", "O", label=LABEL), "2026")

	def test_refuses_numbers_of_another_shape(self):
		for value, formatkennzeichen, template in (
			("9198111310010", "A", ustva_xml.NOT_A_STEUERNUMMER),
			("0123456789", "I", erklaerung.NOT_AN_IDNR),
			("0123456789a", "I", erklaerung.NOT_AN_IDNR),
			("20 26", "O", erklaerung.NOT_DIGITS),
		):
			with self.subTest(value=value, formatkennzeichen=formatkennzeichen):
				self.assertEqual(refused(value, formatkennzeichen).template, template)


class TextTest(TestCase):
	"""C: every other field, in the character set Standard_E_V2 and on one line (StringBaseCType of the schemas)."""

	def test_writes_a_text_in_the_character_set_of_elster_on_one_line(self):
		self.assertEqual(
			value_text(" Müller „Söhne“\nGmbH ", "C", label=LABEL, length=999), 'Müller "Söhne" GmbH'
		)
		self.assertIsNone(value_text("  ", "C", label=LABEL, length=999))

	def test_refuses_a_text_longer_than_its_field(self):
		error = refused("x" * 26, "C", length=25)
		self.assertEqual((error.template, error.values), (ustva_xml.TEXT_TOO_LONG, (26, 25)))

	def test_needs_the_length_of_its_field(self):
		with self.assertRaises(ValueError):
			value_text("Text", "C", label=LABEL)


class FormatsTest(TestCase):
	def test_leaves_a_field_without_a_value_out(self):
		for formatkennzeichen in FORMATS:
			with self.subTest(formatkennzeichen=formatkennzeichen):
				self.assertIsNone(value_text(None, formatkennzeichen, label=LABEL, length=1, options=("1",)))

	def test_refuses_a_formatkennzeichen_it_does_not_write(self):
		for formatkennzeichen in ("E", "K", "L", "W", ""):
			with self.subTest(formatkennzeichen=formatkennzeichen), self.assertRaises(ValueError):
				value_text("1", formatkennzeichen, label=LABEL)

	def test_reads_the_java_quotes_of_a_pattern_of_the_jahresdokumentation(self):
		self.assertEqual(python_pattern(r"\Q1\E|\Q2\E"), r"1|2")
		self.assertEqual(python_pattern(r"\QÄgypten (Land)\E|x"), r"Ägypten\ \(Land\)|x")
		self.assertEqual(python_pattern(r"^(?=.{1,12}$)(?!0\d)\d{1,12}$"), r"^(?=.{1,12}$)(?!0\d)\d{1,12}$")


FIELD = Field(
	form="USt2A",
	context="Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben",
	feldkennung="E3003405",
	label="Bemessungsgrundlage ohne Umsatzsteuer",
	format="N",
	line=40,
	kennzahl="178",
	pattern=r"^(?=.{1,13}$)(-(?=.*[1-9].*))?(?!0\d)\d{1,12}$",
)


class FieldTest(TestCase):
	def test_names_its_path_below_the_root_of_the_nutzdaten(self):
		self.assertEqual(
			FIELD.path, ("USt2A", "Umsaetze", "Tabelle", "Ums_allg", "Unent_Wertabgaben", "E3003405")
		)
		self.assertEqual(Field("KSt1", "", "E8000015", "Organträger", "X").path, ("KSt1", "E8000015"))

	def test_writes_a_value_in_its_format_and_its_pattern(self):
		self.assertEqual(FIELD.text(Decimal("5276")), "5276")
		self.assertIsNone(FIELD.text(None))
		self.assertEqual(
			Field("USt2A", "Allg/Best_Art", "E3002203", "Berechnung", "H", options=("1", "2", "3")).text("1"),
			"1",
		)

	def test_refuses_a_value_its_pattern_does_not_take(self):
		short = Field(
			"KSt1", "AE", "E8122105", "Besitzdauer", "F", pattern=r"^(?=.{1,8}$)(?!0\d)\d{1,3}(,\d{1,4})?$"
		)
		self.assertEqual(short.text(Decimal("365")), "365")
		with self.assertRaises(XmlError) as raised:
			short.text(Decimal("1000"))
		self.assertEqual(
			(raised.exception.template, raised.exception.values, raised.exception.label),
			(erklaerung.NOT_IN_FORMAT, ("1000",), "Besitzdauer"),
		)

	def test_knows_its_formatkennzeichen_its_list_and_its_length(self):
		for fields in (
			{"format": "E"},
			{"format": "H"},
			{"format": "C"},
		):
			with self.subTest(fields=fields), self.assertRaises(ValueError):
				Field("USt2A", "Allg", "E3000901", "Name", **fields)
		self.assertEqual(
			Field("USt2A", "Allg", "E3000901", "Name", "C", length=999).text("Beispiel"), "Beispiel"
		)


USt_2026 = ust(2026)


class CatalogueTest(TestCase):
	def catalogue(self, kind: Datenart = USt_2026, **changes: object) -> FormCatalogue:
		values: dict = {
			"datenart": kind,
			"source": "Jahresdokumentation_E50_2026.ods, Versionslabel 9.0",
			"forms": (Form("USt2A", mandatory=True), Form("UN"), Form("Vorsatz", mandatory=True)),
			"fields": (
				FIELD,
				Field("USt2A", "Allg/Unternehmen", "E3000901", "Name", "C", length=999, required=True),
			),
			"rules": (Rule("30096", "Regel_30096", "Der Name des Unternehmers fehlt.", ("E3000901",)),),
			**changes,
		}
		return FormCatalogue(**values)

	def test_finds_a_field_by_feldkennung_and_by_kennzahl(self):
		catalogue = self.catalogue()
		self.assertIs(catalogue.field("E3003405"), FIELD)
		self.assertEqual(catalogue.kennzahlen, {"178": FIELD})
		self.assertEqual(catalogue.mandatory_forms, ("USt2A", "Vorsatz"))
		with self.assertRaises(KeyError):
			catalogue.field("E9999999")

	def test_holds_its_parts_as_tuples(self):
		catalogue = self.catalogue(forms=[Form("USt2A")], fields=[FIELD], rules=[])
		self.assertEqual(
			(catalogue.forms, catalogue.fields, catalogue.rules), ((Form("USt2A"),), (FIELD,), ())
		)

	def test_is_the_catalogue_of_an_erklaerung(self):
		for kind in (ustva(2026), bilanz("6.9")):
			with self.subTest(datenart=kind.version), self.assertRaises(ValueError):
				self.catalogue(kind)

	def test_refuses_a_field_twice_or_on_a_form_it_does_not_have(self):
		for fields in ((FIELD, FIELD), (Field("FV", "", "E3300101", "Fiskalvertreter", "J"),)):
			with self.subTest(fields=fields), self.assertRaises(ValueError):
				self.catalogue(fields=fields)
		with self.assertRaises(ValueError):
			self.catalogue(forms=(Form("USt2A"), Form("USt2A")))


class TranslationsTest(TestCase):
	def test_every_message_of_the_values_has_a_translation(self):
		with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
			translated = {source for source, *_ in csv.reader(file)}
		self.assertEqual(sorted(set(erklaerung.MESSAGES) - translated), [])


@cache
def fields_of(path: Path) -> tuple[dict[str, str], ...]:
	"""The current fields of every Vordruck of a Jahresdokumentation, which is read once."""
	with zipfile.ZipFile(path) as archive:
		content = etree.fromstring(archive.read("content.xml"))
	tables = {
		table.get(f"{{{eric_schema.ODS_TABLE}}}name"): table
		for table in content.iter(f"{{{eric_schema.ODS_TABLE}}}table")
	}
	forms = [
		line.split(" - ")[0]
		for line in eric_schema.lines(path, "Allg. Information")
		if " - max. lfd. Nr. Vordruck" in line
	]
	found = []
	for form in forms:
		head, *body = [
			eric_schema._cells(row)
			for row in tables[f"{form} - Felder"].iter(f"{{{eric_schema.ODS_TABLE}}}table-row")
		]
		rows = [dict(zip(head, cells, strict=False)) for cells in body if any(cells)]
		found.extend(row for row in rows if row["Änderungsinformation"] != "GEAENDERT_ALTE_VERSION")
	return tuple(found)


class ErklaerungDocumentationTest(TestCase):
	"""The formats against the Jahresdokumentationen of USt 2026, KSt 2025 and GewSt 2025, and the schema of USt 2026."""

	KINDS = (ust(2026), kst(2025), gewst(2025))

	def jahresdokumentation(self, kind: Datenart) -> Path:
		directory = eric_schema.erklaerung_directory(kind.name) / "Jahresdokumentation"
		return directory / f"Jahresdokumentation_{kind.root}_{kind.year}.ods"

	def fields(self, kind: Datenart) -> tuple[dict[str, str], ...]:
		return fields_of(self.jahresdokumentation(kind))

	def test_the_legend_of_the_jahresdokumentation_names_each_format_as_steuerbote_writes_it(self):
		"""The legend breaks some lines; the comparison takes every run of white space as one blank."""
		for kind in self.KINDS:
			with self.subTest(datenart=kind.version):
				legend = dict(
					" ".join(line.split()).split(": ", 1)
					for line in eric_schema.lines(self.jahresdokumentation(kind), "Allg. Information")
					if re.fullmatch(r"[A-Z%]: .*", line, re.DOTALL)
				)
				self.assertEqual({key: legend[key] for key in FORMATS}, dict(FORMATS))

	def test_writes_every_format_the_fields_of_the_erklaerungen_have(self):
		for kind in self.KINDS:
			with self.subTest(datenart=kind.version):
				used = {row["Formatkennzeichen"] for row in self.fields(kind)}
				self.assertEqual(sorted(used - set(FORMATS)), [])

	def test_every_pattern_of_the_jahresdokumentation_reads_as_a_python_pattern(self):
		for kind in self.KINDS:
			with self.subTest(datenart=kind.version):
				for row in self.fields(kind):
					re.compile(python_pattern(row["Format als regulärer Ausdruck"]))

	def test_the_character_set_of_the_texts_is_standard_e_v2(self):
		"""StringZUBaseCType of E50-2026.xsd holds the characters of charset.py, with the line breaks; each character of
		its class lies in the Basic Multilingual Plane, up to the euro sign."""
		xsd = etree.parse(str(eric_schema.documentation() / ust(2026).schema)).getroot()
		(pattern,) = (
			element.get("value")
			for element in xsd.iter("{http://www.w3.org/2001/XMLSchema}pattern")
			if element.getparent().getparent().getparent().get("name") == "StringZUBaseCType"
		)
		allowed = {chr(code) for code in range(0x10000) if re.fullmatch(pattern, chr(code))}
		self.assertEqual(allowed, set(charset.ALLOWED) | {"\n", "\r"})

	def test_the_values_pass_the_schema_of_the_umsatzsteuererklaerung(self):
		kind = ust(2026)
		namespace = kind.namespace
		values = (
			(("Ber_Erkl", "E3000601"), value_text(True, "J", label=LABEL)),
			(("Allg", "Unternehmen", "E3000901"), value_text("Beispiel GmbH", "C", label=LABEL, length=999)),
			(("Allg", "Kleinunternehmer", "E3001601"), value_text(date(2026, 3, 1), "D", label=LABEL)),
			(
				("Allg", "Dauer_Unt_Eig", "E3001401"),
				value_text((date(2026, 1, 1), date(2026, 12, 31)), "B", label=LABEL),
			),
			(
				("Allg", "Best_Art", "E3002203"),
				value_text("1", "H", label=LABEL, options=("1", "2", "3")),
			),
			(
				("Umsaetze", "Tabelle", "Ums_allg", "Unent_Wertabgaben", "E3003405"),
				value_text(Decimal("-5276"), "N", label=LABEL),
			),
			(
				("Umsaetze", "Tabelle", "Ums_allg", "Unent_Wertabgaben", "E3003406"),
				value_text(Decimal("-1002.44"), "P", label=LABEL),
			),
		)
		root = etree.Element(f"{{{namespace}}}E50", nsmap={None: namespace}, version=kind.root_version)
		form = etree.SubElement(root, f"{{{namespace}}}USt2A")
		for path, text in values:
			parent = form
			for name in path:
				child = parent.find(f"{{{namespace}}}{name}")
				parent = child if child is not None else etree.SubElement(parent, f"{{{namespace}}}{name}")
			parent.text = text
		schema = etree.XMLSchema(etree.parse(str(eric_schema.documentation() / kind.schema)))
		if not schema.validate(root):
			self.fail(str(schema.error_log))
