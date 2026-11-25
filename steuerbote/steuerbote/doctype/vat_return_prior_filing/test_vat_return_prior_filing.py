"""The Voranmeldungen filed before Steuerbote on a site: who entered them and when, the periods they may hold, the
start of the books in the VAT Return Settings, and the Dauerfristverlängerung that takes a year filed outside
Steuerbote as its base. The companies and amounts are invented."""

from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import prior_filings
from steuerbote.setup import start
from steuerbote.tests.helpers import make_company, make_mapping, make_settings

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "VAT Return"]

DOCTYPE = "VAT Return Prior Filing"
EXTENSION = "VAT Return Extension"
# Kept its books with a tax adviser until the end of 2026 and starts in ERPNext on 1 January 2027 with the opening
# balances; files monthly with the Dauerfristverlängerung.
COMPANY = "Steuerbote Test Start im laufenden Betrieb GmbH"
# Keeps its books in ERPNext throughout and names no start.
OWN_COMPANY = "Steuerbote Test Ohne Start GmbH"
SOURCE = "Übermittlungsprotokoll der Steuerberatung"
REASON = "Abgegeben von der Steuerberatung vor dem Start der Bücher in ERPNext"
AFTER_THE_FILINGS = "2027-02-15 10:00:00"


def money(value) -> Decimal:
	return Decimal(str(value)).quantize(Decimal("0.01"))


