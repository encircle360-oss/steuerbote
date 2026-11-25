import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from steuerbote.elster import ustva_xml
from steuerbote.steuerbote.doctype.vat_return import bridge
from steuerbote.steuerbote.report.ustva_kennzahlen import comparison
from steuerbote.ustva import (
	DEFAULT_STATUTORY_TAX,
	KENNZAHLEN,
	LedgerLine,
	Period,
	StatutoryTax,
	calculate,
	plausibility,
	registers,
)
from steuerbote.ustva.defaults import SKR03
from steuerbote.ustva.tests.test_plausibility import FIGURES
from steuerbote.vatid.result import Outcome

BOOKED = StatutoryTax.AS_BOOKED
FROM_BASE = StatutoryTax.FROM_BASE


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

	def test_the_sondervorauszahlung_2027_is_deducted_in_december_2027(self):
		values = bridge.sondervorauszahlung_values(Period.month(2027, 12), True, d("4000.00"))
		self.assertEqual(values, {"39": d("4000.00")})
		filing = bridge.filing([{"kennzahl": "39", "reported": 4000.0}, {"kennzahl": "83"}], 2027)
		self.assertEqual(
			(filing.totals["sondervorauszahlung"], filing.totals["kz83"]), (d("4000.00"), d("-4000.00"))
		)


class ProvisionalFormsTest(TestCase):
	"""What the documents and prints of a provisional year say of its forms (steuerbote/ustva/years.py)."""

	def test_2027_takes_the_beta_45_1_5_0_and_the_form_of_2026(self):
		self.assertEqual(
			bridge.provisional_forms(2027), {"documentation": "Beta ERiC 45.1.5.0", "form_year": 2026}
		)

	def test_a_final_year_and_a_year_without_data_have_none(self):
		self.assertIsNone(bridge.provisional_forms(2026))
		self.assertIsNone(bridge.provisional_forms(2099))


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
				"tax": d("190.00"),
				"override": d("0"),
				"override_reason": "",
				"override_basis": d("0"),
			},
		)

	def test_an_override_keeps_the_ledger_amount_it_was_made_against(self):
		overrides = {
			"45": bridge.Override(d("600.00"), "Steuerberatung"),
			"81": bridge.Override(d("1100.00"), "Steuerberatung", d("900.00")),
		}
		rows = {row["kennzahl"]: row for row in bridge.kennzahl_rows(self.result, KENNZAHLEN, overrides)}
		self.assertEqual(
			(rows["45"]["override_basis"], rows["81"]["override_basis"]), (d("500"), d("900.00"))
		)

	def test_a_kennzahl_without_a_tax_at_a_statutory_rate_carries_none(self):
		rows = bridge.kennzahl_rows(self.result, KENNZAHLEN, {})
		self.assertEqual({row["kennzahl"]: row["tax"] for row in rows if row["tax"]}, {"81": d("190.00")})

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


class OverrideBasisTest(TestCase):
	"""An override is made against the ledger amount of its Kennzahl. When the ledger books another amount later, the
	override would hide the change from the return; the hint KORREKTUR-UEBERHOLT holds it until the override is
	confirmed or removed."""

	STORED = (
		{
			"kennzahl": "81",
			"amount": 1000,
			"override": 1100,
			"override_reason": "Spät",
			"override_basis": 900,
		},
		{"kennzahl": "41", "amount": 2000.5},
	)

	def test_an_override_reads_its_basis(self):
		rows = [
			{"kennzahl": "81", "override": 1100, "override_reason": "Spät", "override_basis": 900},
			{"kennzahl": "45", "override": 0, "override_reason": "Steuerberatung"},
		]
		self.assertEqual(
			[override.basis for override in bridge.overrides_of(rows, KENNZAHLEN).values()],
			[d("900.00"), None],
		)

	def test_a_save_keeps_the_basis_of_an_unchanged_override_and_sets_that_of_a_new_one(self):
		rows = [
			{"kennzahl": "81", "override": 1100, "override_reason": " Spät ", "override_basis": 5},
			{"kennzahl": "41", "override": 2100, "override_reason": "Steuerberatung"},
			{"kennzahl": "43", "override": 250, "override_reason": "Ausfuhr"},
			{"kennzahl": "86"},
		]
		self.assertEqual(bridge.override_bases(self.STORED, rows), [d("900.00"), d("2000.50"), None, None])
		changed = [{"kennzahl": "81", "override": 1200, "override_reason": "Spät"}]
		self.assertEqual(bridge.override_bases(self.STORED, changed), [d("1000.00")])

	def test_a_hint_names_each_override_whose_ledger_amount_changed(self):
		rows = [
			{
				"kennzahl": "81",
				"amount": 1300,
				"override": 1100,
				"override_reason": "Spät",
				"override_basis": 900,
			},
			{
				"kennzahl": "41",
				"amount": 2000,
				"override": 2100,
				"override_reason": "x",
				"override_basis": 2000,
			},
			{"kennzahl": "86", "amount": 50},
		]
		(hint,) = bridge.stale_override_hints(rows, FIGURES)
		self.assertEqual(
			(hint.code, hint.severity), (plausibility.Code.OVERRIDE_STALE, plausibility.Severity.ERROR)
		)
		self.assertEqual(
			hint.text,
			"Kz 81: Die Korrektur auf 1.100,00 € wurde bei 900,00 € im Hauptbuch eingetragen; das Hauptbuch bucht "
			"jetzt 1.300,00 €. Die Voranmeldung ist nicht bereit, bis die Korrektur bestätigt ist: Passe Betrag oder "
			"Begründung an, oder lösche die Korrektur.",
		)


