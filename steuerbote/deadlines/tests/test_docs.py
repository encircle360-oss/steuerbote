"""The tables of docs/fristen.md show what the deadlines know: their kinds, their status, the fields that keep the
reminder and the days of the examples; for the annual filings also the notes of a deadline, the DocTypes that file
them and the fields of the Annual Filing Settings they read. docs/architektur.md names the core of the annual
deadlines."""

import ast
import csv
import json
from datetime import date
from pathlib import Path
from unittest import TestCase

from steuerbote.deadlines import (
	AnnualRules,
	AnnualYear,
	Kind,
	Status,
	annual,
	annual_due,
	sondervorauszahlungen,
	voranmeldungen,
	zusammenfassende_meldungen,
)
from steuerbote.hgb.size import SizeClass
from steuerbote.steuerbote.doctype.annual_filing_settings import rules as annual_settings
from steuerbote.steuerbote.doctype.vat_return_settings.rules import PeriodRule, Prepayment
from steuerbote.ustva.period import MONTH_NAMES
from steuerbote.zm import rhythm as zm_rhythm

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "docs" / "fristen.md"
ARCHITECTURE = ROOT / "docs" / "architektur.md"
MODULE = ROOT / "steuerbote" / "steuerbote"
TRANSLATIONS = ROOT / "steuerbote" / "translations" / "de.csv"
WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
MONTHLY = (PeriodRule(2026, "monthly"),)
DAUERFRIST_2026 = (Prepayment(2026, dauerfristverlaengerung=True),)
CHRISTMAS_2026 = frozenset({date(2026, 12, 25), date(2026, 12, 26)})
UNTIL = date(2027, 12, 31)


def due(found, label: str) -> date:
	(item,) = [item for item in found if item.label == label]
	return item.due


# The day each example of the docs falls due, as the core computes it.
EXAMPLES = {
	"Voranmeldung Oktober 2026": lambda: due(voranmeldungen(MONTHLY, (), UNTIL), "Oktober 2026"),
	"Voranmeldung Dezember 2026, der 10. Januar ist ein Sonntag": lambda: due(
		voranmeldungen(MONTHLY, (), UNTIL), "Dezember 2026"
	),
	"Voranmeldung November 2026 mit Dauerfristverlängerung": lambda: due(
		voranmeldungen(MONTHLY, DAUERFRIST_2026, UNTIL), "November 2026"
	),
	"Voranmeldung III. Kalendervierteljahr 2026, der 10. Oktober ist ein Samstag": lambda: due(
		voranmeldungen((PeriodRule(2026, "quarterly"),), (), UNTIL), "III. Kalendervierteljahr 2026"
	),
	"ZM I. Kalendervierteljahr 2026, der 25. April ist ein Samstag": lambda: due(
		zusammenfassende_meldungen((zm_rhythm.Rule(2026, 1, "quarterly"),), UNTIL),
		"I. Kalendervierteljahr 2026",
	),
	"ZM November 2026 mit beiden Weihnachtsfeiertagen in der Liste": lambda: due(
		zusammenfassende_meldungen((zm_rhythm.Rule(2026, 1, "monthly"),), UNTIL, CHRISTMAS_2026),
		"November 2026",
	),
	"Sondervorauszahlung 2027": lambda: due(
		sondervorauszahlungen((PeriodRule(2027, "monthly"),), (Prepayment(2027, True),), UNTIL), "2027"
	),
	"Sondervorauszahlung 2026, die Voranmeldungen beginnen im April": lambda: due(
		sondervorauszahlungen(
			(PeriodRule(2026, "none"), PeriodRule(2026, "monthly", 4)), DAUERFRIST_2026, UNTIL
		),
		"2026",
	),
}


def due_in(year: AnnualYear, kind: Kind) -> date:
	(item,) = [
		item for item in annual.year_obligations(year) if item.kind is kind and isinstance(item.period, int)
	]
	return item.due


