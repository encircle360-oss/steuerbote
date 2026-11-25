"""Berechnen fills the Vorperiodenvergleich and the hints of a VAT Return from the ledger and the invoices of
the period, and leaves its amounts and whether it is ready as they are."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import fmt_money

from steuerbote import ustva
from steuerbote.invoices import load_lines
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)
from steuerbote.ustva.plausibility import NO_VAT_ID_ADVICE
from steuerbote.vatid.exemption import consequence

# The companies, their accounts, parties and vouchers are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

# Files monthly through 2026: a sale in August and a larger one in September, the verified month in October
# and again in November, nothing before August.
COMPANY = "Steuerbote Test Vorperiodenvergleich GmbH"
# The same sales in August and September, under thresholds of 10 % and 50 EUR.
STRICT_COMPANY = "Steuerbote Test Strenge Schwellen GmbH"
# Sells and buys with invoices in October 2026.
INVOICING_COMPANY = "Steuerbote Test Rechnungen GmbH"

# SKR03 numbers of the month in VerifiedMonthTest of the core, a bank, receivables and payables.
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
	"1600": ("Verbindlichkeiten aus Lieferungen und Leistungen", "Liability"),
}

REPORTED_IN_NOVEMBER = ["81", "46", "47", "21", "45", "66", "67", "83"]


def money(value) -> Decimal:
	return Decimal(str(value)).quantize(Decimal("0.01"))


def euros(amount: str) -> str:
	return fmt_money(Decimal(amount), currency="EUR")


def make_accounts(company: str) -> dict[str, str]:
	return {
		number: make_account(company, number, name, root_type)
		for number, (name, root_type) in ACCOUNTS.items()
	}


def post_verified_month(company: str, account: dict[str, str], posting_date: str) -> None:
	"""The month of VerifiedMonthTest in the core, as five journal entries."""
	a = account
	post_journal_entry(
		company, posting_date, [(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)]
	)
	post_journal_entry(company, posting_date, [(a["1400"], 2000, 0), (a["8336"], 0, 2000)])
	post_journal_entry(company, posting_date, [(a["1400"], 500, 0), (a["8338"], 0, 500)])
	post_journal_entry(
		company,
		posting_date,
		[(a["3123"], 300, 0), (a["1577"], 57, 0), (a["1787"], 0, 57), (a["1200"], 0, 300)],
	)
	post_journal_entry(company, posting_date, [(a["1576"], 95, 0), (a["1200"], 0, 95)])


def post_sales_of_august_and_september(company: str, account: dict[str, str]) -> None:
	a = account
	post_journal_entry(
		company, "2026-08-10", [(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)]
	)
	post_journal_entry(
		company, "2026-09-10", [(a["1400"], 1428, 0), (a["8400"], 0, 1200), (a["1776"], 0, 228)]
	)


def calculated(company: str, period: int):
	doc = frappe.get_doc(
		{
			"doctype": "VAT Return",
			"company": company,
			"year": 2026,
			"rhythm": "monthly",
			"period_index": period,
		}
	).insert()
	doc.calculate()
	doc.reload()
	return doc


def hints_of(doc) -> list[tuple[str, str]]:
	return [(row.severity, row.code) for row in doc.hints]


class TestComparison(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STVV")
		cls.account = make_accounts(COMPANY)
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)
		post_sales_of_august_and_september(COMPANY, cls.account)
		post_verified_month(COMPANY, cls.account, "2026-10-10")
		post_verified_month(COMPANY, cls.account, "2026-11-10")

		make_company(STRICT_COMPANY, "STVS")
		strict_account = make_accounts(STRICT_COMPANY)
		make_settings(
			STRICT_COMPANY,
			[(2026, "monthly", 1)],
			comparison_threshold_percent=10,
			comparison_threshold_amount=50,
		)
		make_mapping(STRICT_COMPANY)
		post_sales_of_august_and_september(STRICT_COMPANY, strict_account)

	def test_the_verified_november_gives_only_the_reconciliation_and_the_missing_catalogue(self):
		doc = calculated(COMPANY, 11)
		self.assertEqual((doc.ready, doc.status), (1, "Bereit"))
		self.assertEqual(
			hints_of(doc),
			[("Hinweis", "ABGLEICH-RECHNUNGEN")] * 4 + [("Hinweis", "KEIN-KATALOG")],
		)
		reconciliation = "Kz {0}: Die Rechnungen des Zeitraums ergeben netto {1}, das Hauptbuch {2}."
		ledger = {"81": "1000.00", "46": "300.00", "21": "2000.00", "45": "500.00"}
		self.assertEqual(
			[row.text for row in doc.hints],
			[reconciliation.format(number, euros("0"), euros(amount)) for number, amount in ledger.items()]
			+ ["Kein Katalog für 2025: Der Vergleich mit November 2025 bleibt leer."],
		)
		self.assertFalse(any(row.voucher_type or row.voucher_no or row.party for row in doc.hints))

	def test_november_compares_every_kennzahl_with_the_same_october(self):
		doc = calculated(COMPANY, 11)
		self.assertEqual([row.kennzahl for row in doc.comparison], REPORTED_IN_NOVEMBER)
		finals = {row.kennzahl: money(row.final) for row in doc.kennzahlen}
		for row in doc.comparison:
			with self.subTest(kennzahl=row.kennzahl):
				self.assertEqual(
					(money(row.current), money(row.previous_period), money(row.difference), row.flagged),
					(finals[row.kennzahl], finals[row.kennzahl], money(0), 0),
				)
				self.assertEqual((row.previous_period_known, row.previous_year_known), (1, 0))
				self.assertEqual(money(row.previous_year), money(0))

	def test_a_month_without_postings_compares_with_zero_and_flags_nothing(self):
		doc = calculated(COMPANY, 7)
		self.assertEqual(
			[
				(
					row.kennzahl,
					money(row.current),
					money(row.previous_period),
					row.flagged,
					row.previous_period_known,
				)
				for row in doc.comparison
			],
			[("83", money(0), money(0), 0, 1)],
		)
		self.assertEqual(hints_of(doc), [("Hinweis", "KEIN-KATALOG")])

	def test_a_kennzahl_new_in_its_period_deviates_by_the_rule_of_the_report(self):
		doc = calculated(COMPANY, 8)
		self.assertEqual([(row.kennzahl, row.flagged) for row in doc.comparison], [("81", 1), ("83", 1)])
		self.assertEqual(
			[row.text for row in doc.hints if row.code == "ABWEICHUNG-VORPERIODE"],
			[
				f"Kz 81 liegt mit {euros('1000')} über der Vorperiode Juli 2026 ({euros('0')}).",
				f"Kz 83 liegt mit {euros('190.00')} über der Vorperiode Juli 2026 ({euros('0')}).",
			],
		)
		self.assertEqual((doc.ready, doc.status), (1, "Bereit"))

	def test_the_default_thresholds_leave_a_change_of_a_fifth_alone(self):
		doc = calculated(COMPANY, 9)
		row = next(row for row in doc.comparison if row.kennzahl == "81")
		self.assertEqual(
			(money(row.current), money(row.previous_period), money(row.difference), row.difference_percent),
			(money(1200), money(1000), money(200), 20),
		)
		self.assertEqual([row.kennzahl for row in doc.comparison if row.flagged], [])
		self.assertNotIn("ABWEICHUNG-VORPERIODE", [row.code for row in doc.hints])

	def test_the_thresholds_of_the_settings_decide_what_deviates(self):
		doc = calculated(STRICT_COMPANY, 9)
		self.assertEqual([row.kennzahl for row in doc.comparison if row.flagged], ["81"])
		share = f"{fmt_money(Decimal('20.00'), precision=1)} %"
		self.assertEqual(
			[row.text for row in doc.hints if row.code == "ABWEICHUNG-VORPERIODE"],
			[
				f"Kz 81 liegt mit {euros('1200')} um {share} über der Vorperiode August 2026 ({euros('1000')})."
			],
		)

	def test_january_compares_with_periods_without_catalogue(self):
		doc = calculated(COMPANY, 1)
		self.assertEqual(
			[(row.kennzahl, row.previous_period_known, row.previous_year_known) for row in doc.comparison],
			[("83", 0, 0)],
		)
		self.assertEqual(
			[row.text for row in doc.hints],
			["Kein Katalog für 2025: Der Vergleich mit Dezember 2025 und Januar 2025 bleibt leer."],
		)

	def test_a_mapping_that_does_not_fit_a_compared_year_leaves_its_comparison_empty(self):
		error = ustva.MappingError("account 8400: unknown Kennzahl 81")
		with patch.object(ustva.Mapping, "for_year", side_effect=error):
			doc = calculated(COMPANY, 9)
		self.assertEqual(
			{(row.previous_period_known, row.previous_year_known, row.flagged) for row in doc.comparison},
			{(0, 0, 0)},
		)
		self.assertEqual(
			[(row.code, row.text) for row in doc.hints if row.code != "ABGLEICH-RECHNUNGEN"],
			[
				(
					"ZUORDNUNG-JAHRGANG",
					"Die Kontenzuordnung passt nicht zum Vordruck 2025: Der Vergleich mit September 2025 bleibt leer.",
				),
				(
					"ZUORDNUNG-JAHRGANG",
					"Die Kontenzuordnung passt nicht zum Vordruck 2026: Der Vergleich mit August 2026 bleibt leer.",
				),
			],
		)

	def test_the_period_of_a_saved_return_stays_with_its_comparison_and_hints(self):
		doc = calculated(COMPANY, 11)
		self.assertTrue(doc.comparison and doc.hints)
		counts = (len(doc.comparison), len(doc.hints), doc.status)
		doc.period_index = 10
		with self.assertRaises(frappe.CannotChangeConstantError):
			doc.save()
		doc.reload()
		self.assertEqual((len(doc.comparison), len(doc.hints), doc.status), counts)


def insert(doctype: str, **fields) -> str:
	"""A record written as ERPNext keeps it once submitted, without the validations of its form."""
	doc = frappe.get_doc({"doctype": doctype, **fields})
	doc.db_insert()
	return doc.name


def make_party(doctype: str, name: str, country: str, tax_id: str | None = None) -> str:
	"""A customer or supplier and its billing address in the country; returns the address."""
	name_field = "customer_name" if doctype == "Customer" else "supplier_name"
	insert(doctype, name=name, **{name_field: name}, tax_id=tax_id)
	return insert(
		"Address",
		name=f"{name}-Billing",
		address_title=name,
		address_type="Billing",
		address_line1="Teststraße 1",
		city="Teststadt",
		country=country,
	)


def post_invoice(
	doctype: str,
	name: str,
	party: str,
	address: str,
	posting_date: str,
	items: list[tuple[str, float, tuple[float, ...]]],
	ledger: list[tuple[str, float, float]],
	**fields,
) -> str:
	"""A submitted invoice as Steuerbote reads it: its header, its items with the tax ERPNext computes for
	each of them per tax row (Item Wise Tax Detail), and its GL Entries.

	Submitting a real invoice needs items, price lists and a chart of accounts with receivables and payables
	that neither the ledger nor the invoice lines read, so the rows are written as ERPNext stores them.
	"""
	party_field, name_field, address_field = (
		("customer", "customer_name", "customer_address")
		if doctype == "Sales Invoice"
		else ("supplier", "supplier_name", "supplier_address")
	)
	account_field = "income_account" if doctype == "Sales Invoice" else "expense_account"
	insert(
		doctype,
		name=name,
		company=INVOICING_COMPANY,
		posting_date=posting_date,
		docstatus=fields.pop("docstatus", 1),
		is_opening=fields.pop("is_opening", "No"),
		**{party_field: party, name_field: party, address_field: address},
		**fields,
	)
	for index, (account, net, taxes) in enumerate(items, start=1):
		item = insert(
			f"{doctype} Item",
			name=f"{name}-{index}",
			parent=name,
			parenttype=doctype,
			parentfield="items",
			idx=index,
			item_name="Leistung",
			qty=1,
			net_amount=net,
			base_net_amount=net,
			**{account_field: account},
		)
		for tax_index, amount in enumerate(taxes, start=1):
			insert(
				"Item Wise Tax Detail",
				name=f"{item}-{tax_index}",
				parent=name,
				parenttype=doctype,
				parentfield="item_wise_tax_details",
				idx=tax_index,
				item_row=item,
				rate=19,
				amount=amount,
				taxable_amount=net,
			)
	for account, debit, credit in ledger:
		insert(
			"GL Entry",
			company=INVOICING_COMPANY,
			posting_date=posting_date,
			account=account,
			debit=debit,
			credit=credit,
			voucher_type=doctype,
			voucher_no=name,
			is_cancelled=0,
			is_opening="No",
			docstatus=1,
		)
	return name


class TestHintsFromInvoices(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(INVOICING_COMPANY, "STVR")
		a = cls.account = make_accounts(INVOICING_COMPANY)
		make_settings(INVOICING_COMPANY, [(2026, "monthly", 1)])
		make_mapping(INVOICING_COMPANY)
		german = make_party("Customer", "Muster Handels GmbH", "Germany", "DE123456789")
		austrian = make_party("Customer", "Alpen Beratung GmbH", "Austria")
		swedish = make_party("Supplier", "Nord Software AB", "Sweden", "SE123456789001")
		post_invoice(
			"Sales Invoice",
			"SINV-STVR-0001",
			"Muster Handels GmbH",
			german,
			"2026-10-05",
			[(a["8400"], 1000, (190,))],
			[(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)],
		)
		post_invoice(
			"Sales Invoice",
			"SINV-STVR-0002",
			"Alpen Beratung GmbH",
			austrian,
			"2026-10-06",
			[(a["8336"], 2000, ())],
			[(a["1400"], 2000, 0), (a["8336"], 0, 2000)],
		)
		post_invoice(
			"Purchase Invoice",
			"PINV-STVR-0001",
			"Nord Software AB",
			swedish,
			"2026-10-07",
			[(a["3123"], 300, (57, -57))],
			[(a["3123"], 300, 0), (a["1577"], 57, 0), (a["1787"], 0, 57), (a["1600"], 0, 300)],
		)
		post_invoice(
			"Sales Invoice",
			"SINV-STVR-0003",
			"Muster Handels GmbH",
			german,
			"2026-10-08",
			[(a["8400"], -100, (-19,))],
			[(a["1400"], 0, 119), (a["8400"], 100, 0), (a["1776"], 19, 0)],
			is_return=1,
		)
		post_invoice(
			"Sales Invoice",
			"SINV-STVR-0004",
			"Alpen Beratung GmbH",
			austrian,
			"2026-10-09",
			[(a["8400"], 500, ())],
			[],
			docstatus=2,
		)
		post_invoice(
			"Sales Invoice",
			"SINV-STVR-0005",
			"Alpen Beratung GmbH",
			austrian,
			"2026-10-09",
			[(a["8336"], 700, ())],
			[],
			is_opening="Yes",
		)

	def test_reads_the_lines_of_the_submitted_invoices_of_the_period(self):
		lines = load_lines(INVOICING_COMPANY, "2026-10-01", "2026-10-31", ["8400", "8336"], ["3123"])
		self.assertEqual(
			[
				(
					line.voucher_type,
					line.voucher_no,
					line.posting_date,
					line.party,
					line.party_country,
					line.party_tax_id or None,
					line.account_number,
					line.net_amount,
					line.tax_amount,
					line.is_return,
				)
				for line in lines
			],
			[
				(
					"Sales Invoice",
					"SINV-STVR-0001",
					date(2026, 10, 5),
					"Muster Handels GmbH",
					"Germany",
					"DE123456789",
					"8400",
					money(1000),
					money(190),
					False,
				),
				(
					"Sales Invoice",
					"SINV-STVR-0002",
					date(2026, 10, 6),
					"Alpen Beratung GmbH",
					"Austria",
					None,
					"8336",
					money(2000),
					money(0),
					False,
				),
				(
					"Sales Invoice",
					"SINV-STVR-0003",
					date(2026, 10, 8),
					"Muster Handels GmbH",
					"Germany",
					"DE123456789",
					"8400",
					money(-100),
					money(-19),
					True,
				),
				(
					"Purchase Invoice",
					"PINV-STVR-0001",
					date(2026, 10, 7),
					"Nord Software AB",
					"Sweden",
					"SE123456789001",
					"3123",
					money(300),
					money(0),
					False,
				),
			],
		)

	def test_reads_only_the_accounts_asked_for(self):
		lines = load_lines(INVOICING_COMPANY, "2026-10-01", "2026-10-31", ["8336"], [])
		self.assertEqual([line.voucher_no for line in lines], ["SINV-STVR-0002"])
		self.assertEqual(load_lines(INVOICING_COMPANY, "2026-11-01", "2026-11-30", ["8400"], ["3123"]), [])

	def test_an_eu_service_to_a_customer_without_vat_id_holds_the_return_until_the_remarks_explain_it(self):
		"""Without a USt-IdNr. of the recipient the ZM cannot report the service, and the Voranmeldung holds the same
		voucher the same way (decision of the maintainer, docs/zm.md [Q16])."""
		doc = calculated(INVOICING_COMPANY, 10)
		self.assertEqual((doc.ready, doc.status), (0, "Berechnet"))
		invoice_hints = [
			row for row in doc.hints if row.code not in ("ABWEICHUNG-VORPERIODE", "KEIN-KATALOG")
		]
		self.assertEqual(
			[(row.severity, row.code, row.voucher_type, row.voucher_no, row.party) for row in invoice_hints],
			[("Fehler", "EU-OHNE-USTID", "Sales Invoice", "SINV-STVR-0002", "Alpen Beratung GmbH")],
		)
		self.assertEqual(
			invoice_hints[0].text,
			f"Rechnung SINV-STVR-0002 über {euros('2000.00')} geht in Kz 21 ein, "
			f"aber der Kunde Alpen Beratung GmbH hat keine USt-IdNr. {consequence('21')} {NO_VAT_ID_ADVICE}",
		)
		self.assertEqual(doc.hints[0].code, "EU-OHNE-USTID")
