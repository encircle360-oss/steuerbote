from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.defaults import SKR03, SKR04, purchase_rates
from steuerbote.ustva.input_tax import input_tax_hints
from steuerbote.ustva.plausibility import SEVERITIES, Code, Severity

TOLERANCE = Decimal("0.01")
VOUCHER = "Purchase Invoice:ER-0001"


class Figures:
	def money(self, amount: Decimal) -> str:
		return f"{amount:.2f} €"

	def percent(self, value: Decimal) -> str:
		return f"{value} %"


def line(account: str, debit: str = "0", credit: str = "0", voucher: str | None = VOUCHER) -> LedgerLine:
	return LedgerLine(account, Decimal(debit), Decimal(credit), voucher)


def hints(*lines: LedgerLine, mapping=SKR03, tolerance: Decimal = TOLERANCE):
	return input_tax_hints(lines, mapping, purchase_rates(mapping.chart), tolerance, Figures())


class PurchaseRatesTest(TestCase):
	"""The Standardkontenrahmen SKR 03 and SKR 04 of 2026 name the rate of the Vorsteuer of these purchase accounts."""

	def test_skr03_names_7_and_19_percent_with_the_members_of_the_ranges(self):
		rates = purchase_rates("SKR03")
		self.assertEqual(
			{
				number: rates[number]
				for number in ("3010", "3019", "3030", "3091", "3092", "3300", "3309", "3347")
			},
			{
				"3010": Decimal(7),
				"3019": Decimal(7),
				"3030": Decimal(19),
				"3091": Decimal(7),
				"3092": Decimal(19),
				"3300": Decimal(7),
				"3309": Decimal(7),
				"3347": Decimal(7),
			},
		)
		self.assertEqual((rates["3400"], rates["3409"], rates["3418"]), (Decimal(19),) * 3)
		self.assertNotIn("3349", rates)
		self.assertNotIn("3200", rates)

	def test_skr04_names_the_same_accounts_of_its_own_numbers(self):
		rates = purchase_rates("SKR04")
		self.assertEqual(
			{
				number: rates[number]
				for number in ("5110", "5130", "5191", "5192", "5300", "5347", "5400", "5418")
			},
			{
				"5110": Decimal(7),
				"5130": Decimal(19),
				"5191": Decimal(7),
				"5192": Decimal(19),
				"5300": Decimal(7),
				"5347": Decimal(7),
				"5400": Decimal(19),
				"5418": Decimal(19),
			},
		)
		self.assertNotIn("5349", rates)

	def test_a_chart_of_its_own_names_none(self):
		self.assertEqual(dict(purchase_rates("Eigener Kontenrahmen")), {})

	def test_no_purchase_account_has_a_kennzahl(self):
		for mapping in (SKR03, SKR04):
			with self.subTest(chart=mapping.chart):
				self.assertEqual(
					[number for number in purchase_rates(mapping.chart) if mapping.rule_for(number)], []
				)


