"""The ELSTER Transmission takes the annual documents, read from its files without a bench."""

import ast
import csv
import json
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[3]
DIRECTORY = APP / "steuerbote" / "doctype" / "elster_transmission"
TRANSLATIONS = APP / "translations" / "de.csv"
# The DocTypes of the annual filings that go to ELSTER through ERiC, named before their modules bring them (contract
# of stage 3, 2.2).
ANNUAL_DOCUMENTS = (
	"Annual VAT Return",
	"Electronic Balance Sheet",
	"Corporate Income Tax Return",
	"Trade Tax Return",
)


def document_types() -> tuple[str, ...]:
	module = ast.parse((DIRECTORY / "elster_transmission.py").read_text(encoding="utf-8"))
	(value,) = (
		node.value
		for node in module.body
		if isinstance(node, ast.Assign) and [target.id for target in node.targets] == ["DOCUMENT_TYPES"]
	)
	return ast.literal_eval(value)


class AnnualTransmissionFilesTest(TestCase):
	def setUp(self):
		self.definition = json.loads((DIRECTORY / "elster_transmission.json").read_text(encoding="utf-8"))
		self.fields = {field["fieldname"]: field for field in self.definition["fields"]}

	def test_takes_the_annual_documents_after_the_three_of_before(self):
		self.assertEqual(
			document_types(),
			("VAT Return", "VAT Return Extension", "Recapitulative Statement", *ANNUAL_DOCUMENTS),
		)

	def test_keeps_the_protocol_or_the_freizeichnungsdokument_of_a_run(self):
		"""After an accepted send-Auth ERiC prints a Freizeichnungsdokument for an Erklärung and an
		Übertragungsprotokoll for the other Datenarten (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.1.4.3 and 5.1.4.4)."""
		label = self.fields["protocol_pdf"]["label"]
		self.assertEqual(label, "Protocol or Freizeichnungsdokument (PDF)")
		with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
			self.assertEqual(dict(csv.reader(file))[label], "Protokoll oder Freizeichnungsdokument (PDF)")

	def test_names_the_annual_documents_it_records(self):
		self.assertIn("Erklärung", self.definition["description"])
		self.assertIn("E-Bilanz", self.definition["description"])

	def test_a_frappe_migrate_takes_the_new_definition(self):
		"""bench migrate syncs a DocType whose file is newer than what the site holds."""
		self.assertGreaterEqual(self.definition["modified"], "2026-11-23")
