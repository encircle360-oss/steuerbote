from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.steuerbote.report.ustva_kennzahlen.attribution import (
	COLUMNS,
	SUM_LINES,
	Contribution,
	contributions,
	report_rows,
	vouchers_by_type,
)
from steuerbote.ustva import KENNZAHLEN, AccountRule, LedgerLine, Mapping, Side, TaxCheck, calculate
from steuerbote.ustva.defaults import SKR03, SKR04

ZERO = Decimal("0")


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


BAD_DEBT_MAPPING = Mapping(
	"own",
	(
		AccountRule("8400", "81", Side.CREDIT),
		AccountRule("2406", "81", Side.CREDIT, also_kennzahl="50", also_side=Side.DEBIT),
	),
	(TaxCheck("Umsatzsteuer 19 %", ("8400", "2406"), ("1776",)),),
)


class ContributionsTest(TestCase):
	def test_a_mapped_account_gives_its_balance_per_voucher_to_its_kennzahl(self):
		found = contributions(verified_month(), SKR03)
		self.assertEqual(
			found["81"], [Contribution("81", "Journal Entry:JE-1", ("8400",), d("0"), d("1000"), d("1000"))]
		)
		self.assertEqual(
			found["46"], [Contribution("46", "Journal Entry:JE-4", ("3123",), d("300"), d("0"), d("300"))]
		)
		self.assertEqual(
			found["67"], [Contribution("67", "Journal Entry:JE-4", ("1577",), d("57"), d("0"), d("57"))]
		)

	def test_accounts_without_rule_and_checked_tax_accounts_contribute_nothing(self):
		found = contributions(verified_month(), SKR03)
		accounts = {account for items in found.values() for item in items for account in item.accounts}
		self.assertEqual(accounts, {"8400", "8336", "8338", "3123", "1577", "1576"})

	def test_the_balance_is_taken_on_the_side_of_the_rule(self):
		found = contributions(
			[
				line("8400", credit="100", voucher="Sales Invoice:A"),
				line("8400", debit="30", voucher="Sales Invoice:B"),
			],
			SKR03,
		)
		self.assertEqual([item.amount for item in found["81"]], [d("100"), d("-30")])

	def test_lines_of_one_account_and_voucher_are_summed(self):
		found = contributions(
			[line("8400", credit="600.59", voucher="V"), line("8400", credit="400.40", voucher="V")], SKR03
		)
		self.assertEqual(
			found["81"], [Contribution("81", "V", ("8400",), d("0"), d("1000.99"), d("1000.99"))]
		)

	def test_the_derived_tax_of_a_voucher_comes_from_its_base_and_is_rounded_once(self):
		lines = [line("3123", debit="33.33", voucher=f"V{number}") for number in (1, 2, 3)]
		found = contributions(lines, SKR03)
		self.assertEqual(
			found["47"],
			[
				Contribution("47", f"V{number}", ("3123",), d("33.33"), d("0"), d("6.33"))
				for number in (1, 2, 3)
			],
		)

	def test_accounts_of_one_tax_kennzahl_and_rate_share_one_rounding_per_voucher(self):
		lines = [line("3125", debit="33.33", voucher="V1"), line("3120", debit="33.33", voucher="V1")]
		self.assertEqual(
			contributions(lines, SKR03)["85"],
			[Contribution("85", "V1", ("3125", "3120"), d("66.66"), d("0"), d("12.67"))],
		)

	def test_the_rates_of_one_voucher_are_rounded_separately(self):
		lines = [line("3123", debit="33.33", voucher="V1"), line("3113", debit="33.33", voucher="V1")]
		self.assertEqual(
			[(item.accounts, item.amount) for item in contributions(lines, SKR03)["47"]],
			[(("3123",), d("6.33")), (("3113",), d("2.33"))],
		)

	def test_an_also_kennzahl_takes_the_balance_on_its_own_side(self):
		lines = [
			line("8400", credit="1000", voucher="Sales Invoice:A"),
			line("2406", debit="100", voucher="Journal Entry:B"),
			line("1776", debit="19", voucher="Journal Entry:B"),
		]
		found = contributions(lines, BAD_DEBT_MAPPING)
		self.assertEqual([item.amount for item in found["81"]], [d("1000"), d("-100")])
		self.assertEqual(
			found["50"], [Contribution("50", "Journal Entry:B", ("2406",), d("100"), d("0"), d("100"))]
		)

	def test_lines_without_voucher_form_one_group(self):
		found = contributions([line("8400", credit="10"), line("8400", credit="5")], SKR03)
		self.assertEqual(found["81"], [Contribution("81", None, ("8400",), d("0"), d("15"), d("15"))])

	def test_vouchers_keep_the_order_of_their_first_line(self):
		lines = [
			line("8336", credit="1", voucher="B"),
			line("8400", credit="2", voucher="A"),
			line("8400", credit="3", voucher="B"),
		]
		self.assertEqual([item.voucher for item in contributions(lines, SKR03)["81"]], ["B", "A"])

	def test_lines_can_come_from_a_generator(self):
		found = contributions((line("8400", credit="1", voucher=f"V{n}") for n in range(3)), SKR03)
		self.assertEqual(len(found["81"]), 3)


