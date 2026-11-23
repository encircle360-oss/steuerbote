"""The Bilanzzuordnung of a company (steuerbote/xbrl/mapping.py): its rows, the positions they name in the
HGB-Taxonomie, and the balances of the books placed on those positions."""

from unittest import TestCase

from steuerbote.hgb.statement import RemainingTerm
from steuerbote.ustva import WatchLevel
from steuerbote.xbrl import mapping
from steuerbote.xbrl.mapping import (
	Excluded,
	Mapping,
	MappingError,
	Part,
	Purpose,
	Rule,
	Watched,
)
from steuerbote.xbrl.tests import positions
from steuerbote.xbrl.versions import LATEST

BANK = "bs.ass.currAss.cashEquiv.bank"
BANK_LIABILITY = "bs.eqLiab.liab.bank"


class RuleTest(TestCase):
	def test_a_rule_names_its_account_and_its_position(self):
		rule = Rule("1200", BANK)
		self.assertEqual(
			(
				rule.account_number,
				rule.concept,
				rule.opposite,
				rule.purpose,
				rule.shareholder,
				rule.remaining_term,
			),
			("1200", BANK, None, Purpose.BOTH, False, None),
		)

	def test_names_a_position_without_the_prefix_of_the_gaap_module(self):
		"""As steuerbote/hgb/statement.py and Taxonomy.parents() name them."""
		rule = Rule("1200", f"de-gaap-ci:{BANK}", opposite=f"de-gaap-ci:{BANK_LIABILITY}")
		self.assertEqual((rule.concept, rule.opposite), (BANK, BANK_LIABILITY))
		self.assertEqual(Rule("1200", f"  {BANK} ").concept, BANK)

	def test_takes_a_position_for_the_opposite_balance(self):
		"""A bank account with a credit balance goes to the Verbindlichkeiten gegenüber Kreditinstituten
		(Technischer Leitfaden zur HGB-Taxonomie 6.9, A.13)."""
		self.assertEqual(Rule("1200", BANK, opposite=BANK_LIABILITY).opposite, BANK_LIABILITY)
		self.assertIsNone(Rule("1200", BANK, opposite="").opposite)

	def test_takes_its_purpose_its_shareholder_flag_and_its_remaining_term_by_their_values(self):
		rule = Rule("3150", BANK_LIABILITY, purpose="tax", shareholder=True, remaining_term="up to one year")
		self.assertEqual(
			(rule.purpose, rule.shareholder, rule.remaining_term),
			(Purpose.TAX, True, RemainingTerm.UP_TO_ONE_YEAR),
		)
		self.assertEqual(
			[mapping.REMAINING_TERMS[term] for term in mapping.REMAINING_TERMS],
			[RemainingTerm.UP_TO_ONE_YEAR, RemainingTerm.ONE_TO_FIVE_YEARS, RemainingTerm.OVER_FIVE_YEARS],
		)
		self.assertEqual(
			Rule("3150", BANK_LIABILITY, remaining_term=RemainingTerm.OVER_FIVE_YEARS).term_value,
			"over five years",
		)
		self.assertIsNone(Rule("3150", BANK_LIABILITY).term_value)

	def test_the_purposes_are_those_of_the_datev_charts(self):
		"""„Abschlusszweck: HB Diese Konten sollten ausschließlich für die Handelsbilanz gebucht werden. SB Diese Konten
		sollten ausschließlich für die Steuerbilanz gebucht werden.“ (DATEV SKR 04, Art.-Nr. 11175, „Gültig für 2026“,
		Fußnote 4)"""
		self.assertEqual([purpose.value for purpose in Purpose], ["both", "commercial", "tax"])

	def test_a_rule_counts_for_its_own_purpose_and_one_for_both_for_every_purpose(self):
		both, commercial, tax = (Rule("1200", BANK, purpose=purpose) for purpose in Purpose)
		self.assertEqual(
			[[rule.counts_for(purpose) for purpose in Purpose] for rule in (both, commercial, tax)],
			[[True, True, True], [False, True, False], [False, False, True]],
		)

	def test_an_account_number_is_compared_as_written(self):
		for number in ("", " 1200", "1200 ", None, 1200):
			with self.subTest(number=number), self.assertRaises(MappingError) as caught:
				Rule(number, BANK)
			self.assertEqual(caught.exception.template, mapping.NOT_AN_ACCOUNT_NUMBER)

	def test_a_rule_names_a_position(self):
		for concept in ("", "  ", None):
			with self.subTest(concept=concept), self.assertRaises(MappingError) as caught:
				Rule("1200", concept)
			self.assertEqual(
				(caught.exception.template, caught.exception.values), (mapping.NO_POSITION, ("1200",))
			)

	def test_the_position_for_the_opposite_balance_is_another_one(self):
		with self.assertRaises(MappingError) as caught:
			Rule("1200", BANK, opposite=f"de-gaap-ci:{BANK}")
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (mapping.SAME_OPPOSITE, ("1200",))
		)

	def test_refuses_a_purpose_and_a_remaining_term_it_does_not_know(self):
		with self.assertRaises(MappingError) as caught:
			Rule("1200", BANK, purpose="HB")
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (mapping.NO_PURPOSE, ("1200", "HB"))
		)
		with self.assertRaises(MappingError) as caught:
			Rule("3150", BANK_LIABILITY, remaining_term="kurzfristig")
		self.assertEqual(
			(caught.exception.template, caught.exception.values),
			(mapping.NO_REMAINING_TERM, ("3150", "kurzfristig")),
		)

	def test_the_shareholder_flag_is_yes_or_no(self):
		with self.assertRaises(MappingError) as caught:
			Rule("1200", BANK, shareholder="1")
		self.assertEqual(caught.exception.template, mapping.NO_FLAG)


