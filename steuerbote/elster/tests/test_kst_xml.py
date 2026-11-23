"""The Nutzdaten E30 of the Körperschaftsteuererklärung, also against the schema E30-2025.xsd and the example
kst_2025_ok.xml of the ERiC documentation 44.3.6.0."""

import copy
from collections import Counter
from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from lxml import etree

from steuerbote.elster import kst_xml
from steuerbote.elster.envelope import envelope_for
from steuerbote.elster.erklaerung import Field, FormCatalogue
from steuerbote.elster.kst_xml import SCHEMAS, Schema, nutzdaten, schema_for, to_nutzdaten
from steuerbote.elster.tests import eric_schema
from steuerbote.elster.tests.examples import TEST_STEUERNUMMER
from steuerbote.elster.ustva_xml import XmlError
from steuerbote.elster.vorsatz import Vorsatz
from steuerbote.eric.datenart import kst
from steuerbote.kst.einlagekonto import roll_forward
from steuerbote.kst.form import CATALOGUES, Entry, Vordruck, catalogue_for, entries, kst1f, vordrucke
from steuerbote.kst.tests import jahresdokumentation as jd
from steuerbote.kst.tests.support import FIGURES
from steuerbote.kst.tests.test_golden import koerperschaftsteuer
from steuerbote.kst.years import YEARS
from steuerbote.ustva.years import UnknownYearError

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "kst_2026_muster_it_gmbh.xml"
ZERO = Decimal("0")
COPYRIGHT = "(c) 2026 Beispiel Software GmbH, München"
VORSATZ = Vorsatz(TEST_STEUERNUMMER, "Muster IT GmbH", "Musterweg 1", "Musterstadt", COPYRIGHT, "12345")
# Invented: the Muster IT GmbH with its only Anteilseignerin for the whole VZ.
KST1 = Vordruck(
	"KSt1",
	(
		*entries(
			{
				"E8000016": True,
				"E8000101": "Muster IT GmbH",
				"E8000501": "Musterstadt",
				"E8000601": "Musterstadt",
				"E8001105": "350",
				"E8002606": date(2026, 1, 1),
				"E8002607": date(2026, 12, 31),
				"E8001007": False,
				"E8122601": False,
			}
		),
		Entry("E8122101", "Erika Muster", (0,)),
		Entry("E8122102", "Musterweg 2", (0,)),
		Entry("E8122103", "12345 Musterstadt", (0,)),
		Entry("E8122104", Decimal("25000.00"), (0, 0)),
		Entry("E8122105", Decimal("100"), (0, 0)),
		Entry("E8122106", date(2026, 1, 1), (0, 0)),
		Entry("E8122107", date(2026, 12, 31), (0, 0)),
	),
)
SAMPLES = {
	"N": Decimal("1"),
	"U": Decimal("1"),
	"G": Decimal("1"),
	"M": Decimal("1"),
	"%": Decimal("1.00"),
	"P": Decimal("1.00"),
	"R": Decimal("1.00"),
	"S": Decimal("1.00"),
	"F": Decimal("1"),
	"V": Decimal("1"),
	"J": True,
	"X": True,
	"Y": True,
	"D": date(2026, 1, 31),
	"T": date(2026, 1, 31),
	"B": (date(2026, 1, 1), date(2026, 12, 31)),
	"Z": (date(2026, 1, 1), date(2026, 12, 31)),
	"A": TEST_STEUERNUMMER,
	"I": "12345678903",
	"O": "1",
	"C": "x",
}
"""An invented value per Formatkennzeichen that each field of it takes, but for those of PATTERN_SAMPLES."""
PATTERN_SAMPLES = {
	"DE[0-9]{9}": "DE000000000",
	r"^(?=.{4,4}$)(?=.*[1-9].*)(?!0\d)\d{1,15}$": Decimal("2025"),
	"2": Decimal("2"),
	"91160[0-9]{8}": "9116000000000",
	"^(?=.{5,5}$)([0]{1}[1-9]{1}[0-9]{3})|([1-9]{1}[0-9]{4})": "12345",
	"[1-9]|[1-2][0-9]|[3][0-2]": "1",
	r"^(?=.{8,10}$)(?!0\d)\d{1,3}(,\d{6,6})$": "12,000000",
	"^(?=.{12,12}$)[A-Z]{2}[A-Z0-9]{9}[0-9]{1}": "XX0000000000",
	"^(?=.{1,4}$)[0-9]+": "1",
}
"""Invented values for the fields whose pattern the value of their Formatkennzeichen does not match."""
FIELD_SAMPLES = {
	# E30-2025.xsd takes only a negative Übernahmeverlust, GanzzahlNichtNullOhneFuehrNull_MaxVK12_MaxWm1_CType.
	"E8007014": Decimal("-1"),
	"E4003208": "DEA20260131ABC123",
	"E4003209": "DED20260131ABC123",
}
"""Invented values for single fields: the Registriernummer and Offenlegungsnummer of GewSt 1 A have a pattern of their
own."""


