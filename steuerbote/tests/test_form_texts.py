"""Texts and forms the browser retest of 0.15.0 found misleading, read from their files without a bench: the records
kept as proof read as such for every user, and each text says what happens."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[1]
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSLATIONS = APP / "translations" / "de.csv"
# The records Steuerbote keeps as proof: nobody changes them, the Administrator included, who holds every permission.
PROOF_RECORDS = ("vat_id_confirmation", "elster_transmission", "deadline_reminder")


def german() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return {row[0]: row[1] for row in csv.reader(file) if row}


def description(doctype: str, fieldname: str) -> str:
	meta = json.loads((DOCTYPES / doctype / f"{doctype}.json").read_text(encoding="utf-8"))
	(field,) = (field for field in meta["fields"] if field["fieldname"] == fieldname)
	return field["description"]


class ProofRecordFormsTest(TestCase):
	def test_the_form_of_a_proof_record_offers_no_save_and_no_change(self):
		for doctype in PROOF_RECORDS:
			with self.subTest(doctype=doctype):
				script = (DOCTYPES / doctype / f"{doctype}.js").read_text(encoding="utf-8")
				self.assertRegex(script, r"onload\(frm\)\s*\{[^}]*frm\.set_read_only\(\);")
				self.assertRegex(script, r"refresh\(frm\)\s*\{[^}]*frm\.disable_save\(\);")


class FormTextsTest(TestCase):
	def setUp(self):
		self.german = german()

	def test_the_hints_of_the_return_say_that_an_error_holds_it(self):
		text = self.german[description("vat_return", "hints")]
		self.assertNotIn("nie an", text)
		self.assertIn("Fehler", text)

	def test_the_own_vat_id_names_the_field_of_the_company_as_it_reads_now(self):
		text = self.german[description("vat_return_settings", "ust_idnr")]
		self.assertNotIn("Steuernummer (tax_id)", text)
		self.assertIn("im Feld USt-IdNr. des Unternehmens", text)

	def test_no_vat_return_says_that_steuerbote_relies_on_the_statement(self):
		text = self.german[description("annual_filing_year", "no_vat_return")]
		self.assertNotIn("übernimmt die Erklärung", text)
		self.assertIn("verlässt sich auf diese Angabe", text)

	def test_acknowledged_errors_let_the_document_be_filed_and_do_not_file_it(self):
		script = (APP / "public" / "js" / "annual_filing.js").read_text(encoding="utf-8")
		(banner,) = re.findall(r'__\("(Every error of the findings is acknowledged[^"]*)"\)', script)
		self.assertNotIn("wird trotzdem abgegeben", self.german[banner])
		self.assertIn("kann trotzdem abgegeben werden", self.german[banner])

	def test_the_help_of_the_vat_id_on_the_partner_reads_in_german(self):
		setup = (APP / "steuerbote" / "vat_id_setup.py").read_text(encoding="utf-8")
		(text,) = re.findall(r'DESCRIPTION = \(\n\t"([^"]*)"\n\)', setup)
		self.assertEqual(
			self.german.get(text),
			"Die USt-IdNr. mit Länderkennzeichen, etwa ATU12345678. Die Steuernummer hat ein eigenes Feld.",
		)


class KennzahlenTableTest(TestCase):
	def test_the_kennzahlen_say_that_a_kennzahl_without_postings_is_a_row_by_hand(self):
		"""The table offers „Zeile hinzufügen“ on purpose: a Kennzahl the ledger does not fill is entered as a row by
		hand with a correction and its reason (bridge.kennzahl_rows)."""
		text = german()[description("vat_return", "kennzahlen")]
		self.assertEqual(
			text,
			"Eine Kennzahl ohne Buchungen tragen Sie als Zeile von Hand ein: Kennzahl wählen und den Betrag als "
			"Korrektur mit Begründung angeben. Die übrigen Zeilen füllt „Berechnen“.",
		)


class KontennachweisFormatterTest(TestCase):
	def test_a_line_of_the_form_shows_no_debit_and_credit_it_does_not_have(self):
		"""The rows of the lines carry their amount alone; Frappe would show an empty debit and credit as 0,00 €."""
		script = (
			APP / "steuerbote" / "report" / "ertragsteuer_kontennachweis" / "ertragsteuer_kontennachweis.js"
		).read_text(encoding="utf-8")
		self.assertIn(
			'if (data && ["debit", "credit"].includes(column.fieldname) && data[column.fieldname] == null) {\n\t\t\treturn "";',
			script,
		)
