"""The shared parts of every print format of the app, read from the files without a bench: one stylesheet for all
eight, the running head and foot of every page, and the rules that keep a heading with its table on paper."""

import json
import re
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[1]
PRINT_FORMATS = APP / "steuerbote" / "print_format"
INCLUDES = APP / "templates" / "includes"
STYLE = "steuerbote/templates/includes/print/style.html"
RUNNING = "steuerbote/templates/includes/print/running.html"
CHROMIUM = "steuerbote/templates/includes/print/chromium.html"
# The parts that include the running head and foot for the print formats that include them.
RUNNING_FOR = (
	"steuerbote/templates/includes/annual_filing/head.html",
	"steuerbote/templates/includes/annual_accounts/offenlegung.html",
)
HEX_COLOUR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
CLASS_ATTRIBUTE = re.compile(r'\bclass="([^"]*)"')
CLASS_SELECTOR = re.compile(r"\.(-?[A-Za-z_][\w-]*)")
JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)
JINJA_TAG = re.compile(r"\{%.*?%\}|\{\{.*?\}\}", re.DOTALL)
# What Frappe and wkhtmltopdf give a meaning: the element whose rule holds the page margins, its frame in the
# preview, the elements Frappe hides in print, the header and footer it hands wkhtmltopdf and the page numbers.
FRAPPE_CLASSES = {"print-format", "print-format-gutter", "print-hide", "visible-pdf", "page", "topage"}


def read(path: str) -> str:
	return (APP.parent / path).read_text(encoding="utf-8")


def print_formats() -> dict[str, tuple[dict, str]]:
	return {
		path.parent.name: (
			json.loads(path.read_text(encoding="utf-8")),
			(path.parent / f"{path.parent.name}.html").read_text(encoding="utf-8"),
		)
		for path in PRINT_FORMATS.glob("*/*.json")
		if path.stem == path.parent.name
	}


def templates() -> dict[str, str]:
	"""Every template of a print format and every part they include."""
	found = {name: template for name, (_, template) in print_formats().items()}
	found.update(
		{
			str(path.relative_to(INCLUDES)): path.read_text(encoding="utf-8")
			for path in INCLUDES.rglob("*.html")
		}
	)
	return found