class InputTaxHintsTest(TestCase):
	def test_19_percent_input_tax_on_a_7_percent_purchase_is_a_warning(self):
		(hint,) = hints(
			line("3300", debit="1000.00"), line("1576", debit="190.00"), line("1600", credit="1190.00")
		)
		self.assertEqual(
			(hint.code, hint.voucher_type, hint.voucher_no),
			(Code.INPUT_TAX_DEVIATION, "Purchase Invoice", "ER-0001"),
		)
		self.assertIs(hint.severity, Severity.WARNING)
		self.assertEqual(
			hint.text,
			"Der Beleg ER-0001 bucht 1000.00 € auf Konto 3300 (7 % Vorsteuer) und 190.00 € Vorsteuer; 7 % wären 70.00 €. "
			"Abziehbar ist nur die gesetzlich geschuldete Steuer, die eine ordnungsgemäße Rechnung ausweist "
			"(§ 15 Abs. 1 Satz 1 Nr. 1 UStG): Bitte prüfen Sie Rechnung und Steuervorlage.",
		)

	def test_the_rate_of_the_account_is_quiet(self):
		self.assertEqual(hints(line("3300", debit="1000.00"), line("1571", debit="70.00")), [])
		self.assertEqual(hints(line("3400", debit="1000.00"), line("1576", debit="190.00")), [])
		self.assertEqual(
			hints(line("5400", debit="1000.00"), line("1406", debit="190.00"), mapping=SKR04), []
		)

	def test_a_tax_rounded_per_item_stays_within_the_tolerance_per_voucher(self):
		items = [line("3400", debit="33.33") for _ in range(3)]
		self.assertEqual(hints(*items, line("1576", debit="18.99")), [])
		self.assertEqual(len(hints(*items, line("1576", debit="18.97"))), 1)
		self.assertEqual(hints(*items, line("1576", debit="18.97"), tolerance=Decimal("0.05")), [])

	def test_two_rates_in_one_voucher_add_up(self):
		self.assertEqual(
			hints(
				line("3300", debit="100.00"),
				line("3400", debit="100.00"),
				line("1571", debit="7.00"),
				line("1576", debit="19.00"),
			),
			[],
		)
		(hint,) = hints(
			line("3300", debit="100.00"), line("3400", debit="100.00"), line("1576", debit="38.00")
		)
		self.assertEqual(
			hint.text,
			"Der Beleg ER-0001 bucht 100.00 € auf Konto 3300 (7 % Vorsteuer), 100.00 € auf Konto 3400 (19 % Vorsteuer) "
			"und 38.00 € Vorsteuer; die Sätze der Konten ergeben 26.00 €. Abziehbar ist nur die gesetzlich geschuldete "
			"Steuer, die eine ordnungsgemäße Rechnung ausweist (§ 15 Abs. 1 Satz 1 Nr. 1 UStG): Bitte prüfen Sie Rechnung "
			"und Steuervorlage.",
		)

	def test_a_purchase_return_is_checked_with_its_sign(self):
		(hint,) = hints(
			line("3300", credit="1000.00"), line("1576", credit="190.00"), line("1600", debit="1190.00")
		)
		self.assertIn("-1000.00 € auf Konto 3300", hint.text)
		self.assertEqual(hints(line("3300", credit="1000.00"), line("1571", credit="70.00")), [])

	def test_a_voucher_with_another_purchase_line_is_not_judged(self):
		"""The tax of a voucher that also books on an account without a rate may belong to that line."""
		self.assertEqual(
			hints(line("3300", debit="1000.00"), line("4900", debit="200.00"), line("1576", debit="228.00")),
			[],
		)

	def test_a_voucher_without_a_purchase_account_with_a_rate_is_not_judged(self):
		self.assertEqual(hints(line("4900", debit="200.00"), line("1576", debit="38.00")), [])

	def test_lines_without_a_voucher_are_not_judged(self):
		self.assertEqual(
			hints(line("3300", debit="1000.00", voucher=None), line("1576", debit="190.00", voucher=None)), []
		)

	def test_a_purchase_without_any_input_tax_is_a_warning_too(self):
		(hint,) = hints(line("3400", debit="1000.00"), line("1600", credit="1000.00"))
		self.assertIn("0.00 € Vorsteuer; 19 % wären 190.00 €", hint.text)

	def test_each_voucher_by_itself_in_the_order_of_its_first_line(self):
		found = hints(
			line("3300", debit="100.00", voucher="Journal Entry:JV-2"),
			line("1576", debit="19.00", voucher="Journal Entry:JV-2"),
			line("3300", debit="1000.00"),
			line("1576", debit="190.00"),
		)
		self.assertEqual(
			[(hint.voucher_type, hint.voucher_no) for hint in found],
			[("Journal Entry", "JV-2"), ("Purchase Invoice", "ER-0001")],
		)

	def test_a_chart_without_purchase_rates_has_no_hints(self):
		self.assertEqual(
			input_tax_hints(
				[line("3300", debit="1000.00"), line("1576", debit="190.00")], SKR03, {}, TOLERANCE, Figures()
			),
			[],
		)

	def test_the_code_is_a_warning(self):
		self.assertIs(SEVERITIES[Code.INPUT_TAX_DEVIATION], Severity.WARNING)
