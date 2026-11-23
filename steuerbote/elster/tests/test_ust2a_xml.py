"""The Umsatzsteuererklärung as ELSTER XML: E50 with form USt2A and the Vorsatz, also against the Jahresdokumentation,
the schemas and the example of the ERiC documentation 44.3.6.0, which are skipped without it (eric_schema.py)."""

import copy
import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from lxml import etree

from steuerbote.elster import erklaerung, ust2a_xml, ustva_xml
from steuerbote.elster.envelope import envelope_for
from steuerbote.elster.erklaerung import FormCatalogue
from steuerbote.elster.tests import eric_schema
from steuerbote.elster.tests.examples import FIXTURES, TEST_STEUERNUMMER
from steuerbote.elster.ust2a_xml import (
	FORMAT_PATTERNS,
	MAIN_FORM,
	NO_SCHEMA,
	POSTLEITZAHL,
	SCHEMAS,
	TOO_MANY_GRUNDSTUECKE,
	build,
	schema_for,
	to_nutzdaten,
)
from steuerbote.elster.ustva_xml import XmlError
from steuerbote.elster.vorsatz import Vorsatz
from steuerbote.eric.datenart import ust
from steuerbote.ustjahr.calculation import entries
from steuerbote.ustjahr.form import CATALOGUES, Format, Scope
from steuerbote.ustjahr.rules import check
from steuerbote.ustjahr.tests import jahresdokumentation as jd

YEAR = 2026
CATALOGUE = CATALOGUES[YEAR]
KIND = ust(YEAR)
NAMESPACE = KIND.namespace
D = Decimal
TRANSLATIONS = Path(__file__).resolve().parents[2] / "translations" / "de.csv"
GOLDEN = FIXTURES / "ust2a_2026.xml"

# An invented return of a GmbH for 2026: sales at 19 and 7 % with an Entnahme, innergemeinschaftliche Lieferungen and
# Erwerbe, an Ausfuhr, exempt sales under § 4 Nummer 11 UStG, a Dreiecksgeschäft as its first buyer, a service under §
# 13b UStG, Vorsteuer, a correction under § 15a UStG for another asset after its sale, a Grundstück first used in
# 2026 and the Mitwirkung of a Steuerberatung. The amounts are those of entries(), as the return files them.
AMOUNTS = {
	"E3003303": D("250000"),
	"E3003304": D("47500.00"),
	"E3003405": D("1200"),
	"E3003406": D("228.00"),
	"E3004401": D("10000"),
	"E3004402": D("700.00"),
	"E3103301": D("40000"),
	"E3103801": D("15000"),
	"E3104502": D("3000"),
	"E3100801": D("5000"),
	"E3100902": D("20000"),
	"E3100903": D("3800.00"),
	"E3101801": D("8000"),
	"E3102205": D("2000"),
	"E3102206": D("380.00"),
	"E3006201": D("30000.00"),
	"E3006301": D("3800.00"),
	"E3006502": D("380.00"),
	"E3008801": D("150.00"),
}
SOLL = D("18028.00")
DETAILS = {
	"E3000401": "DE123456789",
	"E3000901": "Beispiel GmbH",
	"E3001001": "Entwicklung von Software",
	"E3001101": "Hauptstraße",
	"E3001203": "1",
	"E3001206": "80331",
	"E3001207": "München",
	"E3001301": "steuern@example.org",
	"E3002203": "1",
	"E3002506": "10001",
	"E3002501": "Muster",
	"E3002502": "Erika",
	"E3002503": "Beispielweg 2",
	"E3002504": "80331 München",
	"E3002602": True,
	"E3104501": "11",
	"E3007301": True,
	"E3008501": True,
	"E3007801": True,
}
GRUNDSTUECK = {
	"E3007401": "Beispielweg 5, 80331 München",
	"E3007402": date(2026, 4, 1),
	"E3007403": "Vermietung an Unternehmer",
	"E3007404": D("100.00"),
	"E3007405": D("38000"),
	"E3007406": D("38000"),
}
RETURN = {**DETAILS, **entries(CATALOGUE, AMOUNTS, SOLL)}
COPYRIGHT = "(c) 2026 Beispiel Software GmbH, München"


