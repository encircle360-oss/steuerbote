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
	Purpose,
	Rule,
	Watched,
)
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
