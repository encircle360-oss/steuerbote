"""The accounts of the tax templates against the Kontenzuordnung: which have no place, and their hints."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva.calculation import AccountBalance, LedgerLine
from steuerbote.ustva.defaults import SKR03, deliberately_without_kennzahl
from steuerbote.ustva.plausibility import Code, Severity
from steuerbote.ustva.tax_templates import TemplateAccount, balances, hints, without_place
from steuerbote.ustva.tests.test_plausibility import FIGURES


def d(value: str) -> Decimal:
	return Decimal(value)


def account(
	number: str | None, name: str = "Umsatzsteuer 16 %", *templates: str, docname: str | None = None
) -> TemplateAccount:
	return TemplateAccount(
		account=(f"{number} - {name} - STB" if number else f"{name} - STB") if docname is None else docname,
		account_number=number,
		account_name=name,
		templates=templates or ("Inland 16 % - STB",),
	)


OSS = account("1767", "Umsatzsteuer aus im anderen EU-Land steuerpflichtigen Lieferungen", "OSS - STB")
OUTPUT_TAX_19 = account("1776", "Umsatzsteuer 19 %", "Inland 19 % - STB")
INPUT_TAX_19 = account("1576", "Abziehbare Vorsteuer 19 %", "Einkauf Inland - STB")
WATCHED = account("1548", "Vorsteuer im Folgejahr abziehbar", "Einkauf Folgejahr - STB")
WITHOUT_PLACE = account("1775", "Umsatzsteuer 16 %", "Inland 16 % - STB", "Artikel 16 % - STB")
WITHOUT_NUMBER = account(None, "Steuer Sonderfall", "Sonderfall - STB")


class TemplateAccountTest(TestCase):
	def test_an_account_without_number_has_none(self):
		self.assertIsNone(WITHOUT_NUMBER.account_number)

	def test_the_number_is_one_a_rule_could_match(self):
		for number in ("", " 1775", "1775 "):
			with self.subTest(number=number), self.assertRaisesRegex(ValueError, "not an account number"):
				account(number)

	def test_names_the_account_in_erpnext(self):
		with self.assertRaisesRegex(ValueError, "names no account"):
			account("1775", docname="")

	def test_comes_from_at_least_one_template(self):
		with self.assertRaisesRegex(ValueError, "1775 - Umsatzsteuer 16 % - STB is named by no template"):
			TemplateAccount("1775 - Umsatzsteuer 16 % - STB", "1775", "Umsatzsteuer 16 %", ())

	def test_keeps_its_templates_as_a_tuple(self):
		self.assertEqual(
			TemplateAccount("1775 - X - STB", "1775", "X", ["A - STB", "B - STB"]).templates,  # type: ignore[arg-type]
			("A - STB", "B - STB"),
		)


class WithoutPlaceTest(TestCase):
	def test_accounts_the_mapping_maps_checks_or_watches_have_a_place(self):
		self.assertEqual(without_place((OUTPUT_TAX_19, INPUT_TAX_19, WATCHED), SKR03), ())

	def test_an_account_without_rule_check_or_watched_entry_has_none(self):
		self.assertEqual(without_place((OUTPUT_TAX_19, WITHOUT_PLACE), SKR03), (WITHOUT_PLACE,))

	def test_an_account_deliberately_without_kennzahl_is_left_out(self):
		self.assertEqual(without_place((OSS,), SKR03), (OSS,))
		self.assertEqual(without_place((OSS,), SKR03, deliberately_without_kennzahl("SKR03")), ())

	def test_an_account_without_number_never_has_a_place(self):
		self.assertEqual(
			without_place((WITHOUT_NUMBER,), SKR03, deliberately_without_kennzahl("SKR03")), (WITHOUT_NUMBER,)
		)

	def test_keeps_the_order_given(self):
		self.assertEqual(
			without_place((WITHOUT_NUMBER, OUTPUT_TAX_19, WITHOUT_PLACE), SKR03),
			(WITHOUT_NUMBER, WITHOUT_PLACE),
		)


class BalancesTest(TestCase):
	def test_sums_debits_and_credits_of_the_accounts_asked_for(self):
		lines = [
			LedgerLine("1775", credit=d("160.00"), voucher="Sales Invoice:A"),
			LedgerLine("1775", debit=d("16.00"), voucher="Sales Invoice:B"),
			LedgerLine("8400", credit=d("1000.00"), voucher="Sales Invoice:A"),
		]
		self.assertEqual(balances(lines, ["1775"]), {"1775": AccountBalance("1775", d("16.00"), d("160.00"))})

	def test_an_account_without_postings_has_none(self):
		self.assertEqual(balances([], ["1775"]), {})


class HintsTest(TestCase):
	def test_names_the_account_its_templates_and_its_balance(self):
		(hint,) = hints((WITHOUT_PLACE,), {"1775": AccountBalance("1775", d("16.00"), d("160.00"))}, FIGURES)
		self.assertEqual((hint.code, hint.severity), (Code.TAX_TEMPLATE_WITHOUT_PLACE, Severity.HINT))
		self.assertEqual(
			hint.text,
			"Konto 1775 Umsatzsteuer 16 % aus den Steuervorlagen „Inland 16 % - STB“ und „Artikel 16 % - STB“ "
			"hat keinen Platz in der Kontenzuordnung und im Zeitraum einen Saldo von 144,00 € im Haben "
			"(Soll 16,00 €, Haben 160,00 €), der in keine Kennzahl eingeht.",
		)
		self.assertEqual((hint.voucher_type, hint.voucher_no, hint.party), ("", "", ""))

	def test_a_debit_balance(self):
		(hint,) = hints((WITHOUT_PLACE,), {"1775": AccountBalance("1775", d("50.00"), d("0"))}, FIGURES)
		self.assertIn("einen Saldo von 50,00 € im Soll (Soll 50,00 €, Haben 0,00 €)", hint.text)

	def test_says_when_the_account_has_no_balance_in_the_period(self):
		for found in ({}, {"1775": AccountBalance("1775", d("16.00"), d("16.00"))}):
			with self.subTest(balances=found):
				(hint,) = hints((account("1775", "Umsatzsteuer 16 %"),), found, FIGURES)
				self.assertEqual(
					hint.text,
					"Konto 1775 Umsatzsteuer 16 % aus der Steuervorlage „Inland 16 % - STB“ hat keinen Platz in "
					"der Kontenzuordnung; im Zeitraum hat es keinen Saldo.",
				)

	def test_names_three_templates_and_more_in_a_list(self):
		three = account("1775", "Umsatzsteuer 16 %", "A - STB", "B - STB", "C - STB")
		(hint,) = hints((three,), {}, FIGURES)
		self.assertIn("aus den Steuervorlagen „A - STB“, „B - STB“ und „C - STB“ hat", hint.text)

	def test_an_account_without_number_can_have_no_rule(self):
		(hint,) = hints((WITHOUT_NUMBER,), {}, FIGURES)
		self.assertEqual(
			hint.text,
			"Konto Steuer Sonderfall aus der Steuervorlage „Sonderfall - STB“ hat keine Kontonummer, "
			"deshalb kann keine Regel der Kontenzuordnung es zuordnen.",
		)

	def test_one_hint_per_account_in_the_order_given(self):
		found = hints((WITHOUT_NUMBER, WITHOUT_PLACE), {}, FIGURES)
		self.assertEqual(
			[hint.text.split(" aus ")[0] for hint in found],
			["Konto Steuer Sonderfall", "Konto 1775 Umsatzsteuer 16 %"],
		)
