import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from unittest import TestCase

from steuerbote.elster import zm_xml
from steuerbote.elster.ustva_xml import TEXT_MISSING, XmlError
from steuerbote.steuerbote.doctype.recapitulative_statement import bridge
from steuerbote.steuerbote.doctype.recapitulative_statement.bridge import FiledReturn, Party
from steuerbote.steuerbote.report.ustva_kennzahlen.attribution import Contribution
from steuerbote.zm.comparison import compare
from steuerbote.zm.errors import ZmError
from steuerbote.zm.findings import Code, Finding
from steuerbote.zm.lines import Art, Meldezeile, Override, Validity, build
from steuerbote.zm.period import ReportingPeriod
from steuerbote.zm.reconciliation import Filed, reconcile
from steuerbote.zm.rhythm import Coverage
from steuerbote.zm.tests.support import AUSTRIA, FIGURES, FRANCE, SPAIN, d, invoice

MARCH = ReportingPeriod.month(2026, 3)
DOCTYPES = Path(__file__).parents[1]


def fields_of(doctype: str) -> dict[str, dict]:
	definition = json.loads((DOCTYPES / doctype / f"{doctype}.json").read_text(encoding="utf-8"))
	return {field["fieldname"]: field for field in definition["fields"]}


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
	SPAN = (date(2026, 4, 1), date(2026, 6, 30))

	def test_the_result_of_the_latest_confirmation_and_unconfirmed_without_one(self):
		self.assertEqual(
			bridge.validity_for(
				[AUSTRIA, FRANCE, SPAIN, "XI123456789", ""],
				{AUSTRIA: {"result": "valid"}, FRANCE: {"result": "invalid"}, SPAIN: {"result": "unknown"}},
				self.SPAN,
			),
			{
				AUSTRIA: Validity.CONFIRMED,
				FRANCE: Validity.INVALID,
				SPAIN: Validity.UNCONFIRMED,
				"XI123456789": Validity.UNCONFIRMED,
			},
		)

	def test_a_number_valid_all_through_the_months_counts_as_confirmed_for_them(self):
		"""evatr-2006: „Die angefragte USt-IdNr. ist zum Anfragezeitpunkt nicht gültig. Sie war gültig im Zeitraum,
		der durch die Werte in den Feldern gueltigAb und gueltigBis beschrieben ist.“ evatr-2002: „Sie ist erst
		gültig ab dem Datum im Feld gueltigAb.“ (Statusmeldungen of the eVatR API)"""
		records = {
			AUSTRIA: {"result": "invalid", "valid_from": date(2019, 1, 1), "valid_until": date(2026, 7, 15)},
			FRANCE: {"result": "invalid", "valid_from": "2019-01-01", "valid_until": "2026-06-15"},
			SPAIN: {"result": "invalid", "valid_from": date(2026, 5, 1), "valid_until": None},
			"XI123456789": {"result": "invalid", "valid_from": date(2026, 4, 1)},
			"EL123456789": {"result": "invalid", "valid_until": date(2026, 6, 30)},
			"BE0123456789": {"result": "invalid"},
		}
		self.assertEqual(
			bridge.validity_for(records, records, self.SPAN),
			{
				AUSTRIA: Validity.CONFIRMED,
				FRANCE: Validity.INVALID,
				SPAIN: Validity.INVALID,
				"XI123456789": Validity.CONFIRMED,
				"EL123456789": Validity.CONFIRMED,
				"BE0123456789": Validity.INVALID,
			},
		)
		self.assertEqual(bridge.validity_for([AUSTRIA], records), {AUSTRIA: Validity.INVALID})

	def test_the_day_each_number_was_last_asked_about(self):
		records = {
			AUSTRIA: {"requested_at": datetime(2026, 3, 2, 9, 30)},
			FRANCE: {"requested_at": None},
		}
		self.assertEqual(bridge.asked_on(records), {AUSTRIA: date(2026, 3, 2)})

	def test_the_first_and_last_day_of_the_months_a_statement_reports(self):
		june = Coverage(ReportingPeriod.month(2026, 6), (6,), (4, 5, 6))
		self.assertEqual(bridge.covered_span(june), (date(2026, 4, 1), date(2026, 6, 30)))
		april = Coverage(ReportingPeriod.month(2026, 4), (4,), ())
		self.assertEqual(bridge.covered_span(april), (date(2026, 4, 1), date(2026, 4, 30)))

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
			("Verbringen nach Spanien", None, "unconfirmed"),
		)
		self.assertEqual([row["manual"] for row in rows], [0, 1, 0])
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


