"""Zuordnung exportieren and Zuordnung importieren on a site: the file attached privately with its header, the checks
of an import, taking over some differences, and the round trip from one company to another."""

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

import steuerbote
from steuerbote.mapping_sync import FILE_FORMAT, body_of_items, file_body
from steuerbote.mappings import transfer
from steuerbote.tests.helpers import make_account, make_company

# The tests build their own companies and accounts and need none of ERPNext's test records.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Account"]

MAPPING = "VAT Return Mapping"
SOURCE = "Steuerbote Test Datei Quelle GmbH"
TARGET = "Steuerbote Test Datei Ziel GmbH"
SHORT = "Steuerbote Test Datei Knapp GmbH"
# SKR03 accounts: a sale at 19 % with its tax, the Vorsteuer, a watched account and a bank, which the defaults leave
# out. SHORT lacks the Vorsteuer and the watched account.
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1548": ("Vorsteuer im Folgejahr abziehbar", "Asset"),
	"1200": ("Bank", "Asset"),
}
SHORT_ACCOUNTS = ("8400", "1776", "1200")


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
		"rules": [
			(row.account_number, row.kennzahl, row.side, row.tax_rate, row.also_kennzahl, row.also_side)
			for row in mapping.rules
		],
		"checks": [(row.label, row.base_accounts, row.tax_accounts, row.side) for row in mapping.checks],
		"watched": [(row.account_number, row.level) for row in mapping.watched],
	}


