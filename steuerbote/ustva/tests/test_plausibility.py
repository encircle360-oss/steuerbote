from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva import KENNZAHLEN, Period
from steuerbote.ustva.defaults import SKR03
from steuerbote.ustva.plausibility import (
	EU_MEMBER_STATES,
	SEVERITIES,
	Code,
	EarlierPeriod,
	InvoiceLine,
	Severity,
	compare,
	comparison_hints,
	hints,
	invoice_hints,
	member_state,
	purchase_accounts,
	reconciliation_hints,
	sales_accounts,
)


def d(value: str) -> Decimal:
	return Decimal(value)


class GermanFigures:
	"""The figures as a site with the number format #.###,## shows them."""

	def money(self, amount: Decimal) -> str:
		digits = f"{amount:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
		return f"{digits} €"

	def percent(self, value: Decimal) -> str:
		return f"{value:.1f}".replace(".", ",") + " %"


FIGURES = GermanFigures()


def report_rule(current: Decimal, previous: Decimal) -> bool:
	"""A rule as the report UStVA Kennzahlen applies it with its default thresholds: a change of more than
	100 euros and of more than 50 % of the previous amount, any change from zero exceeding every share."""
	change = abs(current - previous)
	return change > d("100") and change * 100 > d("50") * abs(previous)


def invoice(
	account: str,
	net: str,
	tax: str = "0",
	*,
	voucher: str = "ACC-SINV-2026-00001",
	party: str = "Muster GmbH",
	country: str | None = "Austria",
	tax_id: str | None = "ATU12345678",
	voucher_type: str = "Sales Invoice",
	is_return: bool = False,
) -> InvoiceLine:
	return InvoiceLine(
		voucher_type=voucher_type,
		voucher_no=voucher,
		posting_date=date(2026, 11, 5),
		party=party,
		party_country=country,
		party_tax_id=tax_id,
		account_number=account,
		net_amount=d(net),
		tax_amount=d(tax),
		is_return=is_return,
	)


def codes(found) -> list[str]:
	return [hint.code for hint in found]


class MemberStatesTest(TestCase):
	def test_lists_the_27_member_states_of_2026(self):
		self.assertEqual(len(EU_MEMBER_STATES), 27)
		self.assertEqual(len({state.code for state in EU_MEMBER_STATES}), 27)
		self.assertEqual(len({state.country for state in EU_MEMBER_STATES}), 27)
		self.assertNotIn("GB", {state.code for state in EU_MEMBER_STATES})

	def test_finds_a_member_state_by_its_code_or_by_the_name_erpnext_gives_the_country(self):
		for country in ("AT", "at", "Austria", " austria "):
			with self.subTest(country=country):
				state = member_state(country)
				self.assertIsNotNone(state)
				assert state is not None
				self.assertEqual((state.code, state.german), ("AT", "Österreich"))
		self.assertEqual(member_state("Czech Republic").code, "CZ")
		self.assertEqual(member_state("Greece").code, "GR")

	def test_monaco_counts_as_part_of_france(self):
		self.assertEqual(member_state("Monaco").code, "FR")
		self.assertEqual(member_state("MC").code, "FR")

	def test_a_country_outside_the_eu_is_no_member_state(self):
		for country in ("Switzerland", "United Kingdom", "GB", "Norway", "", "  ", None):
			with self.subTest(country=country):
				self.assertIsNone(member_state(country))


class InvoiceLineTest(TestCase):
	def test_amounts_are_cents_as_decimal(self):
		with self.assertRaises(TypeError):
			InvoiceLine("Sales Invoice", "S-1", date(2026, 11, 5), "P", None, None, "8400", 100.0, d("0"))  # type: ignore[arg-type]
		with self.assertRaisesRegex(ValueError, "finite cents"):
			invoice("8400", "100.001")

	def test_the_account_number_is_one_a_rule_could_match(self):
		with self.assertRaisesRegex(ValueError, "not an account number"):
			invoice(" 8400", "100")

	def test_an_invoice_is_no_return_unless_said(self):
		line = InvoiceLine("Sales Invoice", "S-1", date(2026, 11, 5), "P", None, None, "8400", d("1"), d("0"))
		self.assertFalse(line.is_return)


