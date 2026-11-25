"""Every text of the ELSTER transmission has a German translation in translations/de.csv."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.eric import proxy

APP = Path(__file__).resolve().parents[3]
MODULE = APP / "steuerbote"
TRANSLATIONS = APP / "translations" / "de.csv"
DOCTYPES = ("eric_settings", "elster_transmission", "elster_transmission_message")
VAT_RETURN_FIELDS = ("transmission_in_progress",)
SOURCES = (
	MODULE / "doctype/eric_settings/eric_settings.py",
	MODULE / "doctype/eric_settings/eric_settings.js",
	MODULE / "doctype/elster_transmission/elster_transmission.py",
	MODULE / "doctype/elster_transmission/elster_transmission.js",
	MODULE / "doctype/elster_transmission/elster_transmission_list.js",
	MODULE / "doctype/elster_transmission/transmission.py",
	MODULE / "doctype/vat_return/vat_return.py",
	MODULE / "doctype/vat_return/vat_return.js",
	MODULE / "doctype/vat_return/transmission_adapter.py",
	MODULE / "record_files.py",
	APP / "public/js/elster_transmission.js",
)
# German terms and values that read the same in every language.
UNTRANSLATED = frozenset(
	{
		"Datenlieferant",
		"Datenschutzhinweise",
		"Erfolgreich",
		"Fehlgeschlagen",
		"Hersteller-ID",
		"Läuft",
		"Nutzdaten (XML)",
		"Proxy",
		"Testmerker",
		"Transferticket",
		"Unbekannt",
		"UStVA Kennzahlen",
	}
)
# Labels Frappe and ERPNext translate themselves; the app keeps out of their translations.
FRAMEWORK_LABELS = frozenset(
	{
		"Code",
		"Discard",
		"Document",
		"Document Type",
		"Field",
		"Files",
		"Finished At",
		"Kind",
		"Message",
		"Messages",
		"Not permitted",
		"Remarks",
		"Result",
		"Started At",
		"Status",
		"User",
		"View",
	}
)
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")


def translated() -> set[str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return {source for source, *_ in csv.reader(file)}


def doctype(name: str) -> dict:
	return json.loads((MODULE / "doctype" / name / f"{name}.json").read_text(encoding="utf-8"))


def field_texts(fields) -> set[str]:
	texts = set()
	for field in fields:
		texts.update(field[key] for key in ("label", "description") if field.get(key))
		if field["fieldtype"] == "Select":
			texts.update(option for option in field["options"].split("\n") if option)
	return texts


def texts_of_the_transmission() -> set[str]:
	texts = set()
	for name in DOCTYPES:
		definition = doctype(name)
		texts.update(text for text in (definition["name"], definition.get("description")) if text)
		texts.update(field_texts(definition["fields"]))
	texts.update(
		field_texts(
			field for field in doctype("vat_return")["fields"] if field["fieldname"] in VAT_RETURN_FIELDS
		)
	)
	for source in SOURCES:
		texts.update(TRANSLATED_LITERAL.findall(source.read_text(encoding="utf-8")))
	texts.update(proxy.MESSAGES)
	return texts - UNTRANSLATED - FRAMEWORK_LABELS


class TransmissionTranslationsTest(TestCase):
	def test_the_sources_are_read(self):
		texts = texts_of_the_transmission()
		for text in (
			"ERiC Settings",
			"Install Runtime",
			"Mark as Filed Outside",
			"Calculate the return before transmitting it.",
			"A transmission of {0} is running. Wait for its result.",
			"Certificate File (.pfx)",
			"Errors {0}, hints {1}: see the messages below.",
			"Latest run {0}, {1}, {2}: errors {3}, hints {4}.",
			"Proxy URL",
			proxy.NO_PORT,
		):
			with self.subTest(text=text):
				self.assertIn(text, texts)

	def test_every_text_of_the_transmission_is_translated(self):
		self.assertEqual(sorted(texts_of_the_transmission() - translated()), [])

	def test_the_framework_labels_are_left_to_the_framework(self):
		self.assertEqual(sorted(FRAMEWORK_LABELS & translated()), [])


class SimulationNoteTest(TestCase):
	"""The note of the simulation in ERiC Settings is one long sentence. Frappe lays the close button of a message over
	the end of its text (.close-message in frappe/public/scss/desk/form.scss), so the note is a permanent message, without
	that button, which wraps over the whole width of the form."""

	def test_the_note_is_a_permanent_message(self):
		script = (MODULE / "doctype/eric_settings/eric_settings.js").read_text(encoding="utf-8")
		self.assertNotIn("frm.set_intro(", script)
		call = re.search(r"frm\.\$simulation_note = frm\.dashboard\.set_headline_alert\((.*?)\);\n", script, re.S)
		self.assertIsNotNone(call)
		self.assertRegex(call.group(1), r'"orange",\s*true\s*$')
