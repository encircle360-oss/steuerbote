import ctypes
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from steuerbote.eric import api
from steuerbote.eric.api import (
	DRUCKE,
	PRUEFE_HINWEISE,
	SENDE,
	VALIDIERE,
	EncryptionParameters,
	EricError,
	EricLibrary,
	Pdf,
	PrintParameters,
)
from steuerbote.eric.tests import stub

DELIVERY = (
	'<?xml version="1.0" encoding="UTF-8"?>'
	'<Elster xmlns="http://www.elster.de/elsterxml/schema/v11"><TransferHeader version="11">'
	"<Verfahren>ElsterAnmeldung</Verfahren><DatenArt>UStVA</DatenArt><Vorgang>send-Auth</Vorgang>"
	"<HerstellerID>12345</HerstellerID><DatenLieferant>Beispiel GmbH</DatenLieferant></TransferHeader>"
	'<DatenTeil><Nutzdatenblock><NutzdatenHeader version="11"><NutzdatenTicket>1</NutzdatenTicket>'
	'<Empfaenger id="F">9198</Empfaenger></NutzdatenHeader><Nutzdaten>{marker}<Ort>München</Ort></Nutzdaten>'
	"</Nutzdatenblock></DatenTeil></Elster>"
)
DATENTEIL = (
	"<DatenTeil><Nutzdatenblock><Nutzdaten><Kz83>95.00</Kz83></Nutzdaten></Nutzdatenblock></DatenTeil>"
)
CONTAINER = b"\x30\x82\x00\x10fake\x00pkcs12\x00with\x00zero bytes"
PIN = b"123456"


def delivery(marker: str = "") -> str:
	return DELIVERY.format(marker=marker)


class StubTestCase(TestCase):
	"""Runs against a copy of the stub laid out like an ERiC runtime, initialised for each test."""

	initialise = True

	@classmethod
	def setUpClass(cls):
		cls.directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-test-"))
		cls.addClassCleanup(shutil.rmtree, cls.directory)
		cls.lib_dir = stub.install(cls.directory)
		cls.log_dir = cls.directory / "log"
		cls.log_dir.mkdir()
		cls.eric = EricLibrary(cls.lib_dir / api.LIBRARY)
		cls.stub = stub.Controls(cls.lib_dir)

	def setUp(self):
		self.stub.reset()
		buffers = self.stub.live_buffers
		self.addCleanup(lambda: self.assertEqual(self.stub.live_buffers, buffers, "a return buffer leaked"))
		if self.initialise:
			self.eric.initialise(self.lib_dir, self.log_dir)
			self.addCleanup(self.stub.reset)


class DeclarationTest(TestCase):
	def test_flags_are_the_documented_bits(self):
		self.assertEqual((VALIDIERE, SENDE, DRUCKE, PRUEFE_HINWEISE), (2, 4, 32, 128))

	def test_print_parameters_follow_version_4(self):
		self.assertEqual(api.PRINT_PARAMETERS_VERSION, 4)
		self.assertEqual(
			[(name, kind) for name, kind in PrintParameters._fields_],
			[
				("version", ctypes.c_uint32),
				("vorschau", ctypes.c_uint32),
				("duplexDruck", ctypes.c_uint32),
				("pdfName", ctypes.c_char_p),
				("fussText", ctypes.c_char_p),
				("pdfCallback", api.PdfCallback),
				("pdfCallbackBenutzerdaten", ctypes.c_void_p),
			],
		)

	def test_encryption_parameters_follow_version_3(self):
		self.assertEqual(api.ENCRYPTION_PARAMETERS_VERSION, 3)
		self.assertEqual(
			[(name, kind) for name, kind in EncryptionParameters._fields_],
			[("version", ctypes.c_uint32), ("zertifikatHandle", ctypes.c_uint32), ("pin", ctypes.c_char_p)],
		)

	def test_error_names_code_and_text(self):
		error = EricError(610201106, "Falsche PIN.")
		self.assertEqual(
			(error.code, error.text, str(error)), (610201106, "Falsche PIN.", "610201106: Falsche PIN.")
		)


