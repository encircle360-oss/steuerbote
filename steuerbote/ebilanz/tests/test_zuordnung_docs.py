"""docs/ebilanz-zuordnung.md shows the defaults of the Bilanzzuordnung as steuerbote/ebilanz/defaults.py holds them:
their versions and size, the notable choices with the place the defaults give, the review list for the
Steuerberatung and Vorgaben aktualisieren; and docs/architektur.md names the module and the page."""

import re
from pathlib import Path
from unittest import TestCase

from steuerbote.ebilanz.defaults import CHARTS, DEFAULTS, defaults_for, defaults_version
from steuerbote.xbrl.mapping import DefaultExcluded, DefaultRule, DefaultWatched

DOCS = Path(__file__).resolve().parents[3] / "docs"
DOC = DOCS / "ebilanz-zuordnung.md"
ARCHITECTURE = DOCS / "architektur.md"
VERSION = "6.9"


def section(heading: str) -> str:
	"""The text under a heading of the document, up to the next heading of the same or a higher level."""
	text = DOC.read_text(encoding="utf-8")
	level = heading.split(" ", 1)[0]
	start = text.index(f"\n{heading}\n")
	ends = [text.find(f"\n{'#' * depth} ", start + 1) for depth in range(1, len(level) + 1)]
	ends = [end for end in ends if end != -1]
	return text[start : min(ends) if ends else len(text)]


def rows(text: str) -> list[list[str]]:
	"""The cells of the rows of the first table in the text, without its head."""
	lines = text.splitlines()
	start = next(index for index, line in enumerate(lines) if line.startswith("|"))
	table = []
	for line in lines[start + 2 :]:
		if not line.startswith("|"):
			break
		table.append([cell.strip() for cell in line.strip().strip("|").split("|")])
	return table


def place(chart: str, number: str) -> str:
	"""The place of an account as the page writes it: the position, „beobachtet“ or „außerhalb“."""
	match defaults_for(chart, VERSION).entry_for(number):
		case DefaultRule(concept=concept):
			return f"`{concept}`"
		case DefaultWatched():
			return "beobachtet"
		case DefaultExcluded():
			return "außerhalb"
	return "ohne Vorgabe"


class ScopeTest(TestCase):
	def test_names_the_version_of_the_defaults_of_each_chart(self):
		text = section("## Umfang")
		for chart in sorted(CHARTS):
			with self.subTest(chart=chart):
				self.assertIn(f"„{defaults_version(chart, VERSION)}“", text)

	def test_counts_the_entries_of_each_chart(self):
		"""The table of the scope: entries with a position, watched and outside the Bilanz and the GuV."""
		found = {row[0]: row[1:] for row in rows(section("## Umfang"))}
		for chart in sorted(CHARTS):
			with self.subTest(chart=chart):
				entry = DEFAULTS[VERSION][chart]
				self.assertEqual(
					found[chart], [str(len(entry.rules)), str(len(entry.watched)), str(len(entry.excluded))]
				)


class ChoicesTest(TestCase):
	def test_every_notable_choice_is_the_place_the_defaults_give(self):
		"""Each row names the accounts of SKR03 and SKR04, a dash for none, and the place both take."""
		table = rows(section("## Auffällige Entscheidungen"))
		self.assertGreaterEqual(len(table), 20)
		for skr03, skr04, where, _why in table:
			with self.subTest(accounts=(skr03, skr04)):
				places = {
					place(chart, number.split("-")[0])
					for chart, numbers in (("SKR03", skr03), ("SKR04", skr04))
					for number in re.findall(r"\d{4,5}(?:-\d{4,5})?", numbers)
				}
				self.assertEqual(places, {where})


class ReviewTest(TestCase):
	def test_the_review_list_for_the_steuerberatung(self):
		text = section("## Prüfliste für die Steuerberatung")
		items = re.findall(r"^\d+\. \*\*(.+?)\*\*", text, re.MULTILINE)
		self.assertEqual(
			items,
			[
				"Freigabe.",
				"Restlaufzeiten.",
				"Auffangpositionen.",
				"Personengesellschaften.",
				"Gesellschafter.",
				"Vermögensverrechnung.",
				"Abschlusszweck.",
				"Konten der Vorlagen von ERPNext.",
				"Beobachtete Konten.",
			],
		)


class UpdatesTest(TestCase):
	def test_says_how_a_company_changes_a_row_and_how_a_new_revision_reaches_it(self):
		self.assertIn("Vorgaben aktualisieren", section("## Neue Revisionen der Vorgaben"))
		self.assertIn("einrichtung.md#vorgaben-aktualisieren", section("## Neue Revisionen der Vorgaben"))
		self.assertIn("Bilanzzuordnung", section("## Eine Zeile ändern"))


class ArchitectureTest(TestCase):
	def test_the_architecture_names_the_module_and_the_page(self):
		text = ARCHITECTURE.read_text(encoding="utf-8")
		self.assertIn("| `steuerbote/ebilanz/defaults.py` |", text)
		self.assertIn("## Vorgaben der Bilanzzuordnung", text)
		self.assertIn("(ebilanz-zuordnung.md)", text)
