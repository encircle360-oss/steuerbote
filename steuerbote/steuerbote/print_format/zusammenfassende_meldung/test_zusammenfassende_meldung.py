import html
import re

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_customer,
	make_mapping,
	make_settings,
	post_payment_entry,
	post_sales_invoice,
)

PRINT_FORMAT = "Zusammenfassende Meldung"
COMPANY = "Steuerbote Test ZM-Druckformat GmbH"
ALPEN = "Alpen Handel GmbH (Druck)"
PARIS = "Paris Services SA (Druck)"
ACCOUNTS = {
	"8125": ("Steuerfreie innergemeinschaftliche Lieferungen", "Income"),
	"8743": ("Gewährte Skonti innergemeinschaftliche Lieferungen", "Income"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
	"1200": ("Bank", "Asset"),
}


def cells(markup: str) -> str:
	"""The printed text with every table cell closed by " |", so that a line reads as one string."""
	text = re.sub(r"<(style|script)\b.*?</\1>", " ", markup, flags=re.DOTALL | re.IGNORECASE)
	text = re.sub(r"</t[dh]>", " |", text)
	text = re.sub(r"<br\s*/?>", " ", text)
	text = re.sub(r"<[^>]+>", " ", text)
	return re.sub(r"\s+", " ", html.unescape(text))


class TestZusammenfassendeMeldung(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STZD")
		a = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(
			COMPANY,
			[(2026, "monthly", 1)],
			ust_idnr="DE123456789",
			zm_rules=[{"year": 2026, "valid_from_month": 1, "rhythm": "monthly", "services_monthly": 1}],
		)
		make_mapping(COMPANY)
		make_customer(ALPEN, "Austria", "ATU12345678")
		make_customer(PARIS, "France", "FR12345678901")
		invoice = post_sales_invoice(
			COMPANY, "SINV-STZD-1", ALPEN, "2026-03-10", [(a["1400"], 10000, 0), (a["8125"], 0, 10000)]
		)
		post_sales_invoice(
			COMPANY, "SINV-STZD-2", PARIS, "2026-03-11", [(a["1400"], 3000, 0), (a["8336"], 0, 3000)]
		)
		post_payment_entry(
			COMPANY,
			"PE-STZD-1",
			ALPEN,
			"2026-03-20",
			[invoice],
			[(a["1200"], 9800, 0), (a["8743"], 200, 0), (a["1400"], 0, 10000)],
		)

	def calculated(self):
		doc = frappe.get_doc(
			{
				"doctype": "Recapitulative Statement",
				"company": COMPANY,
				"year": 2026,
				"period_kind": "month",
				"period_index": 3,
			}
		).insert()
		doc.calculate()
		doc.reload()
		return doc

	def printed(self, doc) -> str:
		return cells(
			frappe.get_print("Recapitulative Statement", doc.name, print_format=PRINT_FORMAT, no_letterhead=1)
		)

	def test_the_print_format_is_installed_for_the_statement(self):
		self.assertEqual(
			frappe.db.get_value(
				"Print Format", PRINT_FORMAT, ["doc_type", "print_format_type", "standard", "module"]
			),
			("Recapitulative Statement", "Jinja", "Yes", "Steuerbote"),
		)

	def test_prints_the_lines_per_ust_idnr_and_art_with_the_sum_of_each_art(self):
		doc = self.calculated()
		text = self.printed(doc)
		for expected in (
			"Zusammenfassende Meldung März 2026",
			f"Unternehmen | {COMPANY} |",
			"USt-IdNr. | DE123456789 |",
			"Meldezeitraum | März 2026 |",
			"Fällig am | 27.04.2026 |",
			"Meldeart | Erstmeldung |",
			f"Meldung | {doc.name}, Berechnet |",
			f"ATU12345678 | {ALPEN} | L | 9.800 |",
			f"FR12345678901 | {PARIS} | S | 3.000 |",
			"Innergemeinschaftliche Warenlieferungen | L | 9.800 |",
			"Lieferungen im Dreiecksgeschäft (§ 25b Absatz 2 UStG) | D | 0 |",
			"Sonstige Leistungen (§ 3a Absatz 2 UStG) | S | 3.000 |",
			"Dieser Ausdruck ist keine Abgabe.",
		):
			with self.subTest(expected=expected):
				self.assertIn(expected, text)
		self.assertNotIn("Korrekturen gegenüber dem Hauptbuch", text)

	def test_prints_the_overrides_with_their_reason(self):
		doc = self.calculated()
		row = next(row for row in doc.lines if row.vat_id == "FR12345678901")
		row.override = 2500
		row.override_reason = "Gutschrift vom 30. März 2026"
		doc.save()
		text = self.printed(doc)
		self.assertIn(f"FR12345678901 | {PARIS} | S | 2.500 |", text)
		self.assertIn("Korrekturen gegenüber dem Hauptbuch", text)
		self.assertIn("FR12345678901 | S | 3.000,00 | 2.500 | Gutschrift vom 30. März 2026 |", text)

	def test_prints_the_open_errors_the_releases_and_the_lines_the_file_leaves_out(self):
		"""The printout that goes to the Steuerberatung shows what holds the statement and what it does not report."""
		doc = self.calculated()
		text = self.printed(doc)
		self.assertIn("Offene Fehler", text)
		self.assertIn("ZM-USTID-UNBESTAETIGT: Die USt-IdNr. ATU12345678 ist nicht bestätigt.", text)
		self.assertNotIn("Nicht in der Meldung", text)
		row = next(row for row in doc.lines if row.vat_id == "ATU12345678")
		row.acceptance_reason = "Bestätigung vom Liefertag in der Akte"
		paris = next(row for row in doc.lines if row.vat_id == "FR12345678901")
		paris.override = 0
		paris.override_reason = "Leistung an einen Nichtunternehmer, Rechnung wird berichtigt"
		doc.save()
		text = self.printed(doc)
		self.assertIn("Freigegebene USt-IdNrn.", text)
		self.assertIn("ATU12345678 | L | Bestätigung vom Liefertag in der Akte |", text)
		self.assertIn("Nicht in der Meldung", text)
		self.assertIn(f"FR12345678901 | {PARIS} | S | 3.000,00 |", text)
		self.assertEqual(
			[(row["vat_id"], row["art"]) for row in doc.left_out_lines()], [("FR12345678901", "S")]
		)