class AmountsKeptTest(TestCase):
	"""Before a statement is transmitted, made into its file or filed, its lines and sums are built again from its
	vouchers and overrides and set against what it holds."""

	def setUp(self):
		self.lines = statement(
			invoice("SINV-1", "1000.99"),
			invoice("SINV-2", "20.00", kennzahl="21", vat_id=FRANCE),
			invoice("SINV-3", "50.00", vat_id=None),
			overrides={(SPAIN, Art.L): Override(d("5000"), "Verbringen nach Spanien")},
		)
		self.stored = {
			"lines": bridge.line_rows(self.lines, {}, MARCH),
			**bridge.totals(self.lines.meldezeilen),
		}

	def test_the_lines_and_the_sums_of_a_save_are_kept(self):
		self.assertTrue(bridge.amounts_kept(self.lines, MARCH, None, self.stored))

	def test_lines_and_sums_read_as_frappe_gives_them(self):
		"""Floats for the amounts, None for a line without USt-IdNr., the rows in any order."""
		rows = [
			{
				**row,
				"vat_id": row["vat_id"] or None,
				"amount": float(row["amount"]),
				"reported": float(row["reported"]),
				"filed_amount": 0.0,
			}
			for row in reversed(self.stored["lines"])
		]
		totals = {field: float(amount) for field, amount in bridge.totals(self.lines.meldezeilen).items()}
		self.assertTrue(bridge.amounts_kept(self.lines, MARCH, None, {"lines": rows, **totals}))

	def test_a_line_or_a_sum_changed_past_the_save_is_not_kept(self):
		for field, value in (
			("amount", d("1000.98")),
			("reported", d("999")),
			("filed_amount", d("1")),
			("in_file", 0),
		):
			with self.subTest(field=field):
				rows = [dict(row) for row in self.stored["lines"]]
				next(row for row in rows if row["vat_id"] == AUSTRIA)[field] = value
				self.assertFalse(bridge.amounts_kept(self.lines, MARCH, None, {**self.stored, "lines": rows}))
		for field in ("total_l", "total_d", "total_s"):
			with self.subTest(field=field):
				self.assertFalse(bridge.amounts_kept(self.lines, MARCH, None, {**self.stored, field: d("1")}))
		for rows in (self.stored["lines"][1:], [*self.stored["lines"], line_row(AUSTRIA, "S")]):
			with self.subTest(rows=len(rows)):
				self.assertFalse(bridge.amounts_kept(self.lines, MARCH, None, {**self.stored, "lines": rows}))

	def test_a_berichtigung_keeps_what_was_filed_for_its_lines(self):
		held = {(AUSTRIA, Art.L): d("900"), ("ES111111113", Art.L): d("100")}
		stored = {
			"lines": bridge.line_rows(self.lines, {}, MARCH, held),
			**bridge.totals(self.lines.meldezeilen),
		}
		self.assertTrue(bridge.amounts_kept(self.lines, MARCH, held, stored))
		self.assertFalse(bridge.amounts_kept(self.lines, MARCH, None, stored))


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
				"filed_note": "",
				"deviating_vouchers": 1,
				"balanced": 0,
				"manual": d("0"),
			},
		)
		self.assertEqual(
			[(row["art"], row["filed"], row["filed_known"], row["balanced"]) for row in rows[1:]],
			[("D", d("0"), 0, 1), ("S", d("0"), 0, 1)],
		)

	def test_the_lines_entered_by_hand_have_a_column_of_their_own(self):
		lines = statement(
			invoice("SINV-1", "1000.00"),
			overrides={("ATU99999999", Art.L): Override(d("2500"), "Verbringen in das Lager Wien")},
		)
		rows = bridge.reconciliation_rows(
			reconcile(lines, [share("Sales Invoice:SINV-1", "1000.00")], FIGURES)
		)
		self.assertEqual(
			(rows[0]["statement"], rows[0]["manual"], rows[0]["reported"]),
			(d("1000.00"), d("2500"), d("3500")),
		)

	def test_every_value_of_a_row_has_a_field_in_its_table(self):
		lines = statement(invoice("SINV-1", "1000.00"))
		reconciliation = bridge.reconciliation_rows(reconcile(lines, [], FIGURES))[0]
		(line,) = bridge.line_rows(lines, {}, MARCH)
		for doctype, row in (
			("recapitulative_statement_reconciliation", reconciliation),
			("recapitulative_statement_line", line),
		):
			with self.subTest(doctype=doctype):
				self.assertEqual(set(row) - set(fields_of(doctype)), set())


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


