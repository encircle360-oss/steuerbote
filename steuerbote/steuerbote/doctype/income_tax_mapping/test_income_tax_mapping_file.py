"""Zuordnung exportieren and Zuordnung importieren of the Income Tax Mapping on a site: the file attached privately with
its header, the checks of an import, and the round trip from one company to another."""

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

import steuerbote
from steuerbote.income_tax_mapping_sync import FILE_FORMAT, body_of_items, file_body
from steuerbote.mapping_sync import FILE_FORMAT as VAT_FILE_FORMAT
from steuerbote.mappings import transfer
from steuerbote.tests.helpers import make_account, make_company

# The tests build their own companies and accounts and need none of ERPNext's test records.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Account"]

MAPPING = "Income Tax Mapping"
SOURCE = "Steuerbote Test Ertragsteuern Datei Quelle GmbH"
TARGET = "Steuerbote Test Ertragsteuern Datei Ziel GmbH"
SHORT = "Steuerbote Test Ertragsteuern Datei Knapp GmbH"
# SKR03 accounts: two taxes on income, a trading account, a watched account and a bank, which the defaults leave out.
# SHORT lacks the trading account and the watched account.
ACCOUNTS = {
	"2200": ("Körperschaftsteuer", "Expense"),
	"4320": ("Gewerbesteuer", "Expense"),
	"2654": ("Erträge aus anderen Wertpapieren und Ausleihungen des Umlaufvermögens", "Income"),
	"4126": ("Tantiemen Gesellschafter-Geschäftsführer", "Expense"),
	"1200": ("Bank", "Asset"),
}
SHORT_ACCOUNTS = ("2200", "4320", "1200")


def make_accounts(company: str, numbers=tuple(ACCOUNTS)) -> dict[str, str]:
	return {
		number: frappe.db.get_value("Account", {"company": company, "account_number": number})
		or make_account(company, number, *ACCOUNTS[number])
		for number in numbers
	}


def new_mapping(company: str, chart: str = "SKR03", defaults: bool = True):
	frappe.delete_doc_if_exists(MAPPING, company, force=True)
	mapping = frappe.new_doc(MAPPING)
	mapping.update({"company": company, "chart": chart})
	if defaults:
		mapping.load_defaults()
	return mapping.insert()


def ids(comparison: dict) -> list[tuple[str, str, bool]]:
	return [
		(difference["id"], difference["change"], difference["proposes"])
		for difference in comparison["differences"]
	]


def rows(mapping) -> dict[str, list]:
	"""The tables of a mapping as their rows by account number, in their order."""
	return {
		"rules": [(row.account_number, row.category, row.trading_class or None) for row in mapping.rules],
		"watched": [(row.account_number, row.level) for row in mapping.watched],
	}


def attach(company: str, file_name: str, text: str, private: bool) -> str:
	"""A file uploaded to the mapping of the company, as the uploader of the form makes it; returns its address."""
	return (
		frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"attached_to_doctype": MAPPING,
				"attached_to_name": company,
				"is_private": int(private),
				"content": text.encode("utf-8"),
			}
		)
		.insert()
		.file_url
	)


