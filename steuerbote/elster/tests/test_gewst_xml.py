"""The Nutzdaten E20 of the Gewerbesteuererklärung, also against the schema E20-2025.xsd and the example
GewSt_2025.xml of the ERiC documentation 44.3.6.0."""

from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from lxml import etree

from steuerbote.elster.envelope import envelope_for
from steuerbote.elster.gewst_xml import SCHEMAS, nutzdaten, schema_for, to_nutzdaten
from steuerbote.elster.tests import eric_schema
from steuerbote.elster.tests.examples import TEST_STEUERNUMMER
from steuerbote.elster.tests.test_kst_xml import VORSATZ, canonical, every_field, names, vordrucke_of
from steuerbote.eric.datenart import gewst
from steuerbote.gewst.form import CATALOGUES, catalogue_for, vordrucke
from steuerbote.gewst.years import YEARS
from steuerbote.kst.form import Entry, Vordruck, entries
from steuerbote.kst.tests import jahresdokumentation as jd
from steuerbote.kst.tests.test_golden import gewerbesteuer, koerperschaftsteuer
from steuerbote.ustva.years import UnknownYearError

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gewst_2026_muster_it_gmbh.xml"
# Invented: the Muster IT GmbH with its only Betriebsstätte in Musterstadt.
GENERAL = entries(
	{
		"E4000101": "Muster IT GmbH",
		"E4000201": "Softwareentwicklung",
		"E4000501": "350",
		"E4001506": False,
		"E4001102": False,
		"E4001110": "12345",
		"E4001111": "Musterstadt",
	}
)


# Invented: the receipt of the donation of the worked example, lines 92a to 92c.
RECEIPTS = (
	Entry("E4009220", "Musterverein e. V.", (0,)),
	Entry("E4009221", Decimal("1000.00"), (0,)),
	Entry("E4009222", "1", (0,)),
)


def muster_it_gmbh() -> tuple[Vordruck, ...]:
	"""The Vordrucke of the worked example „Muster IT GmbH“ with the general details of GewSt 1 A and the receipt of
	its donation."""
	gewst_1a, *begs = vordrucke(gewerbesteuer(koerperschaftsteuer()))
	return (gewst_1a.extended(*GENERAL, *RECEIPTS), *begs)


def beg(name: str) -> Vordruck:
	return Vordruck("BEG", entries({"E4050201": name, "E4050601": Decimal("100")}))


class YearsTest(TestCase):
	def test_hold_exactly_the_years_of_the_catalogues(self):
		self.assertEqual(tuple(SCHEMAS), tuple(CATALOGUES))
		self.assertEqual(tuple(SCHEMAS), tuple(YEARS))
		self.assertEqual(schema_for(2026).documentation_year, 2025)
		self.assertEqual(schema_for(2026).indexed, frozenset())

	def test_a_year_without_a_schema_is_refused(self):
		with self.assertRaises(UnknownYearError) as raised:
			schema_for(2027)
		self.assertEqual(str(raised.exception), "no schema E20 for 2027; known years: 2026")
		with self.assertRaises(UnknownYearError):
			nutzdaten(2027, muster_it_gmbh(), VORSATZ)


class StructureTest(TestCase):
	def test_writes_e20_with_gewst_1_a_an_anlage_beg_per_holding_and_the_vorsatz_last(self):
		root = nutzdaten(2026, (beg("Gamma AG"), *muster_it_gmbh()), VORSATZ)
		self.assertEqual(root.tag, f"{{{gewst(2026).namespace}}}E20")
		self.assertEqual(root.get("version"), "2026")
		self.assertEqual(names(root), ["GewSt1A", "BEG", "BEG", "Vorsatz"])
		self.assertEqual(
			[element.findtext("{*}Allg/{*}E4050201") for element in root.findall("{*}BEG")],
			["Gamma AG", "Beta GmbH"],
		)
		vorsatz = root.find("{*}Vorsatz")
		self.assertEqual(
			(vorsatz.findtext("{*}Unterfallart"), vorsatz.findtext("{*}Zeitraum")), ("20", "2026")
		)

	def test_writes_the_muster_it_gmbh(self):
		self.assertEqual(to_nutzdaten(2026, muster_it_gmbh(), VORSATZ), FIXTURE.read_text(encoding="utf-8"))

	def test_writes_each_instance_of_a_repeated_context_in_its_order(self):
		gewst_1a, *_ = muster_it_gmbh()
		donations = gewst_1a.extended(
			Entry("E4009221", Decimal("600.00"), (2,)), Entry("E4009221", Decimal("400.00"), (1,))
		)
		root = nutzdaten(2026, (donations,), VORSATZ)
		self.assertEqual(
			[
				item.text
				for item in root.iterfind("{*}GewSt1A/{*}Kuerz/{*}Zuw/{*}Stb_Zweck/{*}Einz/{*}E4009221")
			],
			["1000,00", "400,00", "600,00"],
		)