class ReadyOfTest(TestCase):
	"""A return is ready when every Verprobung passes, no watched account has a balance, no error among the hints
	holds it and its forms are final."""

	PASSED = ({"passed": 1}, {"passed": 1})

	def test_ready_from_the_stored_tables(self):
		self.assertTrue(bridge.ready_of(self.PASSED, [], [{"severity": "Warnung"}], provisional=False))
		self.assertFalse(bridge.ready_of([{"passed": 1}, {"passed": 0}], [], [], provisional=False))
		self.assertFalse(bridge.ready_of(self.PASSED, [{"account_number": "1590"}], [], provisional=False))
		self.assertFalse(bridge.ready_of(self.PASSED, [], [{"severity": "Fehler"}], provisional=False))
		self.assertFalse(bridge.ready_of(self.PASSED, [], [], provisional=True))


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


def stored_rows() -> list[dict]:
	"""The Kennzahlen of the verified month as Berechnen stores them, each row with the name Frappe gives it."""
	rows = bridge.kennzahl_rows(calculate(verified_month(), SKR03), KENNZAHLEN, {})
	return [{**row, "name": f"row-{index}"} for index, row in enumerate(rows)]


def stored_return(rows: list[dict]) -> dict:
	"""A return as validate leaves it: the final amount of each row and the sums of the form over them."""
	filing = bridge.filing(rows, 2026)
	return {
		"kennzahlen": [{**row, **filed} for row, filed in zip(rows, filing.rows, strict=True)],
		**filing.totals,
	}


class RestoredTest(TestCase):
	"""Frappe keeps no read-only field from a save through its API: a save keeps the Kennzahlen and amounts Berechnen
	computed and takes no more from its rows than the overrides."""

	def setUp(self):
		self.stored = stored_rows()

	def test_a_row_keeps_the_kennzahl_and_the_amounts_berechnen_stored(self):
		sent = [dict(row) for row in self.stored]
		sent[0].update(
			{"kennzahl": "86", "amount": 10, "reported": 10, "override": 1100, "override_reason": "x"}
		)
		kept = bridge.restored(self.stored, sent)
		self.assertEqual(
			kept[0],
			{
				"name": "row-0",
				"kennzahl": "81",
				"amount": d("1000.00"),
				"reported": d("1000.00"),
				"tax": d("190.00"),
			},
		)
		self.assertEqual(
			[(row["name"], row["kennzahl"]) for row in kept],
			[(row["name"], row["kennzahl"]) for row in self.stored],
		)

	def test_a_row_the_save_adds_only_overrides(self):
		added = [
			{"kennzahl": " 43 ", "amount": 99, "reported": 99, "override": 250, "override_reason": "Export"},
			{"name": "forged", "kennzahl": "86", "amount": 500, "reported": 500, "tax": 35},
		]
		kept = bridge.restored(self.stored, [*self.stored, *added])
		self.assertEqual(
			kept[-2:],
			[
				{"name": None, "kennzahl": "43", "amount": d("0"), "reported": d("0"), "tax": d("0")},
				{"name": None, "kennzahl": "86", "amount": d("0"), "reported": d("0"), "tax": d("0")},
			],
		)

	def test_a_row_berechnen_computed_stays_on_the_return(self):
		for number in ("81", "83"):
			sent = [row for row in self.stored if row["kennzahl"] != number]
			with self.subTest(kennzahl=number), self.assertRaises(bridge.RowError) as raised:
				bridge.restored(self.stored, sent)
			self.assertEqual(
				(raised.exception.problem, raised.exception.kennzahl), (bridge.RowProblem.REMOVED, number)
			)

	def test_kz83_stays_without_an_amount_as_well(self):
		stored = [{"name": "row-0", "kennzahl": "83", "amount": 0.0, "reported": 0.0}]
		with self.assertRaises(bridge.RowError) as raised:
			bridge.restored(stored, [])
		self.assertEqual(raised.exception.kennzahl, "83")

	def test_a_row_that_only_overrides_can_be_removed(self):
		override = {
			"name": "row-9",
			"kennzahl": "43",
			"amount": 0.0,
			"reported": 0.0,
			"override": 250.0,
			"override_reason": "Export",
		}
		kept = bridge.restored([*self.stored, override], self.stored)
		self.assertEqual([row["name"] for row in kept], [row["name"] for row in self.stored])


class AmountsKeptTest(TestCase):
	"""Before a filing, the amounts the return holds are computed again from its rows."""

	def setUp(self):
		self.rows = stored_rows()
		self.stored = stored_return(self.rows)

	def test_a_return_holds_what_its_rows_give(self):
		self.assertTrue(bridge.amounts_kept(self.rows, self.stored, 2026))

	def test_a_sum_or_a_final_amount_changed_past_the_save_is_found(self):
		changes = {
			"kz83": lambda stored: stored.update({"kz83": 1.9}),
			"output_tax": lambda stored: stored.update({"output_tax": 0}),
			"final": lambda stored: stored["kennzahlen"][0].update({"final": 10}),
			"row": lambda stored: stored["kennzahlen"].pop(0),
		}
		for case, change in changes.items():
			stored = stored_return(self.rows)
			change(stored)
			with self.subTest(case):
				self.assertFalse(bridge.amounts_kept(self.rows, stored, 2026))

	def test_rows_that_differ_from_the_stored_return_are_found(self):
		changed = [dict(row) for row in self.rows]
		changed[0].update({"override": 1100, "override_reason": "Invoice booked in April"})
		self.assertFalse(bridge.amounts_kept(changed, self.stored, 2026))
		self.assertTrue(bridge.amounts_kept(changed, stored_return(changed), 2026))


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
				"derived_base": d("0"),
			},
		)
		self.assertEqual(
			(
				rows["Umsatzsteuer nach § 13b UStG 19 %"]["computed_tax"],
				rows["Umsatzsteuer 7 %"]["computed_tax"],
			),
			(d("57.00"), d("0.00")),
		)


