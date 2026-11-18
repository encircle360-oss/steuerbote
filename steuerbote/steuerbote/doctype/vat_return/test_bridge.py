from decimal import Decimal
from unittest import TestCase

from steuerbote.steuerbote.doctype.vat_return import bridge
from steuerbote.ustva import KENNZAHLEN, LedgerLine, Period, calculate
from steuerbote.ustva.defaults import SKR03


def d(value: str) -> Decimal:
	return Decimal(value)


def line(account: str, debit: str = "0", credit: str = "0", voucher: str | None = None) -> LedgerLine:
	return LedgerLine(account, Decimal(debit), Decimal(credit), voucher)


def verified_month() -> list[LedgerLine]:
	"""The month of VerifiedMonthTest in the core, booked as five journal entries."""
	return [
		line("1400", debit="1190", voucher="Journal Entry:JE-1"),
		line("8400", credit="1000", voucher="Journal Entry:JE-1"),
		line("1776", credit="190", voucher="Journal Entry:JE-1"),
		line("1400", debit="2000", voucher="Journal Entry:JE-2"),
		line("8336", credit="2000", voucher="Journal Entry:JE-2"),
		line("1400", debit="500", voucher="Journal Entry:JE-3"),
		line("8338", credit="500", voucher="Journal Entry:JE-3"),
		line("3123", debit="300", voucher="Journal Entry:JE-4"),
		line("1577", debit="57", voucher="Journal Entry:JE-4"),
		line("1787", credit="57", voucher="Journal Entry:JE-4"),
		line("1200", credit="300", voucher="Journal Entry:JE-4"),
		line("1576", debit="95", voucher="Journal Entry:JE-5"),
		line("1200", credit="95", voucher="Journal Entry:JE-5"),
	]


class SondervorauszahlungTest(TestCase):
	def test_is_deducted_in_december_with_dauerfrist(self):
		values = bridge.sondervorauszahlung_values(Period.month(2026, 12), True, d("1200.00"))
		self.assertEqual(values, {"39": d("1200.00")})

	def test_is_deducted_in_the_fourth_quarter_with_dauerfrist(self):
		values = bridge.sondervorauszahlung_values(Period.quarter(2026, 4), True, d("300.00"))
		self.assertEqual(values, {"39": d("300.00")})

	def test_is_not_deducted_before_the_last_period_of_the_year(self):
		self.assertEqual(bridge.sondervorauszahlung_values(Period.month(2026, 11), True, d("1200")), {})
		self.assertEqual(bridge.sondervorauszahlung_values(Period.quarter(2026, 3), True, d("1200")), {})

	def test_is_not_deducted_without_dauerfrist(self):
		self.assertEqual(bridge.sondervorauszahlung_values(Period.month(2026, 12), False, d("1200")), {})

	def test_nothing_is_deducted_without_an_amount(self):
		self.assertEqual(bridge.sondervorauszahlung_values(Period.month(2026, 12), True, d("0")), {})


class KennzahlRowsTest(TestCase):
	def setUp(self):
		self.result = calculate(verified_month(), SKR03)

	def test_one_row_per_reported_kennzahl_in_the_order_of_the_form(self):
		rows = bridge.kennzahl_rows(self.result, KENNZAHLEN, {})
		self.assertEqual([row["kennzahl"] for row in rows], ["81", "46", "47", "21", "45", "66", "67", "83"])

	def test_a_row_describes_its_kennzahl_and_carries_amount_and_reported_value(self):
		row = bridge.kennzahl_rows(self.result, KENNZAHLEN, {})[0]
		self.assertEqual(
			row,
			{
				"kennzahl": "81",
				"line": 13,
				"label": KENNZAHLEN["81"].label,
				"kind": "base",
				"amount": d("1000"),
				"reported": d("1000"),
				"override": d("0"),
				"override_reason": "",
			},
		)

	def test_overrides_are_kept(self):
		overrides = {"45": bridge.Override(d("600.00"), "Correction from the Steuerberatung")}
		row = next(
			row for row in bridge.kennzahl_rows(self.result, KENNZAHLEN, overrides) if row["kennzahl"] == "45"
		)
		self.assertEqual((row["reported"], row["override"]), (d("500"), d("600.00")))
		self.assertEqual(row["override_reason"], "Correction from the Steuerberatung")

	def test_an_override_without_a_ledger_amount_gets_a_row_of_its_own(self):
		overrides = {"43": bridge.Override(d("250.00"), "Export without booking")}
		rows = bridge.kennzahl_rows(self.result, KENNZAHLEN, overrides)
		self.assertEqual([row["kennzahl"] for row in rows][:3], ["81", "43", "46"])
		row = rows[1]
		self.assertEqual((row["amount"], row["reported"], row["override"]), (d("0"), d("0"), d("250.00")))


