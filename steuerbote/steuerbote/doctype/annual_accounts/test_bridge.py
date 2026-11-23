"""The bridge of the Annual Accounts, without a bench: the size of both Abschlussstichtage, the headcount, the
statement with its corrections and its lines, the Angaben, the signatories, the register data, the findings, what
holds the Feststellung back, the Ergebnisverwendung, the Übermittlung and the inputs of the XBRL.

The books are those of the invented companies of steuerbote/hgb/tests/companies.py."""

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.hgb import upload
from steuerbote.hgb.disclosure import Mode, Signature
from steuerbote.hgb.instance import Address
from steuerbote.hgb.notes import Answer, NoteAnswer, RegisterData, catalogue
from steuerbote.hgb.schemes import balance_sheet_scheme
from steuerbote.hgb.size import Basis, Criteria, SizeClass
from steuerbote.hgb.statement import Balance, Finding, ProfitPresentation, RemainingTerm, Severity, build
from steuerbote.hgb.tests import companies
from steuerbote.jahresmeldung.corrections import RevisionStatus
from steuerbote.jahresmeldung.findings import Severity as AnnualSeverity
from steuerbote.jahresmeldung.overrides import OverrideError
from steuerbote.steuerbote.doctype.annual_accounts import bridge
from steuerbote.steuerbote.doctype.annual_accounts.bridge import (
	Appropriation,
	BridgeError,
	Code,
	Employee,
	Problem,
)
from steuerbote.steuerbote.doctype.annual_filing_settings import rules as settings_rules
from steuerbote.xbrl import checks
from steuerbote.xbrl import mapping as xbrl_mapping
from steuerbote.xbrl.facts import Periods

PARENTS = companies.PARENTS
KLEINST, KLEIN = SizeClass.KLEINST, SizeClass.KLEIN
END = date(2026, 12, 31)
PRIOR_END = date(2025, 12, 31)
PREPAID = "bs.ass.prepaidExp"
EQUITY = "bs.eqLiab.equity"
NET_INCOME = "bs.eqLiab.equity.netIncome"
SALES = "is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales"
MATERIAL = "is.netIncome.regular.operatingTC.grossTradingProfit.materialServices"


def kleinst(**options):
	return bridge.statements(
		2026, KLEINST, companies.KLEINST_2026, parents=PARENTS, prior=companies.KLEINST_2025, **options
	)


def klein(**options):
	return bridge.statements(
		2026, KLEIN, companies.KLEIN_2026, parents=PARENTS, prior=companies.KLEIN_2025, **options
	)


def rows_by_concept(rows):
	return {row["concept"]: row for row in rows}


def filed(rows):
	"""The rows as Berechnen stores them, each reporting its amount."""
	return [{**row, "reported": row["amount"], "manual": 0} for row in rows]


class SizeTest(TestCase):
	def test_reads_the_classes_as_the_document_and_the_settings_name_them(self):
		self.assertIs(bridge.size_class_of("Kleinst"), KLEINST)
		self.assertIs(bridge.size_class_of("Groß"), SizeClass.GROSS)
		self.assertIsNone(bridge.size_class_of(""))
		self.assertEqual(
			[bridge.stored_class(size) for size in SizeClass], ["Kleinst", "Klein", "Mittelgroß", "Groß"]
		)
		self.assertEqual(bridge.stored_class(None), "")

	def test_a_negative_criterion_counts_as_zero(self):
		found = bridge.criteria(END, Decimal("-1"), Decimal("-500.00"), Decimal("2"))
		self.assertEqual(
			(found.bilanzsumme, found.umsatzerloese, found.arbeitnehmer), (Decimal(0), Decimal(0), Decimal(2))
		)

	def test_the_previous_criteria_are_those_of_the_settings_where_they_hold_all_three(self):
		books = Criteria(PRIOR_END, Decimal("1"), Decimal("2"), Decimal("3"))
		record = settings_rules.SizeRecord(
			PRIOR_END, "Kleinst", "Jahresabschluss 2025", Decimal("400000"), Decimal("800000"), Decimal("9")
		)
		self.assertEqual(
			bridge.previous_criteria(record, books),
			Criteria(PRIOR_END, Decimal("400000"), Decimal("800000"), Decimal("9")),
		)
		self.assertIs(bridge.previous_criteria(replace(record, employees=None), books), books)
		self.assertIs(bridge.previous_criteria(None, books), books)
		self.assertIsNone(bridge.previous_criteria(None, None))

	def test_decides_on_two_closing_dates_and_the_first_after_a_founding(self):
		small = Criteria(END, Decimal("300000"), Decimal("600000"), Decimal("5"))
		before = Criteria(PRIOR_END, Decimal("300000"), Decimal("600000"), Decimal("5"))
		decision = bridge.decide(small, before, None, founded_in_year=False, excluded_from_kleinst=False)
		self.assertEqual((decision.applied, decision.basis), (KLEINST, Basis.CONFIRMED))
		founded = bridge.decide(small, None, None, founded_in_year=True, excluded_from_kleinst=False)
		self.assertEqual((founded.applied, founded.basis), (KLEINST, Basis.FOUNDING))
		holding = bridge.decide(small, before, None, founded_in_year=False, excluded_from_kleinst=True)
		self.assertEqual((holding.applied, holding.kleinst_excluded), (KLEIN, True))
		unknown = bridge.decide(small, None, None, founded_in_year=False, excluded_from_kleinst=False)
		self.assertIsNone(unknown.applied)

	def test_the_class_by_hand_needs_its_reason_and_is_a_hint_where_it_differs(self):
		small = Criteria(END, Decimal("300000"), Decimal("600000"), Decimal("5"))
		decision = bridge.decide(small, None, None, founded_in_year=True, excluded_from_kleinst=False)
		with self.assertRaises(BridgeError) as raised:
			bridge.applied_class(decision, KLEIN, " ")
		self.assertEqual(raised.exception.template, bridge.OVERRIDE_WITHOUT_REASON)
		self.assertEqual(bridge.applied_class(decision, KLEINST, "gleich"), (KLEINST, ()))
		applied, (hint,) = bridge.applied_class(decision, KLEIN, "Umwandlung, siehe Steuerberatung")
		self.assertEqual(
			(applied, hint.code, hint.severity), (KLEIN, Code.CLASS_BY_HAND, AnnualSeverity.HINT)
		)
		self.assertIn("Kleinstkapitalgesellschaft", hint.text)
		self.assertIn("Umwandlung", hint.text)
		self.assertEqual(bridge.applied_class(decision, None, ""), (KLEINST, ()))

	def test_without_a_decision_and_without_a_class_by_hand_no_class_applies(self):
		small = Criteria(END, Decimal("300000"), Decimal("600000"), Decimal("5"))
		undecided = bridge.decide(small, None, None, founded_in_year=False, excluded_from_kleinst=False)
		applied, (error,) = bridge.applied_class(undecided, None, "")
		self.assertIsNone(applied)
		self.assertEqual((error.code, error.severity), (Code.NO_CLASS, AnnualSeverity.ERROR))
		_, (hint,) = bridge.applied_class(undecided, KLEIN, "Vorjahr klein")
		self.assertIn("keine", hint.text)

	def test_the_hints_of_the_size(self):
		small = Criteria(END, Decimal("300000"), Decimal("600000"), Decimal("5"))
		before = Criteria(PRIOR_END, Decimal("300000"), Decimal("600000"), Decimal("5"))
		decision = bridge.decide(small, before, None, founded_in_year=True, excluded_from_kleinst=True)
		record = settings_rules.SizeRecord(END, "Klein", "Jahresabschluss")
		self.assertEqual(
			[finding.code for finding in bridge.size_findings(decision, KLEIN, record)], [Code.NOT_PREPARED]
		)
		large = bridge.decide(small, None, None, founded_in_year=True, excluded_from_kleinst=False)
		self.assertEqual(
			[finding.code for finding in bridge.size_findings(large, SizeClass.MITTELGROSS, None)],
			[Code.NOT_PREPARED, Code.SIZE_HISTORY],
		)
		self.assertEqual(
			bridge.size_findings(
				large, KLEINST, settings_rules.SizeRecord(END, "Kleinst", "Jahresabschluss")
			),
			(),
		)
		self.assertEqual(
			[finding.code for finding in bridge.size_findings(large, KLEINST, record)], [Code.SIZE_HISTORY]
		)