class DerivedBaseRowTest(TestCase):
	def test_a_check_row_carries_the_base_derived_from_vouchers_without_base_account(self):
		lines = [
			line("4980", debit="1000", voucher="Journal Entry:JE-1"),
			line("1577", debit="190", voucher="Journal Entry:JE-1"),
			line("1787", credit="190", voucher="Journal Entry:JE-1"),
		]
		rows = {row["label"]: row for row in bridge.check_rows(calculate(lines, SKR03))}
		self.assertEqual(rows["Umsatzsteuer nach § 13b UStG 19 %"]["derived_base"], d("1000.00"))
		self.assertEqual(rows["Umsatzsteuer nach § 13b UStG 19 %"]["passed"], 1)


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


SETTINGS_DOCTYPE = Path(__file__).parents[1] / "vat_return_settings" / "vat_return_settings.json"
SETTINGS = {
	"company": "Beispiel GmbH",
	"elster_tax_number": "9123045678901",
	"filer_name": None,
	"street": "Hauptstraße 1",
	"postal_code": "80331",
	"city": "München",
	"phone": None,
	"email": None,
	"wid_nr": None,
}


class FilerTest(TestCase):
	def test_takes_the_steuernummer_and_the_datenlieferant_from_the_settings(self):
		filer = bridge.filer(
			{**SETTINGS, "phone": "089 1234567", "email": "erika@example.org", "wid_nr": "DE123456789"}
		)
		self.assertEqual(
			(filer.steuernummer, filer.name, filer.street, filer.postal_code, filer.city),
			("9123045678901", "Beispiel GmbH", "Hauptstraße 1", "80331", "München"),
		)
		self.assertEqual(
			(filer.phone, filer.email, filer.wid_nr), ("089 1234567", "erika@example.org", "DE123456789")
		)

	def test_without_a_name_of_its_own_the_datenlieferant_is_the_company(self):
		self.assertEqual(bridge.filer(SETTINGS).name, "Beispiel GmbH")
		self.assertEqual(
			bridge.filer({**SETTINGS, "filer_name": "Beispiel Holding"}).name, "Beispiel Holding"
		)

	def test_a_missing_street_is_refused(self):
		with self.assertRaises(ustva_xml.XmlError) as raised:
			bridge.filer({**SETTINGS, "street": None})
		self.assertEqual(raised.exception.label, ustva_xml.STREET_LABEL)

	def test_the_settings_hold_each_part_of_the_datenlieferant_as_long_as_elster_takes_it(self):
		definition = json.loads(SETTINGS_DOCTYPE.read_text(encoding="utf-8"))
		lengths = {field["fieldname"]: field.get("length") for field in definition["fields"]}
		self.assertEqual(set(bridge.DATENLIEFERANT_FIELDS), set(ustva_xml.DATENLIEFERANT))
		for attribute, fieldname in bridge.DATENLIEFERANT_FIELDS.items():
			with self.subTest(field=fieldname):
				self.assertEqual(lengths[fieldname], ustva_xml.DATENLIEFERANT[attribute].length)
		self.assertEqual(lengths["wid_nr"], len("DE123456789"))


# The company, its address and its contact as datenlieferant_defaults takes them, invented.
COMPANY_CONTACT = {
	"name": "Beispiel GmbH",
	"street": "Hauptstraße 1",
	"postal_code": "80331",
	"city": "München",
	"phone": "089 1234567",
	"email": "steuern@example.org",
}


class DatenlieferantDefaultsTest(TestCase):
	def test_fills_every_empty_part_from_the_company(self):
		empty = dict.fromkeys(bridge.DATENLIEFERANT_FIELDS.values())
		self.assertEqual(
			bridge.datenlieferant_defaults(empty, COMPANY_CONTACT),
			{
				"filer_name": "Beispiel GmbH",
				"street": "Hauptstraße 1",
				"postal_code": "80331",
				"city": "München",
				"phone": "089 1234567",
				"email": "steuern@example.org",
			},
		)

	def test_keeps_what_the_settings_hold(self):
		settings = {"filer_name": "Beispiel Holding", "street": "  ", "city": "Augsburg", "phone": None}
		self.assertEqual(
			bridge.datenlieferant_defaults(settings, COMPANY_CONTACT),
			{
				"street": "Hauptstraße 1",
				"postal_code": "80331",
				"phone": "089 1234567",
				"email": "steuern@example.org",
			},
		)

	def test_takes_nothing_the_company_lacks(self):
		self.assertEqual(
			bridge.datenlieferant_defaults({}, {"name": " Beispiel GmbH ", "street": "", "phone": None}),
			{"filer_name": "Beispiel GmbH"},
		)

	def test_leaves_out_what_elster_would_not_take(self):
		"""Too long for the schema, or with a character outside the set of ELSTER: the field stays empty for the
		user, and the settings still save."""
		company = {**COMPANY_CONTACT, "street": "Industriestraße 123, Gebäude C, 3. OG", "city": "Łódź"}
		defaults = bridge.datenlieferant_defaults({}, company)
		self.assertNotIn("street", defaults)
		self.assertNotIn("city", defaults)
		self.assertEqual(defaults["postal_code"], "80331")


