"""The checks of a printout as PDF (printouts.py) on pages made up of words, without a PDF and without a bench."""

from unittest import TestCase

from steuerbote.tests import printouts
from steuerbote.tests.printouts import MM, Expectations, Margins, Page, Word

A4 = (595.0, 842.0)
MARGINS = Margins(top=28, bottom=18, left=20, right=15)
LEFT = 20 * MM + 2
BODY_TOP = 28 * MM + 10


def word(text: str, x0: float, y: float, width: float | None = None) -> Word:
	return Word(x0, y - 8, x0 + (width if width is not None else 5 * len(text)), y, text)


def line(text: str, y: float, x0: float = LEFT) -> list[Word]:
	"""The words of a text set left to right on one line from x0, each 5 points a letter and 3 points apart."""
	words, x = [], x0
	for part in text.split():
		words.append(word(part, x, y))
		x += 5 * len(part) + 3
	return words


def page(*texts: str, number: int = 1, total: int = 1, start: float = BODY_TOP) -> Page:
	"""A page with the running foot „Seite n von N“ and the texts as lines of its body, 12 points apart."""
	words = [w for index, text in enumerate(texts) for w in line(text, start + 12 * index)]
	words += line(f"Seite {number} von {total}", A4[1] - 10 * MM)
	return Page(*A4, tuple(words))


def pages(*bodies: tuple[str, ...]) -> list[Page]:
	return [page(*texts, number=n, total=len(bodies)) for n, texts in enumerate(bodies, start=1)]


class ReadBboxTest(TestCase):
	def test_reads_pages_and_words_with_their_boxes(self):
		xhtml = (
			'<doc><page width="595.276000" height="841.890000">\n'
			'<word xMin="56.7" yMin="45.6" xMax="73.3" yMax="54.0">Gew&amp;St</word>\n'
			"</page>\n"
			'<page width="595.276000" height="841.890000">\n</page></doc>'
		)
		result = printouts.read_bbox(xhtml)
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0].words, (Word(56.7, 45.6, 73.3, 54.0, "Gew&St"),))
		self.assertEqual(result[1].words, ())
		self.assertEqual((result[0].width, result[0].height), (595.276, 841.89))


class LinesTest(TestCase):
	def test_groups_words_by_baseline_left_to_right(self):
		words = [word("b", 100, 200.5), word("a", 60, 200), word("c", 60, 230)]
		self.assertEqual([printouts.text_of(found) for found in printouts.lines(words)], ["a b", "c"])

	def test_the_body_leaves_out_the_running_head_and_foot(self):
		head = line("Gewerbesteuererklärung 2026", 20 * MM)
		found = printouts.body(Page(*A4, (*head, *page("Zeile").words)), MARGINS)
		self.assertEqual(printouts.text_of(printouts.lines(found)[0]), "Zeile")
		self.assertEqual(len(printouts.lines(found)), 1)


class PageCountTest(TestCase):
	def test_accepts_a_count_within_the_range(self):
		self.assertEqual(printouts.page_count(pages(("a",), ("b",)), 1, 2), [])

	def test_names_a_count_outside_the_range(self):
		self.assertEqual(
			printouts.page_count(pages(("a",), ("b",), ("c",)), 1, 2), ["3 Seiten statt 1 bis 2"]
		)


class PageNumbersTest(TestCase):
	def test_accepts_seite_n_von_n_on_every_page(self):
		self.assertEqual(printouts.page_numbers(pages(("a",), ("b",))), [])

	def test_names_a_page_without_its_number(self):
		found = [page("a", number=1, total=2), Page(*A4, tuple(line("b", BODY_TOP)))]
		self.assertEqual(printouts.page_numbers(found), ["Seite 2: keine Seitenzahl „Seite 2 von 2“"])


class OnEveryPageTest(TestCase):
	def test_names_the_page_a_text_is_missing_on(self):
		found = pages(("GewSt-2026-00001 · Berechnet",), ("Zeile",))
		self.assertEqual(
			printouts.on_every_page(found, ["GewSt-2026-00001"]), ["Seite 2: „GewSt-2026-00001“ fehlt"]
		)

	def test_finds_a_text_over_several_words(self):
		self.assertEqual(printouts.on_every_page(pages(("Muster  GmbH (TEST)",)), ["Muster GmbH (TEST)"]), [])


class BleedTest(TestCase):
	def test_accepts_words_within_the_margins(self):
		self.assertEqual(printouts.bleed(pages(("Steuerbote Sandbox C (TEST)",)), MARGINS), [])

	def test_names_a_word_that_runs_over_the_right_edge(self):
		cut = Page(*A4, (word("Forschungsinstitut", A4[0] - 15 * MM - 20, BODY_TOP, width=90),))
		self.assertEqual(
			printouts.bleed([cut], MARGINS), ["Seite 1: „Forschungsinstitut“ läuft über den Rand"]
		)

	def test_names_a_word_left_of_the_left_margin(self):
		early = Page(*A4, (word("Drucken", 15 * MM, BODY_TOP),))
		self.assertEqual(printouts.bleed([early], MARGINS), ["Seite 1: „Drucken“ läuft über den Rand"])


