from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from unittest import TestCase

from steuerbote.steuerbote.doctype.recapitulative_statement import bridge
from steuerbote.steuerbote.doctype.recapitulative_statement.bridge import FiledReturn, Party
from steuerbote.steuerbote.report.ustva_kennzahlen.attribution import Contribution
from steuerbote.zm.comparison import compare
from steuerbote.zm.errors import ZmError
from steuerbote.zm.findings import Code, Finding
from steuerbote.zm.lines import Art, Meldezeile, Override, Validity, build
from steuerbote.zm.period import ReportingPeriod
from steuerbote.zm.reconciliation import Filed, reconcile
from steuerbote.zm.tests.support import AUSTRIA, FIGURES, FRANCE, SPAIN, d, invoice

MARCH = ReportingPeriod.month(2026, 3)


def share(voucher: str | None, amount: str, kennzahl: str = "41") -> Contribution:
	return Contribution(kennzahl, voucher, ("8125",), d("0"), d(amount), d(amount))


def statement(*amounts, validity=None, overrides=None):
	return build(amounts, FIGURES, validity=validity, overrides=overrides)


def line_row(vat_id: str, art: str, reported: str = "0", **fields) -> dict:
	return {"vat_id": vat_id, "art": art, "reported": reported, **fields}


class ReportingPeriodTest(TestCase):
	def test_each_kind_with_its_number(self):
		self.assertEqual(bridge.reporting_period("month", 2026, 3), MARCH)
		self.assertEqual(bridge.reporting_period("two_months", 2026, 2), ReportingPeriod(2026, 4, 5))
		self.assertEqual(bridge.reporting_period("quarter", 2026, 4), ReportingPeriod(2026, 10, 12))
		self.assertEqual(bridge.reporting_period("year", 2026, 0), ReportingPeriod.calendar_year(2026))

	def test_refuses_a_kind_or_number_the_core_does_not_know(self):
		for kind, index in (("week", 1), ("month", 13), ("quarter", 5), ("two_months", 0)):
			with self.subTest(kind=kind, index=index), self.assertRaises(ValueError):
				bridge.reporting_period(kind, 2026, index)


class CsvFileNameTest(TestCase):
	def test_names_the_period_and_a_berichtigung(self):
		self.assertEqual(bridge.csv_file_name(MARCH, correction=False), "ZM-2026-03.csv")
		self.assertEqual(
			bridge.csv_file_name(ReportingPeriod(2026, 4, 5), correction=False), "ZM-2026-04-05.csv"
		)
		self.assertEqual(
			bridge.csv_file_name(ReportingPeriod.quarter(2026, 2), correction=True),
			"ZM-2026-Q2-berichtigt.csv",
		)
		self.assertEqual(
			bridge.csv_file_name(ReportingPeriod.calendar_year(2026), correction=False), "ZM-2026.csv"
		)


