"""Vorgaben aktualisieren on a site: the version and the rows Vorgaben laden notes, the differences to the defaults of
today with their origin, taking over some of them while the rest stays, a call without a choice, which notes the
defaults of today only when the user declined the differences, and the defaults a mapping without rows waits for, which
its form names."""

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.mapping_sync import ACCOUNT, CHECK, default_items, dump_items, load_items
from steuerbote.tests.helpers import make_account, make_company
from steuerbote.ustva import LATEST_YEAR

# The tests build their own companies and accounts and need none of ERPNext's test records.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Account"]

COMPANY = "Steuerbote Test Vorgaben GmbH"
MAPPING = "VAT Return Mapping"
VERSION = "SKR03 2026.4"
# SKR03 accounts: a sale at 19 % with its tax, a service under § 13b UStG with its taxes, the Vorsteuer, a watched
# account at each level and a bank, which the defaults leave out.
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"3123": ("Sonstige Leistungen EU 19 % Vorsteuer und 19 % Umsatzsteuer", "Expense"),
	"1787": ("Umsatzsteuer nach § 13b UStG 19 %", "Liability"),
	"1577": ("Abziehbare Vorsteuer nach § 13b UStG 19 %", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1548": ("Vorsteuer im Folgejahr abziehbar", "Asset"),
	"8603": ("Sonstige betriebliche Erträge", "Income"),
	"1200": ("Bank", "Asset"),
}
CHECK_19 = (CHECK, "Umsatzsteuer 19 %")
CHECK_13B = (CHECK, "Umsatzsteuer nach § 13b UStG 19 %")


def make_accounts(company: str) -> dict[str, str]:
	return {
		number: frappe.db.get_value("Account", {"company": company, "account_number": number})
		or make_account(company, number, name, root_type)
		for number, (name, root_type) in ACCOUNTS.items()
	}


def ids(comparison: dict) -> list[tuple[str, bool]]:
	return [(difference["id"], difference["proposes"]) for difference in comparison["differences"]]


def defaults_to_load(mapping) -> str | None:
	"""The defaults the form of the mapping names above its fields, as Vorgaben laden would fetch them."""
	mapping.run_method("onload")
	return mapping.get_onload("defaults_to_load")