class UnternehmerTest(TestCase):
	"""The element unternehmer of the Nutzdaten from the VAT Return Settings of the company."""

	SETTINGS = MappingProxyType(
		{
			"company": "Beispiel GmbH",
			"ust_idnr": "DE123456789",
			"filer_name": None,
			"street": "Hauptstraße 1",
			"postal_code": "80331",
			"city": "München",
			"phone": "089 1234567",
			"email": "steuern@example.org",
			"teilnehmernummer": None,
		}
	)

	def test_names_the_company_with_its_ust_idnr_and_the_address_of_the_datenlieferant(self):
		self.assertEqual(
			bridge.unternehmer(self.SETTINGS, "de"),
			zm_xml.Unternehmer(
				ust_idnr="DE123456789",
				name="Beispiel GmbH",
				street="Hauptstraße 1",
				postal_code="80331",
				city="München",
				country="DE",
				phone="089 1234567",
			),
		)

	def test_the_name_and_the_teilnehmernummer_of_the_settings_come_first(self):
		filer = bridge.unternehmer(
			{**self.SETTINGS, "filer_name": "Beispiel Handel", "teilnehmernummer": "0300000"}, "DE"
		)
		self.assertEqual((filer.name, filer.teilnehmernummer), ("Beispiel Handel", "0300000"))

	def test_empty_fields_are_left_out_and_the_required_ones_refused(self):
		filer = bridge.unternehmer({**self.SETTINGS, "phone": "", "postal_code": ""}, "AT")
		self.assertEqual((filer.phone, filer.postal_code, filer.country), (None, None, "AT"))
		with self.assertRaises(XmlError) as raised:
			bridge.unternehmer({**self.SETTINGS, "street": None}, "DE")
		self.assertEqual(
			(raised.exception.template, raised.exception.label), (TEXT_MISSING, zm_xml.STREET_LABEL)
		)
		with self.assertRaises(XmlError) as raised:
			bridge.unternehmer({**self.SETTINGS, "ust_idnr": None}, "DE")
		self.assertEqual(raised.exception.template, zm_xml.NOT_A_GERMAN_VAT_ID)


class ZmTest(TestCase):
	"""The Zusammenfassende Meldung for ERiC from the lines of the statement."""

	def test_an_erstmeldung_reports_the_meldezeilen_of_the_statement(self):
		lines = statement(invoice("SINV-1", "1000.00"), invoice("SINV-2", "50.00", vat_id=FRANCE))
		zm = bridge.zm(MARCH, lines, None, 0, 0)
		self.assertEqual(
			(zm.period, zm.lines, zm.meldeart, zm.anzeige, zm.widerruf),
			(MARCH, lines.meldezeilen, zm_xml.Meldeart.ERSTMELDUNG, False, False),
		)

	def test_a_berichtigung_reports_what_changes_what_the_bzst_holds(self):
		lines = statement(invoice("SINV-1", "1000.00"), invoice("SINV-2", "50.00", vat_id=FRANCE))
		held = {(AUSTRIA, Art.L): d("1000"), (SPAIN, Art.L): d("70")}
		zm = bridge.zm(MARCH, lines, held, 0, 0)
		self.assertEqual(zm.meldeart, zm_xml.Meldeart.BERICHTIGUNG)
		self.assertEqual(zm.reported, bridge.file_lines(lines, MARCH, held)[0])

	def test_anzeige_and_widerruf_come_from_their_check_fields(self):
		lines = statement(invoice("SINV-1", "1000.00"))
		self.assertTrue(bridge.zm(MARCH, lines, None, 1, 0).anzeige)
		self.assertTrue(bridge.zm(MARCH, lines, None, "0", 1).widerruf)


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


