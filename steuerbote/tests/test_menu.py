"""The menu of the module: the sidebar Steuerbote links every list, report and page of the module, each entry with an
icon the way the sidebars of ERPNext 16 carry theirs, read from the files without a bench.

ERPNext shapes the sidebar of a module such as Accounts (erpnext/accounts/sidebar/accounts/accounts.json) in two
parts: first the workspace and the main documents, each a link with an icon of its own, then the groups, each a
Section Break with indent and an icon that stays closed until it is opened, whose entries follow it as children
without an icon. The desk draws the icon of a link and of a group, and none for an entry of a group, "even one they
set themselves" (frappe/public/js/frappe/ui/sidebar/sidebar_item.js in Frappe 16.60.2); a link without an icon gets
the icon of a list.

An icon is a symbol of the sprites the desk loads: those of Frappe and ERPNext, pinned in desk_symbols.txt, and the
app's own (app_include_icons in hooks.py).
"""

import csv
import json
from collections import Counter
from pathlib import Path
from unittest import TestCase
from xml.etree import ElementTree

from steuerbote import hooks

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "steuerbote"
SIDEBAR = MODULE / "sidebar" / "steuerbote" / "steuerbote.json"
WORKSPACE = MODULE / "workspace" / "steuern" / "steuern.json"
DOCK = APP / "dock" / "steuerbote" / "steuerbote.json"
TRANSLATIONS = APP / "translations" / "de.csv"
DESK_SYMBOLS = Path(__file__).with_name("desk_symbols.txt")
# Frappe serves the public folder of an app under this path.
ASSETS = "/assets/steuerbote/"
SVG = "{http://www.w3.org/2000/svg}"
# The German that Frappe gives the labels of the groups it names itself.
FRAMEWORK_GERMAN = {"Reports": "Berichte", "Settings": "Einstellungen", "Setup": "Einrichtung"}
# The desk cuts a label after about 22 characters, in the sidebar as on a shortcut card.
LONGEST_LABEL = 20
# What an entry of ERPNext's sidebars is and how a group is drawn: indented, closed until it is opened.
ENTRY_TYPES = frozenset({"Link", "Section Break"})
GROUP = {"indent": 1, "collapsible": 1, "keep_closed": 1}


def read_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def names(kind: str) -> set[str]:
	return {read_json(path)["name"] for path in (MODULE / kind).glob("*/*.json")}


def lists() -> set[str]:
	"""The DocTypes of the module that are not child tables: each has a list or, as a single, a form of its own."""
	definitions = (read_json(path) for path in (MODULE / "doctype").glob("*/*.json"))
	return {definition["name"] for definition in definitions if not definition.get("istable")}


def documents() -> set[str]:
	"""The DocTypes of the module whose documents are filed, the Belege."""
	definitions = (read_json(path) for path in (MODULE / "doctype").glob("*/*.json"))
	return {definition["name"] for definition in definitions if definition.get("is_submittable")}


def german_names() -> set[str]:
	"""The workspace and the reports, whose names read the same in every language."""
	return {read_json(WORKSPACE)["name"]} | names("report")


def desk_symbols() -> set[str]:
	"""The symbols of Frappe and ERPNext, and those of the sprites of the app."""
	pinned = {
		line
		for line in DESK_SYMBOLS.read_text(encoding="utf-8").splitlines()
		if line and not line.startswith("#")
	}
	own = {
		symbol.get("id")
		for url in hooks.app_include_icons
		for symbol in ElementTree.parse(APP / "public" / url.removeprefix(ASSETS))
		.getroot()
		.iter(f"{SVG}symbol")
	}
	return pinned | own


def symbol(icon: str) -> str:
	"""The symbol the desk draws for an icon (frappe.utils.icon in frappe/public/js/frappe/utils/utils.js)."""
	return icon if icon.startswith("es-") else f"icon-{icon}"


