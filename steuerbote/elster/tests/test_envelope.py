from unittest import TestCase

from lxml import etree

from steuerbote import __version__
from steuerbote.elster import ust1h_xml, ustva_xml, vorsatz
from steuerbote.elster.envelope import envelope_for, envelope_of, to_envelope, transfer_datenlieferant
from steuerbote.elster.tests import eric_schema
from steuerbote.elster.tests.examples import (
	CREATED,
	FIXTURES,
	anmeldung,
	antrag,
	children,
	elements,
	filer,
	parse,
	voranmeldung,
)
from steuerbote.elster.ustva_xml import XmlError, to_nutzdaten
from steuerbote.eric.datenart import EBILANZ_NAMESPACE, Datenart, bilanz, gewst, kst, ust

CONTACT = {"phone": "089 1234567", "email": "erika@example.org"}


def envelope(**arguments) -> bytes:
	values: dict = {"hersteller_id": "12345", "testmerker": True, "produkt_version": "0.1.0", **arguments}
	return to_envelope(filer(**CONTACT), voranmeldung(), CREATED, **values)


def header(document: bytes, name: str) -> list[tuple[str, str | None]]:
	(element,) = parse(document).iter(f"{{*}}{name}")
	return children(element)


class EnvelopeTest(TestCase):
	def test_writes_the_envelope_of_the_example_month(self):
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
			header(document, "Hersteller"), [("ProduktName", "steuerbote"), ("ProduktVersion", __version__)]
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


class Ust1HEnvelopeTest(TestCase):
	"""Form USt 1 H travels in the same envelope as the Voranmeldung, as the Datenart UStVA (HB table 2-13)."""

	def envelope(self, filing, **arguments) -> bytes:
		values: dict = {"hersteller_id": "12345", "testmerker": True, "produkt_version": "0.1.0", **arguments}
		nutzdaten = ust1h_xml.build(filer(**CONTACT), filing, CREATED, values["hersteller_id"])
		return envelope_of(nutzdaten, filer(**CONTACT), **values)

	def test_names_the_verfahren_datenart_and_vorgang_of_the_voranmeldung(self):
		for filing in (antrag(), anmeldung()):
			with self.subTest(context=filing.context):
				self.assertEqual(
					header(self.envelope(filing), "TransferHeader")[:5],
					header(envelope(), "TransferHeader")[:5],
				)
				self.assertEqual(
					header(self.envelope(filing, testmerker=False), "TransferHeader")[:4],
					[
						("Verfahren", "ElsterAnmeldung"),
						("DatenArt", "UStVA"),
						("Vorgang", "send-Auth"),
						("HerstellerID", "12345"),
					],
				)

	def test_sends_to_the_bundesfinanzamtsnummer_of_the_steuernummer(self):
		(empfaenger,) = parse(self.envelope(anmeldung())).iter("{*}Empfaenger")
		self.assertEqual((empfaenger.get("id"), empfaenger.text), ("F", "9198"))

	def test_carries_the_nutzdaten_of_the_form(self):
		(nutzdaten,) = parse(self.envelope(anmeldung())).iter("{*}Nutzdaten")
		(anmeldungssteuern,) = nutzdaten
		ours = ust1h_xml.build(filer(**CONTACT), anmeldung(), CREATED, "12345")
		self.assertEqual(
			etree.tostring(anmeldungssteuern, method="c14n2", strip_text=True),
			etree.tostring(ours, method="c14n2", strip_text=True),
		)

	def test_refuses_an_hersteller_id_of_another_shape(self):
		nutzdaten = ust1h_xml.build(filer(), antrag(), CREATED, "12345")
		with self.assertRaises(XmlError) as raised:
			envelope_of(nutzdaten, filer(), hersteller_id="74931", testmerker=True)
		self.assertEqual(raised.exception.template, ustva_xml.ILLUSTRATION_HERSTELLER_ID)


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


ERSTELLER = "Beispiel GmbH; Hauptstraße; 1; ; ; 80331; München; Deutschland; 089 1234567; info@example.org"


def erklaerung(kind: Datenart) -> etree._Element:
	"""The Nutzdaten of an Erklärung of the Datenart with nothing but its Vorsatz."""
	root = etree.Element(f"{{{kind.namespace}}}{kind.root}", nsmap={None: kind.namespace})
	root.set("version", kind.root_version)
	filer = vorsatz.Vorsatz(
		steuernummer="9198011310010",
		name="Beispiel GmbH",
		street="Hauptstraße 1",
		postal_code="80331",
		city="München",
		copyright="(c) 2026 Beispiel Software GmbH, München",
	)
	vorsatz.append_to(root, kind, filer)
	return root


