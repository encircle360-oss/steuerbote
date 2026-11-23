"""The Voranmeldung against the reports Sales Register and Purchase Register: rows, differences and hints."""

from decimal import Decimal
from types import MappingProxyType
from unittest import TestCase

from steuerbote.ustva.calculation import LedgerLine, calculate
from steuerbote.ustva.defaults import SKR03, SKR04, deliberately_without_kennzahl
from steuerbote.ustva.kennzahlen import KENNZAHLEN
from steuerbote.ustva.mapping import AccountRule, Mapping, Side, TaxCheck
from steuerbote.ustva.plausibility import Code, Severity
from steuerbote.ustva.registers import (
	PURCHASE_KENNZAHLEN,
	SALES_KENNZAHLEN,
	Reason,
	Register,
	RegisterLine,
	Row,
	hints,
	reconcile,
	subject,
)
from steuerbote.ustva.tests.test_plausibility import FIGURES

SALES = Register.SALES
PURCHASES = Register.PURCHASES
IGNORED = deliberately_without_kennzahl("SKR03")


def d(value: str) -> Decimal:
	return Decimal(value)


def shown(register: Register, number: str | None, amount: str, opening: bool = False) -> RegisterLine:
	"""What an invoice of the register shows in the column of an account; an account without number goes by name."""
	account = f"{number} - Konto - STB" if number else "Sonderkonto - STB"
	return RegisterLine(register, account, number, d(amount), opening)


def booked(
	number: str, debit: str = "0", credit: str = "0", voucher: str = "Journal Entry:JE-1"
) -> LedgerLine:
	return LedgerLine(number, d(debit), d(credit), voucher)


# The sale and the § 13b service of VerifiedMonthTest in the core, made with invoices, and a Vorsteuer.
INVOICED = (
	shown(SALES, "8400", "1000.00"),
	shown(SALES, "1776", "190.00"),
	shown(SALES, "8336", "2000.00"),
	shown(PURCHASES, "3123", "300.00"),
	shown(PURCHASES, "1577", "57.00"),
	shown(PURCHASES, "1787", "-57.00"),
	shown(PURCHASES, "4930", "95.00"),
	shown(PURCHASES, "1576", "95.00"),
)
LEDGER = (
	booked("1400", debit="1190.00", voucher="Sales Invoice:A"),
	booked("8400", credit="1000.00", voucher="Sales Invoice:A"),
	booked("1776", credit="190.00", voucher="Sales Invoice:A"),
	booked("1400", debit="2000.00", voucher="Sales Invoice:B"),
	booked("8336", credit="2000.00", voucher="Sales Invoice:B"),
	booked("3123", debit="300.00", voucher="Purchase Invoice:C"),
	booked("1577", debit="57.00", voucher="Purchase Invoice:C"),
	booked("1787", credit="57.00", voucher="Purchase Invoice:C"),
	booked("1600", credit="300.00", voucher="Purchase Invoice:C"),
	booked("4930", debit="95.00", voucher="Purchase Invoice:D"),
	booked("1576", debit="95.00", voucher="Purchase Invoice:D"),
	booked("1600", credit="190.00", voucher="Purchase Invoice:D"),
)


def compared(rows: tuple[Row, ...]) -> list[tuple]:
	return [
		(row.register, row.kennzahl, row.account_number, row.register_amount, row.ledger_amount)
		for row in rows
		if row.compared
	]


def not_compared(rows: tuple[Row, ...]) -> list[tuple]:
	return [(row.register, row.reason, row.register_amount, row.accounts) for row in rows if not row.compared]


class RegisterTest(TestCase):
	def test_the_registers_carry_the_names_of_the_reports(self):
		self.assertEqual([register.value for register in Register], ["Sales Register", "Purchase Register"])

	def test_the_kennzahlen_of_each_register_follow_the_sections_of_the_form(self):
		lines = {number: kennzahl.line for number, kennzahl in KENNZAHLEN.items()}
		self.assertEqual({lines[number] for number in SALES_KENNZAHLEN}, {*range(13, 24), *range(33, 37)})
		self.assertEqual({lines[number] for number in PURCHASE_KENNZAHLEN}, {*range(24, 33), *range(38, 42)})

	def test_the_amounts_no_invoice_gives_are_reconciled_with_no_register(self):
		reconciled = SALES_KENNZAHLEN | PURCHASE_KENNZAHLEN
		amounts = {number for number, kennzahl in KENNZAHLEN.items() if kennzahl.holds_amount}
		self.assertEqual(sorted(amounts - reconciled), ["37", "39", "50", "59", "63", "64", "65", "69", "83"])
		self.assertEqual(SALES_KENNZAHLEN & PURCHASE_KENNZAHLEN, frozenset())

	def test_every_verprobung_of_the_defaults_is_reconciled_with_one_register(self):
		for mapping in (SKR03, SKR04):
			for check in mapping.checks:
				for account in check.tax_accounts:
					rows = reconcile(
						[shown(SALES, account, "1"), shown(PURCHASES, account, "1")], [], mapping
					)
					with self.subTest(chart=mapping.chart, account=account):
						self.assertEqual(len([row for row in rows if row.compared]), 1)
						self.assertEqual(
							[row.reason for row in rows if not row.compared], [Reason.OTHER_REGISTER]
						)


