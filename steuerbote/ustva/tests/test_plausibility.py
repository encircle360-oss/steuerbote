from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva import KENNZAHLEN, Period
from steuerbote.ustva.calculation import AccountBalance, DerivedBase
from steuerbote.ustva.defaults import SKR03
from steuerbote.ustva.plausibility import (
	DEFAULT_CONFIRMATION_AGE,
	EU_MEMBER_STATES,
	RESIDENCE_CODES,
	SEVERITIES,
	VAT_ID_CODES,
	VAT_ID_KENNZAHLEN,
	Code,
	EarlierPeriod,
	Hint,
	InvoiceLine,
	LatestConfirmation,
	Severity,
	compare,
	comparison_hints,
	confirmable,
	derived_base_hints,
	hints,
	invoice_hints,
	member_state,
	merged,
	purchase_accounts,
	reconciliation_hints,
	residence_hints,
	sales_accounts,
	vat_id_hints,
	watched_account_hints,
)
from steuerbote.ustva.residence import Finding, Problem
from steuerbote.vatid.result import Outcome


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

	def test_a_name_that_ends_with_a_full_stop_closes_the_sentence(self):
		(hint,) = invoice_hints([invoice("8125", "500", country=None, party="Muster B.V.")], SKR03, FIGURES)
		self.assertTrue(hint.text.endswith("des Kunden Muster B.V."))
		self.assertFalse(hint.text.endswith(".."))

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


REVERSE_CHARGE_19 = "Umsatzsteuer nach § 13b UStG 19 %"


def derived(voucher: str | None, base: str, tax: str, accounts: tuple[str, ...] = ()) -> DerivedBase:
	return DerivedBase(REVERSE_CHARGE_19, voucher, "84", d("19"), d(tax), d(base), accounts)


class DerivedBaseReconciliationTest(TestCase):
	def test_a_base_derived_from_a_voucher_is_no_difference_to_the_invoices(self):
		"""The invoices count the accounts of a Kennzahl's rules; a derived base sits on none of them."""
		lines = [invoice("3125", "300", voucher_type="Purchase Invoice")]
		ledger = {"84": d("1300")}
		found = reconciliation_hints(
			lines, ledger, SKR03, FIGURES, derived=(derived("V1", "1000.00", "190.00", ("4980",)),)
		)
		self.assertEqual(found, [])
		self.assertEqual(
			codes(reconciliation_hints(lines, ledger, SKR03, FIGURES)), [Code.INVOICES_AND_LEDGER]
		)


class DerivedBaseHintsTest(TestCase):
	"""A base taken from the tax, because the lines of the voucher did not show it, is named for a check."""

	def test_names_the_voucher_the_tax_the_rate_and_the_base(self):
		(hint,) = derived_base_hints([derived("Journal Entry:ACC-JV-2026-00012", "63.05", "11.98")], FIGURES)
		self.assertEqual((hint.code, hint.severity), (Code.BASE_FROM_TAX, Severity.HINT))
		self.assertEqual(
			hint.text,
			"Kz 84: Der Beleg bucht 11,98 € Steuer auf „Umsatzsteuer nach § 13b UStG 19 %“, aber nichts auf ein "
			"Grundlagenkonto, und seine übrigen Buchungszeilen ergeben die Bemessungsgrundlage nicht eindeutig. "
			"Steuerbote hat sie aus der Steuer zurückgerechnet (11,98 € zu 19,0 %) und meldet 63,05 €; "
			"bitte prüfe sie am Beleg.",
		)
		self.assertEqual(
			(hint.voucher_type, hint.voucher_no, hint.party), ("Journal Entry", "ACC-JV-2026-00012", "")
		)

	def test_lines_without_voucher(self):
		(hint,) = derived_base_hints([derived(None, "1000.00", "190.00")], FIGURES)
		self.assertTrue(hint.text.startswith("Kz 84: Die Buchungen ohne Beleg buchen 190,00 € Steuer"))
		self.assertEqual((hint.voucher_type, hint.voucher_no), ("", ""))

	def test_a_base_read_from_the_lines_of_its_voucher_gets_no_hint(self):
		self.assertEqual(derived_base_hints([derived("V1", "1000.00", "190.00", ("4980",))], FIGURES), [])

	def test_the_hints_follow_the_order_given(self):
		found = derived_base_hints(
			[derived("Journal Entry:B", "1.00", "0.19"), derived("Journal Entry:A", "2.00", "0.38")], FIGURES
		)
		self.assertEqual([hint.voucher_no for hint in found], ["B", "A"])

	def test_hints_name_them_after_the_watched_accounts(self):
		comparison = compare(
			{},
			EarlierPeriod(Period.month(2026, 10), {}),
			EarlierPeriod(Period.month(2025, 11), {}),
			KENNZAHLEN,
			report_rule,
		)
		found = hints(
			comparison,
			[],
			{"84": d("63.05")},
			SKR03,
			FIGURES,
			watched=(AccountBalance("8605", d("0"), d("80")),),
			derived=(derived("Journal Entry:J1", "63.05", "11.98"),),
		)
		self.assertEqual(codes(found), [Code.WATCHED_ACCOUNT, Code.BASE_FROM_TAX])


