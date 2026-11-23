"""The annual return against the filed Voranmeldungen: period by period and Kennzahl by Kennzahl."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.ustjahr.calculation import ManualLine, calculate, entries
from steuerbote.ustjahr.form import KZ_816, KZ_820, Finding, Severity
from steuerbote.ustjahr.reconciliation import (
	INVOICE,
	JOURNAL_ENTRY,
	LATE,
	MESSAGES,
	NO_RUN,
	OTHER_YEAR,
	REST,
	REST_OF_KZ_820,
	Cause,
	ReconciliationError,
	journal_entries,
	reconcile,
)
from steuerbote.ustjahr.soll import Filed, FiledKennzahl, Override, vorauszahlungssoll
from steuerbote.ustjahr.split import AnnualRule, split
from steuerbote.ustva import calculate as calculate_ustva
from steuerbote.ustva.calculation import LedgerLine, UstvaResult
from steuerbote.ustva.mapping import AccountRule, Mapping, Side, TaxCheck
from steuerbote.ustva.period import Period
from steuerbote.ustva.rounding import ZERO, tax_from_base, to_cents

RATE_19 = Decimal("19")
MONTHS = tuple(Period.month(2026, month) for month in range(1, 13))
MAPPING = Mapping(
	"test",
	(
		AccountRule("8400", "81", Side.CREDIT),
		AccountRule("8125", "41", Side.CREDIT),
		AccountRule("3123", "46", Side.DEBIT, RATE_19),
		AccountRule("1576", "66", Side.DEBIT),
		AccountRule("1577", "67", Side.DEBIT),
		AccountRule("1558", "64", Side.DEBIT),
		AccountRule("1794", "69", Side.CREDIT),
	),
	checks=(TaxCheck("Umsatzsteuer 19 %", ("8400",), ("1776",)), TaxCheck("§ 13b", ("3123",), ("1787",))),
	watched=("1769",),
)
SPLIT = split(
	MAPPING, role_defaults={"1558": "E3008701"}, annual_rules=(AnnualRule("1769", "E3102805", Side.CREDIT),)
)


def line(account: str, debit: str = "0", credit: str = "0", voucher: str | None = None) -> LedgerLine:
	return LedgerLine(account, Decimal(debit), Decimal(credit), voucher)


def month(index: int, base: str = "1000.40", input_tax: str = "95.00") -> list[LedgerLine]:
	tax = tax_from_base(Decimal(base), RATE_19)
	voucher = f"R{index}"
	return [
		line("8400", credit=base, voucher=voucher),
		line("1776", credit=str(tax), voucher=voucher),
		line("1576", debit=input_tax, voucher=f"E{index}"),
	]


def filing(period: Period, lines: list[LedgerLine], corrections: dict[str, Decimal] | None = None) -> Filed:
	"""The Voranmeldung of a period as it was filed from its ledger then, with the corrections of the company."""
	result = calculate_ustva(lines, MAPPING)
	corrected = corrections or {}
	kennzahlen = {
		number: FiledKennzahl(value.amount, value.reported, corrected.get(number, value.reported))
		for number, value in result.values.items()
	}
	return Filed(period, f"UStVA-{period.code}", kennzahlen["83"].final, lines=kennzahlen)


class Year:
	"""A year of twelve Voranmeldungen: the ledger when each was filed, and today's ledger."""

	def __init__(self, base: str = "1000.40") -> None:
		self.filed_lines = {period: month(period.index, base) for period in MONTHS}
		self.today = {period: list(lines) for period, lines in self.filed_lines.items()}

	def post(self, period: Period, *lines: LedgerLine) -> None:
		self.today[period].extend(lines)

	def filings(self, corrections: dict[Period, dict[str, Decimal]] | None = None) -> list[Filed]:
		return [
			filing(period, self.filed_lines[period], (corrections or {}).get(period)) for period in MONTHS
		]

	def now(self) -> dict[Period, UstvaResult]:
		return {period: calculate_ustva(lines, MAPPING) for period, lines in self.today.items()}

	def lines(self) -> list[LedgerLine]:
		return [line for lines in self.today.values() for line in lines]