def busy_month(mapping: Mapping) -> list[LedgerLine]:
	"""Postings on both sides of every account of a mapping, spread over shared vouchers and none."""
	lines = []
	accounts = [rule.account_number for rule in mapping.rules] + [
		account for check in mapping.checks for account in check.tax_accounts
	]
	for index, account in enumerate(accounts):
		lines.append(
			line(account, debit=f"{index * 37 % 997}.{index * 13 % 100:02d}", voucher=f"V{index % 7}")
		)
		lines.append(
			line(account, credit=f"{index * 53 % 991}.{index * 29 % 100:02d}", voucher=f"V{index % 5}")
		)
		if index % 4 == 0:
			lines.append(line(account, credit=f"0.{index % 100:02d}"))
	return lines


class AgreementTest(TestCase):
	"""The vouchers of every Kennzahl add up to the amount the core computes for it."""

	def assert_agrees(self, lines: list[LedgerLine], mapping: Mapping) -> None:
		result = calculate(lines, mapping)
		found = contributions(lines, mapping)
		self.assertGreater(len(found), 1)
		for number in result.values.keys() | found.keys():
			with self.subTest(kennzahl=number):
				if number == "83":
					self.assertNotIn(number, found)
					continue
				total = sum((item.amount for item in found.get(number, ())), ZERO)
				value = result.values.get(number)
				self.assertEqual(total, value.amount if value else ZERO)

	def test_the_verified_month(self):
		self.assert_agrees(verified_month(), SKR03)

	def test_every_rule_of_the_skr03_defaults(self):
		self.assert_agrees(busy_month(SKR03), SKR03)

	def test_every_rule_of_the_skr04_defaults(self):
		self.assert_agrees(busy_month(SKR04), SKR04)

	def test_a_bad_debt_with_its_also_kennzahl(self):
		self.assert_agrees(busy_month(BAD_DEBT_MAPPING), BAD_DEBT_MAPPING)


POSTING_DATES = {f"Journal Entry:JE-{number}": date(2026, 3, number) for number in range(1, 6)}
ACCOUNT_NAMES = {
	"8400": "8400 - Erlöse 19 % USt - STKZ",
	"8336": "8336 - Erlöse sonstige Leistungen EU - STKZ",
	"8338": "8338 - Erlöse Drittland nicht steuerbar - STKZ",
	"3123": "3123 - Sonstige Leistungen EU 19 % - STKZ",
	"1577": "1577 - Vorsteuer nach § 13b UStG 19 % - STKZ",
	"1576": "1576 - Abziehbare Vorsteuer 19 % - STKZ",
}


PARTIES = {"Sales Invoice:SI-1": "Kunde GmbH", "Purchase Invoice:PI-1": "Lieferant AG"}


