from unittest import TestCase

from steuerbote.setup.chart import SIGNATURES, SKR03, SKR04, Basis, Detection, detect
from steuerbote.ustva.tests.fixtures import datev_2026, erpnext_v16

# The names of ERPNext's own templates (erpnext/accounts/doctype/account/chart_of_accounts/verified, version 16).
ERPNEXT_SKR03 = "SKR03 mit Kontonummern"
ERPNEXT_SKR04 = "SKR04 mit Kontonummern"


class TemplateTest(TestCase):
	def test_the_templates_of_erpnext_name_their_chart(self):
		self.assertEqual(detect(ERPNEXT_SKR03, ()), Detection(SKR03, Basis.TEMPLATE))
		self.assertEqual(detect(ERPNEXT_SKR04, ()), Detection(SKR04, Basis.TEMPLATE))

	def test_a_template_names_the_chart_with_or_without_blank_and_zero(self):
		for name, chart in (
			("SKR 03", SKR03),
			("skr04 DATEV", SKR04),
			("Kontenrahmen SKR3", SKR03),
			("SKR 4", SKR04),
		):
			with self.subTest(name=name):
				self.assertEqual(detect(name, ()), Detection(chart, Basis.TEMPLATE))

	def test_the_template_decides_before_the_accounts(self):
		self.assertEqual(detect(ERPNEXT_SKR04, SIGNATURES[SKR03]), Detection(SKR04, Basis.TEMPLATE))

	def test_a_template_that_names_both_charts_is_ambiguous(self):
		self.assertEqual(detect("SKR03 und SKR04", SIGNATURES[SKR03]), Detection(None, Basis.AMBIGUOUS))

	def test_another_template_leaves_it_to_the_accounts(self):
		for name in (None, "", "Standard", "Standard with Numbers", "SKR030", "PSKR03"):
			with self.subTest(name=name):
				self.assertEqual(detect(name, SIGNATURES[SKR04]), Detection(SKR04, Basis.ACCOUNTS))


class AccountsTest(TestCase):
	def test_the_signatures_are_erloese_umsatzsteuer_and_vorsteuer_at_19_percent(self):
		self.assertEqual(SIGNATURES, {SKR03: {"8400", "1776", "1576"}, SKR04: {"4400", "3806", "1406"}})

	def test_the_accounts_of_the_erpnext_templates_tell_their_chart(self):
		self.assertEqual(detect(None, erpnext_v16.SKR03_VAT_ACCOUNTS), Detection(SKR03, Basis.ACCOUNTS))
		self.assertEqual(detect(None, erpnext_v16.SKR04_VAT_ACCOUNTS), Detection(SKR04, Basis.ACCOUNTS))

	def test_the_accounts_of_the_datev_charts_tell_their_chart(self):
		self.assertEqual(detect(None, datev_2026.SKR03_VAT_ACCOUNTS), Detection(SKR03, Basis.ACCOUNTS))
		self.assertEqual(detect(None, datev_2026.SKR04_VAT_ACCOUNTS), Detection(SKR04, Basis.ACCOUNTS))

	def test_one_account_of_the_signature_missing_tells_nothing(self):
		self.assertEqual(detect(None, {"8400", "1776", "1200"}), Detection(None, Basis.NONE))

	def test_accounts_without_a_signature_are_a_chart_of_their_own(self):
		self.assertEqual(detect(None, ()), Detection(None, Basis.NONE))
		self.assertEqual(detect(None, ["100", "200", "300"]), Detection(None, Basis.NONE))

	def test_the_signatures_of_both_charts_are_ambiguous(self):
		self.assertEqual(
			detect(None, SIGNATURES[SKR03] | SIGNATURES[SKR04]), Detection(None, Basis.AMBIGUOUS)
		)