class AccountsTest(TestCase):
	def test_sales_accounts_feed_the_kennzahlen_the_hints_look_at(self):
		accounts = sales_accounts(SKR03)
		for number in ("8400", "8300", "8125", "8336", "8338"):
			with self.subTest(account=number):
				self.assertIn(number, accounts)
		for number in ("3123", "1776", "1576", "8100"):
			with self.subTest(account=number):
				self.assertNotIn(number, accounts)

	def test_purchase_accounts_are_those_of_section_13b(self):
		accounts = purchase_accounts(SKR03)
		self.assertIn("3123", accounts)
		self.assertIn("3125", accounts)
		self.assertNotIn("8400", accounts)
		self.assertNotIn("1576", accounts)


class EuHintsTest(TestCase):
	def test_an_eu_service_to_a_customer_without_vat_id(self):
		(hint,) = invoice_hints([invoice("8336", "2000", tax_id=None)], SKR03, FIGURES)
		self.assertEqual(
			(hint.code, hint.severity, hint.voucher_type, hint.voucher_no, hint.party),
			(Code.EU_WITHOUT_VAT_ID, Severity.WARNING, "Sales Invoice", "ACC-SINV-2026-00001", "Muster GmbH"),
		)
		self.assertEqual(
			hint.text,
			"Rechnung ACC-SINV-2026-00001 über 2.000,00 € geht in Kz 21 ein, "
			"aber der Kunde Muster GmbH hat keine USt-IdNr.",
		)

	def test_a_blank_vat_id_is_no_vat_id(self):
		self.assertEqual(
			codes(invoice_hints([invoice("8125", "500", tax_id="  ")], SKR03, FIGURES)),
			[Code.EU_WITHOUT_VAT_ID],
		)

	def test_an_eu_delivery_to_a_german_address(self):
		(hint,) = invoice_hints(
			[invoice("8125", "500", country="Germany", tax_id="DE123456789")], SKR03, FIGURES
		)
		self.assertEqual((hint.code, hint.severity), (Code.EU_ADDRESS, Severity.WARNING))
		self.assertEqual(
			hint.text,
			"Rechnung ACC-SINV-2026-00001 über 500,00 € geht in Kz 41 ein, "
			"aber die Anschrift des Kunden Muster GmbH liegt in Deutschland.",
		)

	def test_an_eu_service_to_an_address_outside_the_eu(self):
		(hint,) = invoice_hints(
			[invoice("8336", "750", country="Switzerland", tax_id="CHE-123")], SKR03, FIGURES
		)
		self.assertEqual(hint.code, Code.EU_ADDRESS)
		self.assertTrue(hint.text.endswith("liegt außerhalb der EU (Switzerland)."), hint.text)

	def test_an_eu_delivery_without_an_address(self):
		(hint,) = invoice_hints([invoice("8125", "500", country=None)], SKR03, FIGURES)
		self.assertEqual(hint.code, Code.EU_ADDRESS)
		self.assertTrue(hint.text.endswith("aber die Rechnung nennt keine Anschrift des Kunden Muster GmbH."))

	def test_a_customer_in_another_member_state_with_vat_id_gets_no_hint(self):
		self.assertEqual(invoice_hints([invoice("8125", "500"), invoice("8336", "100")], SKR03, FIGURES), [])

	def test_a_line_can_lack_both_the_vat_id_and_the_address(self):
		found = invoice_hints([invoice("8125", "500", country="Germany", tax_id=None)], SKR03, FIGURES)
		self.assertEqual(codes(found), [Code.EU_WITHOUT_VAT_ID, Code.EU_ADDRESS])

	def test_an_invoice_gets_one_hint_per_kennzahl_with_its_total(self):
		lines = [
			invoice("8125", "500", tax_id=None),
			invoice("8125", "250", tax_id=None),
			invoice("8336", "100", tax_id=None),
			invoice("8125", "40", tax_id=None, voucher="ACC-SINV-2026-00002"),
		]
		found = invoice_hints(lines, SKR03, FIGURES)
		self.assertEqual(
			[(hint.voucher_no, hint.text.split(" geht")[0]) for hint in found],
			[
				("ACC-SINV-2026-00001", "Rechnung ACC-SINV-2026-00001 über 750,00 €"),
				("ACC-SINV-2026-00001", "Rechnung ACC-SINV-2026-00001 über 100,00 €"),
				("ACC-SINV-2026-00002", "Rechnung ACC-SINV-2026-00002 über 40,00 €"),
			],
		)

	def test_a_credit_note_is_named_as_such(self):
		(hint,) = invoice_hints(
			[invoice("8125", "-500", tax_id=None, voucher="ACC-SINV-RET-2026-00001", is_return=True)],
			SKR03,
			FIGURES,
		)
		self.assertTrue(
			hint.text.startswith("Gutschrift ACC-SINV-RET-2026-00001 über -500,00 € geht in Kz 41")
		)

	def test_other_kennzahlen_and_unmapped_accounts_get_no_eu_hint(self):
		lines = [invoice("8338", "500", country="Germany", tax_id=None), invoice("9999", "10", tax_id=None)]
		self.assertEqual(invoice_hints(lines, SKR03, FIGURES), [])