class VoranmeldungTest(TestCase):
	def setUp(self):
		rows = bridge.kennzahl_rows(calculate(verified_month(), SKR03), KENNZAHLEN, {})
		self.rows = list(bridge.filing(rows, 2026).rows)
		self.doc = {"kennzahlen": self.rows, "kz83": 95.0}

	def test_files_the_final_amounts_and_kz83_of_the_return(self):
		voranmeldung = bridge.voranmeldung(self.doc, Period.month(2026, 3))
		self.assertEqual(voranmeldung.period, Period.month(2026, 3))
		self.assertEqual(
			dict(voranmeldung.amounts),
			{
				"81": d("1000.00"),
				"46": d("300.00"),
				"47": d("57.00"),
				"21": d("2000.00"),
				"45": d("500.00"),
				"66": d("95.00"),
				"67": d("57.00"),
				"83": d("95.00"),
			},
		)
		self.assertEqual(
			(
				voranmeldung.corrected,
				voranmeldung.attachments,
				voranmeldung.no_sepa_mandate,
				voranmeldung.offset_requested,
			),
			(False, False, False, False),
		)
		self.assertEqual((voranmeldung.supplementary_code, voranmeldung.begruendung), (None, None))

	def test_kz83_comes_from_the_return_and_not_from_its_row(self):
		rows = [{**row, "final": 1} if row["kennzahl"] == "83" else row for row in self.rows]
		voranmeldung = bridge.voranmeldung({**self.doc, "kennzahlen": rows}, Period.month(2026, 3))
		self.assertEqual(voranmeldung.amounts["83"], d("95.00"))

	def test_takes_the_further_details_of_the_return(self):
		doc = {
			**self.doc,
			"is_correction": 1,
			"attachments": 1,
			"no_sepa_mandate": 1,
			"offset_requested": 1,
			"supplementary_code": "2",
			"kz500_begruendung": "Siehe Anlage",
		}
		voranmeldung = bridge.voranmeldung(doc, Period.month(2026, 3), reported_before={"43"})
		self.assertEqual(
			(
				voranmeldung.corrected,
				voranmeldung.attachments,
				voranmeldung.no_sepa_mandate,
				voranmeldung.offset_requested,
			),
			(True, True, True, True),
		)
		self.assertEqual((voranmeldung.supplementary_code, voranmeldung.begruendung), ("2", "Siehe Anlage"))
		self.assertEqual(voranmeldung.reported_before, frozenset({"43"}))

	def test_files_january_2027_in_the_schema_of_2027(self):
		rows = list(
			bridge.filing(
				bridge.kennzahl_rows(calculate(verified_month(), SKR03.for_year(2027)), KENNZAHLEN, {}), 2027
			).rows
		)
		voranmeldung = bridge.voranmeldung({"kennzahlen": rows, "kz83": 95.0}, Period.month(2027, 1))
		document = ustva_xml.to_nutzdaten(
			bridge.filer(
				{
					"company": "Beispiel GmbH",
					"elster_tax_number": "9198011310010",
					"street": "Hauptstraße 1",
					"postal_code": "80331",
					"city": "München",
				}
			),
			voranmeldung,
			date(2027, 2, 3),
			"12345",
		)
		self.assertIn(
			'<Anmeldungssteuern xmlns="http://finkonsens.de/elster/elsteranmeldung/ustva/v2027" version="2027">',
			document,
		)
		self.assertIn("<Jahr>2027</Jahr>\n\t\t\t<Zeitraum>01</Zeitraum>", document)

	def test_a_return_that_corrects_nothing_writes_no_zeros(self):
		voranmeldung = bridge.voranmeldung(self.doc, Period.month(2026, 3), reported_before={"43"})
		self.assertEqual(voranmeldung.reported_before, frozenset())

	def test_an_empty_code_and_begruendung_are_none(self):
		voranmeldung = bridge.voranmeldung(
			{**self.doc, "supplementary_code": "", "kz500_begruendung": ""}, Period.month(2026, 3)
		)
		self.assertEqual((voranmeldung.supplementary_code, voranmeldung.begruendung), (None, None))

	def test_takes_the_date_of_the_switch_to_the_regelbesteuerung_as_frappe_gives_it(self):
		for value, expected in (
			(date(2026, 3, 14), date(2026, 3, 14)),
			("2026-03-14", date(2026, 3, 14)),
			("", None),
			(None, None),
		):
			with self.subTest(value=value):
				voranmeldung = bridge.voranmeldung(
					{**self.doc, "regelbesteuerung_from": value}, Period.month(2026, 3)
				)
				self.assertEqual(voranmeldung.regelbesteuerung_from, expected)

	def test_the_return_keeps_the_date_of_kz70_in_a_date_field(self):
		self.assertEqual(fields_of("vat_return")["regelbesteuerung_from"]["fieldtype"], "Date")


class ReportedTest(TestCase):
	def test_names_the_kennzahlen_with_an_amount_other_than_kz83(self):
		rows = [
			{"kennzahl": "81", "final": 1000.0},
			{"kennzahl": " 45 ", "final": 0.0},
			{"kennzahl": "66", "final": -0.5},
			{"kennzahl": "83", "final": 5.0},
		]
		self.assertEqual(bridge.reported(rows), frozenset({"81", "66"}))


DOCTYPES = Path(__file__).parents[1]


def fields_of(doctype: str) -> dict[str, dict]:
	definition = json.loads((DOCTYPES / doctype / f"{doctype}.json").read_text(encoding="utf-8"))
	return {field["fieldname"]: field for field in definition["fields"]}


class FinalAmountsTest(TestCase):
	def test_the_amount_each_kennzahl_is_filed_with_and_kz83(self):
		rows = bridge.kennzahl_rows(calculate(verified_month(), SKR03), KENNZAHLEN, {})
		next(row for row in rows if row["kennzahl"] == "81").update(
			{"override": 1100.0, "override_reason": "Invoice booked in April"}
		)
		self.assertEqual(
			bridge.final_amounts(rows, 2026),
			{
				"81": d("1100"),
				"46": d("300"),
				"47": d("57.00"),
				"21": d("2000"),
				"45": d("500"),
				"66": d("95.00"),
				"67": d("57.00"),
				"83": d("114.00"),
			},
		)