class ResidenceHintsTest(TestCase):
	"""The decisions on the suppliers of sections C and D, as the person who files reads them."""

	def hint(
		self, problem: Problem, *facts: str, supplier: str = "Harbor Analytics Inc.", kennzahl: str = "84"
	):
		alternative = "46" if kennzahl == "84" else "84"
		finding = Finding(problem, "Purchase Invoice:PI-7", supplier, facts, kennzahl, alternative)
		(found,) = residence_hints([finding])
		self.assertEqual(
			(found.voucher_type, found.voucher_no, found.party), ("Purchase Invoice", "PI-7", supplier)
		)
		return found

	def test_a_voucher_without_supplier(self):
		finding = Finding(Problem.NO_SUPPLIER, "Journal Entry:J-3", kennzahl="84", alternative="46")
		(hint,) = residence_hints([finding])
		self.assertEqual((hint.code, hint.severity), (Code.RESIDENCE_OPEN, Severity.HINT))
		self.assertEqual((hint.voucher_type, hint.voucher_no, hint.party), ("Journal Entry", "J-3", ""))
		self.assertEqual(
			hint.text,
			"Kz 84: Der Beleg bucht Steuer nach § 13b UStG ohne Grundlagenkonto und nennt keinen Lieferanten; "
			"Steuerbote meldet die Bemessungsgrundlage in Kz 84, der Vorgabe der Verprobung. Ist es eine sonstige "
			"Leistung nach § 3a Abs. 2 UStG eines im übrigen Gemeinschaftsgebiet ansässigen Unternehmers, gehört sie "
			"in Kz 46: Ordne den Beleg oder den Lieferanten in der Kontenzuordnung unter „Einordnung nach § 13b UStG“ "
			"ein.",
		)

	def test_suppliers_in_different_places(self):
		hint = self.hint(
			Problem.SUPPLIERS_DISAGREE,
			"Vltava Software s.r.o.",
			"other member state",
			"Harbor Analytics Inc.",
			"third country",
		)
		self.assertEqual(hint.code, Code.RESIDENCE_OPEN)
		self.assertEqual(
			hint.text,
			"Kz 84: Die Lieferanten des Belegs sind an verschiedenen Orten ansässig (Vltava Software s.r.o. im "
			"übrigen Gemeinschaftsgebiet, Harbor Analytics Inc. im Drittlandsgebiet); Steuerbote meldet die "
			"Bemessungsgrundlage in Kz 84. Ordne den Beleg oder den Lieferanten in der Kontenzuordnung unter "
			"„Einordnung nach § 13b UStG“ ein.",
		)

	def test_a_supplier_without_country(self):
		hint = self.hint(Problem.NO_COUNTRY, supplier="Nebula Tools LLC")
		self.assertEqual(hint.code, Code.RESIDENCE_OPEN)
		self.assertEqual(
			hint.text,
			"Kz 84: Beim Lieferanten Nebula Tools LLC ist weder ein Land noch eine Anschrift mit Land gepflegt. "
			"Steuerbote meldet die Bemessungsgrundlage in Kz 84. Pflege das Land des Lieferanten, oder ordne den "
			"Beleg oder den Lieferanten in der Kontenzuordnung unter „Einordnung nach § 13b UStG“ ein.",
		)
		with_prefix = self.hint(Problem.NO_COUNTRY, "IE", supplier="Nebula Tools LLC")
		self.assertIn(
			"gepflegt; seine USt-IdNr. beginnt mit IE, das zeigt aber nur eine Registrierung. Steuerbote",
			with_prefix.text,
		)

	def test_an_address_elsewhere(self):
		hint = self.hint(Problem.ADDRESS_ELSEWHERE, "United States", "Ireland")
		self.assertEqual((hint.code, hint.severity), (Code.RESIDENCE_CONFLICT, Severity.HINT))
		self.assertEqual(
			hint.text,
			"Kz 84: Beim Lieferanten Harbor Analytics Inc. steht als Land United States, seine Anschrift liegt aber "
			"in Ireland. Steuerbote folgt dem Land; bitte prüfe, wo der Lieferant ansässig ist.",
		)

	def test_a_vat_id_of_another_place(self):
		hint = self.hint(Problem.VAT_ID_PREFIX, "United States", "IE")
		self.assertEqual(hint.code, Code.RESIDENCE_CONFLICT)
		self.assertEqual(
			hint.text,
			"Kz 84: Der Lieferant Harbor Analytics Inc. hat das Land United States, seine USt-IdNr. beginnt aber mit "
			"IE. Steuerbote folgt dem Land, denn ansässig ist ein Unternehmer, wo er Sitz, Geschäftsleitung oder eine "
			"Betriebsstätte hat (§ 13b Abs. 7 UStG), nicht wo er registriert ist; bitte prüfe den Sitz am Beleg.",
		)

	def test_a_template_of_another_reverse_charge_for_a_supplier_of_a_member_state(self):
		hint = self.hint(
			Problem.TEMPLATE_OTHER_FROM_MEMBER_STATE, "Reverse Charge", supplier="Liffey Cloud Ltd"
		)
		self.assertEqual(hint.code, Code.RESIDENCE_CONFLICT)
		self.assertEqual(
			hint.text,
			"Kz 84: Die Steuervorlage Reverse Charge ist als andere Leistung nach § 13b Abs. 2 UStG eingeordnet, der "
			"Lieferant Liffey Cloud Ltd ist aber im übrigen Gemeinschaftsgebiet ansässig. Ist es eine sonstige "
			"Leistung nach § 3a Abs. 2 UStG, gehört sie in Kz 46: Ordne den Beleg oder den Lieferanten in der "
			"Kontenzuordnung unter „Einordnung nach § 13b UStG“ ein.",
		)

	def test_an_eu_service_stated_for_a_supplier_outside_the_member_states(self):
		hint = self.hint(Problem.STATED_EU_SERVICE_OUTSIDE, "supplier", "third country", kennzahl="46")
		self.assertEqual((hint.code, hint.severity), (Code.EU_SERVICE_OUTSIDE, Severity.WARNING))
		self.assertEqual(
			hint.text,
			"Kz 46: Der Lieferant ist als sonstige Leistung aus dem übrigen Gemeinschaftsgebiet eingeordnet, der "
			"Lieferant Harbor Analytics Inc. ist laut Stammdaten aber im Drittlandsgebiet ansässig. Kz 46 setzt einen "
			"im übrigen Gemeinschaftsgebiet ansässigen Unternehmer voraus (§ 13b Abs. 1 UStG); bitte prüfe die "
			"Einordnung.",
		)
		for source, start in (
			("voucher", "Der Beleg ist"),
			("tax template", "Die Steuervorlage des Belegs ist"),
		):
			with self.subTest(source=source):
				hint = self.hint(Problem.STATED_EU_SERVICE_OUTSIDE, source, "domestic", kennzahl="46")
				self.assertTrue(hint.text.startswith(f"Kz 46: {start} als sonstige Leistung"))
				self.assertIn("laut Stammdaten aber im Inland ansässig", hint.text)

	def test_a_base_account_of_kz_46_for_a_supplier_outside_the_member_states(self):
		hint = self.hint(Problem.EU_SERVICE_ACCOUNT_OUTSIDE, "country", "third country", kennzahl="46")
		self.assertEqual((hint.code, hint.severity), (Code.EU_SERVICE_OUTSIDE, Severity.WARNING))
		self.assertEqual(
			hint.text,
			"Kz 46: Der Beleg bucht auf ein Grundlagenkonto von Kz 46, der Lieferant Harbor Analytics Inc. ist laut "
			"Stammdaten aber im Drittlandsgebiet ansässig. Kz 46 nimmt nur sonstige Leistungen nach § 3a Abs. 2 UStG "
			"eines im übrigen Gemeinschaftsgebiet ansässigen Unternehmers auf (§ 13b Abs. 1 UStG), alle anderen "
			"gehören in Kz 84.",
		)
		stated = self.hint(
			Problem.EU_SERVICE_ACCOUNT_OUTSIDE, "supplier", "other member state", kennzahl="46"
		)
		self.assertIn(
			"Harbor Analytics Inc. ist aber als andere Leistung nach § 13b Abs. 2 UStG eingeordnet.",
			stated.text,
		)
		addressed = self.hint(Problem.EU_SERVICE_ACCOUNT_OUTSIDE, "address", "domestic", kennzahl="46")
		self.assertIn("laut Stammdaten aber im Inland ansässig", addressed.text)

	def test_an_acquisition_from_a_supplier_of_the_drittlandsgebiet(self):
		hint = self.hint(Problem.ACQUISITION_OUTSIDE_EU, "United States", kennzahl="")
		self.assertEqual((hint.code, hint.severity), (Code.ACQUISITION_OUTSIDE_EU, Severity.WARNING))
		self.assertEqual(
			hint.text,
			"Der Beleg bucht Umsatzsteuer aus innergemeinschaftlichem Erwerb, der Lieferant Harbor Analytics Inc. ist "
			"laut Stammdaten aber im Drittlandsgebiet ansässig (United States). Ein innergemeinschaftlicher Erwerb "
			"setzt voraus, dass der Gegenstand aus einem anderen Mitgliedstaat kommt (§ 1a Abs. 1 Nr. 1 UStG); kommt "
			"er aus dem Drittlandsgebiet, ist es eine Einfuhr. Bitte prüfe den Beleg.",
		)

	def test_every_problem_has_a_code(self):
		self.assertEqual(set(RESIDENCE_CODES), set(Problem))

	def test_hints_put_them_after_the_bases_from_the_tax_and_the_warnings_first(self):
		comparison = compare(
			{},
			EarlierPeriod(Period.month(2026, 10), {}),
			EarlierPeriod(Period.month(2025, 11), {}),
			KENNZAHLEN,
			report_rule,
		)
		findings = (
			Finding(Problem.NO_SUPPLIER, "Journal Entry:J1", kennzahl="84", alternative="46"),
			Finding(Problem.ACQUISITION_OUTSIDE_EU, "Purchase Invoice:P1", "Harbor Analytics Inc.", ("US",)),
		)
		found = hints(
			comparison,
			[],
			{"84": d("63.05")},
			SKR03,
			FIGURES,
			derived=(derived("Journal Entry:J1", "63.05", "11.98"),),
			findings=findings,
		)
		self.assertEqual(codes(found), [Code.ACQUISITION_OUTSIDE_EU, Code.BASE_FROM_TAX, Code.RESIDENCE_OPEN])


