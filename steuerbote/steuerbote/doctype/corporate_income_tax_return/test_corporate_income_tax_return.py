"""The Körperschaftsteuererklärung on the Frappe test site, with the worked example „Muster IT GmbH“ of
steuerbote/tests/income_tax.py: Berechnen from the ledger, the settings and the tables of the return, the lines by hand
and the corrections, each finding that holds the return back, „Bereit“ once the forms of the year are final,
„Rückstellungen vorschlagen“ and the zu versteuerndes Einkommen once the provisions are posted, Prüfen in the
simulation, the filing, the Berichtigung and the print. A second company has no Annual Filing Settings. Every name,
number and amount is invented.
"""

import re
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, getdate

from steuerbote.eric.result import Outcome
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge
from steuerbote.tests import income_tax
from steuerbote.tests.helpers import acknowledge_errors, make_account, make_company, make_user, post_ledger
from steuerbote.tests.income_tax import (
	COMPANY,
	MAPPING,
	SETTINGS,
	YEAR,
	blocking_codes,
	finding_codes,
	hint_codes,
	money,
)
from steuerbote.tests.transmitting import Transmitting

# The companies, their accounts, Fiscal Years, Journal Entries and users are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Account",
	"Company",
	"Corporate Income Tax Return",
	"DocType",
	"Fiscal Year",
	"Journal Entry",
	"User",
]

DOCTYPE = income_tax.CORPORATE
WITHOUT_SETTINGS = "Steuerbote Test KSt ohne Einstellungen GmbH"
FILED_IN_MEIN_ELSTER = "mein_elster"
VGA = "Miete an die Gesellschafterin über dem Marktniveau, Vertrag vom 2. Januar 2026"
REFUND = "Erstattung der Körperschaftsteuer 2025 mit der Vorauszahlung verrechnet"
UEBERLEITUNG = "Überleitung: Rückstellung für drohende Verluste nach § 5 Absatz 4a EStG"
REMARKS = (
	"Mit der Steuerberatung abgestimmt: die Vordrucke 2026 entsprechen denen der Jahresdokumentation 2025."
)


def d(value: str) -> Decimal:
	return Decimal(value)


# The fields of the computation of the worked example.
WORKED_EXAMPLE = {
	"net_income": d("88175.00"),
	"business_income": d("112200.00"),
	"sum_of_income": d("112200.00"),
	"total_income": d("111200.00"),
	"zve": d("111200.00"),
	"kst": d("16680.00"),
	"solz": d("917.40"),
	"capital_gains_tax_credit": d("5000.00"),
	"solz_credit": d("275.00"),
	"kst_prepayments": d("10000.00"),
	"solz_prepayments": d("550.00"),
	"kst_balance": d("1680.00"),
	"solz_balance": d("92.40"),
	"einlagekonto": d("0.00"),
}
# The lines of the worked example in the order of the forms: Anlage GK, ZVE, Z, WA and KSt 1 F.
LINES = [
	"E8002001",
	"E8002104",
	"E8100301",
	"E8100501",
	"E8100601",
	"E8100702",
	"E8101101",
	"E8101301",
	"E8101401",
	"E8560401",
	"E8560801",
	"E8561212",
	"E8561410",
	"E8561301",
	"E8561411",
	"E8562101",
	"E8109901",
	"E8004904",
	"E8005401",
	"E8005601",
	"E8006901",
	"E8007501",
	"E8007504",
	"E8007502",
	"E8005602",
	"E8009701",
	"E8006101",
	"E8010101",
	"E8120401",
	"E8120601",
	"E8240103",
	"E8245601",
]
FINAL = {"return_value": (False, YEAR)}
"""The answer of bridge.provisional once ELSTER has published the forms of the year."""