class PlacesTest(TestCase):
	def test_a_watched_account_blocks_unless_its_level_says_hint(self):
		"""As in the VAT Return Mapping since v0.4.0 (steuerbote/ustva/mapping.py)."""
		self.assertEqual(Watched("1360").level, WatchLevel.BLOCKING)
		self.assertEqual(Watched("1360", "hint").level, WatchLevel.HINT)
		with self.assertRaises(MappingError) as caught:
			Watched("1360", "sperrt")
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (mapping.NO_LEVEL, ("1360", "sperrt"))
		)
		with self.assertRaises(MappingError):
			Watched("")

	def test_an_account_outside_the_bilanz_and_the_guv_says_why_on_one_line(self):
		self.assertEqual(
			Excluded("9000", "  Saldenvortrag,\n Sachkonten ").reason, "Saldenvortrag, Sachkonten"
		)
		for reason in ("", " \n ", None):
			with self.subTest(reason=reason), self.assertRaises(MappingError) as caught:
				Excluded("9000", reason)
			self.assertEqual(
				(caught.exception.template, caught.exception.values), (mapping.NO_REASON, ("9000",))
			)
		with self.assertRaises(MappingError):
			Excluded(" 9000", "Saldenvortrag")


class MappingTest(TestCase):
	def setUp(self):
		self.mapping = Mapping(
			"SKR03",
			rules=[Rule("1200", BANK, opposite=BANK_LIABILITY)],
			watched=[Watched("1360", WatchLevel.HINT)],
			excluded=[Excluded("9000", "Saldenvortrag")],
		)

	def test_names_the_positions_of_the_latest_taxonomy_unless_told_otherwise(self):
		self.assertEqual(self.mapping.taxonomy_version, LATEST.version)
		self.assertEqual(Mapping("SKR03", taxonomy_version="6.9").taxonomy_version, "6.9")
		with self.assertRaises(MappingError) as caught:
			Mapping("SKR03", taxonomy_version="6.8")
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (mapping.UNKNOWN_VERSION, ("6.8",))
		)

	def test_keeps_its_rows_as_tuples(self):
		self.assertEqual(
			(self.mapping.rules, self.mapping.watched, self.mapping.excluded),
			(
				(Rule("1200", BANK, opposite=BANK_LIABILITY),),
				(Watched("1360", WatchLevel.HINT),),
				(Excluded("9000", "Saldenvortrag"),),
			),
		)

	def test_gives_each_account_its_place(self):
		self.assertEqual(self.mapping.place_of("1200"), Rule("1200", BANK, opposite=BANK_LIABILITY))
		self.assertEqual(self.mapping.place_of("1360"), Watched("1360", WatchLevel.HINT))
		self.assertEqual(self.mapping.place_of("9000"), Excluded("9000", "Saldenvortrag"))
		self.assertIsNone(self.mapping.place_of("4400"))
		self.assertEqual(self.mapping.numbers, frozenset({"1200", "1360", "9000"}))

	def test_an_account_has_one_place(self):
		"""Each account goes to exactly one position or is outside the Bilanz and the GuV for a reason."""
		for places in (
			{"rules": [Rule("1200", BANK), Rule("1200", BANK_LIABILITY)]},
			{"rules": [Rule("1200", BANK)], "watched": [Watched("1200")]},
			{"rules": [Rule("1200", BANK)], "excluded": [Excluded("1200", "Bank")]},
			{"watched": [Watched("1360"), Watched("1360", WatchLevel.HINT)]},
			{"watched": [Watched("1360")], "excluded": [Excluded("1360", "Geldtransit")]},
			{"excluded": [Excluded("9000", "Saldenvortrag"), Excluded("9000", "Vortrag")]},
		):
			with self.subTest(places=places), self.assertRaises(MappingError) as caught:
				Mapping("SKR03", **places)
			self.assertEqual(caught.exception.template, mapping.TWICE)

	def test_a_mapping_error_reads_as_its_template_with_its_values(self):
		error = MappingError(mapping.TWICE, "1200")
		self.assertEqual(str(error), mapping.TWICE.format("1200"))
		self.assertEqual((error.template, error.values), (mapping.TWICE, ("1200",)))

	def test_every_template_is_one_the_frappe_layer_translates(self):
		self.assertEqual(
			set(mapping.MESSAGES),
			{
				mapping.NOT_AN_ACCOUNT_NUMBER,
				mapping.NO_POSITION,
				mapping.SAME_OPPOSITE,
				mapping.NO_PURPOSE,
				mapping.NO_REMAINING_TERM,
				mapping.NO_FLAG,
				mapping.NO_LEVEL,
				mapping.NO_REASON,
				mapping.TWICE,
				mapping.UNKNOWN_VERSION,
			},
		)
		self.assertEqual(len(mapping.MESSAGES), len(set(mapping.MESSAGES)))