def reconciled(year: Year, filed: list[Filed] | None = None, **kwargs: object):
	filed = year.filings() if filed is None else filed
	soll = vorauszahlungssoll(2026, filed, MONTHS)
	result = calculate(year.lines(), SPLIT, kwargs.pop("manual", ()))  # type: ignore[arg-type]
	return result, soll, reconcile(result, soll, year.now(), **kwargs)  # type: ignore[arg-type]


class AgreementTest(TestCase):
	def test_a_year_as_filed_differs_from_its_voranmeldungen_only_by_rounding(self):
		year = Year()
		_result, _soll, recon = reconciled(year)
		self.assertTrue(recon.ready)
		self.assertEqual([period.cause for period in recon.periods], [Cause.NONE] * 12)
		kz81 = recon.kennzahl("81")
		self.assertEqual(
			(kz81.filed, kz81.filed_ledger, kz81.ledger_now, kz81.annual),
			(Decimal("12000"), Decimal("12004.80"), Decimal("12004.80"), Decimal("12004")),
		)
		self.assertEqual(
			(kz81.late, kz81.corrections, kz81.rounding, kz81.annual_only, kz81.rest),
			(ZERO, ZERO, Decimal("4"), ZERO, ZERO),
		)
		self.assertEqual(kz81.difference, Decimal("4"))

	def test_kz_820_is_explained_by_the_rounding_of_the_year(self):
		year = Year()
		result, soll, recon = reconciled(year)
		filed = entries(SPLIT.catalogue, result.reported, soll.amount)
		balance = recon.balance
		self.assertEqual(balance.kz820, filed[KZ_820])
		self.assertEqual(balance.kz820, filed[KZ_816] - soll.amount)
		self.assertEqual(
			(balance.late, balance.corrections, balance.unfiled, balance.sondervorauszahlung, balance.soll),
			(ZERO, ZERO, ZERO, ZERO, ZERO),
		)
		self.assertEqual((balance.rounding, balance.annual_only, balance.rest), (balance.kz820, ZERO, ZERO))

	def test_twelve_months_of_99_cents_explain_2_26_euros_by_rounding(self):
		year = Year(base="100.99")
		for period in MONTHS:
			year.filed_lines[period] = [
				entry for entry in year.filed_lines[period] if entry.account_number != "1576"
			]
			year.today[period] = list(year.filed_lines[period])
		_result, soll, recon = reconciled(year)
		self.assertEqual(soll.amount, Decimal("228.00"))
		self.assertEqual(
			(recon.balance.kz820, recon.balance.rounding, recon.balance.rest),
			(Decimal("2.26"), Decimal("2.26"), ZERO),
		)
		self.assertEqual(recon.kennzahl("81").rounding, Decimal("11"))


class LatePostingTest(TestCase):
	def test_a_posting_after_the_filing_shows_in_its_period_and_kennzahl(self):
		year = Year()
		year.post(
			MONTHS[2],
			line("8400", credit="100.00", voucher="R3b"),
			line("1776", credit="19.00", voucher="R3b"),
		)
		_result, _soll, recon = reconciled(year)
		march = recon.periods[2]
		self.assertEqual(
			(march.period, march.vat_return, march.late, march.corrections, march.cause),
			(MONTHS[2], "UStVA-03", Decimal("19.00"), ZERO, Cause.LATE_POSTINGS),
		)
		self.assertEqual(march.difference, Decimal("19.00"))
		self.assertEqual(recon.kennzahl("81").late, Decimal("100.00"))
		self.assertEqual(recon.balance.late, Decimal("19.00"))
		self.assertEqual((recon.kennzahl("81").rest, recon.balance.rest), (ZERO, ZERO))
		self.assertIn(
			Finding("BUCHUNG-NACH-ABGABE", Severity.HINT, LATE, ("März 2026", "19.00")), recon.findings
		)
		self.assertTrue(recon.ready)

	def test_a_correction_of_the_voranmeldung_the_books_never_got(self):
		year = Year()
		filed = year.filings({MONTHS[4]: {"66": Decimal("100.00"), "83": Decimal("90.00")}})
		_result, _soll, recon = reconciled(year, filed)
		may = recon.periods[4]
		self.assertEqual((may.kz83, may.kz83_now, may.late), (Decimal("90.00"), Decimal("95.00"), ZERO))
		self.assertEqual((may.corrections, may.cause), (Decimal("5.00"), Cause.CORRECTIONS))
		self.assertEqual(recon.kennzahl("66").corrections, Decimal("-5.00"))
		self.assertEqual((recon.balance.corrections, recon.balance.rest), (Decimal("5.00"), ZERO))

	def test_both_causes_together(self):
		year = Year()
		year.post(MONTHS[0], line("1576", debit="10.00", voucher="E1b"))
		filed = year.filings({MONTHS[0]: {"83": Decimal("100.00")}})
		_result, _soll, recon = reconciled(year, filed)
		self.assertIs(recon.periods[0].cause, Cause.LATE_POSTINGS_AND_CORRECTIONS)


