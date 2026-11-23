"""The tables of the defaults of the annual return in docs/ustva-kennzahlen.md show exactly those of defaults.py."""

import re
from unittest import TestCase

from steuerbote.ustjahr.defaults import annual_rules, defaults_version, role_defaults
from steuerbote.ustjahr.form import catalogue_for
from steuerbote.ustjahr.split import AnnualRule
from steuerbote.ustva.defaults import SKR03, SKR03_RANGES, SKR04, SKR04_RANGES, with_ranges
from steuerbote.ustva.mapping import WatchLevel
from steuerbote.ustva.tests.test_docs import ACCOUNT_CELL, SIDES, section, tables

YEAR = 2026
CHARTS = {"SKR03": (SKR03, SKR03_RANGES), "SKR04": (SKR04, SKR04_RANGES)}
LABEL = "Bezeichnung laut Kontenrahmen 2026"
FIELD_CELL = re.compile(r"(?P<field>E\d{7})(?: \(Kz (?P<kz>\d+)\))?")
WATCHED = "beobachtet"


class AnnualDocTablesTest(TestCase):
	def accounts(self, cell: str, ranges: dict[str, str]) -> tuple[str, ...]:
		"""The accounts of a cell such as "8910 bis 8913"; a range must be the DATEV range of the defaults."""
		match = ACCOUNT_CELL.fullmatch(cell)
		self.assertIsNotNone(match, cell)
		assert match is not None
		self.assertEqual(ranges.get(match["first"]), match["last"], f"{cell}: range of the defaults")
		return with_ranges((match["first"],), ranges)

	def field(self, cell: str, line: str) -> str:
		"""The Feldkennung of a cell such as "E3003405 (Kz 178)", whose Kennzahl and line are those of the form."""
		match = FIELD_CELL.fullmatch(cell)
		self.assertIsNotNone(match, cell)
		assert match is not None
		field = catalogue_for(YEAR).field(match["field"])
		self.assertEqual((match["kz"], line), (field.kennzahl, str(field.line)), cell)
		return field.element

	def charts_of(self, heading: str, header: list[str]) -> list[tuple[str, list[list[str]]]]:
		found = tables(section(heading))
		self.assertEqual([table_header[0] for table_header, _ in found], list(CHARTS))
		for table_header, _ in found:
			self.assertEqual(table_header[1:], header)
		return [(table_header[0], rows) for table_header, rows in found]

	def test_the_line_tables_show_the_field_of_every_role(self):
		for chart, rows in self.charts_of("### Vorgabe der Zeilen", [LABEL, "Kz", "Feld", "Zeile"]):
			mapping, ranges = CHARTS[chart]
			fields = role_defaults(chart, YEAR)
			shown: list[str] = []
			for account_cell, label, kz_cell, field_cell, line in rows:
				field = self.field(field_cell, line)
				accounts = self.accounts(account_cell, ranges)
				with self.subTest(chart=chart, account=accounts[0]):
					self.assertTrue(label)
					rule = mapping.rule_for(accounts[0])
					if kz_cell == WATCHED:
						self.assertIsNone(rule)
						self.assertIn(accounts[0], mapping.watched_at(WatchLevel.BLOCKING))
					else:
						self.assertEqual(rule.kennzahl, kz_cell)
					for account in accounts:
						self.assertEqual(fields[account], field)
				shown.extend(accounts)
			self.assertCountEqual(shown, list(fields), chart)

	def test_the_tables_of_the_accounts_only_the_annual_return_reads_show_every_one(self):
		header = [LABEL, "Feld", "Zeile", "Seite"]
		for chart, rows in self.charts_of("### Konten nur für die Umsatzsteuererklärung", header):
			_mapping, ranges = CHARTS[chart]
			shown: list[AnnualRule] = []
			for account_cell, label, field_cell, line, side in rows:
				self.assertTrue(label, account_cell)
				field = self.field(field_cell, line)
				shown.extend(
					AnnualRule(account, field, SIDES[side]) for account in self.accounts(account_cell, ranges)
				)
			self.assertEqual(tuple(shown), annual_rules(chart, YEAR), chart)

	def test_the_section_names_the_version_of_the_defaults(self):
		text = section("### Vorgaben der Umsatzsteuererklärung")
		for chart in CHARTS:
			with self.subTest(chart=chart):
				self.assertIn(f"„{defaults_version(chart, YEAR)}“", text)