def sender(**fields: object) -> Vorsatz:
	values: dict = {
		"steuernummer": TEST_STEUERNUMMER,
		"name": "Beispiel GmbH",
		"street": "Hauptstraße 1",
		"postal_code": "80331",
		"city": "München",
		"copyright": COPYRIGHT,
		**fields,
	}
	return Vorsatz(**values)


def written(values: dict, grundstuecke: tuple = ()) -> etree._Element:
	return build(YEAR, values, sender(), grundstuecke)


def leaves(root: etree._Element) -> list[tuple[str, str | None]]:
	"""Each field below USt2A by its path from USt2A, with its text, in the order of the document."""
	(form,) = root.iterchildren(f"{{{NAMESPACE}}}{MAIN_FORM}")
	found = []
	for element in form.iter():
		if len(element) == 0:
			path = [etree.QName(ancestor).localname for ancestor in element.iterancestors()]
			path = path[: path.index(MAIN_FORM)]
			found.append(("/".join([*reversed(path), etree.QName(element).localname]), element.text))
	return found


def texts(root: etree._Element) -> dict[str, str | None]:
	return {path.rpartition("/")[2]: text for path, text in leaves(root)}


def canonical(element: etree._Element) -> bytes:
	"""The element in Canonical XML 2.0 without the white space between elements, with the namespace it inherits."""
	return etree.tostring(copy.deepcopy(element), method="c14n2", strip_text=True)


def values_of(form: etree._Element) -> tuple[dict[str, object], list[dict[str, object]]]:
	"""The values of a USt2A element as build() takes them, and those of its Grundstücke."""
	values: dict[str, object] = {}
	grundstuecke: list[dict[str, object]] = []
	for element in form.iter():
		name = etree.QName(element).localname
		if name == "Ang_Grdst":
			grundstuecke.append({etree.QName(child).localname: value_of(child) for child in element})
		elif len(element) == 0 and etree.QName(element.getparent()).localname != "Ang_Grdst":
			values[name] = value_of(element)
	return values, grundstuecke


def value_of(element: etree._Element) -> object:
	return typed(CATALOGUE.field(etree.QName(element).localname).format, element.text or "")


def typed(form: Format, text: str) -> object:
	if form.amount:
		return D(text.replace(",", "."))
	if form in (Format.YES, Format.CROSS):
		return True
	if form is Format.DATE:
		return datetime.strptime(text, "%d.%m.%Y").date()
	if form is Format.DAYS:
		return tuple(datetime.strptime(f"{day}.{YEAR}", "%d.%m.%Y").date() for day in text.split("-"))
	return text


# A value of each format the form takes, which every pattern of that format takes too.
SAMPLES = {
	Format.EUROS: D("-1"),
	Format.UNSIGNED_EUROS: D("1"),
	Format.CENTS: D("-1.00"),
	Format.UNSIGNED_CENTS: D("1.00"),
	Format.YES: True,
	Format.CROSS: True,
	Format.LIST: "1",
	Format.TEXT: "Text",
	Format.DATE: date(2026, 7, 1),
	Format.DAYS: (date(2026, 3, 1), date(2026, 6, 30)),
}
OWN_SAMPLES = {
	"E3000401": "DE123456789",
	"E3001203": "12",
	"E3001206": "80331",
	"E3001403": "80331",
	"E3001404": "4711",
}


def every_field() -> tuple[dict[str, object], dict[str, object]]:
	"""A value for each field Steuerbote files, and those of a Grundstück: no return, but each element in its place."""
	values, grundstueck = {}, {}
	for field in CATALOGUE.fields:
		if field.scope in (Scope.IN, Scope.KLEINUNTERNEHMER):
			value = OWN_SAMPLES.get(field.element, SAMPLES[field.format])
			(grundstueck if field.repeat > 1 else values)[field.element] = value
	return values, grundstueck


