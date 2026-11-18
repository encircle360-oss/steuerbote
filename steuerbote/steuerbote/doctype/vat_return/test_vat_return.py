from datetime import date
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.steuerbote.doctype.vat_return import vat_return
from steuerbote.tests.helpers import make_account, make_company, post_journal_entry
from steuerbote.ustva import Rhythm

# The company, its accounts and the vouchers are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

COMPANY = "Steuerbote Test Voranmeldung GmbH"

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


def money(value) -> Decimal:
	return Decimal(str(value)).quantize(Decimal("0.01"))


class FakeSettings:
	"""VAT Return Settings as the return reads them."""

	chart = "SKR03"
	tolerance = 0.01

	def __init__(self, rhythm: Rhythm, dauerfrist: bool = False, sondervorauszahlung: str = "0") -> None:
		self.rhythm = rhythm
		self.dauerfrist = dauerfrist
		self.amount = Decimal(sondervorauszahlung)

	def rhythm_for(self, year: int, month: int) -> Rhythm:
		return self.rhythm

	def has_dauerfrist(self, year: int) -> bool:
		return self.dauerfrist

	def sondervorauszahlung(self, year: int) -> Decimal:
		return self.amount


class TestVATReturn(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STVA")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		a = cls.account
		march = "2026-03-10"
		cls.sale = post_journal_entry(
			COMPANY, march, [(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)]
		)
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

	def new_return(self, period: int, **fields):
		return frappe.get_doc(
			{"doctype": "VAT Return", "company": COMPANY, "year": 2026, "period_index": period, **fields}
		).insert()

	def calculated(self, period: int, **fields):
		doc = self.new_return(period, **fields)
		doc.calculate()
		doc.reload()
		return doc

	def kennzahl(self, doc, number: str):
		return next(row for row in doc.kennzahlen if row.kennzahl == number)

	def amounts(self, doc) -> dict[str, Decimal]:
		return {row.kennzahl: money(row.final) for row in doc.kennzahlen}

	def test_takes_the_period_from_the_settings(self):
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
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

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
		with self.assertRaises(frappe.ValidationError):
			doc.submit()
		doc.reload()
		doc.remarks = "The Steuerberatung corrects the invoice in July."
		doc.submit()
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
		first.submit()
		self.assertEqual(first.status, "Abgegeben")
		with self.assertRaises(frappe.ValidationError):
			self.new_return(4)
		correction = self.calculated(4, is_correction=1)
		correction.submit()
		first.reload()
		self.assertEqual((first.status, correction.status), ("Ersetzt", "Abgegeben"))

	def test_cancelling_a_correction_restores_the_return_it_replaced(self):
		first = self.calculated(7)
		first.submit()
		correction = self.calculated(7, is_correction=1)
		correction.submit()
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
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{"doctype": "VAT Return", "company": COMPANY, "year": 2025, "period_index": 1}
			).insert()

	def test_quarterly_filing_from_the_settings(self):
		with patch.object(vat_return, "settings_for", return_value=FakeSettings(Rhythm.QUARTERLY)):
			doc = self.new_return(2)
		self.assertEqual(
			(doc.rhythm, doc.period_code, doc.period_label, doc.from_date, doc.to_date, doc.deadline),
			(
				"quarterly",
				"42",
				"II. Kalendervierteljahr 2026",
				date(2026, 4, 1),
				date(2026, 6, 30),
				date(2026, 7, 10),
			),
		)

	def test_december_deducts_the_sondervorauszahlung_with_dauerfrist(self):
		settings = FakeSettings(Rhythm.MONTHLY, dauerfrist=True, sondervorauszahlung="1200.00")
		with patch.object(vat_return, "settings_for", return_value=settings):
			doc = self.calculated(12)
		self.assertEqual(doc.deadline, date(2027, 2, 10))
		self.assertEqual(self.amounts(doc), {"39": money(1200), "83": money(-1200)})
		self.assertEqual((money(doc.sondervorauszahlung), money(doc.kz83)), (money(1200), money(-1200)))
