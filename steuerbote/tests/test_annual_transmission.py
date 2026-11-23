"""Prüfen, Testsenden and Senden of an annual document through Transmittable, on the test document of
steuerbote/tests/annual_document.py: an Erklärung in the Datenart of its year with its Vorsatz and the copyright
notice of the ERiC Settings, the E-Bilanz with the DatenLieferant of its NutzdatenHeader, the Steuernummer of the
Annual Filing Settings, and the printout ERiC makes of each, the Freizeichnungsdokument or the Übertragungsprotokoll.

Without a runtime the simulation answers; FakeEric of steuerbote/tests/transmitting.py stands in for an installed
ERiC."""

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.eric.result import TESTMERKER, Outcome
from steuerbote.tests import annual_document
from steuerbote.tests.annual_document import COMPANY, DOCTYPE, LINE_DOCTYPE, LINES, source
from steuerbote.tests.transmitting import TICKET, TRANSMISSION, FakeEric, Transmitting

COPYRIGHT = "Steuerbote Test GmbH, München"
SETTINGS = "Annual Filing Settings"
REASON = "Gutschrift vom 30. Dezember 2026, gebucht im Januar"


class AnnualTransmissionTestCase(Transmitting, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		annual_document.install()
		annual_document.make_company_with_settings()
		cls.elster_tax_number = frappe.db.get_value("VAT Return Settings", COMPANY, "elster_tax_number")

	def setUp(self):
		super().setUp()
		self.eric_settings(copyright=COPYRIGHT)
		self.enterContext(annual_document.use_controller())
		self.addCleanup(annual_document.discard_all)

	def calculated(self, **fields):
		doc = frappe.get_doc(
			{"doctype": DOCTYPE, "company": COMPANY, "year": 2026, "source": source(*LINES), **fields}
		).insert()
		doc.calculate()
		doc.reload()
		return doc

	def file_name(self, transmission) -> str:
		return self.attachment(transmission, "protocol_pdf").file_name


class TestErklaerung(AnnualTransmissionTestCase):
	def test_pruefen_goes_with_the_datenart_of_the_year_the_vorsatz_and_the_finanzamt_of_the_steuernummer(
		self,
	):
		doc = self.calculated()
		transmission, _, run = self.transmitted(doc, "validate")
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.simulated), ("Erfolgreich", "valid", 1)
		)
		self.assertNotIn("error", [row.severity for row in transmission.messages])
		self.assertIn("SIM-001", self.codes(transmission))
		_, nutzdaten, header, *_ = run.call_args.args
		self.assertEqual(
			(header.datenart_version, header.empfaenger, header.nutzdaten_datenlieferant),
			("KSt_30_2026", self.elster_tax_number[:4], None),
		)
		for element in (
			"<Unterfallart>30</Unterfallart>",
			f"<StNr>{self.elster_tax_number}</StNr>",
			"<Zeitraum>2026</Zeitraum>",
			f"<AbsName>{COMPANY}</AbsName>",
			"<AbsStr>Musterweg 12a</AbsStr>",
			"<AbsPlz>80331</AbsPlz>",
			"<AbsOrt>München</AbsOrt>",
			f"<Copyright>{COPYRIGHT}</Copyright>",
			"<Bescheid>2</Bescheid>",
		):
			with self.subTest(element=element):
				self.assertIn(element, nutzdaten)

	def test_testsenden_keeps_the_freizeichnungsdokument(self):
		doc = self.calculated()
		self.assertEqual(doc.elster_state()["printout"], "Freizeichnungsdokument")
		transmission, _, _ = self.transmitted(doc, "test_send")
		self.assertEqual((transmission.status, transmission.testmerker), ("Erfolgreich", TESTMERKER))
		self.assertTrue(self.file_name(transmission).endswith("-test_send-freizeichnungsdokument.pdf"))
		self.assertIn(b"Freizeichnungsdokument", self.attachment(transmission, "protocol_pdf").get_content())
		self.assertEqual(doc.docstatus, 0)

	def test_senden_files_it_with_its_transferticket(self):
		self.use_runtime(copyright=COPYRIGHT)
		doc = self.calculated()
		fake = FakeEric()
		transmission, _, _ = self.transmitted(doc, "send", fake, self.stash(doc))
		self.assertEqual((transmission.status, transmission.transferticket), ("Erfolgreich", TICKET))
		self.assertTrue(self.file_name(transmission).endswith("-send-freizeichnungsdokument.pdf"))
		self.assertEqual(
			(doc.docstatus, doc.status, doc.filed_via, doc.transferticket, doc.filed_by),
			(1, "Abgegeben", "eric", TICKET, frappe.session.user),
		)
		(sent,) = fake.runs
		self.assertEqual(sent["header"].hersteller_id, "12345")
		self.assertIn(f"<Copyright>{COPYRIGHT}</Copyright>", sent["nutzdaten"])

	def test_outside_the_simulation_an_erklaerung_needs_the_copyright_notice(self):
		self.use_runtime(copyright="")
		doc = self.calculated()
		with self.assertRaisesRegex(frappe.ValidationError, "Enter the Copyright Notice"):
			self.transmit(doc, "validate")

	def test_takes_the_steuernummer_of_the_annual_filing_settings_where_they_have_one(self):
		self.addCleanup(
			frappe.db.set_value,
			SETTINGS,
			COMPANY,
			{"income_tax_number": None, "elster_income_tax_number": None},
		)
		settings = frappe.get_doc(SETTINGS, COMPANY)
		settings.income_tax_number = "123/456/78902"
		settings.save()
		own = frappe.db.get_value(SETTINGS, COMPANY, "elster_income_tax_number")
		self.assertNotEqual(own, self.elster_tax_number)
		doc = self.calculated()
		self.assertEqual(doc.elster_tax_number(), own)
		_, _, run = self.transmitted(doc, "validate")
		_, nutzdaten, header, *_ = run.call_args.args
		self.assertEqual(header.empfaenger, own[:4])
		self.assertIn(f"<StNr>{own}</StNr>", nutzdaten)

	def test_waits_for_berechnen_and_for_the_amounts_as_stored(self):
		doc = frappe.get_doc(
			{"doctype": DOCTYPE, "company": COMPANY, "year": 2026, "source": source(*LINES)}
		).insert()
		with self.assertRaisesRegex(frappe.ValidationError, "before transmitting it"):
			self.transmit(doc, "validate")
		doc = frappe.get_doc(DOCTYPE, doc.name)
		doc.calculate()
		frappe.db.set_value(LINE_DOCTYPE, doc.lines[0].name, {"correction": 50, "correction_reason": REASON})
		with self.assertRaisesRegex(frappe.ValidationError, "do not agree with its lines as stored"):
			self.transmit(frappe.get_doc(DOCTYPE, doc.name), "validate")

	def test_after_a_send_with_an_unknown_outcome_only_the_remarks_change_and_the_note_of_its_filing_files_it(
		self,
	):
		self.use_runtime(copyright=COPYRIGHT)
		doc = self.calculated()
		transmission, _, _ = self.transmitted(doc, "send", FakeEric(outcome=Outcome.UNKNOWN), self.stash(doc))
		self.assertEqual((transmission.status, doc.docstatus), ("Unbekannt", 0))
		self.assertEqual(doc.elster_state()["locked"]["status"], "Unbekannt")
		doc.lines[0].correction = 90
		doc.lines[0].correction_reason = REASON
		with self.assertRaisesRegex(frappe.ValidationError, "is unknown"):
			doc.save()
		doc.reload()
		doc.remarks = "In Mein ELSTER nachgesehen."
		doc.save()
		doc.mark_filed_outside("mein_elster")
		doc.reload()
		self.assertEqual((doc.docstatus, doc.status, doc.filed_via), (1, "Abgegeben", "mein_elster"))

	def test_senden_waits_for_a_send_with_an_unknown_outcome_and_refuses_one_elster_accepted(self):
		"""The Finanzamt has a document whose Senden ELSTER accepted, or may have it when the outcome is unknown."""
		self.use_runtime(copyright=COPYRIGHT)
		doc = self.calculated()
		for status, message in (
			("Unbekannt", "is unknown. Check in Mein ELSTER whether it arrived"),
			("Erfolgreich", f"was transmitted already with Transferticket {TICKET}"),
		):
			with self.subTest(status=status):
				frappe.db.delete(TRANSMISSION, {"document_type": DOCTYPE, "document": doc.name})
				doc.new_transmission("send", simulated=False, status=status, transferticket=TICKET)
				token = self.stash(doc)
				with self.assertRaisesRegex(frappe.ValidationError, message):
					self.transmit(frappe.get_doc(DOCTYPE, doc.name), "send", token)

	def test_a_filed_document_is_not_transmitted_again(self):
		self.use_runtime(copyright=COPYRIGHT)
		doc = self.calculated()
		self.transmitted(doc, "send", FakeEric(), self.stash(doc))
		with self.assertRaisesRegex(frappe.ValidationError, "is no draft and is not transmitted"):
			self.transmit(frappe.get_doc(DOCTYPE, doc.name), "validate")


