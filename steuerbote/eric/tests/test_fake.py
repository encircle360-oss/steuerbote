import hashlib
import os
import re
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, mock

from steuerbote.eric.fake import DOCUMENTATION_VARIABLE, SIMULATED_VERSION, Simulation, placeholder_pdf
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import ERROR, HINT, TESTMERKER, Operation, Outcome

NAMESPACE = "http://finkonsens.de/elster/elsteranmeldung/ustva/v2026"
NUTZDATEN = (
	f'<Anmeldungssteuern xmlns="{NAMESPACE}" version="2026">\n'
	"\t<Erstellungsdatum>20261118</Erstellungsdatum>\n"
	"\t<Steuerfall>\n"
	"\t\t<Umsatzsteuervoranmeldung>\n"
	"\t\t\t<Jahr>2026</Jahr>\n"
	"\t\t\t<Zeitraum>10</Zeitraum>\n"
	"\t\t\t<Steuernummer>9198011310010</Steuernummer>\n"
	"\t\t\t<Kz81>1000</Kz81>\n"
	"\t\t\t<Kz83>190.00</Kz83>\n"
	"\t\t</Umsatzsteuervoranmeldung>\n"
	"\t</Steuerfall>\n"
	"</Anmeldungssteuern>\n"
)
HEADER = EnvelopeHeader(
	hersteller_id="00000",
	datenlieferant="Beispiel GmbH",
	produkt_name="Steuerbote",
	produkt_version="0.1.0",
	empfaenger_finanzamt="9198",
	datenart_version="UStVA_2026",
	testmerker=None,
	nutzdaten_ticket="1",
)
TEST_HEADER = replace(HEADER, testmerker=TESTMERKER)

# A schema of our own with the shape of the UStVA schema, for the test of the schema check: the schemas of
# the ERiC documentation may not be passed on.
SCHEMA = f"""<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="{NAMESPACE}" targetNamespace="{NAMESPACE}"
	elementFormDefault="qualified">
	<xs:element name="Anmeldungssteuern">
		<xs:complexType>
			<xs:sequence>
				<xs:element name="Erstellungsdatum" type="xs:string"/>
				<xs:element name="Steuerfall">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="Umsatzsteuervoranmeldung">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="Jahr" type="xs:gYear"/>
										<xs:element name="Zeitraum" type="xs:string"/>
										<xs:element name="Steuernummer" type="xs:string"/>
										<xs:element name="Kz81" type="xs:integer" minOccurs="0"/>
										<xs:element name="Kz83" type="xs:decimal" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
			</xs:sequence>
			<xs:attribute name="version" type="xs:string" use="required"/>
		</xs:complexType>
	</xs:element>
</xs:schema>
"""


def codes(result) -> list[str]:
	return [message.code for message in result.messages]


class SimulationTestCase(TestCase):
	def setUp(self):
		self.directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-fake-"))
		self.addCleanup(shutil.rmtree, self.directory)
		patcher = mock.patch.dict(os.environ)
		patcher.start()
		self.addCleanup(patcher.stop)
		os.environ.pop(DOCUMENTATION_VARIABLE, None)

	def documentation(self, root: Path, year: int = 2026) -> Path:
		schema = (
			root / "Datenarten" / "ElsterAnmeldung" / "UStVA" / "Schema" / str(year) / f"UStVA-{year}.xsd"
		)
		schema.parent.mkdir(parents=True)
		schema.write_text(SCHEMA, encoding="utf-8")
		return root


