"""Checks of a printout as PDF, on the words and their boxes that `pdftotext -bbox` of Poppler reads from each page.

A print format can look right in the preview of the browser and still break badly on paper: a heading alone at the
foot of a page, a code that runs into the message beside it, an amount cut off at the edge, a last page with one line.
These checks find what can be found without eyes, on the PDF that wkhtmltopdf made. The module imports no Frappe; the
proof in CI (print_proof.py) renders the printouts and hands their words to it.
"""

import html
import itertools
import re
from dataclasses import dataclass, field

# 1 mm in PDF points.
MM = 72 / 25.4
# Words whose baselines differ by less than this many points stand on the same line.
SAME_LINE = 2.0
# Two words on a line may touch; overlapping by more than this many points, one is printed over the other.
OVERPRINT = 0.8
# How far a word may reach into the margin before it counts as cut off or bleeding, in points.
BLEED = 1.0
# How far apart the same line may stand in the printouts of the two generators, in points.
SAME_PLACE = 1 * MM

PAGE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.DOTALL)
WORD = re.compile(
	r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', re.DOTALL
)


@dataclass(frozen=True)
class Word:
	x0: float
	y0: float
	x1: float
	y1: float
	text: str


@dataclass(frozen=True)
class Page:
	width: float
	height: float
	words: tuple[Word, ...]


@dataclass(frozen=True)
class Margins:
	"""The margins of the body of a page in millimetres; the running head and foot stand in top and bottom."""

	top: float
	bottom: float
	left: float
	right: float


@dataclass(frozen=True)
class Expectations:
	"""What a printout must hold: its pages, the texts on every page, the headings that must not end a page, the
	pairs of texts that must stand on the same page, the least number of lines of the body of a last page, texts it
	must hold somewhere, such as one in the language it is printed in, and texts it must not hold anywhere."""

	pages: tuple[int, int]
	on_every_page: tuple[str, ...] = ()
	headings: tuple[str, ...] = ()
	together: tuple[tuple[str, str], ...] = ()
	last_page_lines: int = 4
	somewhere: tuple[str, ...] = ()
	nowhere: tuple[str, ...] = ()
	margins: Margins = field(default_factory=lambda: Margins(top=28, bottom=18, left=20, right=15))


def read_bbox(xhtml: str) -> list[Page]:
	"""The pages of the output of `pdftotext -bbox` with their words in reading order."""
	pages = []
	for width, height, content in PAGE.findall(xhtml):
		words = tuple(
			Word(float(x0), float(y0), float(x1), float(y1), html.unescape(text).strip())
			for x0, y0, x1, y1, text in WORD.findall(content)
		)
		pages.append(Page(float(width), float(height), words))
	return pages


def lines(words) -> list[list[Word]]:
	"""The words grouped into lines by their baseline, top to bottom, each line left to right."""
	result: list[list[Word]] = []
	for word in sorted(words, key=lambda word: (word.y1, word.x0)):
		if result and abs(result[-1][0].y1 - word.y1) < SAME_LINE:
			result[-1].append(word)
		else:
			result.append([word])
	return [sorted(line, key=lambda word: word.x0) for line in result]


def text_of(line) -> str:
	return " ".join(word.text for word in line)


def body(page: Page, margins: Margins) -> list[Word]:
	"""The words between the running head and the running foot."""
	top, bottom = margins.top * MM, page.height - margins.bottom * MM
	return [word for word in page.words if word.y0 >= top - BLEED and word.y1 <= bottom + BLEED]


def page_text(page: Page) -> str:
	return " ".join(text_of(line) for line in lines(page.words))


def page_count(pages, low: int, high: int) -> list[str]:
	if low <= len(pages) <= high:
		return []
	return [f"{len(pages)} Seiten statt {low} bis {high}"]


def page_numbers(pages) -> list[str]:
	"""Each page names itself as „Seite n von N“."""
	total = len(pages)
	return [
		f"Seite {number}: keine Seitenzahl „Seite {number} von {total}“"
		for number, page in enumerate(pages, start=1)
		if f"Seite {number} von {total}" not in page_text(page)
	]


def on_every_page(pages, texts) -> list[str]:
	return [
		f"Seite {number}: „{text}“ fehlt"
		for number, page in enumerate(pages, start=1)
		for text in texts
		if " ".join(text.split()) not in page_text(page)
	]


def bleed(pages, margins: Margins) -> list[str]:
	"""No word starts left of the left margin or ends right of the right margin, where the paper or a printer cuts it."""
	problems = []
	for number, page in enumerate(pages, start=1):
		left, right = margins.left * MM - BLEED, page.width - margins.right * MM + BLEED
		problems += [
			f"Seite {number}: „{word.text}“ läuft über den Rand"
			for word in page.words
			if word.x0 < left or word.x1 > right
		]
	return problems