# Invented: the single values of the sales and the write-down of the worked example, Anlage GK lines 161 to 166a and
# 184 to 186.
SALES = (
	Entry("E8561202", "Delta AG", (0,)),
	Entry("E8561213", date(2026, 5, 4), (0,)),
	Entry("E8561211", Decimal("30000.00"), (0,)),
	Entry("E8561202", "Epsilon GmbH", (1,)),
	Entry("E8561213", date(2026, 9, 30), (1,)),
	Entry("E8561403", Decimal("12000.00"), (1,)),
	Entry("E8561402", "Zeta GmbH", (0,)),
	Entry("E8561408", Decimal("4000"), (0,)),
)


def muster_it_gmbh() -> tuple[Vordruck, ...]:
	"""The Vordrucke of the worked example „Muster IT GmbH“ with its KSt 1, the single values of its sales, Anlage WA
	line 15 and KSt 1 F."""
	found = {vordruck.form: vordruck for vordruck in vordrucke(koerperschaftsteuer())}
	found["GK"] = found["GK"].extended(*SALES)
	found["WA"] = found["WA"].extended(Entry("E8122801", False))
	return (KST1, *found.values(), kst1f(roll_forward(ZERO, FIGURES)))


def sample(field: Field) -> object:
	if field.feldkennung in FIELD_SAMPLES:
		return FIELD_SAMPLES[field.feldkennung]
	if field.format == "H":
		return field.options[0]
	return PATTERN_SAMPLES.get(field.pattern or "", SAMPLES[field.format])


def rows_of(field: Field, schema: Schema, row: int = 0) -> tuple[int, ...]:
	"""The instances of the repeated contexts of the field, all ``row``."""
	return tuple(row for prefix in prefixes(field) if prefix in schema.repeats)


def prefixes(field: Field) -> Iterator[str]:
	names = [part for part in field.context.split("/") if part]
	for length in range(len(names)):
		yield "/".join((field.form, *names[: length + 1]))


def every_field(catalogue: FormCatalogue, schema: Schema, form: str, row: int = 0) -> tuple[Entry, ...]:
	"""An entry with an invented value for each field of the Vordruck."""
	return tuple(
		Entry(field.feldkennung, sample(field), rows_of(field, schema, row))
		for field in catalogue.fields
		if field.form == form
	)


def names(element: etree._Element) -> list[str]:
	return [etree.QName(child).localname for child in element]


def canonical(element: etree._Element) -> bytes:
	return etree.tostring(copy.deepcopy(element), method="c14n2", strip_text=True)