def ebilanz() -> etree._Element:
	"""The Nutzdaten of an E-Bilanz: its Stichtag and an XBRL instance without facts."""
	root = etree.Element(f"{{{EBILANZ_NAMESPACE}}}EBilanz", nsmap={"ebilanz": EBILANZ_NAMESPACE}, version="2")
	etree.SubElement(root, f"{{{EBILANZ_NAMESPACE}}}stichtag").text = "20261231"
	etree.SubElement(
		root, "{http://www.xbrl.org/2003/instance}xbrl", nsmap={"xbrli": "http://www.xbrl.org/2003/instance"}
	)
	return root


def delivery(nutzdaten: etree._Element, kind: Datenart, **arguments) -> bytes:
	values: dict = {
		"empfaenger": "9198",
		"hersteller_id": "12345",
		"testmerker": True,
		"datenlieferant": "Beispiel GmbH; Erika Beispiel",
		"produkt_version": "0.1.0",
		**arguments,
	}
	return envelope_for(nutzdaten, kind, **values)


class ErklaerungEnvelopeTest(TestCase):
	"""The envelope of an Erklärung follows elster11_<root>_<Jahr>_extern.xsd of its Datenart (ERiC-Entwicklerhandbuch
	44.3.6.0, Tabellen 7-9, 7-13 and 7-15)."""

	def test_names_the_verfahren_datenart_and_vorgang_of_the_erklaerung(self):
		fields = header(delivery(erklaerung(ust(2026)), ust(2026)), "TransferHeader")
		self.assertEqual(
			fields[:6],
			[
				("Verfahren", "ElsterErklaerung"),
				("DatenArt", "USt"),
				("Vorgang", "send-Auth"),
				("Testmerker", "700000004"),
				("HerstellerID", "12345"),
				("DatenLieferant", "Beispiel GmbH; Erika Beispiel"),
			],
		)
		self.assertEqual([name for name, _ in fields[6:]], ["Datei"])

	def test_sends_to_the_finanzamt_and_carries_the_nutzdaten(self):
		document = delivery(erklaerung(kst(2026)), kst(2026), testmerker=False)
		(empfaenger,) = parse(document).iter("{*}Empfaenger")
		self.assertEqual((empfaenger.get("id"), empfaenger.text), ("F", "9198"))
		self.assertNotIn("Testmerker", dict(header(document, "TransferHeader")))
		((nutzdaten,),) = parse(document).iter("{*}Nutzdaten")
		self.assertEqual(
			etree.tostring(nutzdaten, method="c14n2", strip_text=True),
			etree.tostring(erklaerung(kst(2026)), method="c14n2", strip_text=True),
		)

	def test_refuses_an_hersteller_id_of_another_shape(self):
		with self.assertRaises(XmlError) as raised:
			delivery(erklaerung(ust(2026)), ust(2026), hersteller_id="74931")
		self.assertEqual(raised.exception.template, ustva_xml.ILLUSTRATION_HERSTELLER_ID)

	def test_passes_the_schema_of_the_delivery_of_each_erklaerung(self):
		for kind in (ust(2026), kst(2025), gewst(2025)):
			for testmerker in (True, False):
				with self.subTest(datenart=kind.version, testmerker=testmerker):
					schema = eric_schema.erklaerung_envelope_schema(kind.name, kind.root, kind.year)
					document = etree.fromstring(delivery(erklaerung(kind), kind, testmerker=testmerker))
					if not schema.validate(document):
						self.fail(str(schema.error_log))


class BilanzEnvelopeTest(TestCase):
	"""The envelope of an E-Bilanz follows ebilanz_000002.xsd with the DatenLieferant in its NutzdatenHeader
	(ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 9.7.1)."""

	def test_names_the_datenlieferant_of_the_nutzdaten_header_after_the_hersteller(self):
		document = delivery(ebilanz(), bilanz("6.9"), nutzdaten_datenlieferant=ERSTELLER)
		self.assertEqual(
			[name for name, _ in header(document, "NutzdatenHeader")],
			["NutzdatenTicket", "Empfaenger", "Hersteller", "DatenLieferant"],
		)
		self.assertEqual(dict(header(document, "NutzdatenHeader"))["DatenLieferant"], ERSTELLER)
		self.assertEqual(dict(header(document, "TransferHeader"))["Verfahren"], "ElsterBilanz")

	def test_another_delivery_names_none(self):
		names = [name for name, _ in header(delivery(erklaerung(ust(2026)), ust(2026)), "NutzdatenHeader")]
		self.assertNotIn("DatenLieferant", names)

	def test_passes_the_schema_of_the_delivery_of_the_bilanz(self):
		for testmerker in (True, False):
			with self.subTest(testmerker=testmerker):
				schema = eric_schema.bilanz_envelope_schema()
				document = etree.fromstring(
					delivery(
						ebilanz(), bilanz("6.9"), testmerker=testmerker, nutzdaten_datenlieferant=ERSTELLER
					)
				)
				if not schema.validate(document):
					self.fail(str(schema.error_log))
