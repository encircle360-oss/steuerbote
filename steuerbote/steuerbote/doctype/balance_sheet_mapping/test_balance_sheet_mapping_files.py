"""The Balance Sheet Mapping, read from its files without a bench: its DocTypes with the fields and options the core
reads (steuerbote/xbrl/mapping.py, steuerbote/balance_mapping_sync.py), and every text in German."""

import csv
import json
from pathlib import Path
from unittest import TestCase

from steuerbote import balance_mapping_sync
from steuerbote.ustva import WatchLevel
from steuerbote.xbrl import mapping
from steuerbote.xbrl.mapping import REMAINING_TERMS, Purpose
from steuerbote.xbrl.versions import LATEST, TAXONOMIES

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
	{"SKR03", "SKR04", "Eigener Kontenrahmen", *TAXONOMIES, "Company", "Account", "Position", "Reason"}
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
		taxonomy = self.fields["taxonomy_version"]
		self.assertEqual(options(taxonomy), list(TAXONOMIES))
		self.assertEqual(
			(taxonomy["default"], taxonomy["read_only"], taxonomy["reqd"]), (LATEST.version, 1, 1)
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
			(rule["concept_label"]["fieldtype"], rule["concept_label"]["read_only"]), ("Data", 1)
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