class OverprintTest(TestCase):
	def test_accepts_words_that_touch(self):
		touching = (word("Fehler", 60, 200, width=30), word("GEWST", 90.5, 200))
		self.assertEqual(printouts.overprint([Page(*A4, touching)]), [])

	def test_names_a_code_that_runs_into_the_message(self):
		overlapping = (word("GEWST-VORLAEUFIG", 100, 200, width=80), word("Steuerbote", 160, 200))
		self.assertEqual(
			printouts.overprint([Page(*A4, overlapping)]),
			["Seite 1: „GEWST-VORLAEUFIG“ und „Steuerbote“ überdecken sich"],
		)

	def test_leaves_words_on_different_lines_alone(self):
		stacked = (word("Bemessungsgrundlage", 100, 200, width=80), word("EUR", 120, 210))
		self.assertEqual(printouts.overprint([Page(*A4, stacked)]), [])


class LastPageTest(TestCase):
	def test_a_single_page_may_be_short(self):
		self.assertEqual(printouts.last_page(pages(("a",)), MARGINS, 4), [])

	def test_names_a_last_page_with_almost_nothing_on_it(self):
		found = pages(("a", "b", "c", "d"), ("Dieser Ausdruck ist keine Abgabe.",))
		self.assertEqual(printouts.last_page(found, MARGINS, 4), ["letzte Seite mit nur 1 Zeilen"])

	def test_accepts_a_last_page_with_enough_lines(self):
		self.assertEqual(printouts.last_page(pages(("a",), ("a", "b", "c", "d")), MARGINS, 4), [])


class LonelyHeadingsTest(TestCase):
	def test_names_a_heading_that_ends_a_page(self):
		found = pages(("Zeile 1", "Befunde"), ("Art Code Nachricht", "Fehler"))
		self.assertEqual(
			printouts.lonely_headings(found, MARGINS, ("Befunde",)),
			["Seite 1: Überschrift „Befunde“ allein am Seitenende"],
		)

	def test_accepts_a_heading_followed_by_its_first_lines(self):
		found = pages(("Befunde", "Art Code Nachricht", "Fehler"), ("Fehler",))
		self.assertEqual(printouts.lonely_headings(found, MARGINS, ("Befunde",)), [])

	def test_the_last_line_of_the_last_page_is_no_concern(self):
		self.assertEqual(
			printouts.lonely_headings(
				pages(
					("a", "Befunde"),
				),
				MARGINS,
				("Befunde",),
			),
			[],
		)


class TogetherTest(TestCase):
	def test_accepts_a_block_on_one_page(self):
		found = pages(
			("Berechnung", "Gewerbesteuer 7.112,00", "Abschlusszahlung oder Erstattung 5.112,00"),
		)
		self.assertEqual(printouts.together(found, [("Berechnung", "Abschlusszahlung oder Erstattung")]), [])

	def test_names_a_total_separated_from_its_heading(self):
		found = pages(("Berechnung", "Gewerbesteuer"), ("Abschlusszahlung oder Erstattung",))
		self.assertEqual(
			printouts.together(found, [("Berechnung", "Abschlusszahlung oder Erstattung")]),
			["„Berechnung“ auf Seite 1, „Abschlusszahlung oder Erstattung“ auf Seite 2"],
		)

	def test_names_a_text_that_is_missing(self):
		self.assertEqual(
			printouts.together(pages(("Berechnung",)), [("Berechnung", "Gemeinde")]),
			["„Berechnung“ oder „Gemeinde“ fehlt"],
		)


class CheckTest(TestCase):
	def test_a_clean_printout_has_no_problems(self):
		found = pages(
			("GewSt-2026-00001", "Berechnung", "Gewerbesteuer"), ("GewSt-2026-00001", "a", "b", "c")
		)
		expected = Expectations(
			pages=(1, 3),
			on_every_page=("GewSt-2026-00001",),
			headings=("Befunde",),
			together=(("Berechnung", "Gewerbesteuer"),),
		)
		self.assertEqual(printouts.check(found, expected), [])

	def test_collects_the_problems_of_every_check(self):
		found = pages(("Zeile", "Befunde"), ("Fehler",))
		expected = Expectations(pages=(1, 1), on_every_page=("Zeile",), headings=("Befunde",))
		self.assertEqual(
			printouts.check(found, expected),
			[
				"2 Seiten statt 1 bis 1",
				"Seite 2: „Zeile“ fehlt",
				"letzte Seite mit nur 1 Zeilen",
				"Seite 1: Überschrift „Befunde“ allein am Seitenende",
			],
		)


class LanguageTest(TestCase):
	def test_names_a_text_the_printout_must_hold_and_lacks(self):
		found = pages(
			("Befunde", "Steuerbote hat die Vordrucke für 2026 vorläufig"),
		)
		self.assertEqual(printouts.somewhere(found, ["Steuerbote hat die Vordrucke"]), [])
		self.assertEqual(
			printouts.somewhere(found, ["Bemessungsgrundlage"]), ["„Bemessungsgrundlage“ fehlt im Ausdruck"]
		)

	def test_names_a_text_the_printout_must_not_hold(self):
		found = pages(("Befunde",), ("Steuerbote has the forms of 2026 provisionally",))
		self.assertEqual(
			printouts.nowhere(found, ["Steuerbote has"]), ["Seite 2: „Steuerbote has“ im Ausdruck"]
		)
		self.assertEqual(printouts.nowhere(found, ["Umsatzsteuer"]), [])

	def test_check_reports_both(self):
		expected = Expectations(pages=(1, 1), somewhere=("Seite",), nowhere=("Befunde",))
		self.assertEqual(printouts.check(pages(("Befunde",)), expected), ["Seite 1: „Befunde“ im Ausdruck"])

	def test_matches_whole_words_only(self):
		found = pages(("Dombauhütte der Kathedrale",), ("Steuerbote has the forms",))
		self.assertEqual(printouts.nowhere(found, ["the"]), ["Seite 2: „the“ im Ausdruck"])
