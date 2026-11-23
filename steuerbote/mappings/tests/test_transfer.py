import hashlib
import html
import json
from datetime import date
from unittest import TestCase

from steuerbote.mappings.transfer import (
	BAD_HEADER,
	CHECKSUM_DIFFERS,
	FORMAT_VERSION,
	MESSAGES,
	NEWER_FORMAT,
	NOT_A_FILE,
	NOT_JSON,
	OTHER_FORMAT,
	Header,
	TransferError,
	TransferFile,
	canonical_json,
	checksum,
	message,
	read,
	write,
)

KIND = "steuerbote/vat-return-mapping"
BODY = {
	"mapping": {
		"rules": [{"account_number": "8400", "kennzahl": "81", "side": "credit", "tax_rate": None}],
		"checks": [],
		"watched": [{"account_number": "1548", "level": "hint"}],
	},
	"defaults": None,
}
EXPORTED_ON = date(2026, 11, 23)


def written(body=BODY, **fields) -> str:
	header = {
		"app_version": "0.5.0",
		"company": "Muster Möbel GmbH",
		"chart": "SKR03",
		"defaults_version": "SKR03 2026.1",
		"exported_on": EXPORTED_ON,
		**fields,
	}
	return write(KIND, body, **header)


def changed(text: str, part: str, **fields) -> str:
	"""The text of a file with fields of its header or body set, as an editor would leave it."""
	data = json.loads(text)
	data[part].update(fields)
	return json.dumps(data, indent=2)


def refusal(text: str) -> tuple[str, tuple]:
	try:
		read(text, KIND)
	except TransferError as error:
		return error.template, error.values
	raise AssertionError("read the file")


class CanonicalTest(TestCase):
	def test_the_canonical_json_sorts_keys_and_leaves_out_blanks(self):
		self.assertEqual(canonical_json({"b": [1, "ä"], "a": None}), '{"a":null,"b":[1,"ä"]}')

	def test_the_checksum_is_the_sha256_of_the_canonical_body(self):
		self.assertEqual(checksum(BODY), hashlib.sha256(canonical_json(BODY).encode("utf-8")).hexdigest())
		self.assertEqual(checksum({"b": 1, "a": 2}), checksum({"a": 2, "b": 1}))
		self.assertNotEqual(checksum(BODY), checksum({**BODY, "defaults": {}}))


class WriteTest(TestCase):
	def test_the_file_holds_the_header_first_and_then_the_body(self):
		data = json.loads(written())
		self.assertEqual(list(data), ["header", "body"])
		self.assertEqual(
			data["header"],
			{
				"format": KIND,
				"format_version": FORMAT_VERSION,
				"app_version": "0.5.0",
				"company": "Muster Möbel GmbH",
				"chart": "SKR03",
				"defaults_version": "SKR03 2026.1",
				"exported_on": "2026-11-23",
				"sha256": checksum(BODY),
			},
		)
		self.assertEqual(data["body"], BODY)

	def test_the_file_is_indented_utf_8_for_people_to_read(self):
		text = written()
		self.assertIn('\n "header": {\n  "format": "steuerbote/vat-return-mapping",', text)
		self.assertIn("Möbel", text)
		self.assertTrue(text.endswith("}\n"))


class ReadTest(TestCase):
	def test_read_gives_back_the_header_and_the_body(self):
		self.assertEqual(
			read(written(), KIND),
			TransferFile(
				Header(
					KIND,
					1,
					"0.5.0",
					"Muster Möbel GmbH",
					"SKR03",
					"SKR03 2026.1",
					EXPORTED_ON,
					checksum(BODY),
				),
				BODY,
			),
		)

	def test_the_indent_of_the_file_does_not_matter(self):
		compact = json.dumps(json.loads(written()))
		self.assertEqual(read(compact, KIND).body, BODY)

	def test_a_text_that_is_no_json_is_refused(self):
		for text in ("", "{header", "Kontenzuordnung"):
			with self.subTest(text=text):
				self.assertEqual(refusal(text), (NOT_JSON, ()))

	def test_a_file_needs_a_header_and_a_body(self):
		for data in ([], {"header": {}}, {"header": {}, "body": {}, "more": 1}, {"header": [], "body": {}}):
			with self.subTest(data=data):
				self.assertEqual(refusal(json.dumps(data)), (NOT_A_FILE, ()))

	def test_a_file_of_another_kind_is_refused(self):
		text = changed(written(), "header", format="steuerbote/balance-sheet-mapping")
		self.assertEqual(refusal(text), (OTHER_FORMAT, ("steuerbote/balance-sheet-mapping", KIND)))

	def test_a_newer_format_version_is_refused(self):
		self.assertEqual(
			refusal(changed(written(), "header", format_version=2)), (NEWER_FORMAT, (2, FORMAT_VERSION))
		)

	def test_each_field_of_the_header_is_needed_in_its_form(self):
		for field, value in (
			("format", None),
			("format_version", "1"),
			("format_version", True),
			("format_version", 0),
			("app_version", 5),
			("company", None),
			("chart", ["SKR03"]),
			("defaults_version", None),
			("exported_on", 20261123),
			("exported_on", "23.11.2026"),
			("sha256", None),
		):
			with self.subTest(field=field, value=value):
				self.assertEqual(
					refusal(changed(written(), "header", **{field: value})), (BAD_HEADER, (field,))
				)

	def test_a_file_changed_after_the_export_is_refused(self):
		data = json.loads(written())
		data["body"]["mapping"]["watched"][0]["level"] = "blocking"
		self.assertEqual(refusal(json.dumps(data)), (CHECKSUM_DIFFERS, ()))
		self.assertEqual(refusal(changed(written(), "header", sha256="0" * 64)), (CHECKSUM_DIFFERS, ()))

	def test_the_messages_name_what_is_wrong(self):
		self.assertEqual(str(TransferError(OTHER_FORMAT, "x", KIND)), f"The file holds x, not {KIND}.")
		self.assertEqual(len(set(MESSAGES)), 6)


class MessageTest(TestCase):
	"""The text of a refusal as Zuordnung importieren shows it, in a dialog that reads it as HTML."""

	def refused(self, text: str) -> TransferError:
		with self.assertRaises(TransferError) as raised:
			read(text, KIND)
		return raised.exception

	def test_translates_the_template_and_escapes_each_value_of_the_file(self):
		german = {OTHER_FORMAT: "Die Datei enthält {0}, nicht {1}."}
		error = self.refused(changed(written(), "header", format="<b>Müller & Söhne</b>"))
		self.assertEqual(
			message(error, lambda text: german.get(text, text), html.escape),
			f"Die Datei enthält &lt;b&gt;Müller &amp; Söhne&lt;/b&gt;, nicht {KIND}.",
		)

	def test_escapes_a_value_that_is_no_text_as_its_text(self):
		error = self.refused(changed(written(), "header", format_version=2))
		self.assertEqual(
			message(error, str, html.escape),
			f"The file has the format version 2; this Steuerbote reads up to {FORMAT_VERSION}.",
		)