class TaxHintsTest(TestCase):
	def test_a_taxable_revenue_without_tax(self):
		(hint,) = invoice_hints([invoice("8400", "1000", "0", country="Germany")], SKR03, FIGURES)
		self.assertEqual((hint.code, hint.severity), (Code.ZERO_TAX, Severity.WARNING))
		self.assertEqual(
			hint.text,
			"Rechnung ACC-SINV-2026-00001 an Muster GmbH bucht 1.000,00 € auf Konto 8400 (Kz 81) ohne Umsatzsteuer.",
		)
		self.assertEqual((hint.voucher_no, hint.party), ("ACC-SINV-2026-00001", "Muster GmbH"))

	def test_a_line_without_amount_and_tax_gets_no_hint(self):
		self.assertEqual(invoice_hints([invoice("8400", "0", "0")], SKR03, FIGURES), [])

	def test_tax_that_deviates_from_the_rate_of_the_kennzahl(self):
		(hint,) = invoice_hints([invoice("8400", "1000", "180")], SKR03, FIGURES)
		self.assertEqual((hint.code, hint.severity), (Code.TAX_DEVIATION, Severity.WARNING))
		self.assertEqual(
			hint.text,
			"Rechnung ACC-SINV-2026-00001 an Muster GmbH berechnet für 1.000,00 € auf Konto 8400 (Kz 81) "
			"180,00 € Umsatzsteuer, 19 % wären 190,00 €.",
		)

	def test_one_cent_per_line_is_tolerated(self):
		self.assertEqual(invoice_hints([invoice("8400", "1000", "190.01")], SKR03, FIGURES), [])
		self.assertEqual(invoice_hints([invoice("8400", "33.33", "6.34")], SKR03, FIGURES), [])
		self.assertEqual(
			codes(invoice_hints([invoice("8400", "1000", "190.02")], SKR03, FIGURES)), [Code.TAX_DEVIATION]
		)

	def test_the_reduced_rate_of_kz_86(self):
		self.assertEqual(invoice_hints([invoice("8300", "100", "7")], SKR03, FIGURES), [])
		(hint,) = invoice_hints([invoice("8300", "100", "19")], SKR03, FIGURES)
		self.assertTrue(hint.text.endswith("(Kz 86) 19,00 € Umsatzsteuer, 7 % wären 7,00 €."), hint.text)

	def test_a_credit_note_carries_negative_tax(self):
		self.assertEqual(
			invoice_hints([invoice("8400", "-1000", "-190", is_return=True)], SKR03, FIGURES), []
		)
		(hint,) = invoice_hints([invoice("8400", "-1000", "0", is_return=True)], SKR03, FIGURES)
		self.assertTrue(
			hint.text.startswith("Gutschrift ACC-SINV-2026-00001 an Muster GmbH bucht -1.000,00 €")
		)

	def test_tax_without_a_base_deviates(self):
		self.assertEqual(
			codes(invoice_hints([invoice("8400", "0", "19")], SKR03, FIGURES)), [Code.TAX_DEVIATION]
		)

	def test_lines_of_other_kennzahlen_are_not_checked_for_tax(self):
		self.assertEqual(
			invoice_hints([invoice("8338", "500", "0"), invoice("3123", "300", "0")], SKR03, FIGURES), []
		)


