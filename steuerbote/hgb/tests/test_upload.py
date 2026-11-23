"""The upload of the Jahresabschluss to the Unternehmensregister, step by step, as data with its sources."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.hgb.disclosure import DisclosureError, Mode, filing_fees
from steuerbote.hgb.schemes import balance_sheet_scheme
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.upload import (
	FILES_PER_ORDER,
	IDENTIFICATION,
	READ_ON,
	RECORDS,
	STEPS,
	TEST_PLATFORM_ADDRESS,
	Identification,
	StepKey,
	costs,
	identification,
	steps,
	web_form,
)

KLEINST = SizeClass.KLEINST
KLEIN = SizeClass.KLEIN


def keys(found) -> tuple[StepKey, ...]:
	return tuple(step.key for step in found)


class StepsTest(TestCase):
	"""Steuerbote writes the file and a person uploads it: the register has no public interface for it."""

	def test_an_upload_goes_from_the_registration_to_the_beleg(self):
		"""„In 4 Schritten zur Veröffentlichung Ihres Jahresabschlusses“: register once, identify, transmit, manage
		the orders under „Meine Daten“ (Publikations-Plattform, „So geht's - Jahresabschluss Veröffentlichung“)."""
		self.assertEqual(
			keys(steps(KLEIN, Mode.OFFENLEGUNG, first_upload=False)),
			(
				StepKey.REGISTER,
				StepKey.IDENTIFY,
				StepKey.ORDER,
				StepKey.UPLOAD,
				StepKey.CONFIRMATION,
				StepKey.RECEIPT,
			),
		)

	def test_the_testplattform_comes_before_the_first_real_upload(self):
		"""„Hier können Sie die Kompatibilität Ihrer XBRL-Dateien unabhängig von der regulären Auftragsübermittlung
		überprüfen.“ (Publikations-Plattform, „Arbeitshilfen - XBRL-Programm“)"""
		first = steps(KLEIN, Mode.OFFENLEGUNG, first_upload=True)
		self.assertIs(first[0].key, StepKey.TEST_PLATFORM)
		self.assertEqual(keys(first[1:]), keys(steps(KLEIN, Mode.OFFENLEGUNG, first_upload=False)))

	def test_the_testplattform_is_asked_for_by_mail(self):
		"""„Bei Interesse wenden Sie sich bitte an den Verlag unter der E-Mail-Adresse
		testplattform@rt.bundesanzeiger.de. Sie erhalten dann die Zugangsdaten zur Testplattform.“"""
		self.assertEqual(TEST_PLATFORM_ADDRESS, "testplattform@rt.bundesanzeiger.de")
		(step,) = (step for step in STEPS if step.key is StepKey.TEST_PLATFORM)
		self.assertIn(TEST_PLATFORM_ADDRESS, step.text)

	def test_the_registration_names_the_register_of_the_company(self):
		"""For an upload to the register the registration takes „Firma oder Name des Unternehmens, Registergericht,
		Registerart, Registernummer“ (§ 3 Abs. 2 URV), once: „Eine einmalige Registrierung genügt.“"""
		(step,) = (step for step in STEPS if step.key is StepKey.REGISTER)
		for word in ("einmal", "Registergericht", "Registerart", "Registernummer"):
			with self.subTest(word=word):
				self.assertIn(word, step.text)
		self.assertIn("§ 3 Abs. 2 URV", step.text)

	def test_each_person_who_uploads_identifies_once_before(self):
		"""„Identifizieren lassen muss sich jede natürliche Person, die ... eine Datenübermittlung ... tatsächlich
		vornimmt.“ „Die Identifizierung muss jedoch vor dem Beginn der Übermittlung(en) abgeschlossen sein.“ „Die
		Identifikation muss grundsätzlich nur einmal je berechtigter Person erfolgen.“ (Publikations-Plattform,
		„Registrieren / Identifizieren“; § 3a Abs. 1 URV)"""
		found = keys(steps(KLEINST, Mode.HINTERLEGUNG, first_upload=False))
		self.assertLess(found.index(StepKey.IDENTIFY), found.index(StepKey.UPLOAD))
		(step,) = (step for step in STEPS if step.key is StepKey.IDENTIFY)
		self.assertIn("jede Person", step.text)
		self.assertIn("einmal", step.text)
		self.assertIn("Namensänderung", step.text)

	def test_the_identification_step_names_each_method_with_its_fee(self):
		(step,) = (step for step in STEPS if step.key is StepKey.IDENTIFY)
		for text in ("12,00 €", "22,00 €", "7,60 €"):
			with self.subTest(fee=text):
				self.assertIn(text, step.text)

	def test_one_file_per_order(self):
		"""„Sie können nur eine Datei pro Auftrag übermitteln.“ (Publikations-Plattform, Fragen und Antworten,
		„Aufträge an das Unternehmensregister“)"""
		self.assertEqual(FILES_PER_ORDER, 1)
		(step,) = (step for step in STEPS if step.key is StepKey.UPLOAD)
		self.assertIn("eine Datei je Auftrag", step.text)

	def test_xml_is_the_format_of_the_law(self):
		"""Daten „im strukturierten Format Extensible Markup Language (XML)“ (§ 11 Abs. 2 Satz 1 Nr. 4 URV); another
		format costs „neben der Gebühr ein Konvertierungsentgelt“ (Publikations-Plattform)."""
		(step,) = (step for step in STEPS if step.key is StepKey.UPLOAD)
		self.assertIn("§ 11 Abs. 2 Satz 1 Nr. 4 URV", step.text)
		self.assertIn("Konvertierungsentgelt", step.text)

	def test_a_kleinst_that_deposits_ticks_the_box_of_the_hinterlegung(self):
		"""„Mit dem Setzen des Hakens kommen Sie Ihrer gesetzlichen Mitteilungspflicht ... nach.“ (Publikations-
		Plattform, „Übermittlung von Jahresabschlüssen“), the Mitteilung of § 326 Abs. 2 Satz 2 HGB."""
		deposit = keys(steps(KLEINST, Mode.HINTERLEGUNG, first_upload=False))
		self.assertLess(deposit.index(StepKey.ORDER), deposit.index(StepKey.DEPOSIT))
		self.assertLess(deposit.index(StepKey.DEPOSIT), deposit.index(StepKey.UPLOAD))
		(step,) = (step for step in STEPS if step.key is StepKey.DEPOSIT)
		self.assertIn("§ 326 Abs. 2 Satz 2 HGB", step.text)

	def test_no_box_for_a_kleinst_that_publishes_or_for_klein(self):
		self.assertNotIn(StepKey.DEPOSIT, keys(steps(KLEINST, Mode.OFFENLEGUNG, first_upload=False)))
		self.assertNotIn(StepKey.DEPOSIT, keys(steps(KLEIN, Mode.OFFENLEGUNG, first_upload=True)))

	def test_the_day_of_the_transmission_keeps_the_deadline(self):
		"""„Für die Wahrung der Fristen ... ist der Zeitpunkt der Übermittlung der Unterlagen maßgebend.“ (§ 325
		Abs. 4 Satz 2 HGB)"""
		(step,) = (step for step in STEPS if step.key is StepKey.CONFIRMATION)
		self.assertIn("§ 325 Abs. 4 Satz 2 HGB", step.text)
		self.assertIn("Auftragsbestätigung", step.text)

	def test_the_beleg_follows_the_einstellung(self):
		"""„Nach erfolgter Einstellung in das Unternehmensregister steht Ihnen ein PDF-Beleg im Menü „Meine Daten“
		unter "Aufträge & Abrufe" zur Verfügung.“"""
		(step,) = (step for step in STEPS if step.key is StepKey.RECEIPT)
		self.assertIn("Beleg", step.text)
		self.assertIn("Aufträge & Abrufe", step.text)

	def test_only_the_classes_steuerbote_prepares(self):
		for size_class in (SizeClass.MITTELGROSS, SizeClass.GROSS):
			with self.subTest(size_class=size_class), self.assertRaises(DisclosureError):
				steps(size_class, Mode.OFFENLEGUNG, first_upload=False)

	def test_only_a_kleinst_deposits(self):
		with self.assertRaises(DisclosureError):
			steps(KLEIN, Mode.HINTERLEGUNG, first_upload=False)

	def test_every_step_has_a_title_a_text_and_a_source(self):
		for step in STEPS:
			with self.subTest(step=step.key):
				self.assertTrue(step.title.strip())
				self.assertTrue(step.text.strip())
				self.assertTrue(step.sources)
				for source in step.sources:
					self.assertTrue(source.title.strip())
					self.assertTrue(source.url.startswith("https://"))

	def test_each_step_once_in_the_order_of_an_upload(self):
		self.assertEqual(keys(STEPS), tuple(StepKey))

	def test_the_sources_were_read_on_23_november_2026(self):
		self.assertEqual(READ_ON, date(2026, 11, 23))


class IdentificationTest(TestCase):
	"""Nr. 1441 KV JVKostG: „Verfahren zur Registrierung nach § 3 Abs. 2, § 3a URV“, by the method of the
	Identitätsprüfung."""

	def test_with_the_eid_it_costs_12_euros(self):
		method = identification(Identification.EID)
		self.assertEqual(method.fee, Decimal("12.00"))
		self.assertEqual(
			method.reference, "Nr. 1441 Buchst. a KV JVKostG; § 3a Abs. 1 Satz 3 Nr. 1 und 2 URV"
		)

	def test_by_video_22_euros(self):
		method = identification(Identification.VIDEO)
		self.assertEqual(method.fee, Decimal("22.00"))
		self.assertEqual(method.reference, "Nr. 1441 Buchst. b KV JVKostG; § 3a Abs. 1 Satz 3 Nr. 3 URV")

	def test_through_the_steuerberaterplattform_7_60_euros(self):
		method = identification(Identification.TAX_ADVISOR_PLATFORM)
		self.assertEqual(method.fee, Decimal("7.60"))
		self.assertEqual(method.reference, "Nr. 1441 Buchst. c KV JVKostG; § 3a Abs. 4 URV")

	def test_each_method_once_with_a_decimal_fee(self):
		self.assertEqual(tuple(method.method for method in IDENTIFICATION), tuple(Identification))
		for method in IDENTIFICATION:
			with self.subTest(method=method.method):
				self.assertIsInstance(method.fee, Decimal)
				self.assertTrue(method.label.strip())


class CostsTest(TestCase):
	"""The register charges the Einstellung by class and a fee a year (Nr. 1410, 1420 and 1421 KV JVKostG)."""

	def test_a_kleinst_pays_18_50_euros_and_3_euros_a_year(self):
		found = costs(KLEINST)
		self.assertEqual((found.filing, found.yearly), (Decimal("18.50"), Decimal("3.00")))
		self.assertEqual(found.total, Decimal("21.50"))
		self.assertIsNone(found.identification)

	def test_klein_pays_25_euros_and_3_euros_a_year(self):
		found = costs(KLEIN)
		self.assertEqual((found.filing, found.yearly), (Decimal("25.00"), Decimal("3.00")))
		self.assertEqual(found.total, Decimal("28.00"))

	def test_the_fees_are_those_of_the_disclosure(self):
		for size_class in (KLEINST, KLEIN):
			with self.subTest(size_class=size_class):
				fees = filing_fees(size_class)
				found = costs(size_class)
				self.assertEqual(
					(found.filing, found.filing_reference, found.yearly, found.yearly_reference),
					(fees.filing, fees.filing_reference, fees.yearly, fees.yearly_reference),
				)

	def test_the_first_upload_adds_the_identification(self):
		found = costs(KLEINST, Identification.EID)
		self.assertEqual(found.identification, identification(Identification.EID))
		self.assertEqual(found.total, Decimal("33.50"))

	def test_no_costs_for_a_class_steuerbote_does_not_prepare(self):
		with self.assertRaises(DisclosureError):
			costs(SizeClass.GROSS)


class RecordsTest(TestCase):
	"""What the Annual Accounts hold after the upload: the order, its confirmation, the Beleg and the day of the
	Einstellung (Publikations-Plattform, Fragen und Antworten, „Aufträge an das Unternehmensregister“)."""

	def test_records_the_order_its_confirmation_the_einstellung_and_the_beleg(self):
		self.assertEqual(
			tuple(record.field for record in RECORDS),
			(
				"transmitted_on",
				"transmitted_by",
				"order_number",
				"confirmation_file",
				"published_on",
				"receipt_file",
				"fees",
			),
		)

	def test_a_berichtigung_names_the_order_number_and_the_day(self):
		"""„Nennen Sie anschließend die Auftragsnummer und das Datum der Veröffentlichung bzw. Hinterlegung, die Sie
		berichtigen möchten. Diese finden Sie auf Ihrem Beleg oder im Menü „Meine Daten“ unter „Aufträge &
		Abrufe“.“ (Publikations-Plattform, „Übermittlung von Jahresabschlüssen“)"""
		(record,) = (record for record in RECORDS if record.field == "order_number")
		self.assertIn("Berichtigung", record.text)

	def test_every_record_has_a_label_a_text_and_a_source(self):
		for record in RECORDS:
			with self.subTest(record=record.field):
				self.assertTrue(record.label.strip())
				self.assertTrue(record.text.strip())
				self.assertTrue(record.source.url.startswith("https://"))


class WebFormTest(TestCase):
	"""„Im Formular müssen Sie nur Ihre Bilanzdaten in die mit den üblichen Bilanzpositionen vorbelegten Felder
	eintragen und in ein zweites Feld den Anhang hineinkopieren.“ (Publikations-Plattform, „So geht's -
	Jahresabschluss Veröffentlichung“) The form needs a login, so its field names are unverified."""

	def test_lists_the_positions_of_the_balance_sheet_of_the_class(self):
		for size_class in (KLEINST, KLEIN):
			with self.subTest(size_class=size_class):
				form = web_form(size_class, 2026)
				visible = balance_sheet_scheme(2026).visible(size_class)
				self.assertEqual(
					tuple((field.concept, field.marker, field.label) for field in form.fields),
					tuple((position.concept, position.marker, position.label) for position in visible),
				)

	def test_klein_pastes_the_anhang_and_a_kleinst_its_angaben_under_the_balance_sheet(self):
		self.assertEqual(web_form(KLEIN, 2026).text_field, "Anhang")
		self.assertEqual(web_form(KLEINST, 2026).text_field, "Angaben unter der Bilanz")

	def test_its_field_names_are_unverified(self):
		form = web_form(KLEIN, 2026)
		self.assertFalse(form.verified)
		self.assertTrue(form.source.url.startswith("https://www.publikations-plattform.de/"))

	def test_only_for_small_companies(self):
		with self.assertRaises(DisclosureError):
			web_form(SizeClass.MITTELGROSS, 2026)
