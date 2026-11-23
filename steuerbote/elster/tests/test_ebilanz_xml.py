"""The Nutzdaten of the E-Bilanz of the invented GmbH: the element EBilanz with the Bilanzstichtag and the instance,
the delivery against ebilanz_000002.xsd and its golden file, and the size ERiC takes."""

import csv
from dataclasses import replace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from lxml import etree

from steuerbote.ebilanz.instance import EBilanzError, Sources
from steuerbote.ebilanz.tests.test_gcd import MASTER, OPENING
from steuerbote.ebilanz.tests.test_instance import OPENING_BOOKS, built
from steuerbote.elster import ebilanz_xml
from steuerbote.elster.tests import eric_schema
from steuerbote.elster.ustva_xml import XmlError
from steuerbote.eric.datenart import EBILANZ_NAMESPACE, bilanz
from steuerbote.eric.header import nutzdaten_datenlieferant

FIXTURES = Path(__file__).parent / "fixtures"
TRANSLATIONS = Path(__file__).parents[2] / "translations" / "de.csv"
XBRL = "{http://www.xbrl.org/2003/instance}xbrl"
EBILANZ = f"{{{EBILANZ_NAMESPACE}}}"
DATENLIEFERANT = nutzdaten_datenlieferant(
	name="Beispiel Werkstatt GmbH",
	street="Musterweg",
	house_number="12",
	house_number_suffix="a",
	postal_code="12345",
	city="Musterstadt",
	country="Deutschland",
	phone="0123 456789",
	email="info@example.org",
)


def delivery(ebilanz, **arguments) -> bytes:
	return ebilanz_xml.envelope(
		ebilanz,
		**{
			"hersteller_id": "12345",
			"testmerker": True,
			"datenlieferant": "Beispiel Werkstatt GmbH; Erika Beispiel",
			"nutzdaten_datenlieferant": DATENLIEFERANT,
			"produkt_version": "0.1.0",
			**arguments,
		},
	)


class NutzdatenTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.ebilanz = built()

	def test_wraps_the_instance_with_its_stichtag(self):
		"""ebilanz_000002.xsd; Leitfaden B.2.2 and rule 170205022: the stichtag is the Bilanzstichtag of the GCD."""
		root = ebilanz_xml.nutzdaten(self.ebilanz)
		self.assertEqual((root.tag, root.get("version")), (f"{EBILANZ}EBilanz", "2"))
		stichtag, instance = root
		self.assertEqual((stichtag.tag, stichtag.text), (f"{EBILANZ}stichtag", "20261231"))
		self.assertEqual(instance.tag, XBRL)
		(closing,) = instance.iter(
			"{http://www.xbrl.de/taxonomies/de-gcd-2025-04-01}genInfo.report.period.balSheetClosingDate"
		)
		self.assertEqual(closing.text, "2026-12-31")

	def test_the_stichtag_of_an_eroeffnungsbilanz_is_its_first_day(self):
		opening = built(sources=Sources(OPENING_BOOKS, first_year=True), statement_type="EB", periods=OPENING)
		self.assertEqual(ebilanz_xml.nutzdaten(opening)[0].text, "20260301")

	def test_the_datenart_of_the_taxonomy(self):
		self.assertEqual(ebilanz_xml.datenart(self.ebilanz), bilanz("6.9"))

	def test_gives_the_nutzdaten_as_text_for_the_datenteil(self):
		text = ebilanz_xml.to_nutzdaten(self.ebilanz)
		self.assertTrue(text.startswith(f'<ebilanz:EBilanz xmlns:ebilanz="{EBILANZ_NAMESPACE}" version="2">'))
		self.assertEqual(etree.fromstring(text.encode("utf-8"))[1].tag, XBRL)

	def test_refuses_more_than_erics_100_mib(self):
		"""ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.3.8.1, Tabelle 5-7."""
		self.assertEqual(ebilanz_xml.MAX_NUTZDATEN_BYTES, 100 * 1024 * 1024 - 64 * 1024)
		with patch.object(ebilanz_xml, "MAX_NUTZDATEN_BYTES", 1000):
			with self.assertRaises(XmlError) as raised:
				ebilanz_xml.to_nutzdaten(self.ebilanz)
			self.assertEqual(raised.exception.template, ebilanz_xml.TOO_LARGE)
			with self.assertRaises(XmlError):
				delivery(self.ebilanz)

	def test_an_e_bilanz_without_an_instance_has_no_nutzdaten(self):
		with self.assertRaises(EBilanzError):
			ebilanz_xml.nutzdaten(built(replace(MASTER, steuernummer=None)))


class DeliveryTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.ebilanz = built()

	def test_writes_the_delivery_of_its_golden_file(self):
		self.assertEqual(delivery(self.ebilanz), (FIXTURES / "ebilanz_2026_gmbh.xml").read_bytes())

	def test_goes_to_the_finanzamt_of_the_steuernummer_with_the_datenlieferant(self):
		"""Leitfaden B.2.1 a; ERiC-Entwicklerhandbuch, Kap. 9.7.1."""
		root = etree.fromstring(delivery(self.ebilanz))
		(empfaenger,) = root.iter("{*}Empfaenger")
		self.assertEqual((empfaenger.get("id"), empfaenger.text), ("F", "9198"))
		header = next(root.iter("{*}NutzdatenHeader"))
		self.assertEqual(
			(etree.QName(header[-1]).localname, header[-1].text), ("DatenLieferant", DATENLIEFERANT)
		)
		(verfahren,) = root.iter("{*}Verfahren")
		self.assertEqual(verfahren.text, "ElsterBilanz")

	def test_passes_the_schema_of_the_delivery_of_the_bilanz(self):
		for testmerker in (True, False):
			with self.subTest(testmerker=testmerker):
				schema = eric_schema.bilanz_envelope_schema()
				document = etree.fromstring(delivery(self.ebilanz, testmerker=testmerker))
				if not schema.validate(document):
					self.fail(str(schema.error_log))


class TranslationsTest(TestCase):
	def test_every_message_has_a_translation(self):
		with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
			translated = {source for source, *_ in csv.reader(file)}
		self.assertEqual(sorted(set(ebilanz_xml.MESSAGES) - translated), [])