class SchemaTest(TestCase):
	"""SCHEMAS: the catalogue of form USt 2 A of each year as the FormCatalogue of its Erklärung, with the patterns and
	lists of its Jahresdokumentation."""

	def test_the_schema_of_2026_is_the_catalogue_of_the_form_on_ust2a(self):
		schema = SCHEMAS[YEAR]
		self.assertIsInstance(schema, FormCatalogue)
		self.assertEqual(schema.datenart, KIND)
		self.assertEqual(
			[(form.name, form.count, form.mandatory) for form in schema.forms],
			[("USt2A", 1, True), ("UN", 1, False), ("FV", 1, False), ("Vorsatz", 1, True)],
		)
		self.assertEqual(schema.mandatory_forms, ("USt2A", "Vorsatz"))
		self.assertEqual(
			[
				(field.form, field.context, field.feldkennung, field.format, field.line)
				for field in schema.fields
			],
			[
				(MAIN_FORM, field.context, field.element, field.format.value, field.line)
				for field in CATALOGUE.fields
			],
		)
		self.assertEqual(
			[(field.kennzahl, field.length, field.required) for field in schema.fields],
			[(field.kennzahl, field.length, field.mandatory) for field in CATALOGUE.fields],
		)

	def test_a_label_is_the_beschreibung_of_the_field_with_its_year(self):
		self.assertEqual(SCHEMAS[YEAR].field("E3000901").label, "Name des Unternehmers")
		self.assertEqual(
			SCHEMAS[YEAR].field("E3011301").label,
			"Vorauszahlungssoll 2026 (einschließlich Sondervorauszahlung)",
		)

	def test_a_field_has_the_pattern_of_its_format_its_length_or_its_own(self):
		schema = SCHEMAS[YEAR]
		self.assertEqual(schema.field("E3003303").pattern, FORMAT_PATTERNS["N"])
		self.assertEqual(schema.field("E3003304").pattern, FORMAT_PATTERNS["P"])
		self.assertEqual(schema.field("E3000901").pattern, ".{1,999}")
		self.assertEqual(schema.field("E3001204").pattern, ".{1,6}")
		self.assertEqual(schema.field("E3001206").pattern, POSTLEITZAHL)
		self.assertEqual(schema.field("E3002203").pattern, r"\Q1\E|\Q2\E|\Q3\E")
		self.assertEqual(schema.field("E3002203").options, ("1", "2", "3"))
		self.assertEqual(schema.field("E3002201").options, ("1", "2", "3", "4"))

	def test_the_schemas_are_those_of_the_catalogues(self):
		self.assertEqual(list(SCHEMAS), list(CATALOGUES))

	def test_a_year_without_its_schema_is_refused(self):
		for call in (lambda: schema_for(2027), lambda: build(2027, RETURN, sender())):
			with self.assertRaises(XmlError) as raised:
				call()
			self.assertEqual((raised.exception.template, raised.exception.values), (NO_SCHEMA, (2027,)))