def value_of(field: Field, text: str) -> object:
	"""The value a text of the field stands for, the reverse of Field.text."""
	if field.format in "NUGMP%RSFV":
		return Decimal(text.replace(",", "."))
	if field.format in "JXY":
		return text != "2"
	if field.format == "D":
		return datetime.strptime(text, "%d.%m.%Y").date()
	if field.format == "T":
		return datetime.strptime(f"{text}2026", "%d.%m.%Y").date()
	if field.format == "B":
		begin, end = text.split("-")
		return tuple(datetime.strptime(f"{day}.2026", "%d.%m.%Y").date() for day in (begin, end))
	if field.format == "Z":
		return tuple(datetime.strptime(day, "%d.%m.%Y").date() for day in text.split("-"))
	return text


def vordrucke_of(root: etree._Element, catalogue: FormCatalogue, schema: Schema) -> tuple[Vordruck, ...]:
	"""The Vordrucke of Nutzdaten that the catalogue has, with the values of their fields."""
	fields = {field.feldkennung: field for field in catalogue.fields}
	forms = {form.name for form in catalogue.forms} - {"Vorsatz"}
	found = []
	for element in root:
		form = etree.QName(element).localname
		if form in forms:
			wj = element.findtext(f"{{{catalogue.datenart.namespace}}}{kst_xml.INDEX}")
			found.append(Vordruck(form, tuple(_entries(element, form, fields, schema)), wj))
	return tuple(found)


def _entries(
	node: etree._Element, path: str, fields: dict[str, Field], schema: Schema, rows: tuple[int, ...] = ()
) -> Iterator[Entry]:
	instances: Counter[str] = Counter()
	for child in node:
		name = etree.QName(child).localname
		if len(child):
			here = f"{path}/{name}"
			if here in schema.repeats:
				yield from _entries(child, here, fields, schema, (*rows, instances[name]))
				instances[name] += 1
			else:
				yield from _entries(child, here, fields, schema, rows)
		elif name != kst_xml.INDEX:
			yield Entry(name, value_of(fields[name], child.text or ""), rows)


def written(*given: Vordruck, year: int = 2026) -> etree._Element:
	"""The Nutzdaten of the Vordrucke, with the KSt 1 of the example unless one is given."""
	if not any(vordruck.form == "KSt1" for vordruck in given):
		given = (KST1, *given)
	return nutzdaten(year, given, VORSATZ)


def vordruck_of(root: etree._Element, form: str) -> etree._Element:
	(element,) = (child for child in root if etree.QName(child).localname == form)
	return element


class YearsTest(TestCase):
	def test_hold_exactly_the_years_of_the_catalogues(self):
		self.assertEqual(tuple(SCHEMAS), tuple(CATALOGUES))
		self.assertEqual(tuple(SCHEMAS), tuple(YEARS))
		self.assertEqual(schema_for(2026).documentation_year, 2025)
		self.assertEqual(schema_for(2026).indexed, frozenset({"GK", "KSt1F"}))

	def test_a_year_without_a_schema_is_refused(self):
		with self.assertRaises(UnknownYearError) as raised:
			schema_for(2027)
		self.assertEqual(str(raised.exception), "no schema E30 for 2027; known years: 2026")
		with self.assertRaises(UnknownYearError):
			nutzdaten(2027, (KST1,), VORSATZ)