class CoverageFieldsTest(TestCase):
	"""A statement keeps the months it reports, so that what checks it later reads the same months, whatever the
	rules say by then."""

	JUNE = Coverage(ReportingPeriod.month(2026, 6), (6,), (4, 5, 6))
	APRIL = Coverage(ReportingPeriod.month(2026, 4), (4,), ())

	def test_the_first_and_last_day_of_the_goods_and_of_the_services_months(self):
		self.assertEqual(
			bridge.coverage_fields(self.JUNE),
			{
				"goods_from": date(2026, 6, 1),
				"goods_to": date(2026, 6, 30),
				"services_from": date(2026, 4, 1),
				"services_to": date(2026, 6, 30),
			},
		)
		self.assertEqual(
			bridge.coverage_fields(self.APRIL),
			{
				"goods_from": date(2026, 4, 1),
				"goods_to": date(2026, 4, 30),
				"services_from": None,
				"services_to": None,
			},
		)

	def test_the_months_kept_read_back_also_as_frappe_sends_them(self):
		for covered in (self.JUNE, self.APRIL):
			with self.subTest(period=covered.period):
				self.assertEqual(
					bridge.kept_coverage(covered.period, bridge.coverage_fields(covered)), covered
				)
		sent = {name: str(day) if day else None for name, day in bridge.coverage_fields(self.JUNE).items()}
		self.assertEqual(bridge.kept_coverage(self.JUNE.period, sent), self.JUNE)
		self.assertIsNone(bridge.kept_coverage(self.JUNE.period, dict.fromkeys(bridge.COVERAGE_FIELDS)))


class OverlappingTest(TestCase):
	"""The Lieferungen and the sonstige Leistungen of a month are filed once each."""

	@staticmethod
	def filing(name: str, covered: Coverage) -> dict:
		period = covered.period
		return {
			"name": name,
			"from_date": period.start,
			"to_date": period.end,
			**bridge.coverage_fields(covered),
		}

	def test_the_first_filing_that_reports_a_month_of_the_same_kind(self):
		quarter = self.filing("ZM-1", Coverage(ReportingPeriod.quarter(2026, 1), (1, 2, 3), (1, 2, 3)))
		march = self.filing("ZM-2", Coverage(ReportingPeriod.month(2026, 3), (3,), (1, 2, 3)))
		january = Coverage(ReportingPeriod.month(2026, 1), (1,), ())
		self.assertEqual(bridge.overlapping(january, [quarter, march]), quarter)
		services = Coverage(ReportingPeriod.month(2026, 2), (2,), (2,))
		self.assertEqual(bridge.overlapping(services, [march]), march)

	def test_months_of_another_kind_or_another_month_do_not_clash(self):
		april = self.filing("ZM-4", Coverage(ReportingPeriod.month(2026, 4), (4,), ()))
		may = self.filing("ZM-5", Coverage(ReportingPeriod.month(2026, 5), (5,), ()))
		june = Coverage(ReportingPeriod.month(2026, 6), (6,), (4, 5, 6))
		self.assertIsNone(bridge.overlapping(june, [april, may]))
		self.assertIsNone(bridge.overlapping(june, []))

	def test_a_filing_that_keeps_no_months_counts_with_all_months_of_its_period(self):
		kept_nothing = {
			"name": "ZM-0",
			"from_date": "2026-04-01",
			"to_date": "2026-06-30",
			**dict.fromkeys(bridge.COVERAGE_FIELDS),
		}
		self.assertEqual(
			bridge.overlapping(Coverage(ReportingPeriod.month(2026, 6), (6,), ()), [kept_nothing]),
			kept_nothing,
		)
		self.assertIsNone(
			bridge.overlapping(Coverage(ReportingPeriod.month(2026, 7), (7,), (7,)), [kept_nothing])
		)