class ReconciliationTest(TestCase):
	def test_invoices_that_match_the_ledger_give_no_hint(self):
		lines = [
			invoice("8400", "1000", "190"),
			invoice("8336", "2000"),
			invoice("3123", "300", voucher_type="Purchase Invoice"),
		]
		ledger = {"81": d("1000"), "21": d("2000"), "46": d("300"), "47": d("57"), "83": d("190")}
		self.assertEqual(reconciliation_hints(lines, ledger, SKR03, FIGURES), [])

	def test_a_difference_of_more_than_one_euro(self):
		(hint,) = reconciliation_hints([invoice("8400", "800", "152")], {"81": d("1000")}, SKR03, FIGURES)
		self.assertEqual((hint.code, hint.severity), (Code.INVOICES_AND_LEDGER, Severity.HINT))
		self.assertEqual(
			hint.text, "Kz 81: Die Rechnungen des Zeitraums ergeben netto 800,00 €, das Hauptbuch 1.000,00 €."
		)
		self.assertEqual((hint.voucher_type, hint.voucher_no, hint.party), ("", "", ""))

	def test_one_euro_is_tolerated(self):
		self.assertEqual(
			reconciliation_hints([invoice("8400", "999")], {"81": d("1000")}, SKR03, FIGURES), []
		)
		self.assertEqual(
			codes(reconciliation_hints([invoice("8400", "998.99")], {"81": d("1000")}, SKR03, FIGURES)),
			[Code.INVOICES_AND_LEDGER],
		)

	def test_a_ledger_amount_without_invoices(self):
		(hint,) = reconciliation_hints([], {"45": d("500")}, SKR03, FIGURES)
		self.assertEqual(
			hint.text, "Kz 45: Die Rechnungen des Zeitraums ergeben netto 0,00 €, das Hauptbuch 500,00 €."
		)

	def test_invoices_without_a_ledger_amount(self):
		(hint,) = reconciliation_hints(
			[invoice("3125", "100", voucher_type="Purchase Invoice")], {}, SKR03, FIGURES
		)
		self.assertEqual(
			hint.text, "Kz 84: Die Rechnungen des Zeitraums ergeben netto 100,00 €, das Hauptbuch 0,00 €."
		)

	def test_only_the_bases_of_invoices_are_reconciled(self):
		ledger = {"66": d("95"), "47": d("57"), "83": d("-95"), "48": d("700")}
		self.assertEqual(reconciliation_hints([invoice("9999", "10")], ledger, SKR03, FIGURES), [])

	def test_the_hints_follow_the_order_of_the_form(self):
		found = reconciliation_hints(
			[], {"21": d("2000"), "81": d("1000"), "84": d("50"), "86": d("30")}, SKR03, FIGURES
		)
		self.assertEqual([hint.text[:5] for hint in found], ["Kz 81", "Kz 86", "Kz 84", "Kz 21"])