class IntegrationTestIncomeTaxMappingFile(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for company, abbr, numbers in (
			(SOURCE, "STEDQ", tuple(ACCOUNTS)),
			(TARGET, "STEDZ", tuple(ACCOUNTS)),
			(SHORT, "STEDK", SHORT_ACCOUNTS),
		):
			make_company(company, abbr)
			make_accounts(company, numbers)
		cls.source_accounts = make_accounts(SOURCE)

	def setUp(self):
		self.source = new_mapping(SOURCE)
		(trading,) = (row for row in self.source.rules if row.account_number == "2654")
		trading.trading_class = "derivatives"
		self.source.append("watched", {"account": self.source_accounts["1200"], "level": "hint"})
		self.source.save()
		self.exported = self.source.export_mapping()
		self.text = self.exported["content"]

	def test_the_export_is_a_private_file_at_the_mapping_with_its_header(self):
		today = getdate()
		self.assertEqual(
			self.exported["file_name"],
			f"Kontenzuordnung-Ertragsteuern-Steuerbote-Test-Ertragsteuern-Datei-Quelle-GmbH-{today.isoformat()}.json",
		)
		file = frappe.get_doc("File", {"file_url": self.exported["file_url"]})
		self.assertEqual(
			(file.is_private, file.attached_to_doctype, file.attached_to_name), (1, MAPPING, SOURCE)
		)
		self.assertTrue(self.exported["file_url"].startswith("/private/files/"))
		self.assertEqual(file.get_content(), self.text)
		data = json.loads(self.text)
		body = file_body(self.source.current_items(), self.source.defaults_taken_over())
		self.assertEqual(
			data["header"],
			{
				"format": FILE_FORMAT,
				"format_version": transfer.FORMAT_VERSION,
				"app_version": steuerbote.__version__,
				"company": SOURCE,
				"chart": "SKR03",
				"defaults_version": "SKR03 2026.3",
				"exported_on": today.isoformat(),
				"sha256": transfer.checksum(body),
			},
		)
		self.assertEqual(data["body"], body)
		self.assertEqual(
			data["body"]["mapping"]["rules"][2],
			{"account_number": "2654", "category": "trading_unclassified", "trading_class": "derivatives"},
		)

	def test_a_second_export_of_the_day_keeps_the_file(self):
		self.assertEqual(self.source.export_mapping()["file_url"], self.exported["file_url"])
		self.assertEqual(
			frappe.db.count("File", {"attached_to_doctype": MAPPING, "attached_to_name": SOURCE}), 1
		)

	def test_the_round_trip_gives_the_second_company_the_same_mapping(self):
		target = new_mapping(TARGET, defaults=False)
		comparison = target.compare_with_file(content=self.text)
		self.assertEqual(
			(comparison["company"], comparison["chart"], comparison["defaults_version"]),
			(SOURCE, "SKR03", "SKR03 2026.3"),
		)
		self.assertTrue(all(proposes for _id, _change, proposes in ids(comparison)))
		chosen = [difference["id"] for difference in comparison["differences"]]
		self.assertEqual(target.import_file(content=self.text, chosen=chosen), len(chosen))
		target = frappe.get_doc(MAPPING, TARGET)
		self.assertEqual(rows(target), rows(frappe.get_doc(MAPPING, SOURCE)))
		self.assertEqual(target.current_items(), self.source.current_items())
		self.assertEqual(target.defaults_version, "SKR03 2026.3")
		self.assertEqual(target.defaults_taken_over(), self.source.defaults_taken_over())
		self.assertEqual(target.compare_with_file(content=self.text)["differences"], [])

	def test_the_import_takes_what_is_chosen_and_keeps_the_rest(self):
		target = new_mapping(TARGET)
		self.assertEqual(
			ids(target.compare_with_file(content=self.text)),
			[("account:2654", "Will Change", True), ("account:1200", "Will Be Added", True)],
		)
		self.assertEqual(target.import_file(content=self.text, chosen=["account:2654"]), 1)
		target = frappe.get_doc(MAPPING, TARGET)
		self.assertEqual(
			rows(target)["rules"],
			[("2200", "kst", None), ("4320", "gewst", None), ("2654", "trading_unclassified", "derivatives")],
		)
		self.assertEqual(rows(target)["watched"], [("4126", "hint")])

	def test_an_uploaded_file_must_be_private_and_attached_to_the_mapping(self):
		target = new_mapping(TARGET)
		private = attach(TARGET, "kontenzuordnung-ertragsteuern.json", self.text, private=True)
		self.assertEqual(len(target.compare_with_file(file_url=private)["differences"]), 2)
		public = attach(
			TARGET, "kontenzuordnung-ertragsteuern-oeffentlich.json", self.text + " ", private=False
		)
		with self.assertRaisesRegex(frappe.ValidationError, "is a public file"):
			target.compare_with_file(file_url=public)
		elsewhere = attach(
			SOURCE, "kontenzuordnung-ertragsteuern-quelle.json", self.text + "\n", private=True
		)
		with self.assertRaisesRegex(frappe.ValidationError, "There is no file .* at this mapping"):
			target.compare_with_file(file_url=elsewhere)
		frappe.clear_messages()
		with self.assertRaisesRegex(frappe.ValidationError, "Upload the file or paste its content"):
			target.compare_with_file(content="  \n")
		frappe.clear_messages()

	def test_a_file_changed_after_the_export_or_of_another_kind_is_refused(self):
		data = json.loads(self.text)
		data["body"]["mapping"]["watched"][0]["level"] = "blocking"
		vat_file = transfer.write(
			VAT_FILE_FORMAT,
			data["body"],
			app_version=steuerbote.__version__,
			company=SOURCE,
			chart="SKR03",
			defaults_version="",
			exported_on=getdate(),
		)
		target = new_mapping(TARGET)
		for content, refusal in (
			(json.dumps(data), "The checksum of the file does not fit its content"),
			(vat_file, "The file holds steuerbote/vat-return-mapping, not steuerbote/income-tax-mapping"),
		):
			with self.subTest(refusal=refusal), self.assertRaisesRegex(frappe.ValidationError, refusal):
				target.compare_with_file(content=content)
		frappe.clear_messages()

	def test_the_refusal_shows_what_the_file_holds_as_text(self):
		content = json.dumps({"header": {"format": "<b>steuerbote</b>"}, "body": {}})
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"The file holds &lt;b&gt;steuerbote&lt;/b&gt;, not steuerbote/income-tax-mapping",
		):
			new_mapping(TARGET).compare_with_file(content=content)
		frappe.clear_messages()

	def test_a_file_of_another_chart_is_refused(self):
		target = new_mapping(TARGET, chart="SKR04", defaults=False)
		with self.assertRaisesRegex(
			frappe.ValidationError, "The file holds a mapping of SKR03, this mapping is one of SKR04"
		):
			target.compare_with_file(content=self.text)
		frappe.clear_messages()

	def test_a_file_with_accounts_the_company_lacks_is_refused_with_their_numbers(self):
		short = new_mapping(SHORT)
		before = rows(frappe.get_doc(MAPPING, SHORT))
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"The company has no ledger account with the numbers 2654, 4126, which the file",
		):
			short.compare_with_file(content=self.text)
		frappe.clear_messages()
		self.assertEqual(rows(frappe.get_doc(MAPPING, SHORT)), before)

	def test_a_file_whose_rows_the_core_refuses_is_refused(self):
		items = self.source.current_items()
		items[("account", "2200")] = {**items[("account", "2200")], "trading_class": "shares"}
		text = transfer.write(
			FILE_FORMAT,
			{"mapping": body_of_items(items), "defaults": None},
			app_version=steuerbote.__version__,
			company=SOURCE,
			chart="SKR03",
			defaults_version="",
			exported_on=getdate(),
		)
		with self.assertRaisesRegex(
			frappe.ValidationError, "The file holds no valid mapping: .*a trading class needs the category"
		):
			new_mapping(TARGET).compare_with_file(content=text)
		frappe.clear_messages()