class UnfiledTest(TestCase):
	def test_a_period_without_a_filed_voranmeldung_shows_as_not_filed(self):
		year = Year()
		filed = year.filings()[:-1]
		_result, _soll, recon = reconciled(year, filed)
		december = recon.periods[-1]
		self.assertEqual((december.vat_return, december.kz83, december.cause), (None, ZERO, Cause.NOT_FILED))
		self.assertEqual(december.kz83_now, year.now()[MONTHS[-1]].kz83)
		self.assertEqual(recon.kennzahl("81").unfiled, Decimal("1000.40"))
		self.assertEqual(recon.balance.unfiled, year.now()[MONTHS[-1]].prepayment)
		self.assertEqual((recon.kennzahl("81").rest, recon.balance.rest), (ZERO, ZERO))


class AnnualOnlyTest(TestCase):
	def test_accounts_only_the_annual_return_reads_and_lines_by_hand(self):
		year = Year()
		year.post(MONTHS[5], line("1769", credit="76.00", voucher="A1"))
		manual = (ManualLine("E3008701", Decimal("300.00"), "§ 44 Absatz 3 UStDV"),)
		_result, _soll, recon = reconciled(year, manual=manual)
		self.assertEqual(recon.kennzahl("69").annual_only, Decimal("76.00"))
		self.assertEqual(recon.kennzahl("64").annual_only, Decimal("300.00"))
		self.assertEqual(recon.balance.annual_only, Decimal("-224.00"))
		self.assertTrue(recon.ready)

	def test_corrections_of_the_annual_return_count_with_the_annual_only_amounts(self):
		year = Year()
		result = calculate(year.lines(), SPLIT)
		soll = vorauszahlungssoll(2026, year.filings(), MONTHS)
		reported = {**result.reported, "E3006201": result.reported["E3006201"] + Decimal("10.00")}
		recon = reconcile(result, soll, year.now(), reported)
		self.assertEqual(recon.kennzahl("66").annual_only, Decimal("10.00"))
		self.assertEqual(recon.balance.annual_only, Decimal("-10.00"))
		self.assertEqual(recon.balance.kz820, entries(SPLIT.catalogue, reported, soll.amount)[KZ_820])


class SollTest(TestCase):
	def test_an_overridden_soll_and_a_sondervorauszahlung_not_credited(self):
		year = Year()
		filed = year.filings()
		soll = vorauszahlungssoll(
			2026, filed, MONTHS, Decimal("50.00"), override=Override(Decimal("1000.00"), "Bescheid")
		)
		result = calculate(year.lines(), SPLIT)
		recon = reconcile(result, soll, year.now())
		self.assertEqual(recon.balance.sondervorauszahlung, Decimal("-50.00"))
		self.assertEqual(recon.balance.soll, soll.computed - Decimal("1000.00"))
		self.assertEqual(recon.balance.rest, ZERO)


