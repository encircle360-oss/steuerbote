"""What the Umsatzsteuererklärung reads from ERPNext: the ledger of the year and of its periods, the filed
Voranmeldungen with their Kennzahlen, the Sondervorauszahlung, the payments to the Finanzamt, the day of a switch to
the Regelbesteuerung, and the details of the company and its Steuerberatung. Every name and amount is invented."""

from datetime import date
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import ustjahr_sources
from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)
from steuerbote.ustjahr.soll import FiledKennzahl
from steuerbote.ustva.period import Period

COMPANY = "Steuerbote Test USt-Erklärung Quellen GmbH"
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1780": ("Umsatzsteuer-Vorauszahlungen", "Liability"),
	"1781": ("Umsatzsteuer-Vorauszahlungen 1/11", "Liability"),
	"1200": ("Bank", "Asset"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}
FILED_IN_MEIN_ELSTER = "mein_elster"


def d(value: str) -> Decimal:
	return Decimal(value)


class TestUstjahrSources(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STUQ")
		a = cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		for year in (2025, 2026, 2027):
			ensure_fiscal_year(COMPANY, date(year, 6, 30))
		cls.settings = make_settings(
			COMPANY,
			[(2026, "monthly", 1)],
			[(2026, True, "1100.00")],
			wid_nr="DE123456788",
			phone="089 1234567",
			email="buchhaltung@example.org",
		)
		make_mapping(COMPANY)
		cls.sale(a, "2025-12-30", 100)
		cls.sale(a, "2026-03-10", 1000)
		cls.march = cls.filed(3, regelbesteuerung_from="2026-03-01")
		cls.sale(a, "2026-03-20", 200)
		cls.march_corrected = cls.filed(3, is_correction=1)
		cls.sale(a, "2026-04-10", 500)
		cls.april = cls.filed(4, regelbesteuerung_from="2026-02-01")
		cls.sale(a, "2027-01-05", 300)
		post_journal_entry(COMPANY, "2026-02-10", [(a["1781"], 1100, 0), (a["1200"], 0, 1100)], exclude=True)
		post_journal_entry(COMPANY, "2026-04-10", [(a["1780"], 190, 0), (a["1200"], 0, 190)])
		refund = post_journal_entry(COMPANY, "2026-05-10", [(a["1200"], 30, 0), (a["1780"], 0, 30)])
		refund.cancel()
		post_journal_entry(COMPANY, "2027-01-10", [(a["1780"], 95, 0), (a["1200"], 0, 95)])

	@classmethod
	def sale(cls, a: dict, posting_date: str, net: int) -> None:
		tax = net * 19 // 100
		post_journal_entry(
			COMPANY, posting_date, [(a["1400"], net + tax, 0), (a["8400"], 0, net), (a["1776"], 0, tax)]
		)

	@classmethod
	def filed(cls, month: int, **fields) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": month,
				**fields,
			}
		).insert()
		doc.calculate()
		doc.reload()
		doc.mark_filed_outside(filed_via=FILED_IN_MEIN_ELSTER)
		return doc.name

	def test_reads_the_ledger_of_the_calendar_year(self):
		lines = ustjahr_sources.year_lines(COMPANY, 2026)
		self.assertEqual(sum(line.credit for line in lines if line.account_number == "8400"), d("1700.00"))

	def test_runs_the_voranmeldung_on_each_period(self):
		mapping = frappe.get_doc("VAT Return Mapping", COMPANY).to_mapping(2026)
		march, april = Period.month(2026, 3), Period.month(2026, 4)
		runs = ustjahr_sources.period_runs(COMPANY, (march, april), mapping, d("0.01"))
		self.assertEqual(list(runs), [march, april])
		self.assertEqual(
			(runs[march].values["81"].amount, runs[april].values["81"].amount), (d("1200.00"), d("500.00"))
		)

	def test_gives_each_account_its_line_of_the_annual_return(self):
		split = ustjahr_sources.annual_split(COMPANY, 2026)
		self.assertEqual(split.field_of("8400"), "E3003303")

	def test_a_company_without_a_mapping_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "has no VAT Return Mapping"):
			ustjahr_sources.annual_split("Steuerbote Test Ohne Zuordnung Jahr GmbH", 2026)

	def test_reads_the_latest_filed_voranmeldung_of_each_period_with_its_kennzahlen(self):
		filed = ustjahr_sources.filed_voranmeldungen(COMPANY, 2026)
		self.assertEqual(
			[(entry.period, entry.name) for entry in filed],
			[
				(Period.month(2026, 3), self.march_corrected),
				(Period.month(2026, 4), self.april),
			],
		)
		march = filed[0]
		self.assertEqual((march.kz83, march.kz39), (d("228.00"), d("0.00")))
		self.assertEqual(march.lines["81"], FiledKennzahl(d("1200.00"), d("1200.00"), d("1200.00")))
		self.assertEqual(frappe.db.get_value("VAT Return", self.march, "status"), "Ersetzt")
		self.assertEqual(ustjahr_sources.filed_voranmeldungen(COMPANY, 2027), ())

	def test_reads_the_earliest_day_of_a_switch_the_filed_voranmeldungen_name(self):
		self.assertEqual(ustjahr_sources.switch_to_regelbesteuerung(COMPANY, 2026), date(2026, 2, 1))
		self.assertIsNone(ustjahr_sources.switch_to_regelbesteuerung(COMPANY, 2027))

	def test_reads_the_sondervorauszahlung_of_a_year_with_dauerfristverlaengerung(self):
		self.assertEqual(ustjahr_sources.sondervorauszahlung(self.settings, 2026), d("1100.00"))
		self.assertEqual(ustjahr_sources.sondervorauszahlung(self.settings, 2027), d("0"))

	def test_reads_the_payments_of_the_year_also_from_journal_entries_the_voranmeldung_leaves_out(self):
		lines = ustjahr_sources.payment_lines(COMPANY, 2026, ("1780", "1781"))
		self.assertEqual(
			sorted((line.account_number, line.debit, line.credit) for line in lines),
			[("1780", d("190.00"), d("0.00")), ("1781", d("1100.00"), d("0.00"))],
		)
		self.assertEqual(ustjahr_sources.payment_lines(COMPANY, 2026, ()), [])

	def test_reads_the_details_of_the_company_from_its_settings(self):
		details = ustjahr_sources.company(COMPANY)
		self.assertEqual(
			(details.name, details.wid_nr, details.phone, details.email, details.address),
			(COMPANY, "DE123456788", "089 1234567", "buchhaltung@example.org", None),
		)
		settings = frappe.get_doc(
			{
				"doctype": "Annual Filing Settings",
				"company": COMPANY,
				"legal_form": "GmbH",
				"business_purpose": "Softwareentwicklung",
				"street": "Musterweg",
				"house_number": "12",
				"postal_code": "80331",
				"city": "München",
				"country": "Germany",
				"advisor_name": "Steuerkanzlei Beispiel",
				"advisor_client_number": "4711",
				"years": [{"year": 2026, "advisor_prepares": 1}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Annual Filing Settings", settings.name, force=True)
		details = ustjahr_sources.company(COMPANY)
		self.assertEqual(
			(details.business_purpose, details.address.street_line), ("Softwareentwicklung", "Musterweg 12")
		)
		advisor = ustjahr_sources.advisor(COMPANY, 2026)
		self.assertEqual((advisor.name, advisor.client_number), ("Steuerkanzlei Beispiel", "4711"))
		self.assertIsNone(ustjahr_sources.advisor(COMPANY, 2027))

	def test_a_company_without_annual_filing_settings_has_no_steuerberatung(self):
		self.assertIsNone(ustjahr_sources.advisor(COMPANY, 2026))
