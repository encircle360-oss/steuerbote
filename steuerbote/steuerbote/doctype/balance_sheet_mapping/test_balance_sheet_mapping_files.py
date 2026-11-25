"""The Balance Sheet Mapping, read from its files without a bench: its DocTypes with the fields and options the core
reads (steuerbote/xbrl/mapping.py, steuerbote/balance_mapping_sync.py), the field that takes the labels of the positions
in the HGB-Taxonomie 6.9 of esteuer.de (steuerbote/xbrl/tests/real.py), and every text in German."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote import balance_mapping_sync, hooks
from steuerbote.ebilanz.defaults import CHARTS, defaults_for
from steuerbote.mappings import transfer
from steuerbote.setup.steps import Step
from steuerbote.ustva import WatchLevel
from steuerbote.xbrl import mapping
from steuerbote.xbrl.mapping import REMAINING_TERMS, Purpose
from steuerbote.xbrl.tests import real
from steuerbote.xbrl.versions import FIRST, TAXONOMIES

APP = Path(__file__).resolve().parents[3]
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSLATIONS = APP / "translations" / "de.csv"
MAPPING_DOCTYPES = (
	"balance_sheet_mapping",
	"balance_sheet_mapping_rule",
	"balance_sheet_mapping_watched_account",
	"balance_sheet_mapping_excluded_account",
)
# The charts and the versions of the taxonomy read the same in every language, and Frappe translates its own labels,
# which the app keeps out of: ERPNext translates „Purpose“ as „Zweck“, so the Abschlusszweck keeps its German name.
UNTRANSLATED = frozenset(
	{
		"SKR03",
		"SKR04",
		"Eigener Kontenrahmen",
		*TAXONOMIES,
		"Company",
		"Account",
		"Position",
		"Reason",
		"Root Type",
	}
)


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def definition(name: str) -> dict:
	return json.loads((DOCTYPES / name / f"{name}.json").read_text(encoding="utf-8"))


def fields_of(name: str) -> dict[str, dict]:
	return {field["fieldname"]: field for field in definition(name)["fields"]}


def options(field: dict) -> list[str]:
	return field["options"].split("\n")


DATA_LENGTH = 140
"""The characters a Data field of Frappe takes unless it sets a length of its own: saving a longer value fails with
CharacterLengthExceededError (frappe.model.document.Document._validate_length)."""
TEXT_FIELDS = frozenset({"Small Text", "Text"})
TEXT_BYTES = 65_535
"""The bytes a Small Text or a Text field takes: Frappe stores both in a text column of MariaDB
(frappe/database/mariadb/database.py), which holds 65,535 bytes, and checks no length of its own."""


def takes(field: dict, text: str) -> bool:
	"""Whether saving keeps the text whole in the field."""
	if field["fieldtype"] in TEXT_FIELDS:
		return len(text.encode("utf-8")) <= TEXT_BYTES
	if field["fieldtype"] == "Data":
		return len(text) <= int(field.get("length") or DATA_LENGTH)
	raise AssertionError(f"no length known for a field of the type {field['fieldtype']}")


def refused(field: dict, labels: dict[str, str]) -> list[tuple[int, str]]:
	"""Each position whose label saving refuses in the field, with the length of the label, longest first."""
	return sorted(
		((len(label), position) for position, label in labels.items() if not takes(field, label)),
		reverse=True,
	)


class MappingDefinitionTest(TestCase):
	def setUp(self):
		self.definition = definition("balance_sheet_mapping")
		self.fields = fields_of("balance_sheet_mapping")

	def test_the_mapping_is_one_document_per_company(self):
		self.assertEqual(
			{key: self.definition[key] for key in ("name", "module", "autoname", "naming_rule")},
			{
				"name": "Balance Sheet Mapping",
				"module": "Steuerbote",
				"autoname": "field:company",
				"naming_rule": "By fieldname",
			},
		)
		company = self.fields["company"]
		self.assertEqual(
			{key: company.get(key) for key in ("fieldtype", "options", "reqd", "unique", "set_only_once")},
			{"fieldtype": "Link", "options": "Company", "reqd": 1, "unique": 1, "set_only_once": 1},
		)

	def test_the_charts_are_those_of_the_vat_return_mapping(self):
		vat = fields_of("vat_return_mapping")["chart"]
		self.assertEqual(
			{key: self.fields["chart"][key] for key in ("options", "default", "reqd")},
			{key: vat[key] for key in ("options", "default", "reqd")},
		)

	def test_the_positions_belong_to_a_version_of_the_taxonomy_steuerbote_knows(self):
		"""A new mapping takes the version of the first fiscal year Steuerbote files; „Auf neue Taxonomie heben“ moves
		it to a later one."""
		taxonomy = self.fields["taxonomy_version"]
		self.assertEqual(options(taxonomy), list(TAXONOMIES))
		self.assertEqual(options(taxonomy), ["6.9", "6.10"])
		self.assertEqual(
			(taxonomy["default"], taxonomy["read_only"], taxonomy["reqd"]), (FIRST.version, 1, 1)
		)

	def test_keeps_the_defaults_it_took_over_as_vat_return_mapping_does(self):
		vat = fields_of("vat_return_mapping")
		for name in ("defaults_version", "defaults_rows"):
			with self.subTest(field=name):
				self.assertEqual(
					{
						key: self.fields[name].get(key)
						for key in ("fieldtype", "read_only", "hidden", "label")
					},
					{key: vat[name].get(key) for key in ("fieldtype", "read_only", "hidden", "label")},
				)

	def test_holds_the_rules_the_watched_accounts_and_those_outside_the_bilanz_and_the_guv(self):
		self.assertEqual(
			self.definition["field_order"],
			[
				"company",
				"chart",
				"taxonomy_version",
				"defaults_version",
				"defaults_rows",
				"rules",
				"watched",
				"excluded",
				"previous_taxonomy_version",
				"previous_rows",
			],
		)
		self.assertEqual(
			{
				name: (self.fields[name]["fieldtype"], self.fields[name]["options"])
				for name in ("rules", "watched", "excluded")
			},
			{
				"rules": ("Table", "Balance Sheet Mapping Rule"),
				"watched": ("Table", "Balance Sheet Mapping Watched Account"),
				"excluded": ("Table", "Balance Sheet Mapping Excluded Account"),
			},
		)

	def test_the_permissions_are_those_of_the_vat_return_mapping(self):
		self.assertEqual(self.definition["permissions"], definition("vat_return_mapping")["permissions"])


class RowDefinitionTest(TestCase):
	def test_each_row_names_its_account_by_its_number(self):
		for name in MAPPING_DOCTYPES[1:]:
			fields = fields_of(name)
			with self.subTest(doctype=name):
				self.assertEqual((definition(name)["istable"], definition(name)["module"]), (1, "Steuerbote"))
				self.assertEqual(definition(name)["field_order"][:2], ["account", "account_number"])
				self.assertEqual(
					(fields["account"]["fieldtype"], fields["account"]["options"], fields["account"]["reqd"]),
					("Link", "Account", 1),
				)
				self.assertEqual(
					(fields["account_number"]["fetch_from"], fields["account_number"]["read_only"]),
					("account.account_number", 1),
				)

	def test_a_rule_holds_the_fields_the_core_reads(self):
		rule = fields_of("balance_sheet_mapping_rule")
		self.assertEqual(
			definition("balance_sheet_mapping_rule")["field_order"],
			["account", "account_number", "concept", "concept_label", *balance_mapping_sync.RULE_FIELDS[1:]],
		)
		self.assertEqual((rule["concept"]["fieldtype"], rule["concept"]["reqd"]), ("Data", 1))
		self.assertEqual(
			(rule["concept_label"]["fieldtype"], rule["concept_label"]["read_only"]), ("Small Text", 1)
		)
		self.assertEqual(
			(rule["opposite_concept"]["fieldtype"], rule["opposite_concept"].get("reqd")), ("Data", None)
		)
		self.assertEqual(options(rule["purpose"]), [purpose.value for purpose in Purpose])
		self.assertEqual((rule["purpose"]["default"], rule["purpose"]["reqd"]), (Purpose.BOTH.value, 1))
		self.assertEqual((rule["shareholder"]["fieldtype"], rule["shareholder"]["default"]), ("Check", "0"))
		self.assertEqual(options(rule["remaining_term"]), ["", *REMAINING_TERMS])

	def test_the_grid_of_the_rules_shows_account_position_and_what_the_rule_says(self):
		shown = [
			field["fieldname"]
			for field in definition("balance_sheet_mapping_rule")["fields"]
			if field.get("in_list_view")
		]
		self.assertEqual(
			shown, ["account", "concept", "opposite_concept", "purpose", "shareholder", "remaining_term"]
		)
		self.assertLessEqual(
			sum(
				field.get("columns", 0)
				for field in definition("balance_sheet_mapping_rule")["fields"]
				if field.get("in_list_view")
			),
			10,
		)

	def test_a_watched_account_has_the_levels_of_the_core_and_blocks_unless_set(self):
		level = fields_of("balance_sheet_mapping_watched_account")["level"]
		self.assertEqual(options(level), [watch.value for watch in WatchLevel])
		self.assertEqual((level["default"], level["reqd"]), (WatchLevel.BLOCKING.value, 1))

	def test_an_account_outside_the_bilanz_and_the_guv_names_its_reason(self):
		reason = fields_of("balance_sheet_mapping_excluded_account")["reason"]
		self.assertEqual((reason["fieldtype"], reason["reqd"]), ("Data", 1))


class LabelTest(TestCase):
	"""Saving writes the label of the position of each rule in the HGB-Taxonomie into the field Label of the Position,
	and a label longer than the field takes fails the whole mapping: Vorgaben laden, Steuerbote einrichten and a rule
	by hand alike."""

	def setUp(self):
		self.taxonomy = real.view()
		self.field = fields_of("balance_sheet_mapping_rule")["concept_label"]

	def test_takes_the_label_of_every_position_of_the_defaults(self):
		"""The defaults name positions whose labels are longer than 140 characters, such as the Gebäude-Anteil of the
		Bauten auf eigenen Grundstücken with 181 and the Abschreibungen auf Forderungen gegenüber
		Kapitalgesellschaften, an denen eine Beteiligung besteht, with 314."""
		labels = {
			rule.concept: self.taxonomy.label(rule.concept)
			for chart in sorted(CHARTS)
			for rule in defaults_for(chart, real.VERSION.version).rules
		}
		self.assertGreater(max(len(label) for label in labels.values()), DATA_LENGTH)
		self.assertEqual(refused(self.field, labels), [])

	def test_takes_the_label_of_every_position_a_rule_may_name(self):
		"""A rule by hand may name a position with a longer label than any of the defaults, up to the 507 characters
		of bs.eqLiab.equity.revenueRes.assMeasuredAtFairValue.finalPrev."""
		labels = {
			name: self.taxonomy.label(name)
			for name in self.taxonomy.concepts
			if mapping.position_problem(self.taxonomy, "0000", name) is None
		}
		self.assertGreater(max(len(label) for label in labels.values()), DATA_LENGTH)
		self.assertEqual(refused(self.field, labels), [])


class TranslationsTest(TestCase):
	def test_the_app_keeps_out_of_the_translations_of_frappe_and_erpnext(self):
		self.assertEqual(sorted({"Position", "Reason", "Purpose"} & translations().keys()), [])

	def test_every_text_of_the_doctypes_reads_in_german(self):
		texts = set()
		for name in MAPPING_DOCTYPES:
			texts.add(definition(name)["name"])
			for field in definition(name)["fields"]:
				texts.update(field[key] for key in ("label", "description") if field.get(key))
				if field["fieldtype"] == "Select":
					texts.update(option for option in options(field) if option)
		self.assertIn("Balance Sheet Mapping Excluded Account", texts)
		self.assertEqual(sorted(texts - translations().keys() - UNTRANSLATED), [])

	def test_the_names_read_in_german(self):
		german = translations()
		self.assertEqual(
			[
				german[name]
				for name in (
					"Balance Sheet Mapping",
					"Abschlusszweck",
					"Remaining Term",
					"Accounts outside the Bilanz and the GuV",
				)
			],
			["Bilanzzuordnung", "Abschlusszweck", "Restlaufzeit", "Konten außerhalb von Bilanz und GuV"],
		)
		self.assertEqual(
			[german[purpose.value] for purpose in Purpose],
			["Handels- und Steuerbilanz", "nur Handelsbilanz", "nur Steuerbilanz"],
		)
		self.assertEqual(
			[german[term] for term in REMAINING_TERMS], [term.value for term in REMAINING_TERMS.values()]
		)

	def test_every_message_of_the_core_reads_in_german(self):
		"""Saving and importing show what steuerbote/xbrl/mapping.py and steuerbote/balance_mapping_sync.py refuse."""
		messages = {
			*mapping.MESSAGES,
			*(refusal.template for refusal in mapping.REFUSALS),
			*balance_mapping_sync.MESSAGES,
		}
		self.assertEqual(sorted(messages - translations().keys()), [])


FOLDER = DOCTYPES / "balance_sheet_mapping"
DIFFERENCES_SCRIPT = APP / "public" / "js" / "mapping_differences.js"
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")


def constants(source: str) -> dict[str, object]:
	"""The module-level constants of a source whose value is a literal."""
	found = {}
	for node in ast.parse(source).body:
		if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
			try:
				found[node.targets[0].id] = ast.literal_eval(node.value)
			except ValueError:
				continue
	return found


def function(script: str, name: str) -> str:
	found = re.search(rf"\nfunction {name}\([^)]*\) \{{\n(?P<body>.*?)\n\}}\n", script, re.DOTALL)
	if found is None:
		raise AssertionError(f"no function {name}")
	return found["body"]


class FormFilesTest(TestCase):
	"""The form of the Balance Sheet Mapping, as the one of the VAT Return Mapping: the methods it calls are
	whitelisted for POST, its dialogs escape what the site holds, the file stays private, and every text reads in
	German."""

	def setUp(self):
		self.script = (FOLDER / "balance_sheet_mapping.js").read_text(encoding="utf-8")
		self.source = (FOLDER / "balance_sheet_mapping.py").read_text(encoding="utf-8")

	def test_the_methods_the_form_calls_are_whitelisted_for_post(self):
		methods = sorted(set(re.findall(r'frm\.call\("(\w+)"', self.script)))
		self.assertEqual(
			methods,
			[
				"accounts_without_place",
				"compare_with_defaults",
				"compare_with_file",
				"export_mapping",
				"export_previous_mapping",
				"import_file",
				"lift_taxonomy",
				"load_defaults",
				"update_from_defaults",
				"watch_accounts_without_place",
			],
		)
		for method in methods:
			with self.subTest(method=method):
				self.assertRegex(self.source, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {method}\(')

	def test_the_form_offers_the_ledger_accounts_of_the_company_in_each_table(self):
		self.assertIn('for (const table of ["rules", "watched", "excluded"])', self.script)
		self.assertIn("filters: { company: doc.company, is_group: 0 },", self.script)
		self.assertIn('["rules", "watched", "excluded"].some(', self.script)

	def test_the_form_shows_the_differences_in_the_dialog_of_the_mappings_headed_by_account(self):
		self.assertTrue(
			self.script.startswith('{% include "steuerbote/public/js/mapping_differences.js" %}\n')
		)
		self.assertEqual(self.script.count('subject_label: __("Account"),'), 2)
		dialog = DIFFERENCES_SCRIPT.read_text(encoding="utf-8")
		self.assertIn("subject_label, proposed_label", dialog)
		self.assertIn('${escape(subject_label || __("Account or Tax Check"))}', dialog)

	def test_the_export_is_saved_by_the_browser_under_its_name(self):
		body = function(self.script, "export_mapping")
		for part in ("new Blob([file.content]", "link.download = file.file_name;", "frm.reload_doc();"):
			with self.subTest(part=part):
				self.assertIn(part, body)
		self.assertIn('return f"Bilanzzuordnung-{re.sub(', self.source)

	def test_an_upload_stays_private_and_the_file_browser_stays_closed(self):
		body = function(self.script, "upload_mapping_file")
		for part in (
			"docname: frm.doc.name,",
			"allow_toggle_private: false,",
			"allow_web_link: false,",
			"disable_file_browser: true,",
			'allowed_file_types: [".json"]',
		):
			with self.subTest(part=part):
				self.assertIn(part, body)

	def test_the_dialog_of_the_accounts_escapes_what_the_site_holds(self):
		body = function(self.script, "show_accounts_without_place")
		self.assertIn("const escape = frappe.utils.escape_html;", body)
		for value in ("account.account_number", "account.account_name", "account.root_type"):
			with self.subTest(value=value):
				shown = re.findall(rf"\$\{{[^}}]*{re.escape(value)}[^}}]*\}}", body)
				self.assertTrue(shown)
				self.assertTrue(all("escape" in expression for expression in shown), shown)

	def test_every_field_of_a_difference_has_a_german_label(self):
		labels = constants(self.source)["FIELD_LABELS"]
		self.assertEqual(set(labels), {"place", *balance_mapping_sync.RULE_FIELDS, "level", "reason"})
		self.assertEqual(sorted(set(labels.values()) - translations().keys() - UNTRANSLATED), [])

	def test_every_text_of_the_form_and_its_controller_reads_in_german(self):
		found = constants(self.source)
		texts = {
			*TRANSLATED_LITERAL.findall(self.script),
			*TRANSLATED_LITERAL.findall(self.source),
			*(found[name] for name in ("INVALID", "NOT_CHECKED", "OTHER_TAXONOMY", "NOTHING_TO_WATCH")),
			*transfer.MESSAGES,
		}
		self.assertIn("Check Accounts", texts)
		self.assertEqual(sorted(texts - translations().keys() - UNTRANSLATED), [])
		german = translations()
		self.assertEqual(german["Check Accounts"], "Konten prüfen")
		self.assertEqual(german["Invalid Balance Sheet Mapping"], "Ungültige Bilanzzuordnung")


class SetupStepTest(TestCase):
	"""Steuerbote einrichten makes the Balance Sheet Mapping through the hook steuerbote_setup_steps."""

	def test_the_hook_runs_the_step_of_the_mapping_after_those_of_the_voranmeldung_and_the_ertragsteuern(
		self,
	):
		(entry,) = (
			entry for entry in hooks.steuerbote_setup_steps if entry["key"] == "balance_sheet_mapping"
		)
		step = Step.from_hook(entry)
		self.assertEqual(
			(step.key, step.label, step.order, step.run, step.needs),
			(
				"balance_sheet_mapping",
				"Balance Sheet Mapping",
				50,
				"steuerbote.steuerbote.doctype.balance_sheet_mapping.setup.run",
				(),
			),
		)
		self.assertEqual([entry["order"] for entry in hooks.steuerbote_setup_steps], [35, 40, 50, 60, 70])
		self.assertRegex(
			(FOLDER / "setup.py").read_text(encoding="utf-8"), r"\ndef run\(context: SetupContext\)"
		)

	def test_every_note_of_the_step_reads_in_german(self):
		source = (FOLDER / "setup.py").read_text(encoding="utf-8")
		found = constants(source)
		(listed,) = (
			node.value
			for node in ast.parse(source).body
			if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "MESSAGES"
		)
		messages = {found[name.id] for name in listed.elts}
		self.assertEqual(len(messages), 8)
		self.assertEqual(sorted(messages - translations().keys()), [])


class LiftFilesTest(TestCase):
	"""Auf neue Taxonomie heben: the fields that keep the rows of the previous version, the button the form offers
	while a later version exists, the dialog of what the lift found, and every text in German."""

	def setUp(self):
		self.fields = fields_of("balance_sheet_mapping")
		self.script = (FOLDER / "balance_sheet_mapping.js").read_text(encoding="utf-8")
		self.source = (FOLDER / "balance_sheet_mapping.py").read_text(encoding="utf-8")

	def test_keeps_the_previous_version_and_its_rows_as_the_defaults_taken_over(self):
		"""As defaults_version and defaults_rows keep the defaults: the version shown once there is one, the rows in
		the dump of steuerbote.balance_mapping_sync.dump_items()."""
		previous, rows = self.fields["previous_taxonomy_version"], self.fields["previous_rows"]
		self.assertEqual(
			(previous["fieldtype"], previous["read_only"], previous.get("depends_on")),
			("Data", 1, "previous_taxonomy_version"),
		)
		self.assertEqual((rows["fieldtype"], rows["read_only"], rows["hidden"]), ("Long Text", 1, 1))

	def test_the_form_offers_the_lift_to_the_latest_version_and_the_export_of_the_rows_before(self):
		body = function(self.script, "lift_taxonomy")
		self.assertIn('frm.call("lift_taxonomy", { target: latest })', body)
		self.assertIn('frm.get_docfield("taxonomy_version").options.split("\\n")', self.script)
		self.assertIn("if (frm.doc.previous_rows) {", self.script)
		export = function(self.script, "export_previous_mapping")
		for part in ("new Blob([file.content]", "link.download = file.file_name;"):
			with self.subTest(part=part):
				self.assertIn(part, export)

	def test_the_dialog_of_the_lift_escapes_what_it_shows(self):
		body = function(self.script, "show_lifted")
		self.assertIn("const escape = frappe.utils.escape_html;", body)
		for value in (
			"renamed.account",
			"renamed.old",
			"renamed.new",
			"decision.account",
			"decision.position",
			"decision.text",
			"mussfeld.label",
			"mussfeld.position",
		):
			with self.subTest(value=value):
				shown = re.findall(rf"\$\{{[^}}]*{re.escape(value)}[^}}]*\}}", body)
				self.assertTrue(shown)
				self.assertTrue(all("escape" in expression for expression in shown), shown)

	def test_every_message_of_the_lift_reads_in_german(self):
		found = constants(self.source)
		messages = {found[name] for name in ("NOT_INSTALLED", "NOT_LATER", "NOT_LIFTED", "NO_DEFAULTS")}
		self.assertEqual(sorted(messages - translations().keys()), [])
		german = translations()
		self.assertEqual(german["Lift to New Taxonomy"], "Auf neue Taxonomie heben")
		self.assertEqual(german["Previous HGB Taxonomy"], "Vorherige HGB-Taxonomie")