class PrototypeTest(StubTestCase):
	initialise = False

	def test_every_function_has_its_documented_signature(self):
		library = ctypes.CDLL(str(self.lib_dir / api.LIBRARY))
		for name, (restype, argtypes) in api.PROTOTYPES.items():
			with self.subTest(function=name):
				function = getattr(self.eric._library, name)
				self.assertIs(function.restype, restype)
				self.assertEqual(tuple(function.argtypes), argtypes)
				self.assertTrue(hasattr(library, name))

	def test_process_takes_seven_parameters_without_a_transfer_handle(self):
		self.assertEqual(len(api.PROTOTYPES["EricBearbeiteVorgang"][1]), 7)

	def test_buffer_content_is_read_as_a_pointer_with_its_length(self):
		self.assertIs(api.PROTOTYPES["EricRueckgabepufferInhalt"][0], ctypes.c_void_p)
		self.assertIs(api.PROTOTYPES["EricRueckgabepufferLaenge"][0], ctypes.c_uint32)


class LifecycleTest(StubTestCase):
	initialise = False

	def test_initialises_with_the_plugin_and_log_directories(self):
		self.eric.initialise(self.lib_dir, self.log_dir)
		self.assertTrue(self.stub.initialised)
		self.assertEqual(self.stub.recorded("plugin_path"), str(self.lib_dir))
		self.assertEqual(self.stub.recorded("log_path"), str(self.log_dir))
		self.assertTrue((self.log_dir / "eric.log").is_file())
		self.eric.finish()
		self.assertFalse(self.stub.initialised)
		self.assertEqual(self.stub.recorded("finished"), "1")

	def test_a_second_initialisation_is_an_error_with_its_text(self):
		self.eric.initialise(self.lib_dir, self.log_dir)
		with self.assertRaises(EricError) as raised:
			self.eric.initialise(self.lib_dir, self.log_dir)
		self.assertEqual(
			(raised.exception.code, raised.exception.text), (610001082, "Mehrfache Initialisierung.")
		)
		self.eric.finish()


class SettingTest(StubTestCase):
	def test_sets_a_setting(self):
		self.eric.set_setting("transfer.response_timeout", "60")
		self.assertEqual(self.stub.recorded("setting:transfer.response_timeout"), "60")

	def test_an_unknown_setting_is_an_error_even_without_a_text_from_eric(self):
		with self.assertRaises(EricError) as raised:
			self.eric.set_setting("transfer.unbekannt", "1")
		self.assertEqual(raised.exception.code, 610001860)
		self.assertEqual(raised.exception.text, "ERiC hat keinen Text zum Fehlercode 610001860.")


class TextTest(StubTestCase):
	def test_error_texts_are_utf8(self):
		self.assertEqual(
			self.eric.error_text(610001002),
			"Fehler während der Plausibilitätsprüfung, Datensatz nicht plausibel.",
		)

	def test_version_lists_the_libraries(self):
		self.assertIn("<Name>libericapi.so</Name>", self.eric.version())

	def test_a_buffer_eric_cannot_create_is_an_error(self):
		self.stub.fail_buffer()
		with self.assertRaises(EricError) as raised:
			self.eric.version()
		self.assertEqual(raised.exception.code, 610001013)


class TransferHeaderTest(StubTestCase):
	def test_passes_the_header_fields_and_returns_the_delivery(self):
		xml = self.eric.create_transfer_header(
			DATENTEIL,
			verfahren="ElsterAnmeldung",
			datenart="UStVA",
			vorgang="send-Auth",
			testmerker="700000004",
			hersteller_id="12345",
			datenlieferant="Müller & Söhne GmbH",
		)
		self.assertEqual(self.stub.recorded("th_input"), DATENTEIL)
		self.assertEqual(self.stub.recorded("th_vorgang"), "send-Auth")
		self.assertEqual(self.stub.recorded("th_testmerker"), "700000004")
		self.assertEqual(self.stub.recorded("th_hersteller_id"), "12345")
		self.assertEqual(self.stub.recorded("th_datenlieferant"), "Müller & Söhne GmbH")
		self.assertEqual(self.stub.recorded("th_version_client"), "<NULL>")
		self.assertEqual(self.stub.recorded("th_public_key"), "<NULL>")
		self.assertTrue(xml.startswith('<?xml version="1.0" encoding="UTF-8"?><Elster xmlns='))
		self.assertIn("<DatenLieferant>Müller &amp; Söhne GmbH</DatenLieferant>", xml)
		self.assertIn(DATENTEIL, xml)

	def test_a_real_case_passes_no_testmerker(self):
		self.eric.create_transfer_header(
			DATENTEIL,
			verfahren="ElsterAnmeldung",
			datenart="UStVA",
			vorgang="send-Auth",
			testmerker=None,
			hersteller_id="12345",
			datenlieferant="Beispiel GmbH",
		)
		self.assertEqual(self.stub.recorded("th_testmerker"), "<NULL>")

	def test_a_namespace_on_the_datenteil_is_a_parse_error(self):
		with self.assertRaises(EricError) as raised:
			self.eric.create_transfer_header(
				DATENTEIL.replace("<DatenTeil>", '<DatenTeil xmlns="urn:x">'),
				verfahren="ElsterAnmeldung",
				datenart="UStVA",
				vorgang="send-Auth",
				testmerker=None,
				hersteller_id="12345",
				datenlieferant="Beispiel GmbH",
			)
		self.assertEqual(raised.exception.code, 610301006)


