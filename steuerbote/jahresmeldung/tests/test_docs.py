"""The tables of docs/jahresmeldungen.md show the statuses, the fields every annual document carries, the ways of a
filing and the Berichtigung of each Datenart as steuerbote.jahresmeldung holds them."""

import csv
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.jahresmeldung import corrections
from steuerbote.jahresmeldung.lifecycle import ACCOUNTS, FILED_VIA, FILING, Status, standard_fields

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "docs" / "jahresmeldungen.md"
TRANSLATIONS = ROOT / "steuerbote" / "translations" / "de.csv"
YES, NO = "ja", "nein"
NONE = "\N{EN DASH}"
# The German of the labels Frappe and ERPNext translate themselves (frappe/locale/de.po and erpnext/locale/de.po of
# version 16), and of Transferticket, which is German already.
FRAMEWORK_LABELS = {
	"Due Date": "Fälligkeitsdatum",
	"Fiscal Year": "Geschäftsjahr",
	"From Date": "Von-Datum",
	"Remarks": "Anmerkungen",
	"Status": "Status",
	"To Date": "Bis-Datum",
	"Transferticket": "Transferticket",
}
BY_THE_TAX_ADMINISTRATION = "Korrektur durch Finanzverwaltung"


def table(heading: str, header: list[str]) -> list[list[str]]:
	"""The rows of the table under the heading whose head is header."""
	text = DOC.read_text(encoding="utf-8")
	start = text.index(f"\n{heading}\n")
	following = text.find("\n#", start + 1)
	lines = text[start : following if following > 0 else len(text)].splitlines()
	tables: list[list[list[str]]] = []
	previous = ""
	for line in lines:
		if line.startswith("|"):
			if not previous.startswith("|"):
				tables.append([])
			tables[-1].append([cell.strip() for cell in line.strip().strip("|").split(" | ")])
		previous = line
	(found,) = [rows for rows in tables if rows[0] == header]
	return found[2:]


def names(cell: str) -> list[str]:
	return re.findall(r"`([^`]+)`", cell)


def german(label: str) -> str:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		translations = dict(csv.reader(file))
	return translations[label] if label in translations else FRAMEWORK_LABELS[label]


class StatusTableTest(TestCase):
	def setUp(self):
		self.rows = table("## Status", ["Status", "Erklärungen und E-Bilanz", "Jahresabschluss", "Bedeutung"])

	def test_shows_every_status_once(self):
		self.assertEqual(sorted(row[0] for row in self.rows), sorted(status.value for status in Status))

	def test_marks_the_lifecycles_that_have_it(self):
		for row in self.rows:
			status = Status(row[0])
			with self.subTest(status=status):
				self.assertEqual(row[1], YES if status in FILING.statuses else NO)
				self.assertEqual(row[2], YES if status in ACCOUNTS.statuses else NO)


class FieldTableTest(TestCase):
	def setUp(self):
		self.rows = table("## Felder jedes Belegs", ["Feld", "Bezeichnung", "Inhalt"])
		self.fields = standard_fields(FILING, "Annual VAT Return", transmits=True)

	def test_lists_the_standard_fields_in_their_order(self):
		self.assertEqual(
			[name for row in self.rows for name in names(row[0])],
			[field.fieldname for field in self.fields],
		)

	def test_names_the_german_label_of_each(self):
		self.assertEqual(
			[label for row in self.rows for label in row[1].split(", ")],
			[german(field.label) for field in self.fields],
		)


class FilingTableTest(TestCase):
	def test_names_each_way_of_a_filing_with_its_label(self):
		rows = table("## Abgabe", ["Abgegeben über", "Bezeichnung", "Wann"])
		self.assertEqual([names(row[0]) for row in rows], [[way] for way in FILED_VIA])
		self.assertEqual([row[1] for row in rows], [german(way) for way in FILED_VIA])


class BerichtigungTableTest(TestCase):
	def setUp(self):
		self.rows = table("## Berichtigung", ["Datenart", "Wie", "Felder", "Geprüft", "Quelle"])

	def test_shows_each_datenart_in_its_order(self):
		self.assertEqual([names(row[0])[0] for row in self.rows], list(corrections.BERICHTIGUNGEN))

	def test_names_the_fields_that_mark_it_and_whether_the_way_is_verified(self):
		for row, rule in zip(self.rows, corrections.BERICHTIGUNGEN.values(), strict=True):
			with self.subTest(datenart=rule.datenart):
				self.assertEqual(names(row[2]), list(rule.fields))
				if not rule.fields:
					self.assertEqual(row[2], NONE)
				self.assertEqual(row[3], YES if rule.verified else NO)

	def test_shows_each_status_des_berichts_with_its_label(self):
		rows = table("### Status des Berichts der E-Bilanz", ["Wert", "Status des Berichts", "Wann"])
		self.assertEqual(
			[(names(row[0]), row[1]) for row in rows],
			[
				*(([status.value], corrections.LABELS[status]) for status in corrections.RevisionStatus),
				([corrections.BY_THE_TAX_ADMINISTRATION], BY_THE_TAX_ADMINISTRATION),
			],
		)