class BuildTest(TestCase):
	def test_writes_e50_of_the_year_with_ust2a_and_then_the_vorsatz(self):
		root = written(RETURN)
		self.assertEqual((root.tag, root.get("version")), (f"{{{NAMESPACE}}}E50", "2026"))
		self.assertEqual(root.nsmap, {None: NAMESPACE})
		self.assertEqual([etree.QName(child).localname for child in root], ["USt2A", "Vorsatz"])
		vorsatz = {etree.QName(child).localname: child.text for child in root[1]}
		self.assertEqual((vorsatz["Unterfallart"], vorsatz["Zeitraum"]), ("50", "2026"))

	def test_writes_each_field_in_its_context_in_the_order_of_the_schema(self):
		values = {
			"E3011401": D("-900.00"),
			"E3003405": D("5276"),
			"E3001207": "Ort",
			"E3000901": "Musterunternehmen",
			"E3001203": "1",
			"E3003406": D("1002.44"),
		}
		self.assertEqual(
			leaves(written(values)),
			[
				("Allg/Unternehmen/E3000901", "Musterunternehmen"),
				("Allg/Unternehmen/Adr/E3001203", "1"),
				("Allg/Unternehmen/Adr/E3001207", "Ort"),
				("Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben/E3003405", "5276"),
				("Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben/E3003406", "1002,44"),
				("Berech_USt/Tabelle/Zahl_Erstatt/E3011401", "-900,00"),
			],
		)

	def test_writes_each_value_by_its_formatkennzeichen(self):
		values = {
			"E3003703": D("-14292"),
			"E3003704": D("-1000.4"),
			"E3005901": D("19"),
			"E3106101": D("250"),
			"E3001701": True,
			"E3007802": True,
			"E3001401": (date(2026, 2, 1), date(2026, 12, 31)),
			"E3002203": "2",
			"E3000902": "  Beispiel \n Handel  ",
		}
		self.assertEqual(
			texts(written(values)),
			{
				"E3000902": "Beispiel Handel",
				"E3001401": "01.02-31.12",
				"E3002203": "2",
				"E3001701": "1",
				"E3003703": "-14292",
				"E3003704": "-1000,40",
				"E3005901": "19,00",
				"E3106101": "250",
				"E3007802": "X",
			},
		)
		self.assertEqual(texts(written({"E3001601": date(2026, 3, 1)}))["E3001601"], "01.03.2026")

	def test_leaves_out_what_is_not_given_and_every_context_without_a_field(self):
		root = written({"E3000901": "Beispiel GmbH", "E3001101": None, "E3001701": False, "E3011101": None})
		self.assertEqual(leaves(root), [("Allg/Unternehmen/E3000901", "Beispiel GmbH")])

	def test_files_the_zeros_entries_gives_for_a_year_without_amounts(self):
		"""Kz 177 = 0 with its tax (rule 30449, unverified), Kz 816, line 125 and Kz 820 (30070, 30915, 30620)."""
		filed = texts(written(dict(entries(CATALOGUE, {}, D("0.00")))))
		for element, text in (
			("E3003303", "0"),
			("E3003304", "0,00"),
			("E3011101", "0,00"),
			("E3011301", "0,00"),
			("E3011401", "0,00"),
		):
			with self.subTest(element=element):
				self.assertEqual(filed[element], text)

	def test_refuses_a_value_the_pattern_of_its_field_does_not_take(self):
		for element, value, label in (
			("E3001203", "1a", "Hausnummer"),
			("E3001206", "00123", "Postleitzahl (Inland)"),
			("E3001403", "8033", "Postleitzahl zum Postfach"),
			("E3001404", "Fach 5", "Postfach"),
			("E3000401", "DE12345678", "Wirtschafts-Identifikationsnummer"),
		):
			with self.subTest(element=element), self.assertRaises(XmlError) as raised:
				written({element: value})
			self.assertEqual(
				(raised.exception.template, raised.exception.values, raised.exception.label),
				(erklaerung.NOT_IN_FORMAT, (value,), label),
			)

	def test_refuses_a_value_its_format_does_not_take(self):
		for element, value, template in (
			("E3003303", D("100.50"), erklaerung.NOT_WHOLE),
			("E3003304", D("19.005"), erklaerung.TOO_MANY_DECIMALS),
			("E3005901", D("-1.00"), erklaerung.NEGATIVE),
			("E3003303", D("1000000000000"), erklaerung.TOO_MANY_DIGITS),
			("E3002203", "4", erklaerung.NOT_AN_OPTION),
			("E3001203", "12345", ustva_xml.TEXT_TOO_LONG),
			("E3000901", "Beispiel ☃ GmbH", ustva_xml.TEXT_CHARACTERS),
			("E3001401", (date(2026, 6, 1), date(2026, 5, 1)), erklaerung.NOT_A_SPAN),
		):
			with self.subTest(element=element, value=value), self.assertRaises(XmlError) as raised:
				written({element: value})
			self.assertEqual(raised.exception.template, template)

	def test_takes_the_digits_before_the_comma_the_jd_gives_the_field(self):
		"""The Umfang der Verwendung im Erstjahr in line 95 takes more than twelve, up to its pattern."""
		grundstueck = {"E3007404": D("1234567890123.00")}
		self.assertEqual(texts(written({}, (grundstueck,)))["E3007404"], "1234567890123,00")
		with self.assertRaises(XmlError) as raised:
			written({}, ({"E3007404": D("12345678901234.00")},))
		self.assertEqual(raised.exception.template, erklaerung.NOT_IN_FORMAT)

	def test_refuses_a_value_of_the_wrong_type(self):
		for element, value in (("E3003303", 100), ("E3001701", "ja"), ("E3001601", "01.03.2026")):
			with self.subTest(element=element), self.assertRaises(TypeError):
				written({element: value})

	def test_refuses_a_field_the_form_does_not_have_and_one_steuerbote_does_not_file(self):
		"""A company resident abroad (Kz 125, Anlage UN), a Fiskalvertreter (Kz 126, Anlage FV) and the sales under §§ 25
		and 25a UStG are out of scope; the lines of a Kleinunternehmer are filed when the ledger feeds them."""
		for element, value in (
			("E9999999", "1"),
			("E3001402", True),
			("E3001801", True),
			("E3001208", "1010"),
			("E3005401", D("100")),
			("E3005403", D("100")),
			("E3010602", D("1.00")),
		):
			with self.subTest(element=element), self.assertRaises(ValueError):
				written({element: value})
		self.assertEqual(texts(written({"E3104701": D("5000")}))["E3104701"], "5000")

	def test_writes_each_grundstueck_of_line_95_in_a_context_of_its_own_after_kz_370(self):
		second = {"E3007401": "Beispielweg 7", "E3007405": D("1900")}
		root = written({"E3007301": True, "E3008501": True}, (GRUNDSTUECK, {}, second))
		self.assertEqual(
			leaves(root),
			[
				("Ber_VoSt_15a/Grdst_erstm_Verw/E3007301", "1"),
				("Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst/E3007401", "Beispielweg 5, 80331 München"),
				("Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst/E3007402", "01.04.2026"),
				("Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst/E3007403", "Vermietung an Unternehmer"),
				("Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst/E3007404", "100,00"),
				("Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst/E3007405", "38000"),
				("Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst/E3007406", "38000"),
				("Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst/E3007401", "Beispielweg 7"),
				("Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst/E3007405", "1900"),
				("Ber_VoSt_15a/Aend_Verh/E3008501", "1"),
			],
		)
		(verwendung,) = root.iter(f"{{{NAMESPACE}}}Grdst_erstm_Verw")
		self.assertEqual(
			[etree.QName(child).localname for child in verwendung], ["E3007301", *["Ang_Grdst"] * 2]
		)

	def test_line_95_takes_up_to_99_grundstuecke(self):
		self.assertEqual(len(list(written({}, (GRUNDSTUECK,) * 99).iter(f"{{{NAMESPACE}}}Ang_Grdst"))), 99)
		with self.assertRaises(XmlError) as raised:
			written({}, (GRUNDSTUECK,) * 100)
		self.assertEqual(
			(raised.exception.template, raised.exception.values), (TOO_MANY_GRUNDSTUECKE, (99, 100))
		)

	def test_the_fields_of_a_grundstueck_go_with_it(self):
		with self.assertRaisesRegex(ValueError, "E3007401 is a field of a Grundstück of line 95"):
			written({"E3007401": "Beispielweg 5"})
		with self.assertRaisesRegex(ValueError, "E3007301 is no field of a Grundstück of line 95"):
			written({}, ({"E3007301": True},))

	def test_the_nutzdaten_are_the_tree_as_text(self):
		text = to_nutzdaten(YEAR, RETURN, sender(), (GRUNDSTUECK,))
		self.assertEqual(text, GOLDEN.read_text(encoding="utf-8"))
		self.assertTrue(text.startswith(f'<E50 xmlns="{NAMESPACE}" version="2026">\n\t<USt2A>'))
		self.assertEqual(
			canonical(etree.fromstring(text.encode())), canonical(written(RETURN, (GRUNDSTUECK,)))
		)