class TestVATReturnPriorFiling(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STSL")
		make_settings(COMPANY, [(2026, "monthly", 1)], [(2026, True, "4000.00")], books_start="2027-01-01")
		make_mapping(COMPANY)
		make_company(OWN_COMPANY, "STOS")
		make_settings(OWN_COMPANY, [(2026, "monthly", 1)])
		make_mapping(OWN_COMPANY)

	def setUp(self):
		frappe.db.savepoint("prior_filing_test")
		self.addCleanup(frappe.db.rollback, save_point="prior_filing_test")

	def record(self, month: int, kz83, kz39=0, company: str = COMPANY, rhythm: str = "monthly", **fields):
		with self.freeze_time(AFTER_THE_FILINGS):
			doc = frappe.get_doc(
				{
					"doctype": DOCTYPE,
					"company": company,
					"year": 2026,
					"rhythm": rhythm,
					"period_index": month,
					"filed_on": "2027-02-10"
					if month == 12 or rhythm == "quarterly"
					else f"2026-{month + 1:02d}-10",
					"kz83": kz83,
					"kz39": kz39,
					"source_document": SOURCE,
					"reason": REASON,
					**fields,
				}
			).insert()
			doc.submit()
		return doc

	def whole_year(self) -> list:
		records = [self.record(month, 2500) for month in range(1, 12)]
		records.append(self.record(12, -2000, 4000))
		return records

	def test_names_who_entered_it_and_when(self):
		doc = self.record(12, -2000, 4000, entered_by="Guest")
		self.assertEqual((doc.period_label, doc.entered_by), ("Dezember 2026", "Administrator"))
		self.assertTrue(doc.entered_on)
		self.assertRegex(doc.name, r"^VVS-2026-\d{5}$")

	def test_takes_no_period_from_the_start_of_the_books_on(self):
		with (
			self.assertRaisesRegex(
				frappe.ValidationError, "Januar 2027 begins on or after the start of the books"
			),
			self.freeze_time(AFTER_THE_FILINGS),
		):
			frappe.get_doc(
				{
					"doctype": DOCTYPE,
					"company": COMPANY,
					"year": 2027,
					"rhythm": "monthly",
					"period_index": 1,
					"filed_on": "2027-02-10",
					"kz83": 100,
					"source_document": SOURCE,
					"reason": REASON,
				}
			).insert()

	def test_needs_its_source_document_and_its_reason(self):
		with self.assertRaises(frappe.MandatoryError):
			self.record(5, 100, source_document="", reason="")

	def test_a_filing_in_the_future_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "A return cannot be filed in the future"):
			self.record(5, 100, filed_on="2027-03-01")

	def test_a_period_a_vat_return_files_through_steuerbote_holds_itself(self):
		vat_return = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": OWN_COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": 3,
			}
		).insert()
		vat_return.calculate()
		vat_return.reload()
		vat_return.mark_filed_outside("In Mein ELSTER abgegeben")
		with self.assertRaisesRegex(frappe.ValidationError, "through Steuerbote already"):
			self.record(1, 300, company=OWN_COMPANY, rhythm="quarterly")

	def test_months_of_another_rhythm_overlap(self):
		quarter = self.record(4, 3000, rhythm="quarterly")
		with self.assertRaisesRegex(frappe.ValidationError, f"{quarter.name} covers months of Dezember 2026"):
			self.record(12, 1000)
		corrected = self.record(4, 3100, rhythm="quarterly")
		self.assertEqual(corrected.docstatus, 1)

	def test_the_latest_filing_of_a_period_counts(self):
		self.record(5, 100)
		corrected = self.record(5, 150, filed_on="2026-09-01")
		self.assertEqual(
			next(
				(filed.name, filed.kz83)
				for filed in start.latest(prior_filings.prior_filings(COMPANY, {2026}))
			),
			(corrected.name, money(150)),
		)

	def test_a_cancelled_record_counts_no_more(self):
		doc = self.record(5, 100)
		doc.cancel()
		self.assertEqual(prior_filings.prior_filings(COMPANY, {2026}), [])

	def test_the_books_start_on_the_first_day_of_a_month(self):
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		settings.books_start = "2027-01-15"
		with self.assertRaisesRegex(frappe.ValidationError, "first day of a month"):
			settings.save()

	def test_the_books_start_after_every_period_entered_as_filed_before(self):
		doc = self.record(12, -2000, 4000)
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		settings.books_start = "2026-12-01"
		with self.assertRaisesRegex(frappe.ValidationError, f"{doc.name} enters Dezember 2026"):
			settings.save()

	def test_the_books_start_after_every_period_filed_through_steuerbote(self):
		vat_return = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": OWN_COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": 6,
			}
		).insert()
		vat_return.calculate()
		vat_return.reload()
		vat_return.mark_filed_outside("In Mein ELSTER abgegeben")
		settings = frappe.get_doc("VAT Return Settings", OWN_COMPANY)
		settings.books_start = "2026-06-01"
		settings.save()
		settings.books_start = "2027-01-01"
		with self.assertRaisesRegex(frappe.ValidationError, f"{vat_return.name} files Juni 2026"):
			settings.save()

	def test_the_dauerfristverlaengerung_takes_the_year_filed_before_steuerbote(self):
		"""Kz 83 of the twelve Voranmeldungen 2026 comes to 25.500 €, December credited 4.000 € in Kz 39: Zeile 8 is
		29.500 €, the Sondervorauszahlung 2027 one eleventh in whole euros (§ 47 Absatz 1 UStDV)."""
		records = self.whole_year()
		with self.freeze_time(AFTER_THE_FILINGS):
			doc = frappe.get_doc({"doctype": EXTENSION, "company": COMPANY, "year": 2027}).insert()
			doc.calculate()
			doc.reload()
		self.assertEqual(
			[(row.period_label, row.vat_return, row.prior_filing) for row in doc.base_rows][-1],
			("Dezember 2026", None, records[-1].name),
		)
		self.assertEqual(len(doc.base_rows), 12)
		self.assertEqual(
			(money(doc.kz83), money(doc.kz39), money(doc.computed_base), money(doc.sondervorauszahlung)),
			(money(25500), money(4000), money(29500), money(2681)),
		)
		self.assertIsNone(doc.missing_periods)
		self.assertNotIn("missing from the base", doc.findings or "")
		printed = frappe.get_print(
			EXTENSION, doc.name, print_format="Dauerfristverlängerung", no_letterhead=1
		)
		self.assertIn(f"{records[0].name} (vor Steuerbote abgegeben)", printed)

	def test_a_missing_month_stays_an_open_point(self):
		self.whole_year()[4].cancel()
		with self.freeze_time(AFTER_THE_FILINGS):
			doc = frappe.get_doc({"doctype": EXTENSION, "company": COMPANY, "year": 2027}).insert()
			doc.calculate()
			doc.reload()
		self.assertEqual(doc.missing_periods, "Mai 2026")
		self.assertIn("Kz 83 of Mai 2026 is missing from the base.", doc.findings)