CASH = "bs.ass.currAss.cashEquiv.cash"
SALES = "is.netIncome.netSales"
RECEIVABLES = "bs.ass.currAss.receiv.trade"
LOANS = "bs.ass.fixAss.fin.otherLoans"
SHARES = "bs.ass.fixAss.fin.sharesInAffil"


def problems(*rules: Rule, parts: dict | None = None, taxonomy=None) -> list[tuple[str, tuple]]:
	"""The templates and values of the problems of a mapping with the rules."""
	found = mapping.check(Mapping("SKR03", rules=rules), taxonomy or positions.view(), parts)
	return [(problem.refusal.template, problem.values) for problem in found]


class PartTest(TestCase):
	def test_a_position_belongs_to_the_bilanz_or_to_the_guv_by_its_presentation(self):
		taxonomy = positions.view()
		self.assertEqual(mapping.part_of(taxonomy, BANK), Part.BALANCE_SHEET)
		self.assertEqual(mapping.part_of(taxonomy, f"de-gaap-ci:{SALES}"), Part.INCOME_STATEMENT)
		self.assertIsNone(mapping.part_of(taxonomy, "BVV.profitLoss"))
		self.assertIsNone(mapping.part_of(taxonomy, "bs.ass.unknown"))

	def test_an_account_belongs_to_the_part_its_report_type_in_erpnext_names(self):
		"""Account.report_type of ERPNext 16, „Balance Sheet“ for Asset, Liability and Equity, „Profit and Loss“ for
		Income and Expense (erpnext/accounts/doctype/account/account.py)."""
		self.assertEqual(Part.of_report_type("Balance Sheet"), Part.BALANCE_SHEET)
		self.assertEqual(Part.of_report_type("Profit and Loss"), Part.INCOME_STATEMENT)
		with self.assertRaises(ValueError):
			Part.of_report_type("")