class IntegrationTestMappingFile(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for company, abbr, numbers in (
			(SOURCE, "STDQ", tuple(ACCOUNTS)),
			(TARGET, "STDZ", tuple(ACCOUNTS)),
			(SHORT, "STDK", SHORT_ACCOUNTS),
		):
			make_company(company, abbr)
			make_accounts(company, numbers)
		cls.source_accounts = make_accounts(SOURCE)

	def setUp(self):
		self.source = new_mapping(SOURCE)
		self.source.watched[0].level = "hint"
		self.source.append("watched", {"account": self.source_accounts["1200"], "level": "blocking"})
		self.source.save()
		self.exported = self.source.export_mapping()
		self.text = self.exported["content"]

	def test_the_export_is_a_private_file_at_the_mapping_with_its_header(self):
		today = getdate()
		self.assertEqual(
			self.exported["file_name"],
			f"Kontenzuordnung-Steuerbote-Test-Datei-Quelle-GmbH-{today.isoformat()}.json",
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
				"defaults_version": "SKR03 2026.2",
				"exported_on": today.isoformat(),
				"sha256": transfer.checksum(body),
			},
		)
		self.assertEqual(data["body"], body)
		self.assertEqual([row["level"] for row in data["body"]["mapping"]["watched"]], ["hint", "blocking"])

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
			(SOURCE, "SKR03", "SKR03 2026.2"),
		)
		self.assertTrue(all(proposes for _id, _change, proposes in ids(comparison)))
		chosen = [difference["id"] for difference in comparison["differences"]]
		self.assertEqual(target.import_file(content=self.text, chosen=chosen), len(chosen))
		target = frappe.get_doc(MAPPING, TARGET)
		self.assertEqual(rows(target), rows(frappe.get_doc(MAPPING, SOURCE)))
		self.assertEqual(target.current_items(), self.source.current_items())
		self.assertEqual(target.defaults_version, "SKR03 2026.2")
		self.assertEqual(target.defaults_taken_over(), self.source.defaults_taken_over())
		self.assertEqual(target.compare_with_file(content=self.text)["differences"], [])

	def test_the_import_takes_what_is_chosen_and_keeps_the_rest(self):
		target = new_mapping(TARGET)
		self.assertEqual(
			ids(target.compare_with_file(content=self.text)),
			[("account:1548", "Will Change", True), ("account:1200", "Will Be Added", True)],
		)
		self.assertEqual(target.import_file(content=self.text, chosen=["account:1548"]), 1)
		target = frappe.get_doc(MAPPING, TARGET)
		self.assertEqual(rows(target)["watched"], [("1548", "hint")])

	def test_an_uploaded_file_must_be_private_and_attached_to_the_mapping(self):
		target = new_mapping(TARGET)
		private = attach(TARGET, "kontenzuordnung.json", self.text, private=True)
		self.assertEqual(len(target.compare_with_file(file_url=private)["differences"]), 2)
		public = attach(TARGET, "kontenzuordnung-oeffentlich.json", self.text + " ", private=False)
		with self.assertRaisesRegex(frappe.ValidationError, "is a public file"):
			target.compare_with_file(file_url=public)
		elsewhere = attach(SOURCE, "kontenzuordnung-quelle.json", self.text + "\n", private=True)
		with self.assertRaisesRegex(frappe.ValidationError, "There is no file .* at this mapping"):
			target.compare_with_file(file_url=elsewhere)
		frappe.clear_messages()

	def test_pasted_content_goes_before_an_uploaded_file(self):
		target = new_mapping(TARGET)
		self.assertEqual(
			len(
				target.compare_with_file(file_url="/private/files/missing.json", content=self.text)[
					"differences"
				]
			),
			2,
		)

	def test_without_a_file_or_content_the_import_asks_for_one(self):
		for content in (None, "", "  \n"):
			with (
				self.subTest(content=content),
				self.assertRaisesRegex(frappe.ValidationError, "Upload the file or paste its content"),
			):
				self.source.compare_with_file(content=content)
		frappe.clear_messages()

	def test_a_file_changed_after_the_export_is_refused(self):
		data = json.loads(self.text)
		data["body"]["mapping"]["watched"][0]["level"] = "blocking"
		with self.assertRaisesRegex(
			frappe.ValidationError, "The checksum of the file does not fit its content"
		):
			new_mapping(TARGET).compare_with_file(content=json.dumps(data))
		frappe.clear_messages()

	def test_a_text_that_is_no_mapping_file_is_refused(self):
		for content, refusal in (
			("{rules", "The file is no JSON"),
			("{}", "The file is no mapping of Steuerbote"),
		):
			with self.subTest(content=content), self.assertRaisesRegex(frappe.ValidationError, refusal):
				self.source.compare_with_file(content=content)
		frappe.clear_messages()

	def test_the_refusal_shows_what_the_file_holds_as_text(self):
		content = json.dumps({"header": {"format": "<b>Müller & Söhne</b>"}, "body": {}})
		with self.assertRaisesRegex(
			frappe.ValidationError, f"The file holds &lt;b&gt;Müller &amp; Söhne&lt;/b&gt;, not {FILE_FORMAT}"
		):
			self.source.compare_with_file(content=content)
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
			"The company has no ledger account with the numbers 1548, 1576, which the file",
		):
			short.compare_with_file(content=self.text)
		frappe.clear_messages()
		self.assertEqual(rows(frappe.get_doc(MAPPING, SHORT)), before)

	def test_a_file_whose_rows_the_core_refuses_is_refused(self):
		items = self.source.current_items()
		items[("account", "8400")] = {**items[("account", "8400")], "kennzahl": "999"}
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
			frappe.ValidationError, "The file holds no valid mapping: .*unknown Kennzahl 999"
		):
			new_mapping(TARGET).compare_with_file(content=text)
		frappe.clear_messages()

	def test_a_file_without_defaults_leaves_the_mapping_without_them(self):
		mapping = frappe.get_doc(MAPPING, SOURCE)
		mapping.defaults_rows = None
		mapping.defaults_version = None
		mapping.save()
		text = mapping.export_mapping()["content"]
		self.assertEqual(json.loads(text)["header"]["defaults_version"], "")
		target = new_mapping(TARGET)
		target.import_file(content=text, chosen=[])
		target = frappe.get_doc(MAPPING, TARGET)
		self.assertEqual((target.defaults_version or None, target.defaults_rows or None), (None, None))
		self.assertIsNone(target.defaults_taken_over())


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
