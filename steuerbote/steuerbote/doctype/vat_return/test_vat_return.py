from datetime import date
from decimal import Decimal
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase
from lxml import etree

from steuerbote.elster.tests import eric_schema
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
	submitted_without_record,
)

# The companies, their accounts and the vouchers are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

# Files monthly through 2026, without Dauerfristverlängerung.
COMPANY = "Steuerbote Test Voranmeldung GmbH"
# Files quarterly until September 2026 and monthly from October, with Dauerfristverlängerung.
SWITCHING_COMPANY = "Steuerbote Test Dauerfrist GmbH"
# Has VAT Return Settings but no VAT Return Mapping.
UNMAPPED_COMPANY = "Steuerbote Test Ohne Zuordnung GmbH"
# Has neither.
BARE_COMPANY = "Steuerbote Test Ohne Einstellungen GmbH"
FILED_IN_MEIN_ELSTER = "In Mein ELSTER abgegeben"

# SKR03 numbers of the month in VerifiedMonthTest of the core, a bank and a receivables account, and a
# watched account.
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"8338": ("Erlöse Drittland nicht steuerbar", "Income"),
	"3123": ("Sonstige Leistungen EU 19 %", "Expense"),
	"1787": ("Umsatzsteuer nach § 13b UStG 19 %", "Liability"),
	"1577": ("Vorsteuer nach § 13b UStG 19 %", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1200": ("Bank", "Asset"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
	"1548": ("Vorsteuer im Folgejahr abziehbar", "Asset"),
}


# The Datenlieferant of COMPANY, invented.
DATENLIEFERANT = {"street": "Hauptstraße 1", "postal_code": "80331", "city": "München"}
IMPORT_DECLARATION = b'<?xml version="1.0" encoding="ISO-8859-15" standalone="no"?>\n'


def money(value) -> Decimal:
	return Decimal(str(value)).quantize(Decimal("0.01"))


def attached_file(url: str, doc):
	"""The File that attaches the file at the url to the return; returns of the same content share the url."""
	return frappe.get_doc(
		"File", {"file_url": url, "attached_to_doctype": "VAT Return", "attached_to_name": doc.name}
	)


def contents(url: str) -> bytes:
	return Path(frappe.get_doc("File", {"file_url": url}).get_full_path()).read_bytes()


def elements(document: bytes) -> list[tuple[str, str]]:
	"""Name and text of each child of Umsatzsteuervoranmeldung in an import file."""
	(anmeldung,) = etree.fromstring(document).iter("{*}Umsatzsteuervoranmeldung")
	return [(etree.QName(child).localname, child.text) for child in anmeldung]


def kennzahlen(document: bytes) -> dict[str, str]:
	return {name: text for name, text in elements(document) if name.startswith("Kz")}


