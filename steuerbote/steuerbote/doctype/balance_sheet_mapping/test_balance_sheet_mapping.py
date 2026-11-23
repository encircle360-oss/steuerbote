"""The Balance Sheet Mapping on a site: what saving checks against the taxonomy, Vorgaben laden and Vorgaben
aktualisieren with the defaults of a chart, the file of a mapping from one company to another, Konten prüfen, and the
books placed on the positions.

The extended mini taxonomy (steuerbote/xbrl/tests/positions.py) stands in for the installed HGB-Taxonomie 6.9, and a
small table of defaults for the defaults of the DATEV charts (steuerbote/ebilanz/defaults.py); the empty table of
revision 0 stands in for the defaults before them. Where the labels of the positions count, the package of esteuer.de
that STEUERBOTE_TAXONOMY_6_9 names is the installed taxonomy (steuerbote/xbrl/tests/real.py)."""

import json
from contextlib import contextmanager
from decimal import Decimal
from types import MappingProxyType
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import balance_mapping_sync
from steuerbote.balance_mapping_sync import FILE_FORMAT, default_items, dump_items, file_body, load_items
from steuerbote.ebilanz import defaults as ebilanz_defaults
from steuerbote.mappings import transfer
from steuerbote.steuerbote.doctype.balance_sheet_mapping import balance_sheet_mapping
from steuerbote.tests.helpers import make_account, make_company
from steuerbote.ustva import WatchLevel
from steuerbote.xbrl.mapping import (
	AccountBalance,
	Books,
	DefaultExcluded,
	DefaultRule,
	Defaults,
	DefaultWatched,
	Part,
	Purpose,
)
from steuerbote.xbrl.tests import positions, real

# The tests build their own companies and accounts and need none of ERPNext's test records.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Account"]

MAPPING = "Balance Sheet Mapping"
COMPANY = "Steuerbote Test Bilanzzuordnung GmbH"
TARGET = "Steuerbote Test Bilanzzuordnung Ziel GmbH"
NEIGHBOUR = "Steuerbote Test Bilanzzuordnung Nachbar GmbH"
LABELS = "Steuerbote Test Bilanzzuordnung Bezeichnungen GmbH"
BANK = "bs.ass.currAss.cashEquiv.bank"
BANK_LIABILITY = "bs.eqLiab.liab.bank"
SUBSCRIBED = "bs.eqLiab.equity.subscribed.corp"
SALES = "is.netIncome.netSales"
# SKR04 accounts: two banks, the Gezeichnetes Kapital, Verbindlichkeiten, Erlöse, a Geldtransit, a Saldenvortrag and
# an account without number.
ACCOUNTS = {
	"1800": ("Bank", "Asset"),
	"1810": ("Bank 2", "Asset"),
	"2900": ("Gezeichnetes Kapital", "Equity"),
	"3300": ("Verbindlichkeiten aus Lieferungen und Leistungen", "Liability"),
	"4400": ("Erlöse 19 % USt", "Income"),
	"1460": ("Geldtransit", "Asset"),
	"9000": ("Saldenvorträge, Sachkonten", "Equity"),
}
# SKR04 accounts that the defaults put on positions whose labels in the HGB-Taxonomie 6.9 are longer than 140
# characters.
LABEL_ACCOUNTS = {
	"0240": ("Geschäftsbauten", "Asset"),
	"3011": (
		"Rückstellungen für Zuschussverpflichtungen für Pensionskassen und Lebensversicherungen",
		"Liability",
	),
	"6286": ("Forderungsverluste 19 % USt (soweit unüblich hoch)", "Expense"),
	"6310": ("Miete (unbewegliche Wirtschaftsgüter)", "Expense"),
}
TEST_DEFAULTS = Defaults(
	"SKR04",
	"6.9",
	rules=(
		DefaultRule("1800-1849", BANK, opposite=BANK_LIABILITY),
		DefaultRule("2900", SUBSCRIBED),
		DefaultRule("4400", SALES),
	),
	watched=(DefaultWatched("1460", WatchLevel.HINT),),
	excluded=(DefaultExcluded("9000-9009", "Saldenvorträge der Klasse 9"),),
)


def make_accounts(company: str, accounts: dict[str, tuple[str, str]] = ACCOUNTS) -> dict[str, str]:
	return {
		number: frappe.db.get_value("Account", {"company": company, "account_number": number})
		or make_account(company, number, label, root_type)
		for number, (label, root_type) in accounts.items()
	}