class HeadcountTest(TestCase):
	def setUp(self):
		self.employees = (
			Employee(date(2020, 1, 1)),
			Employee(date(2026, 4, 1), date(2026, 9, 30)),
			Employee(date(2026, 7, 1), employment_type="Apprentice"),
			Employee(date(2026, 12, 31), employment_type="Full-time"),
		)

	def test_counts_each_quarter_end_without_the_types_not_counted(self):
		counts = bridge.headcounts(self.employees, END, {"Apprentice"})
		self.assertEqual(
			counts,
			{date(2026, 3, 31): 1, date(2026, 6, 30): 2, date(2026, 9, 30): 2, date(2026, 12, 31): 2},
		)
		self.assertEqual(bridge.average_employees(counts, END), Decimal("1.75"))
		self.assertEqual(
			bridge.headcount_text(counts), "31.03.2026: 1; 30.06.2026: 2; 30.09.2026: 2; 31.12.2026: 2"
		)
		self.assertEqual(bridge.headcounts(self.employees, END, ())[date(2026, 12, 31)], 3)

	def test_the_arbeitnehmer_by_hand_need_their_reason_and_are_a_hint(self):
		self.assertEqual(bridge.employees_applied(Decimal("1.75"), None, ""), (Decimal("1.75"), ()))
		with self.assertRaises(BridgeError):
			bridge.employees_applied(Decimal("1.75"), Decimal("1"), "")
		employees, (hint,) = bridge.employees_applied(
			Decimal("1.75"), Decimal("1"), "Geschäftsführer mitgezählt"
		)
		self.assertEqual((employees, hint.code), (Decimal("1"), Code.EMPLOYEES_BY_HAND))
		self.assertIn("1,75", hint.text)

	def test_a_hint_where_the_settings_leave_types_out_but_the_employees_carry_none(self):
		self.assertEqual(bridge.employment_type_finding({"Apprentice"}, typed=True), ())
		self.assertEqual(bridge.employment_type_finding((), typed=False), ())
		(hint,) = bridge.employment_type_finding({"Apprentice"}, typed=False)
		self.assertEqual(hint.code, Code.EMPLOYMENT_TYPE)


class StatementsTest(TestCase):
	def test_without_corrections_the_document_files_the_books(self):
		found = kleinst()
		self.assertIs(found.filed, found.books)
		self.assertEqual(found.balances, companies.KLEINST_2026)
		self.assertEqual(found.refused, ())

	def test_a_correction_is_the_balance_of_its_difference_and_moves_the_totals(self):
		found = kleinst(corrections={PREPAID: Decimal("500.00")})
		self.assertEqual(found.books.balance_sheet.aktiva_total, Decimal("78671.50"))
		self.assertEqual(found.filed.balance_sheet.aktiva_total, Decimal("78691.50"))
		(delta,) = found.balances[len(companies.KLEINST_2026) :]
		self.assertEqual(
			(delta.concept, delta.amount, delta.source), (PREPAID, Decimal("20.00"), "Korrektur")
		)
		self.assertIn("JA-BILANZ-UNGLEICH", [finding.code for finding in found.filed.findings])

	def test_a_correction_to_the_amount_of_the_books_changes_nothing(self):
		found = kleinst(corrections={PREPAID: Decimal("480.00")})
		self.assertIs(found.filed, found.books)

	def test_a_correction_on_a_line_that_takes_none_is_refused(self):
		found = kleinst(corrections={EQUITY + ".subscribed": Decimal("1")})
		self.assertEqual(found.refused, ("bs.eqLiab.equity.subscribed",))
		self.assertIs(found.filed, found.books)
		(error,) = bridge.refused_findings(found.refused)
		self.assertEqual(
			(error.code, error.severity, error.reference),
			(Code.CORRECTION, AnnualSeverity.ERROR, found.refused[0]),
		)

	def test_takes_corrections_only_on_lines_that_take_balances(self):
		kleinst_lines = bridge.correctable(kleinst().books)
		self.assertIn(EQUITY, kleinst_lines)
		self.assertNotIn("bs.ass.deficitNotCoveredByCapital", kleinst_lines)
		self.assertIn(SALES, kleinst_lines)
		self.assertNotIn(MATERIAL, kleinst_lines)
		self.assertNotIn("is.netIncome", kleinst_lines)
		klein_lines = bridge.correctable(klein().books)
		self.assertNotIn(EQUITY, klein_lines)
		self.assertIn(EQUITY + ".subscribed", klein_lines)
		self.assertNotIn(NET_INCOME, klein_lines)


