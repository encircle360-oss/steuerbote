"""Über Steuerbote, read from the files without a bench: the block that says who makes Steuerbote and where its source,
documentation and issues are, at the bottom of the workspace Steuern and on the page Steuerbote einrichten, and the
line of every printout that names the version of Steuerbote that made it."""

import csv
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from unittest import TestCase

from steuerbote import __version__, hooks
from steuerbote.steuerbote import about

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "steuerbote"
WORKSPACE = MODULE / "workspace" / "steuern" / "steuern.json"
SETUP_PAGE = MODULE / "page" / "steuerbote_setup" / "steuerbote_setup.js"
ENDPOINT = MODULE / "about_block.py"
FIXTURE = APP / "fixtures" / "custom_html_block.json"
TRANSLATIONS = APP / "translations" / "de.csv"
PRINT_FORMATS = MODULE / "print_format"
INCLUDES = APP / "templates" / "includes"
CREATED_WITH = "steuerbote/templates/includes/created_with.html"
ANNUAL_FOOTER = "steuerbote/templates/includes/annual_filing/footer.html"
METHOD = "steuerbote.steuerbote.about_block.render"
REPOSITORY = "https://github.com/encircle360-oss/steuerbote"
# What the block shows in German, word for word, and where its links lead.
GERMAN = {
	"title": f"Steuerbote {__version__}",
	"licence": "Steuerbote ist freie Software (AGPL-3.0) der encircle360 GmbH und aller Mitwirkenden.",
	"disclaimer": "Ohne Gewähr. Steuerbote ersetzt keine steuerliche Beratung.",
	"services": "Einführung, Betrieb und Unterstützung: encircle360.com",
}
LINKS = [
	("Quelltext", REPOSITORY),
	("Dokumentation", f"{REPOSITORY}/tree/main/docs"),
	("Fehler melden", f"{REPOSITORY}/issues"),
	("Haftungsausschluss", f"{REPOSITORY}/blob/main/docs/haftungsausschluss.md"),
	("encircle360.com", "https://encircle360.com/?ref=steuerbote"),
]
# The print formats that carry their footer themselves; the annual ones share footer.html.
OWN_FOOTER = ("umsatzsteuer_voranmeldung", "zusammenfassende_meldung", "dauerfristverlängerung")


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def german(text: str) -> str:
	return translations().get(text, text)


class Markup(HTMLParser):
	"""The elements of a piece of HTML with their attributes, the links with their text, and the text."""

	def __init__(self, markup: str):
		super().__init__()
		self.elements: list[tuple[str, dict[str, str | None]]] = []
		self.links: list[tuple[str, dict[str, str | None]]] = []
		self.text: list[str] = []
		self._link: dict[str, str | None] | None = None
		self._link_text: list[str] = []
		self.feed(markup)

	def handle_starttag(self, tag, attrs):
		self.elements.append((tag, dict(attrs)))
		if tag == "a":
			self._link, self._link_text = dict(attrs), []

	def handle_endtag(self, tag):
		if tag == "a" and self._link is not None:
			self.links.append(("".join(self._link_text).strip(), self._link))
			self._link = None

	def handle_data(self, data):
		self.text.append(data)
		if self._link is not None:
			self._link_text.append(data)

	def lines(self) -> list[str]:
		return [line for line in (re.sub(r"\s+", " ", part).strip() for part in self.text) if line]


def remote(markup: str) -> list[str]:
	"""Whatever in a piece of HTML would make the browser load something by itself rather than on a click."""
	found = re.findall(r"<\s*(?:script|link|iframe|object|embed|video|audio|source)\b", markup, re.IGNORECASE)
	found += re.findall(r"url\(|@import|srcset", markup, re.IGNORECASE)
	parsed = Markup(markup)
	found += [
		value or ""
		for tag, attributes in parsed.elements
		for name, value in attributes.items()
		if name in {"src", "poster", "data"} and not (value or "").startswith("/assets/steuerbote/")
	]
	found += [
		attributes.get("href") or ""
		for tag, attributes in parsed.elements
		if tag != "a" and "href" in attributes
	]
	return found


