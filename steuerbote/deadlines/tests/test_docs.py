"""The tables of docs/fristen.md show what the deadlines know: their kinds, their status, the fields that keep the
reminder and the days of the examples."""

from datetime import date
from pathlib import Path
from unittest import TestCase

from steuerbote.deadlines import (
	Kind,
	Status,
	annual,
	sondervorauszahlungen,
	voranmeldungen,
	zusammenfassende_meldungen,
)
from steuerbote.steuerbote.doctype.vat_return_settings.rules import PeriodRule, Prepayment
from steuerbote.ustva.period import MONTH_NAMES
from steuerbote.zm import rhythm as zm_rhythm

DOC = Path(__file__).resolve().parents[3] / "docs" / "fristen.md"
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
			["company", "kind", "period_label", "due_date", "sent_on"],
		)

	def test_the_examples_fall_due_on_the_days_the_core_computes(self):
		examples = rows("## Welche Fristen", first=1)
		self.assertEqual([row[0] for row in examples], list(EXAMPLES))
		for name, day in examples:
			with self.subTest(example=name):
				self.assertEqual(german_date(day), EXAMPLES[name]())

	def test_reads_a_german_date_only_with_its_weekday(self):
		self.assertEqual(german_date("Mittwoch, 10. Februar 2027"), date(2027, 2, 10))
		with self.assertRaisesRegex(ValueError, "Mittwoch"):
			german_date("Dienstag, 10. Februar 2027")