class LineRowsTest(TestCase):
	def setUp(self):
		self.rows = bridge.line_rows(kleinst(corrections={PREPAID: Decimal("500.00")}), PARENTS)
		self.by_concept = rows_by_concept(self.rows)

	def test_writes_each_side_with_its_vermerke_and_its_total_then_the_guv(self):
		statements = [row["statement"] for row in self.rows]
		self.assertEqual(statements[0], "Aktiva")
		self.assertEqual(self.rows[statements.index("Passiva") - 1]["concept"], "bs.ass")
		self.assertEqual(statements[-1], "GuV")
		self.assertEqual(self.rows[-1]["concept"], "is.netIncome")
		total = self.by_concept["bs.ass"]
		self.assertEqual(
			(total["level"], total["label"], total["amount"], total["prior"]),
			("Summe", "Summe Aktiva", Decimal("78691.50"), Decimal("60450.75")),
		)
		vermerk = self.by_concept["bs.eqLiab.liab.ofWhichToShareholders"]
		self.assertEqual(
			(vermerk["level"], vermerk["parent_concept"], vermerk["amount"], vermerk["shown"]),
			("Vermerk", "bs.eqLiab.liab", Decimal("3000.00"), 1),
		)

	def test_a_line_that_takes_a_correction_holds_the_books_and_every_other_the_amount_filed(self):
		prepaid = self.by_concept[PREPAID]
		self.assertEqual((prepaid["amount"], prepaid["takes_correction"]), (Decimal("480.00"), 1))
		self.assertEqual(self.by_concept["bs.ass"]["takes_correction"], 0)
		self.assertEqual(self.by_concept["bs.ass.currAss"]["parent_concept"], "")

	def test_names_the_sources_of_the_balances_under_each_line(self):
		sources = self.by_concept["bs.eqLiab.liab"]["sources"]
		self.assertIn("0650 Darlehen", sources)
		self.assertIn("1776 Umsatzsteuer 19 %", sources)
		self.assertIn("Korrektur", self.by_concept[PREPAID]["sources"])
		self.assertEqual(self.by_concept["bs.ass.defTax"]["sources"], "")

	def test_a_line_without_an_amount_in_either_year_is_not_shown(self):
		self.assertEqual(self.by_concept["bs.ass.defTax"]["shown"], 0)
		self.assertEqual(self.by_concept[EQUITY]["shown"], 1)

	def test_the_guv_names_the_item_its_part_belongs_to(self):
		part = self.by_concept[f"{MATERIAL}.material"]
		self.assertEqual((part["level"], part["parent_concept"]), ("Kleinbuchstabe", MATERIAL))
		self.assertEqual(self.by_concept[SALES]["parent_concept"], "")

	def test_a_first_year_without_a_previous_one_holds_zero(self):
		rows = bridge.line_rows(
			bridge.statements(2026, KLEINST, companies.KLEINST_2026, parents=PARENTS), PARENTS
		)
		self.assertEqual({row["prior"] for row in rows}, {Decimal(0)})

	def test_a_balance_without_a_source_or_a_position_names_nothing(self):
		balances = (
			*companies.KLEINST_2026,
			Balance("bs.ass.unknown", Decimal("0")),
			Balance("is.netIncome.unknown", Decimal("0"), source="9999 Unbekannt"),
		)
		cyclic = {
			**PARENTS,
			"is.netIncome.unknown": "is.netIncome.loop",
			"is.netIncome.loop": "is.netIncome.unknown",
		}
		found = bridge.statements(2026, KLEINST, balances, parents=cyclic)
		rows = bridge.line_rows(found, cyclic)
		self.assertNotIn("9999 Unbekannt", " ".join(row["sources"] for row in rows))

	def test_reads_what_a_line_reports(self):
		rows = filed(self.rows)
		rows.append({"concept": "bs.ass", "manual": 1, "reported": Decimal("1")})
		self.assertEqual(bridge.reported(rows, "bs.ass"), Decimal("78691.50"))
		self.assertIsNone(bridge.reported(rows, "bs.unknown"))


class CorrectionsTest(TestCase):
	def test_reads_the_corrections_with_their_reasons(self):
		rows = [
			{"concept": PREPAID, "correction": 500, "correction_reason": "Abgrenzung der Miete Januar"},
			{"concept": EQUITY, "correction": 0, "correction_reason": ""},
		]
		self.assertEqual(bridge.corrections_of(rows), {PREPAID: Decimal("500.00")})
		with self.assertRaises(OverrideError):
			bridge.corrections_of([{"concept": PREPAID, "correction": 5, "correction_reason": ""}])

	def test_refuses_a_line_by_hand_and_a_correction_of_a_line_that_takes_none(self):
		rows = [
			{"concept": PREPAID, "correction": 500, "correction_reason": "Miete", "takes_correction": 1},
			{"concept": "bs.ass", "correction": 1, "correction_reason": "Summe", "takes_correction": 0},
			{"concept": "x", "manual": 1, "correction": 1, "correction_reason": "von Hand"},
			{"concept": EQUITY, "takes_correction": 1},
		]
		self.assertEqual(
			bridge.correction_problems(rows),
			(Problem(bridge.CORRECTION_REFUSED, ("bs.ass",)), Problem(bridge.NO_LINE_BY_HAND)),
		)