class RegisterLineTest(TestCase):
	def test_an_account_without_number_goes_by_its_name(self):
		self.assertIsNone(shown(SALES, None, "5").account_number)

	def test_the_register_accepts_its_name(self):
		self.assertIs(RegisterLine("Sales Register", "8400 - X", "8400", d("1")).register, SALES)  # type: ignore[arg-type]

	def test_the_account_number_is_one_a_rule_could_match(self):
		with self.assertRaisesRegex(ValueError, "not an account number"):
			RegisterLine(SALES, "8400 - X", " 8400", d("1"))

	def test_names_an_account(self):
		with self.assertRaisesRegex(ValueError, "names no account"):
			RegisterLine(SALES, "", "8400", d("1"))

	def test_amounts_are_finite_decimals(self):
		with self.assertRaises(TypeError):
			RegisterLine(SALES, "8400 - X", "8400", 1.5)  # type: ignore[arg-type]
		with self.assertRaisesRegex(ValueError, "finite"):
			RegisterLine(SALES, "8400 - X", "8400", d("NaN"))

	def test_an_invoice_is_no_opening_invoice_unless_said(self):
		self.assertFalse(shown(SALES, "8400", "1").opening)


class ReconcileTest(TestCase):
	def test_invoices_that_make_the_whole_ledger_leave_no_difference(self):
		rows = reconcile(INVOICED, LEDGER, SKR03, IGNORED)
		self.assertEqual(
			compared(rows),
			[
				(SALES, "81", "", d("1000.00"), d("1000.00")),
				(SALES, "", "1776", d("190.00"), d("190.00")),
				(SALES, "21", "", d("2000.00"), d("2000.00")),
				(PURCHASES, "46", "", d("300.00"), d("300.00")),
				(PURCHASES, "", "1787", d("57.00"), d("57.00")),
				(PURCHASES, "66", "1576", d("95.00"), d("95.00")),
				(PURCHASES, "67", "1577", d("57.00"), d("57.00")),
			],
		)
		self.assertTrue(all(row.difference == 0 for row in rows if row.compared))
		self.assertEqual(not_compared(rows), [(PURCHASES, Reason.NO_PLACE, d("95.00"), ("4930",))])

	def test_the_ledger_amount_of_a_kennzahl_is_the_amount_berechnen_gives_it(self):
		rows = reconcile(INVOICED, LEDGER, SKR03, IGNORED)
		values = calculate(LEDGER, SKR03).values
		for row in rows:
			if row.kennzahl and not row.account_number:
				with self.subTest(kennzahl=row.kennzahl):
					self.assertEqual(row.ledger_amount, values[row.kennzahl].amount)

	def test_a_journal_entry_on_a_revenue_account_is_a_difference(self):
		ledger = (*LEDGER, booked("8400", credit="500.00"), booked("1776", credit="95.00"))
		rows = reconcile(INVOICED, ledger, SKR03, IGNORED)
		differences = [(row.kennzahl, row.account_number, row.difference) for row in rows if row.difference]
		self.assertEqual(differences, [("81", "", d("500.00")), ("", "1776", d("95.00"))])

	def test_an_invoice_missing_from_the_ledger_is_a_difference_too(self):
		rows = reconcile((*INVOICED, shown(SALES, "8400", "100.00")), LEDGER, SKR03, IGNORED)
		self.assertEqual([row.difference for row in rows if row.kennzahl == "81"], [d("-100.00")])

	def test_a_credit_note_reduces_the_register_as_it_reduces_the_ledger(self):
		lines = (*INVOICED, shown(SALES, "8400", "-100.00"), shown(SALES, "1776", "-19.00"))
		ledger = (*LEDGER, booked("8400", debit="100.00"), booked("1776", debit="19.00"))
		rows = reconcile(lines, ledger, SKR03, IGNORED)
		self.assertEqual(
			[
				(row.register_amount, row.ledger_amount)
				for row in rows
				if row.kennzahl == "81" or row.account_number == "1776"
			],
			[(d("900.00"), d("900.00")), (d("171.00"), d("171.00"))],
		)

	def test_the_purchase_register_shows_the_debit_side_and_a_deducted_tax_as_credit(self):
		rows = reconcile(INVOICED, LEDGER, SKR03, IGNORED)
		(output_tax,) = (row for row in rows if row.account_number == "1787")
		self.assertEqual((output_tax.register_amount, output_tax.ledger_amount), (d("57.00"), d("57.00")))

	def test_a_kennzahl_or_tax_account_of_the_register_with_a_ledger_amount_alone_gets_a_row(self):
		rows = reconcile(
			INVOICED, (*LEDGER, booked("8338", credit="500.00"), booked("1571", debit="7.00")), SKR03
		)
		self.assertIn((SALES, "45", "", d("0"), d("500.00")), compared(rows))
		self.assertIn((PURCHASES, "66", "1571", d("0"), d("7.00")), compared(rows))

	def test_a_tax_account_a_rule_maps_carries_its_kennzahl(self):
		mapping = Mapping(
			"test",
			(
				AccountRule("3123", "46", Side.DEBIT),
				AccountRule("1787", "47", Side.CREDIT),
			),
		)
		rows = reconcile(INVOICED, LEDGER, mapping)
		self.assertEqual(
			compared(rows),
			[
				(PURCHASES, "46", "", d("300.00"), d("300.00")),
				(PURCHASES, "47", "1787", d("57.00"), d("57.00")),
			],
		)

	def test_amounts_are_summed_exactly_and_rounded_to_cents_once(self):
		lines = [shown(SALES, "8400", "100.004"), shown(SALES, "8400", "0.001")]
		(row,) = reconcile(lines, [booked("8400", credit="100.01")], SKR03)
		self.assertEqual(
			(row.register_amount, row.ledger_amount, row.difference), (d("100.01"), d("100.01"), d("0"))
		)

	def test_rows_follow_the_form_each_tax_account_after_its_base(self):
		rows = reconcile(
			INVOICED, (*LEDGER, booked("8300", credit="100.00"), booked("1771", credit="7.00")), SKR03
		)
		self.assertEqual(
			[(row.kennzahl, row.account_number) for row in rows if row.register is SALES],
			[("81", ""), ("", "1776"), ("86", ""), ("", "1771"), ("21", "")],
		)

	def test_a_register_without_an_account_in_the_period_is_not_compared(self):
		rows = reconcile([line for line in INVOICED if line.register is PURCHASES], LEDGER, SKR03, IGNORED)
		self.assertEqual(not_compared(rows)[0], (SALES, Reason.NO_ACCOUNT, d("0"), ()))
		self.assertEqual({row.register for row in rows if row.compared}, {PURCHASES})

	def test_nothing_to_compare_gives_no_row(self):
		self.assertEqual(reconcile([], [], SKR03), ())
		self.assertEqual(
			reconcile([], [booked("1200", debit="10.00"), booked("1600", credit="10.00")], SKR03), ()
		)

	def test_what_cannot_be_compared_is_named_with_its_amount(self):
		lines = (
			*INVOICED,
			shown(SALES, "8336", "700.00", opening=True),
			shown(SALES, "1767", "19.00"),
			shown(SALES, "8603", "40.00"),
			shown(SALES, "3123", "10.00"),
			shown(SALES, "1794", "3.00"),
			shown(SALES, None, "5.00"),
			shown(PURCHASES, "1548", "8.00"),
			shown(PURCHASES, "3400", "200.00"),
			shown(PURCHASES, "3405", "100.00"),
		)
		rows = reconcile(lines, LEDGER, SKR03, IGNORED)
		self.assertEqual(
			not_compared(rows),
			[
				(SALES, Reason.OPENING, d("700.00"), ("8336",)),
				(SALES, Reason.DELIBERATELY_WITHOUT_KENNZAHL, d("19.00"), ("1767",)),
				(SALES, Reason.WATCHED, d("40.00"), ("8603",)),
				(SALES, Reason.OTHER_REGISTER, d("13.00"), ("1794", "3123")),
				(SALES, Reason.NO_NUMBER, d("5.00"), ("Sonderkonto - STB",)),
				(PURCHASES, Reason.DELIBERATELY_WITHOUT_KENNZAHL, d("300.00"), ("3400", "3405")),
				(PURCHASES, Reason.NO_PLACE, d("95.00"), ("4930",)),
				(PURCHASES, Reason.WATCHED, d("8.00"), ("1548",)),
			],
		)
		self.assertTrue(all(row.difference is None for row in rows if not row.compared))

	def test_an_account_on_an_invoice_of_the_other_register_leaves_its_difference_there(self):
		lines = (*INVOICED, shown(SALES, "3123", "10.00"))
		ledger = (*LEDGER, booked("3123", debit="10.00", voucher="Sales Invoice:E"))
		rows = reconcile(lines, ledger, SKR03, IGNORED)
		(base,) = (row for row in rows if row.kennzahl == "46")
		self.assertEqual(
			(base.register_amount, base.ledger_amount, base.difference),
			(d("300.00"), d("310.00"), d("10.00")),
		)

	def test_the_tax_accounts_of_a_verprobung_across_both_registers_are_not_compared(self):
		mapping = Mapping(
			"test",
			(AccountRule("8400", "81", Side.CREDIT), AccountRule("3425", "89", Side.DEBIT)),
			(TaxCheck("gemischt", ("8400", "3425"), ("1776",)),),
		)
		rows = reconcile([shown(SALES, "8400", "100.00"), shown(SALES, "1776", "19.00")], [], mapping)
		self.assertEqual(compared(rows), [(SALES, "81", "", d("100.00"), d("0"))])
		self.assertEqual(not_compared(rows), [(SALES, Reason.OTHER_REGISTER, d("19.00"), ("1776",))])