class VoucherAmountsTest(TestCase):
	PARTIES = MappingProxyType(
		{
			"Sales Invoice:SINV-1": Party("CUST-1", "Alpen GmbH", "ATU 123 456 78"),
			"Payment Entry:PE-1": Party("CUST-1", "Alpen GmbH", AUSTRIA, "Austria"),
		}
	)

	def test_keeps_what_each_voucher_adds_to_kz_41_42_and_21_with_its_party(self):
		amounts = bridge.voucher_amounts_of(
			[
				share("Sales Invoice:SINV-1", "1000.00"),
				share("Payment Entry:PE-1", "-20.00"),
				share("Journal Entry:JE-1", "300.00", kennzahl="21"),
				share("Sales Invoice:SINV-1", "190.00", kennzahl="81"),
			],
			self.PARTIES,
		)
		self.assertEqual(
			[
				(item.voucher, item.kennzahl, item.amount, item.party, item.vat_id, item.destination)
				for item in amounts
			],
			[
				("Sales Invoice:SINV-1", "41", d("1000.00"), "Alpen GmbH", "ATU 123 456 78", None),
				("Payment Entry:PE-1", "41", d("-20.00"), "Alpen GmbH", AUSTRIA, "Austria"),
				("Journal Entry:JE-1", "21", d("300.00"), None, None, None),
			],
		)

	def test_leaves_out_shares_without_voucher_or_amount(self):
		"""A share without voucher stays on the side of the ledger, where the reconciliation names it."""
		self.assertEqual(
			bridge.voucher_amounts_of([share(None, "50.00"), share("Sales Invoice:SINV-1", "0.00")], {}), []
		)

	def test_the_rows_of_the_vouchers_give_back_the_same_amounts(self):
		amounts = bridge.voucher_amounts_of(
			[share("Sales Invoice:SINV-1", "1000.00"), share("Payment Entry:PE-1", "-20.00", kennzahl="42")],
			self.PARTIES,
		)
		rows = bridge.voucher_rows(amounts, self.PARTIES)
		self.assertEqual(
			rows[1],
			{
				"voucher_type": "Payment Entry",
				"voucher_no": "PE-1",
				"customer": "CUST-1",
				"party": "Alpen GmbH",
				"vat_id": AUSTRIA,
				"kennzahl": "42",
				"art": "D",
				"amount": d("-20.00"),
				"destination": "Austria",
			},
		)
		self.assertIsNone(
			bridge.voucher_rows(bridge.voucher_amounts_of([share("Journal Entry:JE-9", "1.00")], {}), {})[0][
				"customer"
			]
		)
		self.assertEqual(bridge.voucher_amounts(rows), amounts)

	def test_rows_as_frappe_stores_them_read_as_cents(self):
		row = {
			"voucher_type": "Sales Invoice",
			"voucher_no": "SINV-1",
			"kennzahl": "41",
			"amount": 1000.1,
			"party": "",
			"vat_id": "",
			"destination": "",
		}
		(item,) = bridge.voucher_amounts([row])
		self.assertEqual(
			(item.amount, item.party, item.vat_id, item.destination), (d("1000.10"), None, None, None)
		)


class OverridesTest(TestCase):
	def test_an_override_takes_effect_with_its_reason(self):
		overrides = bridge.overrides_of(
			[
				line_row("atu 12345678", "L", override="900", override_reason="Gutschrift im April"),
				line_row(FRANCE, "S", override="0", override_reason="Kein Unternehmer"),
				line_row(SPAIN, "L"),
			]
		)
		self.assertEqual(
			overrides,
			{
				(AUSTRIA, Art.L): Override(d("900.00"), "Gutschrift im April"),
				(FRANCE, Art.S): Override(d("0"), "Kein Unternehmer"),
			},
		)

	def test_an_amount_without_reason_is_refused(self):
		with self.assertRaises(ZmError) as raised:
			bridge.overrides_of([line_row(AUSTRIA, "L", override=500)])
		self.assertEqual(
			raised.exception.template,
			"An override of a line of the Zusammenfassende Meldung needs a Begründung.",
		)

	def test_an_override_takes_whole_euros(self):
		with self.assertRaisesRegex(ZmError, "whole euros"):
			bridge.overrides_of([line_row(AUSTRIA, "L", override=500.5, override_reason="Skonto")])

	def test_a_line_is_overridden_once(self):
		with self.assertRaisesRegex(ZmError, "is overridden twice"):
			bridge.overrides_of(
				[
					line_row(AUSTRIA, "L", override=1, override_reason="a"),
					line_row("ATU 12345678", "L", override=2, override_reason="b"),
				]
			)


class ValidityTest(TestCase):
	def test_the_result_of_the_latest_confirmation_and_unconfirmed_without_one(self):
		self.assertEqual(
			bridge.validity_for(
				[AUSTRIA, FRANCE, SPAIN, "XI123456789", ""],
				{AUSTRIA: "valid", FRANCE: "invalid", SPAIN: "unknown"},
			),
			{
				AUSTRIA: Validity.CONFIRMED,
				FRANCE: Validity.INVALID,
				SPAIN: Validity.UNCONFIRMED,
				"XI123456789": Validity.UNCONFIRMED,
			},
		)

	def test_the_vat_ids_of_the_vouchers_and_the_overrides(self):
		amounts = [invoice("1", "10.00", vat_id="atu12345678"), invoice("2", "5.00", vat_id=None)]
		overrides = {(FRANCE, Art.S): Override(d("100"), "Verbringen")}
		self.assertEqual(bridge.line_vat_ids(amounts, overrides), {AUSTRIA, "", FRANCE})


