"""The bridge between the Corporate Income Tax Return and the core of the Körperschaftsteuer, without a bench: the
worked example „Muster IT GmbH“ of the research of stage 3 (steuerbote/kst/tests/test_golden.py) through the rows of
the DocTypes, and each rule of the bridge on invented figures."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from steuerbote.elster.erklaerung import Field
from steuerbote.elster.ustva_xml import XmlError
from steuerbote.jahresmeldung.findings import Severity
from steuerbote.kst.categories import AccountRule, Category, Mapping
from steuerbote.kst.form import Entry, Vordruck, catalogue_for
from steuerbote.kst.provisions import ACCOUNTS
from steuerbote.kst.tests.support import FIGURES, credit, debit
from steuerbote.kst.tests.test_golden import LEDGER, MAPPING
from steuerbote.steuerbote.doctype.annual_filing_settings import rules
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge
from steuerbote.steuerbote.doctype.corporate_income_tax_return.bridge import (
	CARRY_BACK_WITHOUT_LOSS,
	CONTRACTS,
	DETAILS_MISSING,
	HOLDING_WITHOUT_SHARE,
	NO_RECEIPTS,
	NO_SETTINGS,
	NO_SINGLE_VALUES,
	NO_UEBERLEITUNG,
	NOT_IN_EUROS,
	NUTZDATEN,
	PREPAYMENTS,
	PROVISIONAL,
	RECEIPTS_DIFFER,
	SHARES,
	UNCONFIRMED,
	UNKNOWN,
	UNKNOWN_HOLDING,
	UNMAPPED,
	UNNUMBERED,
	BridgeError,
	Posting,
)

YEAR = 2026
FROM, TO = date(2026, 1, 1), date(2026, 12, 31)
ZERO = Decimal("0")
BOOKED = {"KSt": Decimal("10000.00"), "SolZ": Decimal("550.00"), "GewSt": Decimal("15000.00")}
REASON = "Überleitung: Rückstellung für Prozesskosten nur in der Handelsbilanz"


def translate(text: str) -> str:
	"""The texts as the bridge writes them; the Frappe layer translates them."""
	return text


def ledger(*extra, booked: dict | None = None, unnumbered=()) -> bridge.Ledger:
	lines = (*LEDGER, *extra)
	return bridge.Ledger(
		lines,
		sum((line.credit - line.debit for line in lines), ZERO),
		unnumbered,
		BOOKED if booked is None else booked,
	)


def shareholder(
	row: int = 1, name: str = "Erika Muster", percent: str = "100", **values
) -> rules.Shareholder:
	values = {"from_date": date(2020, 1, 1), **values}
	return rules.Shareholder(
		row,
		name,
		"Natural Person",
		Decimal("25000"),
		Decimal(percent),
		street="Musterweg 2",
		postal_code_and_town="12345 Musterstadt",
		**values,
	)


def prepayments(kst: str = "2500.00", solz: str = "137.50", gewst: str = "3750.00") -> tuple:
	return (
		*(rules.Prepayment("KSt", YEAR, date(YEAR, month, 10), Decimal(kst)) for month in (3, 6, 9, 12)),
		*(rules.Prepayment("SolZ", YEAR, date(YEAR, month, 10), Decimal(solz)) for month in (3, 6, 9, 12)),
		*(rules.Prepayment("GewSt", YEAR, date(YEAR, month, 15), Decimal(gewst)) for month in (2, 5, 8, 11)),
	)


COMPANY = bridge.Company(
	"Muster IT GmbH",
	rechtsform="350",
	management_seat="Musterstadt",
	registered_seat="Musterstadt",
	business_purpose="Softwareentwicklung",
	founded_on=date(2020, 1, 1),
)
SETTINGS = bridge.Settings(
	COMPANY,
	shareholders=(shareholder(),),
	holdings=(
		rules.Holding("Gamma AG", YEAR, Decimal("0.5"), Decimal("0.5")),
		rules.Holding("Beta GmbH", YEAR, Decimal("12"), Decimal("12")),
	),
	prepayments=prepayments(),
	reviewed_on=date(2026, 10, 15),
)
HOLDING_RESULTS = (
	{"idx": 1, "kind": "Dividends", "holding_name": "Gamma AG", "amount": 8000},
	{"idx": 2, "kind": "Dividends", "holding_name": "Beta GmbH", "amount": 12000},
	{
		"idx": 3,
		"kind": "Sale",
		"holding_name": "Delta AG",
		"result_date": "2026-05-04",
		"sale_price": 80000,
		"sale_costs": 1000,
		"book_value": 49000,
	},
	{
		"idx": 4,
		"kind": "Sale",
		"holding_name": "Epsilon GmbH",
		"result_date": date(2026, 9, 30),
		"sale_price": 20000,
		"book_value": 32000,
	},
	{"idx": 5, "kind": "Write-down", "holding_name": "Zeta GmbH", "amount": 4000},
)
RETURN = bridge.Return(
	YEAR,
	FROM,
	TO,
	holding_results=HOLDING_RESULTS,
	credits=({"idx": 1, "issuer": "Musterbank AG", "capital_gains_tax": 5000, "solz": 275},),
	donations=({"idx": 1, "recipient": "Musterverein e. V.", "amount": 1000},),
)


def compute(
	ret: bridge.Return = RETURN, books: bridge.Ledger | None = None, settings=SETTINGS, mapping=MAPPING
):
	return bridge.compute(ret, books or ledger(), mapping, settings, FIGURES, translate)


def codes(computation) -> list[str]:
	return [finding.code for finding in computation.findings]


def reported(rows) -> list[dict]:
	"""The rows as a save stores them: each files the amount of the form."""
	return [
		{**row, "reported": row["form_amount"], "correction": ZERO, "correction_reason": "", "manual": 0}
		for row in rows
	]


def line(rows, feldkennung: str) -> dict:
	(found,) = (row for row in rows if row["feldkennung"] == feldkennung)
	return found


def by_hand(feldkennung: str, amount: str, reason: str = REASON) -> dict:
	return {
		"feldkennung": feldkennung,
		"correction": Decimal(amount),
		"correction_reason": reason,
		"manual": 1,
	}


def corrected(rows, feldkennung: str, amount: str, reason: str = REASON) -> list[dict]:
	return [
		{**row, "correction": Decimal(amount), "correction_reason": reason}
		if row["feldkennung"] == feldkennung
		else row
		for row in rows
	]


def entries(vordrucke, form: str) -> dict:
	(found,) = (vordruck for vordruck in vordrucke if vordruck.form == form)
	return {(entry.feldkennung, entry.rows): entry.value for entry in found.entries}


class MusterItGmbhTest(TestCase):
	"""The worked example of the research of stage 3, section 2.4, as Berechnen of the return computes it."""

	def setUp(self):
		self.computation = compute()

	def test_computes_the_taxes_of_the_example(self):
		self.assertEqual(
			self.computation.values,
			{
				"net_income": Decimal("88175"),
				"business_income": Decimal("112200"),
				"sum_of_income": Decimal("112200"),
				"total_income": Decimal("111200"),
				"zve": Decimal("111200"),
				"kst": Decimal("16680"),
				"solz": Decimal("917.40"),
				"capital_gains_tax_credit": Decimal("5000.00"),
				"solz_credit": Decimal("275.00"),
				"kst_prepayments": Decimal("10000.00"),
				"solz_prepayments": Decimal("550.00"),
				"kst_balance": Decimal("1680.00"),
				"solz_balance": Decimal("92.40"),
				"einlagekonto": Decimal("0"),
			},
		)

	def test_only_the_forms_of_the_year_hold_the_example_back(self):
		self.assertEqual(codes(self.computation), [PROVISIONAL])
		(finding,) = self.computation.findings
		self.assertEqual((finding.severity, finding.reference), (Severity.ERROR, "Jahresdokumentation 2025"))
		self.assertIn("provisionally from the Jahresdokumentation 2025", finding.text)

	def test_each_line_names_its_form_line_and_beschreibung_and_the_books_beside_the_form(self):
		rows = self.computation.lines
		self.assertEqual(
			{key: line(rows, "E8002001")[key] for key in ("form", "line", "form_amount", "ledger_amount")},
			{
				"form": "GK",
				"line": "11",
				"form_amount": Decimal("88175"),
				"ledger_amount": Decimal("88175.00"),
			},
		)
		self.assertTrue(line(rows, "E8002001")["label"].startswith("Jahresüberschuss/-fehlbetrag"))
		self.assertEqual(line(rows, "E8100301")["ledger_amount"], Decimal("10000.00"))
		self.assertEqual(line(rows, "E8109901")["ledger_amount"], ZERO)
		self.assertEqual(line(rows, "E8007502")["form_amount"], Decimal("16680"))
		self.assertEqual(line(rows, "E8120401")["form_amount"], Decimal("5000.00"))

	def test_the_lines_keep_the_order_of_the_catalogue_and_leave_out_repeated_contexts(self):
		ranks = {item.feldkennung: rank for rank, item in enumerate(catalogue_for(YEAR).fields)}
		keys = [row["feldkennung"] for row in self.computation.lines]
		self.assertEqual(keys, sorted(keys, key=ranks.__getitem__))
		self.assertEqual(len(keys), len(set(keys)))
		self.assertNotIn("E8560403", keys)
		self.assertEqual({row["form"] for row in self.computation.lines}, {"GK", "ZVE", "Z", "WA", "KSt1F"})
		self.assertTrue(all(isinstance(row["form_amount"], Decimal) for row in self.computation.lines))

	def test_the_vordrucke_filed_pass_the_rules_steuerbote_checks(self):
		filed = bridge.filed_vordrucke(RETURN, reported(self.computation.lines), SETTINGS)
		self.assertEqual([vordruck.form for vordruck in filed], ["KSt1", "GK", "ZVE", "Z", "WA", "KSt1F"])
		self.assertEqual(bridge.rule_findings(YEAR, filed, translate), [])

	def test_the_einlagekonto_of_the_example_stays_at_zero(self):
		self.assertEqual(
			entries((self.computation.kst1f,), "KSt1F"), {("E8240103", ()): ZERO, ("E8245601", ()): ZERO}
		)
		self.assertEqual(self.computation.kst1f.wj, "WJ1")


class LossCarryBackTest(TestCase):
	"""§ 10d Absatz 1 EStG: a Verlustrücktrag needs a loss of the year; steuerbote.kst.losses refuses one for a
	positive Gesamtbetrag der Einkünfte."""

	LOSS = (credit("8400", "10000.00", "S-1"), debit("4120", "50000.00", "P-1"))

	def loss_year(self, **values):
		ret = bridge.Return(YEAR, FROM, TO, loss_carry_back=Decimal("20000"), **values)
		books = bridge.Ledger(self.LOSS, Decimal("-40000.00"))
		return bridge.compute(ret, books, Mapping("SKR03", ()), SETTINGS, FIGURES, translate)

	def test_a_loss_takes_the_carry_back_chosen(self):
		computation = self.loss_year(carry_back_chosen=True)
		self.assertEqual(computation.result.losses.carry_back, Decimal("20000.00"))
		self.assertEqual(line(computation.lines, "E8008102")["form_amount"], Decimal("20000.00"))
		self.assertEqual(line(computation.lines, "E8008001")["form"], "Verluste")
		self.assertNotIn(CARRY_BACK_WITHOUT_LOSS, codes(computation))

	def test_a_carry_back_not_chosen_counts_not(self):
		self.assertIsNone(self.loss_year().result.losses.carry_back)

	def test_a_carry_back_of_a_positive_year_is_left_out_with_an_error(self):
		computation = compute(replace(RETURN, carry_back_chosen=True, loss_carry_back=Decimal("5000")))
		self.assertFalse(computation.result.losses.carry_back)
		self.assertNotIn("E8008102", [row["feldkennung"] for row in computation.lines])
		(finding,) = (item for item in computation.findings if item.code == CARRY_BACK_WITHOUT_LOSS)
		self.assertEqual(
			(finding.severity, finding.text, finding.reference),
			(
				Severity.ERROR,
				"A Verlustrücktrag of 5.000,00 € needs a loss, and the Gesamtbetrag der Einkünfte is 111.200,00 €; "
				"the return leaves it out.",
				"§ 10d Absatz 1 EStG",
			),
		)
		self.assertEqual(computation.values["zve"], Decimal("111200"))

	def test_choosing_a_carry_back_of_nothing_in_a_positive_year_says_nothing(self):
		self.assertEqual(codes(compute(replace(RETURN, carry_back_chosen=True))), [PROVISIONAL])


class CorrectionsTest(TestCase):
	"""A correction files another amount on a line of the books or one left to hand, and a line by hand adds an amount
	to one; the core takes each as a ManualLine of its step, so that the sums of the form add it."""

	def setUp(self):
		self.rows = reported(compute().lines)

	def corrected_return(self, rows) -> bridge.Computation:
		return compute(replace(RETURN, lines=tuple(rows)))

	def test_a_correction_files_its_amount_and_the_sums_follow(self):
		computation = self.corrected_return(corrected(self.rows, "E8100301", "9000"))
		row = line(computation.lines, "E8100301")
		self.assertEqual((row["form_amount"], row["ledger_amount"]), (Decimal("9000"), Decimal("10000.00")))
		self.assertEqual(computation.values["zve"], Decimal("110200"))

	def test_lines_by_hand_add_the_ueberleitung_and_a_hidden_distribution(self):
		rows = [
			*self.rows,
			by_hand("E8002001", "-1000"),
			by_hand("E8002701", "2500", "Verdeckte Gewinnausschüttung: Miete über dem Marktpreis"),
		]
		computation = self.corrected_return(rows)
		self.assertEqual(line(computation.lines, "E8002001")["form_amount"], Decimal("87175"))
		self.assertEqual(line(computation.lines, "E8002701")["form_amount"], Decimal("2500"))
		self.assertEqual(computation.values["zve"], Decimal("112700"))

	def test_a_correction_of_a_line_with_lines_by_hand_files_the_amount_corrected(self):
		rows = [*corrected(self.rows, "E8002001", "87000"), by_hand("E8002001", "-1000")]
		computation = self.corrected_return(rows)
		self.assertEqual(line(computation.lines, "E8002001")["form_amount"], Decimal("87000"))

	def test_a_correction_to_the_amount_of_the_books_changes_nothing(self):
		computation = self.corrected_return(corrected(self.rows, "E8100301", "10000"))
		self.assertEqual(computation.values, compute().values)
		self.assertEqual(computation.result.lines["corporate_tax"].manual, ())

	def test_a_line_derived_from_others_takes_no_correction(self):
		rows = corrected(self.rows, "E8109901", "100000")
		for check in (lambda: self.corrected_return(rows), lambda: bridge.check_lines(YEAR, rows)):
			with self.subTest(check=check), self.assertRaises(BridgeError) as raised:
				check()
			self.assertEqual(
				(raised.exception.template, raised.exception.values), (bridge.NOT_CORRECTABLE, ("E8109901",))
			)

	def test_a_line_by_hand_names_a_line_of_the_books_or_one_left_to_hand(self):
		field = bridge.manual_field(YEAR, " e8002701 ")
		self.assertEqual((field.feldkennung, field.form, field.line), ("E8002701", "GK", "75"))
		for feldkennung, shown in (("E8109901", "E8109901"), ("", "-"), (None, "-")):
			with self.subTest(feldkennung=feldkennung), self.assertRaises(BridgeError) as raised:
				bridge.manual_field(YEAR, feldkennung)
			self.assertEqual(
				(raised.exception.template, raised.exception.values), (bridge.NOT_A_LINE, (shown,))
			)
		with self.assertRaises(BridgeError) as raised:
			bridge.check_lines(YEAR, [by_hand("E8007502", "100")])
		self.assertEqual(raised.exception.template, bridge.NOT_A_LINE)

	def test_a_line_of_whole_euros_takes_no_cents(self):
		for rows in (corrected(self.rows, "E8002001", "88175.50"), [by_hand("e8002701", "10.50")]):
			with self.subTest(rows=rows[-1]), self.assertRaises(BridgeError) as raised:
				bridge.check_lines(YEAR, rows)
			self.assertEqual(raised.exception.template, bridge.NOT_WHOLE)
		self.assertEqual(str(raised.exception), "The line E8002701 files whole euros, not 10.50.")
		bridge.check_lines(YEAR, [*corrected(self.rows, "E8002001", "88175"), by_hand("E8002701", "10")])

	def test_only_the_lines_of_the_books_and_those_left_to_hand_take_a_correction(self):
		self.assertEqual(bridge.CORRECTABLE_FIELDS["E8002001"], "net_income")
		self.assertEqual(bridge.CORRECTABLE_FIELDS["E8002701"], "hidden_distributions")
		self.assertEqual(bridge.CORRECTABLE_FIELDS["E8100301"], "corporate_tax")
		for feldkennung in ("E8109901", "E8007502", "E8120401"):
			with self.subTest(feldkennung=feldkennung):
				self.assertNotIn(feldkennung, bridge.CORRECTABLE_FIELDS)
		self.assertFalse(set(bridge.CONTRIBUTION_STEPS.values()) & bridge.CORRECTABLE)

	def test_a_line_by_hand_is_filed_in_the_line_of_its_field(self):
		computation = self.corrected_return([*self.rows, by_hand("E8002701", "2500")])
		rows = [*reported(computation.lines), by_hand("E8002701", "2500")]
		filed = entries(bridge.filed_vordrucke(RETURN, rows, SETTINGS), "GK")
		self.assertEqual(filed[("E8002701", ())], Decimal("2500"))


class TablesTest(TestCase):
	"""What a save refuses of the tables and amounts of the return, before the core takes them."""

	def refused(self, **values) -> BridgeError:
		with self.assertRaises(BridgeError) as raised:
			bridge.check_tables(bridge.Return(YEAR, FROM, TO, **values), translate)
		return raised.exception

	def assert_refused(self, values: dict, template: str, *shown: object) -> None:
		error = self.refused(**values)
		self.assertEqual((error.template, error.values), (template, shown))

	def test_the_tables_of_the_example_pass(self):
		bridge.check_tables(RETURN, translate)
		bridge.check_tables(replace(RETURN, previous_equity=Decimal("-5000")), translate)

	def test_a_holding_result_is_of_a_kind_with_an_amount_above_zero_and_costs_not_below(self):
		row = {"idx": 2, "kind": "Dividends", "holding_name": "Beta GmbH", "amount": Decimal("100.50")}
		bridge.check_tables(bridge.Return(YEAR, FROM, TO, holding_results=(row,)), translate)
		for changed, template, shown in (
			({"kind": "Spin-off"}, bridge.NOT_AN_OPTION, ("§ 8b results", 2, "Spin-off")),
			({"amount": 0}, bridge.NOT_POSITIVE, ("§ 8b results", 2)),
			({"kind": "Write-down"}, bridge.ROW_NOT_IN_EUROS, ("§ 8b results", 2)),
			(
				{"financing_costs": -1},
				bridge.ROW_NEGATIVE,
				("§ 8b results", 2, "Related Costs under § 8 Nr. 1 GewStG (BEG Line 8)"),
			),
			(
				{"other_costs": -1, "idx": None},
				bridge.ROW_NEGATIVE,
				("§ 8b results", "?", "Other Related Costs (BEG Line 9)"),
			),
		):
			with self.subTest(changed=changed):
				self.assert_refused({"holding_results": ({**row, **changed},)}, template, *shown)

	def test_a_sale_has_its_day_and_a_gain_or_a_loss_from_amounts_not_below_zero(self):
		sale = HOLDING_RESULTS[2]
		bridge.check_tables(
			bridge.Return(YEAR, FROM, TO, holding_results=(sale, HOLDING_RESULTS[3])), translate
		)
		for changed, template, shown in (
			({"result_date": None}, bridge.SALE_WITHOUT_DAY, ("§ 8b results", 3)),
			({"book_value": 79000}, bridge.SALE_WITHOUT_RESULT, ("§ 8b results", 3)),
			({"sale_costs": -1}, bridge.ROW_NEGATIVE, ("§ 8b results", 3, "Sale Costs")),
		):
			with self.subTest(changed=changed):
				self.assert_refused({"holding_results": ({**sale, **changed},)}, template, *shown)

	def test_a_tax_certificate_holds_no_amount_below_zero(self):
		self.assert_refused(
			{"credits": ({"idx": 1, "capital_gains_tax": 10, "solz": -1},)},
			bridge.ROW_NEGATIVE,
			"tax certificates",
			1,
			"Solidaritätszuschlag",
		)

	def test_a_donation_is_above_zero(self):
		self.assert_refused({"donations": ({"idx": 3, "amount": 0},)}, bridge.NOT_POSITIVE, "donations", 3)

	def test_a_distribution_is_of_a_kind_in_whole_euros_and_reduces_the_einlagekonto_by_at_most_itself(self):
		row = {
			"idx": 1,
			"kind": "Ordinary Distribution",
			"resolution_date": date(2026, 5, 15),
			"outflow_date": "2026-05-20",
			"amount": 10000,
			"certified_reduction": 2000,
		}
		bridge.check_tables(bridge.Return(YEAR, FROM, TO, distributions=(row,)), translate)
		for changed, template in (
			({"kind": "Dividend"}, bridge.NOT_AN_OPTION),
			({"kind": "Payment under § 20 Abs. 1 Nr. 9 and 10a EStG"}, bridge.NOT_AN_OPTION),
			({"amount": Decimal("10000.50")}, bridge.ROW_NOT_IN_EUROS),
			({"certified_reduction": Decimal("2000.50")}, bridge.ROW_NOT_IN_EUROS),
			({"certified_reduction": 10001}, bridge.REDUCTION_ABOVE_AMOUNT),
		):
			with self.subTest(changed=changed):
				self.assertEqual(self.refused(distributions=({**row, **changed},)).template, template)

	def test_a_leistung_flows_out_in_the_wirtschaftsjahr_after_its_resolution(self):
		"""Rules 8920296, 8920247 and 8920298 of KSt 1 F."""
		row = {"idx": 2, "kind": "Ordinary Distribution", "resolution_date": "2026-05-15", "amount": 10000}
		for outflow in (None, "2027-01-02"):
			with self.subTest(outflow=outflow):
				self.assert_refused(
					{"distributions": ({**row, "outflow_date": outflow},)},
					bridge.DAY_OUTSIDE,
					"distributions",
					2,
					"Date of the Outflow",
					"01.01.2026",
					"31.12.2026",
				)
		for changed, template in (
			({"resolution_date": None, "outflow_date": "2026-05-20"}, bridge.NO_RESOLUTION),
			({"outflow_date": "2026-05-14"}, bridge.OUTFLOW_BEFORE_RESOLUTION),
		):
			with self.subTest(changed=changed):
				self.assertEqual(self.refused(distributions=({**row, **changed},)).template, template)
		hidden = {"kind": "Hidden Distribution", "outflow_date": "2026-12-31", "amount": 2500}
		bridge.check_tables(bridge.Return(YEAR, FROM, TO, distributions=(hidden,)), translate)

	def test_a_contribution_has_a_treatment_a_kind_a_description_in_kind_and_whole_euros(self):
		row = {
			"idx": 1,
			"shareholder": "Erika Muster",
			"contribution_date": "2026-03-01",
			"treatment": "Other Contribution",
			"amount": 5000,
		}
		bridge.check_tables(bridge.Return(YEAR, FROM, TO, contributions=(row,)), translate)
		for changed, template in (
			({"treatment": "Gift"}, bridge.NOT_AN_OPTION),
			({"kind": "Cash"}, bridge.NOT_AN_OPTION),
			({"kind": "Contribution in Kind", "description": " "}, bridge.NO_DESCRIPTION),
			({"amount": 0}, bridge.NOT_POSITIVE),
			({"amount": Decimal("5000.10")}, bridge.ROW_NOT_IN_EUROS),
			({"contribution_date": "2025-12-31"}, bridge.DAY_OUTSIDE),
		):
			with self.subTest(changed=changed):
				self.assertEqual(self.refused(contributions=({**row, **changed},)).template, template)

	def test_the_amounts_of_the_return_are_whole_euros_and_not_below_zero_but_the_equity(self):
		for values, template, label in (
			({"loss_carry_back": Decimal("10.50")}, bridge.FIELD_NOT_IN_EUROS, "Verlustrücktrag"),
			(
				{"turnover_and_wages": Decimal("-1")},
				bridge.FIELD_NEGATIVE,
				"Turnover, Wages and Salaries (Anlage Z Line 10)",
			),
			(
				{"previous_nominal_capital": Decimal("-25000")},
				bridge.FIELD_NEGATIVE,
				"Nennkapital at the End of the Previous Wirtschaftsjahr (KSt 1 F Line 18)",
			),
			(
				{"previous_equity": Decimal("0.01")},
				bridge.FIELD_NOT_IN_EUROS,
				"Equity at the End of the Previous Wirtschaftsjahr (KSt 1 F Line 17)",
			),
		):
			with self.subTest(values=values):
				self.assert_refused(values, template, label)

	def test_the_labels_of_the_texts_are_translated(self):
		error = self.refused(donations=({"idx": 3, "amount": 0},))
		with self.assertRaises(BridgeError) as raised:
			bridge.check_tables(bridge.Return(YEAR, FROM, TO, donations=({"amount": 0},)), str.upper)
		self.assertEqual(raised.exception.values, ("DONATIONS", "?"))
		self.assertEqual(str(error), "Row 3 of the donations: the amount is above zero.")


class HoldingsTest(TestCase):
	"""§ 8b KStG by the holdings register of the Annual Filing Settings: the share at the start of the calendar year
	decides on the dividends (§ 8b Absatz 4 Satz 1 KStG), the flag of § 8b Absatz 7 KStG on all of them."""

	def test_the_columns_of_the_dividends_show_the_register_and_the_exemption(self):
		for name, shown in (("Beta GmbH", "§ 8b Abs. 1 KStG"), (" gamma  ag ", "Streubesitz")):
			with self.subTest(name=name):
				registered, exemption = bridge.holding_exemption(
					YEAR, {"kind": "Dividends", "holding_name": name}, SETTINGS
				)
				self.assertEqual(exemption, shown)
				self.assertEqual(registered.year, YEAR)
		trading = replace(SETTINGS, company=replace(COMPANY, section_8b_7=True))
		self.assertEqual(
			bridge.holding_exemption(YEAR, {"kind": "Dividends", "holding_name": "Beta GmbH"}, trading)[1],
			"§ 8b Abs. 7 KStG",
		)

	def test_a_row_of_another_kind_or_holding_shows_nothing(self):
		for row, settings in (
			({"kind": "Sale", "holding_name": "Beta GmbH"}, SETTINGS),
			({"kind": "Dividends", "holding_name": "Omega AG"}, SETTINGS),
			({"kind": "Dividends", "holding_name": "Beta GmbH"}, None),
			(
				{"kind": "Dividends", "holding_name": "Beta GmbH"},
				replace(SETTINGS, holdings=(rules.Holding("Beta GmbH", 2025, Decimal("12")),)),
			),
		):
			with self.subTest(row=row, settings=settings is not None):
				self.assertEqual(bridge.holding_exemption(YEAR, row, settings), (None, ""))

	def test_a_share_of_the_register_stands_in_for_the_other(self):
		for registered, shares in (
			(rules.Holding("Beta GmbH", YEAR, Decimal("12")), (Decimal("12"), Decimal("12"))),
			(rules.Holding("Beta GmbH", YEAR, None, Decimal("15")), (Decimal("15"), Decimal("15"))),
			(rules.Holding("Beta GmbH", YEAR, Decimal("5"), Decimal("15")), (Decimal("5"), Decimal("15"))),
			(rules.Holding("Beta GmbH", YEAR), (ZERO, ZERO)),
		):
			with self.subTest(registered=registered):
				holding = bridge.holding_of(registered)
				self.assertEqual((holding.share_at_year_start, holding.share_at_ez_start), shares)
				self.assertFalse(holding.foreign)

	def test_a_holding_with_its_seat_abroad_is_foreign(self):
		for country, foreign in (("Austria", True), ("Germany", False), (None, False)):
			with self.subTest(country=country):
				registered = rules.Holding("Alpha GmbH", YEAR, Decimal("20"), country=country)
				self.assertIs(bridge.holding_of(registered).foreign, foreign)

	def test_dividends_of_a_holding_the_register_does_not_name_hold_the_return_back(self):
		results = (
			*HOLDING_RESULTS,
			{"idx": 6, "kind": "Dividends", "holding_name": "Omega AG", "amount": 500},
		)
		computation = compute(replace(RETURN, holding_results=results))
		(finding,) = (item for item in computation.findings if item.code == UNKNOWN_HOLDING)
		self.assertEqual(finding.severity, Severity.ERROR)
		self.assertIn("The dividends of Omega AG name no holding", finding.text)
		self.assertEqual(len(computation.result.p8b.holdings), 2)

	def test_a_holding_whose_register_names_no_share_holds_the_return_back(self):
		"""Without a share the holding would be Streubesitz and its dividends taxed in full (§ 8b Abs. 4 Satz 1 KStG,
		§ 9 Nr. 2a GewStG), though the register names it."""
		settings = replace(SETTINGS, holdings=(*SETTINGS.holdings, rules.Holding("Omega AG", YEAR)))
		results = (
			*HOLDING_RESULTS,
			{"idx": 6, "kind": "Dividends", "holding_name": "Omega AG", "amount": 500},
		)
		computation = compute(replace(RETURN, holding_results=results), settings=settings)
		(finding,) = (item for item in computation.findings if item.code == HOLDING_WITHOUT_SHARE)
		self.assertEqual(finding.severity, Severity.ERROR)
		self.assertEqual(
			finding.text,
			"The holding Omega AG of the Annual Filing Settings for 2026 names no share, so § 8b Absatz 4 KStG takes "
			"its dividends of 500,00 € as Streubesitz and taxes them in full; enter its share at the start of the "
			"calendar year and of the Erhebungszeitraum there.",
		)

	def test_anlage_gk_names_each_exempt_holding_and_each_single_value(self):
		filed = entries(bridge.filed_vordrucke(RETURN, reported(compute().lines), SETTINGS), "GK")
		self.assertEqual(
			{key: value for key, value in filed.items() if key[1]},
			{
				("E8561202", (0,)): "Delta AG",
				("E8561213", (0,)): date(2026, 5, 4),
				("E8561204", (0,)): Decimal("80000.00"),
				("E8561205", (0,)): Decimal("1000.00"),
				("E8561206", (0,)): Decimal("49000.00"),
				("E8561211", (0,)): Decimal("30000.00"),
				("E8561202", (1,)): "Epsilon GmbH",
				("E8561213", (1,)): date(2026, 9, 30),
				("E8561204", (1,)): Decimal("20000.00"),
				("E8561205", (1,)): ZERO,
				("E8561206", (1,)): Decimal("32000.00"),
				("E8561403", (1,)): Decimal("12000.00"),
				("E8561402", (0,)): "Zeta GmbH",
				("E8561408", (0,)): Decimal("4000.00"),
				("E8560403", (0,)): "Beta GmbH",
				("E8560406", (0,)): Decimal("12"),
				("E8560407", (0,)): "1",
				("E8560404", (0,)): Decimal("12000.00"),
			},
		)

	def test_a_write_up_and_a_sale_without_a_day_are_single_values_too(self):
		ret = bridge.Return(
			YEAR,
			FROM,
			TO,
			holding_results=(
				{"kind": "Write-up", "holding_name": "Zeta GmbH", "amount": 1500},
				{"kind": "Sale", "holding_name": "Delta AG", "sale_price": 700},
			),
		)
		filed = entries(bridge.filed_vordrucke(ret, (), None), "GK")
		self.assertEqual(
			filed,
			{
				("E8561239", (0,)): "Zeta GmbH",
				("E8561210", (0,)): Decimal("1500.00"),
				("E8561202", (0,)): "Delta AG",
				("E8561204", (0,)): Decimal("700.00"),
				("E8561205", (0,)): ZERO,
				("E8561206", (0,)): ZERO,
				("E8561211", (0,)): Decimal("700.00"),
			},
		)

	def test_the_result_of_a_sale_is_its_price_less_its_costs_and_the_book_value(self):
		"""§ 8b Absatz 2 Satz 2 KStG."""
		self.assertEqual(bridge.sale_result(HOLDING_RESULTS[2]), Decimal("30000.00"))
		self.assertEqual(bridge.sale_result(HOLDING_RESULTS[3]), Decimal("-12000.00"))
		self.assertEqual(bridge.sale_result({}), ZERO)

	def test_the_trading_book_exempts_no_holding_in_anlage_gk(self):
		trading = replace(SETTINGS, company=replace(COMPANY, section_8b_7=True))
		filed = entries(bridge.filed_vordrucke(RETURN, (), trading), "GK")
		self.assertNotIn(("E8560403", (0,)), filed)

	def test_results_of_the_books_without_their_single_values_hold_the_return_back(self):
		computation = compute(replace(RETURN, holding_results=HOLDING_RESULTS[:2]))
		found = [item for item in computation.findings if item.code == NO_SINGLE_VALUES]
		self.assertEqual(
			[item.reference for item in found],
			["Anlage GK Zeile 166b", "Anlage GK Zeile 166c", "Anlage GK Zeile 188"],
		)
		self.assertEqual(
			found[0].text,
			"Anlage GK line 166b declares 30.000,00 €, and the § 8b results list no single value of it. Enter each "
			"sale, write-up or write-down there with the company it concerns.",
		)


class SettingsFindingsTest(TestCase):
	"""What the Annual Filing Settings have to give before the return is ready."""

	def findings(self, settings, ret: bridge.Return = RETURN, books: bridge.Ledger | None = None) -> list:
		return [item for item in compute(ret, books, settings).findings if item.code != PROVISIONAL]

	def test_a_company_without_settings_is_not_ready(self):
		"""Without the register, the dividends name no holding, and § 8b Absatz 4 KStG taxes them as Streubesitz."""
		found = self.findings(None, books=ledger(booked={}))
		self.assertEqual(
			[item.code for item in found],
			["KST-STREUBESITZ", UNKNOWN_HOLDING, UNKNOWN_HOLDING, NO_SETTINGS],
		)
		self.assertEqual(
			found[-1].text,
			"The company has no Annual Filing Settings, which give the Rechtsform, the seats and the shareholders.",
		)

	def test_the_rechtsform_and_the_seats_are_given(self):
		company = bridge.Company("Muster IT GmbH", registered_seat="Musterstadt")
		(finding,) = self.findings(replace(SETTINGS, company=company))
		self.assertEqual(finding.code, DETAILS_MISSING)
		self.assertEqual(
			finding.text,
			"The Annual Filing Settings of Muster IT GmbH lack what the return needs: Legal Form, Place of Management.",
		)

	def test_the_shareholders_hold_99_to_100_percent_on_each_day(self):
		cases = (
			((shareholder(percent="99.5"),), None),
			((shareholder(percent="50"),), "01.01.2026"),
			(
				(
					shareholder(to_date=date(2026, 6, 30)),
					shareholder(2, "Max Muster", from_date=date(2026, 7, 1)),
				),
				None,
			),
			(
				(
					shareholder(to_date=date(2026, 6, 30)),
					shareholder(2, "Max Muster", from_date=date(2026, 8, 1)),
				),
				"01.07.2026",
			),
			((shareholder(from_date=date(2027, 1, 1)),), "01.01.2026"),
		)
		for shareholders, day in cases:
			with self.subTest(shareholders=shareholders):
				found = self.findings(replace(SETTINGS, shareholders=shareholders))
				self.assertEqual([item.code for item in found], [SHARES] if day else [])
				if day:
					self.assertTrue(found[0].text.startswith(f"On {day} the shareholders"))
		(finding,) = self.findings(replace(SETTINGS, shareholders=(shareholder(percent="50"),)))
		self.assertIn("hold 50,0 %", finding.text)

	def test_a_handelsbilanz_with_ueberleitungsrechnung_needs_the_ueberleitung_on_line_11(self):
		settings = replace(SETTINGS, company=replace(COMPANY, accounting_standard="HGBM"))
		(finding,) = self.findings(settings)
		self.assertEqual((finding.code, finding.reference), (NO_UEBERLEITUNG, "§ 60 Absatz 2 EStDV"))
		rows = reported(compute().lines)
		for lines in ([*rows, by_hand("E8002001", "-1000")], corrected(rows, "E8002001", "88000")):
			with self.subTest(lines=lines[-1]):
				self.assertEqual(self.findings(settings, replace(RETURN, lines=tuple(lines))), [])

	def test_the_vorauszahlungen_of_the_notices_are_compared_with_those_booked(self):
		settings = replace(SETTINGS, prepayments=prepayments(kst="2400.00"))
		(finding,) = self.findings(settings)
		self.assertEqual((finding.code, finding.severity), (PREPAYMENTS, Severity.HINT))
		self.assertEqual(
			finding.text,
			"The Vorauszahlungen KSt of the Annual Filing Settings come to 9.600,00 €, those booked on the account of "
			"the tax to 10.000,00 €.",
		)
		self.assertEqual(compute(settings=settings).values["kst_prepayments"], Decimal("9600.00"))

	def test_the_returns_wait_for_the_review_of_a_steuerberatung(self):
		"""Decision 6.4 of the contract of stage 3: the classes of the trading accounts, the status under § 8b Absatz 7
		KStG and the review list are confirmed before the first filing."""
		(finding,) = self.findings(replace(SETTINGS, reviewed_on=None))
		self.assertEqual((finding.code, finding.severity), (bridge.NOT_REVIEWED, Severity.ERROR))
		self.assertTrue(
			finding.text.startswith("The Annual Filing Settings name no day on which a Steuerberatung")
		)

	def test_a_shareholder_with_more_than_three_periods_holds_the_return_back(self):
		"""KSt1/AE/Einzel/Besitzdauer repeats at most three times."""
		quarters = (
			(date(2026, 1, 1), date(2026, 3, 31)),
			(date(2026, 4, 1), date(2026, 6, 30)),
			(date(2026, 7, 1), date(2026, 9, 30)),
			(date(2026, 10, 1), None),
		)
		periods = tuple(
			shareholder(row, from_date=first, to_date=last) for row, (first, last) in enumerate(quarters, 1)
		)
		(finding,) = self.findings(replace(SETTINGS, shareholders=periods))
		self.assertEqual(
			(finding.code, finding.text),
			(
				bridge.PERIODS,
				"Erika Muster holds shares in 4 periods of the Wirtschaftsjahr, and KSt 1 lines 23 to 23b take three of "
				"them.",
			),
		)

	def test_a_chart_of_its_own_compares_no_vorauszahlungen(self):
		books = bridge.Ledger(LEDGER, ledger().net_income, (), None)
		self.assertEqual(
			self.findings(replace(SETTINGS, prepayments=prepayments(kst="1.00")), books=books), []
		)
		self.assertIsNone(books.booked_prepayments)

	def test_the_vorauszahlungen_of_another_year_count_not(self):
		other = (*prepayments(), rules.Prepayment("KSt", 2025, date(2025, 12, 10), Decimal("999.00")))
		self.assertEqual(
			bridge.prepayments_of(YEAR, replace(SETTINGS, prepayments=other))["KSt"], Decimal("10000.00")
		)
		self.assertEqual(bridge.prepayments_of(YEAR, None), {"KSt": ZERO, "SolZ": ZERO, "GewSt": ZERO})


class CarryForwardsTest(TestCase):
	"""The carry-forwards of the last notices as of the end of the previous Wirtschaftsjahr, which count once someone
	confirmed them against the notice."""

	def stated(
		self, kind, amount: str, confirmed: bool = True, as_of: date = date(2025, 12, 31)
	) -> rules.CarryForward:
		return rules.CarryForward(kind, as_of, Decimal(amount), confirmed=confirmed)

	def test_a_confirmed_loss_carried_forward_reduces_the_income(self):
		settings = replace(SETTINGS, carry_forwards=(self.stated(rules.CarryForwardKind.LOSS, "11200"),))
		computation = compute(settings=settings)
		self.assertEqual(computation.values["zve"], Decimal("100000"))
		self.assertEqual(codes(computation), [PROVISIONAL])

	def test_a_carry_forward_not_confirmed_holds_the_return_back(self):
		settings = replace(
			SETTINGS, carry_forwards=(self.stated(rules.CarryForwardKind.LOSS, "11200", False),)
		)
		computation = compute(settings=settings)
		(finding,) = (item for item in computation.findings if item.code == UNCONFIRMED)
		self.assertEqual(
			finding.text,
			"Loss Carried Forward (§ 10d EStG) as of 31.12.2025 in the Annual Filing Settings is not confirmed "
			"against its notice; the return takes only confirmed carry-forwards.",
		)
		self.assertEqual(computation.values["zve"], Decimal("111200"))

	def test_a_carry_forward_in_cents_counts_in_whole_euros(self):
		found = []
		stated = (self.stated(rules.CarryForwardKind.EINLAGEKONTO, "1000.50"),)
		amount = bridge.carry_forward(
			stated, rules.CarryForwardKind.EINLAGEKONTO, date(2025, 12, 31), FIGURES, translate, found
		)
		self.assertEqual(amount, Decimal("1001"))
		self.assertEqual([item.code for item in found], [NOT_IN_EUROS])
		self.assertEqual(
			found[0].text,
			"Einlagekonto (§ 27 KStG) as of 31.12.2025 is 1.000,50 €, not whole euros as a notice states it; the "
			"return takes 1.001,00 €.",
		)

	def test_a_carry_forward_stated_after_the_opening_day_or_of_another_kind_counts_not(self):
		stated = (
			self.stated(rules.CarryForwardKind.LOSS, "5000", as_of=date(2026, 12, 31)),
			self.stated(rules.CarryForwardKind.FEHLBETRAG, "7000"),
		)
		found = []
		self.assertEqual(
			bridge.carry_forward(
				stated, rules.CarryForwardKind.LOSS, date(2025, 12, 31), FIGURES, translate, found
			),
			ZERO,
		)
		self.assertEqual(found, [])

	def test_in_its_first_year_in_steuerbote_the_return_needs_the_carry_forwards_of_the_last_notice(self):
		"""A company whose returns of the previous year were filed outside Steuerbote (steuerbote/setup/start.py): a
		missing amount would count 0 silently."""
		first = replace(RETURN, first_year=True)
		computation = compute(first)
		missing = [item for item in computation.findings if item.code == bridge.CARRY_FORWARD_MISSING]
		self.assertEqual(
			[item.text for item in missing],
			[
				bridge.CARRY_FORWARD_MISSING_TEXT.format(kind, "31.12.2025")
				for kind in ("Loss Carried Forward (§ 10d EStG)", "Einlagekonto (§ 27 KStG)")
			],
		)
		self.assertTrue(all(item.blocking for item in missing))
		stated = (
			self.stated(rules.CarryForwardKind.LOSS, "0"),
			self.stated(rules.CarryForwardKind.EINLAGEKONTO, "25000"),
		)
		settings = replace(SETTINGS, carry_forwards=stated)
		self.assertNotIn(bridge.CARRY_FORWARD_MISSING, codes(compute(first, settings=settings)))
		self.assertNotIn(bridge.CARRY_FORWARD_MISSING, codes(compute()))

	def test_in_its_first_year_an_amount_of_an_earlier_day_does_not_do(self):
		stated = (
			self.stated(rules.CarryForwardKind.LOSS, "0", as_of=date(2024, 12, 31)),
			self.stated(rules.CarryForwardKind.EINLAGEKONTO, "0"),
		)
		computation = compute(
			replace(RETURN, first_year=True), settings=replace(SETTINGS, carry_forwards=stated)
		)
		self.assertEqual(codes(computation).count(bridge.CARRY_FORWARD_MISSING), 1)

	def test_the_einlagekonto_and_the_sonderausweis_go_to_kst_1_f(self):
		settings = replace(
			SETTINGS,
			carry_forwards=(
				self.stated(rules.CarryForwardKind.EINLAGEKONTO, "20000"),
				self.stated(rules.CarryForwardKind.SONDERAUSWEIS, "3000"),
			),
		)
		computation = compute(settings=settings)
		self.assertEqual(computation.values["einlagekonto"], Decimal("20000"))
		self.assertEqual(computation.einlagekonto.sonderausweis, Decimal("3000"))
		self.assertEqual(line(computation.lines, "E8240103")["form_amount"], Decimal("20000"))


class LedgerFindingsTest(TestCase):
	"""What the books of the Wirtschaftsjahr hold back or point out."""

	def findings(self, *extra, mapping=MAPPING, ret: bridge.Return = RETURN, unnumbered=()) -> list:
		computation = compute(ret, ledger(*extra, unnumbered=unnumbered), mapping=mapping)
		return [item for item in computation.findings if item.code != PROVISIONAL]

	def test_an_account_the_defaults_place_and_the_mapping_lacks_holds_the_return_back(self):
		(finding,) = self.findings(debit("2203", "400.00", "JV-9"))
		self.assertEqual((finding.code, finding.reference), (UNMAPPED, "Kontenzuordnung Ertragsteuern"))
		self.assertEqual(
			finding.text,
			"Account 2203 has a balance (debit 400,00 €, credit 0,00 €), and the defaults of SKR03 give it a place "
			"for the Körperschaftsteuer and the Gewerbesteuer, but the Income Tax Mapping of the company has no row "
			"for it.",
		)

	def test_an_account_that_evens_out_or_is_watched_or_has_no_default_holds_nothing_back(self):
		watched = Mapping(MAPPING.chart, MAPPING.rules, watched=("2203",))
		for extra, mapping in (
			((debit("2203", "400.00", "JV-9"), credit("2203", "400.00", "JV-10")), MAPPING),
			((debit("4999", "400.00", "JV-9"),), MAPPING),
			((debit("2203", "400.00", "JV-9"),), watched),
		):
			with self.subTest(extra=extra):
				self.assertNotIn(UNMAPPED, [item.code for item in self.findings(*extra, mapping=mapping)])

	def test_an_account_the_datev_chart_does_not_know_is_pointed_out_with_its_balance(self):
		"""An account outside the DATEV chart the defaults follow, such as one of an older edition for the sale of shares
		of a Kapitalgesellschaft, gets no default and counts only in the Jahresüberschuss; the hint names it, so that a
		result under § 8b KStG does not stay taxed in full unseen. An account of the chart without a mark gets none."""
		(finding,) = [
			item for item in self.findings(credit("2723", "8000.00", "JV-9")) if item.code == UNKNOWN
		]
		self.assertEqual(
			(finding.severity, finding.reference), (Severity.HINT, "Kontenzuordnung Ertragsteuern")
		)
		self.assertEqual(
			finding.text,
			"Account 2723 has a balance (debit 0,00 €, credit 8.000,00 €) but is no account of the DATEV chart SKR03 "
			"2026 the defaults follow, so it counts in the Jahresüberschuss alone. If it holds Bezüge, Gewinne or "
			"Gewinnminderungen aus Anteilen (§ 8b KStG) or another amount the taxes on income treat apart, give it its "
			"category in the Income Tax Mapping.",
		)
		self.assertNotIn(UNKNOWN, [item.code for item in self.findings(credit("4400", "8000.00", "JV-9"))])

	def test_a_chart_of_its_own_has_no_defaults_to_compare_with(self):
		mapping = Mapping("Eigener Kontenrahmen", MAPPING.rules)
		self.assertEqual(bridge.unmapped(ledger(debit("2203", "400.00")), mapping, FIGURES, translate), [])

	def test_an_account_without_a_number_holds_the_return_back(self):
		(finding,) = self.findings(
			unnumbered=(bridge.Unnumbered("Sonstige Erlöse - MIT", Decimal("250.00")),)
		)
		self.assertEqual(finding.code, UNNUMBERED)
		self.assertEqual(
			finding.text,
			"Account Sonstige Erlöse - MIT of the profit and loss account has a balance of 250,00 € and no account "
			"number, so the Income Tax Mapping cannot place it.",
		)

	def test_the_findings_of_the_core_come_first_as_the_table_holds_them(self):
		mapping = Mapping(
			MAPPING.chart,
			(
				*(rule for rule in MAPPING.rules if rule.account_number != "2654"),
				AccountRule("2654", Category.TRADING_UNCLASSIFIED),
				AccountRule("2219", Category.FOREIGN_TAX),
			),
		)
		computation = compute(books=ledger(debit("2219", "150.00", "DIV-3")), mapping=mapping)
		self.assertEqual(
			codes(computation)[:3], ["KST-HANDEL-OHNE-KLASSE", "KST-AUSLAENDISCHE-STEUERN", PROVISIONAL]
		)
		self.assertTrue(all(item.blocking for item in computation.findings[:2]))

	def test_zuwendungen_of_the_books_need_their_receipts(self):
		(finding,) = self.findings(ret=replace(RETURN, donations=()))
		self.assertEqual((finding.code, finding.severity), (NO_RECEIPTS, Severity.ERROR))
		self.assertIn("deductible Zuwendungen of 1.000,00 €", finding.text)
		(finding,) = self.findings(
			ret=replace(RETURN, donations=({"recipient": "Musterverein e. V.", "amount": 800},))
		)
		self.assertEqual((finding.code, finding.severity), (RECEIPTS_DIFFER, Severity.HINT))
		self.assertEqual(
			finding.text,
			"The receipts of the Zuwendungen come to 800,00 €, the deductible Zuwendungen in the books to 1.000,00 €.",
		)

	def test_the_receipts_give_the_zuwendungen_anlage_z_deducts(self):
		ret = replace(RETURN, donations=({"recipient": "Musterverein e. V.", "amount": 800},))
		self.assertEqual(bridge.eligible_donations(ret, ledger(), MAPPING), Decimal("800.00"))
		self.assertEqual(bridge.eligible_donations(RETURN, ledger(), MAPPING), Decimal("1000.00"))

	def test_zuwendungen_that_are_no_zuwendungen_of_the_law_count_not(self):
		"""SKR03 2380 and 2384 hold Zuwendungen that § 9 Absatz 1 Nummer 2 KStG does not deduct
		(steuerbote.kst.defaults.NON_DEDUCTIBLE_DONATIONS)."""
		mapping = Mapping(MAPPING.chart, (*MAPPING.rules, AccountRule("2380", Category.DONATIONS)))
		books = ledger(debit("2380", "300.00", "JV-11"))
		self.assertEqual(bridge.deductible_in_books(books, mapping), Decimal("1000.00"))
		self.assertEqual(
			bridge.deductible_in_books(bridge.Ledger((credit("2383", "50.00"),), ZERO), MAPPING), ZERO
		)

	def test_no_zuwendungen_need_no_receipts(self):
		books = tuple(line for line in LEDGER if line.account_number != "2383")
		computation = bridge.compute(
			replace(RETURN, donations=()),
			bridge.Ledger(books, sum((item.credit - item.debit for item in books), ZERO), (), BOOKED),
			MAPPING,
			SETTINGS,
			FIGURES,
			translate,
		)
		self.assertEqual(codes(computation), [PROVISIONAL])

	def test_kapitalertragsteuer_of_the_certificates_is_compared_with_that_booked(self):
		ret = replace(RETURN, credits=({"capital_gains_tax": 4000, "solz": 220},))
		(finding,) = self.findings(ret=ret)
		self.assertEqual((finding.code, finding.severity), (bridge.CAPITAL_GAINS_TAX, Severity.HINT))
		self.assertEqual(
			finding.text,
			"The Kapitalertragsteuer of the Steuerbescheinigungen comes to 4.000,00 €, that booked as an expense to 5.000,00 €.",
		)

	def test_contracts_with_shareholders_are_a_hint_for_the_steuerberatung(self):
		(finding,) = self.findings(ret=replace(RETURN, shareholder_contracts=True))
		self.assertEqual(
			(finding.code, finding.severity, finding.reference),
			(CONTRACTS, Severity.HINT, "Anlage WA Zeile 16"),
		)


class TurnoverTest(TestCase):
	"""Anlage Z line 10: where the Zuwendungen exceed 20 % of the Summe der Einkünfte, the deduction may take 4 per
	mille of the turnover and the wages and salaries of the calendar year instead (§ 9 Absatz 1 Nummer 2 Satz 1
	Buchstabe b KStG), and the line is filed, if need be with 0 (rule 8900101)."""

	BOOKS = (credit("8400", "10000.00", "S-1"), debit("2383", "5000.00", "JV-1"))
	MAPPING = Mapping("SKR03", (AccountRule("2383", Category.DONATIONS),))

	def computed(self, **values) -> bridge.Computation:
		ret = bridge.Return(
			YEAR, FROM, TO, donations=({"recipient": "Musterverein e. V.", "amount": 5000},), **values
		)
		books = bridge.Ledger(self.BOOKS, Decimal("5000.00"), (), {})
		return bridge.compute(ret, books, self.MAPPING, SETTINGS, FIGURES, translate)

	def test_the_turnover_not_stated_holds_the_return_back(self):
		computation = self.computed(turnover_and_wages=Decimal("900000"))
		self.assertIn("KST-UMSATZ-FEHLT", codes(computation))
		self.assertIsNone(computation.result.donations.turnover_and_wages)

	def test_a_turnover_of_0_counts_once_stated(self):
		computation = self.computed(turnover_and_wages_given=True)
		self.assertNotIn("KST-UMSATZ-FEHLT", codes(computation))
		self.assertEqual(computation.result.donations.turnover_and_wages, ZERO)
		self.assertEqual(line(computation.lines, "E8006001")["form_amount"], ZERO)


class BookedTaxesTest(TestCase):
	"""The Vorauszahlungen booked and the provisions already posted, from the postings on the accounts of the taxes."""

	ACCOUNTS = ACCOUNTS["SKR03"]

	def test_a_voucher_that_touches_no_provision_is_a_vorauszahlung(self):
		postings = (
			Posting("Journal Entry:JV-1", "2200", Decimal("2500.00"), ZERO),
			Posting("Journal Entry:JV-1", "1200", ZERO, Decimal("2500.00")),
			Posting("Journal Entry:JV-2", "4320", Decimal("3750.00"), ZERO),
			Posting("Journal Entry:JV-3", "2200", ZERO, Decimal("100.00")),
		)
		prepaid, posted = bridge.booked_taxes(postings, self.ACCOUNTS)
		self.assertEqual(prepaid, {"KSt": Decimal("2400.00"), "SolZ": ZERO, "GewSt": Decimal("3750.00")})
		self.assertEqual(posted, {"KSt": ZERO, "SolZ": ZERO, "GewSt": ZERO})

	def test_a_voucher_on_the_provision_or_the_refund_is_a_provision(self):
		accounts = self.ACCOUNTS
		postings = (
			Posting("Journal Entry:JV-7", accounts.kst.expense, Decimal("1772.40"), ZERO),
			Posting("Journal Entry:JV-7", accounts.kst.provision, ZERO, Decimal("1772.40")),
			Posting("Journal Entry:JV-8", accounts.gewst.expense, ZERO, Decimal("80.00")),
			Posting("Journal Entry:JV-8", accounts.gewst.refund, Decimal("80.00"), ZERO),
		)
		prepaid, posted = bridge.booked_taxes(postings, accounts)
		self.assertEqual(prepaid, {"KSt": ZERO, "SolZ": ZERO, "GewSt": ZERO})
		self.assertEqual(posted, {"KSt": Decimal("1772.40"), "SolZ": ZERO, "GewSt": Decimal("-80.00")})

	def test_the_ledger_keeps_what_it_is_given(self):
		books = bridge.Ledger(
			[credit("8400", "100.00")], Decimal("100.00"), [bridge.Unnumbered("Erlöse", ZERO)], {"KSt": ZERO}
		)
		self.assertIsInstance(books.lines, tuple)
		self.assertIsInstance(books.unnumbered, tuple)
		with self.assertRaises(TypeError):
			books.booked_prepayments["KSt"] = Decimal("1")


class Kst1Test(TestCase):
	"""KSt 1 from the settings and the return."""

	def kst1(self, ret: bridge.Return = RETURN, settings=SETTINGS) -> dict:
		return dict(entries(bridge.filed_vordrucke(ret, (), settings), "KSt1").items())

	def test_names_the_company_its_seats_the_wirtschaftsjahr_and_the_shareholder(self):
		self.assertEqual(
			self.kst1(),
			{
				("E8000016", ()): True,
				("E8000101", ()): "Muster IT GmbH",
				("E8000501", ()): "Musterstadt",
				("E8000601", ()): "Musterstadt",
				("E8001105", ()): "350",
				("E8002606", ()): FROM,
				("E8002607", ()): TO,
				("E8001007", ()): False,
				("E8122111", (0,)): False,
				("E8122101", (0,)): "Erika Muster",
				("E8122102", (0,)): "Musterweg 2",
				("E8122103", (0,)): "12345 Musterstadt",
				("E8122104", (0, 0)): Decimal("25000"),
				("E8122105", (0, 0)): Decimal("100"),
				("E8122106", (0, 0)): FROM,
				("E8122107", (0, 0)): TO,
				("E8122601", ()): False,
			},
		)

	def test_without_settings_names_what_the_return_knows(self):
		self.assertEqual(
			self.kst1(settings=None),
			{
				("E8000016", ()): True,
				("E8002606", ()): FROM,
				("E8002607", ()): TO,
				("E8001007", ()): False,
				("E8122601", ()): False,
			},
		)

	def test_the_qualified_free_text_goes_with_its_key(self):
		filed = self.kst1(
			replace(RETURN, supplement_key="2", supplement_text="  Abweichende Auffassung zu § 8b  ")
		)
		self.assertEqual(
			(filed[("E8001305", ())], filed[("E8001304", ())]), ("2", "Abweichende Auffassung zu § 8b")
		)
		self.assertNotIn(("E8001304", ()), self.kst1(replace(RETURN, supplement_text="   ")))

	def test_a_company_founded_in_the_year_says_so_and_its_shareholders_changed(self):
		founded = date(2026, 3, 1)
		settings = replace(
			SETTINGS,
			company=replace(COMPANY, founded_on=founded),
			shareholders=(shareholder(from_date=founded),),
		)
		filed = self.kst1(replace(RETURN, from_date=founded), settings)
		self.assertIs(filed[("E8000703", ())], True)
		self.assertIs(filed[("E8122601", ())], True)
		self.assertIs(filed[("E8122111", (0,))], True)
		self.assertEqual(filed[("E8122106", (0, 0))], founded)

	def test_says_for_each_shareholder_whether_its_data_changed(self):
		"""KSt 1 line 21a: ERiC refuses an Anteilseigner without it, rule 8912022 („NichtAlleFelderOderKeinFeldAngegeben
		(E8122111, E8122101, E8122102, E8122103)“, Jahresdokumentation KSt 2025; validation with ERiC 44.3.6.0). A
		shareholder whose holding begins or ends within the Wirtschaftsjahr changed, one who held all year did not."""
		settings = replace(
			SETTINGS,
			shareholders=(
				shareholder(percent="60"),
				shareholder(row=2, name="Max Muster", percent="40", from_date=date(2026, 7, 1)),
			),
		)
		filed = self.kst1(settings=settings)
		self.assertEqual((filed[("E8122111", (0,))], filed[("E8122111", (1,))]), (False, True))

	def test_the_trading_book_and_the_steuerberatung_of_the_year(self):
		advisor = bridge.Advisor(
			name="Muster Steuerberatung GmbH", town="12345 Musterstadt", client_number="4711"
		)
		settings = replace(SETTINGS, company=replace(COMPANY, section_8b_7=True, advisor=advisor))
		filed = self.kst1(settings=settings)
		self.assertIs(filed[("E8001008", ())], True)
		self.assertEqual(
			{key: filed[key] for key in filed if key[0] in ("E8001901", *bridge.ADVISOR_FIELDS.values())},
			{
				("E8001901", ()): True,
				("E8019910", ()): "Muster Steuerberatung GmbH",
				("E8019913", ()): "12345 Musterstadt",
				("E8019916", ()): "4711",
			},
		)

	def test_each_shareholder_once_with_at_most_three_periods_cut_to_the_wirtschaftsjahr(self):
		periods = (
			shareholder(1, "Erika Muster", "50", to_date=date(2026, 3, 31)),
			shareholder(2, "Erika  Muster", "60", from_date=date(2026, 4, 1), to_date=date(2026, 6, 30)),
			shareholder(3, "erika muster", "70", from_date=date(2026, 7, 1), to_date=date(2026, 9, 30)),
			shareholder(4, "Erika Muster", "80", from_date=date(2026, 10, 1)),
			shareholder(5, "Max Muster", "50", to_date=date(2025, 12, 31)),
			shareholder(6, "Max Muster", "20", from_date=date(2027, 1, 1)),
		)
		found = bridge.shareholder_entries(RETURN, periods)
		self.assertEqual({entry.rows[0] for entry in found}, {0})
		self.assertEqual(
			[(entry.rows, entry.value) for entry in found if entry.feldkennung == "E8122105"],
			[((0, 0), Decimal("50")), ((0, 1), Decimal("60")), ((0, 2), Decimal("70"))],
		)
		self.assertEqual(
			[entry.value for entry in found if entry.feldkennung in ("E8122106", "E8122107")][:2],
			[FROM, date(2026, 3, 31)],
		)
		self.assertTrue(bridge.shareholders_changed(RETURN, periods))

	def test_shareholders_changed_once_a_period_begins_or_ends_before_the_last_day(self):
		for shareholders, changed in (
			((shareholder(),), False),
			((shareholder(to_date=TO),), False),
			((shareholder(to_date=date(2026, 12, 30)),), True),
			((shareholder(from_date=date(2026, 12, 31)),), True),
			((shareholder(to_date=date(2025, 12, 31)),), False),
		):
			with self.subTest(shareholders=shareholders):
				self.assertIs(bridge.shareholders_changed(RETURN, shareholders), changed)

	def test_the_numbers_of_a_shareholder_go_to_elster(self):
		person = shareholder(tax_number="9198011310010", idnr="12345678903")
		found = bridge.shareholder_entries(RETURN, (person,))
		self.assertEqual(
			[entry.feldkennung for entry in found][:5],
			["E8122109", "E8122110", "E8122101", "E8122102", "E8122103"],
		)
		self.assertEqual(bridge.IDENTIFIERS, {"E8122109", "E8122110", "E8122112", "E8122113"})

	def test_the_kst_1_takes_the_w_idnr_without_its_unterscheidungsmerkmal(self):
		"""KSt 1 line 23b holds the W-IdNr. in eleven characters (E30-2025.xsd, E8122112); the settings may hold it with
		the Unterscheidungsmerkmal the GCD of the E-Bilanz takes."""
		person = shareholder(wid_nr="DE123456788-00001")
		found = {entry.feldkennung: entry.value for entry in bridge.shareholder_entries(RETURN, (person,))}
		self.assertEqual(found["E8122112"], "DE123456788")


class KSt1FTest(TestCase):
	"""KSt 1 F: the Leistungen of the Wirtschaftsjahr and the Einlagen, with the steuerliches Einlagekonto (§ 27 KStG)."""

	DISTRIBUTIONS = (
		{
			"kind": "Ordinary Distribution",
			"resolution_date": "2026-05-15",
			"outflow_date": date(2026, 5, 20),
			"amount": 30000,
		},
		{
			"kind": "Hidden Distribution",
			"outflow_date": "2026-11-30",
			"amount": 2500,
			"certified_reduction": 2500,
		},
	)
	CONTRIBUTIONS = (
		{
			"shareholder": "Erika Muster",
			"contribution_date": "2026-02-01",
			"treatment": "Not Booked to Profit",
			"kind": "Cash Contribution",
			"amount": 10000,
		},
		{
			"shareholder": " Erika Muster ",
			"contribution_date": date(2026, 4, 1),
			"treatment": "Booked to Profit and Paid",
			"kind": "Contribution in Kind",
			"description": " Notebook ",
			"amount": 1500,
		},
		{"shareholder": "Erika Muster", "treatment": "Booked to Profit, Not Paid", "amount": 700},
		{
			"shareholder": "Erika Muster",
			"contribution_date": "2026-06-30",
			"treatment": "Other Contribution",
			"amount": 5000,
		},
	)
	EINLAGEKONTO = (
		rules.CarryForward(
			rules.CarryForwardKind.EINLAGEKONTO, date(2025, 12, 31), Decimal("40000"), confirmed=True
		),
	)

	def computed(self, **values) -> bridge.Computation:
		ret = replace(RETURN, distributions=self.DISTRIBUTIONS, contributions=self.CONTRIBUTIONS, **values)
		return compute(ret, settings=replace(SETTINGS, carry_forwards=self.EINLAGEKONTO))

	def test_the_einlagen_go_to_their_lines_of_anlage_gk_and_kst_1_f(self):
		computation = self.computed()
		lines = computation.result.lines
		self.assertEqual(
			{key: lines[key].declared for key in bridge.CONTRIBUTION_STEPS.values()},
			{
				"contributions_paid": Decimal("1500"),
				"contributions_unpaid": Decimal("700"),
				"contributions_not_booked": Decimal("10000"),
			},
		)
		self.assertEqual(lines["contributions_not_booked"].manual[0].reason, "Erika Muster, 01.02.2026")
		self.assertEqual(lines["contributions_unpaid"].manual[0].reason, "Erika Muster")
		unnamed = replace(RETURN, contributions=({"treatment": "Booked to Profit, Not Paid", "amount": 700},))
		self.assertEqual(
			compute(unnamed).result.lines["contributions_unpaid"].manual[0].reason,
			"Booked to Profit, Not Paid",
		)
		self.assertEqual(
			bridge.contributions_by_line(self.CONTRIBUTIONS),
			(Decimal("1500.00"), Decimal("10000.00"), Decimal("5000.00")),
		)

	def test_the_einlagekonto_takes_the_einlagen_paid_and_the_distributions(self):
		computation = self.computed(
			previous_equity=Decimal("120000"), previous_nominal_capital=Decimal("25000")
		)
		account = computation.einlagekonto
		self.assertEqual(account.contributions, Decimal("16500.00"))
		self.assertEqual(account.distributions, Decimal("32500.00"))
		self.assertEqual(account.certified_reduction, Decimal("2500.00"))
		filed = entries((computation.kst1f,), "KSt1F")
		self.assertEqual(
			(filed[("E8201001", ())], filed[("E8201101", ())]), (Decimal("120000"), Decimal("25000"))
		)
		self.assertEqual(computation.values["einlagekonto"], account.closing)

	def test_without_the_equity_of_the_previous_year_the_einlagekonto_has_no_ausschuettbarer_gewinn(self):
		computation = self.computed()
		self.assertIsNone(computation.einlagekonto.distributable)
		self.assertNotIn(("E8201001", ()), entries((computation.kst1f,), "KSt1F"))
		self.assertEqual(bridge.previous_equity(RETURN), (None, None))
		self.assertEqual(
			bridge.previous_equity(replace(RETURN, previous_equity=Decimal("-3000"))),
			(Decimal("-3000.00"), ZERO),
		)

	def test_the_single_leistungen_and_einlagen_are_filed(self):
		"""Each Leistung with its kind, day, amount and certified reduction (rule 8912016), each Einlage with its
		shareholder, day and kind (rule 8920300)."""
		ret = replace(RETURN, distributions=self.DISTRIBUTIONS, contributions=self.CONTRIBUTIONS)
		filed = entries(bridge.filed_vordrucke(ret, reported(self.computed().lines), SETTINGS), "KSt1F")
		self.assertEqual(
			{
				key: value
				for key, value in filed.items()
				if key[1] or key[0] in ("E8121406", "E8122011", "E8122003")
			},
			{
				("E8122020", (0,)): "1",
				("E8122021", (0,)): date(2026, 5, 15),
				("E8122022", (0,)): date(2026, 5, 20),
				("E8122023", (0,)): Decimal("30000.00"),
				("E8122024", (0,)): ZERO,
				("E8122020", (1,)): "2",
				("E8122022", (1,)): date(2026, 11, 30),
				("E8122023", (1,)): Decimal("2500.00"),
				("E8122024", (1,)): Decimal("2500.00"),
				("E8121406", ()): Decimal("32500.00"),
				("E8122011", ()): True,
				("E8122003", ()): Decimal("2500"),
				("E8241510", (0,)): "Erika Muster",
				("E8241514", (0,)): date(2026, 2, 1),
				("E8241515", (0,)): "1",
				("E8241510", (1,)): "Erika Muster",
				("E8241514", (1,)): date(2026, 4, 1),
				("E8241515", (1,)): "2",
				("E8241516", (1,)): "Notebook",
				("E8241510", (2,)): "Erika Muster",
				("E8241514", (2,)): date(2026, 6, 30),
				("E8241515", (2,)): "1",
			},
		)

	def test_an_einlage_files_what_its_row_holds(self):
		ret = replace(
			RETURN,
			contributions=(
				{"shareholder": "Erika Muster", "treatment": "Other Contribution", "amount": 100},
			),
		)
		filed = entries(bridge.filed_vordrucke(ret, (), SETTINGS), "KSt1F")
		self.assertEqual(
			{key: value for key, value in filed.items() if key[1]},
			{("E8241510", (0,)): "Erika Muster", ("E8241515", (0,)): "1"},
		)

	def test_leistungen_without_a_certified_reduction_state_0_for_it(self):
		"""Rules 8912016 and 8920254: each Leistung states its certified reduction, and line 12 their sum."""
		ret = replace(RETURN, distributions=self.DISTRIBUTIONS[:1])
		filed = entries(bridge.filed_vordrucke(ret, (), SETTINGS), "KSt1F")
		self.assertEqual((filed[("E8122024", (0,))], filed[("E8122003", ())]), (ZERO, ZERO))
		self.assertNotIn(("E8122011", ()), filed)
		self.assertEqual(entries(bridge.filed_vordrucke(RETURN, (), SETTINGS), "KSt1F"), {})


class FiledVordruckeTest(TestCase):
	"""The Vordrucke the return files, from its lines as stored."""

	def setUp(self):
		self.rows = reported(compute().lines)

	def test_a_field_that_takes_no_zero_is_left_out_at_zero(self):
		"""Anlage GK line 78 takes no zero (Formatkennzeichen G), line 11 does (N)."""
		rows = [
			*({**row, "reported": ZERO} if row["feldkennung"] == "E8002001" else row for row in self.rows),
			{"feldkennung": "E8002801", "reported": ZERO, "manual": 0},
		]
		filed = entries(bridge.filed_vordrucke(RETURN, rows, SETTINGS), "GK")
		self.assertNotIn(("E8002801", ()), filed)
		self.assertEqual(filed[("E8002001", ())], ZERO)

	def test_anlage_z_names_each_receipt_and_where_its_recipient_lies(self):
		ret = replace(
			RETURN,
			donations=(
				{"recipient": " Musterverein e. V. ", "amount": 600},
				{"recipient": "Stiftung Muster, Wien", "amount": 400, "abroad": 1},
			),
		)
		filed = entries(bridge.filed_vordrucke(ret, self.rows, SETTINGS), "Z")
		self.assertEqual(
			{key: value for key, value in filed.items() if key[1]},
			{
				("E8005603", (0,)): "Musterverein e. V.",
				("E8005604", (0,)): Decimal("600.00"),
				("E8005605", (0,)): "1",
				("E8005603", (1,)): "Stiftung Muster, Wien",
				("E8005604", (1,)): Decimal("400.00"),
				("E8005605", (1,)): "2",
			},
		)

	def test_anlage_z_line_9_sums_the_receipts_abroad_rounded_down(self):
		"""Rules 8901015 and 8901017."""
		ret = replace(
			RETURN,
			donations=(
				{"recipient": "Stiftung Muster, Wien", "amount": Decimal("400.70"), "abroad": 1},
				{"recipient": "Fondation Muster, Luxemburg", "amount": Decimal("99.10"), "abroad": 1},
			),
		)
		self.assertEqual(
			entries(bridge.filed_vordrucke(ret, self.rows, SETTINGS), "Z")[("E8009601", ())], Decimal("499")
		)
		self.assertNotIn(("E8009601", ()), entries(bridge.filed_vordrucke(RETURN, self.rows, SETTINGS), "Z"))

	def test_without_anlage_z_no_receipt_is_filed(self):
		rows = [row for row in self.rows if row["form"] != "Z"]
		forms = [vordruck.form for vordruck in bridge.filed_vordrucke(RETURN, rows, SETTINGS)]
		self.assertNotIn("Z", forms)

	def test_anlage_wa_says_whether_contracts_with_shareholders_were_made(self):
		for contracts in (False, True):
			with self.subTest(contracts=contracts):
				filed = entries(
					bridge.filed_vordrucke(
						replace(RETURN, shareholder_contracts=contracts), self.rows, SETTINGS
					),
					"WA",
				)
				self.assertIs(filed[("E8122801", ())], contracts)

	def test_anlage_gk_and_kst_1_f_carry_the_indexfeld_of_the_first_wirtschaftsjahr(self):
		filed = bridge.filed_vordrucke(RETURN, self.rows, SETTINGS)
		self.assertEqual(
			{vordruck.form: vordruck.wj for vordruck in filed},
			{"KSt1": None, "GK": "WJ1", "ZVE": None, "Z": None, "WA": None, "KSt1F": "WJ1"},
		)


class RulesTest(TestCase):
	"""The rules of the Jahresdokumentation E30 that Steuerbote checks itself, on the Vordrucke as filed."""

	def test_a_rule_that_fails_gives_its_fehlercode(self):
		filed = (Vordruck("KSt1", (Entry("E8000016", True), Entry("E8002606", FROM), Entry("E8002607", TO))),)
		found = bridge.rule_findings(YEAR, filed, translate)
		self.assertEqual([item.code for item in found], ["8900744", "8900368"])
		self.assertTrue(all(item.blocking for item in found))
		self.assertTrue(found[0].text.startswith("Die Regel 8900744"))

	def test_vordrucke_elster_would_not_take_are_one_error(self):
		filed = (Vordruck("KSt1", (Entry("E8000101", "M" * 104),)),)
		(finding,) = bridge.rule_findings(YEAR, filed, translate)
		self.assertEqual((finding.code, finding.reference), (NUTZDATEN, "KSt"))
		self.assertEqual(
			finding.text,
			"The return cannot be written as ELSTER takes it: Bezeichnung der Körperschaft, Personenvereinigung oder "
			"Vermögensmasse has 104 characters, ELSTER takes at most 103.",
		)

	def test_the_text_of_what_the_writer_refused_is_translated(self):
		german = {"Name": "Bezeichnung", "{label} has {0} characters": "{label} hat {0} Zeichen"}
		error = XmlError("{label} has {0} characters", 104, label="Name")
		self.assertEqual(
			bridge.xml_text(error, lambda text: german.get(text, text)), "Bezeichnung hat 104 Zeichen"
		)
		self.assertEqual(
			bridge.xml_text(XmlError("{label}{0} is no number", "x"), translate), "x is no number"
		)
		self.assertEqual(bridge.xml_text(ValueError("no field E9999999"), str.upper), "no field E9999999")


class ProvisionalTest(TestCase):
	"""The forms of 2026 come provisionally from the Jahresdokumentation 2025 (steuerbote.kst.years): the return is
	not ready until ELSTER publishes those of 2026."""

	def test_2026_takes_the_forms_of_2025_provisionally(self):
		self.assertEqual(bridge.provisional(YEAR), (True, 2025))

	def test_a_year_with_its_own_forms_holds_nothing_back(self):
		with patch.object(bridge, "provisional", return_value=(False, YEAR)):
			self.assertEqual(codes(compute()), [])

	def test_the_finding_names_the_year_and_the_jahresdokumentation(self):
		finding = bridge.provisional_finding("KST-VORLAEUFIG", 2027, 2026, translate)
		self.assertEqual(
			finding.text,
			"Steuerbote has the forms of 2027 provisionally from the Jahresdokumentation 2026: until ELSTER publishes "
			"those of 2027, the return is not ready. A filing needs this error acknowledged with the reason why it goes nonetheless.",
		)
		self.assertEqual(
			(finding.code, finding.reference, finding.blocking),
			("KST-VORLAEUFIG", "Jahresdokumentation 2026", True),
		)


class TextsTest(TestCase):
	def test_every_text_has_its_values_apart(self):
		self.assertEqual(len(bridge.MESSAGES), len(set(bridge.MESSAGES)))
		self.assertEqual(len(bridge.CODES), len(set(bridge.CODES)))
		self.assertTrue(all(code.startswith("KST-") for code in bridge.CODES))

	def test_a_bridge_error_keeps_its_template_and_values(self):
		error = BridgeError(bridge.NOT_WHOLE, "E8002001", "1.50")
		self.assertEqual(
			(error.template, error.values, str(error)),
			(bridge.NOT_WHOLE, ("E8002001", "1.50"), "The line E8002001 files whole euros, not 1.50."),
		)

	def test_a_reference_keeps_to_the_length_of_its_field(self):
		self.assertEqual(len(bridge.error("KST-X", "Text", "R" * 200).reference), 140)

	def test_describe_leaves_the_line_of_a_field_without_one_empty(self):
		field = Field("KSt1", "", "E8000016", "Einlagekonto", "J")
		self.assertEqual(
			bridge.describe(field),
			{"feldkennung": "E8000016", "form": "KSt1", "line": "", "label": "Einlagekonto"},
		)

	def test_a_return_and_the_settings_keep_their_tables_as_tuples(self):
		ret = bridge.Return(YEAR, FROM, TO, lines=[{}], credits=[{}])
		settings = bridge.Settings(COMPANY, shareholders=[shareholder()])
		self.assertEqual(
			(type(ret.lines), type(ret.credits), type(settings.shareholders)), (tuple, tuple, tuple)
		)
		self.assertEqual(ret.opening_day, date(2025, 12, 31))


def einheitsbilanz(**values) -> bridge.EBilanz:
	"""The Einheitsbilanz of the worked example, whose Jahresüberschuss is that of the books."""
	fields = {
		"name": "EB-2026-00001",
		"accounting_standard": "HAOE",
		"net_income": Decimal("88175.00"),
		"tax_net_income": Decimal("88175.00"),
	}
	return bridge.EBilanz(**{**fields, **values})


def handelsbilanz(**values) -> bridge.EBilanz:
	"""A Handelsbilanz whose Steuerbilanz has 2,000 euros more, a Rückstellung für drohende Verluste it does not keep
	(§ 5 Absatz 4a EStG)."""
	fields = {
		"name": "EB-2026-00002",
		"accounting_standard": "HGBM",
		"net_income": Decimal("88175.00"),
		"tax_net_income": Decimal("90175.00"),
		"transfers": 2,
	}
	return bridge.EBilanz(**{**fields, **values})


class EBilanzTest(TestCase):
	"""Anlage GK line 11 from the E-Bilanz of the Wirtschaftsjahr: its Jahresüberschuss, under HGBM that of the
	Handelsbilanz with the Überleitung to the Steuerbilanz (contract of stage 3, 3.3)."""

	def computed(self, ebilanz, rows=(), books: bridge.Ledger | None = None) -> bridge.Computation:
		return compute(replace(RETURN, ebilanz=ebilanz, lines=tuple(rows)), books)

	def own_codes(self, computation) -> list[str]:
		return [code for code in codes(computation) if code != PROVISIONAL]

	def test_an_einheitsbilanz_gives_line_11_its_jahresueberschuss(self):
		computation = self.computed(einheitsbilanz())
		self.assertEqual(computation.values, compute().values)
		self.assertEqual(computation.result.lines["net_income"].manual, ())
		self.assertEqual(self.own_codes(computation), [])

	def test_a_steuerbilanz_gives_line_11_its_jahresueberschuss_as_it_is(self):
		computation = self.computed(einheitsbilanz(accounting_standard="AO"))
		self.assertEqual(computation.values["zve"], Decimal("111200"))
		self.assertEqual(self.own_codes(computation), [])

	def test_a_handelsbilanz_gives_line_11_the_jahresueberschuss_after_the_ueberleitung(self):
		computation = self.computed(handelsbilanz())
		net_income = computation.result.lines["net_income"]
		self.assertEqual(
			(net_income.ledger, net_income.exact, net_income.declared),
			(Decimal("88175.00"), Decimal("90175.00"), Decimal("90175")),
		)
		(manual,) = net_income.manual
		self.assertEqual(
			(manual.step, manual.amount, manual.reason),
			("net_income", Decimal("2000.00"), "Überleitungsrechnung of the E-Bilanz EB-2026-00002"),
		)
		self.assertEqual(
			{name: computation.values[name] for name in ("net_income", "zve", "kst", "solz")},
			{
				"net_income": Decimal("90175"),
				"zve": Decimal("113200"),
				"kst": Decimal("16980"),
				"solz": Decimal("933.90"),
			},
		)
		row = line(computation.lines, "E8002001")
		self.assertEqual((row["ledger_amount"], row["form_amount"]), (Decimal("88175.00"), Decimal("90175")))
		self.assertEqual(self.own_codes(computation), [])

	def test_the_ueberleitung_is_the_difference_of_the_steuerbilanz_to_the_handelsbilanz(self):
		self.assertEqual(bridge.ueberleitung_lines(None, translate), ())
		self.assertEqual(bridge.ueberleitung_lines(einheitsbilanz(), translate), ())
		lower = handelsbilanz(tax_net_income=Decimal("87175.50"))
		(manual,) = bridge.ueberleitung_lines(lower, translate)
		self.assertEqual(manual.amount, Decimal("-999.50"))

	def test_a_jahresueberschuss_other_than_that_of_the_books_holds_the_return_back(self):
		"""The books hold the provisions posted after the E-Bilanz was calculated: line 11 would leave out the taxes
		that Anlage GK lines 81 to 84 add back from the books."""
		stale = einheitsbilanz(net_income=Decimal("89175.00"), tax_net_income=Decimal("89175.00"))
		computation = self.computed(stale)
		self.assertEqual(computation.values["net_income"], Decimal("89175"))
		(finding,) = [found for found in computation.findings if found.code == bridge.EBILANZ_DIFFERS]
		self.assertEqual((finding.severity, finding.reference), (Severity.ERROR, "Anlage GK Zeile 11"))
		self.assertEqual(
			finding.text,
			"The Jahresüberschuss of the E-Bilanz EB-2026-00001 is 89.175,00 €, that of the profit and loss account of "
			"the books 88.175,00 €: a difference of 1.000,00 €. After a posting such as that of the provisions, "
			"calculate the E-Bilanz again and then the return, so that line 11 of Anlage GK rests on the books its "
			"other lines come from.",
		)

	def test_a_difference_of_less_than_a_euro_is_the_rounding_of_line_11(self):
		close = einheitsbilanz(net_income=Decimal("88175.99"), tax_net_income=Decimal("88175.99"))
		self.assertEqual(self.own_codes(self.computed(close)), [])
		beyond = einheitsbilanz(net_income=Decimal("88174.00"), tax_net_income=Decimal("88174.00"))
		self.assertEqual(self.own_codes(self.computed(beyond)), [bridge.EBILANZ_DIFFERS])

	def test_an_e_bilanz_of_another_finance_book_differs_with_a_hint(self):
		other = einheitsbilanz(
			accounting_standard="AO",
			net_income=Decimal("90175.00"),
			tax_net_income=Decimal("90175.00"),
			same_books=False,
		)
		(finding,) = [
			found for found in self.computed(other).findings if found.code == bridge.EBILANZ_DIFFERS
		]
		self.assertEqual(finding.severity, Severity.HINT)
		self.assertTrue(finding.text.startswith("The E-Bilanz EB-2026-00001 reads another finance book"))

	def test_a_handelsbilanz_without_entries_of_the_ueberleitung_holds_the_return_back(self):
		without = handelsbilanz(tax_net_income=Decimal("88175.00"), transfers=0)
		(finding,) = [found for found in self.computed(without).findings if found.code == NO_UEBERLEITUNG]
		self.assertEqual((finding.severity, finding.reference), (Severity.ERROR, "§ 60 Absatz 2 EStDV"))
		self.assertTrue(finding.text.startswith("The E-Bilanz EB-2026-00002 is a Handelsbilanz"))

	def test_the_e_bilanz_and_not_the_settings_says_whether_line_11_needs_an_ueberleitung(self):
		settings = replace(SETTINGS, company=replace(COMPANY, accounting_standard="HGBM"))
		ret = replace(RETURN, ebilanz=einheitsbilanz())
		self.assertNotIn(NO_UEBERLEITUNG, codes(compute(ret, settings=settings)))

	def test_lines_by_hand_on_line_11_beside_the_e_bilanz_would_count_the_ueberleitung_twice(self):
		rows = reported(compute().lines)
		for case, changed in (
			("line by hand", [*rows, by_hand("E8002001", "-1000")]),
			("correction", corrected(rows, "E8002001", "87000")),
		):
			with self.subTest(case=case):
				computation = self.computed(handelsbilanz(), changed)
				(finding,) = [
					found for found in computation.findings if found.code == bridge.UEBERLEITUNG_TWICE
				]
				self.assertEqual(
					(finding.severity, finding.reference), (Severity.ERROR, "Anlage GK Zeile 11")
				)
		self.assertNotIn(bridge.UEBERLEITUNG_TWICE, codes(self.computed(handelsbilanz(), rows)))


class PriorEBilanzTest(TestCase):
	"""KSt 1 F lines 17 and 18 from the E-Bilanz filed for the previous Wirtschaftsjahr, else by hand."""

	def setUp(self):
		self.prior = bridge.PriorEBilanz("EB-2025-00001", 2025, Decimal("120000.40"), Decimal("25000.00"))

	def computed(self, **values) -> bridge.Computation:
		ret = replace(RETURN, distributions=KSt1FTest.DISTRIBUTIONS, **values)
		return compute(ret, settings=replace(SETTINGS, carry_forwards=KSt1FTest.EINLAGEKONTO))

	def sources(self, computation) -> list:
		return [found for found in computation.findings if found.code == bridge.EQUITY_SOURCE]

	def test_kst_1_f_takes_the_steuerbilanz_of_the_e_bilanz_filed_for_the_previous_year(self):
		computation = self.computed(prior_ebilanz=self.prior)
		filed = entries((computation.kst1f,), "KSt1F")
		self.assertEqual(
			(filed[("E8201001", ())], filed[("E8201101", ())]), (Decimal("120000"), Decimal("25000"))
		)
		self.assertEqual(computation.einlagekonto.distributable, Decimal("55000"))
		(finding,) = self.sources(computation)
		self.assertEqual((finding.severity, finding.reference), (Severity.HINT, "KSt 1 F Zeilen 17 und 18"))
		self.assertEqual(
			finding.text,
			"KSt 1 F lines 17 and 18 take the Eigenkapital laut Steuerbilanz of 120.000,00 € and the Nennkapital of "
			"25.000,00 € at the end of the previous Wirtschaftsjahr from the E-Bilanz EB-2025-00001 filed for 2025.",
		)

	def test_the_e_bilanz_comes_before_the_amounts_by_hand(self):
		computation = self.computed(
			prior_ebilanz=self.prior,
			previous_equity=Decimal("110000"),
			previous_nominal_capital=Decimal("25000"),
		)
		self.assertEqual(
			bridge.previous_equity(replace(RETURN, prior_ebilanz=self.prior)),
			(Decimal("120000"), Decimal("25000")),
		)
		(finding,) = self.sources(computation)
		self.assertTrue(
			finding.text.endswith(
				"filed for 2025; the amounts by hand, 110.000,00 € and 25.000,00 €, do not count."
			)
		)
		same = self.computed(
			prior_ebilanz=self.prior,
			previous_equity=Decimal("120000"),
			previous_nominal_capital=Decimal("25000"),
		)
		self.assertTrue(self.sources(same)[0].text.endswith("filed for 2025."))

	def test_the_steuerbilanz_is_rounded_half_up_to_whole_euros(self):
		for equity, expected in (("120000.50", "120001"), ("-3000.50", "-3001"), ("99.49", "99")):
			with self.subTest(equity=equity):
				prior = replace(self.prior, equity=Decimal(equity))
				self.assertEqual(
					bridge.previous_equity(replace(RETURN, prior_ebilanz=prior)),
					(Decimal(expected), Decimal("25000")),
				)

	def test_without_a_filed_e_bilanz_the_amounts_by_hand_count_and_the_hint_says_so(self):
		computation = self.computed(
			previous_equity=Decimal("110000"), previous_nominal_capital=Decimal("25000")
		)
		self.assertEqual(entries((computation.kst1f,), "KSt1F")[("E8201001", ())], Decimal("110000"))
		(finding,) = self.sources(computation)
		self.assertEqual(
			finding.text,
			"KSt 1 F lines 17 and 18 take the amounts by hand, 110.000,00 € and 25.000,00 €: no E-Bilanz of 2025 is "
			"filed whose Steuerbilanz would give them.",
		)

	def test_without_either_the_return_says_nothing_of_them(self):
		self.assertEqual(self.sources(self.computed()), [])