class TestCorporateIncomeTaxReturn(Transmitting, IntegrationTestCase):
	"""One class, so that the companies and their ledgers are made once; each test removes its returns and sets back
	what it changed."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.account = income_tax.make_muster_it_gmbh()
		cls.unnumbered = frappe.db.get_value(
			"Account", {"company": COMPANY, "account_name": "Sonstige Erlöse ohne Kontonummer"}
		) or make_account(COMPANY, None, "Sonstige Erlöse ohne Kontonummer", "Income")
		make_company(WITHOUT_SETTINGS, "STKOE")
		other = income_tax.make_accounts(
			WITHOUT_SETTINGS, {"8400": ("Erlöse 19 % USt", "Income"), "1200": ("Bank", "Asset")}
		)
		income_tax.make_income_tax_mapping(WITHOUT_SETTINGS)
		income_tax.post_once(
			WITHOUT_SETTINGS,
			other,
			"Sales Invoice",
			"SINV-STKOE-1",
			"2026-03-31",
			(("8400", 0, "10000.00"), ("1200", "10000.00", 0)),
		)

	def setUp(self):
		super().setUp()
		self.addCleanup(income_tax.discard_returns)

	def calculated(self, company: str = COMPANY, tables: dict | None = None, **fields):
		doc = income_tax.new_return(company, tables, **fields)
		doc.calculate()
		doc.reload()
		return doc

	def line(self, doc, feldkennung: str):
		(row,) = (row for row in doc.lines if row.feldkennung == feldkennung and not row.manual)
		return row

	def values(self, doc, *fields: str) -> dict[str, Decimal]:
		return {field: money(doc.get(field)) for field in fields}

	def change_settings(self, change):
		income_tax.change_for_the_test(self, SETTINGS, COMPANY, change)

	def change_mapping(self, change):
		income_tax.change_for_the_test(self, MAPPING, COMPANY, change)

	# Berechnen.

	def test_berechnen_computes_the_worked_example_and_holds_it_for_the_provisional_forms(self):
		doc = self.calculated()
		self.assertEqual(self.values(doc, *WORKED_EXAMPLE), WORKED_EXAMPLE)
		self.assertEqual((doc.status, doc.ready, doc.provisional, doc.vorgang), ("Berechnet", 0, 1, "01"))
		self.assertEqual(finding_codes(doc), ["KST-VORLAEUFIG"])
		(finding,) = doc.findings
		self.assertEqual((finding.blocking, finding.reference), (1, "Jahresdokumentation 2025"))
		self.assertEqual(
			(getdate(doc.from_date), getdate(doc.to_date)), (date(2026, 1, 1), date(2026, 12, 31))
		)

	def test_the_lines_name_form_line_and_field_with_the_amount_of_the_books(self):
		doc = self.calculated()
		self.assertEqual([row.feldkennung for row in doc.lines], LINES)
		self.assertTrue(all(row.label and not row.manual for row in doc.lines))
		expected = {
			"E8002001": ("GK", "11", d("88175.00"), d("88175.00")),
			"E8002104": ("GK", "51", d("0.00"), d("15000.00")),
			"E8100301": ("GK", "81", d("10000.00"), d("10000.00")),
			"E8100501": ("GK", "82", d("825.00"), d("825.00")),
			"E8101301": ("GK", "90", d("900.00"), d("900.00")),
			"E8109901": ("GK", "300", d("0.00"), d("112200.00")),
			"E8007501": ("ZVE", "70", d("0.00"), d("111200.00")),
			"E8007502": ("ZVE", "71", d("0.00"), d("16680.00")),
			"E8005602": ("Z", "5", d("0.00"), d("1000.00")),
			"E8120401": ("WA", "2", d("0.00"), d("5000.00")),
			"E8245601": ("KSt1F", "152", d("0.00"), d("0.00")),
		}
		for feldkennung, (form, line, ledger, filed) in expected.items():
			with self.subTest(feldkennung=feldkennung):
				row = self.line(doc, feldkennung)
				self.assertEqual(
					(
						row.form,
						row.line,
						money(row.ledger_amount),
						money(row.form_amount),
						money(row.reported),
					),
					(form, line, ledger, filed, filed),
				)

	def test_a_save_takes_the_shares_of_the_register_and_the_result_of_each_sale(self):
		doc = income_tax.new_return()
		self.assertEqual(
			[
				(
					row.kind,
					row.holding_name,
					money(row.amount),
					flt(row.percent_on_1_january),
					flt(row.percent_at_start_of_ez),
					row.exemption or "",
				)
				for row in doc.holding_results
			],
			[
				("Dividends", "Gamma AG", d("8000.00"), 0.5, 0.5, "Streubesitz"),
				("Dividends", "Beta GmbH", d("12000.00"), 12.0, 12.0, "§ 8b Abs. 1 KStG"),
				("Sale", "Delta AG", d("30000.00"), 0.0, 0.0, ""),
				("Sale", "Epsilon GmbH", d("-12000.00"), 0.0, 0.0, ""),
				("Write-down", "Zeta GmbH", d("4000.00"), 0.0, 0.0, ""),
			],
		)

	def test_the_turnover_and_wages_of_anlage_z_line_10_count_once_stated_also_at_zero(self):
		"""§ 9 Absatz 1 Nummer 2 Satz 1 Nummer 2 KStG deducts Zuwendungen up to 4 per mille of the turnover and the
		wages and salaries of the calendar year; the line goes with the return once the company states that sum, 0
		included."""
		self.assertNotIn("E8006001", LINES)
		doc = self.calculated(turnover_and_wages_given=1, turnover_and_wages=0)
		row = self.line(doc, "E8006001")
		self.assertEqual((row.form, row.line, money(row.reported)), ("Z", "10", d("0.00")))

	def test_a_year_without_its_forms_is_refused(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "Steuerbote has no forms of the Körperschaftsteuer for 2027 yet"
		):
			income_tax.new_return(tables={}, year=2027)

	def test_is_due_seven_months_after_the_year(self):
		doc = income_tax.new_return()
		self.assertEqual(getdate(doc.deadline), date(2027, 8, 2))

	# Lines by hand and corrections.

	def test_a_line_by_hand_of_a_verdeckte_gewinnausschuettung_raises_the_zve(self):
		doc = self.calculated()
		doc.append("lines", {"feldkennung": "e8002701", "correction": 2500, "correction_reason": VGA})
		doc.save()
		(manual,) = (row for row in doc.lines if row.manual)
		self.assertEqual((manual.feldkennung, manual.form, manual.line), ("E8002701", "GK", "75"))
		self.assertIn("Verdeckte Gewinnausschüttungen", manual.label)
		self.assertEqual((doc.status, doc.ready), ("Berechnet", 0))
		self.assertIn("SB-NEU-BERECHNEN", finding_codes(doc))
		doc.calculate()
		doc.reload()
		self.assertEqual(
			self.values(doc, "business_income", "zve", "kst", "solz", "kst_balance", "solz_balance"),
			{
				"business_income": d("114700.00"),
				"zve": d("113700.00"),
				"kst": d("17055.00"),
				"solz": d("938.02"),
				"kst_balance": d("2055.00"),
				"solz_balance": d("113.02"),
			},
		)
		(manual,) = (row for row in doc.lines if row.manual)
		self.assertEqual((manual.feldkennung, money(manual.reported)), ("E8002701", d("2500.00")))
		self.assertNotIn("SB-NEU-BERECHNEN", finding_codes(doc))

	def test_a_correction_of_a_line_of_the_books_files_its_amount_and_keeps_the_amount_of_the_books(self):
		doc = self.calculated()
		self.line(doc, "E8100301").update({"correction": 9000, "correction_reason": REFUND})
		doc.save()
		doc.calculate()
		doc.reload()
		row = self.line(doc, "E8100301")
		self.assertEqual(
			(money(row.ledger_amount), money(row.form_amount), money(row.reported), row.correction_reason),
			(d("10000.00"), d("9000.00"), d("9000.00"), REFUND),
		)
		self.assertEqual(
			self.values(doc, "business_income", "zve", "kst"),
			{"business_income": d("111200.00"), "zve": d("110200.00"), "kst": d("16530.00")},
		)

	def test_a_line_that_follows_from_others_takes_no_correction_and_no_line_by_hand(self):
		doc = self.calculated()
		self.line(doc, "E8109901").update({"correction": 100000, "correction_reason": REFUND})
		with self.assertRaisesRegex(frappe.ValidationError, "The line E8109901 follows from other lines"):
			doc.save()
		doc.reload()
		doc.append("lines", {"feldkennung": "E8007501", "correction": 1000, "correction_reason": REFUND})
		with self.assertRaisesRegex(
			frappe.ValidationError, "The return has no line E8007501 that takes a line by hand"
		):
			doc.save()

	def test_a_line_in_whole_euros_takes_no_correction_in_cents(self):
		doc = self.calculated()
		self.line(doc, "E8100301").update({"correction": 9000.5, "correction_reason": REFUND})
		with self.assertRaisesRegex(
			frappe.ValidationError, "The line E8100301 files whole euros, not 9000.50"
		):
			doc.save()

	def test_a_change_of_a_table_after_berechnen_asks_for_berechnen_again(self):
		doc = self.calculated()
		doc.append("credits", {"issuer": "Musterbank AG", "capital_gains_tax": 100, "solz": 5.5})
		doc.save()
		self.assertEqual((doc.status, doc.ready), ("Berechnet", 0))
		self.assertIn("SB-NEU-BERECHNEN", finding_codes(doc))
		doc.calculate()
		doc.reload()
		self.assertNotIn("SB-NEU-BERECHNEN", finding_codes(doc))
		self.assertEqual(
			self.values(doc, "capital_gains_tax_credit", "solz_credit"),
			{"capital_gains_tax_credit": d("5100.00"), "solz_credit": d("280.50")},
		)

	def test_a_row_the_forms_do_not_take_is_refused(self):
		doc = income_tax.new_return()
		doc.append("donations", {"recipient": "Musterverein e. V.", "amount": -50})
		with self.assertRaisesRegex(
			frappe.ValidationError, "Row 2 of the donations: the amount is above zero"
		):
			doc.save()

	# What holds the return back.

	def test_a_company_without_annual_filing_settings_is_not_ready(self):
		doc = self.calculated(WITHOUT_SETTINGS, tables={})
		self.assertIn("KST-EINSTELLUNGEN-FEHLEN", blocking_codes(doc))
		self.assertEqual(doc.status, "Berechnet")

	def test_waits_for_the_review_of_the_steuerberatung(self):
		"""Decision 6.4 of the contract of stage 3: a Steuerberatung confirms the classes of the trading accounts, the
		status under § 8b Absatz 7 KStG and the review list before the return is ready."""
		self.change_settings(lambda settings: settings.update({"income_tax_review_on": None}))
		with patch.object(bridge, "provisional", **FINAL):
			doc = self.calculated()
		self.assertEqual(blocking_codes(doc), ["KST-PRUEFUNG-FEHLT"])
		self.assertEqual((doc.status, doc.ready), ("Berechnet", 0))

	def test_kst_1_needs_the_seats_of_the_company(self):
		self.change_settings(
			lambda settings: settings.update({"management_seat": None, "registered_seat": None})
		)
		doc = self.calculated()
		self.assertIn("KST-ANGABEN-FEHLEN", blocking_codes(doc))
		(finding,) = (row for row in doc.findings if row.code == "KST-ANGABEN-FEHLEN")
		self.assertIn("Place of Management, Registered Seat", finding.text)

	def test_the_shares_add_up_to_99_to_100_percent_on_each_day_of_the_wirtschaftsjahr(self):
		self.change_settings(lambda settings: settings.shareholders[0].update({"to_date": "2026-06-30"}))
		doc = self.calculated()
		self.assertIn("KST-ANTEILSEIGNER", blocking_codes(doc))
		(finding,) = (row for row in doc.findings if row.code == "KST-ANTEILSEIGNER")
		self.assertIn("01.07.2026", finding.text)

	def test_a_carry_forward_counts_once_it_is_confirmed_and_in_whole_euros(self):
		stated = {"kind": "Loss Carried Forward (§ 10d EStG)", "as_of": "2025-12-31", "amount": 5000.5}
		self.change_settings(lambda settings: settings.append("carry_forwards", stated))
		doc = self.calculated()
		self.assertIn("KST-VORTRAG-UNBESTAETIGT", blocking_codes(doc))
		self.assertNotIn("KST-VORTRAG-CENT", blocking_codes(doc))
		self.assertEqual(money(doc.zve), d("111200.00"))
		income_tax.discard_returns()
		self.change_settings(lambda settings: settings.carry_forwards[-1].update({"confirmed": 1}))
		doc = self.calculated()
		self.assertNotIn("KST-VORTRAG-UNBESTAETIGT", blocking_codes(doc))
		self.assertIn("KST-VORTRAG-CENT", blocking_codes(doc))
		self.assertEqual(money(doc.zve), d("106199.00"))

	def test_a_handelsbilanz_with_ueberleitungsrechnung_needs_the_ueberleitung_of_line_11_by_hand(self):
		self.change_settings(lambda settings: settings.update({"accounting_standard": "HGBM"}))
		doc = self.calculated()
		self.assertIn("KST-UEBERLEITUNG-FEHLT", blocking_codes(doc))
		doc.append(
			"lines", {"feldkennung": "E8002001", "correction": -1000, "correction_reason": UEBERLEITUNG}
		)
		doc.save()
		doc.calculate()
		doc.reload()
		self.assertNotIn("KST-UEBERLEITUNG-FEHLT", finding_codes(doc))
		self.assertEqual(
			self.values(doc, "net_income", "zve"), {"net_income": d("87175.00"), "zve": d("110200.00")}
		)

	def test_an_account_whose_place_the_defaults_give_needs_its_row_in_the_mapping(self):
		def without_4397(mapping):
			mapping.set("rules", [row for row in mapping.rules if row.account_number != "4397"])

		self.change_mapping(without_4397)
		doc = self.calculated()
		self.assertIn("KST-KONTO-OHNE-ZUORDNUNG", blocking_codes(doc))
		(finding,) = (row for row in doc.findings if row.code == "KST-KONTO-OHNE-ZUORDNUNG")
		self.assertIn("4397", finding.text)

	def test_a_trading_account_needs_its_class(self):
		def unclassified(mapping):
			for row in mapping.rules:
				if row.account_number in income_tax.DERIVATIVES:
					row.trading_class = None

		self.change_mapping(unclassified)
		doc = self.calculated()
		self.assertEqual(blocking_codes(doc).count("KST-HANDEL-OHNE-KLASSE"), 2)

	def test_foreign_taxes_wait_for_the_anlage_aest(self):
		income_tax.post_for_the_test(
			self,
			"JV-STMIT-QUELLENSTEUER",
			"2026-07-01",
			[(self.account["2219"], 300, 0), (self.account["1200"], 0, 300)],
		)
		doc = self.calculated()
		self.assertIn("KST-AUSLAENDISCHE-STEUERN", blocking_codes(doc))

	def test_investment_funds_wait_for_the_teilfreistellung(self):
		"""§ 20 InvStG: Steuerbote does not compute the Teilfreistellung of a result from investment funds yet."""

		def funds(mapping):
			for row in mapping.rules:
				if row.account_number == "2654":
					row.trading_class = "funds"

		self.change_mapping(funds)
		doc = self.calculated()
		self.assertIn("KST-INVESTMENTFONDS", blocking_codes(doc))

	def test_an_account_of_the_profit_and_loss_account_without_a_number_is_named(self):
		income_tax.post_for_the_test(
			self,
			"JV-STMIT-OHNE-NUMMER",
			"2026-07-01",
			[(self.unnumbered, 0, 250), (self.account["1200"], 250, 0)],
		)
		doc = self.calculated()
		self.assertIn("KST-KONTO-OHNE-NUMMER", blocking_codes(doc))
		self.assertEqual(money(doc.net_income), d("88425.00"))

	def test_the_rules_of_the_jahresdokumentation_check_the_return_as_filed(self):
		"""Rule 8912151: KSt 1 of a Kapitalgesellschaft names its Anteilseigner."""
		self.change_settings(lambda settings: settings.set("shareholders", []))
		doc = self.calculated()
		self.assertIn("8912151", blocking_codes(doc))

	def test_the_tables_of_the_return_give_the_single_values_and_the_receipts(self):
		holdings = income_tax.RETURN_TABLES["holding_results"]
		dividends = [row for row in holdings if row["kind"] == "Dividends"]
		unknown = {"kind": "Dividends", "holding_name": "Omega AG", "amount": 500}
		for code, tables, fields in (
			("KST-ZUWENDUNGEN-BESTAETIGUNG", {**income_tax.RETURN_TABLES, "donations": []}, {}),
			("KST-8B-EINZELANGABEN", {**income_tax.RETURN_TABLES, "holding_results": dividends}, {}),
			(
				"KST-BETEILIGUNG-UNBEKANNT",
				{**income_tax.RETURN_TABLES, "holding_results": [*holdings, unknown]},
				{},
			),
			("KST-VERLUSTRUECKTRAG-OHNE-VERLUST", None, {"carry_back_chosen": 1, "loss_carry_back": 1000}),
		):
			with self.subTest(code=code):
				try:
					self.assertIn(code, blocking_codes(self.calculated(tables=tables, **fields)))
				finally:
					income_tax.discard_returns()

	def test_hints_name_what_the_books_say_otherwise_and_hold_nothing_back(self):
		credits = income_tax.RETURN_TABLES["credits"][:1]
		receipt = [{"recipient": "Musterverein e. V.", "amount": 800}]
		for code, tables, fields in (
			("KST-KAPEST", {**income_tax.RETURN_TABLES, "credits": credits}, {}),
			("KST-ZUWENDUNGEN-ABWEICHUNG", {**income_tax.RETURN_TABLES, "donations": receipt}, {}),
			("KST-WA-VERTRAEGE", None, {"shareholder_contracts": 1}),
		):
			with self.subTest(code=code):
				try:
					doc = self.calculated(tables=tables, **fields)
					self.assertIn(code, hint_codes(doc))
					self.assertEqual(blocking_codes(doc), ["KST-VORLAEUFIG"])
				finally:
					income_tax.discard_returns()

	def test_a_hint_names_vorauszahlungen_of_the_notices_that_differ_from_those_booked(self):
		def without_the_last_kst(settings):
			settings.set(
				"prepayments",
				[
					row
					for row in settings.prepayments
					if not (row.tax == "KSt" and getdate(row.due_date) == date(2026, 12, 10))
				],
			)

		self.change_settings(without_the_last_kst)
		doc = self.calculated()
		self.assertIn("KST-VORAUSZAHLUNGEN", hint_codes(doc))
		self.assertEqual(
			self.values(doc, "kst_prepayments", "kst_balance"),
			{"kst_prepayments": d("7500.00"), "kst_balance": d("4180.00")},
		)

	# Bereit and the filing.

	def test_is_ready_once_the_forms_of_the_year_are_final(self):
		with patch.object(bridge, "provisional", **FINAL):
			doc = self.calculated()
			self.assertEqual((doc.status, doc.ready, doc.provisional), ("Bereit", 1, 0))
			self.assertEqual(finding_codes(doc), [])
			doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		doc.reload()
		self.assertEqual((doc.docstatus, doc.status, doc.filed_via), (1, "Abgegeben", FILED_IN_MEIN_ELSTER))

	def test_while_the_forms_of_the_year_are_provisional_a_filing_needs_the_error_acknowledged(self):
		doc = self.calculated(remarks=REMARKS)
		with self.assertRaisesRegex(
			frappe.ValidationError, "is not ready: the error [A-Z0-9-]+ of its findings holds"
		):
			doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		doc.reload()
		acknowledge_errors(doc, REMARKS).mark_filed_outside(FILED_IN_MEIN_ELSTER)
		doc.reload()
		self.assertEqual((doc.docstatus, doc.status, doc.filed_via), (1, "Abgegeben", FILED_IN_MEIN_ELSTER))

	def test_a_berichtigung_starts_with_the_statements_and_tables_of_the_filed_return(self):
		doc = acknowledge_errors(self.calculated(shareholder_contracts=1, remarks=REMARKS), REMARKS)
		doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		correction = frappe.get_doc(DOCTYPE, doc.make_correction())
		self.assertEqual(
			(
				correction.is_correction,
				correction.corrects,
				correction.status,
				correction.shareholder_contracts,
			),
			(1, doc.name, "Berechnet", 1),
		)
		self.assertEqual(
			[len(correction.get(table)) for table in ("holding_results", "credits", "donations")], [5, 2, 1]
		)
		self.assertEqual(money(correction.zve), d("111200.00"))
		acknowledge_errors(correction, REMARKS).mark_filed_outside(FILED_IN_MEIN_ELSTER)
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "status"), "Ersetzt")

	def test_an_accounts_user_calculates_but_does_not_file(self):
		user = make_user("steuerbote-test-kst-buchhaltung@example.com", "Accounts User")
		doc = income_tax.new_return()
		with self.set_user(user):
			doc = frappe.get_doc(DOCTYPE, doc.name)
			doc.calculate()
			with self.assertRaises(frappe.PermissionError):
				doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)

	# Rückstellungen vorschlagen.

	def test_rueckstellungen_vorschlagen_makes_a_draft_journal_entry_of_the_balances(self):
		a = self.account
		doc = self.calculated()
		name = doc.propose_provisions()
		entry = frappe.get_doc("Journal Entry", name)
		self.assertEqual(
			(entry.docstatus, entry.company, getdate(entry.posting_date)), (0, COMPANY, date(2026, 12, 31))
		)
		self.assertEqual(
			[
				(
					row.account,
					money(row.debit_in_account_currency),
					money(row.credit_in_account_currency),
					row.user_remark,
				)
				for row in entry.accounts
			],
			[
				(a["2200"], d("1680.00"), d("0.00"), "Rückstellung Körperschaftsteuer 2026"),
				(a["0963"], d("0.00"), d("1680.00"), "Rückstellung Körperschaftsteuer 2026"),
				(a["2208"], d("92.40"), d("0.00"), "Rückstellung Solidaritätszuschlag 2026"),
				(a["0963"], d("0.00"), d("92.40"), "Rückstellung Solidaritätszuschlag 2026"),
				(a["4320"], d("64.00"), d("0.00"), "Rückstellung Gewerbesteuer 2026"),
				(a["0956"], d("0.00"), d("64.00"), "Rückstellung Gewerbesteuer 2026"),
			],
		)
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "provisions_entry"), name)
		with self.assertRaisesRegex(
			frappe.ValidationError,
			f"The draft Journal Entry {re.escape(name)} holds the provisions proposed before",
		):
			frappe.get_doc(DOCTYPE, doc.name).propose_provisions()

	def test_the_draft_of_the_provisions_may_be_deleted_to_propose_them_again(self):
		"""The refusal to propose again tells the user to delete the draft; deleting it forgets it."""
		doc = self.calculated()
		name = doc.propose_provisions()
		frappe.delete_doc("Journal Entry", name)
		self.assertIsNone(frappe.db.get_value(DOCTYPE, doc.name, "provisions_entry"))
		again = frappe.get_doc(DOCTYPE, doc.name).propose_provisions()
		self.assertEqual(frappe.db.get_value("Journal Entry", again, "docstatus"), 0)
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "provisions_entry"), again)

	def test_the_zve_stays_the_same_once_the_proposed_provisions_are_posted(self):
		"""Every tax on income is added back in Anlage GK lines 81 to 84 (§ 10 Nummer 2 KStG, § 4 Absatz 5b EStG), so
		posting the provisions lowers the Jahresüberschuss and leaves the zu versteuerndes Einkommen."""
		doc = self.calculated()
		before = self.values(doc, "business_income", "zve", "kst", "solz", "kst_balance", "solz_balance")
		frappe.get_doc("Journal Entry", doc.propose_provisions()).submit()
		doc.reload()
		doc.calculate()
		doc.reload()
		self.assertEqual(self.values(doc, *before), before)
		self.assertEqual(money(doc.net_income), d("86339.00"))
		self.assertNotIn("KST-VORAUSZAHLUNGEN", finding_codes(doc))
		self.assertNotIn("KST-RUECKSTELLUNG-DIFFERENZ", finding_codes(doc))
		self.assertEqual(doc.propose_provisions(), "")

	def test_after_a_later_posting_the_return_names_the_difference_and_proposes_it(self):
		"""„Rückstellungen sind zu bilden für ungewisse Verbindlichkeiten“ (§ 249 Abs. 1 Satz 1 HGB), in full: a sale
		posted after the provisions raises the taxes, and the provisions in the books stay too low until the difference
		is posted."""
		a = self.account
		doc = self.calculated()
		frappe.get_doc("Journal Entry", doc.propose_provisions()).submit()
		self.addCleanup(frappe.db.delete, "GL Entry", {"voucher_no": "JV-STMIT-NACHTRAG"})
		post_ledger(
			COMPANY,
			"Journal Entry",
			"JV-STMIT-NACHTRAG",
			"2026-12-30",
			[(a["8400"], 0, 10000), (a["1200"], 10000, 0)],
		)
		doc.reload()
		doc.calculate()
		doc.reload()
		(finding,) = [row for row in doc.findings if row.code == "KST-RUECKSTELLUNG-DIFFERENZ"]
		self.assertEqual(finding.severity, "Hinweis")
		self.assertIn("1.500,00 €", finding.text)
		entry = frappe.get_doc("Journal Entry", doc.propose_provisions())
		self.assertEqual(
			[
				(
					row.account,
					money(row.debit_in_account_currency),
					money(row.credit_in_account_currency),
					row.user_remark,
				)
				for row in entry.accounts[:2]
			],
			[
				(a["2200"], d("1500.00"), d("0.00"), "Anpassung Rückstellung Körperschaftsteuer 2026"),
				(a["0963"], d("0.00"), d("1500.00"), "Anpassung Rückstellung Körperschaftsteuer 2026"),
			],
		)

	def test_without_a_hebesatz_the_proposal_leaves_out_the_gewerbesteuer(self):
		a = self.account
		self.change_settings(lambda settings: settings.set("trade_tax_rates", []))
		doc = self.calculated()
		entry = frappe.get_doc("Journal Entry", doc.propose_provisions())
		self.assertEqual(
			[(row.account, money(row.debit_in_account_currency)) for row in entry.accounts],
			[
				(a["2200"], d("1680.00")),
				(a["0963"], d("0.00")),
				(a["2208"], d("92.40")),
				(a["0963"], d("0.00")),
			],
		)

	def test_a_draft_proposes_no_provisions(self):
		doc = income_tax.new_return()
		with self.assertRaisesRegex(
			frappe.ValidationError, f"Calculate {re.escape(doc.name)} before proposing"
		):
			doc.propose_provisions()

	# Prüfen and the print.

	def test_pruefen_in_the_simulation_checks_e30_with_the_vorsatz(self):
		doc = self.calculated()
		transmission, _, run = self.transmitted(doc, "validate")
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.simulated),
			("Erfolgreich", Outcome.VALID.value, 1),
		)
		self.assertNotIn("error", [row.severity for row in transmission.messages])
		self.assertIn("SIM-001", self.codes(transmission))
		_, nutzdaten, header, *_ = run.call_args.args
		elster_tax_number = frappe.db.get_value("VAT Return Settings", COMPANY, "elster_tax_number")
		self.assertEqual((header.datenart_version, header.empfaenger), ("KSt_30_2026", elster_tax_number[:4]))
		for element in (
			f"<E8000101>{COMPANY}</E8000101>",
			"<E8000501>Musterstadt</E8000501>",
			"<E8001105>350</E8001105>",
			"<E8122101>Erika Musterfrau</E8122101>",
			"<E8002001>88175</E8002001>",
			"<E8109901>112200</E8109901>",
			"<E8007501>111200</E8007501>",
			"<E8007502>16680</E8007502>",
			"<E8005603>Musterverein e. V.</E8005603>",
			"<E8120401>5000,00</E8120401>",
			"<E8120601>275,00</E8120601>",
			"<Unterfallart>30</Unterfallart>",
			"<Vorgang>01</Vorgang>",
			f"<StNr>{elster_tax_number}</StNr>",
			"<Zeitraum>2026</Zeitraum>",
			f"<AbsName>{COMPANY}</AbsName>",
		):
			with self.subTest(element=element):
				self.assertIn(element, nutzdaten)
		self.assertEqual(doc.elster_state()["printout"], "Freizeichnungsdokument")

	def test_prints_the_vordrucke_in_the_order_of_the_forms_and_says_that_they_are_provisional(self):
		doc = self.calculated()
		html = frappe.get_print(DOCTYPE, doc.name, "Körperschaftsteuererklärung")
		for text in (
			"Körperschaftsteuererklärung 2026",
			"vorläufig (Jahresdokumentation 2025)",
			COMPANY,
			"01 Veranlagung",
			"Erika Musterfrau",
			"Jahresüberschuss/-fehlbetrag laut Handels- oder Steuerbilanz",
			"88.175",
			"111.200",
			"Musterverein e. V.",
			"16.680,00",
			"1.680,00",
		):
			with self.subTest(text=text):
				self.assertIn(text, html)
		sections = [
			html.index(f">{title}</td>")
			for title in ("KSt 1", "Anlage GK", "Anlage ZVE", "Anlage Z", "Anlage WA", "KSt 1 F")
		]
		self.assertEqual(sections, sorted(sections))