class CompareTest(TestCase):
	def setUp(self):
		self.october = EarlierPeriod(
			Period.month(2026, 10), {"81": d("1000"), "45": d("500"), "83": d("190")}
		)
		self.last_november = EarlierPeriod(Period.month(2025, 11), None)
		self.current = {"81": d("1200"), "21": d("2000"), "83": d("228.00")}

	def comparison(self, rule=report_rule):
		return compare(self.current, self.october, self.last_november, KENNZAHLEN, rule)

	def row(self, comparison, kennzahl: str):
		return next(row for row in comparison.rows if row.kennzahl == kennzahl)

	def test_a_row_per_kennzahl_of_any_of_the_periods_in_the_order_of_the_form(self):
		self.assertEqual([row.kennzahl for row in self.comparison().rows], ["81", "21", "45", "83"])

	def test_a_row_compares_the_filed_amount_with_the_earlier_periods(self):
		row = self.row(self.comparison(), "81")
		self.assertEqual(
			(row.label, row.current, row.previous_period, row.previous_year),
			(KENNZAHLEN["81"].label, d("1200"), d("1000"), None),
		)
		self.assertEqual((row.difference, row.difference_percent, row.flagged), (d("200"), d("20.00"), False))

	def test_a_kennzahl_of_the_earlier_period_alone_compares_with_zero(self):
		row = self.row(self.comparison(), "45")
		self.assertEqual(
			(row.current, row.previous_period, row.difference, row.difference_percent, row.flagged),
			(d("0"), d("500"), d("-500"), d("-100.00"), True),
		)

	def test_a_kennzahl_new_in_this_period_has_a_difference_but_no_share(self):
		row = self.row(self.comparison(), "21")
		self.assertEqual(
			(row.previous_period, row.difference, row.difference_percent, row.flagged),
			(d("0"), d("2000"), None, True),
		)

	def test_the_rule_decides_what_is_flagged_from_the_current_and_the_previous_amount(self):
		asked = []

		def rule(current, previous):
			asked.append((current, previous))
			return current < previous

		comparison = self.comparison(rule)
		self.assertEqual([row.kennzahl for row in comparison.rows if row.flagged], ["45"])
		self.assertEqual(
			asked,
			[(d("1200"), d("1000")), (d("2000"), d("0")), (d("0"), d("500")), (d("228.00"), d("190"))],
		)

	def test_the_percentage_is_rounded_to_hundredths(self):
		row = self.row(
			compare(
				{"81": d("1000")},
				EarlierPeriod(Period.month(2026, 10), {"81": d("3000")}),
				self.last_november,
				KENNZAHLEN,
				report_rule,
			),
			"81",
		)
		self.assertEqual(row.difference_percent, d("-66.67"))

	def test_a_period_without_catalogue_leaves_its_values_empty_and_flags_nothing(self):
		january = compare(
			{"81": d("1000"), "83": d("190")},
			EarlierPeriod(Period.month(2025, 12), None),
			EarlierPeriod(Period.month(2025, 1), None),
			KENNZAHLEN,
			report_rule,
		)
		self.assertFalse(january.previous_period.known)
		for row in january.rows:
			with self.subTest(kennzahl=row.kennzahl):
				self.assertEqual(
					(
						row.previous_period,
						row.previous_year,
						row.difference,
						row.difference_percent,
						row.flagged,
					),
					(None, None, None, None, False),
				)

	def test_an_earlier_period_with_values_is_known(self):
		comparison = self.comparison()
		self.assertTrue(comparison.previous_period.known)
		self.assertFalse(comparison.previous_year.known)
		self.assertEqual(comparison.previous_period.value("86"), d("0"))
		self.assertIsNone(comparison.previous_year.value("81"))
		self.assertEqual(comparison.previous_year.missing, Code.NO_CATALOGUE)

	def test_kennzahlen_the_form_of_this_year_does_not_know_are_left_out(self):
		earlier = EarlierPeriod(Period.month(2026, 10), {"99": d("10"), "81": d("1")})
		comparison = compare({"83": d("0")}, earlier, self.last_november, KENNZAHLEN, report_rule)
		self.assertEqual([row.kennzahl for row in comparison.rows], ["81", "83"])


class ComparisonHintsTest(TestCase):
	def hints_for(self, current, earlier, previous_year=None):
		previous_year = previous_year or EarlierPeriod(Period.month(2025, 11), {})
		return comparison_hints(compare(current, earlier, previous_year, KENNZAHLEN, report_rule), FIGURES)

	def test_a_conspicuous_increase(self):
		(hint,) = self.hints_for({"81": d("1600")}, EarlierPeriod(Period.month(2026, 10), {"81": d("1000")}))
		self.assertEqual((hint.code, hint.severity), (Code.PREVIOUS_PERIOD, Severity.HINT))
		self.assertEqual(
			hint.text, "Kz 81 liegt mit 1.600,00 € um 60,0 % über der Vorperiode Oktober 2026 (1.000,00 €)."
		)
		self.assertEqual((hint.voucher_type, hint.voucher_no, hint.party), ("", "", ""))

	def test_a_conspicuous_decrease_of_a_quarter(self):
		(hint,) = self.hints_for(
			{"66": d("0")},
			EarlierPeriod(Period.quarter(2026, 2), {"66": d("400")}),
			EarlierPeriod(Period.quarter(2025, 3), {}),
		)
		self.assertEqual(
			hint.text,
			"Kz 66 liegt mit 0,00 € um 100,0 % unter der Vorperiode II. Kalendervierteljahr 2026 (400,00 €).",
		)

	def test_a_kennzahl_new_in_this_period_is_compared_without_a_share(self):
		(hint,) = self.hints_for({"21": d("2000")}, EarlierPeriod(Period.month(2026, 10), {}))
		self.assertEqual(hint.text, "Kz 21 liegt mit 2.000,00 € über der Vorperiode Oktober 2026 (0,00 €).")

	def test_nothing_conspicuous_gives_no_hint(self):
		self.assertEqual(
			self.hints_for({"81": d("1100")}, EarlierPeriod(Period.month(2026, 10), {"81": d("1000")})), []
		)

	def test_a_year_without_catalogue(self):
		(hint,) = self.hints_for(
			{"81": d("1000")},
			EarlierPeriod(Period.month(2026, 10), {"81": d("1000")}),
			EarlierPeriod(Period.month(2025, 11), None),
		)
		self.assertEqual((hint.code, hint.severity), (Code.NO_CATALOGUE, Severity.HINT))
		self.assertEqual(hint.text, "Kein Katalog für 2025: Der Vergleich mit November 2025 bleibt leer.")

	def test_one_hint_per_year_without_catalogue(self):
		found = self.hints_for(
			{"81": d("1000")},
			EarlierPeriod(Period.month(2025, 12), None),
			EarlierPeriod(Period.month(2025, 1), None),
		)
		self.assertEqual(
			[hint.text for hint in found],
			["Kein Katalog für 2025: Der Vergleich mit Dezember 2025 und Januar 2025 bleibt leer."],
		)
		found = self.hints_for(
			{"81": d("1000")},
			EarlierPeriod(Period.month(2025, 1), None),
			EarlierPeriod(Period.month(2024, 2), None),
		)
		self.assertEqual(
			[hint.text for hint in found],
			[
				"Kein Katalog für 2024: Der Vergleich mit Februar 2024 bleibt leer.",
				"Kein Katalog für 2025: Der Vergleich mit Januar 2025 bleibt leer.",
			],
		)

	def test_a_mapping_that_does_not_fit_the_form_of_a_year(self):
		found = self.hints_for(
			{"81": d("1000")},
			EarlierPeriod(Period.month(2026, 10), None, Code.MAPPING_UNFIT),
			EarlierPeriod(Period.month(2025, 11), None),
		)
		self.assertEqual(
			[(hint.code, hint.severity, hint.text) for hint in found],
			[
				(
					Code.NO_CATALOGUE,
					Severity.HINT,
					"Kein Katalog für 2025: Der Vergleich mit November 2025 bleibt leer.",
				),
				(
					Code.MAPPING_UNFIT,
					Severity.HINT,
					"Die Kontenzuordnung passt nicht zum Vordruck 2026: Der Vergleich mit Oktober 2026 bleibt leer.",
				),
			],
		)