def rows(mapping) -> dict[str, list]:
	"""The tables of a mapping as their rows by account number, in their order."""
	return {
		"rules": [
			(
				row.account_number,
				row.concept,
				row.opposite_concept or None,
				row.purpose,
				row.shareholder,
				row.remaining_term or None,
			)
			for row in mapping.rules
		],
		"watched": [(row.account_number, row.level) for row in mapping.watched],
		"excluded": [(row.account_number, row.reason) for row in mapping.excluded],
	}


class MappingTestCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STBLZ")
		cls.accounts = make_accounts(COMPANY)
		cls.without_number = frappe.db.get_value(
			"Account", {"company": COMPANY, "account_name": "Kasse ohne Nummer"}
		) or make_account(COMPANY, None, "Kasse ohne Nummer", "Asset")

	def setUp(self):
		super().setUp()
		self.installed(positions.view())
		frappe.delete_doc_if_exists(MAPPING, COMPANY, force=True)

	def installed(self, view) -> None:
		"""The taxonomy saving checks the positions against, None for one Taxonomie einrichten has not installed."""
		patcher = patch.object(balance_sheet_mapping, "position_taxonomy", return_value=view)
		patcher.start()
		self.addCleanup(patcher.stop)

	def with_defaults(self, defaults: Defaults = TEST_DEFAULTS) -> None:
		patcher = patch.object(balance_mapping_sync, "defaults_for", return_value=defaults)
		patcher.start()
		self.addCleanup(patcher.stop)

	@contextmanager
	def at_revision_0(self):
		"""The empty table of revision 0, before the defaults of the DATEV charts."""
		with (
			patch.object(balance_mapping_sync, "defaults_for", return_value=Defaults("SKR04", "6.9")),
			patch.object(ebilanz_defaults, "REVISIONS", MappingProxyType({"6.9": 0})),
		):
			yield

	def new_mapping(self, company: str = COMPANY, chart: str = "SKR04", **tables):
		frappe.delete_doc_if_exists(MAPPING, company, force=True)
		mapping = frappe.new_doc(MAPPING)
		mapping.update({"company": company, "chart": chart})
		for table, entries in tables.items():
			for entry in entries:
				mapping.append(table, entry)
		return mapping