class OverrideBasisTest(TestCase):
	"""An override is tied to the ledger amount of its line it was made against (steuerbote.zm.lines): a save takes it
	from the stored row while the override stays as it was, and from the ledger amount the stored line showed when
	the override is new or changed. Frappe keeps no read-only field from a save through its API, so the basis never
	comes from the rows a save sends."""

	STORED = (
		line_row(
			AUSTRIA,
			"L",
			amount="55000.99",
			override="55000",
			override_reason="Nachweis",
			override_basis="55000.99",
		),
		line_row(FRANCE, "S", amount="4000.00"),
	)

	def test_an_override_reads_its_basis(self):
		overrides = bridge.overrides_of(
			[
				line_row(
					AUSTRIA, "L", override="55000", override_reason="Nachweis", override_basis="55000.99"
				),
				line_row(FRANCE, "S", override="0", override_reason="Kein Unternehmer", override_basis=None),
				line_row(SPAIN, "L", override="10", override_reason="Verbringen"),
			]
		)
		self.assertEqual([override.basis for override in overrides.values()], [d("55000.99"), None, None])

	def test_an_unchanged_override_keeps_its_basis(self):
		sent = [
			line_row(
				"atu 12345678", "L", override="55000", override_reason=" Nachweis ", override_basis="1.00"
			),
			line_row(FRANCE, "S"),
		]
		self.assertEqual(bridge.override_bases(self.STORED, sent), [d("55000.99"), None])

	def test_a_new_or_changed_override_takes_the_ledger_amount_the_line_showed(self):
		for name, row in (
			("amount", line_row(AUSTRIA, "L", override="57000", override_reason="Nachweis")),
			("reason", line_row(AUSTRIA, "L", override="55000", override_reason="Nachweis geprüft")),
		):
			with self.subTest(name):
				self.assertEqual(bridge.override_bases(self.STORED, [row]), [d("55000.99")])
		new = line_row(FRANCE, "S", override="0", override_reason="Kein Unternehmer")
		self.assertEqual(bridge.override_bases(self.STORED, [new]), [d("4000.00")])

	def test_a_line_the_statement_did_not_hold_has_no_basis_yet(self):
		row = line_row("ATU99999999", "L", override="2500", override_reason="Verbringen")
		self.assertEqual(bridge.override_bases(self.STORED, [row]), [None])
		self.assertEqual(bridge.override_bases((), [row]), [None])


class OpenErrorsTest(TestCase):
	def test_the_errors_that_still_hold_the_statement(self):
		lines = [line_row(AUSTRIA, "L", acceptance_reason="Grund"), line_row(FRANCE, "S")]
		vouchers = bridge.voucher_rows(
			[invoice("SINV-1", "10.00"), invoice("SINV-2", "10.00", kennzahl="21", vat_id=FRANCE)], {}
		)
		hints = [
			{"severity": "Fehler", "code": "ZM-SCHWELLE", "text": "Schwelle"},
			{"severity": "Fehler", "code": "ZM-USTID-UNBESTAETIGT", "text": "alt"},
			{"severity": "Hinweis", "code": "ZM-ABWEICHUNG-VORPERIODE", "text": "Vorperiode"},
		]
		found = bridge.open_errors(bridge.statement_of(vouchers, lines, FIGURES), hints)
		self.assertEqual([code for code, _text in found], ["ZM-USTID-UNBESTAETIGT", "ZM-SCHWELLE"])
		self.assertIn(FRANCE, found[0][1])


class AcceptancesTest(TestCase):
	def test_the_release_of_each_line_with_its_reason(self):
		self.assertEqual(
			bridge.acceptances_of(
				[
					line_row("atu 12345678", "L", acceptance_reason=" Bestätigt am Liefertag "),
					line_row(FRANCE, "S", acceptance_reason=" "),
					line_row(SPAIN, "L"),
				]
			),
			{(AUSTRIA, Art.L): "Bestätigt am Liefertag"},
		)