class OverridesOfTest(TestCase):
	def test_rows_with_a_reason_override(self):
		rows = [
			{"kennzahl": "81", "reported": 1000, "override": 1100, "override_reason": "Late invoice"},
			{"kennzahl": "45", "reported": 500, "override": 0, "override_reason": ""},
		]
		self.assertEqual(
			bridge.overrides_of(rows, KENNZAHLEN), {"81": bridge.Override(d("1100.00"), "Late invoice")}
		)

	def test_an_override_without_a_reason_is_refused(self):
		rows = [{"kennzahl": "81", "override": 1100, "override_reason": "  "}]
		with self.assertRaises(bridge.RowError) as raised:
			bridge.overrides_of(rows, KENNZAHLEN)
		self.assertEqual(
			(raised.exception.problem, raised.exception.kennzahl), (bridge.RowProblem.MISSING_REASON, "81")
		)


class FilingTest(TestCase):
	def setUp(self):
		self.rows = bridge.kennzahl_rows(calculate(verified_month(), SKR03), KENNZAHLEN, {})

	def row(self, kennzahl: str) -> dict:
		return next(row for row in self.rows if row["kennzahl"] == kennzahl)

	def finals(self, filing: bridge.Filing) -> dict[str, Decimal]:
		return {row["kennzahl"]: row["final"] for row in filing.rows}

	def test_without_overrides_the_reported_amounts_are_filed(self):
		filing = bridge.filing(self.rows, 2026)
		self.assertEqual(self.finals(filing), {row["kennzahl"]: row["reported"] for row in self.rows})
		self.assertEqual(
			filing.totals,
			{
				"output_tax": d("247.00"),
				"input_tax": d("152.00"),
				"other_tax": d("0.00"),
				"sondervorauszahlung": d("0.00"),
				"kz83": d("95.00"),
			},
		)

	def test_an_override_with_a_reason_replaces_the_amount_and_the_sums_follow(self):
		self.row("81").update({"override": 1100.0, "override_reason": "Invoice booked in April"})
		filing = bridge.filing(self.rows, 2026)
		self.assertEqual(self.finals(filing)["81"], d("1100"))
		self.assertEqual(filing.totals["output_tax"], d("266.00"))
		self.assertEqual(filing.totals["kz83"], d("114.00"))
		self.assertEqual(self.finals(filing)["83"], d("114.00"))

	def test_an_overridden_base_is_filed_in_full_euros(self):
		self.row("81").update({"override": "1100.75", "override_reason": "Invoice booked in April"})
		filing = bridge.filing(self.rows, 2026)
		self.assertEqual(self.finals(filing)["81"], d("1100"))
		self.assertEqual(filing.totals["kz83"], d("114.00"))

	def test_an_override_to_zero_needs_only_the_reason(self):
		self.row("45").update({"override": 0, "override_reason": "Not a turnover of this company"})
		self.assertEqual(self.finals(bridge.filing(self.rows, 2026))["45"], d("0"))

	def test_rows_are_described_from_the_catalogue(self):
		rows = [{"kennzahl": " 43 ", "override": 250, "override_reason": "Export without booking"}]
		filing = bridge.filing(rows, 2026)
		self.assertEqual(
			filing.rows,
			(
				{
					"kennzahl": "43",
					"line": 22,
					"label": KENNZAHLEN["43"].label,
					"kind": "base",
					"final": d("250"),
				},
			),
		)

	def test_the_sondervorauszahlung_reduces_kz_83(self):
		rows = [{"kennzahl": "39", "reported": 1200.0}, {"kennzahl": "83", "reported": -1200.0}]
		filing = bridge.filing(rows, 2026)
		self.assertEqual(filing.totals["sondervorauszahlung"], d("1200.00"))
		self.assertEqual(self.finals(filing), {"39": d("1200.00"), "83": d("-1200.00")})

	def test_a_return_without_rows_owes_nothing(self):
		filing = bridge.filing([], 2026)
		self.assertEqual(filing.rows, ())
		self.assertEqual(filing.totals["kz83"], d("0.00"))

	def test_missing_values_read_as_zero(self):
		filing = bridge.filing(
			[{"kennzahl": "66", "reported": None, "override": None, "override_reason": None}], 2026
		)
		self.assertEqual(filing.totals["input_tax"], d("0.00"))

	def test_refused_rows(self):
		cases = {
			"unknown Kennzahl": ({"kennzahl": "99"}, bridge.RowProblem.UNKNOWN, "99"),
			"empty Kennzahl": ({"kennzahl": None}, bridge.RowProblem.UNKNOWN, ""),
			"flag": ({"kennzahl": "10"}, bridge.RowProblem.NO_AMOUNT, "10"),
			"override of Kz 83": (
				{"kennzahl": "83", "override": 1, "override_reason": "x"},
				bridge.RowProblem.COMPUTED,
				"83",
			),
			"reason on Kz 83": ({"kennzahl": "83", "override_reason": "x"}, bridge.RowProblem.COMPUTED, "83"),
			"override without reason": (
				{"kennzahl": "81", "override": 5},
				bridge.RowProblem.MISSING_REASON,
				"81",
			),
		}
		for case, (row, problem, kennzahl) in cases.items():
			with self.subTest(case), self.assertRaises(bridge.RowError) as raised:
				bridge.filing([row], 2026)
			self.assertEqual((raised.exception.problem, raised.exception.kennzahl), (problem, kennzahl))

	def test_a_kennzahl_listed_twice_is_refused(self):
		with self.assertRaises(bridge.RowError) as raised:
			bridge.filing([{"kennzahl": "45"}, {"kennzahl": "45 "}], 2026)
		self.assertEqual(raised.exception.problem, bridge.RowProblem.DUPLICATE)