class StructureTest(TestCase):
	def test_writes_e30_in_the_namespace_and_the_version_of_the_vz(self):
		root = written()
		self.assertEqual(root.tag, f"{{{kst(2026).namespace}}}E30")
		self.assertEqual(root.get("version"), "2026")
		self.assertEqual(root.nsmap, {None: "http://finkonsens.de/elster/elstererklaerung/kst/e30/v2026"})

	def test_writes_the_vordrucke_in_the_order_of_the_schema_and_the_vorsatz_last(self):
		root = nutzdaten(2026, tuple(reversed(muster_it_gmbh())), VORSATZ)
		self.assertEqual(names(root), ["KSt1", "GK", "ZVE", "Z", "WA", "KSt1F", "Vorsatz"])
		vorsatz = vordruck_of(root, "Vorsatz")
		self.assertEqual(
			(vorsatz.findtext("{*}Unterfallart"), vorsatz.findtext("{*}Zeitraum")), ("30", "2026")
		)

	def test_writes_the_muster_it_gmbh(self):
		self.assertEqual(to_nutzdaten(2026, muster_it_gmbh(), VORSATZ), FIXTURE.read_text(encoding="utf-8"))

	def test_anlage_gk_and_kst_1_f_begin_with_their_wirtschaftsjahr(self):
		amounts = entries({"E8002001": Decimal("100"), "E8109901": Decimal("100")})
		root = written(
			Vordruck("GK", amounts, "WJ2"), Vordruck("GK", amounts, "WJ1"), kst1f(roll_forward(ZERO, FIGURES))
		)
		first, second = (child for child in root if etree.QName(child).localname == "GK")
		self.assertEqual((names(first)[0], first[0].text), ("WJ", "WJ1"))
		self.assertEqual((names(second)[0], second[0].text), ("WJ", "WJ2"))
		self.assertEqual(names(vordruck_of(root, "KSt1F"))[0], "WJ")

	def test_writes_each_context_once_with_its_fields_in_the_order_of_the_schema(self):
		forward = Vordruck("KSt1", KST1.entries)
		backward = Vordruck("KSt1", tuple(reversed(KST1.entries)))
		self.assertEqual(canonical(written(forward)), canonical(written(backward)))
		steuerpflicht = vordruck_of(written(), "KSt1").find("{*}Steuerpflicht")
		self.assertEqual(names(steuerpflicht), ["E8000501", "E8000601", "Rechtsform"])

	def test_writes_each_instance_of_a_repeated_context_in_its_order(self):
		shareholders = KST1.extended(
			Entry("E8122101", "Max Muster", (1,)),
			Entry("E8122104", Decimal("5000.00"), (0, 1)),
			Entry("E8122106", date(2025, 6, 1), (1, 0)),
		)
		einzel = vordruck_of(written(shareholders), "KSt1").findall("{*}AE/{*}Einzel")
		self.assertEqual([item.findtext("{*}E8122101") for item in einzel], ["Erika Muster", "Max Muster"])
		self.assertEqual(
			[besitz.findtext("{*}E8122104") for besitz in einzel[0].findall("{*}Besitzdauer")],
			["25000,00", "5000,00"],
		)
		self.assertEqual(einzel[1].findtext("{*}Besitzdauer/{*}E8122106"), "01.06.2025")

	def test_leaves_out_none_a_yes_field_that_says_no_and_a_vordruck_without_a_value(self):
		root = written(
			Vordruck("Z", entries({"E8005602": None, "E8009401": None})),
			Vordruck("WA", entries({"E8122801": False, "E8122711": False, "E8120401": None})),
		)
		self.assertNotIn("Z", names(root))
		self.assertEqual(etree.tostring(vordruck_of(root, "WA"), encoding="unicode").count("<"), 6)
		self.assertEqual(vordruck_of(root, "WA").findtext("{*}AE/{*}E8122801"), "2")
		self.assertIsNone(vordruck_of(root, "WA").find("{*}Erwerb_P8c"))