class TestVATReturn(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STVA")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)], **DATENLIEFERANT)
		make_mapping(COMPANY)
		make_company(SWITCHING_COMPANY, "STVD")
		make_settings(
			SWITCHING_COMPANY, [(2026, "quarterly", 1), (2026, "monthly", 10)], [(2026, True, "1200.00")]
		)
		make_mapping(SWITCHING_COMPANY)
		make_company(UNMAPPED_COMPANY, "STVZ")
		make_settings(UNMAPPED_COMPANY, [(2026, "monthly", 1)])
		make_company(BARE_COMPANY, "STVE")

		a = cls.account
		march = "2026-03-10"
		post_journal_entry(COMPANY, march, [(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)])
		post_journal_entry(COMPANY, march, [(a["1400"], 2000, 0), (a["8336"], 0, 2000)])
		post_journal_entry(COMPANY, march, [(a["1400"], 500, 0), (a["8338"], 0, 500)])
		post_journal_entry(
			COMPANY, march, [(a["3123"], 300, 0), (a["1577"], 57, 0), (a["1787"], 0, 57), (a["1200"], 0, 300)]
		)
		post_journal_entry(COMPANY, march, [(a["1576"], 95, 0), (a["1200"], 0, 95)])
		cancelled = post_journal_entry(
			COMPANY, "2026-03-20", [(a["1400"], 119, 0), (a["8400"], 0, 100), (a["1776"], 0, 19)]
		)
		cancelled.cancel()
		post_journal_entry(COMPANY, "2026-03-31", [(a["1776"], 190, 0), (a["1200"], 0, 190)], exclude=True)

	def new_return(self, period: int, company: str = COMPANY, rhythm: str = "monthly", **fields):
		return frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": company,
				"year": 2026,
				"rhythm": rhythm,
				"period_index": period,
				**fields,
			}
		).insert()

	def calculated(self, period: int, **fields):
		doc = self.new_return(period, **fields)
		doc.calculate()
		doc.reload()
		return doc

	def kennzahl(self, doc, number: str):
		return next(row for row in doc.kennzahlen if row.kennzahl == number)

	def roll_back_afterwards(self) -> None:
		"""Undo what the test files or sends, so that its period stays open for the tests after it."""
		frappe.db.savepoint("vat_return_test")
		self.addCleanup(frappe.db.rollback, save_point="vat_return_test")

	def amounts(self, doc) -> dict[str, Decimal]:
		return {row.kennzahl: money(row.final) for row in doc.kennzahlen}

	def test_derives_dates_code_and_deadline_from_the_period(self):
		doc = self.new_return(3)
		self.assertEqual(
			(doc.rhythm, doc.period_code, doc.period_label, doc.status),
			("monthly", "03", "März 2026", "Entwurf"),
		)
		self.assertEqual(
			(str(doc.from_date), str(doc.to_date), str(doc.deadline)),
			("2026-03-01", "2026-03-31", "2026-04-10"),
		)

	def test_calculates_the_verified_month(self):
		doc = self.calculated(3)
		self.assertEqual(
			self.amounts(doc),
			{
				"81": money(1000),
				"46": money(300),
				"47": money(57),
				"21": money(2000),
				"45": money(500),
				"66": money(95),
				"67": money(57),
				"83": money(95),
			},
		)
		self.assertEqual(
			[money(doc.output_tax), money(doc.input_tax), money(doc.other_tax), money(doc.kz83)],
			[money(247), money(152), money(0), money(95)],
		)
		self.assertEqual((doc.ready, doc.status, doc.accounts_without_number), (1, "Bereit", 0))
		self.assertEqual(
			[(row.label, money(row.computed_tax), money(row.booked_tax), row.passed) for row in doc.checks],
			[
				("Umsatzsteuer 19 %", money(190), money(190), 1),
				("Umsatzsteuer nach § 13b UStG 19 %", money(57), money(57), 1),
			],
		)
		self.assertEqual((doc.deviations, doc.unmapped), ([], []))
		row = self.kennzahl(doc, "81")
		self.assertEqual(
			(row.line, row.kind, row.label), (13, "base", "Steuerpflichtige Umsätze zum Steuersatz von 19 %")
		)

	def test_leaves_out_the_cancelled_and_the_excluded_journal_entry(self):
		doc = self.calculated(3)
		self.assertEqual(money(self.kennzahl(doc, "81").reported), money(1000))
		self.assertEqual(money(doc.checks[0].booked_tax), money(190))
		self.assertTrue(doc.checks[0].passed)

	def test_an_override_with_a_reason_is_filed_and_the_sums_follow(self):
		doc = self.calculated(3)
		row = self.kennzahl(doc, "81")
		row.override = 1100
		row.override_reason = "Invoice of 31 March booked in April"
		doc.save()
		doc.reload()
		self.assertEqual(
			(money(row.reported), money(self.kennzahl(doc, "81").final)), (money(1000), money(1100))
		)
		self.assertEqual((money(doc.output_tax), money(doc.kz83)), (money(266), money(114)))
		self.assertEqual(money(self.kennzahl(doc, "83").final), money(114))

	def test_an_override_without_a_reason_is_refused(self):
		doc = self.calculated(3)
		self.kennzahl(doc, "45").override = 600
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_a_new_calculation_keeps_the_overrides(self):
		doc = self.calculated(3)
		row = self.kennzahl(doc, "45")
		row.override = 600
		row.override_reason = "Second invoice to the third country"
		doc.save()
		doc.calculate()
		doc.reload()
		row = self.kennzahl(doc, "45")
		self.assertEqual(
			(money(row.override), row.override_reason), (money(600), "Second invoice to the third country")
		)
		self.assertEqual(money(row.final), money(600))

	def test_submitting_needs_a_calculation(self):
		doc = self.new_return(5)
		with self.assertRaisesRegex(frappe.ValidationError, "Calculate the return before submitting it"):
			doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)

	def test_a_return_that_is_not_ready_needs_remarks(self):
		a = self.account
		entry = post_journal_entry(
			COMPANY, "2026-06-15", [(a["1400"], 1180, 0), (a["8400"], 0, 1000), (a["1776"], 0, 180)]
		)
		doc = self.calculated(6)
		self.assertEqual((doc.ready, doc.status), (0, "Berechnet"))
		self.assertEqual(
			[
				(
					row.check_label,
					row.voucher_type,
					row.voucher_no,
					money(row.computed_tax),
					money(row.booked_tax),
				)
				for row in doc.deviations
			],
			[("Umsatzsteuer 19 %", "Journal Entry", entry.name, money(190), money(180))],
		)
		self.assertEqual(money(doc.deviations[0].difference), money(-10))
		with self.assertRaisesRegex(frappe.ValidationError, "The return is not ready"):
			doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		doc.reload()
		doc.remarks = "The Steuerberatung corrects the invoice in July."
		doc.save()
		doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		self.assertEqual(doc.status, "Abgegeben")

	def test_a_watched_account_with_a_balance_is_listed(self):
		a = self.account
		post_journal_entry(COMPANY, "2026-08-20", [(a["1548"], 50, 0), (a["1200"], 0, 50)])
		doc = self.calculated(8)
		self.assertEqual(
			[(row.account_number, row.account, money(row.debit), money(row.credit)) for row in doc.unmapped],
			[("1548", a["1548"], money(50), money(0))],
		)
		self.assertEqual((doc.ready, doc.status), (0, "Berechnet"))

	def test_a_second_return_for_a_filed_period_must_be_a_correction(self):
		first = self.calculated(4)
		first.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		self.assertEqual(first.status, "Abgegeben")
		with self.assertRaises(frappe.ValidationError):
			self.new_return(4)
		correction = self.calculated(4, is_correction=1)
		correction.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		first.reload()
		self.assertEqual((first.status, correction.status), ("Ersetzt", "Abgegeben"))

	def test_the_status_of_a_filed_return_stays_as_filed(self):
		"""Whether a return counts as filed, for its period and for the base of the Dauerfristverlängerung, follows
		its status: once submitted, only the filing of a corrected return replaces it."""
		self.roll_back_afterwards()
		doc = self.calculated(2)
		doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		doc.reload()
		doc.status = "Ersetzt"
		with self.assertRaises(frappe.UpdateAfterSubmitError):
			doc.save()
		self.assertEqual(frappe.db.get_value("VAT Return", doc.name, "status"), "Abgegeben")

	def test_cancelling_a_correction_restores_the_return_it_replaced(self):
		first = self.calculated(7)
		submitted_without_record(first)
		correction = self.calculated(7, is_correction=1)
		submitted_without_record(correction)
		correction.cancel()
		first.reload()
		self.assertEqual(first.status, "Abgegeben")

	def test_changing_the_period_discards_the_calculation(self):
		doc = self.calculated(3)
		doc.period_index = 9
		doc.save()
		self.assertEqual((doc.status, doc.period_code, doc.kennzahlen, doc.ready), ("Entwurf", "09", [], 0))

	def test_a_number_without_period_is_refused(self):
		for number in (0, 13):
			with self.subTest(number=number), self.assertRaises(frappe.ValidationError):
				self.new_return(number)

	def test_a_return_without_period_names_the_missing_field(self):
		with self.assertRaises(frappe.MandatoryError):
			frappe.get_doc({"doctype": "VAT Return", "company": COMPANY, "year": 2026}).insert()

	def test_a_year_without_kennzahlen_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "no Kennzahlen for 2025"):
			self.new_return(1, year=2025)

	def test_a_rhythm_other_than_the_settings_prescribe_is_refused(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "For month 4 of 2026, .* prescribe filing monthly, not quarterly"
		):
			self.new_return(2, rhythm="quarterly")

	def test_the_rhythm_follows_the_switch_to_monthly_filing(self):
		quarter = self.new_return(2, company=SWITCHING_COMPANY, rhythm="quarterly")
		self.assertEqual(
			(quarter.period_code, quarter.period_label, quarter.from_date, quarter.to_date),
			("42", "II. Kalendervierteljahr 2026", date(2026, 4, 1), date(2026, 6, 30)),
		)
		self.assertEqual(self.new_return(10, company=SWITCHING_COMPANY).period_code, "10")
		with self.assertRaisesRegex(frappe.ValidationError, "prescribe filing quarterly, not monthly"):
			self.new_return(3, company=SWITCHING_COMPANY)
		with self.assertRaisesRegex(frappe.ValidationError, "prescribe filing monthly, not quarterly"):
			self.new_return(4, company=SWITCHING_COMPANY, rhythm="quarterly")

	def test_the_dauerfrist_moves_the_deadline_by_a_month(self):
		quarter = self.new_return(2, company=SWITCHING_COMPANY, rhythm="quarterly")
		self.assertEqual(quarter.deadline, date(2026, 8, 10))

	def test_december_deducts_the_sondervorauszahlung_with_dauerfrist(self):
		doc = self.calculated(12, company=SWITCHING_COMPANY)
		self.assertEqual(doc.deadline, date(2027, 2, 10))
		self.assertEqual(self.amounts(doc), {"39": money(1200), "83": money(-1200)})
		self.assertEqual((money(doc.sondervorauszahlung), money(doc.kz83)), (money(1200), money(-1200)))

	def test_a_company_without_settings_cannot_file(self):
		with self.assertRaisesRegex(frappe.ValidationError, f"{BARE_COMPANY} has no VAT Return Settings"):
			self.new_return(3, company=BARE_COMPANY)

	def test_a_company_without_mapping_cannot_calculate(self):
		doc = self.new_return(3, company=UNMAPPED_COMPANY)
		with self.assertRaisesRegex(frappe.ValidationError, f"{UNMAPPED_COMPANY} has no VAT Return Mapping"):
			doc.calculate()

	def test_makes_the_import_file_for_mein_elster(self):
		doc = self.calculated(3)
		url = doc.make_import_file()
		file = attached_file(url, doc)
		self.assertEqual(
			(file.attached_to_doctype, file.attached_to_name, file.is_private, file.file_name),
			("VAT Return", doc.name, 1, "UStVA_2026_03.xml"),
		)
		document = contents(url)
		self.assertTrue(document.startswith(IMPORT_DECLARATION))
		self.assertIn("<Strasse>Hauptstraße 1</Strasse>".encode("iso-8859-15"), document)
		self.assertEqual(
			elements(document)[:3],
			[("Jahr", "2026"), ("Zeitraum", "03"), ("Steuernummer", "9123045678901")],
		)
		self.assertEqual(
			kennzahlen(document),
			{
				"Kz21": "2000",
				"Kz45": "500",
				"Kz46": "300",
				"Kz47": "57.00",
				"Kz66": "95.00",
				"Kz67": "57.00",
				"Kz81": "1000",
				"Kz83": "95.00",
			},
		)
		self.assertEqual(kennzahlen(document)["Kz83"], f"{money(doc.kz83):f}")

	def test_the_import_file_follows_the_schema_of_the_eric_documentation(self):
		schema = eric_schema.nutzdaten_schema(2026)
		document = contents(self.calculated(3).make_import_file())
		self.assertTrue(schema.validate(etree.ElementTree(etree.fromstring(document))), schema.error_log)

	def test_the_import_file_is_attached_once_for_the_same_content(self):
		doc = self.calculated(3)
		self.assertEqual(doc.make_import_file(), doc.make_import_file())
		self.assertEqual(
			frappe.db.count("File", {"attached_to_doctype": "VAT Return", "attached_to_name": doc.name}), 1
		)

	def test_the_import_file_follows_overrides_and_the_further_details(self):
		doc = self.calculated(9)
		doc.append(
			"kennzahlen", {"kennzahl": "43", "override": 250, "override_reason": "Export without booking"}
		)
		doc.attachments = 1
		doc.supplementary_code = "2"
		doc.kz500_begruendung = (
			"\N{DOUBLE LOW-9 QUOTATION MARK}Gutscheine\N{LEFT DOUBLE QUOTATION MARK}, siehe Anlage"
		)
		doc.save()
		document = contents(doc.make_import_file())
		self.assertEqual(
			kennzahlen(document),
			{
				"Kz22": "1",
				"Kz43": "250",
				"Kz83": "0.00",
				"Kz500": "2",
				"Kz500_Begruendung": '"Gutscheine", siehe Anlage',
			},
		)

	def test_a_kz500_without_begruendung_is_refused(self):
		doc = self.calculated(3)
		doc.supplementary_code = "1"
		with self.assertRaisesRegex(frappe.ValidationError, "Kennzahl 500 needs a Begründung"):
			doc.save()

	def test_a_begruendung_without_kz500_is_refused(self):
		doc = self.calculated(3)
		doc.kz500_begruendung = "Siehe Anlage"
		with self.assertRaisesRegex(frappe.ValidationError, "only filed with Kennzahl 500"):
			doc.save()

	def test_the_date_of_the_switch_to_the_regelbesteuerung_is_filed_in_kz70(self):
		"""Line 12 of the form USt 1 A 2026 takes the date of the switch from the Kleinunternehmer-Regelung,
		which ERiC writes as TT.MM.JJJJ (Jahresdokumentation UStVA 2026, Kz70)."""
		doc = self.calculated(10, regelbesteuerung_from="2026-10-14")
		self.assertEqual(doc.regelbesteuerung_from, date(2026, 10, 14))
		self.assertEqual(kennzahlen(contents(doc.make_import_file())), {"Kz70": "14.10.2026", "Kz83": "0.00"})

	def test_a_switch_to_the_regelbesteuerung_in_another_year_is_refused(self):
		"""Rule 11085153: the year of the date in Kz 70 is the year of the Voranmeldungszeitraum."""
		with self.assertRaisesRegex(frappe.ValidationError, "has to lie in 2026, not in 2025"):
			self.new_return(2, regelbesteuerung_from="2025-12-01")

	def test_the_import_file_needs_a_calculation(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Calculate the return before making the file"):
			self.new_return(5).make_import_file()

	def test_a_return_that_is_not_ready_needs_remarks_for_the_import_file(self):
		a = self.account
		post_journal_entry(
			COMPANY, "2026-01-15", [(a["1400"], 1180, 0), (a["8400"], 0, 1000), (a["1776"], 0, 180)]
		)
		doc = self.calculated(1)
		self.assertEqual(doc.status, "Berechnet")
		with self.assertRaisesRegex(frappe.ValidationError, "The return is not ready"):
			doc.make_import_file()
		doc.remarks = "The Steuerberatung corrects the invoice in February."
		doc.save()
		self.assertEqual(kennzahlen(contents(doc.make_import_file())), {"Kz81": "1000", "Kz83": "190.00"})

	def test_a_corrected_return_writes_zero_for_what_it_no_longer_reports(self):
		first = self.calculated(11)
		first.append(
			"kennzahlen",
			{"kennzahl": "45", "override": 500, "override_reason": "Export invoice without booking"},
		)
		first.save()
		first.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		self.assertEqual(kennzahlen(contents(first.make_import_file())), {"Kz45": "500", "Kz83": "0.00"})
		correction = self.calculated(11, is_correction=1)
		url = correction.make_import_file()
		self.assertEqual(attached_file(url, correction).file_name, "UStVA_2026_11_berichtigt.xml")
		self.assertEqual(kennzahlen(contents(url)), {"Kz10": "1", "Kz45": "0", "Kz83": "0.00"})
		correction.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		self.assertEqual(correction.make_import_file(), url)
		with self.assertRaisesRegex(frappe.ValidationError, "replaced or cancelled return"):
			first.make_import_file()

	def test_the_import_file_needs_the_address_of_the_datenlieferant(self):
		doc = self.calculated(12, company=SWITCHING_COMPANY)
		with self.assertRaisesRegex(frappe.ValidationError, "The street of the Datenlieferant is missing"):
			doc.make_import_file()