class IntegrationTestBalanceSheetMapping(MappingTestCase):
	def test_saving_names_each_position_without_its_prefix_and_with_its_label(self):
		mapping = self.new_mapping(
			rules=[
				{
					"account": self.accounts["1800"],
					"concept": f"de-gaap-ci:{BANK}",
					"opposite_concept": f"de-gaap-ci:{BANK_LIABILITY}",
				}
			]
		).insert()
		(rule,) = frappe.get_doc(MAPPING, mapping.name).rules
		self.assertEqual(
			(rule.account_number, rule.concept, rule.opposite_concept, rule.purpose, rule.concept_label),
			("1800", BANK, BANK_LIABILITY, "both", "Guthaben bei Kreditinstituten"),
		)

	def test_saving_refuses_every_position_a_rule_may_not_name(self):
		mapping = self.new_mapping(
			rules=[
				{"account": self.accounts["1800"], "concept": "bs.ass.currAss.cashEquiv.gold"},
				{"account": self.accounts["4400"], "concept": BANK},
			]
		)
		with self.assertRaises(frappe.ValidationError) as caught:
			mapping.insert()
		message = str(caught.exception)
		self.assertIn(
			"Account 1800: the HGB-Taxonomie 6.9 has no position bs.ass.currAss.cashEquiv.gold.", message
		)
		self.assertIn(
			f"Account 4400 is a profit and loss account, but {BANK} is a position of the Bilanz.", message
		)
		self.assertFalse(frappe.db.exists(MAPPING, COMPANY))

	def test_without_the_taxonomy_the_rows_are_saved_and_the_form_says_that_the_positions_wait(self):
		self.installed(None)
		shown = len(frappe.local.message_log)
		mapping = self.new_mapping(
			rules=[{"account": self.accounts["1800"], "concept": "bs.ass.currAss.cashEquiv.gold"}]
		)
		mapping.insert()
		self.assertEqual(frappe.get_doc(MAPPING, COMPANY).rules[0].concept_label, None)
		self.assertIn(
			"The HGB-Taxonomie 6.9 is not installed, so saving has not checked the positions",
			json.dumps(frappe.local.message_log[shown:]),
		)

	def test_a_row_on_an_account_of_another_company_or_on_a_group_is_refused(self):
		make_company(NEIGHBOUR, "STBLN")
		other = frappe.db.get_value(
			"Account", {"company": NEIGHBOUR, "account_number": "1800"}
		) or make_account(NEIGHBOUR, "1800", "Bank", "Asset")
		with self.assertRaisesRegex(frappe.ValidationError, "does not belong to company"):
			self.new_mapping(rules=[{"account": other, "concept": BANK}]).insert()
		group = frappe.db.get_value("Account", {"company": COMPANY, "is_group": 1})
		with self.assertRaisesRegex(frappe.ValidationError, "is a group"):
			self.new_mapping(watched=[{"account": group, "level": "blocking"}]).insert()

	def test_an_account_in_two_rows_is_refused(self):
		mapping = self.new_mapping(
			rules=[{"account": self.accounts["1460"], "concept": BANK}],
			watched=[{"account": self.accounts["1460"], "level": "hint"}],
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Account 1460 has more than one row"):
			mapping.insert()

	def test_an_account_outside_the_bilanz_and_the_guv_needs_its_reason(self):
		mapping = self.new_mapping(excluded=[{"account": self.accounts["9000"], "reason": " "}])
		with self.assertRaises(frappe.ValidationError):
			mapping.insert()

	def test_place_puts_the_books_on_the_positions_of_the_installed_taxonomy(self):
		mapping = self.new_mapping(
			rules=[{"account": self.accounts["1800"], "concept": BANK, "opposite_concept": BANK_LIABILITY}]
		).insert()
		books = Books(
			(
				AccountBalance(
					self.accounts["1800"], "1800", "Bank", Part.BALANCE_SHEET, credit=Decimal("250")
				),
			)
		)
		with patch.object(
			balance_sheet_mapping.eric_settings, "taxonomy_view", return_value=positions.view()
		):
			placement = mapping.place(books, Purpose.COMMERCIAL)
		((concept, value),) = [(item.concept, item.value) for item in placement.placed]
		self.assertEqual((concept, value, placement.ready), (BANK_LIABILITY, Decimal("250"), True))


class IntegrationTestBalanceSheetMappingDefaults(MappingTestCase):
	def test_vorgaben_laden_takes_the_defaults_for_the_accounts_of_the_company(self):
		self.with_defaults()
		mapping = self.new_mapping()
		self.assertEqual(mapping.load_defaults(), ["3300"])
		mapping.insert()
		stored = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(
			rows(stored),
			{
				"rules": [
					("1800", BANK, BANK_LIABILITY, "both", 0, None),
					("1810", BANK, BANK_LIABILITY, "both", 0, None),
					("2900", SUBSCRIBED, None, "both", 0, None),
					("4400", SALES, None, "both", 0, None),
				],
				"watched": [("1460", "hint")],
				"excluded": [("9000", "Saldenvorträge der Klasse 9")],
			},
		)
		self.assertEqual(stored.defaults_version, "SKR04 Taxonomie 6.9 2026.1")
		self.assertEqual(load_items(stored.defaults_rows), default_items("SKR04", "6.9", set(ACCOUNTS)))
		self.assertEqual(stored.rules[0].account, self.accounts["1800"])

	def test_vorgaben_laden_takes_the_defaults_of_the_datev_chart_for_every_account(self):
		"""The defaults of SKR04 for the HGB-Taxonomie 6.9 give each account of the company its place; without the
		taxonomy the rows are saved unchecked."""
		self.installed(None)
		mapping = self.new_mapping()
		self.assertEqual(mapping.load_defaults(), [])
		mapping.insert()
		stored = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(
			rows(stored),
			{
				"rules": [
					(
						"1460",
						"bs.ass.currAss.receiv.other.other",
						"bs.eqLiab.liab.other.other",
						"both",
						0,
						None,
					),
					("1800", BANK, "bs.eqLiab.liab.bank.other", "both", 0, None),
					("1810", BANK, "bs.eqLiab.liab.bank.other", "both", 0, None),
					("2900", SUBSCRIBED, None, "both", 0, None),
					(
						"3300",
						"bs.eqLiab.liab.trade.genOther",
						"bs.ass.currAss.receiv.other.other",
						"both",
						0,
						None,
					),
					(
						"4400",
						"is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales.generalRateVAT",
						None,
						"both",
						0,
						None,
					),
				],
				"watched": [],
				"excluded": [
					("9000", "Vortragskonto der Eröffnungsbuchungen, ausgeglichen nach dem Vortrag"),
				],
			},
		)
		self.assertEqual(stored.defaults_version, "SKR04 Taxonomie 6.9 2026.1")

	def test_vorgaben_laden_keeps_the_label_of_each_position_of_the_installed_taxonomy_whole(self):
		"""Saving writes the label of each position into its rule, longer than the 140 characters of a Data field for
		the Geschäftsbauten, the Rückstellungen for Pensionskassen, the Forderungsverluste and the Miete."""
		taxonomy = real.view()
		self.installed(taxonomy)
		make_company(LABELS, "STBLB")
		make_accounts(LABELS, LABEL_ACCOUNTS)
		mapping = self.new_mapping(LABELS)
		self.assertEqual(mapping.load_defaults(), [])
		mapping.insert()
		stored = frappe.get_doc(MAPPING, LABELS)
		self.assertEqual(
			[(row.account_number, row.concept, len(row.concept_label or "")) for row in stored.rules],
			[
				("0240", "bs.ass.fixAss.tan.landBuildings.buildingsOnOwnLand.buildings", 181),
				("3011", "bs.eqLiab.accruals.pensions.externalFunds", 181),
				("6286", "is.netIncome.regular.operatingTC.deprAmort.currAss.receiv.other", 288),
				("6310", "is.netIncome.regular.operatingTC.otherCost.leaseFix.other", 161),
			],
		)
		self.assertEqual(
			[row.concept_label for row in stored.rules], [taxonomy.label(row.concept) for row in stored.rules]
		)

	def test_vorgaben_laden_keeps_the_level_of_a_watched_account(self):
		self.with_defaults()
		mapping = self.new_mapping(watched=[{"account": self.accounts["1460"], "level": "blocking"}])
		mapping.load_defaults()
		self.assertEqual([(row.account_number, row.level) for row in mapping.watched], [("1460", "blocking")])
		mapping.insert()
		self.assertEqual(
			[
				(difference["id"], difference["proposes"])
				for difference in mapping.compare_with_defaults()["differences"]
			],
			[("account:1460", False)],
		)

	def test_the_defaults_of_revision_0_hold_no_rows(self):
		mapping = self.new_mapping()
		with self.at_revision_0():
			self.assertEqual(mapping.load_defaults(), sorted(ACCOUNTS))
			mapping.insert()
		self.assertEqual(
			(mapping.rules, mapping.watched, mapping.excluded, mapping.defaults_version),
			([], [], [], "SKR04 Taxonomie 6.9 2026.0"),
		)

	def test_vorgaben_aktualisieren_proposes_the_first_defaults_to_a_mapping_of_revision_0(self):
		"""A mapping made before the defaults of the DATEV charts took over the empty table; every row of the first
		defaults is a change of the defaults, checked in the dialog."""
		mapping = self.new_mapping()
		with self.at_revision_0():
			mapping.load_defaults()
			mapping.insert()
		self.with_defaults()
		comparison = mapping.compare_with_defaults()
		self.assertEqual(comparison["base_known"], True)
		self.assertEqual(
			[
				(difference["id"], difference["change"], difference["proposes"])
				for difference in comparison["differences"]
			],
			[
				(f"account:{number}", "Will Be Added", True)
				for number in ("1800", "1810", "2900", "4400", "1460", "9000")
			],
		)
		(bank,) = (
			difference for difference in comparison["differences"] if difference["id"] == "account:1800"
		)
		self.assertEqual(
			(bank["subject"], bank["proposed"]),
			("Account 1800", f"Position {BANK}, opposite balance {BANK_LIABILITY}, both"),
		)
		chosen = [difference["id"] for difference in comparison["differences"]]
		self.assertEqual(mapping.update_from_defaults(chosen), 6)
		self.assertEqual(len(frappe.get_doc(MAPPING, COMPANY).rules), 4)

	def test_a_chart_of_its_own_has_no_defaults(self):
		mapping = self.new_mapping(chart="Eigener Kontenrahmen")
		with self.assertRaisesRegex(frappe.ValidationError, "There are no defaults for Eigener Kontenrahmen"):
			mapping.load_defaults()


class IntegrationTestBalanceSheetMappingFile(MappingTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(TARGET, "STBLY")
		make_accounts(TARGET)

	def setUp(self):
		super().setUp()
		self.with_defaults()
		self.source = self.new_mapping()
		self.source.load_defaults()
		self.source.insert()
		self.source.rules[0].remaining_term = "up to one year"
		self.source.save()
		self.exported = self.source.export_mapping()
		self.text = self.exported["content"]

	def test_the_export_is_a_private_file_at_the_mapping_with_the_version_of_its_taxonomy(self):
		self.assertTrue(
			self.exported["file_name"].startswith("Bilanzzuordnung-Steuerbote-Test-Bilanzzuordnung-GmbH-")
		)
		file = frappe.get_doc("File", {"file_url": self.exported["file_url"]})
		self.assertEqual(
			(file.is_private, file.attached_to_doctype, file.attached_to_name), (1, MAPPING, COMPANY)
		)
		data = json.loads(self.text)
		self.assertEqual(data["header"]["format"], FILE_FORMAT)
		self.assertEqual(
			data["body"],
			file_body("6.9", self.source.current_items(), self.source.defaults_taken_over()),
		)
		self.assertEqual(data["body"]["taxonomy_version"], "6.9")

	def test_the_round_trip_gives_the_second_company_the_same_mapping(self):
		target = self.new_mapping(TARGET).insert()
		comparison = target.compare_with_file(content=self.text)
		chosen = [difference["id"] for difference in comparison["differences"]]
		self.assertEqual(target.import_file(content=self.text, chosen=chosen), len(chosen))
		target = frappe.get_doc(MAPPING, TARGET)
		self.assertEqual(rows(target), rows(frappe.get_doc(MAPPING, COMPANY)))
		self.assertEqual(target.defaults_version, "SKR04 Taxonomie 6.9 2026.1")
		self.assertEqual(target.defaults_rows, dump_items(load_items(self.source.defaults_rows)))

	def test_an_import_refuses_a_file_of_another_taxonomy_another_chart_or_with_accounts_the_company_lacks(
		self,
	):
		target = self.new_mapping(TARGET).insert()
		body = json.loads(self.text)["body"]
		for changed, refusal in (
			({**body, "taxonomy_version": "6.10"}, "names those of 6.9"),
			(
				{
					**body,
					"mapping": {**body["mapping"], "excluded": [{"account_number": "9999", "reason": "x"}]},
				},
				"9999",
			),
		):
			text = transfer.write(
				FILE_FORMAT,
				changed,
				app_version="0",
				company=COMPANY,
				chart="SKR04",
				defaults_version="",
				exported_on=frappe.utils.getdate(),
			)
			with self.subTest(refusal=refusal), self.assertRaisesRegex(frappe.ValidationError, refusal):
				target.compare_with_file(content=text)
		other = self.new_mapping(TARGET, chart="SKR03").insert()
		with self.assertRaisesRegex(frappe.ValidationError, "this mapping is one of SKR03"):
			other.compare_with_file(content=self.text)

	def test_the_refusal_shows_what_the_file_holds_as_text(self):
		content = json.dumps({"header": {"format": "<b>Müller & Söhne</b>"}, "body": {}})
		with self.assertRaisesRegex(
			frappe.ValidationError, f"The file holds &lt;b&gt;Müller &amp; Söhne&lt;/b&gt;, not {FILE_FORMAT}"
		):
			self.source.compare_with_file(content=content)


class IntegrationTestBalanceSheetMappingAccounts(MappingTestCase):
	def test_konten_pruefen_names_the_accounts_without_a_place(self):
		mapping = self.new_mapping(rules=[{"account": self.accounts["1800"], "concept": BANK}]).insert()
		found = mapping.accounts_without_place()
		self.assertEqual(
			sorted(account["account_number"] for account in found),
			sorted(["", *(number for number in ACCOUNTS if number != "1800")]),
		)
		(without,) = (account for account in found if not account["account_number"])
		self.assertEqual((without["account"], without["root_type"]), (self.without_number, "Asset"))

	def test_watching_them_watches_those_with_a_number_at_the_level_blocking(self):
		mapping = self.new_mapping(rules=[{"account": self.accounts["1800"], "concept": BANK}]).insert()
		added = mapping.watch_accounts_without_place()
		self.assertEqual(len(added), len(ACCOUNTS) - 1)
		stored = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual({row.level for row in stored.watched}, {"blocking"})
		self.assertEqual([account["account_number"] for account in stored.accounts_without_place()], [""])
		with self.assertRaisesRegex(
			frappe.ValidationError, "No account of the company with an account number"
		):
			stored.watch_accounts_without_place()
