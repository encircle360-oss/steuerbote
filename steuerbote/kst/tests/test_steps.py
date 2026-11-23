"""The steps of the computation of the Körperschaftsteuer as data: key, label, law, form, line, field, sign, category."""

import re
from unittest import TestCase

from steuerbote.kst.categories import CATEGORIES, Category
from steuerbote.kst.chain import STEPS, Source, Step, step

# The fields rule 8906062 of Jahresdokumentation_E30_2025.ods sums into Anlage GK line 300, with their signs, as far as
# the steps of the chain declare them.
GK_300 = {
	"E8002001": 1,
	"E8002104": 1,
	"E8002105": -1,
	"E8002602": -1,
	"E8002603": 1,
	"E8002604": 1,
	"E8002605": 1,
	"E8002701": 1,
	"E8002709": 1,
	"E8002801": 1,
	"E8100301": 1,
	"E8100501": 1,
	"E8100601": 1,
	"E8100702": 1,
	"E8101001": 1,
	"E8101101": 1,
	"E8101201": 1,
	"E8101301": 1,
	"E8101401": 1,
	"E8003301": -1,
	"E8003401": -1,
	"E8003601": -1,
	"E8003701": -1,
	"E8562101": 1,
	"E8011302": 1,
}
# Rule 8956047: the fields of line 201.
GK_201 = {
	"E8560401": -1,
	"E8560801": 1,
	"E8561212": -1,
	"E8561410": 1,
	"E8561220": -1,
	"E8561301": 1,
	"E8561411": 1,
}


def fields_of(total: str) -> dict[str, int]:
	return {s.field: s.sign for s in STEPS if s.total == total and s.field is not None}


class StepsTest(TestCase):
	def test_every_step_has_a_key_of_its_own_a_label_and_a_law(self):
		keys = [s.key for s in STEPS]
		self.assertEqual(len(keys), len(set(keys)))
		for item in STEPS:
			with self.subTest(step=item.key):
				self.assertRegex(item.key, r"^[a-z][a-z0-9_]*$")
				self.assertTrue(item.label)
				self.assertRegex(item.law, r"§ \d+")
				self.assertIn(item.sign, (1, -1))

	def test_follows_the_order_of_r_7_1_kstr_from_the_jahresueberschuss_to_the_abschlusszahlung(self):
		keys = [s.key for s in STEPS]
		for earlier, later in (
			("net_income", "corporate_tax"),
			("corporate_tax", "p8b_total"),
			("p8b_total", "business_income"),
			("business_income", "sum_of_income"),
			("sum_of_income", "donation_deduction"),
			("donation_deduction", "total_income"),
			("total_income", "loss_deduction"),
			("loss_deduction", "zve"),
			("zve", "corporate_income_tax"),
			("corporate_income_tax", "kst_balance"),
			("kst_balance", "solz"),
			("solz", "solz_balance"),
		):
			with self.subTest(earlier=earlier, later=later):
				self.assertLess(keys.index(earlier), keys.index(later))

	def test_the_lines_of_anlage_gk_feed_line_300_with_the_signs_of_rule_8906062(self):
		self.assertEqual(fields_of("business_income"), GK_300)

	def test_the_lines_of_paragraph_8b_feed_line_201_with_the_signs_of_rule_8956047(self):
		self.assertEqual(fields_of("p8b_total"), GK_201)

	def test_the_totals_of_anlage_zve(self):
		self.assertEqual(fields_of("sum_of_income"), {"E8004904": 1, "E8004201": -1})
		self.assertEqual(fields_of("total_income"), {"E8005401": 1, "E8005601": -1})
		self.assertEqual(fields_of("zve"), {"E8006901": 1, "E8007001": -1})

	def test_names_the_lines_of_the_forms(self):
		for key, form, line, field in (
			("net_income", "GK", "11", "E8002001"),
			("derivatives_loss", "GK", "51", "E8002104"),
			("p8b_gains", "GK", "166b", "E8561212"),
			("business_income", "GK", "300", "E8109901"),
			("business_income_zve", "ZVE", "2", "E8004904"),
			("sum_of_income", "ZVE", "32", "E8005401"),
			("donation_deduction", "ZVE", "34", "E8005601"),
			("total_income", "ZVE", "53", "E8006901"),
			("loss_deduction", "ZVE", "56", "E8007001"),
			("zve", "ZVE", "70", "E8007501"),
			("corporate_income_tax", "ZVE", "71", "E8007502"),
			("capital_gains_tax_credit", "WA", "2", "E8120401"),
			("solz_credit", "WA", "3", "E8120601"),
		):
			with self.subTest(key=key):
				self.assertEqual((step(key).form, step(key).line, step(key).field), (form, line, field))

	def test_the_steps_beyond_the_declaration_have_no_field(self):
		for key in (
			"kst_remaining",
			"kst_prepayments",
			"kst_balance",
			"solz",
			"solz_remaining",
			"solz_balance",
		):
			with self.subTest(key=key):
				self.assertEqual((step(key).form, step(key).field), ("", None))

	def test_every_category_of_the_koerperschaftsteuer_feeds_one_step(self):
		fed = [category for s in STEPS if s.source is not Source.COMPUTED for category in s.categories]
		self.assertEqual(len(fed), len(set(fed)))
		gewst_only = {c for c, info in CATEGORIES.items() if "GewStG" in info.law and "KStG" not in info.law}
		self.assertEqual(
			set(Category) - set(fed) - gewst_only,
			{
				Category.ENTERTAINMENT_DEDUCTIBLE,
				Category.DIVIDENDS,
				Category.SHARE_GAIN,
				Category.SHARE_LOSS,
				Category.SHARE_WRITEDOWN,
				Category.SHARE_WRITEUP,
				Category.SHARE_SALE_COSTS,
				Category.DERIVATIVES_GAIN,
				Category.DERIVATIVES_LOSS,
				Category.TRADING_UNCLASSIFIED,
			},
		)

	def test_the_computed_steps_name_the_categories_whose_postings_stand_behind_them(self):
		self.assertEqual(step("p8b_dividends").categories, (Category.DIVIDENDS,))
		self.assertEqual(
			step("derivatives_loss").categories, (Category.DERIVATIVES_GAIN, Category.DERIVATIVES_LOSS)
		)
		self.assertEqual(step("investment_funds").categories, (Category.FUNDS,))

	def test_marks_the_steps_steuerbote_computes_later(self):
		self.assertEqual(
			{s.key for s in STEPS if s.source is Source.LATER}, {"investment_funds", "foreign_tax_deduction"}
		)

	def test_the_steps_with_manual_lines_only(self):
		self.assertEqual(
			{s.key for s in STEPS if s.source is Source.MANUAL},
			{
				"iab_addback_3",
				"iab_addback_2",
				"hidden_distributions",
				"profit_participation_rights",
				"contributions_not_booked",
				"contributions_paid",
				"contributions_unpaid",
			},
		)

	def test_finds_a_step_by_its_key(self):
		self.assertIsInstance(step("zve"), Step)
		with self.assertRaisesRegex(KeyError, "no step 'zvE'"):
			step("zvE")

	def test_the_labels_follow_the_forms_in_german(self):
		self.assertEqual(step("business_income").label, "Einkünfte aus Gewerbebetrieb")
		self.assertEqual(step("zve").label, "Zu versteuerndes Einkommen")
		for item in STEPS:
			with self.subTest(step=item.key):
				self.assertIsNone(re.search(r"\b(the|and|of)\b", item.label))