class StatementTest(TestCase):
	VOUCHERS = (
		{
			"voucher_type": "Sales Invoice",
			"voucher_no": "SINV-1",
			"kennzahl": "41",
			"amount": 1000.5,
			"party": "Alpen GmbH",
			"vat_id": AUSTRIA,
		},
		{
			"voucher_type": "Sales Invoice",
			"voucher_no": "SINV-2",
			"kennzahl": "21",
			"amount": 300,
			"party": "Paris SA",
			"vat_id": FRANCE,
		},
	)

	def test_rebuilds_the_lines_from_the_rows_of_vouchers_and_lines(self):
		rows = [
			line_row(AUSTRIA, "L", confirmation_outcome="valid"),
			line_row(
				FRANCE,
				"S",
				confirmation_outcome="invalid",
				override=300,
				override_reason="Bestätigung vom 2. März liegt vor",
			),
		]
		result = bridge.statement_of(self.VOUCHERS, rows, FIGURES)
		self.assertEqual(
			[(line.vat_id, line.art, line.amount, line.reported, line.blocked) for line in result.lines],
			[(AUSTRIA, Art.L, d("1000.50"), d("1000"), False), (FRANCE, Art.S, d("300.00"), d("300"), False)],
		)
		self.assertEqual([finding.code for finding in result.findings], [Code.INVALID_VAT_ID])
		self.assertTrue(result.ready)

	def test_a_number_whose_row_is_gone_counts_as_unconfirmed(self):
		result = bridge.statement_of(
			self.VOUCHERS, [line_row(AUSTRIA, "L", confirmation_outcome="valid")], FIGURES
		)
		self.assertEqual([finding.code for finding in result.findings], [Code.UNCONFIRMED_VAT_ID])
		self.assertFalse(result.ready)


class ConfirmationFieldsTest(TestCase):
	RECORD = MappingProxyType(
		{
			"name": "USTID-2026-00001",
			"requested_at": datetime(2026, 3, 2, 9, 30),
			"service": "bzst",
			"result": "valid",
			"status_code": "evatr-0000",
			"consultation_id": "0a1b2c3d4e5f6071",
		}
	)

	def test_the_latest_confirmation_as_a_line_shows_it(self):
		self.assertEqual(
			bridge.confirmation_fields(self.RECORD),
			{
				"confirmation": "USTID-2026-00001",
				"confirmation_date": date(2026, 3, 2),
				"confirmation_service": "bzst",
				"confirmation_outcome": "valid",
				"confirmation_status": "evatr-0000",
				"consultation_id": "0a1b2c3d4e5f6071",
			},
		)
		self.assertIsNone(
			bridge.confirmation_fields({**self.RECORD, "requested_at": None})["confirmation_date"]
		)
		self.assertEqual(
			bridge.confirmation_fields({**self.RECORD, "requested_at": date(2026, 3, 3)})[
				"confirmation_date"
			],
			date(2026, 3, 3),
		)

	def test_carries_the_confirmation_of_the_rows_over_by_vat_id(self):
		rows = [
			line_row(AUSTRIA, "L", **bridge.confirmation_fields(self.RECORD)),
			line_row(AUSTRIA, "S", **bridge.confirmation_fields(self.RECORD)),
			line_row("", "L"),
		]
		self.assertEqual(bridge.confirmations_of(rows), {AUSTRIA: bridge.confirmation_fields(self.RECORD)})