class ComparisonRowsTest(TestCase):
	def comparison(self, previous_period, previous_year):
		current = {"81": d("1600"), "21": d("2000"), "83": d("304.00")}
		deviates = comparison.Thresholds().exceeded
		return plausibility.compare(current, previous_period, previous_year, KENNZAHLEN, deviates)

	def test_a_row_per_kennzahl_with_its_values_and_whether_it_is_conspicuous(self):
		comparison = self.comparison(
			plausibility.EarlierPeriod(Period.month(2026, 10), {"81": d("1000"), "83": d("190.00")}),
			plausibility.EarlierPeriod(Period.month(2025, 11), None),
		)
		rows = bridge.comparison_rows(comparison)
		self.assertEqual([row["kennzahl"] for row in rows], ["81", "21", "83"])
		self.assertEqual(
			rows[0],
			{
				"kennzahl": "81",
				"label": KENNZAHLEN["81"].label,
				"current": d("1600"),
				"previous_period": d("1000"),
				"previous_year": d("0"),
				"difference": d("600"),
				"difference_percent": d("60.00"),
				"flagged": 1,
				"previous_period_known": 1,
				"previous_year_known": 0,
			},
		)

	def test_a_kennzahl_new_in_this_period_has_a_difference_and_a_flag_but_no_percentage(self):
		comparison = self.comparison(
			plausibility.EarlierPeriod(Period.month(2026, 10), {}),
			plausibility.EarlierPeriod(Period.month(2025, 11), {"21": d("500")}),
		)
		row = bridge.comparison_rows(comparison)[1]
		self.assertEqual(
			{
				key: row[key]
				for key in ("previous_period", "previous_year", "difference", "difference_percent")
			},
			{
				"previous_period": d("0"),
				"previous_year": d("500"),
				"difference": d("2000"),
				"difference_percent": d("0"),
			},
		)
		self.assertEqual(
			(row["flagged"], row["previous_period_known"], row["previous_year_known"]), (1, 1, 1)
		)

	def test_a_period_without_catalogue_writes_zero_and_says_it_is_unknown(self):
		comparison = self.comparison(
			plausibility.EarlierPeriod(Period.month(2025, 12), None),
			plausibility.EarlierPeriod(Period.month(2025, 1), None),
		)
		for row in bridge.comparison_rows(comparison):
			with self.subTest(kennzahl=row["kennzahl"]):
				self.assertEqual(
					[
						row[key]
						for key in ("previous_period", "previous_year", "difference", "difference_percent")
					],
					[d("0")] * 4,
				)
				self.assertEqual(
					(row["flagged"], row["previous_period_known"], row["previous_year_known"]), (0, 0, 0)
				)

	def test_every_value_of_a_row_has_a_field_in_the_table(self):
		comparison = self.comparison(
			plausibility.EarlierPeriod(Period.month(2026, 10), {}),
			plausibility.EarlierPeriod(Period.month(2025, 11), None),
		)
		fields = fields_of("vat_return_comparison")
		self.assertEqual(sorted(bridge.comparison_rows(comparison)[0]), sorted(fields))
		self.assertTrue(all(field.get("read_only") for field in fields.values()))


class HintRowsTest(TestCase):
	def test_a_row_per_hint_with_severity_code_text_voucher_and_party(self):
		found = [
			plausibility.Hint(
				plausibility.Code.EU_WITHOUT_VAT_ID,
				"Rechnung ...",
				"Sales Invoice",
				"ACC-SINV-1",
				"Muster GmbH",
			),
			plausibility.Hint(plausibility.Code.NO_CATALOGUE, "Kein Katalog ..."),
		]
		self.assertEqual(
			bridge.hint_rows(found),
			[
				{
					"severity": "Warnung",
					"code": "EU-OHNE-USTID",
					"text": "Rechnung ...",
					"voucher_type": "Sales Invoice",
					"voucher_no": "ACC-SINV-1",
					"party": "Muster GmbH",
				},
				{
					"severity": "Hinweis",
					"code": "KEIN-KATALOG",
					"text": "Kein Katalog ...",
					"voucher_type": "",
					"voucher_no": "",
					"party": "",
				},
			],
		)

	def test_every_value_of_a_row_has_a_field_in_the_table(self):
		(row,) = bridge.hint_rows([plausibility.Hint(plausibility.Code.ZERO_TAX, "Rechnung ...")])
		fields = fields_of("vat_return_hint")
		self.assertEqual(sorted(row), sorted(fields))
		self.assertTrue(all(field.get("read_only") for field in fields.values()))

	def test_the_severities_are_the_options_of_the_table(self):
		options = fields_of("vat_return_hint")["severity"]["options"].split("\n")
		self.assertEqual(options, [severity.value for severity in plausibility.Severity])


class ThresholdsTest(TestCase):
	def test_the_settings_offer_the_thresholds_the_report_takes_as_its_defaults(self):
		fields = fields_of("vat_return_settings")
		percent, amount = fields["comparison_threshold_percent"], fields["comparison_threshold_amount"]
		self.assertEqual(
			(percent["fieldtype"], Decimal(percent["default"])), ("Percent", comparison.DEFAULT_PERCENT)
		)
		self.assertEqual(
			(amount["fieldtype"], Decimal(amount["default"])), ("Currency", comparison.DEFAULT_AMOUNT)
		)
		self.assertTrue(percent.get("non_negative") and amount.get("non_negative"))