class ValuesTest(TestCase):
	def test_reads_the_criteria_the_result_and_the_gewinnvortrag_of_the_form_of_klein(self):
		values = bridge.statement_values(
			bridge.statements(2026, KLEIN, companies.KLEINST_2026, parents=PARENTS).filed
		)
		self.assertEqual(
			values,
			{
				"bilanzsumme": Decimal("78671.50"),
				"umsatzerloese": Decimal("180000.00"),
				"net_income": Decimal("19000.00"),
				"carried_forward": Decimal("12100.00"),
				"equity": Decimal("56100.00"),
			},
		)

	def test_reads_the_gewinnvortrag_after_part_of_the_appropriation_from_its_vermerk(self):
		after = bridge.statements(
			2026,
			KLEIN,
			companies.KLEIN_2026,
			parents=PARENTS,
			presentation=ProfitPresentation.AFTER_PARTIAL_APPROPRIATION,
		)
		self.assertEqual(bridge.statement_values(after.filed)["carried_forward"], Decimal("245000.00"))

	def test_the_form_of_a_kleinst_does_not_show_the_gewinnvortrag(self):
		with self.assertRaises(ValueError):
			bridge.statement_values(kleinst().filed)

	def test_reads_the_criteria_of_the_previous_year(self):
		self.assertEqual(
			bridge.prior_values(klein().filed),
			{"bilanzsumme": Decimal("1349000.00"), "umsatzerloese": Decimal("3900000.00")},
		)
		first = bridge.statements(2026, KLEIN, companies.KLEIN_2026, parents=PARENTS)
		self.assertIsNone(bridge.prior_values(first.filed))


class PriorByHandTest(TestCase):
	def test_enters_each_figure_at_its_position_with_its_flags(self):
		rows = [
			{"concept": "bs.ass.currAss.cashEquiv", "amount": 10000},
			{"concept": "bs.eqLiab.equity.subscribed", "amount": 25000},
			{
				"concept": "bs.eqLiab.liab.trade",
				"amount": 3000,
				"shareholder": 1,
				"remaining_term": "bis zu einem Jahr",
			},
		]
		balances = bridge.prior_balances(rows, 2026)
		self.assertEqual(
			[
				(balance.concept, balance.amount, balance.shareholder, balance.remaining_term)
				for balance in balances
			],
			[
				("bs.ass.currAss.cashEquiv", Decimal("10000.00"), False, None),
				("bs.eqLiab.equity.subscribed", Decimal("-25000.00"), False, None),
				("bs.eqLiab.liab.trade", Decimal("-3000.00"), True, RemainingTerm.UP_TO_ONE_YEAR),
			],
		)
		self.assertEqual(
			bridge.prior_labels(rows, 2026),
			[
				"IV. Kassenbestand, Bundesbankguthaben, Guthaben bei Kreditinstituten und Schecks",
				"I. Gezeichnetes Kapital",
				"4. Verbindlichkeiten aus Lieferungen und Leistungen",
			],
		)

	def test_refuses_a_position_the_schemes_do_not_hold_or_compute(self):
		for concept in ("bs.ass.unknown", "bs.eqLiab.equity.netIncome", ""):
			for read in (bridge.prior_balances, bridge.prior_labels):
				with (
					self.subTest(concept=concept, read=read.__name__),
					self.assertRaises(BridgeError) as raised,
				):
					read([{"concept": concept, "amount": 1}], 2026)
				self.assertEqual(raised.exception.template, bridge.PRIOR_POSITION)


class NotesTest(TestCase):
	def test_the_catalogue_of_a_class(self):
		self.assertEqual(bridge.catalogue_of(None, equity_zero=False), ())
		self.assertEqual(bridge.catalogue_of(SizeClass.MITTELGROSS, equity_zero=False), ())
		self.assertEqual(
			[entry.item.code for entry in bridge.catalogue_of(KLEINST, equity_zero=True)][-1],
			"EIGENKAPITAL-NULL",
		)

	def test_writes_the_catalogue_with_the_answers_kept_by_code(self):
		stored = [
			{
				"code": "ORGANKREDITE",
				"answer": "ja",
				"text": "Darlehen an die Geschäftsführerin",
				"amount": 8000,
			}
		]
		rows = bridge.note_rows(catalogue(KLEINST), stored)
		self.assertEqual(
			[row["code"] for row in rows], ["HAFTUNGSVERHAELTNISSE", "ORGANKREDITE", "ZUSAETZLICHE-ANGABEN"]
		)
		self.assertEqual(
			{key: rows[1][key] for key in ("answer", "text", "amount", "requirement", "published")},
			{
				"answer": "ja",
				"text": "Darlehen an die Geschäftsführerin",
				"amount": Decimal("8000.00"),
				"requirement": "wenn zutreffend",
				"published": 1,
			},
		)
		self.assertEqual((rows[0]["answer"], rows[0]["amount"]), ("", Decimal("0.00")))
		klein = {row["code"]: row for row in bridge.note_rows(catalogue(SizeClass.KLEIN), [])}
		self.assertEqual((klein["ARBEITNEHMER"]["answer"], klein["FIRMENWERT"]["answer"]), ("ja", ""))
		answered = bridge.note_rows(catalogue(SizeClass.KLEIN), [{"code": "ARBEITNEHMER", "answer": "nein"}])
		self.assertEqual({row["code"]: row["answer"] for row in answered}["ARBEITNEHMER"], "nein")

	def test_a_save_takes_the_answers_of_the_rows_berechnen_stored(self):
		stored = [
			{
				"name": "a",
				"code": "HAFTUNGSVERHAELTNISSE",
				"label": "Haftung",
				"answer": "",
				"text": "",
				"amount": 0,
			},
			{
				"name": "b",
				"code": "ORGANKREDITE",
				"label": "Kredite",
				"answer": "nein",
				"text": "",
				"amount": 0,
			},
		]
		sent = [
			{
				"name": "a",
				"code": "ANDERS",
				"label": "geändert",
				"answer": "ja",
				"text": "Bürgschaft",
				"amount": 15000,
			},
			{"name": "", "code": "NEU", "answer": "ja"},
		]
		kept = bridge.notes_kept(stored, sent)
		self.assertEqual(
			[(row["code"], row["label"], row["answer"], row["text"], row["amount"]) for row in kept],
			[
				("HAFTUNGSVERHAELTNISSE", "Haftung", "ja", "Bürgschaft", Decimal("15000.00")),
				("ORGANKREDITE", "Kredite", "nein", "", Decimal("0.00")),
			],
		)

	def test_the_answers_take_the_average_of_the_arbeitnehmer_and_no_amount_for_zero(self):
		rows = [
			{"code": "ARBEITNEHMER", "answer": "ja", "amount": 0},
			{"code": "BEWERTUNGSMETHODEN", "answer": "ja", "text": "Anschaffungskosten", "amount": 0},
			{"code": "VERBINDLICHKEITEN", "answer": "ja", "text": "Grundschuld", "amount": 120000},
			{"code": "FIRMENWERT", "answer": ""},
		]
		self.assertEqual(
			bridge.answers_of(rows, Decimal("23.75")),
			(
				NoteAnswer("ARBEITNEHMER", Answer.YES, "", Decimal("23.75")),
				NoteAnswer("BEWERTUNGSMETHODEN", Answer.YES, "Anschaffungskosten", None),
				NoteAnswer("VERBINDLICHKEITEN", Answer.YES, "Grundschuld", Decimal("120000.00")),
			),
		)