class AboutBlockTest(TestCase):
	def setUp(self):
		self.markup = about.render(german)
		self.parsed = Markup(self.markup)

	def test_shows_the_logo_the_version_the_licence_and_the_links_in_german(self):
		self.assertIn(
			("img", "/assets/steuerbote/images/steuerbote-logo.svg"),
			[(tag, attributes.get("src")) for tag, attributes in self.parsed.elements],
		)
		lines = " ".join(self.parsed.lines())
		for part, text in GERMAN.items():
			with self.subTest(part=part):
				self.assertIn(text, lines)
		self.assertEqual([(text, attributes["href"]) for text, attributes in self.parsed.links], LINKS)

	def test_shows_the_version_it_is_given_and_by_default_the_installed_one(self):
		self.assertIn(f"Steuerbote {__version__}", " ".join(Markup(about.render(str)).lines()))
		self.assertIn("Steuerbote 99.1.0", " ".join(Markup(about.render(str, "99.1.0")).lines()))
		self.assertIn("Steuerbote 1&lt;2", about.render(str, "1<2"))

	def test_the_pages_it_links_in_the_repository_exist(self):
		for text, attributes in self.parsed.links:
			path = (attributes.get("href") or "").removeprefix(f"{REPOSITORY}/").split("/", 2)
			if path[0] in {"blob", "tree"}:
				with self.subTest(link=text):
					self.assertTrue((APP.parent / path[2]).exists())

	def test_every_link_opens_in_a_new_tab_without_telling_where_it_came_from(self):
		for text, attributes in self.parsed.links:
			with self.subTest(link=text):
				self.assertEqual(attributes.get("target"), "_blank")
				self.assertEqual(set((attributes.get("rel") or "").split()), {"noopener", "noreferrer"})

	def test_loads_nothing_from_another_site(self):
		self.assertEqual(remote(self.markup), [])

	def test_follows_the_colours_of_the_desk_in_light_and_dark(self):
		"""No colour of its own: the variables of the desk, which its dark theme sets anew."""
		self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|\b(?:white|black)\b", self.markup), [])
		for variable in ("--border-color", "--card-bg", "--text-color"):
			with self.subTest(variable=variable):
				self.assertIn(f"var({variable}", self.markup)

	def test_wraps_on_a_narrow_screen(self):
		(section,) = [attributes for tag, attributes in self.parsed.elements if tag == "section"]
		self.assertIn("flex-wrap: wrap", section["style"] or "")
		self.assertIn("min-width: 0", self.markup)

	def test_escapes_what_a_translation_brings(self):
		markup = about.render(lambda text: f"<b>{text}</b>")
		self.assertNotIn("<b>", markup)

	def test_every_text_reads_in_german(self):
		self.assertEqual(sorted(set(about.TEXTS) - translations().keys()), [])
		self.assertEqual(german("About Steuerbote"), about.BLOCK)


class AboutBlockPlacesTest(TestCase):
	def test_the_workspace_ends_with_the_block(self):
		workspace = json.loads(WORKSPACE.read_text(encoding="utf-8"))
		blocks = json.loads(workspace["content"])
		self.assertEqual(
			[(block["type"], block["data"]) for block in blocks[-2:]],
			[("spacer", {"col": 12}), ("custom_block", {"custom_block_name": about.BLOCK, "col": 12})],
		)
		self.assertEqual(
			workspace["custom_blocks"], [{"custom_block_name": about.BLOCK, "label": about.BLOCK}]
		)

	def test_the_block_of_the_workspace_is_a_fixture_open_to_every_user_of_the_desk(self):
		self.assertIn({"dt": "Custom HTML Block", "filters": [["name", "=", about.BLOCK]]}, hooks.fixtures)
		(block,) = json.loads(FIXTURE.read_text(encoding="utf-8"))
		self.assertEqual(
			{key: block[key] for key in ("doctype", "name", "private", "roles")},
			{"doctype": "Custom HTML Block", "name": about.BLOCK, "private": 0, "roles": []},
		)
		self.assertEqual(remote(block["html"]), [])
		self.assertIn(f'method: "{METHOD}"', block["script"])
		self.assertIn("root_element.querySelector", block["script"])
		self.assertNotIn("http", block["script"] + (block["style"] or ""))

	def test_the_setup_page_shows_the_same_block_below_its_report(self):
		script = SETUP_PAGE.read_text(encoding="utf-8")
		(method,) = re.findall(r'const ABOUT_METHOD = "([\w.]+)";', script)
		self.assertEqual(method, METHOD)
		self.assertIn("frappe.call({ method: ABOUT_METHOD })", script)
		self.assertRegex(script, r"report,\n\t\tabout\n\t\)")

	def test_the_desk_gets_the_block_from_the_endpoint_in_the_language_of_the_user(self):
		source = ENDPOINT.read_text(encoding="utf-8")
		self.assertRegex(source, r"@frappe\.whitelist\(\)\ndef render\(\) -> str:")
		self.assertIn("return about.render(_)", source)


class CreatedWithTest(TestCase):
	def test_every_print_format_ends_its_footer_with_the_version_of_steuerbote(self):
		print_formats = sorted(
			path.parent.name for path in PRINT_FORMATS.glob("*/*.json") if path.stem == path.parent.name
		)
		self.assertEqual(len(print_formats), 8)
		annual = (APP.parent / ANNUAL_FOOTER).read_text(encoding="utf-8")
		self.assertRegex(annual, rf'\{{% include "{CREATED_WITH}" %\}}\n</div>\s*$')
		for name in print_formats:
			with self.subTest(print_format=name):
				markup = (PRINT_FORMATS / name / f"{name}.html").read_text(encoding="utf-8")
				if name in OWN_FOOTER:
					self.assertRegex(
						markup,
						re.compile(
							rf'<div class="sb-footer">.*?\{{% include "{CREATED_WITH}" %\}}\n\t</div>', re.S
						),
					)
				else:
					self.assertIn(f'{{% include "{ANNUAL_FOOTER}" %}}', markup)

	def test_the_line_is_small_and_grey_and_names_the_version_without_a_logo_or_a_link(self):
		line = (INCLUDES / "created_with.html").read_text(encoding="utf-8")
		(markup,) = [part for part in line.split("#}") if "<p" in part]
		self.assertEqual(
			markup.strip(),
			'<p style="color: #777;">Erstellt mit Steuerbote {{ steuerbote_version() | e }}</p>',
		)

	def test_the_version_comes_from_the_app(self):
		self.assertEqual(
			hooks.jinja,
			{
				"methods": [
					"steuerbote.steuerbote.about.steuerbote_version",
					"steuerbote.steuerbote.about.steuerbote_pdf_generator",
				]
			},
		)
		self.assertEqual(about.steuerbote_version(), __version__)