def overprint(pages) -> list[str]:
	"""No word on a line overlaps the next one, as a code that runs into the message beside it does."""
	problems = []
	for number, page in enumerate(pages, start=1):
		for line in lines(page.words):
			problems += [
				f"Seite {number}: „{first.text}“ und „{second.text}“ überdecken sich"
				for first, second in itertools.pairwise(line)
				if second.x0 < first.x1 - OVERPRINT
			]
	return problems


def last_page(pages, margins: Margins, least: int) -> list[str]:
	"""A printout of more than one page does not end on a page with almost nothing on it."""
	if len(pages) < 2:
		return []
	count = len(lines(body(pages[-1], margins)))
	return [] if count >= least else [f"letzte Seite mit nur {count} Zeilen"]


def lonely_headings(pages, margins: Margins, headings) -> list[str]:
	"""No page but the last ends with a heading whose table or text begins on the next page."""
	problems = []
	for number, page in enumerate(pages[:-1], start=1):
		page_lines = lines(body(page, margins))
		if page_lines and text_of(page_lines[-1]) in headings:
			problems.append(f"Seite {number}: Überschrift „{text_of(page_lines[-1])}“ allein am Seitenende")
	return problems


def first_page_of(pages, text: str) -> int | None:
	wanted = " ".join(text.split())
	for number, page in enumerate(pages, start=1):
		if wanted in page_text(page):
			return number
	return None


def together(pages, pairs) -> list[str]:
	"""Each pair of texts, such as a heading and the total of its block, stands on the same page."""
	problems = []
	for first, second in pairs:
		one, other = first_page_of(pages, first), first_page_of(pages, second)
		if one is None or other is None:
			problems.append(f"„{first}“ oder „{second}“ fehlt")
		elif one != other:
			problems.append(f"„{first}“ auf Seite {one}, „{second}“ auf Seite {other}")
	return problems


def somewhere(pages, texts) -> list[str]:
	"""Each text stands on some page, such as a text in the language the printout is meant to be in."""
	return [f"„{text}“ fehlt im Ausdruck" for text in texts if first_page_of(pages, text) is None]


def nowhere(pages, texts) -> list[str]:
	"""No text stands on any page as whole words, such as a word of the source language a missing translation falls
	back to."""
	return [
		f"Seite {number}: „{text}“ im Ausdruck"
		for text in texts
		for number, page in enumerate(pages, start=1)
		if f" {' '.join(text.split())} " in f" {page_text(page)} "
	]


@dataclass(frozen=True)
class Frame:
	"""Where on a page the running head ends, the content begins and the running foot begins, in points from the top
	edge; None where the page has nothing there."""

	head: float | None
	first: float | None
	foot: float | None


def frame(page: Page, margins: Margins) -> Frame:
	top, bottom = margins.top * MM, page.height - margins.bottom * MM
	return Frame(
		head=max((word.y1 for word in page.words if word.y1 < top - BLEED), default=None),
		first=min((word.y0 for word in body(page, margins)), default=None),
		foot=min((word.y0 for word in page.words if word.y0 > bottom + BLEED), default=None),
	)


def _mm(points: float | None) -> str:
	return "keins" if points is None else f"{points / MM:.1f} mm".replace(".", ",")


def alike(wkhtmltopdf, chromium, margins: Margins) -> list[str]:
	"""The printout of one document with both generators: the same number of pages, and on each page the head, the
	first line and the foot at the same place, so that it does not matter which generator a site prints with."""
	if len(wkhtmltopdf) != len(chromium):
		return [f"wkhtmltopdf {len(wkhtmltopdf)} Seiten, Chromium {len(chromium)} Seiten"]
	problems = []
	for number, (one, other) in enumerate(zip(wkhtmltopdf, chromium, strict=True), start=1):
		first, second = frame(one, margins), frame(other, margins)
		for label, here, there in (
			("Ende des Kopfs", first.head, second.head),
			("erste Zeile", first.first, second.first),
			("Fuß", first.foot, second.foot),
		):
			if (here is None) != (there is None) or (
				here is not None and there is not None and abs(here - there) > SAME_PLACE
			):
				problems.append(
					f"Seite {number}: {label} mit wkhtmltopdf {_mm(here)}, mit Chromium {_mm(there)}"
				)
	return problems


def check(pages, expected: Expectations) -> list[str]:
	"""Every problem of a printout, empty when it is clean."""
	margins = expected.margins
	return [
		*page_count(pages, *expected.pages),
		*page_numbers(pages),
		*on_every_page(pages, expected.on_every_page),
		*bleed(pages, margins),
		*overprint(pages),
		*last_page(pages, margins, expected.last_page_lines),
		*lonely_headings(pages, margins, expected.headings),
		*together(pages, expected.together),
		*somewhere(pages, expected.somewhere),
		*nowhere(pages, expected.nowhere),
	]
