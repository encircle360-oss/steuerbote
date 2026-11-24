"""The tables of the periodic and the annual documents as the form shows them, read from the files without a bench:
every amount up to 99.999.999,99 € fits into its column at a desk 1440 pixels wide.

Frappe 16 gives a column of the grid the width that its `columns` names (frappe/public/js/frappe/form/grid.js,
LEGACY_COLSIZE_TO_PX: 1 is 60 px, 2 is 100 px, 3 is 140 px, 4 is 200 px) and shares what the grid has left equally
among its columns. At 1440 pixels the grid of a form with its sidebar has about 700 pixels for its columns: with at
most ten units, an amount of two units keeps about 130 pixels while the grid shows at most six columns, enough for
the amount with its euro sign. Each further column takes its share from every amount.
"""

import json
from pathlib import Path
from unittest import TestCase

MODULE = Path(__file__).resolve().parents[1] / "steuerbote"
DOCTYPES = MODULE / "doctype"
DOCUMENTS = (
	"recapitulative_statement",
	"vat_return",
	"vat_return_extension",
	"annual_accounts",
	"annual_vat_return",
	"corporate_income_tax_return",
	"electronic_balance_sheet",
	"trade_tax_return",
)
UNITS = 10
LEAST_UNITS_OF_AN_AMOUNT = 2
MOST_COLUMNS = 6


def definition(name: str) -> dict:
	return json.loads((DOCTYPES / name / f"{name}.json").read_text(encoding="utf-8"))


def file_name(doctype: str) -> str:
	return doctype.lower().replace(" ", "_")


def children() -> list[str]:
	"""The child DocTypes of the tables of the documents, each once."""
	names = {
		file_name(field["options"])
		for parent in DOCUMENTS
		for field in definition(parent)["fields"]
		if field["fieldtype"] == "Table"
	}
	return sorted(names)


def listed(name: str) -> list[dict]:
	return [field for field in definition(name)["fields"] if field.get("in_list_view")]


class TestGrids(TestCase):
	def test_the_documents_have_their_tables(self):
		self.assertIn("vat_return_kennzahl", children())
		self.assertIn("recapitulative_statement_line", children())
		self.assertIn("electronic_balance_sheet_position", children())
		self.assertIn("annual_accounts_line", children())
		self.assertIn("corporate_income_tax_return_donation", children())

	def test_every_column_of_a_grid_names_its_width(self):
		for name in children():
			for field in listed(name):
				with self.subTest(doctype=name, field=field["fieldname"]):
					self.assertGreaterEqual(field.get("columns", 0), 1)

	def test_a_grid_takes_at_most_ten_units(self):
		for name in children():
			with self.subTest(doctype=name):
				self.assertLessEqual(sum(field.get("columns", 0) for field in listed(name)), UNITS)

	def test_an_amount_in_a_grid_takes_at_least_two_units(self):
		for name in children():
			for field in listed(name):
				if field["fieldtype"] == "Currency":
					with self.subTest(doctype=name, field=field["fieldname"]):
						self.assertGreaterEqual(field.get("columns", 0), LEAST_UNITS_OF_AN_AMOUNT)

	def test_a_grid_shows_at_most_six_columns(self):
		for name in children():
			with self.subTest(doctype=name):
				self.assertLessEqual(len(listed(name)), MOST_COLUMNS)
