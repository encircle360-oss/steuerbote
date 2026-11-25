"""Kz 500 in the files of the VAT Return, the VAT Return Extension and the Annual VAT Return, read without a bench:
the select field offers keys that read as the form, in English and through de.csv in the wording of the Vordruck.

Sources: line 55 of USt 1 A 2026 and line 12 of USt 1 H 2026 (BMF-Schreiben „Muster der Vordrucke im
Umsatzsteuer-Voranmeldungs- und -Vorauszahlungsverfahren für das Kalenderjahr 2026“ of 29 December 2025), line 23 of
USt 2 A 2026 (BMF-Schreiben „Muster der Umsatzsteuererklärung 2026“ of 29 December 2025)."""

import csv
import json
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[1]
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSLATIONS = APP / "translations" / "de.csv"

STEUERANMELDUNG = {
	"1 = Facts relevant to the tax could not be explained.": (
		"1 = konnten steuererhebliche Sachverhalte nicht erklärt werden."
	),
	"2 = A legal view deliberately deviating from the view of the administration is taken.": (
		"2 = wird bewusst eine von der Verwaltungsauffassung abweichende Rechtsauffassung vertreten."
	),
	"3 = Facts are to be examined in depth by a person.": "3 = sollen Sachverhalte personell vertieft geprüft werden.",
	"4 = Several of the reasons above apply (multiple choice).": (
		"4 = liegen mehrere der vorgenannten Gründe vor (Mehrfachauswahl)."
	),
}
STEUERERKLAERUNG = {
	**STEUERANMELDUNG,
	"2 = A legal view deliberately deviating from the opinion of the administration is taken.": (
		"2 = wird bewusst eine von der Verwaltungsmeinung abweichende Rechtsauffassung vertreten."
	),
}
del STEUERERKLAERUNG["2 = A legal view deliberately deviating from the view of the administration is taken."]
FIELDS = {
	("vat_return", "supplementary_code"): STEUERANMELDUNG,
	("vat_return_extension", "supplementary_code"): STEUERANMELDUNG,
	("annual_vat_return", "kz500"): STEUERERKLAERUNG,
}


def options(doctype: str, fieldname: str) -> list[str]:
	meta = json.loads((DOCTYPES / doctype / f"{doctype}.json").read_text(encoding="utf-8"))
	(field,) = (field for field in meta["fields"] if field["fieldname"] == fieldname)
	return field["options"].split("\n")


class TestKz500Files(TestCase):
	def setUp(self):
		with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
			self.german = {row[0]: row[1] for row in csv.reader(file) if row}

	def test_the_select_fields_offer_the_keys_in_the_order_of_the_form(self):
		for (doctype, fieldname), keys in FIELDS.items():
			with self.subTest(doctype=doctype):
				self.assertEqual(options(doctype, fieldname), ["", *sorted(keys)])

	def test_each_key_reads_in_german_as_the_line_of_the_vordruck(self):
		for (doctype, _fieldname), keys in FIELDS.items():
			for key, wording in keys.items():
				with self.subTest(doctype=doctype, key=key):
					self.assertEqual(self.german.get(key), wording)