class CheckRowsTest(TestCase):
	def setUp(self):
		self.rows = bridge.check_rows(calculate(verified_month(), SKR03))

	def test_one_row_per_check_of_the_mapping_in_its_order(self):
		self.assertEqual([row["label"] for row in self.rows], [check.label for check in SKR03.checks])

	def test_a_row_carries_the_totals_of_its_check(self):
		rows = {row["label"]: row for row in self.rows}
		self.assertEqual(
			rows["Umsatzsteuer 19 %"],
			{
				"label": "Umsatzsteuer 19 %",
				"computed_tax": d("190.00"),
				"booked_tax": d("190.00"),
				"difference": d("0.00"),
				"deviations": 0,
				"passed": 1,
			},
		)
		self.assertEqual(
			(
				rows["Umsatzsteuer nach § 13b UStG 19 %"]["computed_tax"],
				rows["Umsatzsteuer 7 %"]["computed_tax"],
			),
			(d("57.00"), d("0.00")),
		)


class DeviationRowsTest(TestCase):
	def setUp(self):
		lines = [
			line("8400", credit="1000", voucher="Journal Entry:ACC-JV-2026-00007"),
			line("1776", credit="180", voucher="Journal Entry:ACC-JV-2026-00007"),
			line("8400", credit="100"),
			line("1776", credit="19"),
		]
		self.result = calculate(lines, SKR03)

	def test_one_row_per_deviating_voucher(self):
		self.assertEqual(
			bridge.deviation_rows(self.result)[0],
			{
				"check_label": "Umsatzsteuer 19 %",
				"voucher_type": "Journal Entry",
				"voucher_no": "ACC-JV-2026-00007",
				"computed_tax": d("190.00"),
				"booked_tax": d("180.00"),
				"difference": d("-10.00"),
			},
		)
		self.assertEqual(bridge.check_rows(self.result)[0]["deviations"], 1)
		self.assertEqual(bridge.check_rows(self.result)[0]["passed"], 0)

	def test_lines_without_voucher_deviate_without_voucher_type_and_number(self):
		result = calculate([line("8400", credit="100"), line("1776", credit="10")], SKR03)
		row = bridge.deviation_rows(result)[0]
		self.assertEqual((row["voucher_type"], row["voucher_no"]), ("", ""))

	def test_the_voucher_name_keeps_everything_after_the_first_colon(self):
		self.assertEqual(bridge.split_voucher("Journal Entry:JV:1"), ("Journal Entry", "JV:1"))


class UnmappedRowsTest(TestCase):
	def test_watched_accounts_with_a_balance_and_their_totals(self):
		lines = [
			line("1548", debit="50", voucher="Journal Entry:JE-1"),
			line("1548", debit="20", credit="5", voucher="Journal Entry:JE-2"),
			line("1200", credit="65", voucher="Journal Entry:JE-2"),
			line("1725", debit="10", credit="10", voucher="Journal Entry:JE-3"),
		]
		result = calculate(lines, SKR03)
		self.assertEqual(
			bridge.unmapped_rows(result, lines, {"1548": "1548 - Vorsteuer im Folgejahr - STVA"}),
			[
				{
					"account_number": "1548",
					"account": "1548 - Vorsteuer im Folgejahr - STVA",
					"debit": d("70"),
					"credit": d("5"),
				}
			],
		)

	def test_an_account_without_name_keeps_its_number(self):
		lines = [line("1548", debit="50")]
		row = bridge.unmapped_rows(calculate(lines, SKR03), lines, {})[0]
		self.assertEqual((row["account_number"], row["account"]), ("1548", ""))


class ToAmountTest(TestCase):
	def test_values_of_currency_fields_become_cents(self):
		for value, expected in (
			(95.0, "95.00"),
			("1100.75", "1100.75"),
			(0.1, "0.10"),
			(None, "0.00"),
			(d("7"), "7.00"),
		):
			with self.subTest(value=value):
				self.assertEqual(str(bridge.to_amount(value)), expected)
