"""Which line of the annual return each account feeds."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.ustjahr.form import CATALOGUES
from steuerbote.ustjahr.split import (
	ANNUAL_CHECKED,
	ANNUAL_MAPPED,
	ANNUAL_TWICE,
	MESSAGES,
	NO_DEFAULT,
	NO_PARAGRAPH,
	NO_RULE,
	NOT_A_LINE,
	NOT_FED,
	TWO_CHOICES,
	UNKNOWN_FIELD,
	AnnualRule,
	Assignment,
	Choice,
	How,
	SplitError,
	split,
)
from steuerbote.ustva.defaults import SKR03
from steuerbote.ustva.mapping import AccountRule, Mapping, Side, TaxCheck

RATE_19 = Decimal("19")
MAPPING = Mapping(
	"test",
	(
		AccountRule("8400", "81", Side.CREDIT),
		AccountRule("8910", "81", Side.CREDIT),
		AccountRule("2406", "81", Side.CREDIT, also_kennzahl="50", also_side=Side.DEBIT),
		AccountRule("8300", "86", Side.CREDIT),
		AccountRule("8125", "41", Side.CREDIT),
		AccountRule("8120", "43", Side.CREDIT),
		AccountRule("8100", "48", Side.CREDIT),
		AccountRule("3123", "46", Side.DEBIT, RATE_19),
		AccountRule("1576", "66", Side.DEBIT),
		AccountRule("1558", "64", Side.DEBIT),
		AccountRule("1559", "64", Side.DEBIT),
		AccountRule("1782", "65", Side.CREDIT),
	),
	checks=(TaxCheck("Umsatzsteuer 19 %", ("8400", "8910", "2406"), ("1776",)),),
	watched=("1769",),
	year=2026,
)
SECTION_15A = {"1558": "E3008701", "1559": "E3008702"}


def failure(caught: SplitError) -> tuple[str, tuple[object, ...]]:
	return caught.template, caught.values


class OrderTest(TestCase):
	"""The annual field of the rule, else the default of the role of the account, else the default line."""

	def test_an_account_takes_the_default_line_of_its_kennzahl(self):
		result = split(MAPPING, role_defaults=SECTION_15A)
		self.assertEqual(
			result.assignment("8400"), Assignment("8400", "E3003303", How.DEFAULT, kennzahl="81")
		)
		self.assertEqual(result.field_of("8120"), "E3103902")
		self.assertEqual(result.field_of("8100"), "E3104502")
		self.assertEqual(result.field_of("1782"), "E3005901")
		self.assertEqual(result.field_of("1576"), "E3006201")

	def test_a_kennzahl_with_one_line_gives_every_account_that_line(self):
		result = split(MAPPING, role_defaults=SECTION_15A)
		self.assertEqual(result.field_of("8125"), "E3103301")
		self.assertEqual(result.field_of("3123"), "E3102205")
		self.assertIs(result.assignment("8125").how, How.DEFAULT)

	def test_the_default_of_the_role_comes_before_the_default_line(self):
		result = split(MAPPING, role_defaults={**SECTION_15A, "8910": "E3003405"})
		self.assertEqual(result.assignment("8910"), Assignment("8910", "E3003405", How.ROLE, kennzahl="81"))

	def test_the_annual_field_of_the_rule_comes_first(self):
		result = split(MAPPING, (Choice("8910", "E3003505"),), {**SECTION_15A, "8910": "E3003405"})
		self.assertEqual(result.assignment("8910"), Assignment("8910", "E3003505", How.RULE, kennzahl="81"))

	def test_a_choice_without_a_field_leaves_the_line_to_the_role(self):
		result = split(MAPPING, (Choice("8910"),), {**SECTION_15A, "8910": "E3003405"})
		self.assertIs(result.assignment("8910").how, How.ROLE)

	def test_the_default_of_a_role_the_kennzahl_does_not_take_is_left_aside(self):
		"""A company that mapped the account to another Kennzahl than its role suggests keeps its Kennzahl."""
		result = split(MAPPING, role_defaults={**SECTION_15A, "8400": "E3004401", "8300": "E9999999"})
		self.assertEqual(
			result.assignment("8400"), Assignment("8400", "E3003303", How.DEFAULT, kennzahl="81")
		)
		self.assertEqual(result.field_of("8300"), "E3004401")

	def test_kz_64_takes_the_line_of_its_role(self):
		result = split(MAPPING, role_defaults=SECTION_15A)
		self.assertEqual(result.field_of("1558"), "E3008701")
		self.assertEqual(result.field_of("1559"), "E3008702")

	def test_an_unmapped_account_feeds_no_line(self):
		result = split(MAPPING, role_defaults=SECTION_15A)
		self.assertIsNone(result.field_of("1776"))
		self.assertIsNone(result.assignment("1769"))

	def test_lists_the_accounts_of_a_line(self):
		result = split(MAPPING, (Choice("8910", "E3003405"),), SECTION_15A)
		self.assertEqual(result.accounts("E3003303"), ("8400", "2406"))
		self.assertEqual(result.accounts("E3003405"), ("8910",))
		self.assertEqual(result.accounts("E3003304"), ())

	def test_takes_the_catalogue_of_the_year_of_the_mapping(self):
		self.assertIs(split(MAPPING, role_defaults=SECTION_15A).catalogue, CATALOGUES[2026])

	def test_the_defaults_of_skr03_split_with_the_lines_of_section_15a(self):
		roles = {
			"1558": "E3008701",
			"1559": "E3008702",
			"1556": "E3008801",
			"1557": "E3008802",
			"1528": "E3008803",
			"1529": "E3008804",
		}
		result = split(SKR03.for_year(2026), role_defaults=roles)
		self.assertEqual(len(result.assignments), len(SKR03.rules))
		for rule in SKR03.rules:
			with self.subTest(account=rule.account_number):
				field = result.catalogue.field(result.field_of(rule.account_number))
				self.assertEqual(field.ustva, rule.kennzahl)


class ValidationTest(TestCase):
	"""A line must take the amounts of the Kennzahl of the rule, so the lines of a Kennzahl add up to it."""

	def test_refuses_an_annual_field_the_kennzahl_does_not_take(self):
		with self.assertRaises(SplitError) as caught:
			split(MAPPING, (Choice("8400", "E3004401"),), SECTION_15A)
		self.assertEqual(failure(caught.exception), (NOT_A_LINE, ("8400", "81", "E3004401", 27)))
		self.assertEqual(
			str(caught.exception),
			"Account 8400 feeds Kennzahl 81 of the Voranmeldung, which field E3004401 in line 27 does not take.",
		)

	def test_refuses_a_computed_field_as_annual_field(self):
		with self.assertRaises(SplitError) as caught:
			split(MAPPING, (Choice("8400", "E3003304"),), SECTION_15A)
		self.assertEqual(failure(caught.exception), (NOT_A_LINE, ("8400", "81", "E3003304", 24)))

	def test_refuses_a_field_the_form_does_not_have(self):
		with self.assertRaises(SplitError) as caught:
			split(MAPPING, (Choice("8400", "E9999999"),), SECTION_15A)
		self.assertEqual(failure(caught.exception), (UNKNOWN_FIELD, (2026, "E9999999")))
		self.assertEqual(str(caught.exception), "Form USt 2 A 2026 has no field E9999999.")

	def test_kz_64_needs_an_annual_field(self):
		with self.assertRaises(SplitError) as caught:
			split(MAPPING, role_defaults={"1559": "E3008702"})
		self.assertEqual(failure(caught.exception), (NO_DEFAULT, ("1558", "64")))
		self.assertEqual(
			str(caught.exception),
			"Account 1558 feeds Kennzahl 64 of the Voranmeldung, which splits into lines without a default: "
			"choose its annual field.",
		)

	def test_refuses_a_choice_for_an_account_without_a_rule(self):
		with self.assertRaises(SplitError) as caught:
			split(MAPPING, (Choice("1776", "E3003303"),), SECTION_15A)
		self.assertEqual(failure(caught.exception), (NO_RULE, ("1776",)))

	def test_refuses_two_choices_for_one_account(self):
		with self.assertRaises(SplitError) as caught:
			split(MAPPING, (Choice("8910", "E3003405"), Choice("8910", "E3003505")), SECTION_15A)
		self.assertEqual(failure(caught.exception), (TWO_CHOICES, ("8910",)))


class ParagraphTest(TestCase):
	"""Lines 46, 52 and 54 name the paragraph of their sales: „Umsätze nach § … UStG“ (form USt 2 A 2026)."""

	def test_an_account_of_such_a_line_keeps_the_paragraph_of_its_rule(self):
		result = split(MAPPING, (Choice("8100", "E3104502", " 4 Nummer 14 "),), SECTION_15A)
		self.assertEqual(
			result.assignment("8100"),
			Assignment("8100", "E3104502", How.RULE, kennzahl="48", paragraph="4 Nummer 14"),
		)

	def test_a_blank_paragraph_is_none(self):
		result = split(MAPPING, (Choice("8120", None, "  "),), SECTION_15A)
		self.assertIsNone(result.assignment("8120").paragraph)

	def test_refuses_a_paragraph_for_a_line_that_names_none(self):
		with self.assertRaises(SplitError) as caught:
			split(MAPPING, (Choice("8400", None, "4 Nummer 1"),), SECTION_15A)
		self.assertEqual(failure(caught.exception), (NO_PARAGRAPH, ("8400", "E3003303", 24)))
		self.assertEqual(
			str(caught.exception), "Field E3003303 in line 24 names no paragraph, so account 8400 gives none."
		)


class AnnualRuleTest(TestCase):
	"""Accounts that only the annual return reads, „Zuordnung nur für die Umsatzsteuererklärung“."""

	def test_an_annual_rule_feeds_its_field(self):
		rule = AnnualRule("3552", "E3100801", Side.DEBIT)
		result = split(MAPPING, role_defaults=SECTION_15A, annual_rules=(rule,))
		self.assertEqual(
			result.assignment("3552"), Assignment("3552", "E3100801", How.ANNUAL, side=Side.DEBIT)
		)
		self.assertEqual(result.annual_rules, (rule,))

	def test_a_watched_account_may_feed_a_line_of_the_annual_return(self):
		result = split(
			MAPPING, role_defaults=SECTION_15A, annual_rules=(AnnualRule("1769", "E3102805", Side.CREDIT),)
		)
		self.assertEqual(result.field_of("1769"), "E3102805")

	def test_an_annual_rule_keeps_its_paragraph(self):
		result = split(
			MAPPING,
			role_defaults=SECTION_15A,
			annual_rules=(AnnualRule("8193", "E3104902", Side.CREDIT, "4 Nummer 9 Buchstabe a"),),
		)
		self.assertEqual(result.assignment("8193").paragraph, "4 Nummer 9 Buchstabe a")

	def test_refuses_an_annual_rule_for_a_mapped_account(self):
		with self.assertRaises(SplitError) as caught:
			split(
				MAPPING,
				role_defaults=SECTION_15A,
				annual_rules=(AnnualRule("8400", "E3100801", Side.CREDIT),),
			)
		self.assertEqual(failure(caught.exception), (ANNUAL_MAPPED, ("8400", "81")))

	def test_refuses_an_annual_rule_for_a_tax_account_of_the_verprobung(self):
		with self.assertRaises(SplitError) as caught:
			split(
				MAPPING,
				role_defaults=SECTION_15A,
				annual_rules=(AnnualRule("1776", "E3102805", Side.CREDIT),),
			)
		self.assertEqual(failure(caught.exception), (ANNUAL_CHECKED, ("1776", "Umsatzsteuer 19 %")))

	def test_refuses_two_annual_rules_for_one_account(self):
		rules = (AnnualRule("3552", "E3100801", Side.DEBIT), AnnualRule("3552", "E3101701", Side.DEBIT))
		with self.assertRaises(SplitError) as caught:
			split(MAPPING, role_defaults=SECTION_15A, annual_rules=rules)
		self.assertEqual(failure(caught.exception), (ANNUAL_TWICE, ("3552",)))

	def test_refuses_a_field_no_account_feeds(self):
		for element, line in (
			("E3003304", 24),
			("E3006001", 41),
			("E3000901", 5),
			("E3011301", 125),
			("E3005401", 37),
		):
			with self.subTest(element=element), self.assertRaises(SplitError) as caught:
				split(
					MAPPING,
					role_defaults=SECTION_15A,
					annual_rules=(AnnualRule("3552", element, Side.DEBIT),),
				)
			self.assertEqual(failure(caught.exception), (NOT_FED, ("3552", element, line)))

	def test_refuses_a_field_the_form_does_not_have(self):
		with self.assertRaises(SplitError) as caught:
			split(
				MAPPING, role_defaults=SECTION_15A, annual_rules=(AnnualRule("3552", "E9999999", Side.DEBIT),)
			)
		self.assertEqual(failure(caught.exception), (UNKNOWN_FIELD, (2026, "E9999999")))

	def test_refuses_a_paragraph_for_a_line_that_names_none(self):
		with self.assertRaises(SplitError) as caught:
			split(
				MAPPING,
				role_defaults=SECTION_15A,
				annual_rules=(AnnualRule("3552", "E3100801", Side.DEBIT, "25b"),),
			)
		self.assertEqual(failure(caught.exception), (NO_PARAGRAPH, ("3552", "E3100801", 55)))

	def test_an_annual_rule_names_an_account_and_a_side(self):
		with self.assertRaisesRegex(ValueError, "' 3552' is not an account number"):
			AnnualRule(" 3552", "E3100801", Side.DEBIT)
		self.assertIs(AnnualRule("3552", "E3100801", "debit").side, Side.DEBIT)  # type: ignore[arg-type]
		with self.assertRaisesRegex(ValueError, "'3552 ' is not an account number"):
			Choice("3552 ")


class MessagesTest(TestCase):
	def test_lists_every_template_once_for_the_translations(self):
		self.assertEqual(
			MESSAGES,
			(
				UNKNOWN_FIELD,
				NO_RULE,
				TWO_CHOICES,
				NOT_A_LINE,
				NO_DEFAULT,
				NO_PARAGRAPH,
				ANNUAL_MAPPED,
				ANNUAL_CHECKED,
				ANNUAL_TWICE,
				NOT_FED,
			),
		)
		self.assertEqual(len(set(MESSAGES)), len(MESSAGES))

	def test_an_error_keeps_template_and_values_apart(self):
		error = SplitError(NO_RULE, "1776")
		self.assertEqual(
			(error.template, error.values, str(error)), (NO_RULE, ("1776",), NO_RULE.format("1776"))
		)
		self.assertIsInstance(error, ValueError)
