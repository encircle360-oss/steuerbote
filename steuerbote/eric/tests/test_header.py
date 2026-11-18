from dataclasses import replace
from unittest import TestCase
from xml.etree import ElementTree

from steuerbote.eric.header import (
	ILLUSTRATION_HERSTELLER_ID,
	Datenart,
	EnvelopeHeader,
	datenart,
	datenteil,
	problems,
)
from steuerbote.eric.result import ERROR, TESTMERKER, Operation

NUTZDATEN = (
	'<Anmeldungssteuern xmlns="http://finkonsens.de/elster/elsteranmeldung/ustva/v2026" version="2026">'
	"<Steuerfall><Umsatzsteuervoranmeldung><Jahr>2026</Jahr><Zeitraum>10</Zeitraum>"
	"<Kz83>95.00</Kz83></Umsatzsteuervoranmeldung></Steuerfall></Anmeldungssteuern>"
)

HEADER = EnvelopeHeader(
	hersteller_id="12345",
	datenlieferant="Beispiel GmbH; Erika Beispiel; 089 1234567",
	produkt_name="Steuerbote",
	produkt_version="0.1.0",
	empfaenger_finanzamt="9198",
	datenart_version="UStVA_2026",
	testmerker=None,
	nutzdaten_ticket="1",
)


class DatenartTest(TestCase):
	def test_ustva_is_an_elster_anmeldung_sent_with_authentication(self):
		self.assertEqual(datenart("UStVA_2026"), Datenart("ElsterAnmeldung", "UStVA", "send-Auth", 2026))

	def test_names_the_plugin_library_of_the_year(self):
		self.assertEqual(datenart("UStVA_2027").plugin_library, "libcheckUStVA_2027.so")

	def test_refuses_other_datenart_versions(self):
		for version in ("ESt_2026", "UStVA_26", "UStVA_2026 ", "ustva_2026", "UStVA-2026", ""):
			with self.subTest(version=version), self.assertRaises(ValueError):
				datenart(version)


class DatenteilTest(TestCase):
	def test_heads_the_nutzdaten_with_the_nutzdaten_header(self):
		root = ElementTree.fromstring(datenteil(NUTZDATEN, HEADER))
		self.assertEqual(root.tag, "DatenTeil")
		self.assertEqual(root.attrib, {})
		header = root.find("Nutzdatenblock/NutzdatenHeader")
		self.assertEqual(header.attrib, {"version": "11"})
		self.assertEqual(header.findtext("NutzdatenTicket"), "1")
		self.assertEqual(header.find("Empfaenger").attrib, {"id": "F"})
		self.assertEqual(header.findtext("Empfaenger"), "9198")
		self.assertEqual(header.findtext("Hersteller/ProduktName"), "Steuerbote")
		self.assertEqual(header.findtext("Hersteller/ProduktVersion"), "0.1.0")
		nutzdaten = root.find("Nutzdatenblock/Nutzdaten")
		self.assertEqual(
			[child.tag for child in nutzdaten],
			["{http://finkonsens.de/elster/elsteranmeldung/ustva/v2026}Anmeldungssteuern"],
		)

	def test_keeps_the_nutzdaten_as_they_are(self):
		self.assertIn(f"<Nutzdaten>{NUTZDATEN}</Nutzdaten>", datenteil(NUTZDATEN, HEADER))

	def test_drops_the_declaration_and_byte_order_mark_of_the_nutzdaten(self):
		for prefix in (
			'<?xml version="1.0" encoding="ISO-8859-15" standalone="no"?>\n',
			"\ufeff<?xml version='1.0'?>",
			"\ufeff",
			"\n  ",
		):
			with self.subTest(prefix=prefix):
				self.assertIn(f"<Nutzdaten>{NUTZDATEN}</Nutzdaten>", datenteil(prefix + NUTZDATEN, HEADER))

	def test_escapes_the_header_values(self):
		text = datenteil(NUTZDATEN, replace(HEADER, produkt_name="A & B <C>"))
		self.assertIn("<ProduktName>A &amp; B &lt;C&gt;</ProduktName>", text)
		self.assertEqual(ElementTree.fromstring(text).findtext(".//ProduktName"), "A & B <C>")


class ProblemsTest(TestCase):
	def fields(self, header: EnvelopeHeader, operation: Operation = Operation.VALIDATE, **options) -> list:
		found = problems(header, operation, **options)
		self.assertTrue(all(message.severity == ERROR and message.code == "SB-HEADER" for message in found))
		return [message.field for message in found]

	def test_accepts_a_complete_header(self):
		self.assertEqual(self.fields(HEADER, check_hersteller_id=True), [])
		self.assertEqual(self.fields(HEADER, Operation.SEND, check_hersteller_id=True), [])

	def test_a_test_send_needs_the_testmerker_and_a_send_none(self):
		test = replace(HEADER, testmerker=TESTMERKER)
		self.assertEqual(self.fields(test, Operation.TEST_SEND), [])
		self.assertEqual(self.fields(HEADER, Operation.TEST_SEND), ["Testmerker"])
		self.assertEqual(
			self.fields(replace(HEADER, testmerker="700000001"), Operation.TEST_SEND), ["Testmerker"]
		)
		self.assertEqual(self.fields(test, Operation.SEND), ["Testmerker"])
		self.assertEqual(self.fields(test, Operation.VALIDATE), [])

	def test_checks_the_hersteller_id_only_when_asked(self):
		for hersteller_id in ("", "1234", "123456", "1234a", ILLUSTRATION_HERSTELLER_ID):
			with self.subTest(hersteller_id=hersteller_id):
				header = replace(HEADER, hersteller_id=hersteller_id)
				self.assertEqual(self.fields(header, check_hersteller_id=True), ["HerstellerID"])
				self.assertEqual(self.fields(header, check_hersteller_id=False), [])

	def test_names_each_field_out_of_shape(self):
		cases = {
			"Empfaenger": {"empfaenger_finanzamt": "919"},
			"NutzdatenTicket": {"nutzdaten_ticket": "x" * 33},
			"ProduktName": {"produkt_name": "ELSTER-Helfer"},
			"ProduktVersion": {"produkt_version": ""},
			"DatenLieferant": {"datenlieferant": " "},
			"datenartVersion": {"datenart_version": "UStVA_26"},
		}
		for field, change in cases.items():
			with self.subTest(field=field):
				self.assertEqual(self.fields(replace(HEADER, **change)), [field])

	def test_limits_follow_the_schema(self):
		self.assertEqual(self.fields(replace(HEADER, nutzdaten_ticket="x" * 32)), [])
		self.assertEqual(self.fields(replace(HEADER, nutzdaten_ticket="")), ["NutzdatenTicket"])
		self.assertEqual(self.fields(replace(HEADER, produkt_name="x" * 50)), [])
		self.assertEqual(self.fields(replace(HEADER, produkt_name="x" * 51)), ["ProduktName"])
		self.assertEqual(self.fields(replace(HEADER, produkt_version="1" * 51)), ["ProduktVersion"])
		self.assertEqual(self.fields(replace(HEADER, datenlieferant="x" * 256)), [])
		self.assertEqual(self.fields(replace(HEADER, datenlieferant="x" * 257)), ["DatenLieferant"])

	def test_the_product_name_must_not_contain_elster_in_any_case(self):
		self.assertEqual(self.fields(replace(HEADER, produkt_name="Mein Elster")), ["ProduktName"])