class RefusalTest(TestCase):
	def test_refuses_an_erklaerung_without_gewst_1_a(self):
		with self.assertRaises(ValueError) as raised:
			nutzdaten(2026, (beg("Beta GmbH"),), VORSATZ)
		self.assertEqual(str(raised.exception), "the Erklärung needs its Pflichtvordruck GewSt1A")

	def test_refuses_more_than_99_anlagen_beg_and_an_indexfeld(self):
		gewst_1a, *_ = muster_it_gmbh()
		self.assertEqual(
			len(nutzdaten(2026, (gewst_1a, *(beg(f"Holding {n}") for n in range(99))), VORSATZ)), 101
		)
		with self.assertRaises(ValueError) as raised:
			nutzdaten(2026, (gewst_1a, *(beg(f"Holding {n}") for n in range(100))), VORSATZ)
		self.assertEqual(
			str(raised.exception), f"{catalogue_for(2026).source} takes at most 99 Vordrucke BEG"
		)
		with self.assertRaises(ValueError) as raised:
			nutzdaten(2026, (Vordruck("GewSt1A", gewst_1a.entries, "WJ1"),), VORSATZ)
		self.assertEqual(str(raised.exception), "the Vordruck GewSt1A has no Indexfeld WJ")


class SchemaTest(TestCase):
	"""The Nutzdaten against E20-2025.xsd in the namespace and version of 2025, and in the envelope of
	elster11_E20_2025_extern.xsd (steuerbote.kst.tests.jahresdokumentation)."""

	def assert_valid(self, root: etree._Element) -> None:
		schema = jd.nutzdaten_schema(jd.GEWST, schema_for(2026).documentation_year)
		document = jd.in_documentation_year(root, gewst(2026), gewst(2025))
		if not schema.validate(document):
			self.fail(str(schema.error_log))

	def test_the_muster_it_gmbh_follows_the_schema(self):
		self.assert_valid(nutzdaten(2026, muster_it_gmbh(), VORSATZ))

	def test_every_field_in_two_instances_of_each_repeated_context_follows_the_schema(self):
		catalogue, schema = catalogue_for(2026), schema_for(2026)
		given = []
		for form in ("GewSt1A", "BEG", "BEG"):
			both = (*every_field(catalogue, schema, form), *every_field(catalogue, schema, form, 1))
			given.append(Vordruck(form, tuple(dict.fromkeys(both))))
		self.assert_valid(nutzdaten(2026, given, VORSATZ))

	def test_the_contexts_that_repeat_and_the_vordrucke_are_those_of_the_schema(self):
		schema = schema_for(2026)
		found = jd.occurrences(jd.GEWST, schema.documentation_year)
		forms = {form.name for form in catalogue_for(2026).forms}
		self.assertEqual(
			dict(schema.repeats),
			{path: int(most) for path, most in found.items() if "/" in path and path.split("/")[0] in forms},
		)
		for form in catalogue_for(2026).forms:
			with self.subTest(form=form.name):
				self.assertEqual(form.count, int(found.get(form.name, "1")))
		self.assertEqual(
			tuple(name for name in jd.form_order(jd.GEWST, schema.documentation_year) if name in forms),
			tuple(form.name for form in catalogue_for(2026).forms),
		)

	def test_the_envelope_follows_the_schema_of_the_delivery(self):
		schema = eric_schema.erklaerung_envelope_schema("GewSt", "E20", 2025)
		document = envelope_for(
			jd.in_documentation_year(nutzdaten(2026, muster_it_gmbh(), VORSATZ), gewst(2026), gewst(2025)),
			gewst(2025),
			empfaenger=TEST_STEUERNUMMER[:4],
			hersteller_id="12345",
			testmerker=True,
			datenlieferant="Muster IT GmbH; Erika Muster",
		)
		if not schema.validate(etree.fromstring(document)):
			self.fail(str(schema.error_log))


class ExampleTest(TestCase):
	"""GewSt_2025.xml of the documentation, written again from the values of its GewSt 1 A."""

	def test_writes_the_vordrucke_of_the_example(self):
		kind = gewst(2025)
		document = etree.parse(str(jd.example(jd.GEWST, "GewSt_2025.xml"))).getroot()
		((example,),) = document.iter(f"{{{eric_schema.ELSTER_XML}}}Nutzdaten")
		found = vordrucke_of(
			jd.in_documentation_year(example, kind, gewst(2026)), catalogue_for(2026), schema_for(2026)
		)
		self.assertEqual([vordruck.form for vordruck in found], ["GewSt1A"])
		ours = jd.in_documentation_year(nutzdaten(2026, found, VORSATZ), gewst(2026), kind)
		self.assertEqual(canonical(ours[0]), canonical(example[0]))