class LineRowsTest(TestCase):
	def test_a_row_per_line_with_its_party_amounts_block_and_confirmation(self):
		lines = statement(
			invoice("SINV-1", "1000.99", party=" Alpen GmbH "),
			invoice("SINV-2", "20.00", kennzahl="21", vat_id=FRANCE, party=""),
			validity={AUSTRIA: Validity.CONFIRMED, FRANCE: Validity.UNCONFIRMED},
			overrides={(SPAIN, Art.L): Override(d("5000"), "Verbringen nach Spanien")},
		)
		confirmation = {"confirmation": "USTID-2026-00001", "confirmation_outcome": "valid"}
		rows = bridge.line_rows(lines, {AUSTRIA: confirmation}, MARCH)
		self.assertEqual(
			[
				(
					row["vat_id"],
					row["art"],
					row["party"],
					row["amount"],
					row["reported"],
					row["override"],
					row["blocked"],
				)
				for row in rows
			],
			[
				(AUSTRIA, "L", "Alpen GmbH", d("1000.99"), d("1000"), d("0"), 0),
				(SPAIN, "L", "", d("0"), d("5000"), d("5000"), 0),
				(FRANCE, "S", "", d("20.00"), d("20"), d("0"), 1),
			],
		)
		self.assertEqual(rows[0]["confirmation"], "USTID-2026-00001")
		self.assertEqual(
			(rows[1]["override_reason"], rows[1]["confirmation"], rows[1]["confirmation_outcome"]),
			("Verbringen nach Spanien", None, None),
		)
		self.assertEqual(
			[(row["filed_amount"], row["in_file"]) for row in rows], [(d("0"), 1), (d("0"), 1), (d("0"), 1)]
		)

	def test_a_berichtigung_marks_its_lines_and_cancels_what_is_gone(self):
		"""BZSt, „Berichtigung einer ZM“, case 3: a line under a wrong USt-IdNr. is cancelled with 0 and the right
		line reported; an unchanged line is left out of the Berichtigung."""
		held = {("ES111111113", Art.L): d("21000"), (AUSTRIA, Art.L): d("1000"), (FRANCE, Art.S): d("0")}
		lines = statement(invoice("SINV-1", "1000.00"), invoice("SINV-2", "21000.00", vat_id="ES111111112"))
		rows = bridge.line_rows(lines, {}, MARCH, held)
		self.assertEqual(
			[(row["vat_id"], row["reported"], row["filed_amount"], row["in_file"]) for row in rows],
			[
				(AUSTRIA, d("1000"), d("1000"), 0),
				("ES111111112", d("21000"), d("0"), 1),
				("ES111111113", d("0"), d("21000"), 1),
			],
		)


class HintsTest(TestCase):
	def test_a_row_per_finding_with_voucher_and_party(self):
		finding = Finding(Code.NO_VAT_ID, "Beleg SINV-1 geht ...", "Sales Invoice:SINV-1", "Alpen GmbH")
		self.assertEqual(
			bridge.hint_rows([finding, Finding(Code.FILED_RETURNS, "Die abgegebenen ...")]),
			[
				{
					"severity": "Fehler",
					"code": "ZM-OHNE-USTID",
					"text": "Beleg SINV-1 geht ...",
					"voucher_type": "Sales Invoice",
					"voucher_no": "SINV-1",
					"party": "Alpen GmbH",
				},
				{
					"severity": "Hinweis",
					"code": "ZM-ABGLEICH-VORANMELDUNG",
					"text": "Die abgegebenen ...",
					"voucher_type": "",
					"voucher_no": "",
					"party": "",
				},
			],
		)

	def test_the_findings_of_the_lines_are_found_anew_and_the_others_kept(self):
		lines = statement(invoice("SINV-1", "1000.00"), validity={AUSTRIA: Validity.INVALID})
		stored = [
			{"severity": "Fehler", "code": "ZM-USTID-UNBESTAETIGT", "text": "alt"},
			{"severity": "Fehler", "code": "ZM-SCHWELLE", "text": "Im I. Kalendervierteljahr ..."},
			{"severity": "Hinweis", "code": "ZM-ABWEICHUNG-VORPERIODE", "text": "Die Zeile ..."},
		]
		merged = bridge.merged_hints(lines, stored)
		self.assertEqual(
			[row["code"] for row in merged], ["ZM-USTID-UNGUELTIG", "ZM-SCHWELLE", "ZM-ABWEICHUNG-VORPERIODE"]
		)
		self.assertEqual(
			merged[1],
			{
				"severity": "Fehler",
				"code": "ZM-SCHWELLE",
				"text": "Im I. Kalendervierteljahr ...",
				"voucher_type": None,
				"voucher_no": None,
				"party": None,
			},
		)

	def test_the_lines_and_the_errors_that_no_override_lifts_decide_whether_it_is_ready(self):
		confirmed = statement(invoice("SINV-1", "1000.00"), validity={AUSTRIA: Validity.CONFIRMED})
		blocked = statement(invoice("SINV-1", "1000.00"), validity={AUSTRIA: Validity.INVALID})
		hint = {"severity": "Hinweis", "code": "ZM-ABWEICHUNG-VORPERIODE"}
		self.assertTrue(bridge.ready(confirmed, [hint, {"severity": "Fehler", "code": "ZM-USTID-UNGUELTIG"}]))
		self.assertFalse(bridge.ready(blocked, [hint]))
		for code in ("ZM-SCHWELLE", "ZM-ABGLEICH-HAUPTBUCH"):
			with self.subTest(code=code):
				self.assertFalse(bridge.ready(confirmed, [{"severity": "Fehler", "code": code}]))