class CertificateTest(StubTestCase):
	def test_opens_the_whole_container_from_memory_and_closes_it(self):
		handle = self.eric.open_certificate_from_bytes(CONTAINER, PIN)
		self.assertEqual(handle, 4711)
		self.assertEqual(self.stub.recorded("container_size"), str(len(CONTAINER)))
		self.assertEqual(self.stub.recorded("container_sum"), str(sum(CONTAINER)))
		self.assertEqual(self.stub.recorded("open_password"), PIN.decode())
		self.assertEqual(self.stub.open_certificates, 1)
		self.eric.close_certificate(handle)
		self.assertEqual(self.stub.open_certificates, 0)
		self.assertEqual(self.stub.recorded("closed_handle"), "4711")

	def test_a_wrong_pin_is_an_error(self):
		with self.assertRaises(EricError) as raised:
			self.eric.open_certificate_from_bytes(CONTAINER, stub.WRONG_PIN.encode())
		self.assertEqual(raised.exception.code, 610201106)
		self.assertEqual(
			raised.exception.text, "Es wurde ein falsches Passwort bzw. eine falsche PIN angegeben."
		)

	def test_a_container_of_another_format_is_an_error(self):
		with self.assertRaises(EricError) as raised:
			self.eric.open_certificate_from_bytes(b"PK\x03\x04", PIN)
		self.assertEqual(raised.exception.code, 610201203)

	def test_closing_an_unknown_handle_is_an_error(self):
		with self.assertRaises(EricError) as raised:
			self.eric.close_certificate(1)
		self.assertEqual(raised.exception.code, 610201101)


class ProcessTest(StubTestCase):
	def setUp(self):
		super().setUp()
		self.pdf_path = self.directory / "protocol.pdf"

	def validate(self, marker: str = "") -> api.ProcessResult:
		return self.eric.process(
			delivery(marker),
			"UStVA_2026",
			PRUEFE_HINWEISE | VALIDIERE | DRUCKE,
			preview=True,
			pdf_path=self.pdf_path,
		)

	def send(self, marker: str = "", flags: int = VALIDIERE | SENDE | DRUCKE) -> api.ProcessResult:
		handle = self.eric.open_certificate_from_bytes(CONTAINER, PIN)
		self.addCleanup(self.eric.close_certificate, handle)
		return self.eric.process(
			delivery(marker), "UStVA_2026", flags, pdf_path=self.pdf_path, certificate=handle, pin=PIN
		)

	def test_validates_with_hints_and_a_preview_through_the_print_parameters(self):
		result = self.validate()
		self.assertEqual(result.code, 0)
		self.assertIn("<Erfolg/>", result.return_xml)
		self.assertEqual(result.server_response_xml, "")
		self.assertEqual(self.stub.recorded("datenpuffer"), delivery())
		self.assertEqual(self.stub.recorded("datenart_version"), "UStVA_2026")
		self.assertEqual(self.stub.recorded("flags"), "162")
		self.assertEqual(self.stub.recorded("print_version"), "4")
		self.assertEqual(self.stub.recorded("vorschau"), "1")
		self.assertEqual(self.stub.recorded("duplex"), "0")
		self.assertEqual(self.stub.recorded("pdf_name"), str(self.pdf_path))
		self.assertEqual(self.stub.recorded("fuss_text"), "<NULL>")
		self.assertEqual(self.stub.recorded("pdf_callback_set"), "1")
		self.assertEqual(self.stub.recorded("crypto_version"), "-1")

	def test_receives_the_pdf_through_the_callback_with_all_its_bytes(self):
		(pdf,) = self.validate().pdfs
		self.assertEqual(pdf.name, "1")
		self.assertEqual(len(pdf.data), self.stub.pdf_size)
		self.assertTrue(pdf.data.startswith(b"%PDF-1.4\n") and pdf.data.endswith(b"%%EOF\n"))
		self.assertIn(b"\x00", pdf.data)
		self.assertEqual(self.stub.recorded("pdf_callback_result"), "0")
		self.assertFalse(self.pdf_path.exists())

	def test_sends_with_the_encryption_parameters(self):
		result = self.send()
		self.assertEqual(result.code, 0)
		self.assertEqual(self.stub.recorded("flags"), "38")
		self.assertEqual(self.stub.recorded("vorschau"), "0")
		self.assertEqual(self.stub.recorded("crypto_version"), "3")
		self.assertEqual(self.stub.recorded("certificate_handle"), "4711")
		self.assertEqual(self.stub.recorded("pin"), PIN.decode())
		self.assertIn(
			"<TransferTicket>et0stub0accepted0000000000000001</TransferTicket>", result.server_response_xml
		)
		self.assertEqual(result.pdfs, (Pdf("1", result.pdfs[0].data),))

	def test_sends_without_print_parameters_when_not_printing(self):
		self.assertEqual(self.send(flags=VALIDIERE | SENDE).code, 0)
		self.assertEqual(self.stub.recorded("print_version"), "-1")

	def test_returns_the_code_and_buffer_of_rule_errors_and_hints(self):
		errors = self.validate("STUB-PRUEF-FEHLER")
		self.assertEqual(errors.code, api.GLOBAL_PRUEF_FEHLER)
		self.assertIn("<FachlicheFehlerId>110085064</FachlicheFehlerId>", errors.return_xml)
		hints = self.validate("STUB-HINWEIS")
		self.assertEqual(hints.code, api.GLOBAL_HINWEISE)
		self.assertIn("Bitte prüfen Sie die Kennzahl 26.", hints.return_xml)

	def test_returns_the_code_of_an_invalid_combination(self):
		result = self.eric.process(
			delivery(), "UStVA_2026", VALIDIERE | SENDE | DRUCKE, pdf_path=self.pdf_path
		)
		self.assertEqual(result.code, 610001206)

	def test_returns_the_server_answer_of_a_rejection(self):
		result = self.send("STUB-THEADER")
		self.assertEqual(result.code, api.TRANSFER_ERR_XML_THEADER)
		self.assertIn("<Code>301100005</Code>", result.server_response_xml)


