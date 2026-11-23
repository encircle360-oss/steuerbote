"""The standard records the app ships fit together, read from their files without a bench.

Frappe imports them on install without checking, for example, that a workspace block names an existing
shortcut or that a filter of a report reaches its Python.
"""

import ast
import csv
import json
import re
import struct
from pathlib import Path
from unittest import TestCase
from xml.etree import ElementTree

from steuerbote import hooks
from steuerbote.ustva import KENNZAHLEN, WatchLevel

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "steuerbote"
FIXTURES = APP / "fixtures"
TRANSLATIONS = APP / "translations" / "de.csv"
REPORT = MODULE / "report" / "ustva_kennzahlen"
WORKSPACE = MODULE / "workspace" / "steuern" / "steuern.json"
SIDEBAR = MODULE / "sidebar" / "steuerbote" / "steuerbote.json"
NUMBER_CARDS = MODULE / "number_card"
PRINT_FORMAT = MODULE / "print_format" / "umsatzsteuer_voranmeldung"
ZM_PRINT_FORMAT = MODULE / "print_format" / "zusammenfassende_meldung"
ZM_SCRIPT = MODULE / "doctype" / "recapitulative_statement" / "recapitulative_statement.js"
VAT_RETURN_SCRIPT = MODULE / "doctype" / "vat_return" / "vat_return.js"
TRANSMISSION_SCRIPT = APP / "public" / "js" / "elster_transmission.js"
MAPPING = MODULE / "doctype" / "vat_return_mapping"
MAPPING_RULE = MODULE / "doctype" / "vat_return_mapping_rule" / "vat_return_mapping_rule.json"
WATCHED_ACCOUNT = MODULE / "doctype" / "vat_return_watched_account" / "vat_return_watched_account.json"
MAPPING_DOCTYPES = (
	"vat_return_mapping",
	"vat_return_mapping_rule",
	"vat_return_mapping_check",
	"vat_return_watched_account",
	"vat_return_annual_rule",
)
# The charts of the mapping read the same in every language.
CHART_NAMES = frozenset({"SKR03", "SKR04", "Eigener Kontenrahmen"})
DOCK = APP / "dock" / "steuerbote" / "steuerbote.json"
PERMISSIONS = APP / "permissions.py"
PUBLIC = APP / "public"
LOGO = PUBLIC / "images" / "steuerbote-logo.svg"
LOGO_PNG = PUBLIC / "images" / "steuerbote-logo.png"
# Frappe serves the public folder of an app under this path.
ASSETS = "/assets/steuerbote/"
SVG = "{http://www.w3.org/2000/svg}"
# What would put text, pixels, code or content from elsewhere into a drawing.
NOT_A_SHAPE = frozenset(
	f"{SVG}{tag}" for tag in ("text", "image", "script", "style", "foreignObject", "use", "a")
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Names of the app that read the same in every language.
GERMAN_NAMES = frozenset({"Steuern", "Offene Voranmeldungen", "UStVA Kennzahlen", "Offene Fristen"})
# The German that Frappe shows for the framework labels of the shortcuts and the sidebar.
FRAMEWORK_GERMAN = {"Reports": "Berichte", "Settings": "Einstellungen"}
# Labels Frappe and ERPNext translate themselves; the app keeps out of their translations.
FRAMEWORK_LABELS = frozenset(
	{
		"Account",
		"Company",
		"Credit",
		"Currency",
		"Debit",
		"Party",
		"Posting Date",
		"Print",
		"Setup",
		"Voucher No",
		"Voucher Type",
		*FRAMEWORK_GERMAN,
	}
)
# The desk cuts a label after about 22 characters, in the sidebar as on a shortcut card.
LONGEST_LABEL = 20
# The DocType of the Dauerfristverlängerung, which comes with its own package of the module; the workspace and
# the sidebar lead to it.
DAUERFRIST_DOCTYPE = "VAT Return Extension"
# The lists of the year-end filings, which the section „Jahresmeldungen“ of the sidebar and the workspace will lead
# to once their documents exist; until then the sidebar leaves them out.
AWAITING_THE_SECTION_JAHRESMELDUNGEN = frozenset(
	{"Annual Filing Settings", "Income Tax Mapping", "Annual VAT Return", "Balance Sheet Mapping"}
)
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")
HEX_COLOUR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
CLASS_ATTRIBUTE = re.compile(r'\bclass="([^"]*)"')
CLASS_SELECTOR = re.compile(r"\.(-?[A-Za-z_][\w-]*)")
# Frappe's print stylesheet styles bare classes such as .label (inline, 75 %, bold), so the print format
# names its classes with a prefix of its own.
PRINT_CLASS_PREFIX = "sb-"


def read_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def translated() -> set[str]:
	return set(translations())


def german(text: str) -> str:
	return translations().get(text) or FRAMEWORK_GERMAN.get(text, text)


def doctype_names() -> set[str]:
	return {read_json(path)["name"] for path in (MODULE / "doctype").glob("*/*.json")}


def report_names() -> set[str]:
	return {read_json(path)["name"] for path in (MODULE / "report").glob("*/*.json")}


def page_names() -> set[str]:
	return {read_json(path)["name"] for path in (MODULE / "page").glob("*/*.json")}


def doctypes_with_a_list() -> set[str]:
	"""The DocTypes of the module that are not child tables, the ones Frappe's sidebar links to."""
	definitions = (read_json(path) for path in (MODULE / "doctype").glob("*/*.json"))
	return {definition["name"] for definition in definitions if not definition.get("istable")}


def untranslated(texts: set[str]) -> list[str]:
	return sorted(texts - translated() - GERMAN_NAMES - FRAMEWORK_LABELS)


def asset(url: str) -> Path | None:
	"""The file behind a URL of the app's public folder, or None for any other URL."""
	return PUBLIC / url.removeprefix(ASSETS) if url.startswith(ASSETS) else None


def png_size(path: Path) -> tuple[int, int]:
	"""Width and height from the IHDR chunk, which follows the signature of every PNG file."""
	header = path.read_bytes()[:24]
	if header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
		raise ValueError(f"{path.name} is no PNG file")
	width, height = struct.unpack(">II", header[16:24])
	return width, height


class ReportFilesTest(TestCase):
	def test_the_report_is_a_standard_script_report_of_the_vat_return(self):
		report = read_json(REPORT / "ustva_kennzahlen.json")
		self.assertEqual(
			{
				key: report[key]
				for key in ("name", "report_name", "report_type", "ref_doctype", "is_standard", "module")
			},
			{
				"name": "UStVA Kennzahlen",
				"report_name": "UStVA Kennzahlen",
				"report_type": "Script Report",
				"ref_doctype": "VAT Return",
				"is_standard": "Yes",
				"module": "Steuerbote",
			},
		)
		self.assertIn("VAT Return", doctype_names())

	def test_the_filters_of_the_script_are_those_the_report_reads(self):
		script = (REPORT / "ustva_kennzahlen.js").read_text(encoding="utf-8")
		source = (REPORT / "ustva_kennzahlen.py").read_text(encoding="utf-8")
		fieldnames = re.findall(r'fieldname: "(\w+)"', script)
		self.assertEqual(fieldnames, ["company", "year", "rhythm", "period_index", "only_deviations"])
		assignments = {
			target.id: node.value
			for node in ast.parse(source).body
			if isinstance(node, ast.Assign)
			for target in node.targets
			if isinstance(target, ast.Name)
		}
		self.assertEqual(
			[*ast.literal_eval(assignments["FILTERS"]), ast.literal_eval(assignments["ONLY_DEVIATIONS"])],
			fieldnames,
		)

	def test_the_vat_return_opens_the_report_with_its_own_period(self):
		script = (MODULE / "doctype" / "vat_return" / "vat_return.js").read_text(encoding="utf-8")
		route = re.search(
			r'frappe\.set_route\("query-report", "UStVA Kennzahlen", \{(?P<filters>[^}]*)\}', script
		)
		self.assertIsNotNone(route)
		self.assertEqual(
			re.findall(r"(\w+): frm\.doc\.(\w+)", route["filters"]),
			[(field, field) for field in ("company", "year", "rhythm", "period_index")],
		)

	def test_the_report_shows_its_texts_as_they_read(self):
		"""Frappe writes a Data cell of a report into the page as HTML, so a party called <img src=x onerror=…>
		would run as code. Only the column Print holds HTML on purpose; the formatter escapes every other Data
		cell before Frappe formats it."""
		script = (REPORT / "ustva_kennzahlen.js").read_text(encoding="utf-8")
		formatter = re.search(r"\n\tformatter\(([^)]*)\) \{\n(?P<body>.*?)\n\t\},\n", script, re.DOTALL)
		self.assertIsNotNone(formatter)
		for part in (
			'column.fieldtype === "Data" && column.fieldname !== "print_link"',
			"default_formatter(text ? frappe.utils.escape_html(value) : value, row, column, data)",
		):
			with self.subTest(part=part):
				self.assertIn(part, formatter["body"])
		source = (REPORT / "ustva_kennzahlen.py").read_text(encoding="utf-8")
		data_columns = set(
			re.findall(r'\{"fieldname": "(\w+)", "label": _\("[^"]*"\), "fieldtype": "Data"', source)
		)
		self.assertEqual(data_columns, {"kennzahl", "label", "print_link", "party"})

	def test_every_label_of_the_report_is_translated(self):
		texts = set()
		for name in ("ustva_kennzahlen.js", "ustva_kennzahlen.py"):
			texts.update(TRANSLATED_LITERAL.findall((REPORT / name).read_text(encoding="utf-8")))
		self.assertIn("Ledger Amount", texts)
		self.assertEqual(untranslated(texts), [])


class WorkspaceFilesTest(TestCase):
	def setUp(self):
		self.workspace = read_json(WORKSPACE)
		self.blocks = json.loads(self.workspace["content"])

	def test_the_workspace_belongs_to_the_module(self):
		self.assertEqual(
			{key: self.workspace[key] for key in ("name", "label", "title", "module", "public", "type")},
			{
				"name": "Steuern",
				"label": "Steuern",
				"title": "Steuern",
				"module": "Steuerbote",
				"public": 1,
				"type": "Workspace",
			},
		)

	def test_every_block_names_a_shortcut_or_number_card_of_the_workspace(self):
		shortcuts = {shortcut["label"] for shortcut in self.workspace["shortcuts"]}
		cards = {card["label"] for card in self.workspace["number_cards"]}
		named = {
			"shortcut": [
				block["data"]["shortcut_name"] for block in self.blocks if block["type"] == "shortcut"
			],
			"number_card": [
				block["data"]["number_card_name"] for block in self.blocks if block["type"] == "number_card"
			],
		}
		self.assertEqual(sorted(named["shortcut"]), sorted(shortcuts))
		self.assertEqual(sorted(named["number_card"]), sorted(cards))
		self.assertEqual(len({block["id"] for block in self.blocks}), len(self.blocks))

	def test_the_shortcuts_open_the_returns_the_statements_their_setup_and_the_report(self):
		targets = {
			(shortcut["type"], shortcut["link_to"], shortcut.get("doc_view", ""))
			for shortcut in self.workspace["shortcuts"]
		}
		self.assertEqual(
			targets,
			{
				("DocType", "VAT Return", "New"),
				("DocType", "VAT Return", "List"),
				("DocType", DAUERFRIST_DOCTYPE, "List"),
				("DocType", "Recapitulative Statement", "New"),
				("DocType", "Recapitulative Statement", "List"),
				("DocType", "VAT ID Confirmation", "List"),
				("DocType", "VAT Return Settings", "List"),
				("DocType", "VAT Return Mapping", "List"),
				("Report", "UStVA Kennzahlen", ""),
				("Report", "Offene Fristen", ""),
				("Page", "steuerbote-setup", ""),
			},
		)
		doctypes = doctype_names() | {DAUERFRIST_DOCTYPE}
		for kind, target, _view in targets:
			with self.subTest(target=target):
				if kind == "DocType":
					self.assertIn(target, doctypes)
				elif kind == "Page":
					self.assertIn(target, page_names())
				else:
					self.assertIn(target, report_names())

	def test_the_number_card_counts_vat_returns_in_draft(self):
		(row,) = self.workspace["number_cards"]
		card = read_json(NUMBER_CARDS / "offene_voranmeldungen" / "offene_voranmeldungen.json")
		self.assertEqual(row["number_card_name"], card["name"])
		self.assertEqual(
			{
				key: card[key]
				for key in ("label", "type", "document_type", "function", "is_standard", "module")
			},
			{
				"label": "Offene Voranmeldungen",
				"type": "Document Type",
				"document_type": "VAT Return",
				"function": "Count",
				"is_standard": 1,
				"module": "Steuerbote",
			},
		)
		self.assertEqual(json.loads(card["filters_json"]), [["VAT Return", "docstatus", "=", "0"]])

	def test_every_text_of_the_workspace_is_translated(self):
		headers = {
			re.sub(r"<[^>]+>", "", block["data"]["text"])
			for block in self.blocks
			if block["type"] == "header"
		}
		labels = {shortcut["label"] for shortcut in self.workspace["shortcuts"]}
		self.assertEqual(untranslated(headers | labels), [])

	def test_the_shortcuts_read_short_in_german(self):
		labels = {
			(shortcut["link_to"], shortcut.get("doc_view", "")): german(shortcut["label"])
			for shortcut in self.workspace["shortcuts"]
		}
		self.assertEqual(
			labels,
			{
				("VAT Return", "New"): "Neue Voranmeldung",
				("VAT Return", "List"): "Voranmeldungen",
				("UStVA Kennzahlen", ""): "Kennzahlen (Bericht)",
				(DAUERFRIST_DOCTYPE, "List"): "Dauerfristanträge",
				("Recapitulative Statement", "New"): "Neue ZM",
				("Recapitulative Statement", "List"): "Zusammenf. Meldungen",
				("VAT ID Confirmation", "List"): "USt-IdNr.-Prüfungen",
				("VAT Return Settings", "List"): "Einstellungen",
				("VAT Return Mapping", "List"): "Kontenzuordnung",
				("Offene Fristen", ""): "Offene Fristen",
				("steuerbote-setup", ""): "Einrichten",
			},
		)
		self.assertEqual([label for label in labels.values() if len(label) > LONGEST_LABEL], [])


class SidebarFilesTest(TestCase):
	"""The module ships its sidebar, so that its entries carry short labels instead of the DocType names."""

	def setUp(self):
		self.sidebar = read_json(SIDEBAR)
		self.items = self.sidebar["items"]

	def test_the_sidebar_is_the_module_s_own(self):
		self.assertEqual(
			{key: self.sidebar[key] for key in ("doctype", "name", "title", "module", "app", "standard")},
			{
				"doctype": "Sidebar",
				"name": "Steuerbote",
				"title": "Steuerbote",
				"module": "Steuerbote",
				"app": "steuerbote",
				"standard": 1,
			},
		)

	def test_the_sidebar_leads_to_the_workspace_every_list_and_the_report(self):
		links = [(item["link_type"], item["link_to"]) for item in self.items if item["type"] == "Link"]
		self.assertEqual(links[0], ("Workspace", read_json(WORKSPACE)["name"]))
		self.assertEqual(len(links), len(set(links)))
		self.assertEqual(
			set(links),
			{
				("Workspace", read_json(WORKSPACE)["name"]),
				("Report", read_json(REPORT / "ustva_kennzahlen.json")["name"]),
				("Report", "Offene Fristen"),
			}
			| {
				("DocType", name)
				for name in (doctypes_with_a_list() - AWAITING_THE_SECTION_JAHRESMELDUNGEN)
				| {DAUERFRIST_DOCTYPE}
			},
		)

	def test_the_lists_of_the_year_end_filings_wait_for_their_section_of_the_sidebar(self):
		"""Once the section „Jahresmeldungen“ leads to a list, it leaves AWAITING_THE_SECTION_JAHRESMELDUNGEN."""
		links = {item["link_to"] for item in self.items if item["type"] == "Link"}
		self.assertLessEqual(AWAITING_THE_SECTION_JAHRESMELDUNGEN, doctypes_with_a_list())
		self.assertEqual(sorted(AWAITING_THE_SECTION_JAHRESMELDUNGEN & links), [])

	def test_the_sidebar_reads_short_in_german(self):
		labels = [item["label"] for item in self.items]
		self.assertEqual(untranslated(set(labels)), [])
		in_german = [german(label) for label in labels]
		self.assertEqual(
			in_german,
			[
				"Steuern",
				"Voranmeldungen",
				"Dauerfristanträge",
				"Zusammenf. Meldungen",
				"USt-IdNr.-Prüfungen",
				"Kontenzuordnung",
				"Einstellungen",
				"ERiC-Einstellungen",
				"ELSTER-Übermittlung",
				"Fristerinnerungen",
				"Berichte",
				"UStVA Kennzahlen",
				"Offene Fristen",
			],
		)
		self.assertEqual([label for label in in_german if len(label) > LONGEST_LABEL], [])


class AppEntryFilesTest(TestCase):
	"""The desk offers Steuerbote twice: on the apps screen and on the rail beside the areas of ERPNext."""

	def setUp(self):
		(self.entry,) = hooks.add_to_apps_screen
		self.dock = read_json(DOCK)

	def test_the_apps_screen_opens_the_workspace_under_the_name_and_logo_of_the_app(self):
		self.assertEqual(
			{key: self.entry[key] for key in ("name", "title", "route")},
			{
				"name": hooks.app_name,
				"title": hooks.app_title,
				"route": f"/desk/{read_json(WORKSPACE)['name'].lower()}",
			},
		)
		self.assertEqual((hooks.app_title, hooks.app_home), ("Steuerbote", self.entry["route"]))
		self.assertEqual(asset(self.entry["logo"]), LOGO)

	def test_the_apps_screen_asks_the_app_who_may_see_it(self):
		module, _, function = self.entry["has_permission"].rpartition(".")
		self.assertEqual(module, "steuerbote.permissions")
		functions = {
			node.name: node
			for node in ast.parse(PERMISSIONS.read_text(encoding="utf-8")).body
			if isinstance(node, ast.FunctionDef)
		}
		self.assertIn(function, functions)
		self.assertEqual(functions[function].args.args, [])

	def test_the_app_leaves_the_logo_of_the_login_page_to_the_site(self):
		"""Frappe takes the logo of the login page from the app_logo_url of the installed apps, the second
		one when there are exactly two, so one more would change the login page of every site."""
		self.assertFalse(hasattr(hooks, "app_logo_url"))

	def test_the_dock_mounts_the_app_on_the_rail_of_erpnext(self):
		self.assertEqual(
			{key: self.dock[key] for key in ("doctype", "name", "app", "standard", "user", "mount_on")},
			{
				"doctype": "Dock",
				"name": hooks.app_name,
				"app": hooks.app_name,
				"standard": 1,
				"user": "",
				"mount_on": "erpnext",
			},
		)
		self.assertIn("frappe/erpnext", hooks.required_apps)

	def test_the_rail_entry_opens_the_sidebar_of_the_module_as_steuern(self):
		(item,) = self.dock["items"]
		self.assertEqual(
			{key: item[key] for key in ("link_type", "link_to", "title", "hidden", "added")},
			{
				"link_type": "Sidebar",
				"link_to": read_json(SIDEBAR)["name"],
				"title": read_json(WORKSPACE)["name"],
				"hidden": 0,
				"added": 0,
			},
		)
		self.assertEqual(untranslated({item["title"]}), [])

	def test_the_icon_of_the_rail_entry_is_a_symbol_the_app_ships(self):
		(item,) = self.dock["items"]
		(sprite,) = (asset(url) for url in hooks.app_include_icons)
		self.assertIsNotNone(sprite)
		symbols = {
			symbol.get("id"): symbol.get("viewBox")
			for symbol in ElementTree.parse(sprite).getroot().iter(f"{SVG}symbol")
		}
		self.assertEqual(symbols, {f"icon-{item['icon']}": "0 0 24 24"})


class LogoFilesTest(TestCase):
	"""The logo is a drawing in SVG; the PNG is rendered from it for places that take no SVG."""

	def setUp(self):
		self.logo = ElementTree.parse(LOGO).getroot()

	def test_the_logo_is_a_square_svg(self):
		self.assertEqual(self.logo.tag, f"{SVG}svg")
		self.assertIsNotNone(self.logo.get("viewBox"))
		min_x, min_y, width, height = (float(value) for value in self.logo.get("viewBox").split())
		self.assertEqual((min_x, min_y), (0, 0))
		self.assertEqual(width, height)

	def test_the_logo_holds_shapes_and_nothing_else(self):
		self.assertEqual([element.tag for element in self.logo.iter() if element.tag in NOT_A_SHAPE], [])
		self.assertEqual(
			[name for element in self.logo.iter() for name in element.attrib if name.endswith("href")], []
		)

	def test_the_logo_is_drawn_in_two_colours(self):
		colours = {
			element.get(paint)
			for element in self.logo.iter()
			for paint in ("fill", "stroke")
			if element.get(paint) not in (None, "none")
		}
		self.assertEqual(colours, {"#7C5CFC", "#FFFFFF"})

	def test_the_png_is_the_logo_at_512_pixels(self):
		self.assertEqual(png_size(LOGO_PNG), (512, 512))


class DefaultPrintFormatFilesTest(TestCase):
	"""Frappe keeps the default print format of a DocType an app ships in a Property Setter: DocType.validate
	refuses default_print_format on a standard DocType („Standard DocType cannot have default print format, use
	Customize Form“), and Print Format.make_default sets the Property Setter instead."""

	def setUp(self):
		self.setters = read_json(FIXTURES / "property_setter.json")

	def test_the_hooks_export_the_property_setters_of_the_module(self):
		self.assertIn({"dt": "Property Setter", "filters": [["module", "=", "Steuerbote"]]}, hooks.fixtures)
		self.assertEqual({setter["module"] for setter in self.setters}, {"Steuerbote"})

	def test_each_print_format_of_the_app_is_the_default_of_its_doctype(self):
		formats = {
			record["doc_type"]: record["name"]
			for record in (read_json(path) for path in (MODULE / "print_format").glob("*/*.json"))
		}
		self.assertEqual(
			{setter["doc_type"]: setter["value"] for setter in self.setters},
			formats,
		)
		self.assertEqual(
			set(formats),
			{"VAT Return", "Recapitulative Statement", "VAT Return Extension", "Annual VAT Return"},
		)

	def test_each_property_setter_is_named_and_shaped_as_frappe_makes_it(self):
		for setter in self.setters:
			with self.subTest(doctype=setter["doc_type"]):
				self.assertEqual(
					{
						key: setter[key]
						for key in ("doctype", "name", "doctype_or_field", "property", "property_type")
					},
					{
						"doctype": "Property Setter",
						"name": f"{setter['doc_type']}-main-default_print_format",
						"doctype_or_field": "DocType",
						"property": "default_print_format",
						"property_type": "Data",
					},
				)
				self.assertIn(setter["doc_type"], doctype_names())


class NamingFilesTest(TestCase):
	"""The documents for a year carry the year they are for, not the year they were made in: Frappe reads a part
	{year} of a naming series from the field of the document (parse_naming_series in frappe/model/naming.py)."""

	def test_the_documents_for_a_year_are_numbered_by_that_year(self):
		for name, prefix in (
			("vat_return", "UStVA"),
			("recapitulative_statement", "ZM"),
			("vat_return_extension", "DFV"),
			("annual_vat_return", "UStE"),
		):
			definition = read_json(MODULE / "doctype" / name / f"{name}.json")
			fields = {field["fieldname"]: field for field in definition["fields"]}
			with self.subTest(doctype=definition["name"]):
				self.assertEqual(definition["autoname"], "naming_series:")
				series = fields["naming_series"]
				self.assertEqual((series["options"], series["default"]), (f"{prefix}-.{{year}}.-.#####",) * 2)
				self.assertEqual((fields["year"]["fieldtype"], fields["year"]["reqd"]), ("Int", 1))


class SubmittedFieldsFilesTest(TestCase):
	"""A submitted document stays as it was filed: Steuerbote changes one only in code, with db_set, such as the
	status Ersetzt of a filing that a correction replaces, and no action of a user needs to change a field after
	submit. So no field of the app, its custom fields or its Property Setters allows that."""

	def test_no_field_of_the_app_changes_after_submit(self):
		changeable = [
			f"{definition['name']}.{field['fieldname']}"
			for definition in (read_json(path) for path in sorted((MODULE / "doctype").glob("*/*.json")))
			for field in definition["fields"]
			if field.get("allow_on_submit")
		]
		changeable += [
			f"{field['dt']}.{field['fieldname']}"
			for field in read_json(FIXTURES / "custom_field.json")
			if field.get("allow_on_submit")
		]
		changeable += [
			f"{setter['doc_type']}.{setter.get('field_name')}"
			for setter in read_json(FIXTURES / "property_setter.json")
			if setter["property"] == "allow_on_submit" and str(setter["value"]) != "0"
		]
		self.assertEqual(changeable, [])


class PrintFormatFilesTest(TestCase):
	def setUp(self):
		self.record = read_json(PRINT_FORMAT / "umsatzsteuer_voranmeldung.json")
		self.template = (PRINT_FORMAT / "umsatzsteuer_voranmeldung.html").read_text(encoding="utf-8")

	def test_the_print_format_is_a_standard_jinja_format_of_the_vat_return(self):
		self.assertEqual(
			{
				key: self.record[key]
				for key in ("name", "doc_type", "print_format_type", "standard", "module", "custom_format")
			},
			{
				"name": "Umsatzsteuer-Voranmeldung",
				"doc_type": "VAT Return",
				"print_format_type": "Jinja",
				"standard": "Yes",
				"module": "Steuerbote",
				"custom_format": 0,
			},
		)

	def test_prints_on_a4_in_black_and_grey(self):
		css = self.record["css"] + self.template
		self.assertIn("size: A4 portrait", self.record["css"])
		colours = HEX_COLOUR.findall(css)
		self.assertTrue(colours)
		for colour in colours:
			with self.subTest(colour=colour):
				channels = colour if len(colour) == 3 else (colour[0:2], colour[2:4], colour[4:6])
				self.assertEqual(len(set(channels)), 1)
		self.assertNotIn("<img", self.template)
		self.assertNotRegex(css, r"\b(rgb|hsl)a?\(")

	def test_keeps_to_classes_of_its_own(self):
		used = {name for value in CLASS_ATTRIBUTE.findall(self.template) for name in value.split()}
		styled = set(CLASS_SELECTOR.findall(self.record["css"]))
		self.assertNotIn("label", used | styled)
		self.assertEqual(
			sorted(name for name in used | styled if not name.startswith(PRINT_CLASS_PREFIX)), []
		)
		self.assertEqual(sorted(used), sorted(styled))

	def test_the_header_pairs_each_label_with_its_value(self):
		labels = re.findall(r'<tr><td class="sb-label">([^<]+)</td><td class="sb-value">', self.template)
		self.assertEqual(
			labels,
			[
				"Unternehmen",
				"Steuernummer",
				"Steuernummer im ELSTER-Format",
				"Finanzamt",
				"Voranmeldungszeitraum",
				"Fällig am",
				"Meldung",
			],
		)

	def test_the_labels_of_the_flags_are_those_of_the_catalogue(self):
		for number in ("10", "22", "70", "29", "26"):
			with self.subTest(kennzahl=number):
				self.assertIn(f'"{KENNZAHLEN[number].label}"', self.template)
		self.assertIn(KENNZAHLEN["500"].label, self.template)
		self.assertIn(f'"{KENNZAHLEN["83"].label}", "83"', self.template)

	def test_the_derived_rates_are_those_of_the_catalogue(self):
		rates = {
			number: int(kennzahl.rate) for number, kennzahl in KENNZAHLEN.items() if kennzahl.derives_tax
		}
		self.assertIn(
			"{%- set derived_rates = {"
			+ ", ".join(f'"{number}": {rate}' for number, rate in rates.items())
			+ "} -%}",
			self.template,
		)


class ZmPrintFormatFilesTest(TestCase):
	"""The print format of the Zusammenfassende Meldung keeps to the style of the Umsatzsteuer-Voranmeldung."""

	def setUp(self):
		self.record = read_json(ZM_PRINT_FORMAT / "zusammenfassende_meldung.json")
		self.template = (ZM_PRINT_FORMAT / "zusammenfassende_meldung.html").read_text(encoding="utf-8")

	def test_the_print_format_is_a_standard_jinja_format_of_the_statement(self):
		self.assertEqual(
			{
				key: self.record[key]
				for key in ("name", "doc_type", "print_format_type", "standard", "module", "custom_format")
			},
			{
				"name": "Zusammenfassende Meldung",
				"doc_type": "Recapitulative Statement",
				"print_format_type": "Jinja",
				"standard": "Yes",
				"module": "Steuerbote",
				"custom_format": 0,
			},
		)
		self.assertIn("Recapitulative Statement", doctype_names())

	def test_prints_on_a4_in_black_and_grey(self):
		css = self.record["css"] + self.template
		self.assertIn("size: A4 portrait", self.record["css"])
		colours = HEX_COLOUR.findall(css)
		self.assertTrue(colours)
		for colour in colours:
			with self.subTest(colour=colour):
				channels = colour if len(colour) == 3 else (colour[0:2], colour[2:4], colour[4:6])
				self.assertEqual(len(set(channels)), 1)
		self.assertNotIn("<img", self.template)
		self.assertNotRegex(css, r"\b(rgb|hsl)a?\(")

	def test_keeps_to_classes_of_its_own(self):
		used = {name for value in CLASS_ATTRIBUTE.findall(self.template) for name in value.split()}
		styled = set(CLASS_SELECTOR.findall(self.record["css"]))
		self.assertNotIn("label", used | styled)
		self.assertEqual(
			sorted(name for name in used | styled if not name.startswith(PRINT_CLASS_PREFIX)), []
		)
		self.assertEqual(sorted(used), sorted(styled))

	def test_the_header_pairs_each_label_with_its_value(self):
		labels = re.findall(r'<tr><td class="sb-label">([^<]+)</td><td class="sb-value">', self.template)
		self.assertEqual(
			labels,
			["Unternehmen", "USt-IdNr.", "Meldezeitraum", "Fällig am", "Meldeart", "Meldung", "Abgegeben am"],
		)

	def test_prints_the_lines_of_the_file(self):
		self.assertIn('selectattr("in_file")', self.template)


class ZmFormFilesTest(TestCase):
	"""A draft statement is filed through ELSTER or a note of its filing, never by Buchen alone."""

	def setUp(self):
		self.script = ZM_SCRIPT.read_text(encoding="utf-8")

	def test_a_draft_gets_no_hint_to_submit_it(self):
		setup = re.search(r"\n\tsetup\(frm\) \{\n(?P<body>.*?)\n\t\},\n", self.script, re.DOTALL)
		self.assertIsNotNone(setup)
		self.assertIn("frm.show_submit_message = () => {};", setup["body"])
		self.assertIn("offer_buchen_only_for_an_accepted_send(frm);", self.script)
		self.assertIn("frm.page.clear_primary_action();", TRANSMISSION_SCRIPT.read_text(encoding="utf-8"))

	def test_the_buttons_read_as_the_steps_of_the_zm(self):
		buttons = re.findall(r'frm\.add_custom_button\(__\("([^"]+)"\)', self.script)
		self.assertEqual(
			[german(label) for label in buttons],
			[
				"Berechnen",
				"USt-IdNrn. prüfen",
				"CSV für Mein ELSTER",
				"Berichtigung anlegen",
				"In Mein ELSTER abgegeben",
				"Als außerhalb abgegeben vermerken",
			],
		)

	def test_the_methods_the_form_calls_are_whitelisted_for_post(self):
		source = (ZM_SCRIPT.parent / "recapitulative_statement.py").read_text(encoding="utf-8")
		for method in sorted(set(re.findall(r'frm\.call\("(\w+)"', self.script))):
			with self.subTest(method=method):
				self.assertRegex(source, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {method}\(')


class VatReturnFormFilesTest(TestCase):
	"""A draft is filed through ELSTER or a note of its filing, never by Buchen alone."""

	def setUp(self):
		self.script = VAT_RETURN_SCRIPT.read_text(encoding="utf-8")

	def test_a_draft_gets_no_hint_to_submit_it(self):
		setup = re.search(r"\n\tsetup\(frm\) \{\n(?P<body>.*?)\n\t\},\n", self.script, re.DOTALL)
		self.assertIsNotNone(setup)
		self.assertIn("frm.show_submit_message = () => {};", setup["body"])

	def test_a_return_ready_to_file_says_how_to_file_it(self):
		(note,) = re.findall(r'__\("(Ready to file: [^"]*)"\)', self.script)
		self.assertEqual(
			translations()[note],
			"Bereit zur Abgabe: XML für Mein ELSTER erzeugen oder über ELSTER übermitteln.",
		)
		self.assertRegex(self.script, r'frm\.doc\.status === "Bereit"')


class MappingRuleFilesTest(TestCase):
	"""A rule without a tax rate holds 0, since a Float field stores no blank; mapping_sync reads 0 as no rate."""

	def test_the_rules_table_shows_no_rate_as_blank(self):
		script = (MAPPING / "vat_return_mapping.js").read_text(encoding="utf-8")
		setup = re.search(r"\n\tsetup\(frm\) \{\n(?P<body>.*?)\n\t\},\n", script, re.DOTALL)
		self.assertIsNotNone(setup)
		self.assertIn('frappe.meta.set_formatter("VAT Return Mapping Rule", "tax_rate", null,', setup["body"])

	def test_the_description_of_the_rate_says_what_blank_means(self):
		(rate,) = (field for field in read_json(MAPPING_RULE)["fields"] if field["fieldname"] == "tax_rate")
		self.assertEqual(rate["fieldtype"], "Float")
		self.assertTrue(german(rate["description"]).endswith(" Leer oder 0: kein Satz."))


class WatchedAccountFilesTest(TestCase):
	"""A watched account holds the return or only adds a hint, by the level its row of the mapping gives it."""

	def setUp(self):
		(self.level,) = (
			field for field in read_json(WATCHED_ACCOUNT)["fields"] if field["fieldname"] == "level"
		)

	def test_the_level_offers_the_levels_of_the_core_and_blocks_unless_set(self):
		self.assertEqual(self.level["fieldtype"], "Select")
		self.assertEqual(self.level["options"].split("\n"), [level.value for level in WatchLevel])
		self.assertEqual((self.level["default"], self.level["reqd"]), (WatchLevel.BLOCKING.value, 1))

	def test_the_table_of_the_mapping_shows_account_and_level(self):
		shown = [
			field["fieldname"] for field in read_json(WATCHED_ACCOUNT)["fields"] if field.get("in_list_view")
		]
		self.assertEqual(shown, ["account", "level"])

	def test_the_levels_read_in_german(self):
		self.assertEqual(
			[german(option) for option in self.level["options"].split("\n")], ["Sperrt", "Hinweis"]
		)
		self.assertEqual(german(self.level["label"]), "Stufe")
		self.assertEqual(
			german(self.level["description"]),
			"Sperrt: Ein Saldo auf dem Konto hält die Meldung an. Hinweis: Ein Saldo ergibt nur einen Hinweis an "
			"der Meldung.",
		)

	def test_every_text_of_the_mapping_is_translated(self):
		texts = set()
		for name in MAPPING_DOCTYPES:
			definition = read_json(MODULE / "doctype" / name / f"{name}.json")
			texts.add(definition["name"])
			for field in definition["fields"]:
				texts.update(field[key] for key in ("label", "description") if field.get(key))
				if field["fieldtype"] == "Select":
					texts.update(option for option in field["options"].split("\n") if option)
		for script in ("vat_return_mapping.js", "vat_return_mapping.py"):
			texts.update(TRANSLATED_LITERAL.findall((MAPPING / script).read_text(encoding="utf-8")))
		self.assertIn("Watch Level", texts)
		self.assertEqual(untranslated(texts - CHART_NAMES), [])