class HintsTest(TestCase):
	def test_every_code_has_a_severity(self):
		self.assertEqual(set(SEVERITIES), set(Code))
		self.assertEqual(
			{code for code, severity in SEVERITIES.items() if severity is Severity.WARNING},
			{Code.EU_WITHOUT_VAT_ID, Code.EU_ADDRESS, Code.ZERO_TAX, Code.TAX_DEVIATION},
		)

	def test_the_codes_and_severities_are_those_the_return_stores(self):
		self.assertEqual(
			[code.value for code in Code],
			[
				"EU-OHNE-USTID",
				"EU-VORLAGE-ADRESSE",
				"NULLSATZ-OHNE-GRUND",
				"STEUER-ABWEICHUNG",
				"ABGLEICH-RECHNUNGEN",
				"ABWEICHUNG-VORPERIODE",
				"KEIN-KATALOG",
				"ZUORDNUNG-JAHRGANG",
			],
		)
		self.assertEqual([severity.value for severity in Severity], ["Hinweis", "Warnung"])

	def test_warnings_come_first_and_each_kind_keeps_its_order(self):
		comparison = compare(
			{"81": d("1600"), "21": d("2000")},
			EarlierPeriod(Period.month(2026, 10), {"81": d("1000")}),
			EarlierPeriod(Period.month(2025, 11), None),
			KENNZAHLEN,
			report_rule,
		)
		lines = [invoice("8400", "1600", "0", country="Germany"), invoice("8336", "1500", tax_id=None)]
		found = hints(comparison, lines, {"81": d("1600"), "21": d("2000")}, SKR03, FIGURES)
		self.assertEqual(
			codes(found),
			[
				Code.ZERO_TAX,
				Code.EU_WITHOUT_VAT_ID,
				Code.INVOICES_AND_LEDGER,
				Code.PREVIOUS_PERIOD,
				Code.PREVIOUS_PERIOD,
				Code.NO_CATALOGUE,
			],
		)
		self.assertIsInstance(found, tuple)

	def test_invoice_hints_keep_the_order_of_the_lines(self):
		lines = [
			invoice("8336", "1500", tax_id=None),
			invoice("8400", "1600", "0", voucher="ACC-SINV-2026-00002"),
		]
		self.assertEqual(codes(invoice_hints(lines, SKR03, FIGURES)), [Code.EU_WITHOUT_VAT_ID, Code.ZERO_TAX])