class SignatoriesTest(TestCase):
	def setUp(self):
		self.directors = (
			settings_rules.Director(1, "Erika Beispiel", date(2020, 1, 1), role="Geschäftsführerin"),
			settings_rules.Director(2, "Max Muster", date(2020, 1, 1), date(2026, 6, 30)),
			settings_rules.Director(3, "Paula Prokura", date(2020, 1, 1), signs=False),
		)

	def test_the_signatures_of_the_rows(self):
		rows = [
			{
				"signatory_name": " Erika Beispiel ",
				"function": "Geschäftsführerin",
				"place": "Musterstadt",
				"signed_on": date(2027, 5, 12),
			},
			{"signatory_name": "Max Muster"},
			{"signatory_name": "Paula Prokura", "signed_on": "2027-05-13"},
		]
		self.assertEqual(
			bridge.signatures_of(rows),
			(
				Signature("Erika Beispiel", "Geschäftsführerin", "Musterstadt", date(2027, 5, 12)),
				Signature("Max Muster", "", "", None),
				Signature("Paula Prokura", "", "", date(2027, 5, 13)),
			),
		)

	def test_every_geschaeftsfuehrer_who_signs_signs_and_a_new_document_starts_with_those_in_office(self):
		self.assertEqual(
			[director.name for director in bridge.signing_directors(self.directors)],
			["Erika Beispiel", "Max Muster"],
		)
		self.assertEqual(
			bridge.signatory_rows(self.directors, date(2027, 5, 1), "Musterstadt"),
			[
				{
					"signatory_name": "Erika Beispiel",
					"function": "Geschäftsführerin",
					"place": "Musterstadt",
					"signed_on": None,
				}
			],
		)
		self.assertEqual(len(bridge.signatory_rows(self.directors, date(2026, 6, 30), "")), 2)


class RegisterTest(TestCase):
	def test_names_the_registernummer_with_its_registerart(self):
		settings = {
			"registered_seat": "Musterstadt",
			"register_court": "Amtsgericht Musterstadt",
			"register_type": "HRB",
			"register_number": "12345",
		}
		values = bridge.register_values(" Beispiel Werkstatt GmbH ", settings)
		self.assertEqual(
			values,
			{
				"firma": "Beispiel Werkstatt GmbH",
				"sitz": "Musterstadt",
				"register_court": "Amtsgericht Musterstadt",
				"register_number": "HRB 12345",
			},
		)
		self.assertEqual(
			bridge.register_values("X", {**settings, "register_number": "HRB 12345"})["register_number"],
			"HRB 12345",
		)
		self.assertEqual(bridge.register_values("X", {})["register_number"], "")
		self.assertEqual(
			bridge.register_of(values, in_liquidation=True),
			RegisterData(
				"Beispiel Werkstatt GmbH", "Musterstadt", "Amtsgericht Musterstadt", "HRB 12345", True
			),
		)


class FindingsTest(TestCase):
	def test_the_findings_of_the_core_with_their_source_and_what_they_are_about(self):
		statement = Finding(
			"JA-BILANZ-UNGLEICH", Severity.ERROR, "Aktiva und Passiva weichen ab.", "§ 242 HGB"
		)
		placed = xbrl_mapping.Finding(
			xbrl_mapping.Code.UNPLACED,
			xbrl_mapping.Severity.ERROR,
			"Konto 1590 hat einen Saldo.",
			"§ 246 Abs. 1 Satz 1 HGB",
			"1590",
		)
		checked = checks.Finding(
			checks.Code.CALCULATION, "Die Summe geht nicht auf (Leitfaden).", "Leitfaden", "bs.ass"
		)
		quoted = Finding("JA-X", Severity.HINT, "Schon mit Quelle (§ 1 HGB).", "§ 1 HGB", "x" * 200)
		found = bridge.annual_findings((statement, placed, checked, quoted))
		self.assertEqual(
			[(finding.code, finding.severity, finding.text, finding.reference) for finding in found],
			[
				(
					"JA-BILANZ-UNGLEICH",
					AnnualSeverity.ERROR,
					"Aktiva und Passiva weichen ab. (§ 242 HGB)",
					"",
				),
				(
					"BILANZ-OHNE-PLATZ",
					AnnualSeverity.ERROR,
					"Konto 1590 hat einen Saldo. (§ 246 Abs. 1 Satz 1 HGB)",
					"1590",
				),
				("XBRL-RECHNUNG", AnnualSeverity.ERROR, "Die Summe geht nicht auf (Leitfaden).", "bs.ass"),
				("JA-X", AnnualSeverity.HINT, "Schon mit Quelle (§ 1 HGB).", "x" * 140),
			],
		)
		(prior,) = bridge.annual_findings((placed,), prior_year=True)
		self.assertTrue(prior.text.startswith("Vorjahr: Konto 1590"))

	def test_the_vorjahr_is_missing_only_where_the_company_existed_before(self):
		self.assertEqual(bridge.prior_finding(True, False), ())
		self.assertEqual(bridge.prior_finding(False, True), ())
		(error,) = bridge.prior_finding(False, False)
		self.assertEqual((error.code, error.severity), (Code.NO_PRIOR_YEAR, AnnualSeverity.ERROR))

	def test_the_codes_of_the_file(self):
		self.assertEqual(
			[bridge.xbrl_code(code) for code in ("XBRL-RECHNUNG", "JA-XBRL-ZEICHEN", "JA-BILANZ-UNGLEICH")],
			[True, True, False],
		)