class TotalsTest(TestCase):
	def test_the_sum_of_each_art(self):
		rows = (
			Meldezeile(AUSTRIA, Art.L, d("1000")),
			Meldezeile(FRANCE, Art.L, d("-50")),
			Meldezeile(FRANCE, Art.S, d("20")),
		)
		self.assertEqual(bridge.totals(rows), {"total_l": d("950"), "total_d": d("0"), "total_s": d("20")})


class ReconciliationRowsTest(TestCase):
	def test_a_row_per_art_with_the_ledger_the_lines_and_the_filed_returns(self):
		lines = statement(invoice("SINV-1", "1000.40"), invoice("SINV-2", "200.00", kennzahl="21"))
		ledger = [
			share("Sales Invoice:SINV-1", "1000.40"),
			share("Journal Entry:JE-1", "5.00"),
			share("Sales Invoice:SINV-2", "200.00", "21"),
		]
		result = reconcile(lines, ledger, FIGURES, {"41": Filed(d("1000"), 1)})
		rows = bridge.reconciliation_rows(result)
		self.assertEqual(
			rows[0],
			{
				"art": "L",
				"kennzahl": "41",
				"ledger": d("1005.40"),
				"statement": d("1000.40"),
				"difference": d("-5.00"),
				"reported": d("1000"),
				"filed": d("1000"),
				"filed_known": 1,
				"deviating_vouchers": 1,
				"balanced": 0,
			},
		)
		self.assertEqual(
			[(row["art"], row["filed"], row["filed_known"], row["balanced"]) for row in rows[1:]],
			[("D", d("0"), 0, 1), ("S", d("0"), 0, 1)],
		)


class ComparisonRowsTest(TestCase):
	def test_a_row_per_line_of_either_period(self):
		current = statement(invoice("SINV-1", "12000.00"))
		previous = statement(invoice("SINV-0", "5000.00"), invoice("SINV-X", "300.00", vat_id=FRANCE))
		rows = bridge.comparison_rows(compare(current, previous, lambda now, before: now != before))
		self.assertEqual(
			rows,
			[
				{
					"vat_id": AUSTRIA,
					"art": "L",
					"current": d("12000"),
					"previous": d("5000"),
					"difference": d("7000"),
					"difference_percent": d("140.00"),
					"flagged": 1,
				},
				{
					"vat_id": FRANCE,
					"art": "L",
					"current": d("0"),
					"previous": d("300"),
					"difference": d("-300"),
					"difference_percent": d("-100.00"),
					"flagged": 1,
				},
			],
		)
		(new,) = bridge.comparison_rows(compare(current, statement(), lambda now, before: False))
		self.assertEqual((new["difference_percent"], new["flagged"]), (d("0"), 0))


