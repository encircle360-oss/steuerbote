"""The Vorsatz of the Erklärungen, also against the Jahresdokumentationen, schemas and examples of the ERiC
documentation 44.3.6.0, which has KSt and GewSt up to 2025."""

import copy
import csv
from pathlib import Path
from types import MappingProxyType
from unittest import TestCase

from lxml import etree

from steuerbote.elster import ustva_xml, vorsatz
from steuerbote.elster.tests import eric_schema
from steuerbote.elster.tests.examples import TEST_STEUERNUMMER
from steuerbote.elster.ustva_xml import XmlError
from steuerbote.elster.vorsatz import Vorsatz, append_to, copyright_text
from steuerbote.eric.datenart import Datenart, bilanz, gewst, kst, ust, ustva

TRANSLATIONS = Path(__file__).resolve().parents[2] / "translations" / "de.csv"
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


def written(kind: Datenart, filer: Vorsatz | None = None) -> etree._Element:
	"""The root of the Erklärung of the Datenart with the Vorsatz as its only child."""
	root = etree.Element(f"{{{kind.namespace}}}{kind.root}", nsmap={None: kind.namespace})
	root.set("version", kind.root_version)
	append_to(root, kind, filer or sender())
	return root


def canonical(element: etree._Element) -> bytes:
	"""The element in Canonical XML 2.0 without the white space between elements, with the namespace it inherits."""
	return etree.tostring(copy.deepcopy(element), method="c14n2", strip_text=True)


def children(element: etree._Element) -> list[tuple[str, str | None]]:
	return [(etree.QName(child).localname, child.text) for child in element]


class VorsatzTest(TestCase):
	def test_writes_the_fields_of_the_vorsatz_in_the_order_of_the_schema(self):
		(element,) = written(ust(2026))
		self.assertEqual(etree.QName(element).localname, "Vorsatz")
		self.assertEqual(
			children(element),
			[
				("Unterfallart", "50"),
				("Vorgang", "01"),
				("StNr", TEST_STEUERNUMMER),
				("Zeitraum", "2026"),
				("AbsName", "Beispiel GmbH"),
				("AbsStr", "Hauptstraße 1"),
				("AbsPlz", "80331"),
				("AbsOrt", "München"),
				("Copyright", COPYRIGHT),
				("OrdNrArt", "S"),
				("Rueckuebermittlung", None),
			],
		)
		self.assertEqual(children(element[-1]), [("Bescheid", "2")])

	def test_unterfallart_and_zeitraum_are_those_of_the_datenart(self):
		for kind, unterfallart in ((kst(2026), "30"), (gewst(2025), "20"), (ust(2027), "50")):
			with self.subTest(datenart=kind.version):
				(element,) = written(kind)
				values = dict(children(element))
				self.assertEqual((values["Unterfallart"], values["Zeitraum"]), (unterfallart, str(kind.year)))
				self.assertEqual(element.tag, f"{{{kind.namespace}}}Vorsatz")

	def test_takes_the_namespace_of_the_erklaerung_without_declaring_it_again(self):
		text = etree.tostring(written(ust(2026)), encoding="unicode")
		self.assertEqual(text.count("xmlns="), 1)

	def test_leaves_the_postal_code_out_without_one(self):
		(element,) = written(ust(2026), sender(postal_code=None))
		self.assertNotIn("AbsPlz", dict(children(element)))
		(element,) = written(ust(2026), sender(postal_code=" "))
		self.assertNotIn("AbsPlz", dict(children(element)))

	def test_asks_for_the_bescheiddaten_only_where_wanted(self):
		"""Rueckuebermittlung/Bescheid: 1 for yes, 2 for no, the default the maintainer chose."""
		(element,) = written(ust(2026), sender(bescheiddaten=True))
		self.assertEqual(children(element[-1]), [("Bescheid", "1")])

	def test_a_datenart_without_a_vorsatz_has_none(self):
		for kind in (ustva(2026), bilanz("6.9")):
			with self.subTest(datenart=kind.version), self.assertRaises(ValueError):
				append_to(etree.Element("root"), kind, sender())

	def test_refuses_a_steuernummer_of_another_shape(self):
		for value in ("919801131001", "9198111310010", "91980113100100", "9198 011310010", ""):
			with self.subTest(value=value), self.assertRaises(XmlError) as raised:
				sender(steuernummer=value)
			self.assertEqual(raised.exception.template, ustva_xml.NOT_A_STEUERNUMMER)

	def test_refuses_a_postal_code_that_is_no_german_one(self):
		for value in ("8033", "00331", "803310", "A0331"):
			with self.subTest(value=value), self.assertRaises(XmlError) as raised:
				sender(postal_code=value)
			self.assertEqual(raised.exception.template, vorsatz.NOT_A_POSTLEITZAHL)
		self.assertEqual(sender(postal_code="01067").postal_code, "01067")

	def test_keeps_the_texts_within_the_lengths_of_the_jahresdokumentation(self):
		for field, length in (("name", 45), ("street", 30), ("city", 29), ("copyright", 50)):
			with self.subTest(field=field):
				self.assertEqual(len(getattr(sender(**{field: "x" * length}), field)), length)
				with self.assertRaises(XmlError) as raised:
					sender(**{field: "x" * (length + 1)})
				self.assertEqual(raised.exception.template, ustva_xml.TEXT_TOO_LONG)
				self.assertEqual(raised.exception.values, (length + 1, length))

	def test_name_street_town_and_copyright_are_required(self):
		for field in ("name", "street", "city", "copyright"):
			with self.subTest(field=field), self.assertRaises(XmlError) as raised:
				sender(**{field: "  "})
			self.assertEqual(raised.exception.template, ustva_xml.TEXT_MISSING)

	def test_writes_the_texts_in_the_character_set_of_elster(self):
		filer = sender(name="Müller „Söhne“ GmbH", street="Hauptstraße\t1")
		self.assertEqual((filer.name, filer.street), ('Müller "Söhne" GmbH', "Hauptstraße 1"))
		with self.assertRaises(XmlError) as raised:
			sender(copyright="© 2026 Beispiel Software GmbH")
		self.assertEqual(raised.exception.template, ustva_xml.TEXT_CHARACTERS)
		self.assertEqual(raised.exception.label, vorsatz.COPYRIGHT_LABEL)