class LatestConfirmationsTest(TestCase):
	def test_the_latest_confirmation_of_each_number_as_the_hints_read_it(self):
		"""Frappe gives a Datetime field as a datetime in the time of the site and a Date field as a date; the form
		sends both as text."""
		records = {
			"ATU12345678": {
				"name": "USTID-2026-00002",
				"requested_at": datetime(2026, 11, 20, 15, 0, 1),
				"result": "valid",
				"valid_from": None,
				"valid_until": None,
			},
			"FR12345678901": {
				"requested_at": date(2026, 11, 20),
				"result": "invalid",
				"valid_from": date(2019, 1, 1),
				"valid_until": "2026-11-15",
			},
			"BE0123456789": {"requested_at": "2026-10-02 09:30:00", "result": "unknown"},
		}
		self.assertEqual(
			bridge.latest_confirmations(records),
			{
				"ATU12345678": plausibility.LatestConfirmation(date(2026, 11, 20), Outcome.VALID),
				"FR12345678901": plausibility.LatestConfirmation(
					date(2026, 11, 20), Outcome.INVALID, date(2019, 1, 1), date(2026, 11, 15)
				),
				"BE0123456789": plausibility.LatestConfirmation(date(2026, 10, 2), Outcome.UNKNOWN),
			},
		)
		self.assertEqual(bridge.latest_confirmations({}), {})


class MaxConfirmationAgeTest(TestCase):
	def test_the_age_the_settings_allow_or_else_the_default(self):
		self.assertEqual(
			[bridge.max_confirmation_age(value) for value in (30, "45", 0, None, "")],
			[30, 45, 0, plausibility.DEFAULT_CONFIRMATION_AGE, plausibility.DEFAULT_CONFIRMATION_AGE],
		)

	def test_the_settings_offer_the_age_with_the_default_of_the_core(self):
		field = fields_of("vat_return_settings")["max_confirmation_age"]
		self.assertEqual(
			(field["fieldtype"], int(field["default"]), field["non_negative"]),
			("Int", plausibility.DEFAULT_CONFIRMATION_AGE, 1),
		)


class ReplacedHintsTest(TestCase):
	"""USt-IdNrn. prüfen gives the hints on the USt-IdNrn. anew and leaves the others as Berechnen found them."""

	def row(self, severity: str, code: str, text: str, party: str = "") -> dict:
		return {
			"severity": severity,
			"code": code,
			"text": text,
			"voucher_type": "",
			"voucher_no": "",
			"party": party,
		}

	def test_new_hints_take_the_place_of_those_of_their_codes_and_warnings_stay_first(self):
		stored = [
			{
				**self.row("Warnung", "EU-OHNE-USTID", "a", "X"),
				"voucher_type": "Sales Invoice",
				"voucher_no": "S-1",
			},
			{**self.row("Hinweis", "USTIDNR-UNGEPRUEFT", "nie bestätigt", "Y"), "name": "row-2", "idx": 2},
			self.row("Hinweis", "KEIN-KATALOG", "b"),
		]
		new = [
			plausibility.Hint(plausibility.Code.VAT_ID_INVALID, "c", party="Y"),
			plausibility.Hint(plausibility.Code.VAT_ID_STALE, "d", party="Z"),
		]
		self.assertEqual(
			bridge.replaced_hints(stored, new, plausibility.VAT_ID_CODES),
			[
				{
					**self.row("Warnung", "EU-OHNE-USTID", "a", "X"),
					"voucher_type": "Sales Invoice",
					"voucher_no": "S-1",
				},
				self.row("Warnung", "USTIDNR-UNGUELTIG", "c", "Y"),
				self.row("Hinweis", "KEIN-KATALOG", "b"),
				self.row("Hinweis", "USTIDNR-VERALTET", "d", "Z"),
			],
		)
		self.assertEqual(bridge.replaced_hints(stored[1:2], [], plausibility.VAT_ID_CODES), [])


SALES = registers.Register.SALES
PURCHASES = registers.Register.PURCHASES


def register_row(
	register: registers.Register, number: str | None, amount: str, opening: bool = False
) -> registers.RegisterLine:
	account = f"{number} - Konto - STB" if number else "Sonderkonto - STB"
	return registers.RegisterLine(register, account, number, Decimal(amount), opening)


def reconciliation(*extra: LedgerLine) -> tuple[registers.Row, ...]:
	"""The invoices of the verified month against its ledger, with ``extra`` booked besides."""
	lines = [
		register_row(SALES, "8400", "1000.00"),
		register_row(SALES, "1776", "190.00"),
		register_row(PURCHASES, "3123", "300.00"),
		register_row(PURCHASES, "1577", "57.00"),
		register_row(PURCHASES, "1787", "-57.00"),
		register_row(PURCHASES, "4930", "95.00"),
	]
	ledger = [
		line("8400", credit="1000", voucher="Sales Invoice:A"),
		line("1776", credit="190", voucher="Sales Invoice:A"),
		line("3123", debit="300", voucher="Purchase Invoice:B"),
		line("1577", debit="57", voucher="Purchase Invoice:B"),
		line("1787", credit="57", voucher="Purchase Invoice:B"),
		*extra,
	]
	return registers.reconcile(lines, ledger, SKR03)


ACCOUNTS = {
	"1776": "1776 - Umsatzsteuer 19 % - STB",
	"1787": "1787 - Umsatzsteuer nach § 13b UStG 19 % - STB",
	"1577": "1577 - Vorsteuer nach § 13b UStG 19 % - STB",
}
NAMES = {"1776": "Umsatzsteuer 19 %", "1787": "Umsatzsteuer nach § 13b UStG 19 %"}


