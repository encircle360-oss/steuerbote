"""The bridge between the Trade Tax Return and the core of the Gewerbesteuer, without a bench: the worked example
„Muster IT GmbH“ of the research of stage 3 on the Körperschaftsteuer of its Corporate Income Tax Return, and each
rule of the bridge on invented figures."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from steuerbote.kst.form import Entry, Vordruck
from steuerbote.kst.tests.support import FIGURES
from steuerbote.kst.tests.test_golden import MAPPING
from steuerbote.steuerbote.doctype.annual_filing_settings import rules
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge as kst
from steuerbote.steuerbote.doctype.corporate_income_tax_return import test_bridge as corporate
from steuerbote.steuerbote.doctype.trade_tax_return import bridge
from steuerbote.steuerbote.doctype.trade_tax_return.bridge import (
	DETAILS_MISSING,
	ESTABLISHMENTS,
	NOT_IN_EUROS,
	PREPAYMENTS,
	PROVISIONAL,
	UNCONFIRMED,
)

YEAR = corporate.YEAR
FROM, TO = corporate.FROM, corporate.TO
ZERO = Decimal("0")
translate = corporate.translate
AGS = "09999999"
ESTABLISHMENT = rules.Establishment(1, "Musterstadt", "12345", AGS, date(2020, 1, 1), hebenummer="0815")
RATE = rules.TradeTaxRate(AGS, YEAR, Decimal("400"), "Haushaltssatzung 2026 der Stadt Musterstadt")
SETTINGS = replace(corporate.SETTINGS, establishments=(ESTABLISHMENT,), trade_tax_rates=(RATE,))
RETURN = bridge.Return(YEAR, FROM, TO)
GENERAL = frozenset(
	{
		bridge.COMPANY_NAME,
		bridge.BUSINESS_PURPOSE,
		bridge.WID_NR,
		bridge.RECHTSFORM,
		bridge.SEVERAL_MUNICIPALITIES,
		bridge.MOVED,
		bridge.POSTAL_CODE,
		bridge.PLACE,
		bridge.HEBENUMMER,
	}
)


def compute(
	ret: bridge.Return = RETURN,
	settings=SETTINGS,
	corporate_return: kst.Return = corporate.RETURN,
	books: kst.Ledger | None = None,
) -> bridge.Computation:
	books = books or corporate.ledger()
	computation = kst.compute(corporate_return, books, MAPPING, settings, FIGURES, translate)
	return bridge.compute(ret, computation, books, settings, FIGURES, translate)


def codes(computation) -> list[str]:
	return [finding.code for finding in computation.findings]


def line(rows, feldkennung: str) -> dict:
	(found,) = (row for row in rows if row["feldkennung"] == feldkennung)
	return found


def reported(rows) -> list[dict]:
	return [{**row, "reported": row["form_amount"]} for row in rows]


def entries(vordruck: Vordruck) -> dict:
	return {(entry.feldkennung, entry.rows): entry.value for entry in vordruck.entries}


def stated(kind, amount: str, confirmed: bool = True) -> rules.CarryForward:
	return rules.CarryForward(kind, date(2025, 12, 31), Decimal(amount), confirmed=confirmed)


class MusterItGmbhTest(TestCase):
	"""The worked example of the research of stage 3, section 2.4: Gewerbeertrag 107 600 €, Messbetrag 3 766 €, at
	a Hebesatz of 400 % Gewerbesteuer of 15 064,00 €, 64,00 € due after the Vorauszahlungen."""

	def setUp(self):
		self.computation = compute()

	def test_computes_the_gewerbesteuer_of_the_example(self):
		self.assertEqual(
			self.computation.values,
			{
				"profit": Decimal("97200"),
				"financing_addback": Decimal("0.00"),
				"gewerbeertrag": Decimal("107600"),
				"messbetrag": Decimal("3766"),
				"hebesatz": Decimal("400"),
				"gewst": Decimal("15064.00"),
				"prepayments": Decimal("15000.00"),
				"balance": Decimal("64.00"),
			},
		)

	def test_only_the_forms_of_the_year_hold_the_example_back(self):
		self.assertEqual(codes(self.computation), [PROVISIONAL])
		self.assertIn("provisionally from the Jahresdokumentation 2025", self.computation.findings[0].text)

	def test_the_lines_of_gewst_1_a_with_the_books_beside_the_hinzurechnungen(self):
		rows = self.computation.lines
		self.assertEqual(
			[(row["line"], row["feldkennung"], row["form_amount"], row["ledger_amount"]) for row in rows],
			[
				("39", "E4001703", Decimal("97200"), ZERO),
				("50", "E4003202", Decimal("5000"), Decimal("5000.00")),
				("53", "E4003502", Decimal("6000"), Decimal("6000.00")),
				("55", "E4003602", Decimal("24000"), Decimal("24000.00")),
				("56", "E4003703", Decimal("10000"), Decimal("10000.00")),
				("57", "E4004103", ZERO, ZERO),
				("77", "E4006601", Decimal("11400"), ZERO),
				("92d", "E4003403", Decimal("1000"), ZERO),
			],
		)
		self.assertEqual({row["form"] for row in rows}, {"GewSt1A"})
		self.assertTrue(line(rows, "E4001703")["label"])

	def test_the_gemeinde_takes_the_hebesatz_with_its_source_and_all_of_the_tax(self):
		self.assertEqual(
			self.computation.municipalities,
			[
				{
					"municipality": "Musterstadt",
					"postal_code": "12345",
					"ags": AGS,
					"hebenummer": "0815",
					"hebesatz": Decimal("400"),
					"hebesatz_source": "Haushaltssatzung 2026 der Stadt Musterstadt",
					"messbetrag": Decimal("3766"),
					"gewst": Decimal("15064.00"),
					"prepayments": Decimal("15000.00"),
					"balance": Decimal("64.00"),
				}
			],
		)

	def test_a_holding_below_15_percent_has_its_anlage_beg_without_a_kuerzung(self):
		(holding,) = self.computation.holdings
		self.assertEqual(
			holding,
			{
				"holding_name": "Beta GmbH",
				"paragraph": "",
				"dividends": Decimal("12000"),
				"financing_costs": ZERO,
				"other_costs": ZERO,
				"exempt": Decimal("12000"),
				"not_exempt": ZERO,
				"addback": Decimal("11400"),
				"cut_base": ZERO,
				"cut_financing_costs": ZERO,
				"cut_other_costs": ZERO,
				"cut": ZERO,
			},
		)

	def test_the_vordrucke_filed_pass_the_rules_steuerbote_checks(self):
		filed = bridge.filed_vordrucke(
			RETURN,
			reported(self.computation.lines),
			self.computation.holdings,
			self.computation.municipalities,
			corporate.RETURN.donations,
			SETTINGS,
		)
		self.assertEqual([vordruck.form for vordruck in filed], ["GewSt1A", "BEG"])
		self.assertEqual(bridge.rule_findings(YEAR, filed, translate), [])
		general = entries(filed[0])
		self.assertEqual(
			{key: value for key, value in general.items() if key[0] in GENERAL},
			{
				("E4000101", ()): "Muster IT GmbH",
				("E4000201", ()): "Softwareentwicklung",
				("E4000501", ()): "350",
				("E4001506", ()): False,
				("E4001102", ()): False,
				("E4001110", ()): "12345",
				("E4001111", ()): "Musterstadt",
				("E4001803", ()): "0815",
			},
		)
		self.assertEqual(
			{key: value for key, value in general.items() if key[1]},
			{
				("E4009220", (0,)): "Musterverein e. V.",
				("E4009221", (0,)): Decimal("1000.00"),
				("E4009222", (0,)): "1",
			},
		)


class HoldingsTest(TestCase):
	"""Anlage BEG of each holding whose dividends the Körperschaftsteuer exempts: § 8 Nummer 5 GewStG adds back what a
	holding below 15 % paid, § 9 Nummer 2a and 7 GewStG cut what one of 15 % or more paid."""

	def computed(self, holding: rules.Holding) -> bridge.Computation:
		settings = replace(SETTINGS, holdings=(corporate.SETTINGS.holdings[0], holding))
		results = (
			corporate.HOLDING_RESULTS[0],
			{
				**corporate.HOLDING_RESULTS[1],
				"financing_costs": Decimal("300.40"),
				"other_costs": Decimal("99.50"),
			},
			*corporate.HOLDING_RESULTS[2:],
		)
		return compute(settings=settings, corporate_return=replace(corporate.RETURN, holding_results=results))

	def test_a_holding_of_15_percent_in_germany_falls_under_number_2a_and_adds_nothing_back(self):
		(holding,) = self.computed(rules.Holding("Beta GmbH", YEAR, Decimal("20"), Decimal("20"))).holdings
		self.assertEqual(
			{key: holding[key] for key in ("paragraph", "financing_costs", "other_costs", "addback")},
			{
				"paragraph": "§ 9 Nr. 2a GewStG",
				"financing_costs": Decimal("300"),
				"other_costs": Decimal("100"),
				"addback": ZERO,
			},
		)
		self.assertEqual((holding["exempt"], holding["cut"]), (Decimal("12000"), ZERO))
		beg = entries(bridge.beg_vordruck(holding))
		self.assertEqual(
			{key: beg[key] for key in (("E4050701", ()), ("E4050801", ()), ("E4050901", ()))},
			{("E4050701", ()): "1", ("E4050801", ()): Decimal("300"), ("E4050901", ()): Decimal("100")},
		)
		# Rules 40944, 40946 to 40949 and 40750 of the Jahresdokumentation GewSt 2025: line 12 with line 14, beside
		# line 7 line 16 as line 14, beside line 16 lines 17 and 18 for lines 8 and 9 and line 19, and line 20 beside
		# line 17, even at zero (validation with ERiC 44.3.6.0).
		self.assertEqual(
			{key[0]: value for key, value in beg.items() if key[0] >= "E4051201"},
			{
				"E4051201": Decimal("12000"),
				"E4051401": ZERO,
				"E4051601": ZERO,
				"E4051701": ZERO,
				"E4051801": ZERO,
				"E4051901": ZERO,
				"E4052001": ZERO,
			},
		)

	def test_a_holding_abroad_falls_under_number_7(self):
		holding = rules.Holding("Beta GmbH", YEAR, Decimal("20"), Decimal("20"), country="Austria")
		(row,) = self.computed(holding).holdings
		self.assertEqual(row["paragraph"], "§ 9 Nr. 7 GewStG")
		self.assertEqual(entries(bridge.beg_vordruck(row))[("E4050701", ())], "2")

	def test_anlage_beg_files_what_is_not_zero(self):
		row = {
			"holding_name": " Beta GmbH ",
			"dividends": 1200,
			"paragraph": "",
			"exempt": 0,
			"not_exempt": 0,
		}
		self.assertEqual(
			entries(bridge.beg_vordruck(row)),
			{("E4050201", ()): "Beta GmbH", ("E4050601", ()): Decimal("1200.00")},
		)
		row = {
			"holding_name": "Beta GmbH",
			"dividends": 1200,
			"paragraph": "§ 9 Nr. 2a GewStG",
			"financing_costs": 0,
			"other_costs": 0,
			"exempt": 0,
			"not_exempt": 1200,
			"cut_base": 1200,
			"cut": 1200,
		}
		self.assertEqual(
			entries(bridge.beg_vordruck(row)),
			{
				("E4050201", ()): "Beta GmbH",
				("E4050601", ()): Decimal("1200.00"),
				("E4050701", ()): "1",
				("E4051201", ()): ZERO,
				("E4051401", ()): Decimal("1200.00"),
				("E4051601", ()): Decimal("1200.00"),
				("E4051901", ()): Decimal("1200.00"),
			},
		)

	def test_the_columns_of_the_holdings_are_those_of_the_lines_of_anlage_beg(self):
		self.assertEqual(
			dict(bridge.BEG_COLUMNS),
			{
				"addback": "addback",
				"cut_base": "cut_base",
				"financing_costs": "cut_financing_costs",
				"other_costs": "cut_other_costs",
				"cut": "cut",
			},
		)
		self.assertEqual(dict(bridge.PARAGRAPHS), {1: "§ 9 Nr. 2a GewStG", 2: "§ 9 Nr. 7 GewStG"})


class EstablishmentTest(TestCase):
	"""Steuerbote files for one Betriebsstätte in one Gemeinde (adopted answer Q7 of the research of stage 3)."""

	def test_without_a_betriebsstaette_the_return_has_no_gemeinde_and_no_hebesatz(self):
		computation = compute(settings=replace(SETTINGS, establishments=()))
		self.assertEqual(computation.municipalities, [])
		self.assertEqual(computation.values["hebesatz"], ZERO)
		self.assertEqual(codes(computation), ["GEWST-HEBESATZ-FEHLT", ESTABLISHMENTS, PROVISIONAL])
		(finding,) = (item for item in computation.findings if item.code == ESTABLISHMENTS)
		self.assertEqual(
			finding.text,
			"The Annual Filing Settings name no Betriebsstätte in 2026: GewSt 1 A lines 26 to 33 need the Gemeinde of "
			"the one Betriebsstätte.",
		)
		self.assertEqual(finding.reference, "§§ 28 bis 31 GewStG; GewSt 1 A Zeilen 26 bis 33")

	def test_several_betriebsstaetten_hold_the_return_back(self):
		second = rules.Establishment(2, "Beispielstadt", "54321", "05999999", date(2026, 7, 1))
		computation = compute(settings=replace(SETTINGS, establishments=(ESTABLISHMENT, second)))
		(finding,) = (item for item in computation.findings if item.code == ESTABLISHMENTS)
		self.assertTrue(finding.text.startswith("The Annual Filing Settings name 2 Betriebsstätten in 2026."))
		self.assertEqual(computation.municipalities, [])

	def test_a_betriebsstaette_that_closed_before_the_year_counts_not(self):
		closed = rules.Establishment(
			2, "Beispielstadt", "54321", "05999999", date(2020, 1, 1), date(2025, 6, 30)
		)
		computation = compute(settings=replace(SETTINGS, establishments=(closed, ESTABLISHMENT)))
		self.assertEqual([row["ags"] for row in computation.municipalities], [AGS])

	def test_a_gemeinde_without_a_hebesatz_of_the_year_shows_none(self):
		computation = compute(
			settings=replace(
				SETTINGS, trade_tax_rates=(), establishments=(replace(ESTABLISHMENT, hebenummer=None),)
			)
		)
		(row,) = computation.municipalities
		self.assertEqual(
			{key: row[key] for key in ("hebenummer", "hebesatz", "hebesatz_source", "gewst")},
			{"hebenummer": "", "hebesatz": ZERO, "hebesatz_source": "", "gewst": ZERO},
		)
		self.assertIn("GEWST-HEBESATZ-FEHLT", codes(computation))


class ReadinessTest(TestCase):
	"""What holds the Gewerbesteuererklärung back beside the core: the forms of the year, its settings and every error
	of the Körperschaftsteuer it builds on."""

	def test_the_errors_of_the_koerperschaftsteuer_hold_the_gewerbesteuer_back_too(self):
		ret = replace(corporate.RETURN, donations=(), shareholder_contracts=True)
		computation = compute(corporate_return=ret)
		self.assertEqual(codes(computation), [PROVISIONAL, kst.NO_RECEIPTS])

	def test_taken_over_are_the_errors_but_the_forms_of_the_year(self):
		found = (
			kst.provisional_finding(kst.PROVISIONAL, YEAR, 2025, translate),
			kst.error(kst.UNMAPPED, "Konto", "Kontenzuordnung"),
			kst.Finding(kst.CONTRACTS, kst.Severity.HINT, "Verträge", "Anlage WA"),
		)
		corporate_computation = replace(
			kst.compute(corporate.RETURN, corporate.ledger(), MAPPING, SETTINGS, FIGURES, translate),
			findings=found,
		)
		self.assertEqual([item.code for item in bridge.taken_over(corporate_computation)], [kst.UNMAPPED])

	def test_without_settings_the_return_takes_over_what_the_koerperschaftsteuer_misses(self):
		computation = compute(settings=None, books=corporate.ledger(booked={}))
		self.assertIn(kst.NO_SETTINGS, codes(computation))
		self.assertNotIn(ESTABLISHMENTS, codes(computation))
		self.assertEqual(computation.municipalities, [])

	def test_gewst_1_a_needs_the_gegenstand_and_the_rechtsform(self):
		company = replace(corporate.COMPANY, business_purpose=None)
		computation = compute(settings=replace(SETTINGS, company=company))
		(finding,) = (item for item in computation.findings if item.code == DETAILS_MISSING)
		self.assertEqual(
			(finding.text, finding.reference),
			(
				"The Annual Filing Settings of Muster IT GmbH lack what GewSt 1 A needs: Business Purpose.",
				"GewSt 1 A Zeilen 4 und 14",
			),
		)

	def test_the_vorauszahlungen_of_the_notices_are_compared_with_those_booked(self):
		settings = replace(SETTINGS, prepayments=corporate.prepayments(gewst="3700.00"))
		computation = compute(settings=settings)
		(finding,) = (item for item in computation.findings if item.code == PREPAYMENTS)
		self.assertEqual(
			finding.text,
			"The Vorauszahlungen GewSt of the Annual Filing Settings come to 14.800,00 €, those booked on the account of "
			"the tax to 15.000,00 €.",
		)
		self.assertEqual(computation.values["balance"], Decimal("264.00"))
		self.assertNotIn(kst.PREPAYMENTS, codes(computation))

	def test_a_year_with_its_own_forms_holds_nothing_back(self):
		with (
			patch.object(bridge, "provisional", return_value=(False, YEAR)),
			patch.object(kst, "provisional", return_value=(False, YEAR)),
		):
			self.assertEqual(codes(compute()), [])
		self.assertEqual(bridge.provisional(YEAR), (True, 2025))


class CarryForwardsTest(TestCase):
	"""The Fehlbetrag of § 10a GewStG and the Zuwendungsvortrag of the last notices, GewSt 1 A lines 148 and 150."""

	def test_confirmed_carry_forwards_reduce_the_gewerbeertrag_and_are_filed(self):
		settings = replace(
			SETTINGS,
			carry_forwards=(
				stated(rules.CarryForwardKind.FEHLBETRAG, "7600"),
				stated(rules.CarryForwardKind.DONATIONS_GEWST, "200"),
			),
		)
		computation = compute(settings=settings)
		self.assertEqual(computation.values["gewerbeertrag"], Decimal("99800"))
		self.assertEqual(line(computation.lines, "E4014801")["form_amount"], Decimal("7600"))
		self.assertEqual(line(computation.lines, "E4015001")["form_amount"], Decimal("200"))
		self.assertEqual(codes(computation), [PROVISIONAL])

	def test_in_its_first_year_in_steuerbote_the_return_needs_the_fehlbetrag_of_the_last_notice(self):
		computation = compute(replace(RETURN, first_year=True))
		(missing,) = (item for item in computation.findings if item.code == bridge.CARRY_FORWARD_MISSING)
		self.assertTrue(missing.text.startswith("Fehlbetrag (§ 10a GewStG) has no amount as of 31.12.2025"))
		self.assertTrue(missing.blocking)
		settings = replace(SETTINGS, carry_forwards=(stated(rules.CarryForwardKind.FEHLBETRAG, "0"),))
		self.assertNotIn(
			bridge.CARRY_FORWARD_MISSING, codes(compute(replace(RETURN, first_year=True), settings=settings))
		)

	def test_a_carry_forward_not_confirmed_counts_not_and_holds_the_return_back(self):
		settings = replace(
			SETTINGS, carry_forwards=(stated(rules.CarryForwardKind.FEHLBETRAG, "7600.40", False),)
		)
		computation = compute(settings=settings)
		self.assertEqual(codes(computation), [UNCONFIRMED, PROVISIONAL])
		self.assertNotIn("E4014801", [row["feldkennung"] for row in computation.lines])
		self.assertEqual(computation.values["gewerbeertrag"], Decimal("107600"))

	def test_a_carry_forward_in_cents_counts_rounded_and_holds_the_return_back(self):
		settings = replace(SETTINGS, carry_forwards=(stated(rules.CarryForwardKind.FEHLBETRAG, "7600.40"),))
		computation = compute(settings=settings)
		self.assertEqual(codes(computation), [NOT_IN_EUROS, PROVISIONAL])
		self.assertEqual(line(computation.lines, "E4014801")["form_amount"], Decimal("7600"))

	def test_a_turnover_of_0_stated_goes_to_line_94_too(self):
		computation = compute(corporate_return=replace(corporate.RETURN, turnover_and_wages_given=True))
		self.assertEqual(line(computation.lines, "E4004001")["form_amount"], ZERO)
		self.assertNotIn("E4004001", [row["feldkennung"] for row in compute().lines])

	def test_the_turnover_of_anlage_z_goes_to_line_94(self):
		computation = compute(
			corporate_return=replace(
				corporate.RETURN, turnover_and_wages_given=True, turnover_and_wages=Decimal("800000")
			)
		)
		self.assertEqual(line(computation.lines, "E4004001")["form_amount"], Decimal("800000"))


class FiledVordruckeTest(TestCase):
	"""GewSt 1 A and the Anlagen BEG the return files, from its rows as stored."""

	def test_without_settings_gewst_1_a_says_only_one_gemeinde_that_did_not_move(self):
		self.assertEqual(
			entries(Vordruck("GewSt1A", tuple(bridge.general_entries(RETURN, None, ())))),
			{("E4001506", ()): False, ("E4001102", ()): False},
		)

	def test_the_qualified_free_text_goes_with_its_key(self):
		ret = replace(
			RETURN, supplement_key="1", supplement_text="  Abweichung von der Verwaltungsauffassung  "
		)
		found = entries(Vordruck("GewSt1A", tuple(bridge.general_entries(ret, None, ()))))
		self.assertEqual(
			(found[("E4003204", ())], found[("E4003205", ())]),
			("1", "Abweichung von der Verwaltungsauffassung"),
		)
		found = entries(
			Vordruck("GewSt1A", tuple(bridge.general_entries(replace(RETURN, supplement_text=" "), None, ())))
		)
		self.assertNotIn(("E4003205", ()), found)

	def test_the_gemeinde_files_what_it_has(self):
		rows = (
			{"municipality": "Musterstadt", "postal_code": "", "hebenummer": None},
			{"municipality": "Zweitstadt"},
		)
		found = entries(Vordruck("GewSt1A", tuple(bridge.general_entries(RETURN, None, rows))))
		self.assertEqual(found[("E4001111", ())], "Musterstadt")
		self.assertNotIn(("E4001110", ()), found)
		self.assertNotIn(("E4001803", ()), found)

	def test_a_line_that_takes_no_zero_is_left_out_at_zero_and_a_receipt_abroad_says_so(self):
		rows = [{"feldkennung": "E4003403", "reported": 0}, {"feldkennung": "e4001703", "reported": 0}]
		donations = ({"recipient": "Stiftung Muster, Wien", "amount": 400, "abroad": 1},)
		(general,) = bridge.filed_vordrucke(RETURN, rows, (), (), donations, None)
		found = entries(general)
		self.assertNotIn(("E4003403", ()), found)
		self.assertEqual(found[("E4001703", ())], ZERO)
		self.assertEqual(found[("E4009222", (0,))], "2")

	def test_the_table_of_lines_holds_no_field_of_a_repeated_context_and_no_yes_or_no(self):
		result = compute().result
		gewst_1a = Vordruck(
			"GewSt1A",
			(
				Entry("E4001703", Decimal("1000")),
				Entry("E4009221", Decimal("10.00"), (0,)),
				Entry("E4001506", False),
			),
		)
		self.assertEqual([row["feldkennung"] for row in bridge.line_rows(result, gewst_1a)], ["E4001703"])

	def test_the_return_starts_its_carry_forwards_at_the_end_of_the_previous_year(self):
		self.assertEqual(RETURN.opening_day, date(2025, 12, 31))

	def test_every_text_has_its_values_apart(self):
		self.assertEqual(len(bridge.MESSAGES), len(set(bridge.MESSAGES)))
		self.assertTrue(all(code.startswith("GEWST-") for code in bridge.CODES))
		self.assertFalse(set(bridge.CODES) & set(kst.CODES))
