"""The Umsatzsteuererklärung on the Frappe test site.

A company that files quarterly until September and monthly from October 2026, with Dauerfristverlängerung and a
Sondervorauszahlung of 1,200 euros, books a sale in each quarter and in October, a Vorsteuer in the second quarter, a
Dreiecksgeschäft as first buyer in the third quarter (Kz 742 and Kz 789) and a Berichtigung under § 15a UStG in
December. It files each Voranmeldung in Mein ELSTER; the second quarter gets a sale after its filing and a corrected
Voranmeldung, December a sale after its filing. The payments of the Sondervorauszahlung and of the first quarter are
booked on 1781 and 1780. A second company files monthly and has filed January alone, with the day of a switch to the
Regelbesteuerung in Kz 70. Every name, number and amount is invented.
"""

from datetime import date
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, getdate

from steuerbote.deadlines import Kind, annual_obligations
from steuerbote.eric.result import Outcome
from steuerbote.steuerbote import deadlines
from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	insert_record,
	make_account,
	make_company,
	make_customer,
	make_mapping,
	make_settings,
	make_user,
	post_journal_entry,
	post_ledger,
	post_purchase_invoice,
	post_sales_invoice,
)
from steuerbote.tests.transmitting import TRANSMISSION, Transmitting

# The companies, their accounts, Fiscal Years, Voranmeldungen and users are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Account",
	"Annual VAT Return",
	"Company",
	"DocType",
	"Fiscal Year",
	"User",
	"VAT Return",
]