class ReconciliationRowsTest(TestCase):
	def rows(self, *extra: LedgerLine, earlier=()):
		return bridge.reconciliation_rows(reconciliation(*extra), KENNZAHLEN, ACCOUNTS, NAMES, earlier)

	def test_a_row_per_row_of_the_reconciliation_with_its_subject_and_amounts(self):
		found = self.rows(line("8400", credit="500", voucher="Journal Entry:JE-1"))
		self.assertEqual(
			[
				(
					row["register"],
					row["subject"],
					row["kennzahl"],
					row["account"],
					row["register_amount"],
					row["ledger_amount"],
					row["difference"],
					row["compared"],
					row["explanation"],
				)
				for row in found
			],
			[
				(
					"Sales Register",
					"Kz 81 Steuerpflichtige Umsätze zum Steuersatz von 19 %",
					"81",
					"",
					d("1000.00"),
					d("1500.00"),
					d("500.00"),
					1,
					"",
				),
				(
					"Sales Register",
					"Konto 1776 Umsatzsteuer 19 %",
					"",
					ACCOUNTS["1776"],
					d("190.00"),
					d("190.00"),
					d("0"),
					1,
					"",
				),
				(
					"Purchase Register",
					f"Kz 46 {KENNZAHLEN['46'].label}",
					"46",
					"",
					d("300.00"),
					d("300.00"),
					d("0"),
					1,
					"",
				),
				(
					"Purchase Register",
					"Konto 1787 Umsatzsteuer nach § 13b UStG 19 %",
					"",
					ACCOUNTS["1787"],
					d("57.00"),
					d("57.00"),
					d("0"),
					1,
					"",
				),
				(
					"Purchase Register",
					"Konto 1577",
					"67",
					ACCOUNTS["1577"],
					d("57.00"),
					d("57.00"),
					d("0"),
					1,
					"",
				),
				(
					"Purchase Register",
					"Konten ohne Platz in der Kontenzuordnung: 4930",
					"",
					"",
					d("95.00"),
					d("0"),
					d("0"),
					0,
					"",
				),
			],
		)

	def test_berechnen_keeps_an_explanation_of_a_row_whose_amounts_stay(self):
		journal = line("8400", credit="500", voucher="Journal Entry:JE-1")
		earlier = [{**row, "explanation": " Privatanteil per Journalbuchung "} for row in self.rows(journal)]
		self.assertEqual(
			[row["explanation"] for row in self.rows(journal, earlier=earlier)],
			["Privatanteil per Journalbuchung"] * 6,
		)

	def test_an_explanation_of_other_amounts_is_dropped(self):
		earlier = [
			{**row, "explanation": "Privatanteil"}
			for row in self.rows(line("8400", credit="500", voucher="Journal Entry:JE-1"))
		]
		found = self.rows(line("8400", credit="600", voucher="Journal Entry:JE-1"), earlier=earlier)
		self.assertEqual([row["explanation"] for row in found][:2], ["", "Privatanteil"])

	def test_every_value_of_a_row_has_a_field_in_the_table(self):
		fields = fields_of("vat_return_register_reconciliation")
		self.assertEqual(sorted(self.rows()[0]), sorted(fields))
		self.assertEqual(
			sorted(name for name, field in fields.items() if not field.get("read_only")), ["explanation"]
		)

	def test_the_reports_are_the_options_of_the_table(self):
		options = fields_of("vat_return_register_reconciliation")["register"]["options"].split("\n")
		self.assertEqual(options, [register.value for register in registers.Register])


class ExplanationsKeptTest(TestCase):
	stored = (
		{"name": "r1", "subject": "Kz 81", "difference": d("500.00"), "explanation": ""},
		{
			"name": "r2",
			"subject": "Konto 1776",
			"difference": d("95.00"),
			"explanation": "Storno im Vormonat",
		},
	)

	def test_a_save_takes_the_explanations_and_keeps_what_berechnen_stored(self):
		sent = [
			{"name": "r1", "subject": "Kz 86", "difference": d("0"), "explanation": " Privatanteil "},
			{"name": "r2", "subject": "Konto 1776", "difference": d("95.00"), "explanation": ""},
		]
		self.assertEqual(
			bridge.explanations_kept(self.stored, sent),
			[
				{"name": "r1", "subject": "Kz 81", "difference": d("500.00"), "explanation": "Privatanteil"},
				{"name": "r2", "subject": "Konto 1776", "difference": d("95.00"), "explanation": ""},
			],
		)

	def test_a_row_the_save_leaves_out_keeps_its_explanation_and_one_it_adds_is_not_taken(self):
		sent = [{"name": None, "subject": "Neu", "difference": d("1"), "explanation": "x"}]
		self.assertEqual(bridge.explanations_kept(self.stored, sent), list(self.stored))


class UnexplainedTest(TestCase):
	def test_names_the_rows_with_a_difference_and_no_explanation(self):
		rows = [
			{"subject": "Kz 81", "difference": 500.0, "explanation": None},
			{"subject": "Konto 1776", "difference": "95.00", "explanation": "Storno im Vormonat"},
			{"subject": "Kz 21", "difference": 0, "explanation": ""},
			{"subject": "Konto 1576", "difference": -5.0, "explanation": "  "},
		]
		self.assertEqual(bridge.unexplained(rows), ["Kz 81", "Konto 1576"])

	def test_a_table_without_differences_needs_no_explanation(self):
		self.assertEqual(
			bridge.unexplained(bridge.reconciliation_rows(reconciliation(), KENNZAHLEN, {}, {})), []
		)


def booked_month() -> list[LedgerLine]:
	"""Three invoices of 33.33 euros with 6.33 euros of tax each: 99 euros of Kz 81, 18.99 euros on the tax account."""
	return [
		posting
		for number in (1, 2, 3)
		for posting in (
			line("8400", credit="33.33", voucher=f"Sales Invoice:SINV-{number}"),
			line("1776", credit="6.33", voucher=f"Sales Invoice:SINV-{number}"),
		)
	]