class ServerAnswerTest(StubTestCase):
	def answer(self, marker: str) -> str:
		handle = self.eric.open_certificate_from_bytes(CONTAINER, PIN)
		self.addCleanup(self.eric.close_certificate, handle)
		return self.eric.process(
			delivery(marker), "UStVA_2026", VALIDIERE | SENDE, certificate=handle, pin=PIN
		).server_response_xml

	def test_reads_ticket_and_code_of_the_transfer_header(self):
		answer = self.eric.server_answer(self.answer("STUB-THEADER"))
		self.assertEqual(answer.transferticket, "et0stub0rejected0000000000000002")
		self.assertEqual(answer.code, "301100005")
		self.assertEqual(answer.text, "Stub: Die Daten wurden nicht angenommen.")
		self.assertNotIn("<Fehler>", answer.nutzdaten_errors_xml)

	def test_reads_the_errors_of_the_nutzdaten_headers(self):
		answer = self.eric.server_answer(self.answer("STUB-NHEADER"))
		self.assertEqual(answer.code, "0")
		self.assertIn("<Code>200100007</Code>", answer.nutzdaten_errors_xml)

	def test_an_answer_that_is_no_elster_xml_is_an_error(self):
		with self.assertRaises(EricError) as raised:
			self.eric.server_answer("keine Antwort")
		self.assertEqual(raised.exception.code, 610301006)


class CheckXmlTest(StubTestCase):
	def test_accepts_a_valid_delivery(self):
		self.eric.check_xml(delivery(), "UStVA_2026")
		self.assertEqual(self.stub.recorded("check_xml"), delivery())

	def test_a_schema_error_carries_the_text_of_the_buffer(self):
		with self.assertRaises(EricError) as raised:
			self.eric.check_xml(delivery("STUB-SCHEMA"), "UStVA_2026")
		self.assertEqual(raised.exception.code, 610301200)
		self.assertEqual(raised.exception.text, "Element 'Kz83': Der Wert 'abc' ist kein gültiger Betrag.")

	def test_other_errors_carry_the_error_text(self):
		with self.assertRaises(EricError) as raised:
			self.eric.check_xml(delivery(), "ESt_2026")
		self.assertEqual(raised.exception.code, 610001042)
		self.assertIn("Datenartversion ist unbekannt", raised.exception.text)