class StatementDataTest(TestCase):
	def test_builds_the_statement_again_from_what_the_document_keeps(self):
		found = kleinst(corrections={PREPAID: Decimal("500.00")})
		text = bridge.statement_data(found, companies.KLEINST_2025, PARENTS)
		self.assertEqual(bridge.statement_from_data(text, 2026, KLEINST), found.filed)
		data = json.loads(text)
		self.assertEqual(data["parents"]["bs.ass.currAss.cashEquiv.bank"], "bs.ass.currAss.cashEquiv")
		self.assertNotIn("bs.ass.currAss.cashEquiv", data["parents"])
		self.assertEqual(
			(data["prior_net_income"], data["presentation"]), (None, "vor Verwendung des Jahresergebnisses")
		)

	def test_keeps_a_vorjahr_by_hand_with_its_result_and_the_appropriation(self):
		prior = (
			Balance("bs.ass.currAss.cashEquiv", Decimal("1000")),
			Balance("bs.eqLiab.equity.subscribed", Decimal("-1000")),
		)
		after = ProfitPresentation.AFTER_PARTIAL_APPROPRIATION
		found = bridge.statements(
			2026,
			KLEIN,
			companies.KLEIN_2026,
			parents=PARENTS,
			prior=prior,
			prior_net_income=Decimal("0"),
			presentation=after,
		)
		text = bridge.statement_data(found, prior, PARENTS, prior_net_income=Decimal("0"), presentation=after)
		self.assertEqual(bridge.statement_from_data(text, 2026, KLEIN), found.filed)
		first = bridge.statements(2026, KLEIN, companies.KLEIN_2026, parents=PARENTS)
		self.assertEqual(
			bridge.statement_from_data(bridge.statement_data(first, None, PARENTS), 2026, KLEIN), first.filed
		)


class FilingProblemsTest(TestCase):
	def setUp(self):
		self.rows = filed(bridge.line_rows(kleinst(), PARENTS))
		self.notes = [{"code": entry.item.code, "answer": "nein"} for entry in catalogue(KLEINST)]
		self.register = companies.KLEINST_REGISTER

	def problems(self, **options):
		values = {
			"size_class": KLEINST,
			"adopted_on": date(2027, 5, 12),
			"to_date": END,
			"today": date(2027, 6, 1),
			"codes": (),
			"recalculate": "SB-NEU-BERECHNEN",
		}
		values.update(options)
		rows, notes, register = (
			values.pop(name, default)
			for name, default in (("rows", self.rows), ("notes", self.notes), ("register", self.register))
		)
		return bridge.filing_problems("JA-2026-00001", rows, notes, register, **values)

	def test_a_complete_jahresabschluss_is_festgestellt(self):
		self.assertEqual(self.problems(), ())

	def test_a_calculation_older_than_its_entries_and_no_class(self):
		self.assertEqual(
			[problem.template for problem in self.problems(codes={"SB-NEU-BERECHNEN"}, size_class=None)],
			[bridge.STALE, bridge.NO_CLASS],
		)

	def test_aktiva_and_passiva_apart(self):
		rows = [{**row, "reported": Decimal("1")} if row["concept"] == "bs.ass" else row for row in self.rows]
		(problem,) = self.problems(rows=rows)
		self.assertEqual(problem, Problem(bridge.NOT_BALANCED, ("1,00 €", "78.671,50 €")))

	def test_a_jahresergebnis_of_the_bilanz_other_than_that_of_the_guv(self):
		rows = filed(bridge.line_rows(klein(), PARENTS))
		notes = [{"code": entry.item.code, "answer": "ja", "text": "x"} for entry in catalogue(KLEIN)]
		self.assertEqual(self.problems(rows=rows, notes=notes, size_class=KLEIN), ())
		changed = [{**row, "reported": Decimal("1")} if row["concept"] == NET_INCOME else row for row in rows]
		(problem, *_) = self.problems(rows=changed, notes=notes, size_class=KLEIN)
		self.assertEqual(problem, Problem(bridge.NET_INCOME_DIFFERS, ("1,00 €", "107.000,00 €")))

	def test_missing_data_of_264_abs_1a(self):
		(problem,) = self.problems(register=replace(self.register, sitz="", registernummer=""))
		self.assertEqual(problem.template, bridge.REGISTER_MISSING)
		self.assertIn("Sitz, Registernummer", problem.values[0])

	def test_an_angabe_not_answered(self):
		(problem,) = self.problems(notes=self.notes[1:])
		self.assertEqual(problem.template, bridge.NOTES_OPEN)
		self.assertIn("nicht beantwortet", problem.values[0])
		self.assertEqual(self.problems(size_class=SizeClass.MITTELGROSS, notes=[]), ())

	def test_an_eigenkapital_of_zero_without_its_explanation(self):
		rows = [{**row, "reported": Decimal("0")} if row["concept"] == EQUITY else row for row in self.rows]
		problems = self.problems(rows=rows)
		self.assertIn(Problem(bridge.ZERO_EQUITY), problems)
		notes = [
			*self.notes,
			{"code": "EIGENKAPITAL-NULL", "answer": "ja", "text": "Verluste der Anlaufjahre"},
		]
		self.assertNotIn(Problem(bridge.ZERO_EQUITY), self.problems(rows=rows, notes=notes))

	def test_the_day_of_the_feststellung(self):
		self.assertEqual(self.problems(adopted_on=None), (Problem(bridge.NOT_ADOPTED),))
		self.assertEqual(
			self.problems(adopted_on=END),
			(Problem(bridge.ADOPTED_EARLY, ("31. Dezember 2026", "31. Dezember 2026")),),
		)
		self.assertEqual(
			self.problems(adopted_on=date(2027, 6, 2)), (Problem(bridge.ADOPTED_LATER, ("2. Juni 2027",)),)
		)