NAMES = MappingProxyType({"1776": "Umsatzsteuer 19 %"})


class SubjectTest(TestCase):
	def test_a_kennzahl_with_its_label(self):
		row = Row(SALES, d("1"), d("1"), kennzahl="81")
		self.assertEqual(
			subject(row, KENNZAHLEN, NAMES), "Kz 81 Steuerpflichtige Umsätze zum Steuersatz von 19 %"
		)

	def test_a_tax_account_with_its_name_if_known(self):
		self.assertEqual(
			subject(Row(SALES, d("1"), d("1"), account_number="1776"), KENNZAHLEN, NAMES),
			"Konto 1776 Umsatzsteuer 19 %",
		)
		self.assertEqual(
			subject(Row(PURCHASES, d("1"), d("1"), "66", "1576"), KENNZAHLEN, NAMES), "Konto 1576"
		)

	def test_what_is_not_compared_with_its_reason_and_accounts(self):
		row = Row(PURCHASES, d("300"), reason=Reason.DELIBERATELY_WITHOUT_KENNZAHL, accounts=("3400", "3405"))
		self.assertEqual(
			subject(row, KENNZAHLEN, NAMES), f"{Reason.DELIBERATELY_WITHOUT_KENNZAHL.value}: 3400, 3405"
		)
		self.assertEqual(
			subject(Row(SALES, d("0"), reason=Reason.NO_ACCOUNT), KENNZAHLEN, {}), Reason.NO_ACCOUNT.value
		)