class InventedReturnTest(TestCase):
	def test_the_invented_return_keeps_every_rule_steuerbote_checks(self):
		"""check() takes one value per field and so the Grundstück of line 95 with the rest."""
		self.assertEqual(check(YEAR, {**RETURN, **GRUNDSTUECK}), ())


class TranslationsTest(TestCase):
	def test_every_message_of_the_xml_has_a_translation(self):
		with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
			translated = {source for source, *_ in csv.reader(file)}
		self.assertEqual(sorted(set(ust2a_xml.MESSAGES) - translated), [])


class Ust2aDocumentationTest(TestCase):
	"""SCHEMAS against Jahresdokumentation_E50_2026.ods, the XML against E50-2026.xsd and elster11_E50_2026_extern.xsd,
	and the example Beispiele/USt_2026.xml written from its values."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.nutzdaten = etree.XMLSchema(etree.parse(str(jd.schema(YEAR))))

	def assert_valid(self, schema: etree.XMLSchema, element: etree._Element) -> None:
		if not schema.validate(element):
			self.fail(str(schema.error_log))

	def test_each_field_has_the_pattern_of_the_jd(self):
		patterns = {row["Name"]: row["Format als regulärer Ausdruck"] for row in jd.fields(YEAR)}
		for field in SCHEMAS[YEAR].fields:
			with self.subTest(element=field.feldkennung):
				self.assertEqual(field.pattern, patterns[field.feldkennung])

	def test_the_lists_take_the_values_the_schema_enumerates(self):
		root = etree.parse(str(jd.schema(YEAR))).getroot()
		for field in SCHEMAS[YEAR].fields:
			if field.options:
				with self.subTest(element=field.feldkennung):
					(element,) = root.iterfind(
						f".//{{{eric_schema.XSD}}}element[@name='{field.feldkennung}']"
					)
					(kind,) = root.iterfind(
						f"{{{eric_schema.XSD}}}complexType[@name='{element.get('type')}']"
					)
					values = [item.get("value") for item in kind.iter(f"{{{eric_schema.XSD}}}enumeration")]
					self.assertEqual(field.options, tuple(values))

	def test_the_forms_are_the_vordrucke_of_the_jd(self):
		documented = [
			line
			for line in eric_schema.lines(jd.jahresdokumentation(YEAR), "Allg. Information")
			if " - max. lfd. Nr. Vordruck" in line
		]
		self.assertEqual(
			documented,
			[
				f"{form.name} - max. lfd. Nr. Vordruck: {form.count}{' - Pflichtvordruck' if form.mandatory else ''}"
				for form in SCHEMAS[YEAR].forms
			],
		)

	def test_the_invented_return_passes_the_schema_of_the_nutzdaten_and_of_the_delivery(self):
		root = written(RETURN, (GRUNDSTUECK,))
		self.assert_valid(self.nutzdaten, root)
		envelope = eric_schema.erklaerung_envelope_schema("USt", "E50", YEAR)
		for testmerker in (True, False):
			with self.subTest(testmerker=testmerker):
				document = envelope_for(
					root,
					KIND,
					empfaenger=TEST_STEUERNUMMER[:4],
					hersteller_id="12345",
					testmerker=testmerker,
					datenlieferant="Beispiel GmbH; Erika Beispiel",
					produkt_version="0.1.0",
				)
				self.assert_valid(envelope, etree.fromstring(document))

	def test_every_field_steuerbote_files_is_written_where_the_schema_takes_it(self):
		values, grundstueck = every_field()
		self.assert_valid(self.nutzdaten, written(values, (grundstueck,) * 99))

	def test_writes_the_example_of_the_documentation_from_its_values(self):
		path = eric_schema.erklaerung_directory("USt") / "Beispiele" / "USt_2026.xml"
		(example,) = etree.parse(str(path)).getroot().iter(f"{{{NAMESPACE}}}E50")
		(form,) = example.iterchildren(f"{{{NAMESPACE}}}{MAIN_FORM}")
		values, grundstuecke = values_of(form)
		(head,) = example.iterchildren(f"{{{NAMESPACE}}}Vorsatz")
		fields = {etree.QName(child).localname: child.text for child in head}
		filer = Vorsatz(
			steuernummer=fields["StNr"],
			name=fields["AbsName"],
			street=fields["AbsStr"],
			postal_code=fields.get("AbsPlz"),
			city=fields["AbsOrt"],
			copyright=fields["Copyright"],
		)
		self.assertEqual(canonical(build(YEAR, values, filer, grundstuecke)), canonical(example))