class SidebarMenuTest(TestCase):
	def setUp(self):
		self.sidebar = read_json(SIDEBAR)
		self.items = self.sidebar["items"]
		self.links = [item for item in self.items if item["type"] == "Link"]
		self.groups = [item for item in self.items if item["type"] == "Section Break"]
		self.rail = [item for item in self.items if not item.get("child")]
		self.in_groups = [item for item in self.items if item.get("child")]

	def test_links_every_list_report_and_page_of_the_module(self):
		offered = (
			{("Workspace", read_json(WORKSPACE)["name"])}
			| {("DocType", name) for name in lists()}
			| {("Report", name) for name in names("report")}
			| {("Page", name) for name in names("page")}
		)
		linked = {(item["link_type"], item["link_to"]) for item in self.links}
		self.assertEqual(sorted(offered - linked), [], "missing from the sidebar")
		self.assertEqual(sorted(linked - offered), [], "not of the module")

	def test_names_each_entry_once(self):
		"""The desk keeps the first of two entries with the same target, and of two groups with the same label."""
		targets = Counter((item["link_type"], item["link_to"]) for item in self.links)
		self.assertEqual([target for target, count in targets.items() if count > 1], [])
		labels = Counter(group["label"] for group in self.groups)
		self.assertEqual([label for label, count in labels.items() if count > 1], [])

	def test_is_shaped_like_the_sidebars_of_erpnext(self):
		self.assertEqual(sorted({item["type"] for item in self.items} - ENTRY_TYPES), [])
		self.assertEqual(
			(self.items[0]["link_type"], self.items[0]["link_to"]),
			("Workspace", read_json(WORKSPACE)["name"]),
		)
		first_group = next(
			(index for index, item in enumerate(self.items) if item["type"] == "Section Break"),
			len(self.items),
		)
		self.assertEqual([item["label"] for item in self.items[:first_group] if item.get("child")], [])
		self.assertEqual(
			[
				item["label"]
				for item in self.items[first_group:]
				if item["type"] == "Link" and not item.get("child")
			],
			[],
			"a link after the first group belongs to a group",
		)
		for index, group in enumerate(self.items):
			if group["type"] != "Section Break":
				continue
			with self.subTest(group=group["label"]):
				self.assertEqual({key: group.get(key) for key in GROUP}, GROUP)
				following = self.items[index + 1] if index + 1 < len(self.items) else {}
				self.assertTrue(following.get("child"), "the desk draws no group without entries")

	def test_every_link_and_group_on_the_rail_carries_an_icon_the_desk_has(self):
		symbols = desk_symbols()
		self.assertEqual(
			[item["label"] for item in self.rail if symbol(item.get("icon") or "") not in symbols],
			[],
			"no icon, or one that no sprite of the desk has",
		)

	def test_an_entry_of_a_group_carries_no_icon(self):
		"""Its group stands for it with the group's icon, and the desk would not draw one of its own."""
		self.assertEqual([item["label"] for item in self.in_groups if item.get("icon")], [])

	def test_no_two_entries_on_the_rail_share_an_icon(self):
		icons = Counter(item.get("icon") for item in self.rail)
		self.assertEqual([icon for icon, count in icons.items() if count > 1], [])

	def test_the_header_shows_the_icon_of_the_entry_steuern_on_the_rail_of_erpnext(self):
		"""The desk draws the icon of the dock's entry in the header of the sidebar and the Sidebar's own only
		where that entry is missing (frappe.get_module_icon), so both are the same symbol of the app."""
		(entry,) = read_json(DOCK)["items"]
		self.assertEqual(self.sidebar["header_icon"], entry["icon"])
		self.assertIn(symbol(entry["icon"]), desk_symbols())

	def test_every_label_reads_short_in_german(self):
		german = translations() | FRAMEWORK_GERMAN | {name: name for name in german_names()}
		labels = [item["label"] for item in self.items]
		self.assertEqual(
			sorted(label for label in labels if label not in german), [], "no German row in de.csv"
		)
		self.assertEqual([german[label] for label in labels if len(german[label]) > LONGEST_LABEL], [])


class WorkspaceMenuTest(TestCase):
	def test_the_workspace_leads_to_the_list_of_each_document_of_the_module(self):
		lists_on_the_workspace = {
			shortcut["link_to"]
			for shortcut in read_json(WORKSPACE)["shortcuts"]
			if shortcut["type"] == "DocType" and shortcut.get("doc_view") == "List"
		}
		self.assertEqual(sorted(documents() - lists_on_the_workspace), [], "missing from the workspace")