class AppropriationTest(TestCase):
	def test_the_bilanzgewinn_the_minimum_of_an_ug_and_the_vortrag(self):
		gmbh = Appropriation(
			Decimal("19000.00"), Decimal("12100.00"), Decimal("5000.00"), Decimal("10000.00")
		)
		self.assertEqual(
			(gmbh.bilanzgewinn, gmbh.minimum_reserve, gmbh.carried),
			(Decimal("31100.00"), Decimal(0), Decimal("16100.00")),
		)
		ug = Appropriation(Decimal("10000.00"), Decimal("-2000.00"), ug=True)
		self.assertEqual(ug.minimum_reserve, Decimal("2000.00"))

	def test_a_save_refuses_a_negative_amount_and_more_than_the_bilanzgewinn(self):
		self.assertEqual(
			bridge.appropriation_problems(Appropriation(Decimal("100"), Decimal(0), Decimal("-1"))),
			(Problem(bridge.NEGATIVE_APPROPRIATION, ("-1,00 €",)),),
		)
		self.assertEqual(
			bridge.appropriation_problems(
				Appropriation(Decimal("100"), Decimal("-150"), dividend=Decimal("10"))
			),
			(Problem(bridge.APPROPRIATION_TOO_HIGH, ("10,00 €", "-50,00 €")),),
		)
		self.assertEqual(bridge.appropriation_problems(Appropriation(Decimal("-100"), Decimal(0))), ())
		self.assertEqual(
			bridge.appropriation_problems(Appropriation(Decimal("100"), Decimal(0), Decimal("100"))), ()
		)

	def test_before_berechnen_only_a_negative_amount_is_refused(self):
		"""The Bilanzgewinn is not known before Berechnen, so a distribution waits for it."""
		before = Appropriation(Decimal(0), Decimal(0), dividend=Decimal("5000"))
		self.assertEqual(bridge.appropriation_problems(before, calculated=False), ())
		self.assertEqual(
			bridge.appropriation_problems(
				Appropriation(Decimal(0), Decimal(0), dividend=Decimal("-1")), calculated=False
			),
			(Problem(bridge.NEGATIVE_APPROPRIATION, ("-1,00 €",)),),
		)
		self.assertEqual(
			bridge.appropriation_problems(before),
			(Problem(bridge.APPROPRIATION_TOO_HIGH, ("5.000,00 €", "0,00 €")),),
		)

	def test_an_ug_below_its_quarter_is_an_error(self):
		self.assertEqual(
			bridge.appropriation_findings(
				Appropriation(Decimal("8000"), Decimal(0), Decimal("2000"), ug=True)
			),
			(),
		)
		(error,) = bridge.appropriation_findings(
			Appropriation(Decimal("8000"), Decimal(0), Decimal("1000"), ug=True)
		)
		self.assertEqual((error.code, error.severity), (Code.UG_RESERVE, AnnualSeverity.ERROR))
		self.assertIn("2.000,00 €", error.text)

	def test_the_rows_of_the_draft_journal_entry(self):
		accounts = bridge.APPROPRIATION_ACCOUNTS["SKR03"]
		ug = Appropriation(Decimal("8000"), Decimal(0), Decimal("2000"), Decimal("3000"), ug=True)
		self.assertEqual(
			[
				(row.account, row.debit, row.credit)
				for row in bridge.appropriation_rows(ug, accounts, "0860", reserve_in_books=False)
			],
			[
				("0860", Decimal("5000"), Decimal(0)),
				("0846", Decimal(0), Decimal("2000")),
				("0755", Decimal(0), Decimal("3000")),
			],
		)
		gmbh = Appropriation(Decimal("8000"), Decimal(0), Decimal("2000"))
		self.assertEqual(
			[
				row.account
				for row in bridge.appropriation_rows(
					gmbh, bridge.APPROPRIATION_ACCOUNTS["SKR04"], "2970", reserve_in_books=False
				)
			],
			["2970", "2960"],
		)
		self.assertEqual(
			[row.account for row in bridge.appropriation_rows(ug, accounts, "0860", reserve_in_books=True)],
			["0860", "0755"],
		)
		with self.assertRaises(BridgeError) as raised:
			bridge.appropriation_rows(gmbh, accounts, "0860", reserve_in_books=True)
		self.assertEqual(raised.exception.template, bridge.NO_APPROPRIATION)