class StatutoryTaxTest(TestCase):
	"""A return calculated with the tax as booked keeps that tax in its rows and files Kz 83 with it."""

	def setUp(self):
		result = calculate(booked_month(), SKR03, statutory_tax=BOOKED)
		self.rows = [
			{**row, "name": f"row-{index}"}
			for index, row in enumerate(bridge.kennzahl_rows(result, KENNZAHLEN, {}))
		]

	def row(self, kennzahl: str) -> dict:
		return next(row for row in self.rows if row["kennzahl"] == kennzahl)

	def test_the_row_of_kz81_keeps_the_tax_as_booked(self):
		self.assertEqual((self.row("81")["reported"], self.row("81")["tax"]), (d("99"), d("18.99")))

	def test_files_kz83_with_the_tax_as_booked(self):
		filing = bridge.filing(self.rows, 2026, BOOKED)
		self.assertEqual((filing.totals["output_tax"], filing.totals["kz83"]), (d("18.99"), d("18.99")))
		self.assertEqual(bridge.final_amounts(self.rows, 2026, BOOKED), {"81": d("99"), "83": d("18.99")})

	def test_a_return_from_the_base_files_the_tax_of_the_form_whatever_its_rows_keep(self):
		self.assertEqual(bridge.filing(self.rows, 2026).totals["kz83"], d("18.81"))
		self.assertEqual(bridge.filing(self.rows, 2026, FROM_BASE).totals["kz83"], d("18.81"))
		self.assertEqual(bridge.statutory_tax_of(""), FROM_BASE)
		self.assertEqual(bridge.statutory_tax_of(None), FROM_BASE)
		self.assertEqual(bridge.statutory_tax_of("As Booked"), BOOKED)

	def test_an_overridden_base_takes_the_tax_of_the_form(self):
		self.row("81").update({"override": 100.0, "override_reason": "Invoice booked in April"})
		self.assertEqual(bridge.filed_taxes(self.rows, KENNZAHLEN, BOOKED), {})
		self.assertEqual(bridge.filing(self.rows, 2026, BOOKED).totals["kz83"], d("19.00"))

	def test_the_taxes_a_return_files(self):
		self.assertEqual(bridge.filed_taxes(self.rows, KENNZAHLEN, BOOKED), {"81": d("18.99")})
		self.assertEqual(bridge.filed_taxes(self.rows, KENNZAHLEN, FROM_BASE), {})

	def test_a_base_below_one_euro_files_nothing_but_its_tax(self):
		result = calculate(
			[line("8400", credit="0.80", voucher="V1"), line("1776", credit="0.15", voucher="V1")],
			SKR03,
			statutory_tax=BOOKED,
		)
		rows = bridge.kennzahl_rows(result, KENNZAHLEN, {})
		filing = bridge.filing(rows, 2026, BOOKED)
		self.assertEqual(
			{row["kennzahl"]: row["final"] for row in filing.rows}, {"81": d("0"), "83": d("0.15")}
		)

	def test_a_row_with_a_tax_but_no_amount_stays_on_the_return(self):
		stored = [{"name": "row-0", "kennzahl": "81", "amount": 0.0, "reported": 0.0, "tax": 1.0}]
		with self.assertRaises(bridge.RowError) as raised:
			bridge.restored(stored, [])
		self.assertEqual(
			(raised.exception.problem, raised.exception.kennzahl), (bridge.RowProblem.REMOVED, "81")
		)

	def test_a_save_keeps_the_tax_berechnen_stored(self):
		sent = [{**row, "tax": 0} for row in self.rows]
		self.assertEqual(bridge.restored(self.rows, sent)[0]["tax"], d("18.99"))

	def test_amounts_kept_follow_the_setting_of_the_return(self):
		filing = bridge.filing(self.rows, 2026, BOOKED)
		stored = {
			"kennzahlen": [{**row, **filed} for row, filed in zip(self.rows, filing.rows, strict=True)],
			**filing.totals,
		}
		self.assertTrue(bridge.amounts_kept(self.rows, stored, 2026, BOOKED))
		self.assertFalse(bridge.amounts_kept(self.rows, stored, 2026))

	def test_the_file_for_mein_elster_writes_kz83_with_the_tax_as_booked(self):
		filing = bridge.filing(self.rows, 2026, BOOKED)
		doc = {"kennzahlen": list(filing.rows), "kz83": 18.99, "statutory_tax": "As Booked"}
		rows = [{**row, **filed} for row, filed in zip(self.rows, filing.rows, strict=True)]
		voranmeldung = bridge.voranmeldung({**doc, "kennzahlen": rows}, Period.month(2026, 3))
		self.assertEqual(dict(voranmeldung.taxes), {"81": d("18.99")})
		self.assertEqual(voranmeldung.amounts["83"], d("18.99"))
		content = ustva_xml.to_import_file(bridge.filer(SETTINGS), voranmeldung, date(2026, 4, 2))
		self.assertIn(b"<Kz83>18.99</Kz83>", content)

	def test_the_file_of_a_return_from_the_base_gives_no_taxes(self):
		voranmeldung = bridge.voranmeldung({"kennzahlen": self.rows, "kz83": 18.81}, Period.month(2026, 3))
		self.assertEqual(dict(voranmeldung.taxes), {})

	def test_the_tables_hold_what_the_rows_and_the_settings_carry(self):
		self.assertEqual(fields_of("vat_return_kennzahl")["tax"]["fieldtype"], "Currency")
		self.assertTrue(fields_of("vat_return_kennzahl")["tax"]["read_only"])
		self.assertLessEqual(set(self.rows[0]) - {"name"}, set(fields_of("vat_return_kennzahl")))
		on_the_return = fields_of("vat_return")["statutory_tax"]
		self.assertEqual(on_the_return["options"].split("\n"), ["", *(value.value for value in StatutoryTax)])
		self.assertTrue(on_the_return["read_only"])
		setting = fields_of("vat_return_settings")["statutory_tax"]
		self.assertEqual(setting["options"].split("\n"), [value.value for value in StatutoryTax])
		self.assertEqual(setting["default"], DEFAULT_STATUTORY_TAX.value)
		self.assertTrue(setting["reqd"])