class ValidateTest(SimulationTestCase):
	def test_valid_nutzdaten_are_valid_and_nothing_is_sent(self):
		result = Simulation().run(Operation.VALIDATE, NUTZDATEN, HEADER)
		self.assertTrue(result.ok)
		self.assertIs(result.outcome, Outcome.VALID)
		self.assertTrue(result.simulated)
		self.assertEqual(result.eric_version, SIMULATED_VERSION)
		self.assertIsNone(result.transferticket)
		self.assertIsNone(result.protocol_pdf)
		self.assertIsNone(result.server_response_xml)
		self.assertEqual(codes(result), ["SIM-000", "SIM-001"])
		self.assertTrue(all(message.severity == HINT for message in result.messages))
		self.assertIn("nichts an ELSTER übermittelt", result.messages[0].text)

	def test_accepts_a_declaration_before_the_nutzdaten(self):
		declared = '<?xml version="1.0" encoding="ISO-8859-15" standalone="no"?>\n' + NUTZDATEN
		self.assertTrue(Simulation().run(Operation.VALIDATE, declared, HEADER).ok)

	def test_nutzdaten_that_are_no_xml_are_invalid(self):
		result = Simulation().run(Operation.VALIDATE, "<Anmeldungssteuern>", HEADER)
		self.assertIs(result.outcome, Outcome.INVALID)
		self.assertIn("SIM-002", codes(result))

	def test_the_root_must_be_anmeldungssteuern_of_the_year(self):
		for nutzdaten in (
			NUTZDATEN.replace("Anmeldungssteuern", "Erklaerungssteuern"),
			NUTZDATEN.replace("v2026", "v2025"),
		):
			with self.subTest(nutzdaten=nutzdaten[:80]):
				result = Simulation().run(Operation.VALIDATE, nutzdaten, HEADER)
				self.assertIs(result.outcome, Outcome.INVALID)
				(error,) = (message for message in result.messages if message.severity == ERROR)
				self.assertEqual((error.code, error.field), ("SIM-003", "Anmeldungssteuern"))

	def test_kz83_is_mandatory(self):
		result = Simulation().run(
			Operation.VALIDATE, NUTZDATEN.replace("\t\t\t<Kz83>190.00</Kz83>\n", ""), HEADER
		)
		self.assertIs(result.outcome, Outcome.INVALID)
		(error,) = (message for message in result.messages if message.severity == ERROR)
		self.assertEqual((error.code, error.field), ("SIM-004", "Kz83"))
		self.assertIn("110085064", error.text)

	def test_checks_the_header(self):
		result = Simulation().run(Operation.VALIDATE, NUTZDATEN, replace(HEADER, empfaenger_finanzamt="91"))
		self.assertIs(result.outcome, Outcome.INVALID)
		self.assertIn("SB-HEADER", codes(result))

	def test_needs_no_hersteller_id(self):
		self.assertTrue(Simulation().run(Operation.VALIDATE, NUTZDATEN, replace(HEADER, hersteller_id="")).ok)


class SchemaTest(SimulationTestCase):
	def test_validates_against_the_schema_of_the_documentation(self):
		simulation = Simulation(self.documentation(self.directory / "Dokumentation"))
		result = simulation.run(Operation.VALIDATE, NUTZDATEN, HEADER)
		self.assertTrue(result.ok)
		self.assertEqual(codes(result), ["SIM-000"])
		invalid = simulation.run(
			Operation.VALIDATE, NUTZDATEN.replace("<Kz81>1000</Kz81>", "<Kz81>1.000</Kz81>"), HEADER
		)
		self.assertIs(invalid.outcome, Outcome.INVALID)
		(error,) = (message for message in invalid.messages if message.severity == ERROR)
		self.assertEqual(error.code, "SIM-005")
		self.assertIn("UStVA-2026.xsd", error.text)
		self.assertIn("Kz81", error.text)

	def test_finds_the_documentation_in_the_unzipped_package(self):
		self.documentation(self.directory / "ERiC-44.3.6.0" / "Dokumentation")
		os.environ[DOCUMENTATION_VARIABLE] = str(self.directory)
		self.assertEqual(codes(Simulation().run(Operation.VALIDATE, NUTZDATEN, HEADER)), ["SIM-000"])

	def test_without_a_schema_of_the_year_it_checks_the_structure_only(self):
		simulation = Simulation(self.documentation(self.directory / "Dokumentation", year=2025))
		result = simulation.run(Operation.VALIDATE, NUTZDATEN, HEADER)
		self.assertEqual(codes(result), ["SIM-000", "SIM-001"])
		self.assertIn("2026", result.messages[1].text)

	def test_without_lxml_it_checks_the_structure_only(self):
		simulation = Simulation(self.documentation(self.directory / "Dokumentation"))
		with mock.patch.dict(sys.modules, {"lxml": None, "lxml.etree": None}):
			result = simulation.run(Operation.VALIDATE, NUTZDATEN, HEADER)
		self.assertEqual(codes(result), ["SIM-000", "SIM-001"])
		self.assertIn("lxml", result.messages[1].text)

	def test_refuses_external_entities_in_the_nutzdaten(self):
		simulation = Simulation(self.documentation(self.directory / "Dokumentation"))
		secret = self.directory / "secret.txt"
		secret.write_text("geheim", encoding="utf-8")
		nutzdaten = f'<!DOCTYPE a [<!ENTITY x SYSTEM "file://{secret}">]>' + NUTZDATEN.replace(
			"10</Zeitraum>", "&x;</Zeitraum>"
		)
		result = simulation.run(Operation.VALIDATE, nutzdaten, HEADER)
		self.assertIs(result.outcome, Outcome.INVALID)
		self.assertNotIn("geheim", " ".join(message.text for message in result.messages))