DOCTYPE = "Annual VAT Return"
COMPANY = "Steuerbote Test USt-Erklärung GmbH"
ABBR = "STUE"
MONTHLY_COMPANY = "Steuerbote Test USt-Erklärung Monatlich GmbH"
MONTHLY_ABBR = "STUM"
CUSTOMER = "Musterkunde Jahreserklärung GmbH"
EU_CUSTOMER = "Alpen Handel Jahreserklärung GmbH"
SUPPLIER = "Musterlieferant Jahreserklärung GmbH"
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"8130": ("Lieferungen des ersten Abnehmers bei innergemeinschaftlichen Dreiecksgeschäften", "Income"),
	"2700": ("Sonstige Erträge", "Income"),
	"3552": ("Erwerb 1. Abnehmer innerhalb eines Dreiecksgeschäftes", "Expense"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1558": ("Berichtigung des Vorsteuerabzugs § 15a UStG", "Asset"),
	"1780": ("Umsatzsteuer-Vorauszahlungen", "Liability"),
	"1781": ("Umsatzsteuer-Vorauszahlungen 1/11", "Liability"),
	"1200": ("Bank", "Asset"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
	"1600": ("Verbindlichkeiten aus Lieferungen und Leistungen", "Liability"),
}
ADDRESS = {
	"street": "Musterweg",
	"house_number": "12",
	"postal_code": "80331",
	"city": "München",
	"country": "Germany",
}
FILED_IN_MEIN_ELSTER = "mein_elster"
REASON = "Gutschrift vom 30. Dezember 2026, gebucht im Januar"
# The day the return is noted as filed in the tests, a Monday; the Abschlusszahlung is due a month later.
FILED_ON = "2026-11-02"


def money(value) -> Decimal:
	return Decimal(str(flt(value, 2))).quantize(Decimal("0.01"))


def file_vat_return(company: str, rhythm: str, index: int, **fields) -> str:
	"""Calculate the Voranmeldung of a period and note its filing in Mein ELSTER, with remarks for a period that had
	not ended when it was calculated; returns its name."""
	doc = frappe.get_doc(
		{
			"doctype": "VAT Return",
			"company": company,
			"year": 2026,
			"rhythm": rhythm,
			"period_index": index,
			"remarks": "Erfunden: abgegeben in Mein ELSTER.",
			**fields,
		}
	).insert()
	doc.calculate()
	doc.reload()
	doc.mark_filed_outside(filed_via=FILED_IN_MEIN_ELSTER)
	return doc.name


def sale(company: str, accounts: dict, name: str, posting_date: str, net: int, tax: int) -> None:
	a = accounts
	post_sales_invoice(
		company,
		name,
		CUSTOMER,
		posting_date,
		[(a["1400"], net + tax, 0), (a["8400"], 0, net), (a["1776"], 0, tax)],
	)


class TestAnnualVATReturn(Transmitting, IntegrationTestCase):
	"""One class, so that the ledger and the Voranmeldungen of the year are made once; each test removes its returns."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, ABBR)
		cls.account = a = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		for year in (2026, 2027):
			ensure_fiscal_year(COMPANY, date(year, 6, 30))
		make_settings(
			COMPANY,
			[(2026, "quarterly", 1), (2026, "monthly", 10)],
			[(2026, True, "1200.00")],
			street="Musterweg 12",
			postal_code="80331",
			city="München",
		)
		make_mapping(COMPANY)
		frappe.get_doc(
			{"doctype": "Annual Filing Settings", "company": COMPANY, "legal_form": "GmbH", **ADDRESS}
		).insert(ignore_permissions=True)
		for name, country, vat_id in ((CUSTOMER, "Germany", None), (EU_CUSTOMER, "Austria", "ATU12345678")):
			if not frappe.db.exists("Customer", name):
				make_customer(name, country, vat_id)
		if not frappe.db.exists("Supplier", SUPPLIER):
			insert_record("Supplier", name=SUPPLIER, supplier_name=SUPPLIER, country="Germany")

		sale(COMPANY, a, "SINV-STUE-1", "2026-02-10", 1000, 190)
		file_vat_return(COMPANY, "quarterly", 1)
		sale(COMPANY, a, "SINV-STUE-2", "2026-05-10", 2000, 380)
		post_purchase_invoice(
			COMPANY, "PINV-STUE-1", SUPPLIER, "2026-05-20", [(a["1576"], 95, 0), (a["1600"], 0, 95)]
		)
		cls.first_q2 = file_vat_return(COMPANY, "quarterly", 2)
		sale(COMPANY, a, "SINV-STUE-3", "2026-06-15", 300, 57)
		cls.corrected_q2 = file_vat_return(COMPANY, "quarterly", 2, is_correction=1)
		post_purchase_invoice(
			COMPANY, "PINV-STUE-2", SUPPLIER, "2026-08-10", [(a["3552"], 1000, 0), (a["1600"], 0, 1000)]
		)
		post_sales_invoice(
			COMPANY, "SINV-STUE-4", EU_CUSTOMER, "2026-08-10", [(a["1400"], 1200, 0), (a["8130"], 0, 1200)]
		)
		file_vat_return(COMPANY, "quarterly", 3)
		sale(COMPANY, a, "SINV-STUE-5", "2026-10-12", 500, 95)
		file_vat_return(COMPANY, "monthly", 10)
		file_vat_return(COMPANY, "monthly", 11)
		cls.section_15a = post_journal_entry(
			COMPANY, "2026-12-05", [(a["1558"], 120, 0), (a["2700"], 0, 120)]
		)
		cls.december = file_vat_return(COMPANY, "monthly", 12)
		sale(COMPANY, a, "SINV-STUE-6", "2026-12-28", 100, 19)
		post_journal_entry(COMPANY, "2026-02-10", [(a["1781"], 1200, 0), (a["1200"], 0, 1200)])
		post_journal_entry(COMPANY, "2026-05-11", [(a["1780"], 190, 0), (a["1200"], 0, 190)])

		make_company(MONTHLY_COMPANY, MONTHLY_ABBR)
		for number in ("8400", "1776", "1576"):
			name, root_type = ACCOUNTS[number]
			make_account(MONTHLY_COMPANY, number, name, root_type)
		ensure_fiscal_year(MONTHLY_COMPANY, date(2026, 6, 30))
		make_settings(MONTHLY_COMPANY, [(2026, "monthly", 1)])
		make_mapping(MONTHLY_COMPANY)
		frappe.get_doc(
			{"doctype": "Annual Filing Settings", "company": MONTHLY_COMPANY, "legal_form": "GmbH", **ADDRESS}
		).insert(ignore_permissions=True)
		file_vat_return(MONTHLY_COMPANY, "monthly", 1, regelbesteuerung_from="2026-01-15")

	def setUp(self):
		super().setUp()
		self.addCleanup(self.discard_returns)

	def discard_returns(self):
		"""Take the returns of the tests out with their ELSTER Transmissions: a filed one cannot be cancelled."""
		frappe.db.delete(TRANSMISSION, {"document_type": DOCTYPE})
		for name in frappe.get_all(DOCTYPE, pluck="name"):
			frappe.db.set_value(DOCTYPE, name, "docstatus", 2, update_modified=False)
			frappe.delete_doc(DOCTYPE, name, force=True, ignore_permissions=True)

	def new_return(self, company: str = COMPANY, **fields):
		return frappe.get_doc({"doctype": DOCTYPE, "company": company, "year": 2026, **fields}).insert()

	def calculated(self, company: str = COMPANY, **fields):
		doc = self.new_return(company, **fields)
		doc.calculate()
		doc.reload()
		return doc

	def lines(self, doc) -> dict[str, tuple]:
		return {
			row.feldkennung: (money(row.form_amount), money(row.reported), row.manual)
			for row in doc.lines
			if not row.manual
		}

	def codes(self, doc) -> list[str]:
		return [row.code for row in doc.findings]

	def test_computes_the_lines_of_the_year_from_the_ledger_and_is_ready(self):
		doc = self.calculated()
		self.assertEqual(
			self.lines(doc),
			{
				"E3003303": (Decimal("3900.00"), Decimal("3900.00"), 0),
				"E3003304": (Decimal("741.00"), Decimal("741.00"), 0),
				"E3100801": (Decimal("1000.00"), Decimal("1000.00"), 0),
				"E3101801": (Decimal("1200.00"), Decimal("1200.00"), 0),
				"E3006201": (Decimal("95.00"), Decimal("95.00"), 0),
				"E3008701": (Decimal("120.00"), Decimal("120.00"), 0),
			},
		)
		self.assertEqual((doc.status, doc.ready), ("Bereit", 1))
		row = next(row for row in doc.lines if row.feldkennung == "E3100801")
		self.assertEqual((row.kennzahl, row.line, row.ustva), ("789", 55, ""))

	def test_sums_up_the_form_and_sets_line_125_from_the_filed_voranmeldungen_and_the_sondervorauszahlung(
		self,
	):
		doc = self.calculated()
		self.assertEqual(
			[
				money(doc.get(field))
				for field in ("soll_voranmeldungen", "soll_credited", "sondervorauszahlung")
			],
			[Decimal("-693.00"), Decimal("1200.00"), Decimal("1200.00")],
		)
		self.assertEqual(
			[money(doc.get(field)) for field in ("soll_computed", "vorauszahlungssoll", "kz816", "kz820")],
			[Decimal("507.00"), Decimal("507.00"), Decimal("526.00"), Decimal("19.00")],
		)
		self.assertEqual(
			[money(doc.get(field)) for field in ("line_41", "line_93", "line_108_deductible", "line_117")],
			[Decimal("741.00"), Decimal("95.00"), Decimal("120.00"), Decimal("526.00")],
		)
		self.assertEqual(money(doc.line_62), Decimal("0.00"))

	def test_lists_each_period_with_its_latest_filing_and_the_late_posting_of_december(self):
		doc = self.calculated()
		self.assertEqual(
			[(row.period_code, row.vat_return, row.due, row.cause) for row in doc.periods],
			[
				(
					"41",
					frappe.db.get_value("VAT Return", {"company": COMPANY, "period_code": "41"}),
					1,
					"No Difference",
				),
				("42", self.corrected_q2, 1, "No Difference"),
				(
					"43",
					frappe.db.get_value("VAT Return", {"company": COMPANY, "period_code": "43"}),
					1,
					"No Difference",
				),
				(
					"10",
					frappe.db.get_value("VAT Return", {"company": COMPANY, "period_code": "10"}),
					1,
					"No Difference",
				),
				(
					"11",
					frappe.db.get_value("VAT Return", {"company": COMPANY, "period_code": "11"}),
					1,
					"No Difference",
				),
				("12", self.december, 1, "Late Postings"),
			],
		)
		december = doc.periods[-1]
		self.assertEqual(
			[money(december.get(field)) for field in ("kz83", "kz39", "kz83_now", "difference", "late")],
			[
				Decimal("-1320.00"),
				Decimal("1200.00"),
				Decimal("-1301.00"),
				Decimal("19.00"),
				Decimal("19.00"),
			],
		)
		self.assertEqual(frappe.db.get_value("VAT Return", self.first_q2, "status"), "Ersetzt")

	def test_explains_the_difference_of_each_kennzahl_and_of_kz_820(self):
		doc = self.calculated()
		rows = {row.kennzahl: row for row in doc.reconciliation}
		self.assertEqual(list(rows), ["81", "42", "66", "64", "820"])
		self.assertEqual(
			[money(rows["81"].get(field)) for field in ("filed", "annual", "late", "rest")],
			[Decimal("3800.00"), Decimal("3900.00"), Decimal("100.00"), Decimal("0.00")],
		)
		self.assertEqual(
			[money(rows["820"].get(field)) for field in ("annual", "late", "rest")],
			[Decimal("19.00"), Decimal("19.00"), Decimal("0.00")],
		)

	def test_gives_the_hints_of_the_year_and_no_error(self):
		doc = self.calculated()
		codes = self.codes(doc)
		for code in (
			"ZAHLUNGEN",
			"BUCHUNG-NACH-ABGABE",
			"VORSTEUER-RECHNUNG",
			"JOURNALBUCHUNG-STEUERKONTO",
			"30926",
		):
			with self.subTest(code=code):
				self.assertIn(code, codes)
		self.assertEqual([row.code for row in doc.findings if row.blocking], [])
		(payments,) = (row for row in doc.findings if row.code == "ZAHLUNGEN")
		self.assertIn("1.390,00", payments.text)
		(journal,) = (row for row in doc.findings if row.code == "JOURNALBUCHUNG-STEUERKONTO")
		self.assertIn(self.section_15a.name, journal.text)
		self.assertTrue(all(row.severity == "Hinweis" for row in doc.findings))

	def test_a_reclassification_of_the_vorauszahlungen_to_the_umsatzsteuer_of_a_year_is_no_payment(self):
		"""Bringing the Vorauszahlungen of the year before to „Umsatzsteuer Vorjahr“ at the start of the year moves no
		money to or from the Finanzamt, so the payments the hint ZAHLUNGEN names stay as they are."""
		prior = make_account(COMPANY, "1790", "Umsatzsteuerverbindlichkeiten Vorjahr", "Liability")
		self.addCleanup(frappe.db.delete, "GL Entry", {"voucher_no": "JV-STUE-VORTRAG"})
		post_ledger(
			COMPANY,
			"Journal Entry",
			"JV-STUE-VORTRAG",
			"2026-01-01",
			[(self.account["1780"], 0, 700), (self.account["1781"], 0, 300), (prior, 1000, 0)],
		)
		(payments,) = (row for row in self.calculated().findings if row.code == "ZAHLUNGEN")
		self.assertIn("1.390,00", payments.text)

	def test_the_verprobung_of_the_year_fills_its_table(self):
		doc = self.calculated()
		(check,) = doc.checks
		self.assertEqual(
			(check.label, money(check.booked_tax), check.passed), ("Umsatzsteuer 19 %", Decimal("741.00"), 1)
		)
		self.assertEqual((doc.deviations, doc.unmapped), ([], []))

	def test_is_due_seven_months_after_the_year_or_with_a_steuerberatung_in_february_of_the_second(self):
		doc = self.new_return()
		self.assertEqual(getdate(doc.deadline), date(2027, 8, 2))
		settings = frappe.get_doc("Annual Filing Settings", COMPANY)
		settings.append("years", {"year": 2026, "advisor_prepares": 1})
		settings.update(
			{
				"advisor_name": "Steuerkanzlei Beispiel",
				"advisor_street": "Kanzleiweg 2",
				"advisor_town": "80331 München",
			}
		)
		settings.save()
		self.addCleanup(self.forget_the_steuerberatung)
		doc.reload()
		doc.save()
		self.assertEqual(getdate(doc.deadline), date(2028, 2, 29))

	def test_a_year_the_settings_state_no_return_for_has_none_and_no_deadline(self):
		"""The company states, with its Steuerberatung, that it owes no Umsatzsteuererklärung for the year, such as a
		holding that is no Unternehmer (§ 2 UStG); Steuerbote takes the statement as given."""
		settings = frappe.get_doc("Annual Filing Settings", COMPANY)
		settings.append("years", {"year": 2026, "no_vat_return": 1})
		with self.assertRaisesRegex(
			frappe.ValidationError, "needs one of the reasons|braucht einen der Gründe"
		):
			settings.save()
		settings = frappe.get_doc("Annual Filing Settings", COMPANY)
		settings.append(
			"years",
			{"year": 2026, "no_vat_return": 1, "no_vat_return_reason": "Not an Unternehmer (§ 2 UStG)"},
		)
		settings.save()
		self.addCleanup(self.forget_the_steuerberatung)
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"owes no Umsatzsteuererklärung for 2026|keine Umsatzsteuererklärung für 2026",
		):
			self.new_return()
		rules = deadlines.annual_rules(COMPANY)
		self.assertNotIn(
			Kind.UMSATZSTEUERERKLAERUNG,
			[item.kind for item in annual_obligations(rules, date(2027, 12, 31))],
		)

	def forget_the_steuerberatung(self):
		settings = frappe.get_doc("Annual Filing Settings", COMPANY)
		settings.set("years", [])
		settings.update({"advisor_name": None, "advisor_street": None, "advisor_town": None})
		settings.save()

	def test_a_due_period_without_a_filed_voranmeldung_holds_the_return_until_its_row_gives_a_reason(self):
		doc = self.calculated(MONTHLY_COMPANY)
		self.assertEqual((doc.status, self.codes(doc).count("ZEITRAUM-FEHLT")), ("Berechnet", 11))
		self.assertIn("SB-KZ136", self.codes(doc))
		for row in doc.periods:
			if row.cause == "Not Filed":
				row.waiver_reason = "Vom Finanzamt nicht verlangt, siehe Schreiben vom 12. Januar 2026"
			row.kz83 = 999
		doc.save()
		doc.reload()
		self.assertEqual(sum(money(row.kz83) for row in doc.periods), Decimal("0.00"))
		self.assertIn("SB-NEU-BERECHNEN", self.codes(doc))
		doc.calculate()
		doc.reload()
		self.assertNotIn("ZEITRAUM-FEHLT", self.codes(doc))
		self.assertEqual((doc.status, doc.ready), ("Bereit", 1))
		self.assertEqual(len([row for row in doc.periods if row.waiver_reason]), 11)

	def test_the_soll_of_the_finanzamt_replaces_the_computed_one_with_its_reason(self):
		doc = self.calculated()
		doc.update({"soll_override": 600, "soll_override_reason": "Bescheid vom 3. März 2027"})
		doc.save()
		self.assertEqual(
			(money(doc.vorauszahlungssoll), money(doc.kz820)), (Decimal("600.00"), Decimal("-74.00"))
		)
		self.assertEqual(doc.status, "Berechnet")
		self.assertIn("SB-NEU-BERECHNEN", self.codes(doc))
		doc.calculate()
		doc.reload()
		self.assertIn("SOLL-UEBERSCHRIEBEN", self.codes(doc))
		self.assertEqual(doc.status, "Bereit")

	def test_an_amount_of_the_soll_without_a_reason_is_refused(self):
		doc = self.calculated()
		doc.soll_override = 600
		with self.assertRaisesRegex(frappe.ValidationError, "Vorauszahlungssoll needs a reason"):
			doc.save()

	def test_a_line_by_hand_names_its_field_by_its_kennzahl_and_berechnen_takes_it_in(self):
		doc = self.calculated()
		doc.append("lines", {"feldkennung": "320", "correction": 5, "correction_reason": REASON})
		doc.save()
		manual = next(row for row in doc.lines if row.manual)
		self.assertEqual((manual.feldkennung, manual.kennzahl, manual.line), ("E3006201", "320", 85))
		self.assertEqual(doc.status, "Berechnet")
		doc.calculate()
		doc.reload()
		self.assertEqual(self.lines(doc)["E3006201"][0], Decimal("100.00"))
		self.assertEqual(money(doc.kz816), Decimal("521.00"))
		rows = {row.kennzahl: row for row in doc.reconciliation}
		self.assertEqual(
			(money(rows["66"].annual_only), money(rows["66"].rest)), (Decimal("5.00"), Decimal("0.00"))
		)

	def test_a_line_by_hand_of_a_field_the_ledger_does_not_feed_is_refused(self):
		doc = self.calculated()
		doc.append("lines", {"feldkennung": "E3006001", "correction": 5, "correction_reason": REASON})
		with self.assertRaisesRegex(frappe.ValidationError, "No line by hand can give field E3006001"):
			doc.save()

	def test_a_correction_with_its_reason_files_another_amount_and_berechnen_keeps_it(self):
		doc = self.calculated()
		row = next(row for row in doc.lines if row.feldkennung == "E3101801")
		row.update({"correction": 1300, "correction_reason": REASON})
		doc.save()
		doc.calculate()
		doc.reload()
		self.assertEqual(self.lines(doc)["E3101801"], (Decimal("1200.00"), Decimal("1300.00"), 0))

	def test_grundstuecke_go_with_kz_370(self):
		doc = self.calculated()
		grundstueck = {"location": "Musterweg 12, München", "first_use": "2026-03-01", "extent_of_use": 60}
		doc.append("properties", grundstueck)
		with self.assertRaisesRegex(frappe.ValidationError, "tick Kz 370"):
			doc.save()
		doc.reload()
		doc.append("properties", grundstueck)
		doc.kz370 = 1
		doc.save()
		self.assertEqual((len(doc.properties), doc.status), (1, "Berechnet"))

	def test_a_statement_after_berechnen_asks_for_berechnen_again(self):
		doc = self.calculated()
		doc.kz129 = 1
		doc.save()
		self.assertEqual((doc.status, doc.ready), ("Berechnet", 0))
		self.assertIn("SB-NEU-BERECHNEN", self.codes(doc))
		doc.calculate()
		doc.reload()
		self.assertIn("30011", self.codes(doc))

	def test_a_year_without_its_form_is_refused(self):
		ensure_fiscal_year(COMPANY, date(2027, 6, 30))
		with self.assertRaisesRegex(frappe.ValidationError, "Steuerbote has no form USt 2 A for 2027 yet"):
			self.new_return(year=2027)

	def test_filed_in_mein_elster_it_is_abgegeben_and_its_abschlusszahlung_due_a_month_later(self):
		doc = self.calculated()
		doc.mark_filed_outside(FILED_IN_MEIN_ELSTER, filed_on=FILED_ON)
		doc.reload()
		self.assertEqual((doc.docstatus, doc.status, doc.filed_via), (1, "Abgegeben", FILED_IN_MEIN_ELSTER))
		self.assertEqual(getdate(doc.payment_due), date(2026, 12, 2))

	def test_a_berichtigung_files_kz_110_with_the_kz_816_of_the_return_it_corrects_as_its_soll(self):
		doc = self.calculated()
		doc.mark_filed_outside(FILED_IN_MEIN_ELSTER, filed_on=FILED_ON)
		correction = frappe.get_doc(DOCTYPE, doc.make_correction())
		self.assertEqual((correction.is_correction, correction.corrects), (1, doc.name))
		self.assertEqual(
			[money(correction.get(field)) for field in ("soll_computed", "vorauszahlungssoll", "kz820")],
			[Decimal("526.00"), Decimal("526.00"), Decimal("0.00")],
		)
		self.assertIn("30002", self.codes(correction))
		correction.mark_filed_outside(FILED_IN_MEIN_ELSTER, filed_on=FILED_ON)
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "status"), "Ersetzt")
		self.assertIsNone(frappe.db.get_value(DOCTYPE, correction.name, "payment_due"))

	def test_pruefen_in_the_simulation_checks_e50_with_the_vorsatz(self):
		doc = self.calculated()
		transmission, _, run = self.transmitted(doc, "validate")
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.simulated),
			("Erfolgreich", Outcome.VALID.value, 1),
		)
		_, nutzdaten, header, *_ = run.call_args.args
		self.assertEqual(header.datenart_version, "USt_2026")
		for element in (
			"<E3003303>3900</E3003303>",
			"<E3003304>741,00</E3003304>",
			"<E3100801>1000</E3100801>",
			"<E3011301>507,00</E3011301>",
			"<E3011401>19,00</E3011401>",
			"<E3002203>1</E3002203>",
			"<E3000901>Steuerbote Test USt-Erklärung GmbH</E3000901>",
			"<Unterfallart>50</Unterfallart>",
			"<Zeitraum>2026</Zeitraum>",
		):
			with self.subTest(element=element):
				self.assertIn(element, nutzdaten)
		self.assertEqual(doc.elster_state()["printout"], "Freizeichnungsdokument")

	def test_an_accounts_user_calculates_but_does_not_file(self):
		user = make_user("steuerbote-test-uste-buchhaltung@example.com", "Accounts User")
		doc = self.new_return()
		frappe.set_user(user)
		try:
			doc = frappe.get_doc(DOCTYPE, doc.name)
			doc.calculate()
			with self.assertRaises(frappe.PermissionError):
				doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
		finally:
			frappe.set_user("Administrator")

	def test_prints_the_return_in_the_order_and_wording_of_the_form(self):
		doc = self.calculated()
		html = frappe.get_print(DOCTYPE, doc.name, "Umsatzsteuererklärung")
		for text in (
			"Umsatzsteuererklärung 2026",
			COMPANY,
			"A. Allgemeine Angaben",
			"K. Berechnung der zu entrichtenden Umsatzsteuer",
			"Lieferungen und sonstige Leistungen zu 19 %",
			"3.900",
			"741,00",
			"Keine Eintragungen",
			"Abgleich je Voranmeldungszeitraum",
			"spätere Buchungen",
			"Zum Abgleich mit der Steuerberatung oder zum Übertragen in Mein ELSTER.",
		):
			with self.subTest(text=text):
				self.assertIn(text, html)
		self.assertLess(html.index("B. Steuerpflichtige"), html.index("C. Steuerfreie"))
		self.assertLess(html.index("J. Berichtigung"), html.index("K. Berechnung"))
