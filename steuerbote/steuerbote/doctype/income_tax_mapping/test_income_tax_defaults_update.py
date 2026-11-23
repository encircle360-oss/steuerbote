"""Vorgaben aktualisieren for the Income Tax Mapping on a site: the differences to the defaults of today with their
origin, and taking over some of them while the rest stays."""

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.income_tax_mapping_sync import ACCOUNT, default_items, dump_items, load_items
from steuerbote.tests.helpers import make_account, make_company

# The tests build their own companies and accounts and need none of ERPNext's test records.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Account"]

MAPPING = "Income Tax Mapping"
COMPANY = "Steuerbote Test Ertragsteuern Vorgaben GmbH"
VERSION = "SKR03 2026.1"
# SKR03 accounts: the taxes on income, a trading account, a watched account at each level and a bank, which the
# defaults leave out.
ACCOUNTS = {
	"2200": ("Körperschaftsteuer", "Expense"),
	"2208": ("Solidaritätszuschlag", "Expense"),
	"4320": ("Gewerbesteuer", "Expense"),
	"2654": ("Erträge aus anderen Wertpapieren und Ausleihungen des Umlaufvermögens", "Income"),
	"2250": ("Aufwendungen aus der Zuführung und Auflösung von latenten Steuern", "Expense"),
	"4126": ("Tantiemen Gesellschafter-Geschäftsführer", "Expense"),
	"1200": ("Bank", "Asset"),
}


def make_accounts(company: str) -> dict[str, str]:
	return {
		number: frappe.db.get_value("Account", {"company": company, "account_number": number})
		or make_account(company, number, name, root_type)
		for number, (name, root_type) in ACCOUNTS.items()
	}


def ids(comparison: dict) -> list[tuple[str, bool]]:
	return [(difference["id"], difference["proposes"]) for difference in comparison["differences"]]