class FiledTest(TestCase):
	def returns(self, *periods: tuple[date, date, str]) -> list[FiledReturn]:
		return [
			FiledReturn(start, end, {"41": Decimal(amount), "21": Decimal("10")})
			for start, end, amount in periods
		]

	def test_the_kennzahlen_of_the_voranmeldungen_that_make_up_the_months(self):
		returns = self.returns(
			(date(2026, 4, 1), date(2026, 4, 30), "1000"),
			(date(2026, 5, 1), date(2026, 5, 31), "500"),
			(date(2026, 3, 1), date(2026, 3, 31), "99"),
		)
		span = (date(2026, 4, 1), date(2026, 5, 31))
		self.assertEqual(
			bridge.filed(returns, span, ("41", "42")), {"41": Filed(d("1500"), 2), "42": Filed(d("0"), 2)}
		)

	def test_nothing_unless_the_voranmeldungen_cover_each_month_once(self):
		span = (date(2026, 4, 1), date(2026, 6, 30))
		gap = self.returns(
			(date(2026, 4, 1), date(2026, 4, 30), "1"), (date(2026, 6, 1), date(2026, 6, 30), "1")
		)
		self.assertEqual(bridge.filed(gap, span, ("41",)), {})
		twice = self.returns(
			(date(2026, 4, 1), date(2026, 6, 30), "1"), (date(2026, 5, 1), date(2026, 5, 31), "1")
		)
		self.assertEqual(bridge.filed(twice, span, ("41",)), {})
		self.assertEqual(
			bridge.filed(self.returns((date(2026, 4, 1), date(2026, 6, 30), "7")), span, ("21",)),
			{"21": Filed(d("10"), 1)},
		)
		self.assertEqual(bridge.filed(gap, None, ("21",)), {})

	def test_months_across_the_turn_of_the_year(self):
		returns = self.returns(
			(date(2025, 12, 1), date(2025, 12, 31), "1"), (date(2026, 1, 1), date(2026, 1, 31), "2")
		)
		self.assertEqual(
			bridge.filed(returns, (date(2025, 12, 1), date(2026, 1, 31)), ("41",)), {"41": Filed(d("3"), 2)}
		)


class FiledLinesTest(TestCase):
	def test_a_filed_statement_reported_the_lines_of_its_file(self):
		"""An Erstmeldung its Meldezeilen, a Berichtigung the lines it corrected, those it cancelled with 0."""
		rows = (
			line_row(AUSTRIA, "L", "1000", in_file=1),
			line_row(FRANCE, "S", "0", in_file=1),
			line_row("XI123456789", "S", "500", in_file=0),
			line_row(SPAIN, "D", "300.00", in_file=1),
			line_row("", "L", "40"),
		)
		self.assertEqual(
			bridge.filed_meldezeilen(rows),
			[
				Meldezeile(AUSTRIA, Art.L, d("1000")),
				Meldezeile(FRANCE, Art.S, d("0")),
				Meldezeile(SPAIN, Art.D, d("300")),
			],
		)

	def test_the_file_of_an_erstmeldung_and_of_a_berichtigung(self):
		lines = statement(invoice("SINV-1", "1000.00"), invoice("SINV-2", "50.00", vat_id=FRANCE))
		self.assertEqual(bridge.file_lines(lines, MARCH, None), (lines.meldezeilen, False))
		held = {(AUSTRIA, Art.L): d("1000"), (SPAIN, Art.L): d("70")}
		self.assertEqual(
			bridge.file_lines(lines, MARCH, held),
			((Meldezeile(SPAIN, Art.L, d("0")), Meldezeile(FRANCE, Art.L, d("50"))), True),
		)


class NumbersToConfirmTest(TestCase):
	def test_each_number_a_line_reports_once(self):
		rows = [
			line_row(FRANCE, "S", "20"),
			line_row(AUSTRIA, "L", "1000"),
			line_row(AUSTRIA, "S", "300"),
			line_row(SPAIN, "L", "0"),
			line_row("XI123456789", "S", "50"),
			line_row("DE123456789", "L", "50"),
			line_row("", "L", "40"),
		]
		self.assertEqual(bridge.numbers_to_confirm(rows), [AUSTRIA, FRANCE])

	def test_the_customer_of_a_number_from_the_vouchers_of_its_lines(self):
		rows = [
			{"kennzahl": "41", "vat_id": "atu 12345678", "customer": ""},
			{"kennzahl": "21", "vat_id": "XI123456789", "customer": "CUST-XI"},
			{"kennzahl": "41", "vat_id": "ATU12345678", "customer": "CUST-1"},
		]
		self.assertEqual(bridge.customer_of(rows, AUSTRIA), "CUST-1")
		self.assertIsNone(bridge.customer_of(rows, FRANCE))
		self.assertEqual(bridge.customer_of(rows, "XI123456789"), "CUST-XI")