class WatchedAccountHintsTest(TestCase):
	"""A balance on an account watched for a hint is named with its debits and credits and holds nothing."""

	def test_names_the_account_its_debits_credits_and_balance(self):
		(hint,) = watched_account_hints(
			[AccountBalance("8603", d("0"), d("250"))], {"8603": "Sonstige betriebliche Erträge"}, FIGURES
		)
		self.assertEqual((hint.code, hint.severity), (Code.WATCHED_ACCOUNT, Severity.HINT))
		self.assertEqual(
			hint.text,
			"Konto 8603 Sonstige betriebliche Erträge hat einen Saldo von 250,00 € im Haben "
			"(Soll 0,00 €, Haben 250,00 €), geht aber in keine Kennzahl ein.",
		)
		self.assertEqual((hint.voucher_type, hint.voucher_no, hint.party), ("", "", ""))

	def test_a_debit_balance_of_an_account_without_a_name(self):
		(hint,) = watched_account_hints([AccountBalance("2166", d("1053.11"), d("12.00"))], {}, FIGURES)
		self.assertEqual(
			hint.text,
			"Konto 2166 hat einen Saldo von 1.041,11 € im Soll (Soll 1.053,11 €, Haben 12,00 €), "
			"geht aber in keine Kennzahl ein.",
		)

	def test_an_account_without_a_balance_gets_no_hint(self):
		self.assertEqual(watched_account_hints([AccountBalance("8603", d("100"), d("100"))], {}, FIGURES), [])

	def test_one_hint_per_account_in_the_order_given(self):
		found = watched_account_hints(
			[AccountBalance("8606", d("0"), d("1")), AccountBalance("8603", d("2"), d("0"))],
			{"8603": "Sonstige betriebliche Erträge"},
			FIGURES,
		)
		self.assertEqual(
			[hint.text.split(" hat ")[0] for hint in found],
			["Konto 8606", "Konto 8603 Sonstige betriebliche Erträge"],
		)


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

	def test_a_period_before_the_start_of_the_books_is_not_compared(self):
		"""Its ledger holds only the opening balances, so the comparison stays empty instead of showing every Kennzahl
		as new."""
		(hint,) = self.hints_for(
			{"81": d("1000")},
			EarlierPeriod(Period.month(2026, 12), None, Code.BEFORE_START),
			EarlierPeriod(Period.month(2026, 1), None, Code.BEFORE_START),
		)
		self.assertEqual((hint.code, hint.severity), (Code.BEFORE_START, Severity.HINT))
		self.assertEqual(
			hint.text,
			"Vor dem Start der Bücher in Steuerbote: Der Vergleich mit Dezember 2026 und Januar 2026 bleibt leer.",
		)

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
			{
				Code.EU_WITHOUT_VAT_ID,
				Code.EU_ADDRESS,
				Code.ZERO_TAX,
				Code.TAX_DEVIATION,
				Code.INPUT_TAX_DEVIATION,
				Code.VAT_ID_INVALID,
				Code.EU_SERVICE_OUTSIDE,
				Code.ACQUISITION_OUTSIDE_EU,
			},
		)

	def test_the_codes_and_severities_are_those_the_return_stores(self):
		self.assertEqual(
			[code.value for code in Code],
			[
				"EU-OHNE-USTID",
				"EU-VORLAGE-ADRESSE",
				"NULLSATZ-OHNE-GRUND",
				"STEUER-ABWEICHUNG",
				"VORSTEUER-ABWEICHUNG",
				"ABGLEICH-RECHNUNGEN",
				"KONTO-BEOBACHTET",
				"ABWEICHUNG-VORPERIODE",
				"KEIN-KATALOG",
				"ZUORDNUNG-JAHRGANG",
				"USTIDNR-UNGEPRUEFT",
				"USTIDNR-VERALTET",
				"USTIDNR-UNGUELTIG",
				"STEUERVORLAGE-OHNE-KENNZAHL",
				"REGISTER-ABWEICHUNG",
				"GRUNDLAGE-AUS-STEUER",
				"VOR-START",
				"SITZ-OFFEN",
				"SITZ-WIDERSPRUCH",
				"KZ46-OHNE-EU-SITZ",
				"ERWERB-AUS-DRITTLAND",
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

	def test_balances_watched_for_a_hint_follow_the_reconciliation_with_the_ledger(self):
		comparison = compare(
			{"81": d("1600"), "21": d("2000")},
			EarlierPeriod(Period.month(2026, 10), {"81": d("1000")}),
			EarlierPeriod(Period.month(2025, 11), None),
			KENNZAHLEN,
			report_rule,
		)
		lines = [invoice("8400", "1600", "0", country="Germany"), invoice("8336", "1500", tax_id=None)]
		found = hints(
			comparison,
			lines,
			{"81": d("1600"), "21": d("2000")},
			SKR03,
			FIGURES,
			watched=(AccountBalance("8605", d("0"), d("80")), AccountBalance("8603", d("0"), d("250"))),
			names={"8603": "Sonstige betriebliche Erträge"},
		)
		self.assertEqual(
			codes(found),
			[
				Code.ZERO_TAX,
				Code.EU_WITHOUT_VAT_ID,
				Code.INVOICES_AND_LEDGER,
				Code.WATCHED_ACCOUNT,
				Code.WATCHED_ACCOUNT,
				Code.PREVIOUS_PERIOD,
				Code.PREVIOUS_PERIOD,
				Code.NO_CATALOGUE,
			],
		)
		self.assertTrue(found[3].text.startswith("Konto 8605 hat einen Saldo von 80,00 € im Haben"))
		self.assertTrue(found[4].text.startswith("Konto 8603 Sonstige betriebliche Erträge hat"))

	def test_invoice_hints_keep_the_order_of_the_lines(self):
		lines = [
			invoice("8336", "1500", tax_id=None),
			invoice("8400", "1600", "0", voucher="ACC-SINV-2026-00002"),
		]
		self.assertEqual(codes(invoice_hints(lines, SKR03, FIGURES)), [Code.EU_WITHOUT_VAT_ID, Code.ZERO_TAX])


OCTOBER = Period.month(2026, 10)
AUSTRIAN = "ATU12345678"
FRENCH = "FR12345678901"
ALPEN = "Alpen Handel GmbH"


@dataclass(frozen=True, slots=True)
class Use:
	"""A voucher behind Kz 41, 42 or 21 as the ledger names its customer, like a VoucherAmount of the ZM."""

	vat_id: str | None
	party: str | None = ALPEN
	kennzahl: str = "41"


def asked(day: str, outcome: Outcome = Outcome.VALID, **validity: date) -> LatestConfirmation:
	return LatestConfirmation(date.fromisoformat(day), outcome, **validity)


def found_for(*uses: Use, latest: dict | None = None, period: Period = OCTOBER, age: int = 90) -> list[Hint]:
	return vat_id_hints(uses, latest or {}, period, age)


class VatIdHintsTest(TestCase):
	"""Kz 41 needs a gültige USt-IdNr. at the time of the supply (§ 6a Absatz 1 Satz 1 Nummer 4 UStG), and the ZM
	names the numbers behind Kz 41, 42 and 21 (§ 18a Absatz 7 Satz 1 UStG). The latest confirmation of each number
	(§ 18e UStG) tells whether the BZSt confirmed it, when, and whether it found it valid."""

	def test_a_number_never_confirmed_is_to_be_checked(self):
		(hint,) = found_for(Use(AUSTRIAN))
		self.assertEqual(
			(hint.code, hint.severity, hint.voucher_type, hint.voucher_no, hint.party),
			(Code.VAT_ID_UNCONFIRMED, Severity.HINT, "", "", ALPEN),
		)
		self.assertEqual(
			hint.text,
			"Die USt-IdNr. ATU12345678 des Kunden Alpen Handel GmbH (Kz 41) ist nicht bestätigt. "
			"„USt-IdNrn. prüfen“ lässt sie beim BZSt bestätigen.",
		)

	def test_a_query_without_an_answer_leaves_the_number_unconfirmed(self):
		(hint,) = found_for(Use(AUSTRIAN), latest={AUSTRIAN: asked("2026-10-20", Outcome.UNKNOWN)})
		self.assertEqual((hint.code, hint.severity), (Code.VAT_ID_UNCONFIRMED, Severity.HINT))
		self.assertEqual(
			hint.text,
			"Die USt-IdNr. ATU12345678 des Kunden Alpen Handel GmbH (Kz 41) ist nicht bestätigt: Die "
			"Bestätigungsabfrage vom 20. Oktober 2026 ergab kein Ergebnis. „USt-IdNrn. prüfen“ fragt erneut.",
		)

	def test_a_confirmation_up_to_the_age_of_the_settings_needs_no_hint(self):
		self.assertEqual((date(2026, 10, 31) - date(2026, 8, 2)).days, 90)
		self.assertEqual(found_for(Use(AUSTRIAN), latest={AUSTRIAN: asked("2026-08-02")}), [])
		self.assertEqual(found_for(Use(AUSTRIAN), latest={AUSTRIAN: asked("2026-10-31")}, age=0), [])

	def test_an_older_confirmation_is_out_of_date(self):
		(hint,) = found_for(Use(AUSTRIAN), latest={AUSTRIAN: asked("2026-08-01")})
		self.assertEqual((hint.code, hint.severity, hint.party), (Code.VAT_ID_STALE, Severity.HINT, ALPEN))
		self.assertEqual(
			hint.text,
			"Die USt-IdNr. ATU12345678 des Kunden Alpen Handel GmbH (Kz 41) ist zuletzt am 1. August 2026 "
			"bestätigt worden, 91 Tage vor dem Ende des Voranmeldungszeitraums Oktober 2026; die Einstellungen "
			"lassen höchstens 90 Tage zu. „USt-IdNrn. prüfen“ fragt erneut.",
		)

	def test_the_age_counts_to_the_end_of_the_period_whatever_its_length(self):
		quarter = Period.quarter(2026, 3)
		(hint,) = found_for(Use(AUSTRIAN), latest={AUSTRIAN: asked("2026-06-15")}, period=quarter, age=60)
		self.assertIn(
			"107 Tage vor dem Ende des Voranmeldungszeitraums III. Kalendervierteljahr 2026; die Einstellungen "
			"lassen höchstens 60 Tage zu.",
			hint.text,
		)
		self.assertEqual(found_for(Use(AUSTRIAN), latest={AUSTRIAN: asked("2026-07-02")}, period=quarter), [])

	def test_a_confirmation_after_the_end_of_the_period_is_current(self):
		self.assertEqual(found_for(Use(AUSTRIAN), latest={AUSTRIAN: asked("2026-11-20")}, age=0), [])

	def test_an_invalid_number_is_a_warning_that_names_the_day_of_its_query(self):
		(hint,) = found_for(
			Use(FRENCH, "Paris Services SA", "21"), latest={FRENCH: asked("2026-11-20", Outcome.INVALID)}
		)
		self.assertEqual(
			(hint.code, hint.severity, hint.party),
			(Code.VAT_ID_INVALID, Severity.WARNING, "Paris Services SA"),
		)
		self.assertEqual(
			hint.text,
			"Die USt-IdNr. FR12345678901 des Kunden Paris Services SA (Kz 21) ist laut Bestätigungsabfrage vom "
			"20. November 2026 ungültig.",
		)

	def test_a_number_valid_all_through_the_period_counts_as_confirmed_for_it(self):
		"""evatr-2006 names the time a number was valid, evatr-2002 the day from which it is."""
		lost_after = asked(
			"2026-11-20", Outcome.INVALID, valid_from=date(2019, 1, 1), valid_until=date(2026, 11, 15)
		)
		self.assertEqual(found_for(Use(AUSTRIAN), latest={AUSTRIAN: lost_after}), [])
		valid_from_september = asked("2026-08-15", Outcome.INVALID, valid_from=date(2026, 9, 1))
		self.assertEqual(found_for(Use(AUSTRIAN), latest={AUSTRIAN: valid_from_september}), [])
		(stale,) = found_for(Use(AUSTRIAN), latest={AUSTRIAN: valid_from_september}, age=30)
		self.assertEqual(stale.code, Code.VAT_ID_STALE)
		lost_within = asked("2026-11-20", Outcome.INVALID, valid_until=date(2026, 10, 15))
		(invalid,) = found_for(Use(AUSTRIAN), latest={AUSTRIAN: lost_within})
		self.assertEqual(invalid.code, Code.VAT_ID_INVALID)

	def test_a_number_the_bzst_cannot_confirm_is_a_warning_with_the_reason(self):
		cases = {
			"DE123456789": "Das BZSt bestätigt Unternehmern USt-IdNrn., die ein anderer Mitgliedstaat erteilt hat, "
			"keine deutschen (§ 18e Nr. 1 UStG).",
			"GB123456789": "USt-IdNrn. mit GB lassen sich seit dem 1. Januar 2021 nicht mehr bestätigen; "
			"Unternehmen in Nordirland haben eine USt-IdNr. mit XI.",
			"ATU 12": "Eine USt-IdNr. hat 7 bis 14 Zeichen, ATU12 hat 5.",
		}
		for vat_id, reason in cases.items():
			with self.subTest(vat_id=vat_id):
				(hint,) = found_for(Use(vat_id), latest={AUSTRIAN: asked("2026-10-20")})
				self.assertEqual((hint.code, hint.severity), (Code.VAT_ID_INVALID, Severity.WARNING))
				self.assertEqual(
					hint.text,
					f"Die USt-IdNr. „{vat_id}“ des Kunden Alpen Handel GmbH (Kz 41) lässt sich nicht "
					f"bestätigen: {reason}",
				)

	def test_one_hint_per_number_that_names_its_kennzahlen_in_the_order_of_the_form(self):
		uses = (
			Use(AUSTRIAN, kennzahl="21"),
			Use("atu 123 456 78", "Alpen Handel GmbH Wien", "41"),
			Use(AUSTRIAN, kennzahl="42"),
			Use(AUSTRIAN, kennzahl="41"),
		)
		(hint,) = found_for(*uses)
		self.assertEqual(hint.party, ALPEN)
		self.assertTrue(
			hint.text.startswith("Die USt-IdNr. ATU12345678 des Kunden Alpen Handel GmbH (Kz 41, 42 und 21) ")
		)
		(both,) = found_for(Use(AUSTRIAN, kennzahl="42"), Use(AUSTRIAN, kennzahl="21"))
		self.assertIn("(Kz 42 und 21)", both.text)

	def test_the_numbers_follow_each_other_in_order(self):
		found = found_for(
			Use(FRENCH, "Paris Services SA", "21"),
			Use(AUSTRIAN),
			latest={FRENCH: asked("2026-10-20", Outcome.INVALID)},
		)
		self.assertEqual(
			[(hint.code, hint.party) for hint in found],
			[(Code.VAT_ID_UNCONFIRMED, ALPEN), (Code.VAT_ID_INVALID, "Paris Services SA")],
		)

	def test_the_first_name_a_voucher_gives_names_the_customer(self):
		(hint,) = found_for(
			Use(AUSTRIAN, party=" "), Use(AUSTRIAN, party=None), Use(AUSTRIAN, party="Alpen AG")
		)
		self.assertEqual(hint.party, "Alpen AG")
		(nameless,) = found_for(Use(AUSTRIAN, party=None))
		self.assertEqual(nameless.party, "")
		self.assertTrue(nameless.text.startswith("Die USt-IdNr. ATU12345678 (Kz 41) ist nicht bestätigt."))

	def test_vouchers_without_a_vat_id_and_other_kennzahlen_get_no_hint_here(self):
		"""EU-OHNE-USTID names an invoice of Kz 41 or 21 whose customer has no USt-IdNr."""
		self.assertEqual(found_for(Use(None), Use(" "), Use(AUSTRIAN, kennzahl="81")), [])

	def test_an_age_is_never_below_zero_days(self):
		with self.assertRaisesRegex(ValueError, "not -1 days"):
			found_for(Use(AUSTRIAN), age=-1)

	def test_the_kennzahlen_are_those_of_the_zm_in_the_order_of_the_form(self):
		self.assertEqual(VAT_ID_KENNZAHLEN, ("41", "42", "21"))
		self.assertEqual([number for number in KENNZAHLEN if number in VAT_ID_KENNZAHLEN], ["41", "42", "21"])
		self.assertEqual(VAT_ID_CODES, {Code.VAT_ID_UNCONFIRMED, Code.VAT_ID_STALE, Code.VAT_ID_INVALID})
		self.assertEqual(DEFAULT_CONFIRMATION_AGE, 90)


class ConfirmableTest(TestCase):
	def test_the_numbers_the_bzst_can_confirm_each_once_as_a_confirmation_keeps_them(self):
		uses = (
			Use(FRENCH, kennzahl="21"),
			Use("atu 123 456 78"),
			Use(AUSTRIAN, kennzahl="42"),
			Use("DE123456789"),
			Use("ATU 12"),
			Use(None),
			Use("BE0123456789", kennzahl="81"),
		)
		self.assertEqual(confirmable(uses), [AUSTRIAN, FRENCH])
		self.assertEqual(confirmable(()), [])


class MergedTest(TestCase):
	def test_warnings_come_first_and_each_source_keeps_its_order(self):
		first = (Hint(Code.EU_WITHOUT_VAT_ID, "a"), Hint(Code.INVOICES_AND_LEDGER, "b"))
		second = (Hint(Code.VAT_ID_UNCONFIRMED, "c"), Hint(Code.VAT_ID_INVALID, "d"))
		self.assertEqual([hint.text for hint in merged(first, second)], ["a", "d", "b", "c"])
		self.assertIsInstance(merged(first), tuple)