class TestEBilanz(AnnualTransmissionTestCase):
	def test_testsenden_names_the_datenlieferant_and_keeps_the_uebertragungsprotokoll(self):
		doc = self.calculated(kind="Bilanz")
		self.assertEqual(doc.elster_state()["printout"], "Übertragungsprotokoll")
		transmission, _, run = self.transmitted(doc, "test_send")
		self.assertEqual(transmission.status, "Erfolgreich")
		_, nutzdaten, header, *_ = run.call_args.args
		self.assertEqual(
			(header.datenart_version, header.empfaenger, header.nutzdaten_datenlieferant),
			(
				"Bilanz_6.9",
				self.elster_tax_number[:4],
				f"{COMPANY}; Musterweg; 12; a; Hinterhaus; 80331; München; Deutschland; 089 1234567; "
				"buchhaltung@example.org",
			),
		)
		self.assertIn("<stichtag>20261231</stichtag>", nutzdaten)
		self.assertTrue(self.file_name(transmission).endswith("-test_send-protokoll.pdf"))
		self.assertIn(b"bertragungsprotokoll", self.attachment(transmission, "protocol_pdf").get_content())

	def test_pruefen_prints_nothing(self):
		"""ERiC prints no copy of the E-Bilanz, and Prüfen runs without a preview (EBV-8)."""
		doc = self.calculated(kind="Bilanz")
		transmission, _, _ = self.transmitted(doc, "validate")
		self.assertEqual((transmission.status, transmission.protocol_pdf), ("Erfolgreich", None))

	def test_a_semicolon_would_break_the_ten_parts_of_the_datenlieferant(self):
		self.addCleanup(frappe.db.set_value, SETTINGS, COMPANY, "address_supplement", "Hinterhaus")
		frappe.db.set_value(SETTINGS, COMPANY, "address_supplement", "Hof; links")
		doc = self.calculated(kind="Bilanz")
		with self.assertRaisesRegex(frappe.ValidationError, "takes no semicolon"):
			doc.nutzdaten_datenlieferant()
