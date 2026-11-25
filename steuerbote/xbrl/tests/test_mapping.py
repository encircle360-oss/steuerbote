"""The Bilanzzuordnung of a company (steuerbote/xbrl/mapping.py): its rows, the positions they name in the
HGB-Taxonomie, and the balances of the books placed on those positions."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from unittest import TestCase

from steuerbote.hgb.statement import RemainingTerm
from steuerbote.ustva import WatchLevel
from steuerbote.xbrl import mapping
from steuerbote.xbrl.mapping import (
	AccountBalance,
	Accounts,
	Books,
	DefaultExcluded,
	DefaultRule,
	Defaults,
	DefaultWatched,
	Excluded,
	Mapping,
	MappingError,
	Part,
	Purpose,
	Rule,
	Watched,
)
from steuerbote.xbrl.taxonomy import LABEL
from steuerbote.xbrl.tests import positions
from steuerbote.xbrl.versions import FIRST

BANK = "bs.ass.currAss.cashEquiv.bank"
BANK_LIABILITY = "bs.eqLiab.liab.bank"
TAX_LIABILITY = "bs.eqLiab.liab.other.theroffTax"


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

	def test_takes_the_netting_group_of_its_account(self):
		"""Claims and debts towards the same creditor that can be set off against each other are shown netted, as one
		settlement position (§ 387 BGB, § 226 Abs. 1 AO; § 246 Abs. 2 Satz 1 HGB does not bar it)."""
		rule = Rule("1576", OTHER_ASSETS, opposite=TAX_LIABILITY, netting="  Umsatzsteuer ")
		self.assertEqual(rule.netting, "Umsatzsteuer")
		self.assertIsNone(Rule("1576", OTHER_ASSETS, opposite=TAX_LIABILITY, netting=" ").netting)
		self.assertIsNone(Rule("1576", OTHER_ASSETS).netting)

	def test_a_netting_group_needs_the_position_for_the_opposite_balance(self):
		"""The combined balance of the group decides the side, so every account of it needs a position on each."""
		with self.assertRaises(MappingError) as caught:
			Rule("1576", OTHER_ASSETS, netting="Umsatzsteuer")
		self.assertEqual(
			(caught.exception.template, caught.exception.values),
			(mapping.NETTING_WITHOUT_OPPOSITE, ("1576", "Umsatzsteuer")),
		)


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

	def test_names_the_positions_of_the_first_taxonomy_unless_told_otherwise(self):
		"""A new mapping names the positions of the taxonomy of the first fiscal year Steuerbote files, 6.9, and
		„Auf neue Taxonomie heben“ lifts it to 6.10 (steuerbote/xbrl/changes.py)."""
		self.assertEqual(self.mapping.taxonomy_version, FIRST.version)
		self.assertEqual(Mapping("SKR03", taxonomy_version="6.9").taxonomy_version, "6.9")
		self.assertEqual(Mapping("SKR03", taxonomy_version="6.10").taxonomy_version, "6.10")
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
				mapping.NETTING_WITHOUT_OPPOSITE,
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


RETAINED = "bs.eqLiab.equity.retainedEarnings"
TRADE_ABOVE_ONE_YEAR = "bs.ass.currAss.receiv.trade.above1year"
OTHER_ASSETS = "bs.ass.currAss.receiv.other.misc"
WJ_2026 = (date(2026, 1, 1), date(2026, 12, 31))


def balance(number: str, debit: str = "0", credit: str = "0", part: Part = Part.BALANCE_SHEET, **values):
	return AccountBalance(
		account=values.pop("account", f"{number} - Konto - MG"),
		number=number,
		label=values.pop("label", f"Konto {number}"),
		part=part,
		debit=Decimal(debit),
		credit=Decimal(credit),
	)


def placed(*rules: Rule, balances, purpose=Purpose.BOTH, **values):
	return mapping.place(
		Mapping("SKR04", rules=rules, **values.pop("places", {})),
		Books(tuple(balances), values.pop("earlier_result", Decimal(0))),
		values.pop("taxonomy", positions.view()),
		purpose,
		**values,
	)


def codes(placement) -> list[tuple[str, str, str]]:
	return [(finding.code.value, finding.severity.value, finding.account) for finding in placement.findings]


class AccountBalanceTest(TestCase):
	def test_an_account_balance_is_debit_minus_credit_in_decimal(self):
		self.assertEqual(balance("1800", "1500.25", "300.05").amount, Decimal("1200.20"))
		with self.assertRaises(TypeError):
			AccountBalance("1800 - Bank - MG", "1800", "Bank", Part.BALANCE_SHEET, 1500.25)

	def test_the_books_hold_their_balances_as_a_tuple(self):
		books = Books([balance("1800", "10")])
		self.assertEqual((books.balances, books.earlier_result), ((balance("1800", "10"),), Decimal(0)))


class SignTest(TestCase):
	"""„Entspricht die Soll/Haben-Auszeichnung eines Kontos der Soll/Haben-Auszeichnung der Position, dann ist der
	Kontensaldo unverändert zu weiteren zugeordneten Konten zu addieren ... Bei abweichenden Soll/Haben-Auszeichnungen
	eines Kontos, ist der Kontosaldo mit „-1“ zu multiplizieren“ (Technischer Leitfaden zur HGB-Taxonomie 6.9, A.13)."""

	def test_a_balance_on_the_side_of_its_position_counts_as_it_is(self):
		placement = placed(
			Rule("1800", BANK),
			Rule("4400", SALES),
			balances=[balance("1800", "1000"), balance("4400", credit="500", part=Part.INCOME_STATEMENT)],
		)
		self.assertEqual(
			[(item.concept, item.position, item.amount, item.value) for item in placement.placed],
			[(BANK, BANK, Decimal("1000"), Decimal("1000")), (SALES, SALES, Decimal("-500"), Decimal("500"))],
		)
		self.assertEqual((placement.findings, placement.left_out, placement.ready), ((), (), True))

	def test_a_balance_on_the_other_side_counts_negative(self):
		"""Erlösschmälerungen booked on an account of the Umsatzerlöse lower them."""
		(item,) = placed(
			Rule("4400", SALES), balances=[balance("4400", debit="50", part=Part.INCOME_STATEMENT)]
		).placed
		self.assertEqual((item.concept, item.value), (SALES, Decimal("-50")))

	def test_a_balance_on_the_other_side_goes_to_the_position_for_the_opposite_balance(self):
		"""„Ist der Saldo jedoch im „Haben“ (d.h. das Konto wurde „überzogen“) so erfolgt der Ausweis auf der
		Passivseite unter den Verbindlichkeiten“ (A.13)."""
		rule = Rule("1800", BANK, opposite=BANK_LIABILITY)
		(debit,) = placed(rule, balances=[balance("1800", "100")]).placed
		(credit,) = placed(rule, balances=[balance("1800", "100", "300")]).placed
		self.assertEqual((debit.concept, debit.value), (BANK, Decimal("100")))
		self.assertEqual(
			(credit.concept, credit.position, credit.value), (BANK_LIABILITY, BANK_LIABILITY, Decimal(200))
		)
		(without,) = placed(Rule("1800", BANK), balances=[balance("1800", "100", "300")]).placed
		self.assertEqual((without.concept, without.value), (BANK, Decimal("-200")))

	def test_an_account_without_a_balance_places_nothing(self):
		placement = placed(Rule("1800", BANK), balances=[balance("1800", "70", "70"), balance("9999")])
		self.assertEqual((placement.placed, placement.left_out, placement.findings), ((), (), ()))

	def test_a_davon_position_counts_in_the_position_above_it_in_a_calculation(self):
		"""A „davon“ position is in no calculation (Leitfaden B.14.11), and „Zu rechnerisch nicht verknüpften
		Positionen darf das Tupel „Kontensalden zu einer Position“ nicht übermittelt werden“ (Technischer Leitfaden 6.10,
		B.12.1): its balance counts in the position the presentation puts it under."""
		placement = placed(
			Rule("1210", TRADE_ABOVE_ONE_YEAR),
			Rule("7100", "is.netIncome.interestIncome.assoc"),
			balances=[balance("1210", "80"), balance("7100", credit="12", part=Part.INCOME_STATEMENT)],
		)
		self.assertEqual(
			[(item.concept, item.position, item.value) for item in placement.placed],
			[
				(TRADE_ABOVE_ONE_YEAR, RECEIVABLES, Decimal("80")),
				("is.netIncome.interestIncome.assoc", "is.netIncome.interestIncome", Decimal("12")),
			],
		)


class NettingTest(TestCase):
	"""A netting group: the accounts of claims and debts towards the same creditor that can be set off against each
	other, such as Vorsteuer and Umsatzsteuer towards the Finanzamt, form one settlement position whose combined balance
	decides its side (§ 387 BGB, § 226 Abs. 1 AO, § 16 Abs. 2 Satz 1 UStG); § 246 Abs. 2 Satz 1 HGB bars netting
	only where no such set-off is possible."""

	@property
	def RULES(self) -> tuple[Rule, ...]:
		return (
			Rule("1576", OTHER_ASSETS, opposite=TAX_LIABILITY, netting="Umsatzsteuer"),
			Rule("1776", TAX_LIABILITY, opposite=OTHER_ASSETS, netting="Umsatzsteuer"),
		)

	def test_a_group_with_a_credit_balance_goes_to_the_liabilities_with_every_account(self):
		placement = placed(*self.RULES, balances=[balance("1576", "300"), balance("1776", credit="500")])
		self.assertEqual(
			[(item.balance.number, item.concept, item.value) for item in placement.placed],
			[("1576", TAX_LIABILITY, Decimal("-300")), ("1776", TAX_LIABILITY, Decimal("500"))],
		)
		self.assertEqual(sum(item.value for item in placement.placed), Decimal("200"))

	def test_a_group_with_a_debit_balance_goes_to_the_receivables_with_every_account(self):
		placement = placed(*self.RULES, balances=[balance("1576", "800"), balance("1776", credit="500")])
		self.assertEqual(
			[(item.balance.number, item.concept, item.value) for item in placement.placed],
			[("1576", OTHER_ASSETS, Decimal("800")), ("1776", OTHER_ASSETS, Decimal("-500"))],
		)

	def test_a_balanced_group_stays_on_one_side_and_shows_nothing(self):
		placement = placed(*self.RULES, balances=[balance("1576", "500"), balance("1776", credit="500")])
		self.assertEqual({item.concept for item in placement.placed}, {OTHER_ASSETS})
		self.assertEqual(sum(item.value for item in placement.placed), Decimal(0))

	def test_the_netting_is_a_hint_to_confirm_with_its_amount_and_side(self):
		placement = placed(*self.RULES, balances=[balance("1576", "300"), balance("1776", credit="500")])
		netted = [finding for finding in placement.findings if finding.code is mapping.Code.NETTED]
		self.assertEqual(
			[(finding.severity, finding.account, finding.concept, finding.amount) for finding in netted],
			[(mapping.Severity.HINT, "Umsatzsteuer", TAX_LIABILITY, Decimal("-200"))],
		)
		self.assertIn("1576, 1776", netted[0].text)
		self.assertIn("200,00 €", netted[0].text)
		self.assertIn("§ 246 Abs. 2 Satz 1 HGB", netted[0].source)
		self.assertTrue(placement.ready)

	def test_an_account_outside_the_group_keeps_its_own_side(self):
		placement = placed(
			*self.RULES,
			Rule("1800", BANK, opposite=BANK_LIABILITY),
			balances=[balance("1576", "300"), balance("1776", credit="500"), balance("1800", credit="50")],
		)
		self.assertEqual(
			[(item.balance.number, item.concept) for item in placement.placed],
			[("1576", TAX_LIABILITY), ("1776", TAX_LIABILITY), ("1800", BANK_LIABILITY)],
		)

	def test_groups_are_netted_each_on_their_own(self):
		placement = placed(
			*self.RULES,
			Rule("1800", BANK, opposite=BANK_LIABILITY, netting="Hausbank"),
			Rule("1810", BANK, opposite=BANK_LIABILITY, netting="Hausbank"),
			balances=[
				balance("1576", "300"),
				balance("1776", credit="500"),
				balance("1800", "100"),
				balance("1810", credit="40"),
			],
		)
		self.assertEqual(
			[(item.balance.number, item.concept) for item in placement.placed],
			[("1576", TAX_LIABILITY), ("1776", TAX_LIABILITY), ("1800", BANK), ("1810", BANK)],
		)

	def test_a_balance_left_out_of_the_balance_sheet_does_not_count_in_its_group(self):
		rules = (
			self.RULES[0],
			replace(self.RULES[1], purpose=Purpose.TAX),
		)
		placement = placed(
			*rules,
			balances=[balance("1576", "300"), balance("1776", credit="500")],
			purpose=Purpose.COMMERCIAL,
		)
		self.assertEqual(
			[(item.balance.number, item.concept, item.value) for item in placement.placed],
			[("1576", OTHER_ASSETS, Decimal("300"))],
		)

	def test_a_single_account_of_a_group_shows_no_hint(self):
		placement = placed(*self.RULES, balances=[balance("1776", credit="500")])
		self.assertNotIn(mapping.Code.NETTED, [finding.code for finding in placement.findings])


class PurposeTest(TestCase):
	def test_a_balance_counts_in_the_balance_sheets_its_rule_is_for(self):
		rules = (
			Rule("2981", "bs.eqLiab.liab.other", purpose=Purpose.TAX),
			Rule("6241", "is.netIncome.staff", purpose=Purpose.COMMERCIAL),
			Rule("1800", BANK),
		)
		books = [
			balance("2981", credit="40"),
			balance("6241", "40", part=Part.INCOME_STATEMENT),
			balance("1800", "10"),
		]
		counted = {
			purpose: [item.balance.number for item in placed(*rules, balances=books, purpose=purpose).placed]
			for purpose in Purpose
		}
		self.assertEqual(
			counted,
			{Purpose.BOTH: ["1800"], Purpose.COMMERCIAL: ["6241", "1800"], Purpose.TAX: ["2981", "1800"]},
		)

	def test_a_balance_left_out_for_its_purpose_is_a_hint(self):
		"""„Abschlusszweck: HB Diese Konten sollten ausschließlich für die Handelsbilanz gebucht werden. SB Diese Konten
		sollten ausschließlich für die Steuerbilanz gebucht werden.“ (DATEV SKR 04, Art.-Nr. 11175, Fußnote 4)"""
		books = [balance("2981", credit="40")]
		placement = placed(
			Rule("2981", "bs.eqLiab.liab.other", purpose=Purpose.TAX),
			balances=books,
			purpose=Purpose.COMMERCIAL,
		)
		self.assertEqual(codes(placement), [("BILANZ-ABSCHLUSSZWECK", "Hinweis", "2981")])
		(finding,) = placement.findings
		self.assertIn("nur für die Steuerbilanz", finding.text)
		self.assertEqual(
			(finding.amount, finding.concept, finding.source),
			(Decimal("-40"), "bs.eqLiab.liab.other", "DATEV-Kontenrahmen SKR 03 und SKR 04, Fußnote 4"),
		)
		self.assertEqual((placement.left_out, placement.ready), (tuple(books), True))
		(einheitsbilanz,) = placed(
			Rule("2981", "bs.eqLiab.liab.other", purpose=Purpose.COMMERCIAL), balances=books
		).findings
		self.assertIn("nur für die Handelsbilanz", einheitsbilanz.text)


class PlacesOfBalancesTest(TestCase):
	"""„Der Jahresabschluß hat sämtliche Vermögensgegenstände, Schulden, Rechnungsabgrenzungsposten sowie Aufwendungen
	und Erträge zu enthalten“ (§ 246 Abs. 1 Satz 1 HGB): a balance without a position holds the documents back."""

	def test_a_balance_on_an_account_without_a_place_is_an_error(self):
		books = [balance("1800", "10"), balance("1360", "5", label="Geldtransit")]
		placement = placed(Rule("1800", BANK), balances=books)
		self.assertEqual(codes(placement), [("BILANZ-OHNE-PLATZ", "Fehler", "1360")])
		(finding,) = placement.findings
		self.assertEqual(
			finding.text,
			"Konto 1360 Geldtransit hat einen Saldo, aber keinen Platz in der Bilanzzuordnung: Ordnen Sie es einer "
			"Position zu, oder sagen Sie, warum es außerhalb von Bilanz und GuV liegt.",
		)
		self.assertEqual((finding.amount, finding.source), (Decimal("5"), "§ 246 Abs. 1 Satz 1 HGB"))
		self.assertEqual((placement.left_out, placement.ready), ((books[1],), False))

	def test_a_balance_on_an_account_without_a_number_is_an_error(self):
		"""Every row of the mapping names its account by its number."""
		books = [balance("", "5", account="Kasse - MG", label="Kasse")]
		placement = placed(balances=books)
		self.assertEqual(codes(placement), [("BILANZ-OHNE-KONTONUMMER", "Fehler", "Kasse - MG")])
		self.assertIn("keine Kontonummer", placement.findings[0].text)

	def test_a_balance_on_a_watched_account_holds_the_documents_back_or_adds_a_hint(self):
		books = [balance("1360", "5"), balance("1370", credit="5")]
		placement = placed(
			balances=books, places={"watched": [Watched("1360"), Watched("1370", WatchLevel.HINT)]}
		)
		self.assertEqual(
			codes(placement),
			[("BILANZ-BEOBACHTET", "Fehler", "1360"), ("BILANZ-BEOBACHTET", "Hinweis", "1370")],
		)
		self.assertEqual((placement.left_out, placement.ready), (tuple(books), False))
		self.assertIn("ohne Position", placement.findings[1].text)

	def test_a_balance_outside_the_bilanz_and_the_guv_is_a_hint_with_its_reason(self):
		books = [balance("9000", credit="5")]
		placement = placed(
			balances=books, places={"excluded": [Excluded("9000", "Saldenvortrag Sachkonten")]}
		)
		self.assertEqual(codes(placement), [("BILANZ-AUSSERHALB", "Hinweis", "9000")])
		self.assertIn("Saldenvortrag Sachkonten", placement.findings[0].text)
		self.assertEqual((placement.left_out, placement.ready), (tuple(books), True))

	def test_a_balance_on_a_refused_position_is_an_error_of_the_problem(self):
		books = [balance("1800", "10", part=Part.INCOME_STATEMENT), balance("0600", "7")]
		placement = placed(
			Rule("1800", BANK),
			Rule("0600", "bs.ass.fixAss.tan.lostEquipment"),
			Rule("0700", "nt"),
			balances=books,
		)
		self.assertEqual(
			codes(placement), [("BILANZ-POSITION", "Fehler", "1800"), ("BILANZ-POSITION", "Fehler", "0600")]
		)
		first, second = placement.findings
		self.assertEqual(
			(first.text, first.source, first.concept),
			(
				mapping.INCOME_STATEMENT_ACCOUNT.sentence.format("1800", BANK),
				mapping.INCOME_STATEMENT_ACCOUNT.source,
				BANK,
			),
		)
		self.assertEqual(second.concept, "bs.ass.fixAss.tan.lostEquipment")
		self.assertEqual((placement.left_out, placement.ready), (tuple(books), False))

	def test_a_balance_on_an_auffangposition_is_a_hint(self):
		"""Auffangpositionen are „erkennbar durch die Formulierungen im beschreibenden Text „nicht zuordenbar“ oder
		„ohne Zuordnung““ and serve where „eine durch Mussfelder vorgegebene Differenzierung ... nicht aus der Buchhaltung
		ableitbar“ is (Leitfaden A.10.4)."""
		placement = placed(Rule("1500", OTHER_ASSETS), balances=[balance("1500", "9")])
		self.assertEqual(codes(placement), [("BILANZ-AUFFANGPOSITION", "Hinweis", "1500")])
		self.assertEqual(len(placement.placed), 1)
		self.assertTrue(mapping.catch_all(positions.view(), OTHER_ASSETS))
		self.assertTrue(mapping.catch_all(positions.view(), "bs.ass.currAss.receiv.other.misc"))
		self.assertFalse(mapping.catch_all(positions.view(), BANK))
		labelled = replace(
			positions.view(),
			labels=MappingProxyType(
				{
					**positions.view().labels,
					f"de-gaap-ci:{SALES}": {LABEL: "Umsatzerlöse ohne Zuordnung nach USt"},
				}
			),
		)
		self.assertTrue(mapping.catch_all(labelled, SALES))

	def test_a_position_not_valid_in_the_fiscal_year_is_an_error(self):
		"""„Die Übermittelbarkeit kann zeitlich eingeschränkt sein“ (Leitfaden B.11, B.14.4.1)."""
		books = [balance("0400", "10"), balance("1700", "3")]
		rules = (
			Rule("0400", "bs.ass.fixAss.tan.oldEquipment"),
			Rule("1700", "bs.ass.currAss.cashEquiv.cryptoAssets"),
		)
		self.assertEqual(
			codes(placed(*rules, balances=books, fiscal_year=WJ_2026)),
			[("BILANZ-NICHT-GUELTIG", "Fehler", "0400"), ("BILANZ-NICHT-GUELTIG", "Fehler", "1700")],
		)
		self.assertEqual(codes(placed(*rules, balances=books)), [])
		self.assertEqual(
			codes(placed(*rules[1:], balances=books[1:], fiscal_year=(date(2027, 1, 1), date(2027, 12, 31)))),
			[],
		)


class EarlierResultTest(TestCase):
	"""The result of earlier fiscal years that no Period Closing Voucher closed goes to the closing account, as a
	Period Closing Voucher would book it there (closing_account_head in erpnext/accounts/doctype/
	period_closing_voucher/period_closing_voucher.py): the Gewinnvortrag or Verlustvortrag (§ 266 Abs. 3 A. IV. HGB)."""

	def test_the_earlier_result_goes_to_the_closing_account_with_a_hint(self):
		placement = placed(
			Rule("1800", BANK),
			Rule("2970", RETAINED),
			balances=[balance("1800", "1300"), balance("2970", credit="1000")],
			earlier_result=Decimal("-300"),
			closing_account="2970",
		)
		self.assertEqual(
			[(item.balance.number, item.amount, item.value) for item in placement.placed],
			[("1800", Decimal("1300"), Decimal("1300")), ("2970", Decimal("-1300"), Decimal("1300"))],
		)
		self.assertEqual(codes(placement), [("BILANZ-ERGEBNISVORTRAG", "Hinweis", "2970")])
		self.assertEqual(placement.findings[0].amount, Decimal("-300"))
		self.assertIn("Gewinn früherer Geschäftsjahre", placement.findings[0].text)

	def test_a_closing_account_without_entries_takes_it_all(self):
		placement = placed(
			Rule("2970", RETAINED), balances=[], earlier_result=Decimal("250"), closing_account="2970"
		)
		((item, part),) = [(item, item.balance.part) for item in placement.placed]
		self.assertEqual(
			(item.balance.number, item.value, part), ("2970", Decimal("-250"), Part.BALANCE_SHEET)
		)
		self.assertIn("Verlust früherer Geschäftsjahre", placement.findings[0].text)

	def test_without_a_closing_account_the_earlier_result_is_an_error(self):
		placement = placed(balances=[], earlier_result=Decimal("-300"))
		self.assertEqual(codes(placement), [("BILANZ-ABSCHLUSSKONTO", "Fehler", "")])
		self.assertFalse(placement.ready)

	def test_without_an_earlier_result_the_closing_account_is_as_booked(self):
		placement = placed(
			Rule("2970", RETAINED), balances=[balance("2970", credit="5")], closing_account="2970"
		)
		self.assertEqual(
			([item.amount for item in placement.placed], placement.findings), ([Decimal("-5")], ())
		)


class TaxonomyVersionTest(TestCase):
	def test_a_view_of_another_version_than_the_mapping_names_is_an_error(self):
		"""The positions of one version are not those of another; the mapping has to be moved to the new one first."""
		placement = placed(
			Rule("1800", BANK),
			balances=[balance("1800", "1")],
			taxonomy=replace(positions.view(), version="6.10"),
		)
		self.assertEqual(codes(placement), [("BILANZ-TAXONOMIE", "Fehler", "")])
		self.assertIn("6.9", placement.findings[0].text)
		self.assertIn("6.10", placement.findings[0].text)
		self.assertEqual(len(placement.placed), 1)


class AccountsTest(TestCase):
	"""An entry of the defaults names one account or a range, as the DATEV charts list „Kontenbereiche“."""

	def test_names_one_account_or_a_range_of_accounts(self):
		self.assertEqual((Accounts.of("1800").first, Accounts.of("1800").last), ("1800", "1800"))
		self.assertEqual(Accounts.of("1800-1849"), Accounts("1800", "1849"))
		self.assertEqual(str(Accounts.of("1800-1849")), "1800-1849")
		self.assertEqual(str(Accounts.of("1800")), "1800")

	def test_a_range_holds_its_accounts_of_the_same_length(self):
		accounts = Accounts.of("1800-1849")
		self.assertEqual(
			[number in accounts for number in ("1800", "1825", "1849", "1850", "1799", "18001", "180")],
			[True, True, True, False, False, False, False],
		)

	def test_refuses_what_is_no_account_or_range(self):
		for text in ("", "18a0", "1849-1800", "180-1849", "1800 - 1849", "1800-", "-1849", "1800-1849-1899"):
			with self.subTest(text=text), self.assertRaises(ValueError):
				Accounts.of(text)


class DefaultsTest(TestCase):
	def setUp(self):
		self.defaults = Defaults(
			"SKR04",
			"6.9",
			rules=(
				DefaultRule("1800-1849", BANK, opposite=BANK_LIABILITY),
				DefaultRule("1200", RECEIVABLES, remaining_term=RemainingTerm.UP_TO_ONE_YEAR),
				DefaultRule("3150", BANK_LIABILITY, remaining_term="up to one year", shareholder=False),
			),
			watched=(DefaultWatched("1460", WatchLevel.HINT),),
			excluded=(DefaultExcluded("9000-9009", "Saldenvorträge der Klasse 9"),),
		)

	def test_gives_each_account_of_a_company_the_place_of_the_entry_that_holds_it(self):
		self.assertEqual(
			self.defaults.for_accounts(["9001", "1810", "1200", "3150", "1460", "4400"]),
			Mapping(
				"SKR04",
				rules=(
					Rule("1200", RECEIVABLES, remaining_term=RemainingTerm.UP_TO_ONE_YEAR),
					Rule("1810", BANK, opposite=BANK_LIABILITY),
					Rule("3150", BANK_LIABILITY, remaining_term=RemainingTerm.UP_TO_ONE_YEAR),
				),
				watched=(Watched("1460", WatchLevel.HINT),),
				excluded=(Excluded("9001", "Saldenvorträge der Klasse 9"),),
				taxonomy_version="6.9",
			),
		)

	def test_a_watched_account_keeps_the_level_the_company_gave_it(self):
		"""As Vorgaben laden of the VAT Return Mapping keeps it (steuerbote/mapping_sync.py)."""
		(watched,) = self.defaults.for_accounts(["1460"], levels={"1460": WatchLevel.BLOCKING}).watched
		self.assertEqual(watched.level, WatchLevel.BLOCKING)

	def test_names_the_accounts_of_a_company_no_entry_holds(self):
		self.assertEqual(self.defaults.uncovered(["4400", "1810", "0027", "9009"]), ("0027", "4400"))
		self.assertEqual(self.defaults.covers("1849"), True)
		self.assertEqual(self.defaults.covers("1850"), False)

	def test_entries_do_not_overlap(self):
		with self.assertRaisesRegex(ValueError, "1800-1849 and 1810"):
			Defaults(
				"SKR04", "6.9", rules=(DefaultRule("1800-1849", BANK),), watched=(DefaultWatched("1810"),)
			)

	def test_every_entry_holds_a_valid_place(self):
		with self.assertRaises(MappingError):
			DefaultRule("1800", "")
		with self.assertRaises(MappingError):
			DefaultExcluded("9000", "")
		with self.assertRaises(MappingError):
			DefaultWatched("1460", "sperrt")
		with self.assertRaises(MappingError):
			Defaults("SKR04", "6.8")

	def test_a_default_rule_carries_its_netting_group_to_every_account(self):
		defaults = Defaults(
			"SKR03",
			FIRST.version,
			rules=(DefaultRule("1570-1579", OTHER_ASSETS, TAX_LIABILITY, netting="Umsatzsteuer"),),
		)
		(rule,) = defaults.for_accounts(["1576"]).rules
		self.assertEqual(rule, Rule("1576", OTHER_ASSETS, TAX_LIABILITY, netting="Umsatzsteuer"))
		self.assertEqual(defaults.rows()["rules"][0]["netting"], "Umsatzsteuer")

	def test_the_rows_of_the_defaults_read_as_plain_data(self):
		self.assertEqual(
			self.defaults.rows(),
			{
				"rules": [
					{
						"accounts": "1800-1849",
						"concept": BANK,
						"opposite": BANK_LIABILITY,
						"purpose": "both",
						"shareholder": False,
						"remaining_term": None,
					},
					{
						"accounts": "1200",
						"concept": RECEIVABLES,
						"opposite": None,
						"purpose": "both",
						"shareholder": False,
						"remaining_term": "up to one year",
					},
					{
						"accounts": "3150",
						"concept": BANK_LIABILITY,
						"opposite": None,
						"purpose": "both",
						"shareholder": False,
						"remaining_term": "up to one year",
					},
				],
				"watched": [{"accounts": "1460", "level": "hint"}],
				"excluded": [{"accounts": "9000-9009", "reason": "Saldenvorträge der Klasse 9"}],
			},
		)
