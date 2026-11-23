"""The E-Bilanz on the Frappe test site, with the invented company of steuerbote/tests/ebilanz.py and the HGB-Taxonomie
6.9 installed as „Taxonomie einrichten“ installs it: Berechnen of the short first Wirtschaftsjahr from the books, the
assets and the Balance Sheet Mapping, „Bereit“ and each check that holds it back, the Eröffnungsbilanz, the
Handelsbilanz with the Überleitungsrechnung of the finance book of the Steuerbilanz, corrections and lines by hand,
Prüfen in the simulation, XBRL exportieren, the filing and the Berichtigung, the print and the report E-Bilanz
Positionen. Every name, number and amount is invented.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from steuerbote import ebilanz_sources
from steuerbote.eric.result import Outcome
from steuerbote.eric.runtime import Check
from steuerbote.eric.simulation import bilanz as simulated_bilanz
from steuerbote.steuerbote.report.e_bilanz_positionen import e_bilanz_positionen
from steuerbote.tests.ebilanz import (
	COMPANY,
	DOCTYPE,
	DROHVERLUST,
	END,
	FISCAL_YEAR,
	FOUNDED,
	LAPTOP,
	PERIOD_CLOSING_VOUCHER,
	PERIOD_CLOSING_VOUCHER_DOCTYPE,
	SETTINGS,
	TAX_BOOK,
	YEAR,
	blocking_codes,
	configured,
	discard_documents,
	filed_voranmeldung,
	finding_codes,
	make_company_with_books,
	make_mapping,
	make_schedule,
	money,
	new_document,
	post_for_the_test,
	set_for_the_test,
	taxonomy_root,
)
from steuerbote.tests.helpers import make_user
from steuerbote.tests.transmitting import Transmitting

# The company, its accounts, Fiscal Years, assets and users are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Account",
	"Asset Category",
	"Company",
	"DocType",
	"Electronic Balance Sheet",
	"Finance Book",
	"Fiscal Year",
	"User",
]

BANK = "bs.ass.currAss.cashEquiv.bank"
SALES = "is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales"
OTHER_COSTS = "is.netIncome.regular.operatingTC.otherCost.otherOrdinary"
IMMINENT_LOSS = "bs.eqLiab.accruals.other.imminentLoss"
OFFICE = "Steuerbote Test Büroausstattung"
FILED_NOTE = (
	"Am 15. Mai 2027 durch die Steuerberatung übermittelt, das Übertragungsprotokoll liegt in den Unterlagen."
)
REASON = "Rechnung der Steuerberatung vom 20. Januar 2027 für das Jahr 2026"
IMPAIRMENT = "Wertminderung des Laptops nach einem Wasserschaden am 30. November 2026"


def d(value: str) -> Decimal:
	return Decimal(value)


# The totals of the short first Wirtschaftsjahr: Bilanzsumme, Jahresüberschuss and Betriebsvermögen.
TOTALS = {
	"total_assets": d("61780.00"),
	"total_equity_and_liabilities": d("61780.00"),
	"net_income": d("35280.00"),
	"tax_net_income": d("35280.00"),
	"tax_equity": d("60280.00"),
}
# What a position of the Bilanz and of the GuV reports.
POSITIONS = {
	"bs.ass": d("61780.00"),
	"bs.ass.fixAss.intan.concessionBrands": d("1120.00"),
	"bs.ass.fixAss.tan.landBuildings.landWithoutBuildings": d("10000.00"),
	"bs.ass.fixAss.tan.otherEquipm.office": d("2700.00"),
	BANK: d("47960.00"),
	"bs.eqLiab.equity.subscribed.corp": d("25000.00"),
	"bs.eqLiab.equity.netIncome": d("35280.00"),
	"bs.eqLiab.accruals.other.other": d("1500.00"),
	SALES: d("50000.00"),
	"is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.other": d("900.00"),
	"is.netIncome.regular.operatingTC.otherCost.leaseFix.other": d("12000.00"),
	"is.netIncome": d("35280.00"),
	"BVV.profitLoss.contribution": d("25000.00"),
	"BVV.profitLoss.assetsCurrentYear": d("60280.00"),
}


class TestElectronicBalanceSheet(Transmitting, IntegrationTestCase):
	"""One class, so that the company and its books are made once; each test removes its E-Bilanzen and takes back
	what it changed."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = taxonomy_root()
		cls.account = make_company_with_books()
		make_mapping(cls.account)

	def setUp(self):
		self.enterContext(configured(self.root))
		super().setUp()
		self.addCleanup(discard_documents)
		# Prüfen registers the installed taxonomy with the simulation for the whole process, in which the core tests
		# that follow this class check their E-Bilanzen without one.
		self.addCleanup(simulated_bilanz.unregister_taxonomy, "6.9")

	def calculated(self, **fields):
		doc = new_document(**fields)
		doc.calculate()
		doc.reload()
		return doc

	def row(self, doc, concept: str):
		(row,) = (row for row in doc.positions if row.concept == concept and not row.manual)
		return row

	# Berechnen.

	def test_berechnen_reports_the_short_first_wirtschaftsjahr_and_is_ready(self):
		doc = self.calculated()
		self.assertEqual((doc.status, doc.ready, finding_codes(doc)), ("Bereit", 1, []))
		self.assertEqual(
			(doc.fiscal_year, getdate(doc.from_date), getdate(doc.to_date), getdate(doc.stichtag)),
			(FISCAL_YEAR, FOUNDED, END, END),
		)
		self.assertEqual({field: money(doc.get(field)) for field in TOTALS}, TOTALS)
		self.assertEqual(
			(doc.first_fiscal_year, money(doc.bvv_previous_equity), money(doc.bvv_founding_contribution)),
			(1, d("0.00"), d("25000.00")),
		)
		self.assertEqual(
			(doc.revision_status, doc.accounting_standard, doc.taxonomy_version), ("E", "HAOE", "6.9")
		)

	def test_is_due_with_the_koerperschaftsteuererklaerung_of_the_year(self):
		"""FAQ zur E-Bilanz, Tz. 5: seven months after the year, moved to the next working day."""
		self.assertEqual(getdate(new_document().deadline), date(2027, 8, 2))

	def test_the_positions_report_the_books_with_the_labels_of_the_taxonomy(self):
		doc = self.calculated()
		for concept, amount in POSITIONS.items():
			with self.subTest(concept=concept):
				self.assertEqual(money(self.row(doc, concept).reported), amount)
		bank = self.row(doc, BANK)
		self.assertEqual(
			(bank.label, bank.component, bank.mark, bank.parent_concept, bank.nil),
			(
				"Kassenbestand, Bundesbankguthaben, Guthaben bei Kreditinstituten und Schecks; Guthaben bei "
				"Kreditinstituten",
				"B",
				"rechnerisch notwendig",
				"bs.ass.currAss.cashEquiv",
				0,
			),
		)
		profit = self.row(doc, "bs.eqLiab.equity.profitLoss")
		self.assertEqual((profit.mark, profit.nil, money(profit.reported)), ("Muss", 1, d("0.00")))
		self.assertEqual(
			(self.row(doc, SALES).component, self.row(doc, "BVV.profitLoss.contribution").component),
			("GuV", "BVV"),
		)

	def test_the_kontensalden_name_each_account_on_its_position_in_its_direction(self):
		doc = self.calculated()
		a = self.account
		self.assertEqual(
			[(row.position, row.account, money(row.amount)) for row in doc.accounts],
			[
				("bs.ass.fixAss.intan.concessionBrands", a["0135"], d("1440.00")),
				("bs.ass.fixAss.intan.concessionBrands", a["0136"], d("-320.00")),
				("bs.ass.fixAss.tan.landBuildings.landWithoutBuildings", a["0215"], d("10000.00")),
				("bs.ass.fixAss.tan.otherEquipm.office", a["0650"], d("3600.00")),
				("bs.ass.fixAss.tan.otherEquipm.office", a["0651"], d("-900.00")),
				(BANK, a["1800"], d("47960.00")),
				("bs.eqLiab.equity.subscribed.corp", a["2900"], d("25000.00")),
				("bs.eqLiab.accruals.other.other", a["3070"], d("1500.00")),
				(f"{SALES}.grossSales.generalRateVAT", a["4400"], d("50000.00")),
				("is.netIncome.regular.operatingTC.deprAmort.fixAss.otherIntan", a["6200"], d("320.00")),
				("is.netIncome.regular.operatingTC.deprAmort.fixAss.tan.other", a["6220"], d("900.00")),
				("is.netIncome.regular.operatingTC.otherCost.leaseFix.other", a["6310"], d("12000.00")),
				("is.netIncome.regular.operatingTC.otherCost.legalConsulting", a["6827"], d("1500.00")),
			],
		)
		self.assertEqual([row.account_number for row in doc.accounts][:2], ["0135", "0136"])

	def test_the_anlagenspiegel_has_a_row_per_category_of_the_assets(self):
		doc = self.calculated()
		self.assertEqual(
			[
				(
					row.asset_category,
					row.value_type,
					row.position,
					money(row.additions),
					money(row.depreciation_regular),
					money(row.cost_end),
					money(row.book_value_end),
					row.manual,
				)
				for row in doc.fixed_assets
			],
			[
				(
					OFFICE,
					"StB",
					"bs.ass.fixAss.tan.otherEquipm.office",
					d("3600.00"),
					d("900.00"),
					d("3600.00"),
					d("2700.00"),
					0,
				),
				(
					"Steuerbote Test Grundstücke",
					"StB",
					"bs.ass.fixAss.tan.landBuildings.landWithoutBuildings",
					d("10000.00"),
					d("0.00"),
					d("10000.00"),
					d("10000.00"),
					0,
				),
				(
					"Steuerbote Test Software",
					"StB",
					"bs.ass.fixAss.intan.concessionBrands",
					d("1440.00"),
					d("320.00"),
					d("1440.00"),
					d("1120.00"),
					0,
				),
			],
		)

	# What holds „Bereit“ back.

	def test_an_adjustment_of_erpnext_on_a_fixed_asset_account_waits_for_a_column_by_hand(self):
		"""Leitfaden B.14.12.1: the Anlagenspiegel shows an Asset Value Adjustment as an außerplanmäßige Abschreibung."""
		post_for_the_test(
			self,
			self.account,
			"STEB-WERTMINDERUNG",
			"2026-11-30",
			(("6230", 300, 0), ("0650", 0, 300)),
			voucher_type="Asset Value Adjustment",
			against=LAPTOP,
		)
		doc = self.calculated()
		self.assertIn("SB-ANLAGE-ANPASSUNG", blocking_codes(doc))
		(office,) = (row for row in doc.fixed_assets if row.asset_category == OFFICE)
		self.assertEqual(money(office.erp_adjustment), d("-300.00"))
		office.depreciation_extraordinary = 300
		office.reason = IMPAIRMENT
		doc.save()
		self.assertEqual((doc.status, doc.ready), ("Berechnet", 0))
		self.assertIn("SB-NEU-BERECHNEN", finding_codes(doc))
		doc.calculate()
		doc.reload()
		self.assertEqual((doc.status, doc.ready, finding_codes(doc)), ("Bereit", 1, []))
		(office,) = (row for row in doc.fixed_assets if row.asset_category == OFFICE)
		self.assertEqual(
			(money(office.depreciation_extraordinary), money(office.book_value_end), office.reason),
			(d("300.00"), d("2400.00"), IMPAIRMENT),
		)

	def test_the_depreciation_of_the_schedule_up_to_the_stichtag_is_posted(self):
		"""§ 253 Abs. 3 Satz 1 HGB."""
		set_for_the_test(self, "Depreciation Schedule", f"{LAPTOP}-ohne-1", journal_entry=None)
		doc = self.calculated()
		self.assertEqual(blocking_codes(doc), ["SB-AFA-OFFEN"])
		(finding,) = doc.findings
		self.assertEqual(finding.reference, LAPTOP)
		self.assertIn("900,00 € ab dem 31.12.2026", finding.text)

	def test_an_asset_counts_its_depreciation_once_in_each_book(self):
		"""ERPNext counts the entries without a finance book in every book (steuerbote/balances.py)."""
		schedule = make_schedule(LAPTOP, (("2026-12-31", 900, "STEB-AFA-LAPTOP-2026"),), TAX_BOOK)
		self.addCleanup(frappe.db.delete, "Depreciation Schedule", {"parent": schedule})
		self.addCleanup(frappe.db.delete, "Asset Depreciation Schedule", {"name": schedule})
		doc = self.calculated(accounting_standard="HGBM", tax_finance_book=TAX_BOOK)
		self.assertEqual(doc.ready, 0)
		(finding,) = (row for row in doc.findings if row.code == "SB-ANLAGE-DOPPELT")
		self.assertEqual((finding.blocking, finding.reference), (1, LAPTOP))

	def test_a_missing_period_closing_voucher_is_a_hint_only(self):
		set_for_the_test(self, PERIOD_CLOSING_VOUCHER_DOCTYPE, PERIOD_CLOSING_VOUCHER, docstatus=2)
		doc = self.calculated()
		self.assertEqual((doc.status, doc.ready, finding_codes(doc)), ("Bereit", 1, ["SB-PERIODENABSCHLUSS"]))
		self.assertEqual({field: money(doc.get(field)) for field in TOTALS}, TOTALS)

	def test_a_balance_without_a_place_in_the_mapping_holds_it_back(self):
		post_for_the_test(
			self, self.account, "STEB-GELDTRANSIT", "2026-12-30", (("1360", 100, 0), ("1800", 0, 100))
		)
		doc = self.calculated()
		self.assertEqual(doc.ready, 0)
		self.assertIn("BILANZ-OHNE-PLATZ", blocking_codes(doc))
		(finding,) = (row for row in doc.findings if row.code == "BILANZ-OHNE-PLATZ")
		self.assertEqual(finding.reference, "1360")

	def test_the_taxonomy_is_installed_and_unchanged(self):
		changed = (
			Check("taxonomy_6_9", False, "Die HGB-Taxonomie 6.9 weicht vom Manifest ab: package/x.xsd"),
		)
		with patch.object(ebilanz_sources.eric_settings, "taxonomy_status", return_value=changed):
			doc = self.calculated()
		self.assertEqual((doc.ready, blocking_codes(doc)), (0, ["SB-TAXONOMIE"]))
		self.assertIn("weicht vom Manifest ab", doc.findings[0].text)
		with (
			configured(None),
			self.assertRaisesRegex(frappe.ValidationError, "The HGB-Taxonomie 6.9 is not installed"),
		):
			doc.calculate()

	def test_the_gcd_takes_the_address_of_the_settings(self):
		"""Leitfaden B.14.3.1.16; rule 170205051 of the Jahresdokumentation 6.9."""
		set_for_the_test(self, SETTINGS, COMPANY, city=None)
		doc = self.calculated()
		self.assertEqual(doc.ready, 0)
		self.assertIn("170205051", blocking_codes(doc))

	# The kinds of the E-Bilanz.

	def test_an_eroeffnungsbilanz_shows_the_bilanz_on_the_first_day(self):
		"""§ 5b Abs. 1 Satz 4 EStG."""
		doc = self.calculated(statement_type="Eröffnungsbilanz")
		self.assertEqual((doc.status, doc.ready, finding_codes(doc)), ("Bereit", 1, []))
		self.assertEqual(getdate(doc.stichtag), FOUNDED)
		self.assertEqual({row.component for row in doc.positions}, {"B"})
		self.assertEqual(money(self.row(doc, BANK).reported), d("25000.00"))
		self.assertEqual(
			(money(doc.total_assets), money(doc.net_income), money(doc.tax_equity)),
			(d("25000.00"), d("0.00"), d("25000.00")),
		)
		self.assertEqual(doc.fixed_assets, [])
		self.assertEqual(getdate(doc.deadline), date(2027, 8, 2))

	def test_a_handelsbilanz_takes_its_ueberleitung_from_the_finance_book_of_the_steuerbilanz(self):
		"""§ 5b Abs. 1 Satz 2 EStG; Leitfaden A.11, B.15.1; § 5 Abs. 4a EStG keeps the Drohverlustrückstellung out."""
		for voucher_no, rows, book in DROHVERLUST:
			post_for_the_test(self, self.account, voucher_no, "2026-12-31", rows, finance_book=book)
		doc = self.calculated(accounting_standard="HGBM", tax_finance_book=TAX_BOOK)
		self.assertEqual((doc.status, doc.ready, finding_codes(doc)), ("Bereit", 1, []))
		self.assertEqual(
			[
				(row.kind, row.position, money(row.current), money(row.previous), row.derived)
				for row in doc.transfers
			],
			[
				("Wertänderung", IMMINENT_LOSS, d("-2000.00"), d("0.00"), 1),
				("Wertänderung", OTHER_COSTS, d("-2000.00"), d("0.00"), 1),
			],
		)
		self.assertEqual(
			{field: money(doc.get(field)) for field in ("net_income", "tax_net_income", "tax_equity")},
			{"net_income": d("33280.00"), "tax_net_income": d("35280.00"), "tax_equity": d("60280.00")},
		)
		accrual = self.row(doc, IMMINENT_LOSS)
		self.assertEqual((money(accrual.reported), money(accrual.tax_amount)), (d("2000.00"), d("0.00")))
		self.assertEqual({row.value_type for row in doc.fixed_assets}, {"HB"})

	def test_a_key_takes_one_draft(self):
		new_document()
		with self.assertRaises(frappe.ValidationError):
			new_document()
		new_document(statement_type="Eröffnungsbilanz")

	# Corrections and lines by hand.

	def test_a_correction_reports_another_amount_with_its_reason(self):
		doc = self.calculated()
		bank = self.row(doc, BANK)
		bank.correction = 48000
		bank.correction_reason = REASON
		doc.save()
		self.assertIn("SB-NEU-BERECHNEN", finding_codes(doc))
		doc.calculate()
		doc.reload()
		bank = self.row(doc, BANK)
		self.assertEqual(
			(money(bank.computed), money(bank.reported), bank.correction_reason),
			(d("47960.00"), d("48000.00"), REASON),
		)
		self.assertEqual(doc.ready, 0)

	def test_a_line_by_hand_takes_the_label_of_its_position_and_none_berechnen_reports(self):
		doc = self.calculated()
		doc.append(
			"positions",
			{"concept": f"de-gaap-ci:{OTHER_COSTS}", "correction": 500, "correction_reason": REASON},
		)
		doc.save()
		(manual,) = (row for row in doc.positions if row.manual)
		self.assertEqual(
			(manual.concept, manual.component, money(manual.reported)), (OTHER_COSTS, "GuV", d("500.00"))
		)
		self.assertIn("andere ordentliche sonstige betriebliche Aufwendungen", manual.label)
		self.assertIn("SB-NEU-BERECHNEN", finding_codes(doc))
		doc.append("positions", {"concept": BANK, "correction": 1, "correction_reason": REASON})
		with self.assertRaisesRegex(
			frappe.ValidationError, r"Calculate reports bs\.ass\.currAss\.cashEquiv\.bank already"
		):
			doc.save()

	def test_a_change_of_what_berechnen_reads_asks_for_berechnen_again_before_filing(self):
		doc = self.calculated()
		doc.bvv_contributions = 1000
		doc.remarks = FILED_NOTE
		doc.save()
		self.assertEqual((doc.status, doc.ready), ("Berechnet", 0))
		self.assertIn("SB-NEU-BERECHNEN", finding_codes(doc))
		with self.assertRaisesRegex(frappe.ValidationError, "again before filing it"):
			doc.mark_filed_outside(filed_via="other_way", note=FILED_NOTE)

	# Filing.

	def test_pruefen_in_the_simulation_checks_the_e_bilanz_with_the_installed_taxonomy(self):
		doc = self.calculated()
		transmission, _, run = self.transmitted(doc, "validate")
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.simulated),
			("Erfolgreich", Outcome.VALID.value, 1),
		)
		_, nutzdaten, header, *_ = run.call_args.args
		self.assertEqual(header.datenart_version, "Bilanz_6.9")
		for text in (">20261231<", "9123045678901", COMPANY, "de-gaap-ci:bs.ass.currAss.cashEquiv.bank"):
			with self.subTest(text=text):
				self.assertIn(text, nutzdaten)
		(hint,) = (row for row in transmission.messages if row.code == "SIM-001")
		self.assertIn("mit der HGB-Taxonomie 6.9", hint.text)

	def test_xbrl_exportieren_attaches_the_instance_privately(self):
		doc = self.calculated()
		url = doc.export_xbrl()
		file = frappe.get_doc("File", {"file_url": url})
		self.assertEqual(
			(file.is_private, file.attached_to_doctype, file.attached_to_name), (1, DOCTYPE, doc.name)
		)
		self.assertTrue(file.file_name.startswith("E-Bilanz-Steuerbote-Test-E-Bilanz-GmbH-2026-12-31"))
		content = file.get_content()
		text = content.decode() if isinstance(content, bytes) else content
		for part in ("9123045678901", "de-gaap-ci:bs.ass.currAss.cashEquiv.bank", "2026-12-31"):
			with self.subTest(part=part):
				self.assertIn(part, text)
		self.assertEqual(doc.export_xbrl(), url)

	def test_an_e_bilanz_that_is_not_ready_makes_no_file(self):
		post_for_the_test(
			self, self.account, "STEB-GELDTRANSIT", "2026-12-30", (("1360", 100, 0), ("1800", 0, 100))
		)
		doc = self.calculated()
		with self.assertRaises(frappe.ValidationError):
			doc.export_xbrl()

	def test_a_berichtigung_names_its_status_des_berichts_and_replaces_the_filed_e_bilanz(self):
		"""FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d."""
		doc = self.calculated()
		doc.mark_filed_outside(filed_via="other_way", note=FILED_NOTE)
		doc.reload()
		self.assertEqual((doc.status, doc.revision_status, doc.filed_via), ("Abgegeben", "E", "other_way"))
		self.assertEqual(ebilanz_sources.filed_tax_equity(COMPANY, YEAR), d("60280.00"))
		correction = frappe.get_doc(DOCTYPE, doc.make_correction())
		self.assertEqual(
			(correction.is_correction, correction.corrects, correction.status), (1, doc.name, "Bereit")
		)
		with self.assertRaisesRegex(frappe.ValidationError, "names its Status des Berichts"):
			correction.mark_filed_outside(filed_via="other_way", note=FILED_NOTE)
		correction.reload()
		correction.revision_status = "B"
		correction.save()
		correction.mark_filed_outside(filed_via="other_way", note=FILED_NOTE)
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "status"), "Ersetzt")
		self.assertEqual(frappe.db.get_value(DOCTYPE, correction.name, "status"), "Abgegeben")
		self.assertEqual(ebilanz_sources.filed_tax_equity(COMPANY, YEAR), d("60280.00"))

	def test_mein_elster_takes_no_e_bilanz(self):
		"""FAQ zur E-Bilanz, Tz. 9: „nicht möglich und auch nicht geplant“."""
		doc = self.calculated()
		with self.assertRaises(frappe.ValidationError):
			doc.mark_filed_outside(filed_via="mein_elster")

	def test_an_accounts_user_calculates_but_does_not_file(self):
		user = make_user("steuerbote-test-ebilanz-buchhaltung@example.com", "Accounts User")
		doc = new_document()
		frappe.set_user(user)
		try:
			doc = frappe.get_doc(DOCTYPE, doc.name)
			doc.calculate()
			with self.assertRaises(frappe.PermissionError):
				doc.mark_filed_outside(filed_via="other_way", note=FILED_NOTE)
		finally:
			frappe.set_user("Administrator")

	# Print and report.

	def test_prints_the_e_bilanz_with_the_labels_of_the_taxonomy(self):
		doc = self.calculated()
		html = frappe.get_print(DOCTYPE, doc.name, "E-Bilanz")
		for text in (
			"E-Bilanz 2026",
			COMPANY,
			"Bilanzstichtag",
			"31.12.2026",
			"Einheitsbilanz (HAOE)",
			"erstmalig",
			"Aktiva",
			"Passiva",
			"Kassenbestand, Bundesbankguthaben, Guthaben bei Kreditinstituten und Schecks; Guthaben bei Kreditinstituten",
			"47.960,00",
			"61.780,00",
			"Gewinn- und Verlustrechnung (Gesamtkostenverfahren)",
			"Umsatzerlöse (GKV)",
			"Steuerlicher Betriebsvermögensvergleich",
			"Anlagenspiegel (brutto)",
			OFFICE,
			"Kontennachweis",
			"Büroeinrichtung",
			"Zum Abgleich mit der Steuerberatung.",
		):
			with self.subTest(text=text):
				self.assertIn(text, html)
		self.assertNotIn("<h2>Überleitungsrechnung</h2>", html)
		self.assertNotIn("Mein ELSTER", html)

	def test_e_bilanz_positionen_opens_a_position_to_its_accounts(self):
		doc = self.calculated()
		filters = {"company": COMPANY, "year": YEAR, "statement_type": "Jahresabschluss"}
		_columns, rows = e_bilanz_positionen.execute(filters)
		notes = [row["label"] for row in rows if row["key"] is None]
		self.assertEqual(notes[0], f"E-Bilanz {doc.name}, Bereit.")
		self.assertTrue(notes[1].startswith("No Voranmeldung of the year is filed"))
		(bank,) = (row for row in rows if row["key"] == BANK)
		(account,) = (row for row in rows if row["parent_key"] == BANK)
		self.assertEqual(
			(account["account"], account["account_number"], money(account["reported"]), account["indent"]),
			(self.account["1800"], "1800", d("47960.00"), bank["indent"] + 1),
		)
		filed_voranmeldung(self, 9, {"81": 40000})
		_columns, rows = e_bilanz_positionen.execute(filters)
		notes = [row["label"] for row in rows if row["key"] is None]
		self.assertTrue(notes[1].startswith("The Umsatzerlöse of the E-Bilanz are"))
		filed_voranmeldung(self, 10, {"81": 10000})
		_columns, rows = e_bilanz_positionen.execute(filters)
		self.assertEqual([row["label"] for row in rows if row["key"] is None], [notes[0]])
