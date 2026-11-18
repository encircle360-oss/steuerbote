from unittest import TestCase

from steuerbote import __version__
from steuerbote.elster import ustva_xml
from steuerbote.elster.envelope import to_envelope, transfer_datenlieferant
from steuerbote.elster.tests.examples import (
	CREATED,
	FIXTURES,
	children,
	elements,
	filer,
	parse,
	voranmeldung,
)
from steuerbote.elster.ustva_xml import XmlError, to_nutzdaten

CONTACT = {"phone": "089 1234567", "email": "erika@example.org"}


def envelope(**arguments) -> bytes:
	values: dict = {"hersteller_id": "12345", "testmerker": True, "produkt_version": "0.1.0", **arguments}
	return to_envelope(filer(**CONTACT), voranmeldung(), CREATED, **values)


def header(document: bytes, name: str) -> list[tuple[str, str | None]]:
	(element,) = parse(document).iter(f"{{*}}{name}")
	return children(element)


class EnvelopeTest(TestCase):
	def test_writes_the_example_of_the_specification(self):
		self.assertEqual(envelope(contact="Erika Beispiel"), (FIXTURES / "envelope_2026_10.xml").read_bytes())

	def test_is_utf_8_with_the_elster_namespace_alone_on_the_root(self):
		document = envelope()
		self.assertTrue(
			document.startswith(
				b'<?xml version="1.0" encoding="UTF-8"?>\n<Elster xmlns="http://www.elster.de/elsterxml/schema/v11">\n'
			)
		)
		self.assertIn("Hauptstraße".encode(), document)

	def test_a_real_case_carries_no_testmerker(self):
		self.assertIn(("Testmerker", "700000004"), header(envelope(), "TransferHeader"))
		self.assertNotIn("Testmerker", dict(header(envelope(testmerker=False), "TransferHeader")))

	def test_leaves_to_eric_and_the_server_what_they_set(self):
		self.assertEqual(
			[name for name, _ in header(envelope(), "TransferHeader")],
			["Verfahren", "DatenArt", "Vorgang", "Testmerker", "HerstellerID", "DatenLieferant", "Datei"],
		)

	def test_sends_to_the_bundesfinanzamtsnummer_of_the_steuernummer(self):
		(empfaenger,) = parse(envelope()).iter("{*}Empfaenger")
		self.assertEqual((empfaenger.get("id"), empfaenger.text), ("F", "9198"))

	def test_names_steuerbote_and_its_version_as_the_product(self):
		document = to_envelope(filer(), voranmeldung(), CREATED, hersteller_id="12345", testmerker=True)
		self.assertEqual(
			header(document, "Hersteller"), [("ProduktName", "Steuerbote"), ("ProduktVersion", __version__)]
		)

	def test_carries_the_nutzdaten_with_kz09(self):
		self.assertEqual(
			elements(envelope()), elements(to_nutzdaten(filer(**CONTACT), voranmeldung(), CREATED, "12345"))
		)
		self.assertIn(("Kz09", "12345"), elements(envelope()))

	def test_refuses_an_hersteller_id_of_another_shape(self):
		for value, template in (
			("1234", ustva_xml.NOT_A_HERSTELLER_ID),
			("74931", ustva_xml.ILLUSTRATION_HERSTELLER_ID),
		):
			with self.subTest(value=value), self.assertRaises(XmlError) as raised:
				envelope(hersteller_id=value)
			self.assertEqual(raised.exception.template, template)

	def test_keeps_the_header_texts_within_the_schema(self):
		cases = {
			"ProduktVersion longer than 50": {"produkt_version": "1." * 26},
			"empty ProduktVersion": {"produkt_version": " "},
			"NutzdatenTicket longer than 32": {"nutzdaten_ticket": "x" * 33},
			"empty NutzdatenTicket": {"nutzdaten_ticket": ""},
		}
		for case, arguments in cases.items():
			with self.subTest(case), self.assertRaises(XmlError):
				envelope(**arguments)
		self.assertIn(
			("NutzdatenTicket", "x" * 32), header(envelope(nutzdaten_ticket="x" * 32), "NutzdatenHeader")
		)


class TransferDatenlieferantTest(TestCase):
	def test_follows_the_structure_the_schema_describes(self):
		self.assertEqual(
			transfer_datenlieferant(filer(**CONTACT), "Erika Beispiel"),
			"Beispiel GmbH; Erika Beispiel; 089 1234567; erika@example.org; München; 80331; Hauptstraße 1; "
			"Deutschland",
		)

	def test_keeps_the_place_of_what_is_missing(self):
		self.assertEqual(
			transfer_datenlieferant(filer()),
			"Beispiel GmbH; ; ; ; München; 80331; Hauptstraße 1; Deutschland",
		)

	def test_has_at_most_256_characters(self):
		with self.assertRaises(XmlError) as raised:
			transfer_datenlieferant(filer(**CONTACT), "x" * 200)
		self.assertEqual(raised.exception.template, ustva_xml.TEXT_TOO_LONG)
		self.assertEqual(raised.exception.values[1], 256)