SMALL_2026 = AnnualYear(2026, date(2026, 12, 31), size_class=SizeClass.KLEIN)
# The day each example of the annual deadlines falls due, as the core computes it.
ANNUAL_EXAMPLES = {
	"Umsatzsteuererklärung 2026, der 31. Juli 2027 ist ein Samstag": lambda: due_in(
		SMALL_2026, Kind.UMSATZSTEUERERKLAERUNG
	),
	"Körperschaftsteuererklärung 2026 mit Steuerberatung": lambda: due_in(
		AnnualYear(2026, date(2026, 12, 31), advisor_prepares=True), Kind.KOERPERSCHAFTSTEUERERKLAERUNG
	),
	"Gewerbesteuererklärung 2026, vorab angefordert für Samstag, den 16. Oktober 2027": lambda: due_in(
		AnnualYear(2026, date(2026, 12, 31), advisor_prepares=True, early_request=date(2027, 10, 16)),
		Kind.GEWERBESTEUERERKLAERUNG,
	),
	"E-Bilanz 2026": lambda: due_in(SMALL_2026, Kind.E_BILANZ),
	"Eröffnungsbilanz einer GmbH, gegründet im März 2027": lambda: annual_due(
		AnnualRules(founded_on=date(2027, 3, 15)), Kind.E_BILANZ, 2027, opening_balance=True
	),
	"Feststellung des Jahresabschlusses 2026 einer kleinen Gesellschaft": lambda: due_in(
		SMALL_2026, Kind.FESTSTELLUNG
	),
	"Feststellung des Jahresabschlusses 2026 ohne Größenklasse": lambda: due_in(
		AnnualYear(2026, date(2026, 12, 31)), Kind.FESTSTELLUNG
	),
	"Offenlegung des Jahresabschlusses 2026": lambda: due_in(SMALL_2026, Kind.OFFENLEGUNG),
	"Offenlegung des Jahresabschlusses 2027, ohne Verschiebung vom Sonntag": lambda: due_in(
		AnnualYear(2027, date(2027, 12, 31)), Kind.OFFENLEGUNG
	),
}


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def note_sources() -> list[str]:
	"""The English text of each note, in the order of note_texts in steuerbote/steuerbote/deadlines.py."""
	tree = ast.parse((MODULE / "deadlines.py").read_text(encoding="utf-8"))
	(function,) = [
		node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "note_texts"
	]
	(returned,) = [node.value for node in ast.walk(function) if isinstance(node, ast.Return)]
	return [value.args[0].value for value in returned.values]


def doctype_fields(name: str) -> set[str]:
	path = MODULE / "doctype" / name / f"{name}.json"
	return {field["fieldname"] for field in json.loads(path.read_text(encoding="utf-8"))["fields"]}


def section(heading: str) -> str:
	"""The text under the heading, up to the next heading of the same or a higher level."""
	text = DOC.read_text(encoding="utf-8")
	level = heading.split(" ", 1)[0]
	start = text.index(f"\n{heading}\n")
	ends = [text.find(f"\n{'#' * size} ", start + 1) for size in range(1, len(level) + 1)]
	return text[start : min((end for end in ends if end != -1), default=len(text))]


def rows(heading: str, first: int = 0) -> list[list[str]]:
	"""The cells of the rows of the tables under the heading, without their heads, from the table ``first`` on."""
	tables: list[list[list[str]]] = [[]]
	for line in section(heading).splitlines():
		if line.startswith("|"):
			tables[-1].append([cell.strip() for cell in line.strip().strip("|").split("|")])
		elif tables[-1]:
			tables.append([])
	return [row for table in tables[first:] if table for row in table[2:]]


def german_date(text: str) -> date:
	"""A day written as „Dienstag, 10. November 2026“, whose weekday must fit."""
	weekday, rest = text.split(", ")
	day, month, year = rest.split(" ")
	found = date(int(year), MONTH_NAMES.index(month) + 1, int(day.rstrip(".")))
	if WEEKDAYS[found.weekday()] != weekday:
		raise ValueError(f"{found} is a {WEEKDAYS[found.weekday()]}, not a {weekday}")
	return found