def rules(style: str) -> dict[str, str]:
	"""The rules of the stylesheet by their selector, without its comments, its Jinja tags and its @media blocks."""
	sheet = re.sub(r"</?style>", "", JINJA_TAG.sub("", JINJA_COMMENT.sub("", style)))
	sheet = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", sheet)
	return {" ".join(selector.split()): body for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", sheet)}


class OneStylesheetTest(TestCase):
	def test_every_print_format_includes_the_one_stylesheet_first_and_keeps_no_css_of_its_own(self):
		formats = print_formats()
		self.assertEqual(len(formats), 8)
		for name, (record, template) in formats.items():
			with self.subTest(print_format=name):
				self.assertEqual(record["css"], "")
				include = f'{{% include "{STYLE}" %}}'
				self.assertEqual(template.count(include), 1)
				self.assertLess(template.index(include), template.index('<div class="sb-print">'))
				self.assertEqual(template.count('<div class="sb-print">'), 1)

	def test_every_print_format_runs_a_head_and_foot_over_its_pages(self):
		running = f'{{% include "{RUNNING}" %}}'
		for path in RUNNING_FOR:
			with self.subTest(part=path):
				self.assertIn(running, read(path))
		parts = (running, *(f'{{% include "{path}" %}}' for path in RUNNING_FOR))
		for name, (_, template) in print_formats().items():
			with self.subTest(print_format=name):
				self.assertTrue(any(part in template for part in parts))
				self.assertIn("{%- set running_title = ", template)

	def test_prints_on_a4_with_the_margins_wkhtmltopdf_takes_from_the_print_format_rule(self):
		style = rules(read(STYLE))
		self.assertIn("size: A4 portrait", style["@page"])
		margins = dict(re.findall(r"([\w-]+):\s*([^;]+);", style[".print-format"]))
		self.assertEqual(
			margins,
			{
				"margin-top": "28mm",
				"margin-bottom": "18mm",
				"margin-left": "20mm",
				"margin-right": "15mm",
			},
		)
		self.assertIn(
			"margin: 0 !important", style[".print-format-gutter > .print-format, body > .print-format"]
		)

	def test_sets_no_spacing_of_head_or_foot_and_keeps_the_gap_inside_the_running_head(self):
		"""Frappe 16.60 hands header-spacing from the print CSS to its Chromium-based generator as text, which adds it
		to a number and fails every printout with a running head. Both generators measure the height of the head
		itself, so a gap at the bottom of the head lies between it and the content in either of them."""
		style = read(STYLE)
		self.assertNotRegex(style, r"(header|footer)-spacing")
		self.assertIn("bottom: 4mm;", rules(style)[".sb-running-rule"])

	def test_the_running_head_and_foot_fill_the_top_and_bottom_margins(self):
		"""wkhtmltopdf sets the head into the top margin, its bottom on the content, and the foot into the bottom
		margin, its top under the content. A head as high as the top margin and a foot as high as the bottom margin
		stand at the same place with the Chromium-based generator, which stacks margin, head and content."""
		style = rules(read(STYLE))
		margins = dict(re.findall(r"([\w-]+):\s*([^;]+);", style[".print-format"]))
		self.assertIn(f"height: {margins['margin-top']};", style[".sb-running-head"])
		self.assertIn(f"height: {margins['margin-bottom']};", style[".sb-running-foot"])
		self.assertIn("top: 4mm;", style[".sb-running-foot-rule"])

	def test_the_chromium_based_generator_gets_no_top_and_bottom_margin(self):
		"""Frappe's Chromium-based generator puts the head below the top margin and the foot above the bottom margin;
		with both at 0 the head and foot, as high as the margins, take their place. Frappe sets pdf_generator in the
		form_dict before it renders the print view for a PDF, and the jinja method reads it."""
		include = f'{{% include "{CHROMIUM}" %}}'
		self.assertRegex(
			read(STYLE),
			r'\{%-? if steuerbote_pdf_generator\(\) == "chrome" -?%\}\s*'
			+ re.escape(include)
			+ r"\s*\{%-? endif -?%\}",
		)
		self.assertEqual(
			dict(re.findall(r"([\w-]+):\s*([^;]+);", rules(read(CHROMIUM))[".print-format"])),
			{"margin-top": "0mm", "margin-bottom": "0mm"},
		)
		self.assertIn("steuerbote.steuerbote.about.steuerbote_pdf_generator", read("steuerbote/hooks.py"))

	def test_sets_a_font_with_the_metrics_of_helvetica_that_the_server_has(self):
		style = rules(read(STYLE))
		self.assertIn(
			'font-family: "Nimbus Sans", "Liberation Sans", Arial, Helvetica, sans-serif;',
			style[".sb-print, .sb-running"],
		)

	def test_sets_no_ligatures_which_turn_nr_into_the_numero_sign(self):
		"""Chromium sets Nimbus Sans with its ligatures, and they print „Nr.“ as „№“."""
		style = rules(read(STYLE))
		self.assertIn("font-variant-ligatures: none;", style[".sb-print, .sb-running"])
		self.assertIn('font-feature-settings: "liga" 0, "clig" 0, "dlig" 0;', style[".sb-print, .sb-running"])

	def test_prints_in_black_and_grey_and_loads_nothing(self):
		style = read(STYLE)
		for colour in HEX_COLOUR.findall(style):
			with self.subTest(colour=colour):
				channels = colour if len(colour) == 3 else (colour[0:2], colour[2:4], colour[4:6])
				self.assertEqual(len(set(channels)), 1)
		self.assertNotRegex(style, r"\b(rgb|hsl)a?\(|url\(|@import|<link")

	def test_repeats_the_head_of_a_table_and_keeps_rows_and_blocks_together(self):
		style = rules(read(STYLE))
		self.assertIn("display: table-header-group", style[".sb-print thead"])
		self.assertIn(
			"page-break-inside: avoid",
			style[
				".sb-print .sb-keep, .sb-print .sb-group, .sb-print .sb-footer, .sb-print .sb-angabe, .sb-print tr, .sb-print .sb-steps li"
			],
		)

	def test_hides_in_print_what_frappe_marks_for_the_screen(self):
		self.assertRegex(read(STYLE), r"@media print \{\s*\.print-hide \{\s*display: none !important;")


class RunningHeadAndFootTest(TestCase):
	def setUp(self):
		self.running = JINJA_COMMENT.sub("", read(RUNNING))

	def test_hands_wkhtmltopdf_a_header_and_a_footer_the_preview_hides(self):
		self.assertIn('<div id="header-html" class="visible-pdf">', self.running)
		self.assertIn('<div id="footer-html" class="visible-pdf">', self.running)

	def test_the_head_names_document_company_number_and_period(self):
		head = self.running[: self.running.index('<div id="footer-html"')]
		for text in (
			"running_title",
			"doc.company",
			"doc.name",
			"doc.status",
			"running_number",
			"running_period",
		):
			with self.subTest(text=text):
				self.assertIn(text, head)

	def test_the_foot_names_when_and_with_which_version_and_the_page_of_how_many(self):
		foot = self.running[self.running.index('<div id="footer-html"') :]
		self.assertIn("Erstellt am {{ running_created }} mit Steuerbote {{ steuerbote_version() | e }}", foot)
		self.assertIn('Seite <span class="page"></span> von <span class="topage"></span>', foot)
		self.assertIn(
			'frappe.utils.format_datetime(frappe.utils.now_datetime(), "dd.MM.yyyy HH:mm")', self.running
		)


class ClassesTest(TestCase):
	def test_every_class_is_one_of_its_own_and_styled_or_one_frappe_gives_a_meaning(self):
		styled = set(CLASS_SELECTOR.findall(re.sub(r"\d+\.\d+", "", JINJA_COMMENT.sub("", read(STYLE)))))
		self.assertEqual(
			sorted(name for name in styled if not name.startswith("sb-")),
			sorted(FRAPPE_CLASSES - {"visible-pdf", "page", "topage"}),
		)
		for name, template in templates().items():
			used = {
				item
				for value in CLASS_ATTRIBUTE.findall(JINJA_TAG.sub(" ", template))
				for item in value.split()
			}
			with self.subTest(template=name):
				self.assertEqual(
					sorted(used - FRAPPE_CLASSES - {item for item in used if item.startswith("sb-")}), []
				)
				self.assertEqual(
					sorted(item for item in used if item.startswith("sb-") and item not in styled), []
				)


class HeadingsTest(TestCase):
	def test_a_table_with_a_head_carries_its_heading_in_it(self):
		"""wkhtmltopdf ignores page-break-after, so a heading before a table could end a page alone; as the first
		row of the head it stays with the first rows and repeats on every page of the table."""
		for name, template in templates().items():
			with self.subTest(template=name):
				self.assertNotRegex(
					template,
					r"</h2>\s*<table class=\"sb-lines[^\"]*\">\s*(<colgroup>.*?</colgroup>\s*)?<thead>",
				)

	def test_a_table_whose_head_starts_with_its_heading_sets_its_columns(self):
		"""A table with table-layout: fixed takes the widths of its columns from the first row, which the heading
		spans; the colgroup sets them instead, written out or by a macro of the template."""
		for name, template in templates().items():
			for table in re.findall(r"<table[^>]*>.*?</table>", template, re.DOTALL):
				if 'class="sb-caption"' in table:
					with self.subTest(template=name):
						head = table[: table.index('class="sb-caption"')]
						self.assertRegex(head, r"<colgroup>|_columns\(\w*\) \}\}")

	def test_a_section_of_a_form_keeps_its_heading_with_its_first_rows(self):
		"""wkhtmltopdf keeps a row together but not a group of rows: the heading of a section and its first rows stand
		in a table of their own inside one row of the form, so that a section never starts with its heading alone at
		the foot of a page."""
		for name, template in templates().items():
			for group in template.split('<tbody class="sb-group">')[1:]:
				group = group[: group.index("</tbody>")]
				for heading in ('class="sb-section"', 'class="sb-group-head"'):
					if heading in group:
						with self.subTest(template=name, heading=heading):
							self.assertLess(group.index('<td class="sb-nest"'), group.index(heading))


class AnlagenspiegelTest(TestCase):
	def test_puts_each_position_on_a_line_above_its_amounts_so_that_eight_columns_fit_a4(self):
		"""Abschreibungen und Buchwert has eight columns of amounts (layout.DEPRECIATION_COLUMNS): beside a column for
		the position and one for the Wertart they ran off a portrait page."""
		_, template = print_formats()["e_bilanz"]
		(macro,) = re.findall(r"macro asset_columns\(columns\).*?endmacro", template, re.DOTALL)
		self.assertEqual(macro.count("<col"), 3)
		self.assertIn("{%- for column in columns %}", macro)
		self.assertEqual(template.count('<tr class="sb-asset">'), 1)
		self.assertIn("· {{ row.value_type | e }}</td></tr>", template)
		self.assertIn("· {{ total.value_type | e }}</td></tr>", template)


FEW_FINDINGS = '{%- if annual.findings | length <= 8 %}<div class="sb-keep">{% endif %}'
MANY_FINDINGS = '{%- if annual.findings | length > 8 %}<div class="sb-keep">{% endif %}'
REMARKS = '{% include "steuerbote/templates/includes/annual_filing/remarks.html" %}'
FINDINGS = '{% include "steuerbote/templates/includes/annual_filing/findings.html" %}'
FOOTER = '{% include "steuerbote/templates/includes/annual_filing/footer.html" %}'


class ClosingTest(TestCase):
	"""Alone, the closing note of three lines can end up on a page of its own. It moves to the next page together with
	the remarks, and with up to eight findings with the findings too; more findings fill the pages before."""

	def test_an_annual_document_keeps_the_closing_note_with_the_remarks_and_few_findings(self):
		for name, (_, template) in print_formats().items():
			if FOOTER not in template:
				continue
			with self.subTest(print_format=name):
				self.assertLess(template.index(FEW_FINDINGS), template.index(FINDINGS))
				self.assertLess(template.index(FINDINGS), template.index(MANY_FINDINGS))
				self.assertLess(template.index(MANY_FINDINGS), template.index(REMARKS))
				self.assertRegex(template[template.index(FOOTER) :], r"^\{% include [^%]+%\}\s*</div>")

	def test_the_other_formats_keep_the_closing_note_with_the_remarks(self):
		for name, (_, template) in print_formats().items():
			if FOOTER in template:
				continue
			with self.subTest(print_format=name):
				closing = template[template.rindex('<div class="sb-keep">') :]
				self.assertRegex(closing, r"<h2>(Anmerkungen|Bemerkungen)</h2>")
				self.assertIn('<div class="sb-footer">', closing)