class LineRowsOfOverridesAndReleasesTest(TestCase):
	def test_a_row_keeps_the_basis_of_its_override_and_its_release(self):
		lines = build(
			(invoice("SINV-1", "1000.99"), invoice("SINV-2", "20.00", kennzahl="21", vat_id=FRANCE)),
			FIGURES,
			validity={AUSTRIA: Validity.UNCONFIRMED, FRANCE: Validity.CONFIRMED},
			overrides={(FRANCE, Art.S): Override(d("0"), "Kein Unternehmer")},
			accepted={(AUSTRIA, Art.L): "Bestätigt am Liefertag"},
		)
		rows = bridge.line_rows(lines, {}, MARCH)
		self.assertEqual(
			[(row["override_basis"], row["acceptance_reason"], row["blocked"]) for row in rows],
			[(d("0"), "Bestätigt am Liefertag", 0), (d("20.00"), "", 0)],
		)

	def test_a_number_without_confirmation_shows_so(self):
		lines = statement(
			invoice("SINV-1", "10.00"), invoice("SINV-2", "10.00", vat_id="DE123456789"), validity={}
		)
		rows = bridge.line_rows(lines, {}, MARCH)
		self.assertEqual(
			[(row["vat_id"], row["confirmation_outcome"]) for row in rows],
			[(AUSTRIA, "unconfirmed"), ("DE123456789", None)],
		)
		self.assertIn(
			"unconfirmed", fields_of("recapitulative_statement_line")["confirmation_outcome"]["options"]
		)

	def test_a_berichtigung_shows_an_unchanged_line_with_an_unconfirmed_number_as_holding_nothing(self):
		lines = statement(invoice("SINV-1", "1000.00"), validity={AUSTRIA: Validity.UNCONFIRMED})
		(unchanged,) = bridge.line_rows(lines, {}, MARCH, {(AUSTRIA, Art.L): d("1000")})
		(changed,) = bridge.line_rows(lines, {}, MARCH, {(AUSTRIA, Art.L): d("900")})
		self.assertEqual((unchanged["blocked"], changed["blocked"]), (0, 1))


class ReadyAgainstTest(TestCase):
	def test_a_berichtigung_is_ready_when_only_lines_it_repeats_unchanged_are_unconfirmed(self):
		lines = statement(invoice("SINV-1", "1000.00"), validity={AUSTRIA: Validity.UNCONFIRMED})
		hints = bridge.hint_rows(lines.findings)
		self.assertFalse(bridge.ready(lines, hints))
		self.assertTrue(bridge.ready(lines, hints, {(AUSTRIA, Art.L): d("1000")}))
		self.assertFalse(bridge.ready(lines, hints, {(AUSTRIA, Art.L): d("900")}))

	def test_the_findings_on_overrides_releases_and_old_confirmations_come_from_the_lines(self):
		self.assertLessEqual(
			{Code.OVERRIDE_STALE, Code.VAT_ID_ACCEPTED, Code.CONFIRMATION_STALE}, bridge.LINE_CODES
		)


class RowNamesTest(TestCase):
	"""Every save builds the lines and the findings anew; rows that stay keep the names they had, so that the version
	of the statement shows what changed and not every row removed and added."""

	def test_a_row_keeps_the_name_of_the_stored_row_of_its_key(self):
		stored = [
			{"name": "a1", "vat_id": AUSTRIA, "art": "L"},
			{"name": "f1", "vat_id": FRANCE, "art": "S"},
		]
		rows = [{"vat_id": FRANCE, "art": "S"}, {"vat_id": SPAIN, "art": "L"}]
		self.assertEqual(
			bridge.with_names(rows, stored, ("vat_id", "art")),
			[{"name": "f1", "vat_id": FRANCE, "art": "S"}, {"vat_id": SPAIN, "art": "L"}],
		)

	def test_rows_of_the_same_key_take_one_name_each(self):
		stored = [
			{"name": "h1", "code": "X", "text": "a"},
			{"code": "X", "text": "a"},
			{"name": "h2", "code": "X", "text": "a"},
		]
		rows = [{"code": "X", "text": "a"}] * 3
		self.assertEqual(
			[row.get("name") for row in bridge.with_names(rows, stored, ("code", "text"))], ["h1", "h2", None]
		)


