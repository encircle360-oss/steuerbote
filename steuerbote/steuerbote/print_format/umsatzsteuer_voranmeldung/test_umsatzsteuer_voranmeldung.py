import html
import re

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)

PRINT_FORMAT = "Umsatzsteuer-Voranmeldung"
COMPANY = "Steuerbote Test Druckformat GmbH"

# The SKR03 accounts of the month in VerifiedMonthTest of the core, a bank and a receivables account.
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"8338": ("Erlöse Drittland nicht steuerbar", "Income"),
	"3123": ("Sonstige Leistungen EU 19 %", "Expense"),
	"1787": ("Umsatzsteuer nach § 13b UStG 19 %", "Liability"),
	"1577": ("Vorsteuer nach § 13b UStG 19 %", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1200": ("Bank", "Asset"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}


def cells(markup: str) -> str:
	"""The printed text with every table cell closed by " |", so that a line of the form reads as one string."""
	text = re.sub(r"<(style|script)\b.*?</\1>", " ", markup, flags=re.DOTALL | re.IGNORECASE)
	text = re.sub(r"</t[dh]>", " |", text)
	text = re.sub(r"<br\s*/?>", " ", text)
	text = re.sub(r"<[^>]+>", " ", text)
	return re.sub(r"\s+", " ", html.unescape(text))


class TestUmsatzsteuerVoranmeldung(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STDF")
		a = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(COMPANY, [(2026, "monthly", 1)])
		frappe.db.set_value("VAT Return Settings", COMPANY, "tax_office", "Finanzamt Musterstadt")
		make_mapping(COMPANY)
		march = "2026-03-10"
		post_journal_entry(COMPANY, march, [(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)])
		post_journal_entry(COMPANY, march, [(a["1400"], 2000, 0), (a["8336"], 0, 2000)])
		post_journal_entry(COMPANY, march, [(a["1400"], 500, 0), (a["8338"], 0, 500)])
		post_journal_entry(
			COMPANY, march, [(a["3123"], 300, 0), (a["1577"], 57, 0), (a["1787"], 0, 57), (a["1200"], 0, 300)]
		)
		post_journal_entry(COMPANY, march, [(a["1576"], 95, 0), (a["1200"], 0, 95)])

	def calculated_return(self, period: int, **fields):
		doc = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": period,
				**fields,
			}
		).insert()
		doc.calculate()
		doc.reload()
		return doc

	def printed(self, doc) -> str:
		return frappe.get_print("VAT Return", doc.name, print_format=PRINT_FORMAT, no_letterhead=1)

	def test_the_print_format_is_installed_for_the_vat_return(self):
		self.assertEqual(
			frappe.db.get_value(
				"Print Format", PRINT_FORMAT, ["doc_type", "print_format_type", "standard", "module"]
			),
			("VAT Return", "Jinja", "Yes", "Steuerbote"),
		)

	def test_the_header_names_company_steuernummer_period_and_deadline(self):
		text = cells(self.printed(self.calculated_return(3)))
		for expected in (
			"Umsatzsteuer-Voranmeldung 2026",
			f"Unternehmen | {COMPANY} |",
			"Steuernummer | 123/456/78901 |",
			"Steuernummer im ELSTER-Format | 9123045678901 |",
			"Finanzamt | Finanzamt Musterstadt |",
			"Voranmeldungszeitraum | März 2026 |",
			"Fällig am | 10.04.2026 |",
		):
			self.assertIn(expected, text)

	def test_prints_the_kennzahlen_in_their_sections_with_the_sums_of_the_form(self):
		text = cells(self.printed(self.calculated_return(3)))
		expected_lines = [
			"A. Steuerpflichtige Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben |",
			"13 | Steuerpflichtige Umsätze zum Steuersatz von 19 % | 81 | 1.000 | | 190,00 |",
			"B. Steuerfreie Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben | | Keine Eintragungen |",
			"C. Innergemeinschaftliche Erwerbe | | Keine Eintragungen |",
			"D. Leistungsempfänger als Steuerschuldner (§ 13b UStG) |",
			"30 | Sonstige Leistungen nach § 3a Absatz 2 UStG",
			"| 46 | 300 | 47 | 57,00 |",
			"E. Ergänzende Angaben zu Umsätzen |",
			"35 | Nicht steuerbare sonstige Leistungen gemäß § 18b Satz 1 Nummer 2 UStG | 21 | 2.000 | | |",
			"36 | Übrige nicht steuerbare Umsätze (Leistungsort nicht im Inland) | 45 | 500 | | |",
			"37 | Umsatzsteuer (Summe der Zeilen 13 bis 18 und 25 bis 32) | | | | 247,00 |",
			"F. Abziehbare Vorsteuerbeträge und Berichtigung des Vorsteuerabzugs |",
			"| | 66 | 95,00 |",
			"| | 67 | 57,00 |",
			"45 | Verbleibender Betrag (Zeile 37 abzüglich der Zeilen 38 bis 44) | | | | 95,00 |",
			"G. Andere Steuerbeträge | | Keine Eintragungen |",
			"H. Vorauszahlung/Überschuss |",
			"48 | Umsatzsteuer-Vorauszahlung/Überschuss (Summe der Zeilen 45 bis 47) | | | | 95,00 |",
			"50 | Verbleibende Umsatzsteuer-Vorauszahlung / Verbleibender Überschuss (bitte in jedem Fall ausfüllen) | | | 83 | 95,00 |",
			"J. Sonstige Angaben |",
			"Ergänzende Angaben zur Steueranmeldung |",
		]
		positions = [text.find(expected) for expected in expected_lines]
		self.assertNotIn(
			-1, positions, [line for line, at in zip(expected_lines, positions, strict=True) if at < 0]
		)
		self.assertEqual(positions, sorted(positions))
		self.assertNotIn("{{", text)

	def test_prints_the_flags_of_the_return(self):
		doc = self.calculated_return(
			4,
			attachments=1,
			no_sepa_mandate=1,
			supplementary_code="2",
			kz500_begruendung="Umsatzsteuer auf Gutscheine, siehe Schreiben vom 10. April",
		)
		text = cells(self.printed(doc))
		for expected in (
			"10 | Berichtigte Anmeldung | 10 | |",
			"11 | Belege (z. B. Verträge, Rechnungen) sind beigefügt bzw. werden gesondert eingereicht | 22 | 1 = Ja |",
			"53 | Verrechnung des Erstattungsbetrags erwünscht / Erstattungsbetrag ist abgetreten | 29 | |",
			"| 26 | 1 = Ja |",
			"| 500 | 2 |",
			"wird bewusst eine von der Verwaltungsauffassung abweichende Rechtsauffassung vertreten",
			"Begründung: Umsatzsteuer auf Gutscheine, siehe Schreiben vom 10. April |",
		):
			self.assertIn(expected, text)

	def test_an_override_is_printed_with_its_reason_and_the_remarks_follow(self):
		doc = self.calculated_return(5)
		doc.append(
			"kennzahlen",
			{"kennzahl": "45", "override": 700, "override_reason": "Invoice 2026-17 booked in June"},
		)
		doc.remarks = "Agreed with the Steuerberatung.\n<script>alert(1)</script>Second line"
		doc.save()
		markup = self.printed(doc)
		text = cells(markup)
		self.assertIn(
			"36 | Übrige nicht steuerbare Umsätze (Leistungsort nicht im Inland) | 45 | 700 | | |", text
		)
		self.assertIn("45 | 0 | 700 | Invoice 2026-17 booked in June |", text)
		self.assertIn("Agreed with the Steuerberatung.", text)
		self.assertIn("Second line", text)
		self.assertNotIn("<script>alert(1)</script>", markup)

	def test_the_footer_says_what_the_print_is_for(self):
		text = cells(self.printed(self.calculated_return(6)))
		self.assertIn("Zum Abgleich mit der Steuerberatung oder zum Übertragen in Mein ELSTER.", text)
		self.assertIn("Dieser Ausdruck ist keine Abgabe", text)
