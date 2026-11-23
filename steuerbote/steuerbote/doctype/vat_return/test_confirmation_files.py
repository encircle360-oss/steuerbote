"""USt-IdNrn. prüfen at the Umsatzsteuer-Voranmeldung, read from its files without a bench: the form offers it next
to Berechnen with the dialog of the Zusammenfassende Meldung, the methods the shared script calls are whitelisted,
the return names its USt-IdNr.-Bestätigungen, and its texts read in German."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[3]
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSLATIONS = APP / "translations" / "de.csv"
VAT_RETURN = DOCTYPES / "vat_return"
ZM = DOCTYPES / "recapitulative_statement"
SHARED_SCRIPT = APP / "public" / "js" / "vat_id_confirmation.js"
CONFIRMING = DOCTYPES / "vat_id_confirmation" / "confirming.py"
INCLUDES = [
	'{% include "steuerbote/public/js/elster_transmission.js" %}',
	'{% include "steuerbote/public/js/vat_id_confirmation.js" %}',
]
BUTTON = re.compile(r'frm\.add_custom_button\(__\("([^"]+)"\)')
CALLED = re.compile(r'frm\.call\("(\w+)"')


def read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def doctype(name: str) -> dict:
	return json.loads(read(DOCTYPES / name / f"{name}.json"))


def fields(name: str) -> dict[str, dict]:
	return {field["fieldname"]: field for field in doctype(name)["fields"]}


def whitelisted(source: str, method: str) -> bool:
	return re.search(rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {method}\(', source) is not None


class FormTest(TestCase):
	def test_both_forms_take_the_confirmation_from_the_shared_script(self):
		for script in (VAT_RETURN / "vat_return.js", ZM / "recapitulative_statement.js"):
			with self.subTest(script=script.name):
				text = read(script)
				self.assertEqual(text.splitlines()[:2], INCLUDES)
				for call in ("listen_for_confirmations(frm);", "release_stale_confirmation(frm);"):
					self.assertIn(call, text)
				self.assertRegex(text, r"\(\) =>\n\t\t\t\tconfirm_vat_ids\(\n\t\t\t\t\tfrm,\n")

	def test_confirm_vat_ids_stands_next_to_berechnen(self):
		buttons = BUTTON.findall(read(VAT_RETURN / "vat_return.js"))
		self.assertEqual(buttons[:2], ["Calculate", "Confirm VAT IDs"])

	def test_the_return_offers_confirm_vat_ids_where_the_server_takes_it(self):
		"""A calculated draft that is neither being confirmed nor transmitted, and that no Senden of its own keeps as
		it was sent (confirm_vat_ids, refuse_if_sent)."""
		found = re.search(
			r"\nfunction can_confirm_vat_ids\(frm\) \{\n(?P<body>.*?)\n\}\n",
			read(VAT_RETURN / "vat_return.js"),
			re.DOTALL,
		)
		self.assertIsNotNone(found)
		for condition in (
			'["Berechnet", "Bereit"].includes(frm.doc.status)',
			"frm.doc.docstatus === 0",
			"!frm.doc.confirmation_in_progress",
			"!transmission_blocked(frm)",
			"!locked_as_sent(frm)",
		):
			with self.subTest(condition=condition):
				self.assertIn(condition, found["body"])

	def test_the_methods_the_shared_script_calls_are_whitelisted_for_post(self):
		self.assertEqual(
			sorted(set(CALLED.findall(read(SHARED_SCRIPT)))),
			["confirm_vat_ids", "release_stale_confirmation"],
		)
		self.assertTrue(whitelisted(read(CONFIRMING), "release_stale_confirmation"))
		for controller in (VAT_RETURN / "vat_return.py", ZM / "recapitulative_statement.py"):
			with self.subTest(controller=controller.name):
				self.assertTrue(whitelisted(read(controller), "confirm_vat_ids"))

	def test_the_form_reacts_only_to_confirmations_of_its_doctype(self):
		self.assertIn("if (data.document_type === frm.doctype) {", read(SHARED_SCRIPT))


class RecordsTest(TestCase):
	def test_the_return_lists_its_confirmations_under_its_connections(self):
		self.assertEqual(
			doctype("vat_return")["links"],
			[{"link_doctype": "VAT ID Confirmation", "link_fieldname": "vat_return"}],
		)
		link = fields("vat_id_confirmation")["vat_return"]
		self.assertEqual((link["fieldtype"], link["options"], link["read_only"]), ("Link", "VAT Return", 1))

	def test_the_lock_is_a_read_only_check_that_neither_copies_nor_prints(self):
		for name in ("vat_return", "recapitulative_statement"):
			with self.subTest(doctype=name):
				lock = fields(name)["confirmation_in_progress"]
				self.assertEqual(
					{
						key: lock.get(key)
						for key in ("fieldtype", "default", "read_only", "no_copy", "print_hide")
					},
					{"fieldtype": "Check", "default": "0", "read_only": 1, "no_copy": 1, "print_hide": 1},
				)


class TranslationsTest(TestCase):
	def test_the_new_fields_read_in_german(self):
		german = translations()
		lock = fields("vat_return")["confirmation_in_progress"]
		age = fields("vat_return_settings")["max_confirmation_age"]
		self.assertEqual(
			[german[text] for text in (lock["label"], lock["description"], age["label"])],
			[
				"Prüfung läuft",
				"Gesetzt, während die USt-IdNrn. geprüft werden; bis zum Ende lässt sich die Meldung nicht ändern.",
				"Höchstalter der USt-IdNr.-Bestätigung (Tage)",
			],
		)
		self.assertTrue(german[age["description"]].startswith("„Berechnen“ gibt einen Hinweis"))