class SendTest(SimulationTestCase):
	def test_a_test_send_is_accepted_with_a_simulated_ticket_and_pdf(self):
		result = Simulation().run(Operation.TEST_SEND, NUTZDATEN, TEST_HEADER)
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertEqual(result.testmerker, TESTMERKER)
		self.assertEqual(result.transferticket, "SIM-" + hashlib.sha256(NUTZDATEN.encode()).hexdigest()[:28])
		self.assertEqual(len(result.transferticket), 32)
		self.assertTrue(result.protocol_pdf.startswith(b"%PDF-1.4\n"))
		self.assertIn("Simulation, keine Übermittlung".encode("cp1252"), result.protocol_pdf)
		self.assertIn(result.transferticket.encode(), result.protocol_pdf)
		self.assertIn(b"Kennzahl 83: 190.00", result.protocol_pdf)
		self.assertIn(b"Zeitraum: 10/2026", result.protocol_pdf)
		self.assertIn(b"Vorgang: Testsenden", result.protocol_pdf)

	def test_a_send_is_accepted_without_testmerker(self):
		result = Simulation().run(Operation.SEND, NUTZDATEN, HEADER)
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertIsNone(result.testmerker)
		self.assertIn(b"Vorgang: Senden", result.protocol_pdf)

	def test_is_deterministic(self):
		first = Simulation().run(Operation.TEST_SEND, NUTZDATEN, TEST_HEADER)
		self.assertEqual(Simulation().run(Operation.TEST_SEND, NUTZDATEN, TEST_HEADER), first)

	def test_a_simulated_ticket_never_looks_like_a_real_one(self):
		ticket = Simulation().run(Operation.SEND, NUTZDATEN, HEADER).transferticket
		self.assertIsNone(re.fullmatch(r"[a-z0-9]{32}", ticket))

	def test_invalid_data_are_not_sent(self):
		result = Simulation().run(Operation.SEND, "keine Daten", HEADER)
		self.assertIs(result.outcome, Outcome.INVALID)
		self.assertIsNone(result.transferticket)
		self.assertIsNone(result.protocol_pdf)

	def test_the_testmerker_must_match_the_operation(self):
		self.assertIs(Simulation().run(Operation.TEST_SEND, NUTZDATEN, HEADER).outcome, Outcome.INVALID)
		self.assertIs(Simulation().run(Operation.SEND, NUTZDATEN, TEST_HEADER).outcome, Outcome.INVALID)


class PlaceholderPdfTest(TestCase):
	def test_is_one_page_with_a_valid_cross_reference_table(self):
		pdf = placeholder_pdf("Titel", ["Erste Zeile", "Zweite Zeile mit Ü und ß"])
		self.assertTrue(pdf.startswith(b"%PDF-1.4\n"))
		self.assertTrue(pdf.endswith(b"%%EOF\n"))
		self.assertIn(b"/Count 1", pdf)
		self.assertIn(b"/BaseFont /Helvetica /Encoding /WinAnsiEncoding", pdf)
		self.assertIn(b"/BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding", pdf)
		startxref = int(pdf.rsplit(b"startxref\n", 1)[1].split(b"\n", 1)[0])
		self.assertTrue(pdf[startxref:].startswith(b"xref\n0 7\n"))
		entries = pdf[startxref:].split(b"\n")[3:9]
		for number, entry in enumerate(entries, 1):
			with self.subTest(object=number):
				self.assertEqual(len(entry + b"\n"), 20)
				offset = int(entry[:10])
				self.assertTrue(pdf[offset:].startswith(b"%d 0 obj\n" % number))
		self.assertIn(b"(Titel) Tj", pdf)
		self.assertIn("(Zweite Zeile mit Ü und ß) '".encode("cp1252"), pdf)

	def test_the_stream_length_is_exact(self):
		pdf = placeholder_pdf("Titel", ["Text"])
		length = int(re.search(rb"/Length (\d+)", pdf)[1])
		stream = pdf.split(b"stream\n", 1)[1].split(b"\nendstream", 1)[0]
		self.assertEqual(len(stream), length)

	def test_escapes_what_pdf_strings_reserve(self):
		self.assertIn(rb"(a \(b\) c\\d) '", placeholder_pdf("Titel", ["a (b) c\\d"]))

	def test_replaces_characters_outside_the_encoding(self):
		self.assertIn(b"(Preis ? 5) '", placeholder_pdf("Titel", ["Preis \u2248 5"]))
