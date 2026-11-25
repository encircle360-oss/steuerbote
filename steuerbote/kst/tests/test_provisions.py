"""The proposed provisions for Körperschaftsteuer, Solidaritätszuschlag and Gewerbesteuer, as rows of a draft."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.gewst import chain as gewst
from steuerbote.kst import chain as kst
from steuerbote.kst.categories import Mapping
from steuerbote.kst.provisions import ACCOUNTS, ProvisionRow, Tax, TaxAccounts, differences, propose
from steuerbote.kst.tests.support import FIGURES, credit
from steuerbote.ustva.mapping import MappingError

ZERO = Decimal("0")


def results(profit: str, hebesatz: str | None = "400", **kwargs):
	"""The taxes of a GmbH with the given profit, the Vorauszahlungen of kwargs and no corrections."""
	gewst_prepayments = kwargs.pop("gewst_prepayments", ZERO)
	tax = kst.compute(
		kst.KstInputs(2026, (credit("8400", profit),), Mapping("SKR03", ()), loss_carry_back=ZERO, **kwargs),
		FIGURES,
	)
	trade = gewst.compute(
		tax,
		gewst.GewstInputs(Decimal(hebesatz) if hebesatz else None, prepayments=gewst_prepayments),
		FIGURES,
	)
	return tax, trade


class ProposeTest(TestCase):
	def test_proposes_the_provisions_of_the_three_taxes_on_the_accounts_of_skr03(self):
		tax, trade = results(
			"111200.00",
			capital_gains_tax_credit=Decimal("5000.00"),
			solz_credit=Decimal("275.00"),
			kst_prepayments=Decimal("10000.00"),
			solz_prepayments=Decimal("550.00"),
			gewst_prepayments=Decimal("15500.00"),
		)
		self.assertEqual(
			propose(tax, trade, ACCOUNTS["SKR03"]),
			(
				ProvisionRow(Tax.KST, Decimal("1680.00"), "2200", "0963", 2026),
				ProvisionRow(Tax.SOLZ, Decimal("92.40"), "2208", "0963", 2026),
				ProvisionRow(Tax.GEWST, Decimal("68.00"), "4320", "0956", 2026),
			),
		)

	def test_uses_the_accounts_of_skr04(self):
		tax, trade = results("111200.00")
		rows = propose(tax, trade, ACCOUNTS["SKR04"])
		self.assertEqual(
			[(row.debit_account, row.credit_account) for row in rows],
			[("7600", "3040"), ("7608", "3040"), ("7610", "3035")],
		)

	def test_a_refund_is_a_claim_against_the_finanzamt_or_the_gemeinde(self):
		tax, trade = results(
			"1000.00", kst_prepayments=Decimal("1000.00"), gewst_prepayments=Decimal("500.00")
		)
		rows = propose(tax, trade, ACCOUNTS["SKR03"])
		self.assertEqual(
			[(row.tax, row.amount, row.debit_account, row.credit_account, row.refund) for row in rows],
			[
				(Tax.KST, Decimal("850.00"), "1549", "2200", True),
				(Tax.SOLZ, Decimal("8.25"), "2208", "0963", False),
				(Tax.GEWST, Decimal("360.00"), "1540", "4320", True),
			],
		)

	def test_proposes_nothing_for_a_tax_without_balance(self):
		tax, trade = results("0.00")
		self.assertEqual(propose(tax, trade, ACCOUNTS["SKR03"]), ())

	def test_proposes_the_koerperschaftsteuer_alone_without_the_gewerbesteuer(self):
		tax, _ = results("111200.00")
		self.assertEqual([row.tax for row in propose(tax, None, ACCOUNTS["SKR03"])], [Tax.KST, Tax.SOLZ])

	def test_refuses_a_gewerbesteuer_without_hebesatz(self):
		tax, trade = results("111200.00", hebesatz=None)
		with self.assertRaisesRegex(ValueError, "the Gewerbesteuer has no Hebesatz"):
			propose(tax, trade, ACCOUNTS["SKR03"])


class DifferenceTest(TestCase):
	"""After a later posting the balances of the year change while the provisions posted before stay: „Rückstellungen
	sind zu bilden für ungewisse Verbindlichkeiten“ (§ 249 Abs. 1 Satz 1 HGB), in full, so Steuerbote proposes the
	difference between the balance of each tax and what the books hold of its provision or its claim to a refund."""

	def setUp(self):
		self.tax, self.trade = results(
			"111200.00",
			capital_gains_tax_credit=Decimal("5000.00"),
			solz_credit=Decimal("275.00"),
			kst_prepayments=Decimal("10000.00"),
			solz_prepayments=Decimal("550.00"),
			gewst_prepayments=Decimal("15500.00"),
		)

	def test_the_differences_are_the_balances_less_what_the_books_hold(self):
		posted = {Tax.KST: Decimal("1000.00"), Tax.SOLZ: Decimal("92.40"), Tax.GEWST: Decimal("100.00")}
		self.assertEqual(
			differences(self.tax, self.trade, posted),
			{Tax.KST: Decimal("680.00"), Tax.GEWST: Decimal("-32.00")},
		)
		self.assertEqual(
			differences(self.tax, None, {}), {Tax.KST: Decimal("1680.00"), Tax.SOLZ: Decimal("92.40")}
		)

	def test_proposes_the_difference_to_the_provisions_posted_before(self):
		posted = {Tax.KST: Decimal("1000.00"), Tax.SOLZ: Decimal("92.40"), Tax.GEWST: Decimal("100.00")}
		rows = propose(self.tax, self.trade, ACCOUNTS["SKR03"], posted)
		self.assertEqual(
			[(row.tax, row.amount, row.debit_account, row.credit_account, row.remark) for row in rows],
			[
				(
					Tax.KST,
					Decimal("680.00"),
					"2200",
					"0963",
					"Anpassung Rückstellung Körperschaftsteuer 2026",
				),
				(Tax.GEWST, Decimal("32.00"), "0956", "4320", "Anpassung Rückstellung Gewerbesteuer 2026"),
			],
		)

	def test_a_provision_that_turned_into_a_refund_is_released_and_the_claim_posted(self):
		tax, trade = results(
			"1000.00", kst_prepayments=Decimal("1000.00"), gewst_prepayments=Decimal("500.00")
		)
		posted = {Tax.KST: Decimal("100.00"), Tax.SOLZ: Decimal("8.25"), Tax.GEWST: Decimal("-360.00")}
		rows = propose(tax, trade, ACCOUNTS["SKR03"], posted)
		self.assertEqual(
			[(row.tax, row.amount, row.debit_account, row.credit_account) for row in rows],
			[(Tax.KST, Decimal("100.00"), "0963", "2200"), (Tax.KST, Decimal("850.00"), "1549", "2200")],
		)

	def test_a_claim_to_a_refund_that_grows_smaller_is_reduced(self):
		tax, trade = results(
			"1000.00", kst_prepayments=Decimal("1000.00"), gewst_prepayments=Decimal("500.00")
		)
		posted = {Tax.KST: Decimal("-900.00"), Tax.SOLZ: Decimal("8.25"), Tax.GEWST: Decimal("-360.00")}
		(row,) = propose(tax, trade, ACCOUNTS["SKR03"], posted)
		self.assertEqual(
			(row.tax, row.amount, row.debit_account, row.credit_account, row.remark),
			(
				Tax.KST,
				Decimal("50.00"),
				"2200",
				"1549",
				"Anpassung Erstattungsanspruch Körperschaftsteuer 2026",
			),
		)

	def test_nothing_is_proposed_where_the_books_hold_the_balances(self):
		posted = {Tax.KST: Decimal("1680.00"), Tax.SOLZ: Decimal("92.40"), Tax.GEWST: Decimal("68.00")}
		self.assertEqual(propose(self.tax, self.trade, ACCOUNTS["SKR03"], posted), ())
		self.assertEqual(differences(self.tax, self.trade, posted), {})


class RowTest(TestCase):
	def test_names_the_provision_or_the_refund_in_german(self):
		self.assertEqual(
			ProvisionRow(Tax.KST, Decimal("1680.00"), "2200", "0963", 2026).remark,
			"Rückstellung Körperschaftsteuer 2026",
		)
		self.assertEqual(
			ProvisionRow(Tax.GEWST, Decimal("360.00"), "1540", "4320", 2026, refund=True).remark,
			"Erstattungsanspruch Gewerbesteuer 2026",
		)

	def test_an_amount_is_positive_cents(self):
		with self.assertRaisesRegex(ValueError, "positive amount in cents"):
			ProvisionRow(Tax.KST, Decimal("-1.00"), "2200", "0963", 2026)

	def test_the_accounts_of_a_chart_are_account_numbers(self):
		self.assertEqual(set(ACCOUNTS), {"SKR03", "SKR04"})
		self.assertEqual(ACCOUNTS["SKR03"].gewst, TaxAccounts("4320", "0956", "1540"))
		with self.assertRaises(MappingError):
			TaxAccounts("2200 ", "0963", "1549")