class HintsTest(TestCase):
	def test_a_hint_per_row_with_a_difference(self):
		ledger = (*LEDGER, booked("8400", credit="500.00"), booked("1776", credit="95.00"))
		found = hints(reconcile(INVOICED, ledger, SKR03, IGNORED), {"1776": "Umsatzsteuer 19 %"}, FIGURES)
		self.assertEqual(
			[(hint.code, hint.severity) for hint in found], [(Code.REGISTER_DEVIATION, Severity.HINT)] * 2
		)
		self.assertEqual(
			[hint.text for hint in found],
			[
				"Kz 81: Laut Übersicht über den Umsatz (Sales Register) 1.000,00 €, laut Hauptbuch 1.500,00 €; die "
				"Differenz von 500,00 € braucht vor der Abgabe eine Erklärung.",
				"Konto 1776 Umsatzsteuer 19 %: Laut Übersicht über den Umsatz (Sales Register) 190,00 €, laut "
				"Hauptbuch 285,00 €; die Differenz von 95,00 € braucht vor der Abgabe eine Erklärung.",
			],
		)

	def test_names_the_purchase_register_and_a_negative_difference(self):
		found = hints(reconcile((*INVOICED, shown(PURCHASES, "1576", "5.00")), LEDGER, SKR03), {}, FIGURES)
		self.assertEqual(
			[hint.text for hint in found],
			[
				"Konto 1576: Laut Übersicht über Einkäufe (Purchase Register) 100,00 €, laut Hauptbuch 95,00 €; die "
				"Differenz von -5,00 € braucht vor der Abgabe eine Erklärung."
			],
		)

	def test_rows_without_a_difference_and_rows_not_compared_give_no_hint(self):
		lines = (*INVOICED, shown(SALES, "1767", "19.00"))
		self.assertEqual(hints(reconcile(lines, LEDGER, SKR03, IGNORED), {}, FIGURES), [])
