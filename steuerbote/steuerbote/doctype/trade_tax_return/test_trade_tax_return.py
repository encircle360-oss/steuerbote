"""The Gewerbesteuererklärung on the Frappe test site, on the Körperschaftsteuererklärung of the worked example „Muster
IT GmbH“ of steuerbote/tests/income_tax.py: the Körperschaftsteuererklärung of its company and year it builds on,
Berechnen of GewSt 1 A, the Anlage BEG and the Gemeinde, the corrections it refuses, each finding that holds it back,
„Bereit“ once the forms of the year are final, Prüfen in the simulation, the Berichtigung and the print. A second
company has a Körperschaftsteuererklärung of its own. Every name, number and amount is invented.
"""

import re
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, getdate

from steuerbote.eric.result import Outcome
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge as corporate_bridge
from steuerbote.steuerbote.doctype.trade_tax_return import bridge
from steuerbote.steuerbote.doctype.trade_tax_return.trade_tax_return import latest_corporate_income_tax_return
from steuerbote.tests import income_tax
from steuerbote.tests.helpers import make_company
from steuerbote.tests.income_tax import (
	AGS,
	COMPANY,
	HEBESATZ_SOURCE,
	SETTINGS,
	YEAR,
	blocking_codes,
	finding_codes,
	hint_codes,
	money,
)
from steuerbote.tests.transmitting import Transmitting

# The companies, their accounts, Fiscal Years and returns are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Account",
	"Company",
	"Corporate Income Tax Return",
	"DocType",
	"Fiscal Year",
	"Trade Tax Return",
	"User",
]

DOCTYPE = income_tax.TRADE
OTHER_COMPANY = "Steuerbote Test GewSt andere GmbH"
FILED_IN_MEIN_ELSTER = "mein_elster"
REASON = "Gewinn laut Betriebsprüfung"
REMARKS = (
	"Mit der Steuerberatung abgestimmt: die Vordrucke 2026 entsprechen denen der Jahresdokumentation 2025."
)
SUPPLEMENT = "Die Hinzurechnung nach § 8 Nummer 1 GewStG ist mit der Steuerberatung abgestimmt."


def d(value: str) -> Decimal:
	return Decimal(value)


# The fields of the computation of the worked example.
WORKED_EXAMPLE = {
	"profit": d("97200.00"),
	"financing_addback": d("0.00"),
	"gewerbeertrag": d("107600.00"),
	"messbetrag": d("3766.00"),
	"hebesatz": d("400.00"),
	"gewst": d("15064.00"),
	"prepayments": d("15000.00"),
	"balance": d("64.00"),
}
# The lines of GewSt 1 A of the worked example by Feldkennung: line, amount of the books, amount filed.
LINES = {
	"E4001703": ("39", d("0.00"), d("97200.00")),
	"E4003202": ("50", d("5000.00"), d("5000.00")),
	"E4003502": ("53", d("6000.00"), d("6000.00")),
	"E4003602": ("55", d("24000.00"), d("24000.00")),
	"E4003703": ("56", d("10000.00"), d("10000.00")),
	"E4006601": ("77", d("0.00"), d("11400.00")),
	"E4003403": ("92d", d("0.00"), d("1000.00")),
}
FINAL = {"return_value": (False, YEAR)}
"""The answer of bridge.provisional once ELSTER has published the forms of the year."""