class RefusalTest(TestCase):
	def assert_refused(self, message: str, *given: Vordruck) -> None:
		with self.assertRaises(ValueError) as raised:
			written(*given)
		self.assertEqual(str(raised.exception), message)

	def test_refuses_a_vordruck_or_a_field_the_catalogue_lacks(self):
		source = catalogue_for(2026).source
		self.assert_refused(f"{source} has no Vordruck OT", Vordruck("OT", entries({"E8165020": "x"})))
		self.assert_refused(f"{source} has no Vordruck Vorsatz", Vordruck("Vorsatz"))
		self.assert_refused(f"{source} has no field E3000901", Vordruck("ZVE", entries({"E3000901": "x"})))

	def test_refuses_a_field_on_another_vordruck_or_twice(self):
		self.assert_refused(
			"the field E8109901 belongs to GK, not to ZVE",
			Vordruck("ZVE", entries({"E8109901": Decimal("1")})),
		)
		twice = Vordruck("ZVE", (Entry("E8005401", Decimal("1")), Entry("E8005401", Decimal("2"))))
		self.assert_refused("ZVE: the field E8005401 stands twice in ()", twice)

	def test_refuses_instances_that_do_not_fit_the_repeated_contexts(self):
		self.assert_refused(
			"E8122101 lies in 1 contexts that repeat, so it needs as many instances, not ()",
			KST1.extended(Entry("E8122101", "Max Muster")),
		)
		self.assert_refused(
			"E8000101 lies in 0 contexts that repeat, so it needs as many instances, not (0,)",
			Vordruck("KSt1", (Entry("E8000101", "Muster IT GmbH", (0,)),)),
		)
		self.assert_refused(
			"KSt1/AE/Einzel/Besitzdauer repeats at most 3 times, not 4",
			KST1.extended(Entry("E8122104", Decimal("1.00"), (0, 3))),
		)
		self.assertIsNotNone(written(KST1.extended(Entry("E8122101", "x", (98,)))))
		self.assert_refused(
			"KSt1/AE/Einzel repeats at most 99 times, not 100", KST1.extended(Entry("E8122101", "x", (99,)))
		)

	def test_refuses_a_missing_wrong_or_second_indexfeld(self):
		gk = entries({"E8109901": Decimal("1")})
		self.assert_refused("the Vordruck GK needs its Indexfeld WJ, one of WJ1, WJ2", Vordruck("GK", gk))
		self.assert_refused(
			"the Vordruck GK needs its Indexfeld WJ, one of WJ1, WJ2", Vordruck("GK", gk, "WJ3")
		)
		self.assert_refused(
			"the Vordruck ZVE has no Indexfeld WJ", Vordruck("ZVE", entries({"E8005401": ZERO}), "WJ1")
		)
		self.assert_refused(
			"the Vordruck GK stands twice for WJ1", Vordruck("GK", gk, "WJ1"), Vordruck("GK", gk, "WJ1")
		)

	def test_refuses_more_vordrucke_than_the_jahresdokumentation_allows(self):
		z = Vordruck("Z", entries({"E8010101": ZERO}))
		self.assert_refused(f"{catalogue_for(2026).source} takes at most 1 Vordrucke Z", z, z)

	def test_refuses_an_erklaerung_without_its_pflichtvordruck(self):
		with self.assertRaises(ValueError) as raised:
			nutzdaten(2026, (Vordruck("ZVE", entries({"E8005401": ZERO})),), VORSATZ)
		self.assertEqual(str(raised.exception), "the Erklärung needs its Pflichtvordruck KSt1")
		with self.assertRaises(ValueError):
			nutzdaten(2026, (Vordruck("KSt1", entries({"E8000101": None})),), VORSATZ)

	def test_refuses_a_value_its_field_does_not_take(self):
		with self.assertRaises(XmlError):
			written(Vordruck("ZVE", entries({"E8007501": Decimal("1.50")})))