class RestTest(TestCase):
	def test_a_ledger_the_periods_do_not_explain_leaves_a_rest_that_blocks(self):
		year = Year()
		result = calculate(
			[
				*year.lines(),
				line("8400", credit="50.00", voucher="X"),
				line("1776", credit="9.50", voucher="X"),
			],
			SPLIT,
		)
		soll = vorauszahlungssoll(2026, year.filings(), MONTHS)
		recon = reconcile(result, soll, year.now())
		self.assertEqual((recon.kennzahl("81").rest, recon.balance.rest), (Decimal("50.00"), Decimal("9.50")))
		self.assertFalse(recon.ready)
		self.assertIn(Finding("ABGLEICH-REST", Severity.ERROR, REST, ("81", "50.00")), recon.findings)
		self.assertIn(Finding("ABGLEICH-REST", Severity.ERROR, REST_OF_KZ_820, ("9.50",)), recon.findings)


class KennzahlenTest(TestCase):
	def test_lists_every_kennzahl_with_an_amount_in_the_order_of_the_voranmeldung(self):
		year = Year()
		year.post(MONTHS[1], line("8125", credit="500.00", voucher="R2b"))
		_result, _soll, recon = reconciled(year)
		self.assertEqual([kennzahl.kennzahl for kennzahl in recon.kennzahlen], ["81", "41", "66"])
		with self.assertRaises(KeyError):
			recon.kennzahl("46")

	def test_a_tax_derived_per_voucher_reconciles_with_its_kennzahl(self):
		year = Year()
		for index, period in enumerate(MONTHS[:3]):
			year.filed_lines[period] += [
				line("3123", debit="33.33", voucher=f"S{index}"),
				line("1787", credit="6.33", voucher=f"S{index}"),
			]
			year.today[period] = list(year.filed_lines[period])
		_result, _soll, recon = reconciled(year)
		self.assertEqual(
			(recon.kennzahl("47").filed, recon.kennzahl("47").annual), (Decimal("18.99"), Decimal("18.99"))
		)
		self.assertEqual(recon.kennzahl("47").rest, ZERO)


class HintsTest(TestCase):
	def test_hints_that_the_posting_date_stands_in_for_the_invoice(self):
		"""§ 15 Absatz 1 Satz 1 Nummer 1 Satz 2 UStG: the deduction „setzt voraus, dass der Unternehmer eine nach
		den §§ 14, 14a ausgestellte Rechnung besitzt“."""
		_result, _soll, recon = reconciled(Year())
		self.assertIn(
			Finding("VORSTEUER-RECHNUNG", Severity.HINT, INVOICE, (2026,), ("E3006201",)), recon.findings
		)

	def test_no_hint_on_the_invoices_without_vorsteuer(self):
		year = Year()
		for period in MONTHS:
			year.filed_lines[period] = [
				entry for entry in year.filed_lines[period] if entry.account_number != "1576"
			]
			year.today[period] = list(year.filed_lines[period])
		_result, _soll, recon = reconciled(year)
		self.assertNotIn("VORSTEUER-RECHNUNG", [finding.code for finding in recon.findings])


class JournalEntriesTest(TestCase):
	"""A Journal Entry on a tax account without the flag Exclude from VAT Return changes the annual return."""

	def test_hints_at_journal_entries_on_the_tax_accounts(self):
		lines = [
			line("1576", credit="1140.00", voucher="Journal Entry:JV-1"),
			line("1790", debit="1140.00", voucher="Journal Entry:JV-1"),
			line("1776", debit="12.00", voucher="Journal Entry:JV-2"),
			line("1776", debit="5.00", voucher="Journal Entry:JV-2"),
			line("8400", debit="100.00", voucher="Journal Entry:JV-3"),
			line("1576", debit="10.00", voucher="Purchase Invoice:PI-1"),
		]
		found = journal_entries(
			2026, lines, MAPPING, {"Journal Entry:JV-1", "Journal Entry:JV-2", "Journal Entry:JV-3"}
		)
		self.assertEqual(
			found,
			(
				Finding(
					"JOURNALBUCHUNG-STEUERKONTO",
					Severity.HINT,
					JOURNAL_ENTRY,
					("Journal Entry:JV-1", 2026, "1576", "-1140.00"),
				),
				Finding(
					"JOURNALBUCHUNG-STEUERKONTO",
					Severity.HINT,
					JOURNAL_ENTRY,
					("Journal Entry:JV-2", 2026, "1776", "17.00"),
				),
			),
		)

	def test_no_hint_without_journal_entries(self):
		self.assertEqual(journal_entries(2026, [line("1576", debit="1.00", voucher="JV")], MAPPING, ()), ())