class IntegrationTestDefaultsUpdate(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STVA")
		cls.accounts = make_accounts(COMPANY)

	def setUp(self):
		frappe.delete_doc_if_exists(MAPPING, COMPANY, force=True)
		mapping = frappe.new_doc(MAPPING)
		mapping.update({"company": COMPANY, "chart": "SKR03"})
		mapping.load_defaults()
		self.mapping = mapping.insert()

	def defaults(self) -> dict:
		return default_items("SKR03", LATEST_YEAR, set(ACCOUNTS))

	def as_if_built_from(self, base: dict, current: dict | None = None) -> None:
		"""The mapping as if Vorgaben laden had given it ``base`` once and the user had made ``current`` of it."""
		mapping = frappe.get_doc(MAPPING, COMPANY)
		mapping._set_items(current if current is not None else base)
		mapping.defaults_rows = dump_items(base)
		mapping.defaults_version = "SKR03 2025.4"
		mapping.save()
		self.mapping = mapping

	def test_load_defaults_notes_the_version_and_the_rows_the_defaults_gave(self):
		stored = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(stored.defaults_version, VERSION)
		self.assertEqual(load_items(stored.defaults_rows), self.defaults())
		self.assertEqual(stored.current_items(), self.defaults())

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
		self.assertEqual({row.level for row in self.mapping.watched}, {"hint"})
		self.assertEqual(ids(self.mapping.compare_with_defaults()), [("account:1548", False)])

	def test_the_kennzahl_of_the_base_without_base_account_is_proposed_to_a_mapping_of_revision_1(self):
		old = dict(self.defaults())
		old[CHECK_13B] = {
			name: value
			for name, value in old[CHECK_13B].items()
			if name not in ("derived_base", "derived_base_eu")
		}
		self.as_if_built_from(old)
		comparison = self.mapping.compare_with_defaults()
		self.assertEqual(ids(comparison), [("check:Umsatzsteuer nach § 13b UStG 19 %", True)])
		(difference,) = comparison["differences"]
		self.assertEqual(
			difference["fields"],
			"Kz of the Base Without Base Account, Kz for Suppliers in Other Member States",
		)
		self.assertTrue(
			difference["proposed"].endswith(
				"; base without base account in Kz 84; suppliers in other member states in Kz 46"
			)
		)
		self.mapping.update_from_defaults(chosen=["check:Umsatzsteuer nach § 13b UStG 19 %"])
		stored = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(
			[(row.label, row.derived_base or None, row.derived_base_eu or None) for row in stored.checks],
			[("Umsatzsteuer 19 %", "81", None), ("Umsatzsteuer nach § 13b UStG 19 %", "84", "46")],
		)

	def test_the_kennzahl_for_suppliers_of_other_member_states_is_proposed_to_a_mapping_of_revision_2(self):
		old = dict(self.defaults())
		old[CHECK_13B] = {name: value for name, value in old[CHECK_13B].items() if name != "derived_base_eu"}
		self.as_if_built_from(old)
		comparison = self.mapping.compare_with_defaults()
		self.assertEqual(ids(comparison), [("check:Umsatzsteuer nach § 13b UStG 19 %", True)])
		(difference,) = comparison["differences"]
		self.assertEqual(difference["fields"], "Kz for Suppliers in Other Member States")
		self.mapping.update_from_defaults(chosen=["check:Umsatzsteuer nach § 13b UStG 19 %"])
		stored = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(stored.checks[1].derived_base_eu, "46")

	def test_the_kennzahl_of_output_tax_without_revenue_account_is_proposed_to_a_mapping_of_revision_3(self):
		old = dict(self.defaults())
		old[CHECK_19] = {name: value for name, value in old[CHECK_19].items() if name != "derived_base"}
		self.as_if_built_from(old)
		comparison = self.mapping.compare_with_defaults()
		self.assertEqual(ids(comparison), [("check:Umsatzsteuer 19 %", True)])
		(difference,) = comparison["differences"]
		self.assertEqual(difference["fields"], "Kz of the Base Without Base Account")
		self.assertTrue(difference["proposed"].endswith("; base without base account in Kz 81"))
		self.mapping.update_from_defaults(chosen=["check:Umsatzsteuer 19 %"])
		stored = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual((stored.checks[0].label, stored.checks[0].derived_base), ("Umsatzsteuer 19 %", "81"))
		self.assertEqual(stored.defaults_version, VERSION)

	def test_a_mapping_that_declines_it_keeps_the_deviation(self):
		old = dict(self.defaults())
		old[CHECK_19] = {name: value for name, value in old[CHECK_19].items() if name != "derived_base"}
		self.as_if_built_from(old)
		self.mapping.update_from_defaults(acknowledge=1)
		stored = frappe.get_doc(MAPPING, COMPANY)
		self.assertFalse(stored.checks[0].derived_base)
		self.assertEqual(ids(stored.compare_with_defaults()), [("check:Umsatzsteuer 19 %", False)])

	def test_vorgaben_laden_keeps_the_classifications_under_13b(self):
		supplier = "Steuerbote Test Lieferant Vorgaben"
		if not frappe.db.exists("Supplier", supplier):
			frappe.get_doc({"doctype": "Supplier", "supplier_name": supplier}).insert(ignore_permissions=True)
		mapping = frappe.get_doc(MAPPING, COMPANY)
		mapping.append(
			"reverse_charge",
			{
				"reference_doctype": "Supplier",
				"reference_name": supplier,
				"classification": "Other Reverse Charge",
			},
		)
		mapping.save()
		mapping.load_defaults()
		mapping.save()
		stored = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(
			[(row.reference_doctype, row.reference_name) for row in stored.reverse_charge],
			[("Supplier", supplier)],
		)

	def test_a_change_of_the_defaults_is_proposed_and_a_change_of_the_user_is_not(self):
		old = dict(self.defaults())
		old[(ACCOUNT, "8400")] = {**old[(ACCOUNT, "8400")], "kennzahl": "86"}
		del old[(ACCOUNT, "8603")]
		old[(ACCOUNT, "1200")] = {"place": "watched", "level": "blocking"}
		mine = dict(old)
		mine[(ACCOUNT, "1548")] = {"place": "watched", "level": "hint"}
		self.as_if_built_from(old, mine)
		comparison = self.mapping.compare_with_defaults()
		self.assertEqual(comparison["taken_over"], "SKR03 2025.4")
		self.assertEqual(
			ids(comparison),
			[("account:8400", True), ("account:1548", False), ("account:1200", True), ("account:8603", True)],
		)
		(kennzahl,) = (
			difference for difference in comparison["differences"] if difference["id"] == "account:8400"
		)
		self.assertEqual(
			{key: kennzahl[key] for key in ("subject", "change", "fields", "current", "proposed", "origin")},
			{
				"subject": "Account 8400",
				"change": "Will Change",
				"fields": "Kennzahl",
				"current": "Kz 86, credit",
				"proposed": "Kz 81, credit",
				"origin": "The defaults changed",
			},
		)

	def test_update_takes_over_what_is_chosen_and_keeps_everything_else(self):
		old = dict(self.defaults())
		old[(ACCOUNT, "8400")] = {**old[(ACCOUNT, "8400")], "kennzahl": "86"}
		del old[(ACCOUNT, "8603")]
		old[(ACCOUNT, "1200")] = {"place": "watched", "level": "blocking"}
		mine = {**old, (ACCOUNT, "1548"): {"place": "watched", "level": "hint"}}
		self.as_if_built_from(old, mine)
		taken = self.mapping.update_from_defaults(
			["account:8400", "account:8603", "account:1548-not-a-difference"]
		)
		self.assertEqual(taken, 2)
		mapping = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(
			{(row.account_number, row.kennzahl) for row in mapping.rules},
			{("8400", "81"), ("3123", "46"), ("1577", "67"), ("1576", "66")},
		)
		self.assertEqual(
			[(row.account, row.account_number, row.level) for row in mapping.watched],
			[
				(self.accounts["1548"], "1548", "hint"),
				(self.accounts["1200"], "1200", "blocking"),
				(self.accounts["8603"], "8603", "hint"),
			],
		)
		self.assertEqual(mapping.defaults_version, VERSION)
		self.assertEqual(load_items(mapping.defaults_rows), self.defaults())
		self.assertEqual(
			ids(mapping.compare_with_defaults()), [("account:1548", False), ("account:1200", False)]
		)

	def test_update_with_nothing_chosen_only_notes_the_defaults_of_today(self):
		self.as_if_built_from(self.defaults())
		self.assertEqual(self.mapping.compare_with_defaults()["differences"], [])
		self.assertEqual(self.mapping.update_from_defaults([], acknowledge=True), 0)
		self.assertEqual(frappe.db.get_value(MAPPING, COMPANY, "defaults_version"), VERSION)

	def test_update_without_a_choice_and_without_the_word_of_the_user_changes_nothing(self):
		"""As a client of the API calls it, without the dialog: neither the rows nor the defaults taken over change, so
		the change of the defaults stays proposed."""
		old = dict(self.defaults())
		old[(ACCOUNT, "8400")] = {**old[(ACCOUNT, "8400")], "kennzahl": "86"}
		self.as_if_built_from(old)
		before = frappe.get_doc(MAPPING, COMPANY)
		for chosen in (None, [], ["account:1548-not-a-difference"]):
			with self.subTest(chosen=chosen):
				self.assertEqual(frappe.get_doc(MAPPING, COMPANY).update_from_defaults(chosen), 0)
				stored = frappe.get_doc(MAPPING, COMPANY)
				self.assertEqual(
					(stored.defaults_version, stored.defaults_rows, stored.modified),
					(before.defaults_version, before.defaults_rows, before.modified),
				)
				self.assertEqual(stored.current_items(), old)
		self.assertEqual(
			ids(frappe.get_doc(MAPPING, COMPANY).compare_with_defaults()), [("account:8400", True)]
		)

	def test_update_with_nothing_chosen_and_the_word_of_the_user_declines_the_differences(self):
		"""The dialog says so when the user takes over none: the defaults of today become the base, and the change of
		the defaults left counts as the user's own from then on."""
		old = dict(self.defaults())
		old[(ACCOUNT, "8400")] = {**old[(ACCOUNT, "8400")], "kennzahl": "86"}
		self.as_if_built_from(old)
		self.assertEqual(self.mapping.update_from_defaults([], acknowledge=True), 0)
		stored = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(stored.defaults_version, VERSION)
		self.assertEqual(load_items(stored.defaults_rows), self.defaults())
		self.assertEqual(stored.current_items(), old)
		self.assertEqual(ids(stored.compare_with_defaults()), [("account:8400", False)])

	def test_the_form_names_the_defaults_a_mapping_without_rows_waits_for(self):
		"""A mapping without rows that has not taken over the defaults of today names them; one with rows, one that
		took them over and one of a chart of its own name none."""
		self.assertIsNone(defaults_to_load(frappe.get_doc(MAPPING, COMPANY)))
		frappe.delete_doc(MAPPING, COMPANY, force=True)
		empty = frappe.get_doc({"doctype": MAPPING, "company": COMPANY, "chart": "SKR03"}).insert()
		self.assertEqual(defaults_to_load(empty), VERSION)
		empty.db_set("defaults_version", "SKR03 2025.4")
		self.assertEqual(defaults_to_load(frappe.get_doc(MAPPING, COMPANY)), VERSION)
		empty.db_set("defaults_version", VERSION)
		self.assertIsNone(defaults_to_load(frappe.get_doc(MAPPING, COMPANY)))
		own = frappe.get_doc(MAPPING, COMPANY)
		own.update({"chart": "Eigener Kontenrahmen", "defaults_version": None})
		self.assertIsNone(defaults_to_load(own))

	def test_a_choice_that_breaks_the_mapping_is_refused_and_nothing_changes(self):
		old = {
			key: fields
			for key, fields in self.defaults().items()
			if key not in ((ACCOUNT, "3123"), (ACCOUNT, "1577"), CHECK_13B)
		}
		self.as_if_built_from(old)
		self.assertEqual(
			ids(self.mapping.compare_with_defaults()),
			[
				("account:3123", True),
				("account:1577", True),
				("check:Umsatzsteuer nach § 13b UStG 19 %", True),
			],
		)
		with self.assertRaisesRegex(frappe.ValidationError, "account 3123 is not mapped"):
			frappe.get_doc(MAPPING, COMPANY).update_from_defaults(["check:Umsatzsteuer nach § 13b UStG 19 %"])
		frappe.clear_messages()
		self.assertEqual(frappe.db.get_value(MAPPING, COMPANY, "defaults_version"), "SKR03 2025.4")
		self.assertEqual(frappe.get_doc(MAPPING, COMPANY).current_items(), old)

	def test_without_the_rows_of_the_defaults_every_difference_is_the_users(self):
		mapping = frappe.get_doc(MAPPING, COMPANY)
		mapping.defaults_rows = None
		mapping.defaults_version = None
		mapping.set("rules", [row for row in mapping.rules if row.account_number != "8400"])
		mapping.set("checks", [row for row in mapping.checks if row.label != CHECK_19[1]])
		mapping.save()
		comparison = mapping.compare_with_defaults()
		self.assertEqual((comparison["base_known"], comparison["taken_over"]), (False, ""))
		self.assertEqual(ids(comparison), [("account:8400", False), ("check:Umsatzsteuer 19 %", False)])
		self.assertEqual(
			{difference["origin"] for difference in comparison["differences"]}, {"Origin unknown"}
		)

	def test_vorgaben_laden_stays_the_full_reset(self):
		old = dict(self.defaults())
		old[(ACCOUNT, "8400")] = {**old[(ACCOUNT, "8400")], "kennzahl": "86"}
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

	def test_two_checks_with_one_label_are_refused(self):
		self.mapping.append(
			"checks",
			{"label": CHECK_19[1], "base_accounts": "8603", "tax_accounts": "1787", "side": "credit"},
		)
		with self.assertRaisesRegex(
			frappe.ValidationError, "two tax checks have the label 'Umsatzsteuer 19 %'"
		):
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