class IntegrationTestIncomeTaxDefaultsUpdate(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STETV")
		cls.accounts = make_accounts(COMPANY)

	def setUp(self):
		frappe.delete_doc_if_exists(MAPPING, COMPANY, force=True)
		mapping = frappe.new_doc(MAPPING)
		mapping.update({"company": COMPANY, "chart": "SKR03"})
		mapping.load_defaults()
		self.mapping = mapping.insert()

	def defaults(self) -> dict:
		return default_items("SKR03", set(ACCOUNTS))

	def as_if_built_from(self, base: dict, current: dict | None = None) -> None:
		"""The mapping as if Vorgaben laden had given it ``base`` once and the user had made ``current`` of it."""
		mapping = frappe.get_doc(MAPPING, COMPANY)
		mapping._set_items(current if current is not None else base)
		mapping.defaults_rows = dump_items(base)
		mapping.defaults_version = "SKR03 2025.4"
		mapping.save()
		self.mapping = mapping

	def test_a_mapping_as_vorgaben_laden_made_it_has_no_difference(self):
		comparison = self.mapping.compare_with_defaults()
		self.assertEqual(
			(
				comparison["version"],
				comparison["taken_over"],
				comparison["base_known"],
				comparison["differences"],
			),
			(VERSION, VERSION, True, []),
		)
		self.assertEqual(comparison["unchanged"], len(self.defaults()))

	def test_a_level_vorgaben_laden_kept_is_the_users_own(self):
		for row in self.mapping.watched:
			row.level = "hint"
		self.mapping.load_defaults()
		self.mapping.save()
		self.assertEqual(ids(self.mapping.compare_with_defaults()), [("account:2250", False)])

	def test_a_change_of_the_defaults_is_proposed_and_a_change_of_the_user_is_not(self):
		old = dict(self.defaults())
		old[(ACCOUNT, "2200")] = {**old[(ACCOUNT, "2200")], "category": "solz"}
		del old[(ACCOUNT, "4320")]
		old[(ACCOUNT, "1200")] = {"place": "watched", "level": "blocking"}
		mine = dict(old)
		mine[(ACCOUNT, "2654")] = {**old[(ACCOUNT, "2654")], "trading_class": "derivatives"}
		self.as_if_built_from(old, mine)
		comparison = self.mapping.compare_with_defaults()
		self.assertEqual(comparison["taken_over"], "SKR03 2025.4")
		self.assertEqual(
			ids(comparison),
			[("account:2200", True), ("account:2654", False), ("account:1200", True), ("account:4320", True)],
		)
		(category,) = (
			difference for difference in comparison["differences"] if difference["id"] == "account:2200"
		)
		self.assertEqual(
			{key: category[key] for key in ("subject", "change", "fields", "current", "proposed", "origin")},
			{
				"subject": "Account 2200",
				"change": "Will Change",
				"fields": "Category",
				"current": "solz",
				"proposed": "kst",
				"origin": "The defaults changed",
			},
		)
		(trading,) = (
			difference for difference in comparison["differences"] if difference["id"] == "account:2654"
		)
		self.assertEqual(
			(trading["fields"], trading["current"], trading["proposed"], trading["origin"]),
			("Trading Class", "trading_unclassified, derivatives", "trading_unclassified", "Your own change"),
		)

	def test_update_takes_over_what_is_chosen_and_keeps_everything_else(self):
		old = dict(self.defaults())
		old[(ACCOUNT, "2200")] = {**old[(ACCOUNT, "2200")], "category": "solz"}
		del old[(ACCOUNT, "4320")]
		old[(ACCOUNT, "1200")] = {"place": "watched", "level": "blocking"}
		mine = {**old, (ACCOUNT, "2654"): {**old[(ACCOUNT, "2654")], "trading_class": "derivatives"}}
		self.as_if_built_from(old, mine)
		taken = self.mapping.update_from_defaults(
			["account:2200", "account:4320", "account:2654-not-a-difference"]
		)
		self.assertEqual(taken, 2)
		mapping = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(
			[(row.account_number, row.category, row.trading_class or None) for row in mapping.rules],
			[
				("2200", "kst", None),
				("2208", "solz", None),
				("2654", "trading_unclassified", "derivatives"),
				("4320", "gewst", None),
			],
		)
		self.assertEqual(
			[(row.account, row.account_number, row.level) for row in mapping.watched],
			[
				(self.accounts["2250"], "2250", "blocking"),
				(self.accounts["4126"], "4126", "hint"),
				(self.accounts["1200"], "1200", "blocking"),
			],
		)
		self.assertEqual(mapping.defaults_version, VERSION)
		self.assertEqual(load_items(mapping.defaults_rows), self.defaults())
		self.assertEqual(
			ids(mapping.compare_with_defaults()), [("account:2654", False), ("account:1200", False)]
		)

	def test_update_with_nothing_chosen_only_notes_the_defaults_of_today(self):
		self.as_if_built_from(self.defaults())
		self.assertEqual(self.mapping.compare_with_defaults()["differences"], [])
		self.assertEqual(self.mapping.update_from_defaults([]), 0)
		self.assertEqual(frappe.db.get_value(MAPPING, COMPANY, "defaults_version"), VERSION)

	def test_without_the_rows_of_the_defaults_every_difference_is_the_users(self):
		mapping = frappe.get_doc(MAPPING, COMPANY)
		mapping.defaults_rows = None
		mapping.defaults_version = None
		mapping.set("rules", [row for row in mapping.rules if row.account_number != "2200"])
		mapping.save()
		comparison = mapping.compare_with_defaults()
		self.assertEqual((comparison["base_known"], comparison["taken_over"]), (False, ""))
		self.assertEqual(ids(comparison), [("account:2200", False)])
		self.assertEqual(
			{difference["origin"] for difference in comparison["differences"]}, {"Origin unknown"}
		)

	def test_vorgaben_laden_stays_the_full_reset(self):
		old = dict(self.defaults())
		old[(ACCOUNT, "2200")] = {**old[(ACCOUNT, "2200")], "category": "solz"}
		self.as_if_built_from(old, {**old, (ACCOUNT, "1200"): {"place": "watched", "level": "blocking"}})
		mapping = frappe.get_doc(MAPPING, COMPANY)
		mapping.load_defaults()
		mapping.save()
		self.assertEqual(mapping.current_items(), self.defaults())
		self.assertEqual(mapping.compare_with_defaults()["differences"], [])

	def test_stored_defaults_that_are_no_json_are_refused(self):
		self.mapping.defaults_rows = "{rules"
		with self.assertRaisesRegex(frappe.ValidationError, "the stored defaults are no JSON"):
			self.mapping.save()

	def test_a_chart_of_its_own_has_no_defaults_to_update_from(self):
		self.mapping.chart = "Eigener Kontenrahmen"
		for method in (self.mapping.compare_with_defaults, self.mapping.update_from_defaults):
			with (
				self.subTest(method=method.__name__),
				self.assertRaisesRegex(
					frappe.ValidationError, "There are no defaults for Eigener Kontenrahmen"
				),
			):
				method()