class TestTradeTaxReturn(Transmitting, IntegrationTestCase):
	"""One class, so that the companies and the ledger are made once; each test removes its returns and sets back what
	it changed."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.account = income_tax.make_muster_it_gmbh()
		make_company(OTHER_COMPANY, "STGWA")

	def setUp(self):
		super().setUp()
		self.addCleanup(income_tax.discard_returns)

	def new_return(self, **fields):
		return frappe.get_doc({"doctype": DOCTYPE, "company": COMPANY, "year": YEAR, **fields}).insert()

	def calculated(self, tables: dict | None = None, **fields):
		"""The Gewerbesteuererklärung of the year, calculated on a Körperschaftsteuererklärung with the tables of the
		worked example, or those given."""
		income_tax.new_return(tables=tables)
		doc = self.new_return(**fields)
		doc.calculate()
		doc.reload()
		return doc

	def values(self, doc, *fields: str) -> dict[str, Decimal]:
		return {field: money(doc.get(field)) for field in fields}

	def change_settings(self, change):
		income_tax.change_for_the_test(self, SETTINGS, COMPANY, change)

	def final_forms(self):
		"""While it lasts, the forms of the year are final for both Erklärungen."""
		self.enterContext(patch.object(corporate_bridge, "provisional", **FINAL))
		self.enterContext(patch.object(bridge, "provisional", **FINAL))

	# Berechnen.

	def test_builds_on_the_koerperschaftsteuererklaerung_of_its_company_and_year(self):
		corporate = income_tax.new_return()
		doc = self.new_return()
		self.assertEqual(doc.corporate_income_tax_return, corporate.name)

	def test_builds_on_a_draft_or_else_on_the_latest_filing_no_berichtigung_replaced(self):
		corporate = income_tax.new_return(remarks=REMARKS)
		corporate.calculate()
		corporate.reload()
		corporate.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		self.assertEqual(latest_corporate_income_tax_return(COMPANY, YEAR), corporate.name)
		correction = frappe.get_doc(income_tax.CORPORATE, corporate.make_correction())
		self.assertEqual(latest_corporate_income_tax_return(COMPANY, YEAR), correction.name)
		correction.remarks = REMARKS
		correction.save()
		correction.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		self.assertEqual(latest_corporate_income_tax_return(COMPANY, YEAR), correction.name)
		self.assertIsNone(latest_corporate_income_tax_return(OTHER_COMPANY, YEAR))

	def test_berechnen_computes_the_worked_example_and_holds_it_for_the_provisional_forms(self):
		doc = self.calculated()
		self.assertEqual(self.values(doc, *WORKED_EXAMPLE), WORKED_EXAMPLE)
		self.assertEqual((doc.status, doc.ready, doc.provisional, doc.vorgang), ("Berechnet", 0, 1, "01"))
		self.assertEqual(finding_codes(doc), ["GEWST-VORLAEUFIG"])
		self.assertEqual(
			{
				row.feldkennung: (row.line, money(row.ledger_amount), money(row.reported))
				for row in doc.lines
				if not row.manual
			},
			LINES,
		)
		self.assertTrue(all(row.form == "GewSt1A" and row.label for row in doc.lines))

	def test_the_gemeinde_bears_the_gewerbesteuer_with_the_hebesatz_and_its_source(self):
		doc = self.calculated()
		(gemeinde,) = doc.municipalities
		self.assertEqual(
			(
				gemeinde.municipality,
				gemeinde.postal_code,
				gemeinde.ags,
				flt(gemeinde.hebesatz),
				gemeinde.hebesatz_source,
			),
			("Musterstadt", "12345", AGS, 400.0, HEBESATZ_SOURCE),
		)
		self.assertEqual(
			self.values(gemeinde, "messbetrag", "gewst", "prepayments", "balance"),
			{
				"messbetrag": d("3766.00"),
				"gewst": d("15064.00"),
				"prepayments": d("15000.00"),
				"balance": d("64.00"),
			},
		)

	def test_the_holding_of_12_percent_is_an_anlage_beg_and_the_receipt_goes_to_lines_92a_to_92c(self):
		"""Beta GmbH is held below 15 % at the start of the Erhebungszeitraum, so § 9 Nummer 2a GewStG cuts nothing,
		and § 8 Nummer 5 GewStG adds back the dividends exempt under § 8b Absatz 1 KStG less the 5 % of § 8b Absatz 5
		KStG."""
		doc = self.calculated()
		(holding,) = doc.holdings
		self.assertEqual((holding.holding_name, holding.paragraph or ""), ("Beta GmbH", ""))
		self.assertEqual(
			self.values(holding, "dividends", "exempt", "not_exempt", "addback", "cut"),
			{
				"dividends": d("12000.00"),
				"exempt": d("12000.00"),
				"not_exempt": d("0.00"),
				"addback": d("11400.00"),
				"cut": d("0.00"),
			},
		)
		self.assertEqual(
			[(row.recipient, money(row.amount), row.abroad) for row in doc.donations],
			[("Musterverein e. V.", d("1000.00"), 0)],
		)

	def test_berechnen_needs_a_koerperschaftsteuererklaerung_of_its_company_and_year(self):
		doc = self.new_return()
		self.assertFalse(doc.corporate_income_tax_return)
		with self.assertRaisesRegex(frappe.ValidationError, "has no Körperschaftsteuererklärung for 2026"):
			doc.calculate()
		other = income_tax.new_return(OTHER_COMPANY, tables={})
		doc = frappe.get_doc(DOCTYPE, doc.name)
		doc.corporate_income_tax_return = other.name
		with self.assertRaisesRegex(
			frappe.ValidationError,
			re.escape(f"{other.name} is the Körperschaftsteuererklärung of {OTHER_COMPANY} for 2026"),
		):
			doc.save()

	def test_a_year_without_its_forms_is_refused(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "Steuerbote has no forms of the Gewerbesteuer for 2027 yet"
		):
			self.new_return(year=2027)

	def test_is_due_seven_months_after_the_year(self):
		doc = self.new_return()
		self.assertEqual(getdate(doc.deadline), date(2027, 8, 2))

	def test_takes_no_correction_and_no_line_by_hand(self):
		doc = self.calculated()
		doc.lines[0].update({"correction": 90000, "correction_reason": REASON})
		with self.assertRaisesRegex(frappe.ValidationError, "takes no correction and no line by hand"):
			doc.save()
		doc.reload()
		doc.append("lines", {"feldkennung": "E4001703", "correction": 1000, "correction_reason": REASON})
		with self.assertRaisesRegex(frappe.ValidationError, "takes no correction and no line by hand"):
			doc.save()

	def test_a_change_of_the_free_text_after_berechnen_asks_for_berechnen_again(self):
		doc = self.calculated()
		doc.update({"supplement_key": "1", "supplement_text": SUPPLEMENT})
		doc.save()
		self.assertEqual((doc.status, doc.ready), ("Berechnet", 0))
		self.assertIn("SB-NEU-BERECHNEN", finding_codes(doc))
		doc.calculate()
		doc.reload()
		self.assertNotIn("SB-NEU-BERECHNEN", finding_codes(doc))
		entries = {entry.feldkennung: entry.value for entry in doc.filed_vordrucke()[0].entries}
		self.assertEqual((entries["E4003204"], entries["E4003205"]), ("1", SUPPLEMENT))

	# What holds the return back.

	def test_files_for_one_betriebsstaette_in_one_gemeinde(self):
		self.change_settings(
			lambda settings: settings.append(
				"establishments",
				{
					"municipality": "Beispielhausen",
					"postal_code": "54321",
					"ags": "09888888",
					"from_date": "2026-07-01",
				},
			)
		)
		doc = self.calculated()
		self.assertIn("GEWST-BETRIEBSSTAETTE", blocking_codes(doc))
		self.assertEqual(doc.municipalities, [])

	def test_the_hebesatz_of_the_gemeinde_comes_with_its_source(self):
		self.change_settings(lambda settings: settings.set("trade_tax_rates", []))
		doc = self.calculated()
		self.assertIn("GEWST-HEBESATZ-FEHLT", blocking_codes(doc))
		self.assertEqual(self.values(doc, "hebesatz", "gewst"), {"hebesatz": d("0.00"), "gewst": d("0.00")})

	def test_the_fehlbetrag_of_the_last_notice_counts_once_it_is_confirmed(self):
		stated = {"kind": "Fehlbetrag (§ 10a GewStG)", "as_of": "2025-12-31", "amount": 2000}
		self.change_settings(lambda settings: settings.append("carry_forwards", stated))
		doc = self.calculated()
		self.assertIn("GEWST-VORTRAG-UNBESTAETIGT", blocking_codes(doc))
		self.assertEqual(money(doc.gewerbeertrag), d("107600.00"))
		self.assertNotIn("E4014801", [row.feldkennung for row in doc.lines])
		income_tax.discard_returns()
		self.change_settings(lambda settings: settings.carry_forwards[-1].update({"confirmed": 1}))
		doc = self.calculated()
		self.assertNotIn("GEWST-VORTRAG-UNBESTAETIGT", blocking_codes(doc))
		self.assertEqual(money(doc.gewerbeertrag), d("105600.00"))
		(line,) = (row for row in doc.lines if row.feldkennung == "E4014801")
		self.assertEqual(money(line.reported), d("2000.00"))

	def test_waits_for_the_review_of_the_steuerberatung_as_the_koerperschaftsteuer_does(self):
		self.final_forms()
		self.change_settings(lambda settings: settings.update({"income_tax_review_on": None}))
		doc = self.calculated()
		self.assertEqual(blocking_codes(doc), ["KST-PRUEFUNG-FEHLT"])
		self.assertEqual((doc.status, doc.ready), ("Berechnet", 0))

	def test_gewst_1_a_needs_the_gegenstand_of_the_unternehmen(self):
		self.change_settings(lambda settings: settings.update({"business_purpose": None}))
		doc = self.calculated()
		self.assertIn("GEWST-ANGABEN-FEHLEN", blocking_codes(doc))

	def test_an_error_of_the_koerperschaftsteuer_holds_the_gewerbesteuer_back_too(self):
		doc = self.calculated(tables={**income_tax.RETURN_TABLES, "donations": []})
		self.assertIn("KST-ZUWENDUNGEN-BESTAETIGUNG", blocking_codes(doc))
		self.assertNotIn("KST-VORLAEUFIG", finding_codes(doc))
		self.assertEqual(doc.donations, [])

	def test_a_hint_names_vorauszahlungen_of_the_notices_that_differ_from_those_booked(self):
		def without_the_last_gewst(settings):
			settings.set(
				"prepayments",
				[
					row
					for row in settings.prepayments
					if not (row.tax == "GewSt" and getdate(row.due_date) == date(2026, 11, 15))
				],
			)

		self.change_settings(without_the_last_gewst)
		doc = self.calculated()
		self.assertIn("GEWST-VORAUSZAHLUNGEN", hint_codes(doc))
		self.assertEqual(
			self.values(doc, "prepayments", "balance"),
			{"prepayments": d("11250.00"), "balance": d("3814.00")},
		)

	# Bereit and the filing.

	def test_is_ready_once_the_forms_of_the_year_are_final(self):
		self.final_forms()
		doc = self.calculated()
		self.assertEqual((doc.status, doc.ready, doc.provisional), ("Bereit", 1, 0))
		self.assertEqual(finding_codes(doc), [])
		doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		doc.reload()
		self.assertEqual((doc.docstatus, doc.status, doc.filed_via), (1, "Abgegeben", FILED_IN_MEIN_ELSTER))

	def test_a_berichtigung_builds_on_the_koerperschaftsteuererklaerung_of_the_year(self):
		doc = self.calculated(remarks=REMARKS)
		doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		correction = frappe.get_doc(DOCTYPE, doc.make_correction())
		self.assertEqual(
			(correction.is_correction, correction.corrects, correction.corporate_income_tax_return),
			(1, doc.name, doc.corporate_income_tax_return),
		)
		self.assertEqual((correction.status, money(correction.gewst)), ("Berechnet", d("15064.00")))
		correction.remarks = REMARKS
		correction.save()
		correction.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "status"), "Ersetzt")

	# Prüfen and the print.

	def test_pruefen_in_the_simulation_checks_e20_with_the_vorsatz(self):
		doc = self.calculated()
		transmission, _, run = self.transmitted(doc, "validate")
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.simulated),
			("Erfolgreich", Outcome.VALID.value, 1),
		)
		self.assertNotIn("error", [row.severity for row in transmission.messages])
		_, nutzdaten, header, *_ = run.call_args.args
		elster_tax_number = frappe.db.get_value("VAT Return Settings", COMPANY, "elster_tax_number")
		self.assertEqual((header.datenart_version, header.empfaenger), ("GewSt_2026", elster_tax_number[:4]))
		for element in (
			f"<E4000101>{COMPANY}</E4000101>",
			"<E4000201>Softwareentwicklung</E4000201>",
			"<E4000501>350</E4000501>",
			"<E4001110>12345</E4001110>",
			"<E4001111>Musterstadt</E4001111>",
			"<E4001703>97200</E4001703>",
			"<E4006601>11400</E4006601>",
			"<E4009220>Musterverein e. V.</E4009220>",
			"<E4003403>1000</E4003403>",
			"<E4050201>Beta GmbH</E4050201>",
			"<E4051501>11400</E4051501>",
			"<Unterfallart>20</Unterfallart>",
			f"<StNr>{elster_tax_number}</StNr>",
			"<Zeitraum>2026</Zeitraum>",
		):
			with self.subTest(element=element):
				self.assertIn(element, nutzdaten)
		self.assertEqual(doc.elster_state()["printout"], "Freizeichnungsdokument")

	def test_prints_gewst_1_a_and_the_anlage_beg_and_says_that_the_forms_are_provisional(self):
		doc = self.calculated()
		html = frappe.get_print(DOCTYPE, doc.name, "Gewerbesteuererklärung")
		for text in (
			"Gewerbesteuererklärung 2026",
			"vorläufig (Jahresdokumentation 2025)",
			COMPANY,
			doc.corporate_income_tax_return,
			"Softwareentwicklung",
			"Gewinn aus Gewerbebetrieb",
			"97.200",
			"11.400",
			"Beta GmbH",
			"15.064,00",
			HEBESATZ_SOURCE,
		):
			with self.subTest(text=text):
				self.assertIn(text, html)
		self.assertLess(html.index(">GewSt 1 A</td>"), html.index(">Anlage BEG</td>"))