class InputTest(TestCase):
	def test_every_filed_period_needs_its_run_on_todays_ledger(self):
		year = Year()
		result = calculate(year.lines(), SPLIT)
		soll = vorauszahlungssoll(2026, year.filings(), MONTHS)
		now = year.now()
		del now[MONTHS[3]]
		with self.assertRaises(ReconciliationError) as caught:
			reconcile(result, soll, now)
		self.assertEqual((caught.exception.template, caught.exception.values), (NO_RUN, ("April 2026",)))

	def test_refuses_a_run_of_another_year(self):
		year = Year()
		result = calculate(year.lines(), SPLIT)
		soll = vorauszahlungssoll(2026, year.filings(), MONTHS)
		now = {**year.now(), Period.month(2027, 1): calculate_ustva([], MAPPING)}
		with self.assertRaises(ReconciliationError) as caught:
			reconcile(result, soll, now)
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (OTHER_YEAR, ("Januar 2027", 2026))
		)


class PartsTest(TestCase):
	"""Every difference is the sum of its parts, exactly, whatever the year holds."""

	def test_the_parts_add_up_to_the_difference(self):
		year = Year(base="333.33")
		year.post(
			MONTHS[2], line("8400", credit="100.01", voucher="L1"), line("1776", credit="19.00", voucher="L1")
		)
		year.post(
			MONTHS[5], line("1769", credit="76.00", voucher="A1"), line("1576", debit="0.99", voucher="L2")
		)
		filed = year.filings({MONTHS[4]: {"66": Decimal("100.00"), "83": Decimal("-36.67")}})[:-1]
		soll = vorauszahlungssoll(
			2026, filed, MONTHS, Decimal("10.00"), override=Override(Decimal("500.00"), "Bescheid")
		)
		manual = (ManualLine("E3003303", Decimal("12.34"), "a sale the books lack"),)
		result = calculate([*year.lines(), line("8400", credit="7.77", voucher="X")], SPLIT, manual)
		reported = {**result.reported, "E3006201": result.reported["E3006201"] + Decimal("1.00")}
		recon = reconcile(result, soll, year.now(), reported)
		for kennzahl in recon.kennzahlen:
			with self.subTest(kennzahl=kennzahl.kennzahl):
				parts = (
					kennzahl.late,
					kennzahl.corrections,
					kennzahl.unfiled,
					kennzahl.rounding,
					kennzahl.annual_only,
					kennzahl.rest,
				)
				self.assertEqual(sum(parts, ZERO), kennzahl.difference)
		balance = recon.balance
		parts = (
			balance.late,
			balance.corrections,
			balance.unfiled,
			balance.sondervorauszahlung,
			balance.soll,
			balance.rounding,
			balance.annual_only,
			balance.rest,
		)
		self.assertEqual(sum(parts, ZERO), balance.kz820)
		self.assertEqual(
			(recon.kennzahl("81").rest, to_cents(balance.rest)), (Decimal("7.77"), Decimal("1.48"))
		)
		for period in recon.periods:
			with self.subTest(period=period.period.label):
				expected = period.late + period.corrections if period.vat_return else period.kz83_now
				self.assertEqual(period.difference, expected)


class MessagesTest(TestCase):
	def test_lists_every_template_once_for_the_translations(self):
		self.assertEqual(MESSAGES, (NO_RUN, OTHER_YEAR, LATE, REST, REST_OF_KZ_820, INVOICE, JOURNAL_ENTRY))

	def test_an_error_keeps_template_and_values_apart(self):
		error = ReconciliationError(NO_RUN, "April 2026")
		self.assertEqual(
			(error.template, error.values, str(error)), (NO_RUN, ("April 2026",), NO_RUN.format("April 2026"))
		)
		self.assertIsInstance(error, ValueError)