class DocsTest(TestCase):
	def test_names_the_kinds_of_the_deadlines(self):
		self.assertEqual(
			[row[0] for row in rows("## Welche Fristen")[:3]],
			[kind.value for kind in Kind if kind not in annual.KINDS],
		)

	def test_names_the_status_of_a_deadline(self):
		self.assertEqual(
			[row[0] for row in rows("## Abgegeben, offen oder fehlt")], [status.value for status in Status]
		)

	def test_names_the_fields_of_the_settings(self):
		self.assertEqual(
			[row[0].strip("`") for row in rows("## Einstellungen")], ["deadline_recipients", "reminder_days"]
		)

	def test_names_the_fields_of_the_deadline_reminder(self):
		self.assertEqual(
			[row[0].strip("`") for row in rows("### Fristerinnerung (`Deadline Reminder`)")],
			["company", "kind", "period_label", "due_date", "sent_on", "recipients"],
		)

	def test_the_examples_fall_due_on_the_days_the_core_computes(self):
		examples = rows("## Welche Fristen", first=1)
		self.assertEqual([row[0] for row in examples], list(EXAMPLES))
		for name, day in examples:
			with self.subTest(example=name):
				self.assertEqual(german_date(day), EXAMPLES[name]())

	def test_names_the_annual_kinds_of_the_deadlines(self):
		self.assertEqual(
			[row[0] for row in rows("## Jahresmeldungen")[: len(annual.KINDS)]],
			[kind.value for kind in annual.KINDS],
		)

	def test_the_annual_examples_fall_due_on_the_days_the_core_computes(self):
		examples = rows("### Beispiele der Jahresmeldungen")
		self.assertEqual([row[0] for row in examples], list(ANNUAL_EXAMPLES))
		for name, day in examples:
			with self.subTest(example=name):
				self.assertEqual(german_date(day), ANNUAL_EXAMPLES[name]())

	def test_names_every_note_of_a_deadline_as_the_reminder_writes_it(self):
		german = translations()
		self.assertEqual(
			[row[0] for row in rows("### Hinweise")], [german[source] for source in note_sources()]
		)
		self.assertEqual(len(note_sources()), len(annual.Note))

	def test_names_the_doctypes_that_file_the_annual_deadlines(self):
		self.assertEqual(
			[(row[0].strip("`"), row[1]) for row in rows("### Belege der Jahresmeldungen")],
			[
				(doctype, ", ".join(kind.value for kind in entry.kinds))
				for doctype, entry in annual.DOCTYPES.items()
			],
		)

	def test_names_only_fields_of_the_annual_filing_settings(self):
		fields = (
			doctype_fields("annual_filing_settings")
			| doctype_fields("annual_filing_year")
			| doctype_fields("annual_filing_size_class")
		)
		named = [row[0].strip("`") for row in rows("### Aus den Einstellungen Jahresmeldungen")]
		self.assertTrue(named)
		self.assertLessEqual(set(named), fields)
		self.assertIn("advisor_prepares", named)
		self.assertIn("size_history", named)

	def test_the_size_classes_of_the_settings_are_those_of_the_hgb(self):
		self.assertEqual(
			[size_class.name for size_class in annual_settings.SizeClass],
			[size_class.name for size_class in SizeClass],
		)

	def test_the_architecture_names_the_core_of_the_annual_deadlines(self):
		self.assertIn("| `steuerbote/deadlines/annual.py` |", ARCHITECTURE.read_text(encoding="utf-8"))

	def test_reads_a_german_date_only_with_its_weekday(self):
		self.assertEqual(german_date("Mittwoch, 10. Februar 2027"), date(2027, 2, 10))
		with self.assertRaisesRegex(ValueError, "Mittwoch"):
			german_date("Dienstag, 10. Februar 2027")
