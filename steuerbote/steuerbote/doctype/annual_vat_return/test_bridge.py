"""The bridge between the Annual VAT Return and the core of the Umsatzsteuererklärung, without a bench."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.elster.ustva_xml import XmlError
from steuerbote.jahresmeldung.findings import DATA_LENGTH, Severity
from steuerbote.jahresmeldung.overrides import OverrideError
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import Address
from steuerbote.steuerbote.doctype.annual_vat_return import bridge
from steuerbote.steuerbote.doctype.annual_vat_return.bridge import (
	BLOCKED,
	KLEINUNTERNEHMER,
	MESSAGES,
	SWITCH_MISSING,
	SWITCH_OTHER,
	VERPROBUNG,
	WATCHED,
	Advisor,
	Company,
	YearPeriod,
)
from steuerbote.steuerbote.doctype.vat_return_settings.rules import FilingRhythm, PeriodRule
from steuerbote.ustjahr import form
from steuerbote.ustjahr.calculation import (
	MANUAL_NO_PARAGRAPH,
	MANUAL_NOT_FED,
	CalculationError,
	ManualLine,
	calculate,
)
from steuerbote.ustjahr.reconciliation import reconcile
from steuerbote.ustjahr.soll import Filed, FiledKennzahl, Override, SollError, vorauszahlungssoll
from steuerbote.ustjahr.split import AnnualRule, Choice, split
from steuerbote.ustva import calculate as calculate_ustva
from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.mapping import AccountRule, Mapping, Side, TaxCheck, WatchedAccount, WatchLevel
from steuerbote.ustva.period import Period

YEAR = 2026
MONTHS = tuple(Period.month(YEAR, month) for month in range(1, 13))
QUARTERS = tuple(Period.quarter(YEAR, quarter) for quarter in range(1, 5))
MAPPING = Mapping(
	"SKR03",
	(
		AccountRule("8400", "81", Side.CREDIT),
		AccountRule("8100", "48", Side.CREDIT),
		AccountRule("1576", "66", Side.DEBIT),
	),
	checks=(TaxCheck("Umsatzsteuer 19 %", ("8400",), ("1776",)),),
	watched=(
		WatchedAccount("1548"),
		WatchedAccount("8603", WatchLevel.HINT),
		WatchedAccount("3552", WatchLevel.HINT),
	),
	year=2026,
)
SPLIT = split(
	MAPPING,
	choices=(Choice("8100", paragraph="4 Nummer 8 Buchstabe a"),),
	annual_rules=(AnnualRule("3552", "E3100801", Side.DEBIT),),
)
REASON = "Gutschrift vom 30. Dezember 2026, gebucht im Januar"


def line(account: str, debit: str = "0", credit: str = "0", voucher: str | None = None) -> LedgerLine:
	return LedgerLine(account, Decimal(debit), Decimal(credit), voucher)


def sale(index: int, base: str = "1000.00", tax: str = "190.00") -> list[LedgerLine]:
	voucher = f"Sales Invoice:R{index}"
	return [line("8400", credit=base, voucher=voucher), line("1776", credit=tax, voucher=voucher)]


def rule(year: int, rhythm: str, month: int = 1) -> PeriodRule:
	return PeriodRule(year, FilingRhythm(rhythm), month)


def filing(period: Period, lines: list[LedgerLine], name: str | None = None) -> Filed:
	"""A Voranmeldung filed from the ledger of its period, as its VAT Return keeps it."""
	result = calculate_ustva(lines, MAPPING)
	kennzahlen = {
		number: FiledKennzahl(value.amount, value.reported, value.reported)
		for number, value in result.values.items()
	}
	return Filed(period, name or f"UStVA-{period.code}", kennzahlen["83"].final, lines=kennzahlen)


def row(feldkennung: str, form_amount: str = "0", **values) -> dict:
	return {"feldkennung": feldkennung, "form_amount": Decimal(form_amount), **values}


class YearPeriodsTest(TestCase):
	def test_a_monthly_filer_owes_twelve_voranmeldungen(self):
		periods = bridge.year_periods([rule(YEAR, "monthly")], YEAR)
		self.assertEqual(periods, tuple(YearPeriod(period, True) for period in MONTHS))
		self.assertEqual(bridge.due_periods(periods), MONTHS)

	def test_a_switch_from_quarters_to_months_tiles_the_year(self):
		periods = bridge.year_periods([rule(YEAR, "quarterly"), rule(YEAR, "monthly", 10)], YEAR)
		self.assertEqual([entry.period for entry in periods], [*QUARTERS[:3], *MONTHS[9:]])
		self.assertTrue(all(entry.due for entry in periods))

	def test_a_month_without_a_voranmeldung_is_a_month_of_its_own_that_owes_none(self):
		"""§ 18 Absatz 2 Satz 3 UStG lets the Finanzamt exempt a company; the months still belong to the year."""
		periods = bridge.year_periods([rule(YEAR, "none"), rule(YEAR, "quarterly", 7)], YEAR)
		self.assertEqual(
			[(entry.period, entry.due) for entry in periods],
			[*((month, False) for month in MONTHS[:6]), (QUARTERS[2], True), (QUARTERS[3], True)],
		)

	def test_a_month_before_the_first_rule_owes_none(self):
		periods = bridge.year_periods([rule(YEAR, "monthly", 4)], YEAR)
		self.assertEqual([entry.due for entry in periods], [False] * 3 + [True] * 9)

	def test_a_period_that_ends_before_the_company_began_owes_none(self):
		periods = bridge.year_periods([rule(YEAR, "quarterly")], YEAR, began=date(2026, 5, 15))
		self.assertEqual([entry.due for entry in periods], [False, True, True, True])

	def test_runs_every_period_of_the_year_and_each_filed_one_the_settings_no_longer_set(self):
		periods = bridge.year_periods([rule(YEAR, "monthly")], YEAR)
		filed = [filing(QUARTERS[0], sale(1)), filing(MONTHS[3], sale(2))]
		self.assertEqual(bridge.periods_to_run(periods, filed), (MONTHS[0], QUARTERS[0], *MONTHS[1:]))


class FiledTest(TestCase):
	def test_reads_the_kennzahlen_of_a_filed_vat_return_in_cents(self):
		rows = [
			{"kennzahl": "81", "amount": 1000.4, "reported": 1000, "final": 1100},
			{"kennzahl": "83", "amount": "190.08", "reported": "190.00", "final": "209.00"},
			{"kennzahl": None, "amount": 5},
		]
		self.assertEqual(
			bridge.filed_kennzahlen(rows),
			{
				"81": FiledKennzahl(Decimal("1000.40"), Decimal("1000.00"), Decimal("1100.00")),
				"83": FiledKennzahl(Decimal("190.08"), Decimal("190.00"), Decimal("209.00")),
			},
		)

	def test_the_latest_filing_of_a_period_counts(self):
		corrected = filing(MONTHS[1], sale(1, "2000.00", "380.00"), "UStVA-B")
		first = filing(MONTHS[1], sale(1), "UStVA-A")
		january = filing(MONTHS[0], sale(2))
		self.assertEqual(bridge.latest_per_period([corrected, january, first]), (january, corrected))


class LinesTest(TestCase):
	def setUp(self):
		lines = [
			*sale(1, "1000.40", "190.08"),
			line("8100", credit="500", voucher="Sales Invoice:R2"),
			line("1576", debit="95.20", voucher="Purchase Invoice:E1"),
			line("3552", debit="300", voucher="Purchase Invoice:E2"),
		]
		self.result = calculate(lines, SPLIT, (ManualLine("E3006201", Decimal("4.80"), REASON),))

	def test_writes_a_line_for_every_field_with_an_amount_in_the_order_of_the_form(self):
		rows = bridge.line_rows(self.result)
		self.assertEqual(
			[(entry["feldkennung"], entry["form_amount"], entry["ledger_amount"]) for entry in rows],
			[
				("E3003303", Decimal("1000"), Decimal("1000.40")),
				("E3003304", Decimal("190.08"), Decimal("190.08")),
				("E3104502", Decimal("500"), Decimal("500.00")),
				("E3100801", Decimal("300"), Decimal("300.00")),
				("E3006201", Decimal("100.00"), Decimal("95.20")),
			],
		)

	def test_describes_each_line_and_names_the_paragraph_of_its_accounts(self):
		rows = {entry["feldkennung"]: entry for entry in bridge.line_rows(self.result)}
		self.assertEqual(
			{
				key: rows["E3104502"][key]
				for key in ("label", "kennzahl", "line", "formatkennzeichen", "ustva")
			},
			{
				"label": "nach § 4 Nummer",
				"kennzahl": "287",
				"line": 52,
				"formatkennzeichen": "N",
				"ustva": "48",
			},
		)
		self.assertEqual(rows["E3104502"]["paragraph"], "4 Nummer 8 Buchstabe a")
		self.assertEqual((rows["E3003304"]["kennzahl"], rows["E3003304"]["paragraph"]), ("", ""))
		self.assertEqual(rows["E3100801"]["ustva"], "")

	def test_a_line_by_hand_names_its_field_by_the_feldkennung_or_its_kennzahl(self):
		catalogue = form.catalogue_for(YEAR)
		self.assertEqual(bridge.feldkennung_of(catalogue, " 320 "), "E3006201")
		self.assertEqual(bridge.feldkennung_of(catalogue, "e3103902"), "E3103902")
		self.assertEqual(bridge.feldkennung_of(catalogue, None), "")

	def test_a_line_by_hand_takes_a_field_the_ledger_feeds_and_a_paragraph_only_where_its_line_names_one(
		self,
	):
		catalogue = form.catalogue_for(YEAR)
		self.assertEqual(bridge.manual_field(catalogue, "E3103902", "4 Nummer 2").line, 46)
		self.assertEqual(bridge.manual_field(catalogue, "E3006201", "  ").element, "E3006201")
		for element, paragraph, template in (
			("E9999999", None, MANUAL_NOT_FED),
			("E3006001", None, MANUAL_NOT_FED),
			("E3006201", "4 Nummer 2", MANUAL_NO_PARAGRAPH),
		):
			with self.subTest(element=element), self.assertRaises(CalculationError) as caught:
				bridge.manual_field(catalogue, element, paragraph)
			self.assertEqual((caught.exception.template, caught.exception.values), (template, (element,)))

	def test_a_line_files_its_correction_once_it_has_a_reason_and_a_line_by_hand_nothing_of_its_own(self):
		rows = [
			row("E3003303", "1000"),
			row("E3003304", "190.08", correction=Decimal("190.00"), correction_reason=REASON),
			row("E3006201", "100.00"),
			row("E3006201", manual=1, correction=Decimal("4.80"), correction_reason=REASON),
		]
		self.assertEqual(
			bridge.filed_amounts(rows),
			{"E3003303": Decimal("1000.00"), "E3003304": Decimal("190.00"), "E3006201": Decimal("100.00")},
		)

	def test_hands_the_lines_by_hand_to_the_computation_with_their_paragraph(self):
		rows = [
			row("E3003303", "1000"),
			row(
				" E3103902 ",
				manual=1,
				correction=200,
				correction_reason=f" {REASON} ",
				paragraph=" 4  Nummer 2 ",
			),
			row("E3006201", manual=1, correction="4.80", correction_reason=REASON, paragraph=""),
		]
		self.assertEqual(
			bridge.manual_lines(rows),
			(
				ManualLine("E3103902", Decimal("200.00"), REASON, "4 Nummer 2"),
				ManualLine("E3006201", Decimal("4.80"), REASON),
			),
		)

	def test_a_line_by_hand_without_a_reason_is_refused(self):
		with self.assertRaises(OverrideError):
			bridge.manual_lines([row("E3006201", manual=1, correction=5)])

	def test_the_reconciliation_compares_the_amounts_after_the_corrections_the_document_holds(self):
		rows = [
			row("E3003303", correction=Decimal("990"), correction_reason=REASON),
			row("E3005901", correction=Decimal("0"), correction_reason=REASON),
			row("E3006201", manual=1, correction=Decimal("4.80"), correction_reason=REASON),
			row("E3104502"),
		]
		amounts = bridge.corrected(self.result, rows)
		self.assertEqual(
			amounts,
			{
				**self.result.reported,
				"E3003303": Decimal("990.00"),
				"E3005901": Decimal("0.00"),
			},
		)


class SollTest(TestCase):
	def test_the_finanzamt_sets_the_soll_with_a_reason(self):
		self.assertIsNone(bridge.soll_override(0, " "))
		self.assertEqual(
			bridge.soll_override("1234.5", " Bescheid  vom 3. März 2027 "),
			Override(Decimal("1234.50"), "Bescheid vom 3. März 2027"),
		)
		self.assertEqual(bridge.soll_override(None, "Schätzung"), Override(Decimal("0.00"), "Schätzung"))

	def test_an_amount_without_a_reason_is_refused(self):
		with self.assertRaises(SollError) as caught:
			bridge.soll_override(100, "")
		self.assertEqual(str(caught.exception), "Vorauszahlungssoll needs a reason.")

	def test_line_125_files_the_soll_of_the_finanzamt_else_the_computed_one(self):
		self.assertEqual(bridge.vorauszahlungssoll(1500.25, None), Decimal("1500.25"))
		self.assertEqual(
			bridge.vorauszahlungssoll(1500.25, Override(Decimal("1600"), "Bescheid")), Decimal("1600")
		)


class WaiversTest(TestCase):
	def test_reads_the_reasons_by_period_code(self):
		rows = [
			{"period_code": "01", "waiver_reason": "  In Mein ELSTER\nabgegeben "},
			{"period_code": "02", "waiver_reason": " "},
			{"period_code": None, "waiver_reason": "ohne Zeitraum"},
		]
		self.assertEqual(bridge.waivers_of(rows), {"01": "In Mein ELSTER abgegeben"})

	def test_waives_due_periods_only(self):
		periods = (YearPeriod(MONTHS[0], True), YearPeriod(MONTHS[1], False), YearPeriod(MONTHS[2], True))
		reasons = {"01": "Grund", "02": "Grund"}
		self.assertEqual(bridge.waived(periods, reasons), {MONTHS[0]: "Grund"})

	def test_a_save_keeps_the_stored_rows_and_takes_their_reasons(self):
		stored = [
			{"name": "a", "period_code": "01", "kz83": 100, "waiver_reason": ""},
			{"name": "b", "period_code": "02", "kz83": 200, "waiver_reason": "alt"},
		]
		sent = [
			{"name": "a", "period_code": "05", "kz83": 999, "waiver_reason": " neu "},
			{"name": None, "period_code": "03", "waiver_reason": "fremd"},
		]
		self.assertEqual(
			bridge.waivers_kept(stored, sent),
			[
				{"name": "a", "period_code": "01", "kz83": 100, "waiver_reason": "neu"},
				{"name": "b", "period_code": "02", "kz83": 200, "waiver_reason": "alt"},
			],
		)


class ReconciliationTest(TestCase):
	"""Two quarters filed, the third filed and changed since by a late posting, the fourth not filed."""

	def setUp(self):
		self.periods = bridge.year_periods([rule(YEAR, "quarterly")], YEAR)
		ledger = {quarter: sale(quarter.index) for quarter in QUARTERS}
		filed = [filing(quarter, list(ledger[quarter])) for quarter in QUARTERS[:3]]
		ledger[QUARTERS[2]] += sale(9, "100.00", "19.00")
		lines = [entry for quarter in QUARTERS for entry in ledger[quarter]]
		self.result = calculate(lines, SPLIT)
		self.soll = vorauszahlungssoll(
			YEAR, filed, bridge.due_periods(self.periods), Decimal("0"), {QUARTERS[3]: "Fremd abgegeben"}
		)
		now = {quarter: calculate_ustva(ledger[quarter], MAPPING) for quarter in QUARTERS}
		self.reconciliation = reconcile(self.result, self.soll, now)

	def test_writes_a_row_for_each_period_with_its_cause_and_reason(self):
		rows = bridge.period_rows(self.periods, self.reconciliation, {"44": "Fremd abgegeben"})
		self.assertEqual(
			[
				(entry["period_code"], entry["vat_return"], entry["cause"], entry["waiver_reason"])
				for entry in rows
			],
			[
				("41", "UStVA-41", "No Difference", ""),
				("42", "UStVA-42", "No Difference", ""),
				("43", "UStVA-43", "Late Postings", ""),
				("44", None, "Not Filed", "Fremd abgegeben"),
			],
		)
		third = rows[2]
		self.assertEqual(
			(
				third["kz83"],
				third["kz39"],
				third["kz83_now"],
				third["difference"],
				third["late"],
				third["corrections"],
			),
			(
				Decimal("190.00"),
				Decimal("0.00"),
				Decimal("209.00"),
				Decimal("19.00"),
				Decimal("19.00"),
				Decimal("0.00"),
			),
		)
		self.assertEqual(third["period_label"], "III. Kalendervierteljahr 2026")
		self.assertEqual([entry["due"] for entry in rows], [1, 1, 1, 1])

	def test_a_filed_period_the_settings_no_longer_set_is_no_due_one(self):
		monthly = bridge.year_periods([rule(YEAR, "monthly")], YEAR)
		rows = bridge.period_rows(monthly, self.reconciliation, {})
		self.assertEqual([entry["due"] for entry in rows], [0, 0, 0, 0])

	def test_writes_a_row_for_each_kennzahl_and_for_kz_820_in_cents(self):
		rows = bridge.reconciliation_rows(self.reconciliation, YEAR)
		self.assertEqual([entry["kennzahl"] for entry in rows], ["81", "820"])
		kz81, kz820 = rows
		self.assertEqual(kz81["label"], "Steuerpflichtige Umsätze zum Steuersatz von 19 %")
		self.assertEqual(
			(kz81["filed"], kz81["annual"], kz81["late"], kz81["unfiled"], kz81["rest"]),
			(Decimal("3000.00"), Decimal("4100.00"), Decimal("100.00"), Decimal("1000.00"), Decimal("0.00")),
		)
		self.assertEqual((kz81["sondervorauszahlung"], kz81["soll"]), (Decimal("0.00"), Decimal("0.00")))
		self.assertEqual(kz820["label"], form.catalogue_for(YEAR).field(form.KZ_820).label)
		self.assertEqual(
			(kz820["filed"], kz820["annual"], kz820["late"], kz820["unfiled"], kz820["rest"]),
			(Decimal("0.00"), Decimal("209.00"), Decimal("19.00"), Decimal("190.00"), Decimal("0.00")),
		)
		self.assertTrue(
			all(
				value == value.quantize(Decimal("0.01"))
				for value in kz820.values()
				if isinstance(value, Decimal)
			)
		)


class FindingsTest(TestCase):
	def test_an_error_for_a_verprobung_that_fails_and_an_account_watched_at_the_blocking_level(self):
		lines = [
			line("8400", credit="1000", voucher="Sales Invoice:R1"),
			line("1776", credit="180", voucher="Sales Invoice:R1"),
			line("1548", debit="50", voucher="Journal Entry:J1"),
		]
		found = bridge.own_findings(calculate(lines, SPLIT), SPLIT)
		self.assertEqual(
			[(finding.code, finding.severity, finding.template, finding.values) for finding in found],
			[
				("SB-VERPROBUNG", form.Severity.ERROR, VERPROBUNG, ("Umsatzsteuer 19 %", 1, "-10.00")),
				("SB-KONTO-SPERRT", form.Severity.ERROR, BLOCKED, ("1548", YEAR)),
			],
		)

	def test_a_hint_for_an_account_watched_for_a_hint_that_no_line_reads(self):
		lines = [
			line("8603", credit="70", voucher="Journal Entry:J1"),
			line("3552", debit="40", voucher="Purchase Invoice:E1"),
		]
		found = bridge.own_findings(calculate(lines, SPLIT), SPLIT)
		self.assertEqual(
			[(finding.code, finding.severity, finding.values) for finding in found],
			[("SB-KONTO-HINWEIS", form.Severity.HINT, ("8603", "-70.00", YEAR))],
		)
		self.assertEqual(found[0].template, WATCHED)

	def test_a_hinted_account_without_a_balance_gives_none(self):
		lines = [
			line("8603", credit="70", voucher="Journal Entry:J1"),
			line("8603", debit="70", voucher="Journal Entry:J2"),
		]
		self.assertEqual(bridge.own_findings(calculate(lines, SPLIT), SPLIT), ())

	def test_a_hint_in_a_year_of_a_kleinunternehmer(self):
		found = bridge.own_findings(calculate([], SPLIT), SPLIT, kleinunternehmer=True)
		self.assertEqual(
			[(finding.code, finding.severity, finding.template, finding.values) for finding in found],
			[("SB-KLEINUNTERNEHMER", form.Severity.HINT, KLEINUNTERNEHMER, (YEAR,))],
		)

	def test_turns_every_finding_of_the_core_into_a_row_of_befunde_in_the_words_given(self):
		found = [
			form.Finding(
				"30639", form.Severity.ERROR, "{0} in line {1}.", ("Kz 177", 24), ("E3003303", "E3003304")
			),
			form.Finding("SB-KLEINUNTERNEHMER", form.Severity.HINT, "Kein {0}.", (YEAR,)),
		]
		rows = bridge.findings(found, lambda template: template.replace("in line", "in Zeile"))
		self.assertEqual(
			[(finding.code, finding.severity, finding.text, finding.reference) for finding in rows],
			[
				("30639", Severity.ERROR, "Kz 177 in Zeile 24.", "E3003303, E3003304"),
				("SB-KLEINUNTERNEHMER", Severity.HINT, "Kein 2026.", ""),
			],
		)

	def test_names_as_many_fields_as_the_reference_holds(self):
		fields = [f"E30{index:05d}" for index in range(40)]
		text = bridge.reference(fields)
		self.assertLessEqual(len(text), DATA_LENGTH)
		self.assertTrue(text.startswith("E3000000, E3000001, "))
		self.assertTrue(text.endswith(", …"))
		self.assertEqual(bridge.reference(fields[:3]), "E3000000, E3000001, E3000002")

	def test_a_hint_where_kz_136_names_another_day_of_the_switch_than_kz_70_of_the_voranmeldungen(self):
		switch = date(2026, 4, 1)
		self.assertEqual(bridge.switch_findings(YEAR, None, None), ())
		self.assertEqual(bridge.switch_findings(YEAR, switch, switch), ())
		(missing,) = bridge.switch_findings(YEAR, switch, None)
		self.assertEqual(
			(missing.code, missing.severity, missing.template, missing.values),
			("SB-KZ136", form.Severity.HINT, SWITCH_MISSING, (YEAR, "01.04.2026")),
		)
		(other,) = bridge.switch_findings(YEAR, switch, date(2026, 5, 1))
		self.assertEqual((other.template, other.values), (SWITCH_OTHER, (YEAR, "01.04.2026", "01.05.2026")))

	def test_every_message_is_a_template_of_its_own(self):
		self.assertEqual(
			MESSAGES, (VERPROBUNG, BLOCKED, WATCHED, KLEINUNTERNEHMER, SWITCH_MISSING, SWITCH_OTHER)
		)
		self.assertEqual(len(set(MESSAGES)), len(MESSAGES))


class AmountsTest(TestCase):
	def test_keeps_the_sums_kz_816_line_125_and_kz_820_and_zero_for_a_sum_not_filed(self):
		amounts = {
			"E3006001": Decimal("190.00"),
			"E3011101": Decimal("95"),
			"E3011301": Decimal("50"),
			"E3011401": Decimal("45"),
		}
		sums = bridge.sums(amounts)
		self.assertEqual(
			(sums["line_41"], sums["kz816"], sums["vorauszahlungssoll"], sums["kz820"], sums["line_93"]),
			(Decimal("190.00"), Decimal("95"), Decimal("50"), Decimal("45"), Decimal("0")),
		)
		self.assertEqual(set(sums), set(bridge.SUM_FIELDS))

	def test_files_the_amounts_of_the_lines_with_the_paragraph_of_each_line_with_an_amount(self):
		rows = [
			row("E3003303", "1000"),
			row("E3003304", "190.00"),
			row("E3104502", "500", paragraph="4 Nummer 8 Buchstabe a"),
			row("E3103902", "0", paragraph="4 Nummer 2"),
			row("E3104902", manual=1, correction=10, correction_reason=REASON, paragraph="4 Nummer 14"),
		]
		values = bridge.filed_values(YEAR, rows, Decimal("100.00"), {"E3000901": "Muster GmbH"})
		self.assertEqual(values["E3104501"], "4 Nummer 8 Buchstabe a")
		self.assertNotIn("E3103901", values)
		self.assertNotIn("E3104901", values)
		self.assertEqual(
			(values["E3003303"], values["E3011101"], values["E3011301"], values["E3011401"]),
			(Decimal("1000.00"), Decimal("190.00"), Decimal("100.00"), Decimal("90.00")),
		)
		self.assertEqual(values["E3000901"], "Muster GmbH")

	def test_a_line_without_a_paragraph_field_adds_no_text(self):
		values = bridge.filed_values(YEAR, [row("E3003303", "1000", paragraph="ohne Feld")], Decimal("0"))
		self.assertEqual([element for element, value in values.items() if isinstance(value, str)], [])

	def test_an_amount_the_form_does_not_take_is_refused(self):
		with self.assertRaises(CalculationError):
			bridge.filed_values(YEAR, [row("E3003303", "1000.50")], Decimal("0"))


class DetailsTest(TestCase):
	COMPANY = Company(
		name=" Muster  GmbH ",
		wid_nr="DE123456789",
		business_purpose="Softwareentwicklung",
		address=Address(
			street="Musterweg",
			house_number="12",
			house_number_suffix="a",
			supplement="Hinterhaus",
			postal_code="80331",
			city="München",
		),
		phone="089 1234567",
		email="buchhaltung@example.org",
	)

	def test_section_a_comes_from_the_company_and_kz_133_files_the_soll_versteuerung(self):
		values = bridge.details(YEAR, self.COMPANY, {})
		self.assertEqual(
			values,
			{
				"E3000401": "DE123456789",
				"E3000901": "Muster GmbH",
				"E3001001": "Softwareentwicklung",
				"E3001101": "Musterweg",
				"E3001203": "12",
				"E3001204": "a",
				"E3001205": "Hinterhaus",
				"E3001206": "80331",
				"E3001207": "München",
				"E3001202": "089 1234567",
				"E3001301": "buchhaltung@example.org",
				"E3002203": "1",
			},
		)

	def test_a_company_without_details_files_its_name_and_kz_133(self):
		self.assertEqual(
			bridge.details(YEAR, Company("Muster GmbH"), {}), {"E3000901": "Muster GmbH", "E3002203": "1"}
		)

	def test_files_no_postal_code_of_an_address_abroad(self):
		company = Company(
			"Muster GmbH",
			address=Address(
				street="Ringstraße", house_number="1", postal_code="1010", city="Wien", country="Austria"
			),
		)
		values = bridge.details(YEAR, company, {})
		self.assertNotIn("E3001206", values)
		self.assertEqual(values["E3001207"], "Wien")

	def test_a_berichtigung_files_kz_110(self):
		self.assertIs(bridge.details(YEAR, Company("Muster GmbH"), {}, correction=True)["E3000601"], True)

	def test_line_19_files_the_part_of_the_year_after_the_company_began(self):
		values = bridge.details(YEAR, Company("Muster GmbH"), {}, began=date(2026, 5, 4))
		self.assertEqual(values["E3001401"], (date(2026, 5, 4), date(2026, 12, 31)))
		for began in (date(2026, 1, 1), date(2020, 3, 1), date(2027, 2, 1)):
			with self.subTest(began=began):
				self.assertNotIn("E3001401", bridge.details(YEAR, Company("Muster GmbH"), {}, began=began))

	def test_files_the_statements_of_the_document(self):
		statements = {
			"kz129": 1,
			"kz370": 0,
			"change_by_sale": 1,
			"kz500": "2",
			"kz500_text": "  Abweichende\nRechtsauffassung ",
			"change_reason": " ",
			"kz136": date(2026, 4, 1),
		}
		values = bridge.details(YEAR, Company("Muster GmbH"), statements)
		self.assertEqual(
			{
				element: values[element]
				for element in ("E3001701", "E3007801", "E3002201", "E3002202", "E3001601")
			},
			{
				"E3001701": True,
				"E3007801": True,
				"E3002201": "2",
				"E3002202": "Abweichende Rechtsauffassung",
				"E3001601": date(2026, 4, 1),
			},
		)
		for element in ("E3007301", "E3008402"):
			with self.subTest(element=element):
				self.assertNotIn(element, values)

	def test_a_year_with_a_steuerberatung_files_the_mitwirkung_of_lines_127_to_129(self):
		advisor = Advisor(
			name="Steuerkanzlei Beispiel",
			first_name=None,
			street="Kanzleiweg 2",
			town="80331 München",
			client_number="4711",
		)
		values = bridge.details(YEAR, Company("Muster GmbH"), {}, advisor=advisor)
		self.assertEqual(
			{
				element: value
				for element, value in values.items()
				if element.startswith("E30025") or element == "E3002602"
			},
			{
				"E3002602": True,
				"E3002506": "4711",
				"E3002501": "Steuerkanzlei Beispiel",
				"E3002503": "Kanzleiweg 2",
				"E3002504": "80331 München",
			},
		)

	def test_every_statement_field_names_a_field_of_the_form(self):
		catalogue = form.catalogue_for(YEAR)
		for element in (*bridge.FLAGS.values(), *bridge.TEXTS.values(), bridge.KZ_110, bridge.KZ_133):
			with self.subTest(element=element):
				catalogue.field(element)
		self.assertEqual(bridge.STATEMENT_FIELDS, (*bridge.FLAGS, *bridge.TEXTS))


class GrundstueckeTest(TestCase):
	def test_reads_each_grundstueck_by_the_feldkennungen_of_line_95(self):
		rows = [
			{
				"location": " Musterweg 12,\n80331 München ",
				"first_use": date(2026, 3, 1),
				"kind_of_use": "steuerpflichtige Vermietung",
				"extent_of_use": 60.0,
				"input_tax_total": 19000,
				"input_tax_deducted": 0,
			},
			{
				"location": "",
				"first_use": None,
				"kind_of_use": None,
				"extent_of_use": 0,
				"input_tax_total": None,
				"input_tax_deducted": None,
			},
		]
		self.assertEqual(
			bridge.grundstuecke(rows),
			(
				{
					"E3007401": "Musterweg 12, 80331 München",
					"E3007402": date(2026, 3, 1),
					"E3007403": "steuerpflichtige Vermietung",
					"E3007404": Decimal("60.0"),
					"E3007405": Decimal("19000"),
				},
			),
		)

	def test_reads_the_day_of_the_first_use_from_the_text_of_a_date_field(self):
		(grundstueck,) = bridge.grundstuecke([{"location": "Musterweg 12", "first_use": "2026-03-01"}])
		self.assertEqual(grundstueck["E3007402"], date(2026, 3, 1))

	def test_takes_what_the_xml_takes(self):
		bridge.check_grundstuecke(
			YEAR,
			bridge.grundstuecke(
				[{"location": "Musterweg 12", "extent_of_use": 60, "input_tax_total": 19000}]
			),
		)

	def test_refuses_more_than_99_grundstuecke(self):
		with self.assertRaises(XmlError) as caught:
			bridge.check_grundstuecke(YEAR, [{"E3007401": "Musterweg"}] * 100)
		self.assertEqual(caught.exception.values, (99, 100))

	def test_refuses_cents_where_the_form_takes_whole_euros(self):
		with self.assertRaises(XmlError):
			bridge.check_grundstuecke(YEAR, [{"E3007405": Decimal("100.50")}])

	def test_refuses_a_value_the_pattern_of_its_field_does_not_take(self):
		"""The extent takes 15 digits as a number, but its pattern only 16 characters with the cents."""
		with self.assertRaises(XmlError) as caught:
			bridge.check_grundstuecke(YEAR, [{"E3007404": Decimal("12345678901234")}])
		self.assertEqual(caught.exception.values, ("12345678901234,00",))


class InputsTest(TestCase):
	def test_the_same_inputs_compare_equal_whatever_form_their_values_take(self):
		before = bridge.inputs(
			{"kz129": "1", "kz500_text": "Text"},
			[
				{"feldkennung": "E3103902", "manual": 1, "paragraph": "4 Nummer 2"},
				{"feldkennung": "E3003303"},
			],
			[{"period_code": "01", "waiver_reason": "Grund"}],
			[
				{
					"location": "Musterweg",
					"first_use": date(2026, 3, 1),
					"extent_of_use": 60.0,
					"input_tax_total": 19000,
				}
			],
		)
		after = bridge.inputs(
			{"kz500_text": " Text ", "kz129": "1"},
			[
				{"feldkennung": "E3003303", "paragraph": "anders"},
				{"feldkennung": "E3103902", "manual": 1, "paragraph": "4  Nummer 2"},
			],
			[{"period_code": "01", "waiver_reason": " Grund "}],
			[
				{
					"location": "Musterweg",
					"first_use": "2026-03-01",
					"extent_of_use": "60",
					"input_tax_total": "19000.00",
				}
			],
		)
		self.assertEqual(before, after)

	def test_a_change_of_a_statement_a_paragraph_by_hand_a_reason_or_a_grundstueck_differs(self):
		base = ({"kz129": "0"}, [{"feldkennung": "E3103902", "manual": 1, "paragraph": "4 Nummer 2"}], [], [])
		for changed in (
			({"kz129": "1"}, *base[1:]),
			(base[0], [{"feldkennung": "E3103902", "manual": 1, "paragraph": "4 Nummer 3"}], [], []),
			(*base[:2], [{"period_code": "02", "waiver_reason": "Grund"}], []),
			(*base[:3], [{"location": "Musterweg"}]),
		):
			with self.subTest(changed=changed):
				self.assertNotEqual(bridge.inputs(*base), bridge.inputs(*changed))


class LedgerTest(TestCase):
	def test_names_each_journal_entry_by_its_name_for_the_hints(self):
		lines = [
			line("1776", debit="10", voucher="Journal Entry:ACC-JV-2026-00001"),
			line("8400", credit="10", voucher="Sales Invoice:SINV-1"),
			line("1576", debit="5"),
		]
		named, vouchers = bridge.journal_entry_lines(lines)
		self.assertEqual(
			[entry.voucher for entry in named], ["ACC-JV-2026-00001", "Sales Invoice:SINV-1", None]
		)
		self.assertEqual(vouchers, frozenset({"ACC-JV-2026-00001"}))

	def test_reads_the_payments_on_the_accounts_of_the_chart(self):
		self.assertEqual(bridge.payment_accounts("SKR03"), ("1780", "1781"))
		self.assertEqual(bridge.payment_accounts("SKR04"), ("3820", "3830"))
		self.assertEqual(bridge.payment_accounts("Eigener Kontenrahmen"), ())
		lines = [
			line("1780", debit="1190.00", voucher="Journal Entry:J1"),
			line("1781", debit="1100.00", voucher="Journal Entry:J2"),
			line("1780", credit="40.00", voucher="Journal Entry:J3"),
			line("1200", credit="2250.00", voucher="Journal Entry:J1"),
		]
		self.assertEqual(bridge.paid(lines, ("1780", "1781")), Decimal("2250.00"))
		self.assertIsNone(bridge.paid(lines, ()))
