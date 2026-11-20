"""What the Zusammenfassende Meldung reads from ERPNext: the shares of Kz 41, 42 and 21 by voucher, the customer of
each voucher, the deliveries of each month, the filed Voranmeldungen and the details of a customer."""

from datetime import date
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import zm_sources
from steuerbote.steuerbote.doctype.recapitulative_statement.bridge import FiledReturn, Party
from steuerbote.tests.helpers import (
	insert_record,
	make_account,
	make_company,
	make_customer,
	make_mapping,
	make_settings,
	post_customer_journal_entry,
	post_payment_entry,
	post_sales_invoice,
)
from steuerbote.vatid.result import Details
from steuerbote.zm.period import ReportingPeriod
from steuerbote.zm.rhythm import Coverage

COMPANY = "Steuerbote Test ZM-Quellen GmbH"
NORD = "Nord Logistik AB (Quellen)"
SUD = "Sud Commerce SARL (Quellen)"
ROMA = "Roma Servizi SRL (Quellen)"
ACCOUNTS = {
	"8125": ("Steuerfreie innergemeinschaftliche Lieferungen", "Income"),
	"8743": ("Gewährte Skonti innergemeinschaftliche Lieferungen", "Income"),
	"8130": ("Lieferungen des ersten Abnehmers bei Dreiecksgeschäften", "Income"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"8400": ("Erlöse 19 % USt", "Income"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
	"1200": ("Bank", "Asset"),
}


def d(value: str) -> Decimal:
	return Decimal(value)


class TestZmSources(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STZS")
		a = cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)])
		cls.mapping = make_mapping(COMPANY).to_mapping(2026)
		cls.nord = make_customer(NORD, "Sweden", "SE123456789001", city="Malmö")
		cls.sud = make_customer(SUD, "France", "FR12345678901", city="Lyon", primary=False)
		make_customer(ROMA, "Italy", None, city="")
		cls.shipped = insert_record(
			"Address",
			name="Sud Commerce Lager (Quellen)",
			address_title=SUD,
			address_type="Shipping",
			address_line1="Quai 1",
			city="Lyon",
			country="Belgium",
		)
		october = "2026-10-12"
		cls.delivery = post_sales_invoice(
			COMPANY,
			"SINV-STZS-1",
			NORD,
			october,
			[(a["1400"], 8000, 0), (a["8125"], 0, 8000)],
			customer_address=cls.nord,
		)
		cls.triangular = post_sales_invoice(
			COMPANY,
			"SINV-STZS-2",
			SUD,
			october,
			[(a["1400"], 5000, 0), (a["8130"], 0, 5000)],
			customer_address=cls.sud,
			shipping_address_name=cls.shipped,
		)
		cls.untaxed = post_sales_invoice(
			COMPANY, "SINV-STZS-3", ROMA, october, [(a["1400"], 700, 0), (a["8336"], 0, 700)]
		)
		cls.payment = post_payment_entry(
			COMPANY,
			"PE-STZS-1",
			NORD,
			"2026-10-20",
			[cls.delivery],
			[(a["1200"], 7900, 0), (a["8743"], 100, 0), (a["1400"], 0, 8000)],
		)
		cls.payment_without_invoice = post_payment_entry(
			COMPANY, "PE-STZS-2", SUD, "2026-10-21", [], [(a["1200"], 50, 0), (a["1400"], 0, 50)]
		)
		cls.write_off = post_customer_journal_entry(
			COMPANY,
			"JE-STZS-1",
			"2026-10-25",
			[(a["8743"], 300, 0, None), (a["1400"], 0, 300, NORD)],
		)
		cls.two_customers = post_customer_journal_entry(
			COMPANY,
			"JE-STZS-2",
			"2026-10-26",
			[(a["1400"], 0, 10, NORD), (a["1400"], 0, 10, SUD), (a["8743"], 20, 0, None)],
		)
		post_sales_invoice(
			COMPANY, "SINV-STZS-4", NORD, "2026-11-03", [(a["1400"], 60000, 0), (a["8125"], 0, 60000)]
		)
		post_sales_invoice(
			COMPANY, "SINV-STZS-5", NORD, "2026-11-04", [(a["1400"], 1190, 0), (a["8400"], 0, 1190)]
		)

	def test_the_shares_of_kz_41_and_42_in_the_goods_months_and_of_kz_21_in_the_services_months(self):
		october = ReportingPeriod.month(2026, 10)
		shares = zm_sources.shares(COMPANY, Coverage(october, (10,), (10,)), self.mapping)
		self.assertEqual(
			[(item.kennzahl, item.voucher, item.amount) for item in shares],
			[
				("41", f"Sales Invoice:{self.delivery}", d("8000.00")),
				("41", f"Payment Entry:{self.payment}", d("-100.00")),
				("41", f"Journal Entry:{self.write_off}", d("-300.00")),
				("41", f"Journal Entry:{self.two_customers}", d("-20.00")),
				("42", f"Sales Invoice:{self.triangular}", d("5000.00")),
				("21", f"Sales Invoice:{self.untaxed}", d("700.00")),
			],
		)
		goods_only = zm_sources.shares(COMPANY, Coverage(october, (10,), ()), self.mapping)
		self.assertEqual({item.kennzahl for item in goods_only}, {"41", "42"})

	def test_the_customer_of_each_kind_of_voucher(self):
		vouchers = [
			f"Sales Invoice:{self.delivery}",
			f"Sales Invoice:{self.triangular}",
			f"Sales Invoice:{self.untaxed}",
			f"Payment Entry:{self.payment}",
			f"Payment Entry:{self.payment_without_invoice}",
			f"Journal Entry:{self.write_off}",
			f"Journal Entry:{self.two_customers}",
			"Purchase Invoice:PINV-STZS-1",
			None,
		]
		self.assertEqual(
			zm_sources.parties(vouchers),
			{
				f"Sales Invoice:{self.delivery}": Party(NORD, NORD, "SE123456789001", "Sweden"),
				f"Sales Invoice:{self.triangular}": Party(SUD, SUD, "FR12345678901", "Belgium"),
				f"Sales Invoice:{self.untaxed}": Party(ROMA, ROMA, None, None),
				f"Payment Entry:{self.payment}": Party(NORD, NORD, "SE123456789001", "Sweden"),
				f"Payment Entry:{self.payment_without_invoice}": Party(SUD, SUD, "FR12345678901", None),
				f"Journal Entry:{self.write_off}": Party(NORD, NORD, "SE123456789001"),
			},
		)
		self.assertEqual(zm_sources.parties([]), {})

	def test_the_deliveries_of_each_month_of_the_window(self):
		deliveries = zm_sources.deliveries(COMPANY, (date(2026, 9, 1), date(2026, 11, 30)), self.mapping)
		self.assertEqual(
			deliveries,
			{(2026, 9): d("0"), (2026, 10): d("12580.00"), (2026, 11): d("60000.00")},
		)

	def test_the_filed_voranmeldungen_of_the_span(self):
		filed = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": 10,
			}
		).insert()
		filed.calculate()
		filed.reload()
		filed.mark_filed_outside("In Mein ELSTER abgegeben")
		frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": 9,
			}
		).insert()
		self.assertEqual(
			zm_sources.filed_returns(COMPANY, (date(2026, 9, 1), date(2026, 10, 31))),
			[
				FiledReturn(
					date(2026, 10, 1),
					date(2026, 10, 31),
					{"41": d("7580.00"), "42": d("5000.00"), "21": d("700.00")},
				)
			],
		)
		self.assertEqual(zm_sources.filed_returns(COMPANY, (date(2026, 11, 1), date(2026, 11, 30))), [])
		self.assertEqual(zm_sources.filed_returns(COMPANY, None), [])

	def test_the_details_of_a_customer_for_the_qualified_query(self):
		self.assertEqual(zm_sources.customer_details(NORD), Details(NORD, "Malmö", "12345", "Teststraße 1"))
		self.assertEqual(zm_sources.customer_details(SUD), Details(SUD, "Lyon", "12345", "Teststraße 1"))
		for customer in (ROMA, "Unbekannt GmbH (Quellen)", None):
			with self.subTest(customer=customer):
				self.assertIsNone(zm_sources.customer_details(customer))