class LeftOutTest(TestCase):
	"""The file for Mein ELSTER and the print hold the lines the ZM reports; the lines it leaves out are named, so that
	nobody takes the file or the print for the whole statement."""

	def test_the_lines_with_an_amount_that_the_file_does_not_report(self):
		rows = [
			line_row(AUSTRIA, "L", "1000", amount="1000.00", in_file=1),
			line_row("", "L", "1200", amount="1200.00", party="Muster Kft.", in_file=0),
			line_row("PL-12", "S", "800", amount="800.00", party="Muster Sp. z o.o.", in_file=0),
			line_row(FRANCE, "S", "0", amount="0.00", in_file=0),
		]
		self.assertEqual(
			bridge.left_out(rows, correction=False),
			[
				("ohne USt-IdNr.", "L", "Muster Kft.", d("1200.00")),
				("PL-12", "S", "Muster Sp. z o.o.", d("800.00")),
			],
		)

	def test_a_berichtigung_leaves_out_the_lines_it_repeats_unchanged_without_naming_them(self):
		rows = [
			line_row(AUSTRIA, "L", "1000", amount="1000.00", filed_amount="1000", in_file=0),
			line_row("", "L", "50", amount="50.00", filed_amount="0", in_file=0),
		]
		self.assertEqual(bridge.left_out(rows, correction=True), [("ohne USt-IdNr.", "L", "", d("50.00"))])


class UncomparedTest(TestCase):
	"""A reconciliation row without filed Voranmeldungen to compare with says why, instead of 0,00 €."""

	def test_names_the_months_without_a_filed_voranmeldung(self):
		returns = [FiledReturn(date(2026, 9, 1), date(2026, 9, 30))]
		self.assertEqual(
			bridge.uncompared(returns, (date(2026, 7, 1), date(2026, 9, 30))),
			"Nicht verglichen: Für Juli 2026, August 2026 ist keine Voranmeldung abgegeben.",
		)

	def test_says_so_when_the_voranmeldungen_do_not_fit_the_months(self):
		returns = [
			FiledReturn(date(2026, 7, 1), date(2026, 9, 30)),
			FiledReturn(date(2026, 9, 1), date(2026, 9, 30)),
		]
		self.assertEqual(
			bridge.uncompared(returns, (date(2026, 7, 1), date(2026, 9, 30))),
			"Nicht verglichen: Die abgegebenen Voranmeldungen decken die Monate der Meldung nicht je einmal ab.",
		)

	def test_nothing_to_say_when_they_are_compared_or_the_statement_has_no_such_months(self):
		returns = [FiledReturn(date(2026, 7, 1), date(2026, 9, 30))]
		self.assertEqual(bridge.uncompared(returns, (date(2026, 7, 1), date(2026, 9, 30))), "")
		self.assertEqual(
			bridge.uncompared([], None), "Nicht verglichen: Die Meldung umfasst keine Monate dieser Art."
		)

	def test_the_rows_carry_the_note_of_their_art(self):
		lines = statement(invoice("SINV-1", "1000.00"))
		rows = bridge.reconciliation_rows(reconcile(lines, [], FIGURES), {"L": "a", "D": "a", "S": "b"})
		self.assertEqual([row["filed_note"] for row in rows], ["a", "a", "b"])
		self.assertEqual(
			[row["filed_note"] for row in bridge.reconciliation_rows(reconcile(lines, [], FIGURES))],
			["", "", ""],
		)


class MonthFilingsTest(TestCase):
	"""The ZM places its bookings by month with the rule of the Voranmeldung (steuerbote.ustva.assignment): a month
	counts as filed with the statements that reported its Lieferungen, or its sonstige Leistungen, first and latest."""

	def test_each_month_of_a_filed_span_with_its_first_and_latest_filing(self):
		first, berichtigung, other = (
			datetime(2026, 4, 20, 9),
			datetime(2026, 6, 2, 10),
			datetime(2026, 5, 20, 8),
		)
		found = bridge.month_filings(
			[
				((date(2026, 1, 1), date(2026, 3, 31)), [first]),
				((date(2026, 1, 1), date(2026, 3, 31)), [berichtigung]),
				((date(2026, 4, 1), date(2026, 4, 30)), [other]),
				(None, [other]),
				((date(2026, 5, 1), date(2026, 5, 31)), []),
			]
		)
		self.assertEqual(
			[(filing.period.label, filing.first, filing.latest) for filing in found],
			[
				("Januar 2026", first, berichtigung),
				("Februar 2026", first, berichtigung),
				("März 2026", first, berichtigung),
				("April 2026", other, other),
			],
		)