def rows_of(
	lines: list[LedgerLine],
	mapping: Mapping = SKR03,
	**extra_values: str,
) -> list[dict]:
	extra = {number: Decimal(amount) for number, amount in extra_values.items()}
	return report_rows(
		calculate(lines, mapping, extra_values=extra),
		mapping.catalogue,
		contributions(lines, mapping),
		posting_dates=POSTING_DATES,
		account_names=ACCOUNT_NAMES,
		parties=PARTIES,
		print_label="Drucken",
		currency="EUR",
	)


class ReportRowsTest(TestCase):
	def test_kennzahlen_vouchers_and_sums_follow_the_form(self):
		self.assertEqual(
			[
				(row["indent"], row["kennzahl"], row["line"], row["voucher_no"])
				for row in rows_of(verified_month())
			],
			[
				(0, "81", 13, None),
				(1, "81", None, "JE-1"),
				(0, "46", 30, None),
				(1, "46", None, "JE-4"),
				(0, "47", 30, None),
				(1, "47", None, "JE-4"),
				(0, "21", 35, None),
				(1, "21", None, "JE-2"),
				(0, "45", 36, None),
				(1, "45", None, "JE-3"),
				(0, None, 37, None),
				(0, "66", 38, None),
				(1, "66", None, "JE-5"),
				(0, "67", 41, None),
				(1, "67", None, "JE-4"),
				(0, None, 45, None),
				(0, None, 48, None),
				(0, "83", 50, None),
			],
		)

	def test_a_kennzahl_row_carries_the_form_label_and_both_amounts(self):
		rows = rows_of([line("8400", credit="1000.99", voucher="Journal Entry:JE-1")])
		self.assertEqual(
			rows[0],
			{
				"kennzahl": "81",
				"line": 13,
				"label": KENNZAHLEN["81"].label,
				"posting_date": None,
				"voucher_type": None,
				"voucher_no": None,
				"print_link": None,
				"party": None,
				"account": None,
				"debit": None,
				"credit": None,
				"amount": d("1000.99"),
				"reported": d("1000"),
				"indent": 0,
				"parent_kennzahl": None,
				"bold": 1,
				"currency": "EUR",
			},
		)

	def test_a_voucher_row_names_its_voucher_account_and_postings(self):
		rows = rows_of(verified_month())
		self.assertEqual(
			rows[5],
			{
				"kennzahl": "47",
				"line": None,
				"label": None,
				"posting_date": date(2026, 3, 4),
				"voucher_type": "Journal Entry",
				"voucher_no": "JE-4",
				"print_link": '<a href="/printview?doctype=Journal%20Entry&amp;name=JE-4" target="_blank">Drucken</a>',
				"party": None,
				"account": ACCOUNT_NAMES["3123"],
				"debit": d("300"),
				"credit": d("0"),
				"amount": d("57.00"),
				"reported": None,
				"indent": 1,
				"parent_kennzahl": "47",
				"bold": 0,
				"currency": "EUR",
			},
		)

	def test_the_sums_of_the_form_and_kz_83_carry_the_amounts_as_reported(self):
		rows = {row["line"]: row for row in rows_of(verified_month()) if row["indent"] == 0}
		self.assertEqual(
			[
				(rows[number]["label"], rows[number]["amount"], rows[number]["reported"])
				for number in (37, 45, 48)
			],
			[
				(label, None, d(amount))
				for (_, label, _), amount in zip(SUM_LINES, ("247.00", "95.00", "95.00"), strict=True)
			],
		)
		self.assertEqual((rows[50]["amount"], rows[50]["reported"]), (d("95.00"), d("95.00")))

	def test_the_sondervorauszahlung_is_a_kennzahl_without_vouchers(self):
		rows = rows_of([], **{"39": "1200.00"})
		self.assertEqual(
			[(row["kennzahl"], row["line"], row["amount"], row["reported"]) for row in rows],
			[
				(None, 37, None, d("0.00")),
				(None, 45, None, d("0.00")),
				(None, 48, None, d("0.00")),
				("39", 49, d("1200.00"), d("1200.00")),
				("83", 50, d("-1200.00"), d("-1200.00")),
			],
		)

	def test_a_kennzahl_whose_vouchers_cancel_out_still_shows_them(self):
		rows = rows_of(
			[
				line("8400", credit="100", voucher="Journal Entry:JE-1"),
				line("8400", debit="100", voucher="Journal Entry:JE-2"),
			]
		)
		self.assertEqual(
			[(row["kennzahl"], row["amount"], row["reported"]) for row in rows[:3]],
			[("81", d("0"), d("0")), ("81", d("100"), None), ("81", d("-100"), None)],
		)

	def test_a_derived_tax_from_several_accounts_lists_their_numbers(self):
		voucher = "Purchase Invoice:PI-1"
		rows = rows_of(
			[line("3125", debit="33.33", voucher=voucher), line("3120", debit="33.33", voucher=voucher)]
		)
		tax = next(row for row in rows if row["parent_kennzahl"] == "85")
		self.assertEqual(
			(
				tax["account"],
				tax["label"],
				tax["voucher_type"],
				tax["voucher_no"],
				tax["debit"],
				tax["amount"],
			),
			(None, "3125, 3120", "Purchase Invoice", "PI-1", d("66.66"), d("12.67")),
		)

	def test_an_account_without_known_name_shows_its_number(self):
		rows = rows_of([line("8401", credit="10", voucher="Journal Entry:JE-1")])
		self.assertEqual((rows[1]["account"], rows[1]["label"]), (None, "8401"))

	def test_lines_without_voucher_show_no_voucher(self):
		rows = rows_of([line("8400", credit="10")])
		self.assertEqual(
			(
				rows[1]["posting_date"],
				rows[1]["voucher_type"],
				rows[1]["voucher_no"],
				rows[1]["print_link"],
				rows[1]["party"],
			),
			(None, "", "", None, None),
		)

	def test_an_invoice_names_its_customer_or_supplier(self):
		rows = rows_of(
			[
				line("8400", credit="100", voucher="Sales Invoice:SI-1"),
				line("8400", credit="50", voucher="Journal Entry:JE-1"),
				line("1576", debit="19", voucher="Purchase Invoice:PI-1"),
			]
		)
		self.assertEqual(
			[(row["voucher_no"], row["party"]) for row in rows if row["indent"]],
			[("SI-1", "Kunde GmbH"), ("JE-1", None), ("PI-1", "Lieferant AG")],
		)

	def test_the_link_to_the_print_view_escapes_voucher_and_label(self):
		voucher = "Sales Invoice:SI/2026&<1>"
		rows = report_rows(
			calculate([line("8400", credit="100", voucher=voucher)], SKR03),
			SKR03.catalogue,
			contributions([line("8400", credit="100", voucher=voucher)], SKR03),
			posting_dates={},
			account_names={},
			parties={},
			print_label='Drucken & "Vorschau"',
			currency="EUR",
		)
		self.assertEqual(
			rows[1]["print_link"],
			'<a href="/printview?doctype=Sales%20Invoice&amp;name=SI%2F2026%26%3C1%3E" target="_blank">'
			"Drucken &amp; &quot;Vorschau&quot;</a>",
		)

	def test_every_row_has_every_column(self):
		for row in rows_of(verified_month()):
			self.assertLessEqual(set(COLUMNS), row.keys())


class VouchersByTypeTest(TestCase):
	def test_groups_the_voucher_names_of_the_wanted_types(self):
		vouchers = [
			"Sales Invoice:SI-2",
			"Journal Entry:JE-1",
			"Sales Invoice:SI-1",
			None,
			"Purchase Invoice:PI-1",
			"Sales Invoice:SI-2",
		]
		self.assertEqual(
			vouchers_by_type(vouchers, ("Sales Invoice", "Purchase Invoice")),
			{"Sales Invoice": ["SI-1", "SI-2"], "Purchase Invoice": ["PI-1"]},
		)

	def test_without_vouchers_of_the_types_there_is_nothing_to_read(self):
		self.assertEqual(vouchers_by_type(["Journal Entry:JE-1", None], ("Sales Invoice",)), {})