class CopyrightTextTest(TestCase):
	def test_is_the_copyright_as_the_vorsatz_writes_it(self):
		self.assertEqual(copyright_text(f"  {COPYRIGHT}\n"), COPYRIGHT)

	def test_refuses_an_empty_or_too_long_copyright(self):
		for value, template in (("", ustva_xml.TEXT_MISSING), ("x" * 51, ustva_xml.TEXT_TOO_LONG)):
			with self.subTest(value=value), self.assertRaises(XmlError) as raised:
				copyright_text(value)
			self.assertEqual(raised.exception.template, template)


class TranslationsTest(TestCase):
	def test_every_message_and_label_of_the_vorsatz_has_a_translation(self):
		with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
			translated = {source for source, *_ in csv.reader(file)}
		self.assertEqual(sorted({*vorsatz.MESSAGES, *vorsatz.LABELS} - translated), [])


class VorsatzDocumentationTest(TestCase):
	"""The Vorsatz against the sheets „Vorsatz - Felder“ of the Jahresdokumentationen, the schemas of the Nutzdaten and
	the examples of the ERiC documentation."""

	KINDS = (ust(2026), kst(2025), gewst(2025))
	EXAMPLES = MappingProxyType({"USt": "USt_2026.xml", "KSt": "kst_2025_ok.xml", "GewSt": "GewSt_2025.xml"})

	def fields(self, kind: Datenart) -> dict[str, dict[str, str]]:
		path = (
			eric_schema.erklaerung_directory(kind.name)
			/ "Jahresdokumentation"
			/ f"Jahresdokumentation_{kind.root}_{kind.year}.ods"
		)
		return {
			row["Name"]: row
			for row in eric_schema.sheet(path, "Vorsatz - Felder")
			if row["Änderungsinformation"] != "GEAENDERT_ALTE_VERSION"
		}

	def test_the_jahresdokumentation_gives_the_lengths_and_the_required_texts(self):
		for kind in self.KINDS:
			for name, (length, required) in vorsatz.TEXTS.items():
				with self.subTest(datenart=kind.version, field=name):
					row = self.fields(kind)[name]
					self.assertEqual((int(row["Max. Länge"]), row["Pflichtfeld"] == "Ja"), (length, required))

	def test_the_jahresdokumentation_takes_the_values_steuerbote_writes(self):
		for kind in self.KINDS:
			with self.subTest(datenart=kind.version):
				fields = self.fields(kind)
				self.assertIn(
					rf"\Q{vorsatz.VERANLAGUNG}\E", fields["Vorgang"]["Format als regulärer Ausdruck"]
				)
				self.assertIn(vorsatz.STEUERNUMMER, fields["OrdNrArt"]["Format als regulärer Ausdruck"])
				self.assertEqual(fields["StNr"]["Format als regulärer Ausdruck"], "([0-9]{4})0[0-9]{8}")
				self.assertEqual(fields["Bescheid"]["Format als regulärer Ausdruck"], "1|2")
				self.assertEqual(
					{name for name, row in fields.items() if row["Internes ERiC Feld"] == "Ja"},
					{"Ordnungsbegriff", "TeleNummer", "Bundesfinanzamtsnummer"},
				)

	def test_the_vorsatz_passes_the_schema_of_the_nutzdaten(self):
		for kind in self.KINDS:
			for filer in (sender(), sender(postal_code=None, bescheiddaten=True)):
				with self.subTest(datenart=kind.version, filer=filer):
					schema = etree.XMLSchema(etree.parse(str(eric_schema.documentation() / kind.schema)))
					root = written(kind, filer)
					if not schema.validate(root):
						self.fail(str(schema.error_log))

	def test_writes_the_vorsatz_of_the_examples_from_their_values(self):
		for kind in self.KINDS:
			with self.subTest(datenart=kind.version):
				path = eric_schema.erklaerung_directory(kind.name) / "Beispiele" / self.EXAMPLES[kind.name]
				(example,) = etree.parse(str(path)).getroot().iter(f"{{{kind.namespace}}}Vorsatz")
				values = dict(children(example))
				filer = Vorsatz(
					steuernummer=values["StNr"],
					name=values["AbsName"],
					street=values["AbsStr"],
					postal_code=values.get("AbsPlz"),
					city=values["AbsOrt"],
					copyright=values["Copyright"],
				)
				(ours,) = written(kind, filer)
				self.assertEqual(canonical(ours), canonical(example))