class SchemaTest(TestCase):
	"""The Nutzdaten against E30-2025.xsd in the namespace and version of 2025, and in the envelope of
	elster11_E30_2025_extern.xsd (steuerbote.kst.tests.jahresdokumentation)."""

	def assert_valid(self, root: etree._Element) -> None:
		schema = jd.nutzdaten_schema(jd.KST, schema_for(2026).documentation_year)
		document = jd.in_documentation_year(root, kst(2026), kst(2025))
		if not schema.validate(document):
			self.fail(str(schema.error_log))

	def test_the_muster_it_gmbh_follows_the_schema(self):
		self.assert_valid(nutzdaten(2026, muster_it_gmbh(), VORSATZ))

	def test_every_field_of_each_vordruck_follows_the_schema(self):
		catalogue, schema = catalogue_for(2026), schema_for(2026)
		for form in catalogue.forms[1:-1]:
			with self.subTest(form=form.name):
				wj = "WJ1" if form.name in schema.indexed else None
				vordruck = Vordruck(form.name, every_field(catalogue, schema, form.name), wj)
				self.assert_valid(written(vordruck))
		with self.subTest(form="KSt1"):
			self.assert_valid(written(Vordruck("KSt1", every_field(catalogue, schema, "KSt1"))))

	def test_a_second_instance_of_each_repeated_context_and_wirtschaftsjahr_follows_the_schema(self):
		catalogue, schema = catalogue_for(2026), schema_for(2026)
		given = []
		for form in catalogue.forms[:-1]:
			for wj in ("WJ1", "WJ2") if form.name in schema.indexed else (None,):
				both = (
					*every_field(catalogue, schema, form.name),
					*every_field(catalogue, schema, form.name, 1),
				)
				given.append(Vordruck(form.name, tuple(dict.fromkeys(both)), wj))
		self.assert_valid(written(*given))

	def test_the_contexts_that_repeat_and_the_vordrucke_are_those_of_the_schema(self):
		schema = schema_for(2026)
		found = jd.occurrences(jd.KST, schema.documentation_year)
		forms = {form.name for form in catalogue_for(2026).forms}
		self.assertEqual(
			dict(schema.repeats),
			{path: int(most) for path, most in found.items() if "/" in path and path.split("/")[0] in forms},
		)
		for form in catalogue_for(2026).forms:
			with self.subTest(form=form.name):
				self.assertEqual(form.count, int(found.get(form.name, "1")))
		self.assertEqual(
			tuple(name for name in jd.form_order(jd.KST, schema.documentation_year) if name in forms),
			tuple(form.name for form in catalogue_for(2026).forms),
		)

	def test_the_envelope_follows_the_schema_of_the_delivery(self):
		schema = eric_schema.erklaerung_envelope_schema("KSt", "E30", 2025)
		document = envelope_for(
			jd.in_documentation_year(nutzdaten(2026, muster_it_gmbh(), VORSATZ), kst(2026), kst(2025)),
			kst(2025),
			empfaenger=TEST_STEUERNUMMER[:4],
			hersteller_id="12345",
			testmerker=True,
			datenlieferant="Muster IT GmbH; Erika Muster",
		)
		if not schema.validate(etree.fromstring(document)):
			self.fail(str(schema.error_log))


class ExampleTest(TestCase):
	"""kst_2025_ok.xml of the documentation, written again from the values of its Vordrucke that Steuerbote has: KSt 1,
	Anlage GK, Anlage ZVE and KSt 1 F, without the Anlagen ZinsS, ZwiG and OT."""

	def test_writes_the_vordrucke_of_the_example(self):
		kind = kst(2025)
		document = etree.parse(str(jd.example(jd.KST, "kst_2025_ok.xml"))).getroot()
		((example,),) = document.iter(f"{{{eric_schema.ELSTER_XML}}}Nutzdaten")
		catalogue, schema = catalogue_for(2026), schema_for(2026)
		found = vordrucke_of(jd.in_documentation_year(example, kind, kst(2026)), catalogue, schema)
		self.assertEqual([vordruck.form for vordruck in found], ["KSt1", "GK", "ZVE", "KSt1F"])
		ours = jd.in_documentation_year(nutzdaten(2026, found, VORSATZ), kst(2026), kind)
		forms = {vordruck.form for vordruck in found}
		self.assertEqual(
			[canonical(child) for child in ours if etree.QName(child).localname in forms],
			[canonical(child) for child in example if etree.QName(child).localname in forms],
		)