class TransmissionTest(TestCase):
	def setUp(self):
		self.signed = (Signature("Erika Beispiel", "Geschäftsführerin", "Musterstadt", date(2027, 5, 12)),)

	def problems(self, **options):
		values = {
			"adopted_on": date(2027, 5, 12),
			"transmitted_on": date(2027, 6, 1),
			"today": date(2027, 6, 2),
			"signatures": self.signed,
			"mode": Mode.HINTERLEGUNG,
			"notice": True,
			"order_number": "2027-0815",
		}
		values.update(options)
		return bridge.transmission_record_problems(**values)

	def test_a_complete_uebermittlung(self):
		self.assertEqual(self.problems(), ())
		self.assertEqual(self.problems(mode=Mode.OFFENLEGUNG, notice=False), ())

	def test_what_the_uebermittlung_needs(self):
		self.assertEqual(
			[
				problem.template
				for problem in self.problems(
					transmitted_on=date(2027, 6, 3), signatures=(), notice=False, order_number=" "
				)
			],
			[bridge.TRANSMITTED_LATER, bridge.TRANSMISSION_REFUSED, bridge.NO_NOTICE, bridge.NO_ORDER_NUMBER],
		)
		(before,) = self.problems(adopted_on=date(2027, 6, 2), transmitted_on=date(2027, 6, 1))
		self.assertIn("festgestellte", before.values[0])

	def test_what_the_einstellung_needs(self):
		self.assertEqual(
			bridge.publication_record_problems(date(2027, 6, 1), date(2027, 6, 10), date(2027, 6, 10)), ()
		)
		self.assertEqual(
			bridge.publication_record_problems(date(2027, 6, 1), date(2027, 5, 31), date(2027, 6, 10)),
			(Problem(bridge.PUBLISHED_EARLY, ("31. Mai 2027", "1. Juni 2027")),),
		)
		self.assertEqual(
			bridge.publication_record_problems(date(2027, 6, 1), date(2027, 6, 11), date(2027, 6, 10)),
			(Problem(bridge.PUBLISHED_LATER, ("11. Juni 2027",)),),
		)


class DisclosureTest(TestCase):
	def test_a_kleinst_deposits_unless_told_otherwise_and_every_other_class_publishes(self):
		self.assertIs(bridge.mode_of("", KLEINST), Mode.HINTERLEGUNG)
		self.assertIs(bridge.mode_of("Veröffentlichung", KLEINST), Mode.OFFENLEGUNG)
		self.assertIs(bridge.mode_of("Veröffentlichung", KLEIN), Mode.OFFENLEGUNG)
		self.assertIs(bridge.mode_of("", None), Mode.OFFENLEGUNG)
		for size_class, named in ((KLEIN, "kleine Kapitalgesellschaft"), (None, bridge.NO_CLASS_YET)):
			with self.subTest(size_class=size_class), self.assertRaises(BridgeError) as raised:
				bridge.mode_of("Hinterlegung", size_class)
			self.assertEqual(
				(raised.exception.template, raised.exception.values),
				(bridge.HINTERLEGUNG_FOR_KLEINST, (named,)),
			)
		self.assertEqual([bridge.stored_mode(mode) for mode in Mode], ["Veröffentlichung", "Hinterlegung"])

	def test_a_kleinst_that_publishes_what_it_could_deposit_is_a_hint(self):
		self.assertEqual(bridge.deposit_finding(KLEINST, Mode.HINTERLEGUNG), ())
		self.assertEqual(bridge.deposit_finding(KLEIN, Mode.OFFENLEGUNG), ())
		(hint,) = bridge.deposit_finding(KLEINST, Mode.OFFENLEGUNG)
		self.assertEqual(hint.code, Code.DEPOSIT)


class XbrlInputsTest(TestCase):
	def test_the_periods_with_the_previous_year_of_the_books_or_the_twelve_months_before(self):
		self.assertEqual(
			bridge.periods_of(date(2026, 1, 1), END, date(2025, 1, 1), PRIOR_END),
			Periods(date(2026, 1, 1), END, None, date(2025, 1, 1), PRIOR_END),
		)
		self.assertEqual(
			bridge.prior_period(date(2026, 1, 1), (date(2025, 3, 1), PRIOR_END)),
			(date(2025, 3, 1), PRIOR_END),
		)
		self.assertEqual(bridge.prior_period(date(2026, 1, 1), None), (date(2025, 1, 1), PRIOR_END))
		self.assertEqual(bridge.prior_period(date(2028, 2, 29), None), (date(2027, 2, 28), date(2028, 2, 28)))

	def test_the_address_of_the_gcd(self):
		address = settings_rules.Address("Musterweg", "12", "a", None, "12345", "Musterstadt")
		self.assertEqual(bridge.address_of(address), Address("Musterweg", "12a", "12345", "Musterstadt"))
		abroad = settings_rules.Address("Hauptstraße", "1", None, None, "1010", "Wien", "Austria")
		self.assertEqual(bridge.address_of(abroad).country, "Austria")
		self.assertIsNone(
			bridge.address_of(settings_rules.Address("Musterweg", None, None, None, "12345", "Musterstadt"))
		)

	def test_the_notes_and_the_master_data(self):
		signed = (Signature("Erika Beispiel", "Geschäftsführerin", "Musterstadt", date(2027, 5, 12)),)
		answers = (NoteAnswer("ZUSAETZLICHE-ANGABEN", Answer.NO),)
		notes = bridge.notes_of(companies.KLEINST_REGISTER, answers, signed)
		self.assertEqual(
			(notes.answers, notes.signatures, notes.contingent, notes.advances), (answers, signed, (), ())
		)
		periods = Periods(date(2026, 1, 1), END)
		first = bridge.master_data(
			periods, date(2027, 5, 12), None, founded_on=None, generated_on=None, changed=False
		)
		changed = bridge.master_data(
			periods,
			date(2027, 5, 12),
			None,
			founded_on=date(2024, 3, 1),
			generated_on=date(2027, 6, 1),
			changed=True,
		)
		self.assertEqual((first.revision, changed.revision), (RevisionStatus.FIRST, RevisionStatus.CHANGED))
		self.assertEqual((changed.founded_on, changed.generated_on), (date(2024, 3, 1), date(2027, 6, 1)))

	def test_the_upload_takes_the_steps_of_the_class(self):
		self.assertEqual(
			upload.steps(KLEINST, Mode.HINTERLEGUNG, first_upload=True)[0].title, "Testplattform"
		)


class MessagesTest(TestCase):
	def test_every_message_is_listed_once_for_the_translations(self):
		self.assertEqual(len(bridge.MESSAGES), len(set(bridge.MESSAGES)))
		self.assertIn(bridge.CORRECTION_REFUSED, bridge.MESSAGES)

	def test_the_bilanz_of_2026(self):
		self.assertTrue(balance_sheet_scheme(2026).has(PREPAID))
		self.assertEqual(build(2026, KLEINST, ()).balance_sheet.aktiva_total, Decimal(0))