class PositionTest(TestCase):
	"""What a rule may name: a position of the Bilanz or the GuV that a GmbH or UG may send to the Finanzamt."""

	def test_a_rule_with_positions_of_its_part_has_no_problem(self):
		self.assertEqual(
			problems(
				Rule("1200", BANK, opposite=BANK_LIABILITY),
				Rule("8400", f"de-gaap-ci:{SALES}"),
				parts={"1200": Part.BALANCE_SHEET, "8400": Part.INCOME_STATEMENT},
			),
			[],
		)

	def test_refuses_a_position_the_taxonomy_does_not_have(self):
		"""„Es dürfen bei der Einreichung nur Positionen der zugelassenen, standardisierten Taxonomie-Schemata ...
		verwendet werden.“ (Technischer Leitfaden zur HGB-Taxonomie 6.9, B.10)"""
		self.assertEqual(
			problems(Rule("1200", "bs.ass.currAss.cashEquiv.gold")),
			[(mapping.UNKNOWN_POSITION.template, ("1200", "bs.ass.currAss.cashEquiv.gold", "6.9"))],
		)

	def test_refuses_a_position_that_takes_no_amount_in_euros(self):
		self.assertEqual(
			problems(Rule("1200", "detailedInformation"), Rule("1300", "nt")),
			[
				(mapping.ABSTRACT.template, ("1200", "detailedInformation", "6.9")),
				(mapping.NOT_MONETARY.template, ("1300", "nt", "6.9")),
			],
		)

	def test_refuses_a_position_outside_the_bilanz_and_the_guv(self):
		"""The mapping feeds the Bilanz and the GuV „einschließlich der unverdichteten Kontennachweise“ (§ 5b Abs. 1
		Satz 1 EStG), the Betriebsvermögensvergleich derives from them."""
		self.assertEqual(
			problems(Rule("0800", "BVV.profitLoss"), Rule("0810", "de-gcd:genInfo.company.id.shareholder")),
			[
				(mapping.NOT_A_STATEMENT_POSITION.template, ("0800", "BVV.profitLoss", "6.9")),
				(mapping.NOT_MONETARY.template, ("0810", "de-gcd:genInfo.company.id.shareholder", "6.9")),
			],
		)

	def test_refuses_a_position_of_another_legal_form(self):
		"""„nur Positionen mit der Auszeichnung „legalFormKSt“ = „true“ und Positionen, die keiner Rechtsform
		zugeordnet sind“ (Leitfaden B.4.2): Steuerbote serves the GmbH and the UG."""
		concept = "bs.eqLiab.equity.subscribed.limitedLiablePartners"
		self.assertEqual(
			problems(Rule("0800", concept)), [(mapping.LEGAL_FORM.template, ("0800", concept, "6.9"))]
		)

	def test_refuses_a_position_not_permitted_for_the_finanzverwaltung(self):
		"""„Die mit „Einreichung an Finanzverwaltung“ gekennzeichneten Positionen dürfen für die Übermittlung von
		E-Bilanzen an die Finanzverwaltung nicht verwendet werden.“ (Leitfaden A.9.3, B.14.6)"""
		concept = "bs.ass.consolidationDifference"
		self.assertEqual(
			problems(Rule("0040", concept)), [(mapping.SUBMISSION.template, ("0040", concept, "6.9"))]
		)

	def test_refuses_a_position_of_a_sonder_or_ergaenzungsbilanz(self):
		"""onlyPermittedForSoBil_ErgBil (Leitfaden A.9.3), which a GmbH never files."""
		concept = "bs.eqLiab.liab.colEntity"
		self.assertEqual(
			problems(Rule("0700", concept)), [(mapping.SPECIAL_BALANCE.template, ("0700", concept, "6.9"))]
		)

	def test_refuses_a_position_of_the_umsatzkostenverfahren(self):
		"""Steuerbote draws the GuV up by the Gesamtkostenverfahren, which takes no position marked UKV (Leitfaden
		B.14.3.1.15)."""
		concept = "is.netIncome.costOfSales"
		self.assertEqual(
			problems(Rule("4000", concept)), [(mapping.COST_OF_SALES.template, ("4000", concept, "6.9"))]
		)

	def test_refuses_a_position_without_a_debit_or_credit_balance(self):
		"""„Wird ein Konto einer Position zugeordnet, die keine Soll/Haben-Auszeichnung besitzt, dann muss aus dem
		fachlichen Kontext heraus individuell entschieden werden“ (Leitfaden A.13), which a mapping cannot."""
		self.assertEqual(
			problems(Rule("0001", "bs.ass.noSide")),
			[(mapping.NO_SIDE.template, ("0001", "bs.ass.noSide", "6.9"))],
		)

	def test_checks_the_position_for_the_opposite_balance_alike(self):
		self.assertEqual(
			problems(Rule("1200", BANK, opposite="bs.eqLiab.liab.bank.overdraft")),
			[(mapping.UNKNOWN_POSITION.template, ("1200", "bs.eqLiab.liab.bank.overdraft", "6.9"))],
		)

	def test_the_position_for_the_opposite_balance_lies_on_the_other_side(self):
		"""The opposite position takes a balance on the other side of the position (Leitfaden A.13)."""
		self.assertEqual(
			problems(Rule("1200", BANK, opposite=CASH)), [(mapping.SAME_SIDE.template, ("1200", CASH, BANK))]
		)

	def test_both_positions_of_a_rule_belong_to_one_part(self):
		self.assertEqual(
			problems(Rule("1200", BANK, opposite=SALES)),
			[(mapping.OTHER_PARTS.template, ("1200", BANK, SALES))],
		)

	def test_an_account_goes_to_a_position_of_its_own_part(self):
		"""The Bilanz holds the Vermögen and the Schulden at the Stichtag, the GuV the Aufwendungen and Erträge of the
		Geschäftsjahr (§ 242 Abs. 1 und 2 HGB): ERPNext sums a balance sheet account up to the day and a profit and loss
		account within the year, so its balance fits only a position of its own part."""
		self.assertEqual(
			problems(
				Rule("1200", SALES),
				Rule("8400", BANK),
				parts={"1200": Part.BALANCE_SHEET, "8400": Part.INCOME_STATEMENT},
			),
			[
				(mapping.BALANCE_SHEET_ACCOUNT.template, ("1200", SALES)),
				(mapping.INCOME_STATEMENT_ACCOUNT.template, ("8400", BANK)),
			],
		)

	def test_a_remaining_term_goes_with_forderungen_and_verbindlichkeiten(self):
		"""§ 268 Abs. 4 Satz 1 and Abs. 5 Satz 1 HGB note the remaining terms of the Forderungen and the
		Verbindlichkeiten; a bank account with a credit balance is one of them."""
		term = RemainingTerm.UP_TO_ONE_YEAR
		self.assertEqual(
			problems(
				Rule("3150", BANK_LIABILITY, remaining_term=term),
				Rule("1400", RECEIVABLES, remaining_term=term),
				Rule("1200", BANK, opposite=BANK_LIABILITY, remaining_term=term),
			),
			[],
		)
		self.assertEqual(
			problems(Rule("1000", CASH, remaining_term=term)),
			[(mapping.REMAINING_TERM.template, ("1000", CASH))],
		)

	def test_the_shareholder_flag_goes_with_ausleihungen_forderungen_and_verbindlichkeiten(self):
		"""„Ausleihungen, Forderungen und Verbindlichkeiten gegenüber Gesellschaftern“ (§ 42 Abs. 3 GmbHG)."""
		self.assertEqual(
			problems(
				Rule("3500", BANK_LIABILITY, shareholder=True),
				Rule("1300", RECEIVABLES, shareholder=True),
				Rule("0505", LOANS, shareholder=True),
			),
			[],
		)
		self.assertEqual(
			problems(Rule("0500", SHARES, shareholder=True), Rule("1000", CASH, shareholder=True)),
			[
				(mapping.SHAREHOLDER.template, ("0500", SHARES)),
				(mapping.SHAREHOLDER.template, ("1000", CASH)),
			],
		)

	def test_a_problem_reads_as_its_template_for_the_form_and_as_its_sentence_for_a_document(self):
		(problem,) = mapping.check(
			Mapping("SKR03", rules=[Rule("1000", CASH, shareholder=True)]), positions.view()
		)
		self.assertEqual(problem.message, mapping.SHAREHOLDER.template.format("1000", CASH))
		self.assertEqual(problem.text, mapping.SHAREHOLDER.sentence.format("1000", CASH))
		self.assertEqual((problem.account_number, problem.source), ("1000", "§ 42 Abs. 3 GmbHG"))
		self.assertTrue(problem.text.startswith("Konto 1000"))

	def test_every_refusal_has_a_template_a_sentence_and_a_source(self):
		for refusal in mapping.REFUSALS:
			with self.subTest(refusal=refusal.template):
				self.assertTrue(refusal.template.startswith("Account {0}"))
				self.assertTrue(refusal.sentence.startswith("Konto {0}"))
				self.assertTrue(refusal.source)
		self.assertEqual(len({refusal.template for refusal in mapping.REFUSALS}), len(mapping.REFUSALS))
