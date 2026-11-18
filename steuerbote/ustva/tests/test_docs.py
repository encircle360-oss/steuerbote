"""The mapping tables of docs/ustva-kennzahlen.md show exactly the defaults of defaults.py."""

import re
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from steuerbote.ustva.defaults import (
	SKR03,
	SKR03_IGNORED,
	SKR03_RANGES,
	SKR04,
	SKR04_IGNORED,
	SKR04_RANGES,
	with_ranges,
)
from steuerbote.ustva.mapping import AccountRule, Mapping, Side

DOC = Path(__file__).resolve().parents[3] / "docs" / "ustva-kennzahlen.md"
SIDES = {"Haben": Side.CREDIT, "Soll": Side.DEBIT}
CHARTS: dict[str, tuple[Mapping, tuple[str, ...], dict[str, str]]] = {
	"SKR03": (SKR03, SKR03_IGNORED, SKR03_RANGES),
	"SKR04": (SKR04, SKR04_IGNORED, SKR04_RANGES),
}
KZ_CELL = re.compile(
	r"(?P<kz>\d+)(?:, Steuer (?P<rate>\d+(?:,\d+)?) % in Kz (?P<tax>\d+))?(?:, zusätzlich Kz (?P<also>\d+))?"
)
ACCOUNT_CELL = re.compile(r"(?P<first>\d{4})(?: bis (?P<last>\d{4}))?")


def section(heading: str) -> str:
	text = DOC.read_text(encoding="utf-8")
	start = text.index(f"\n{heading}\n") + len(heading) + 2
	following = re.search(r"\n#{2,3} ", text[start:])
	return text[start : start + following.start()] if following else text[start:]


def tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
	"""Header and rows of each Markdown table in the text."""
	found: list[list[list[str]]] = []
	in_table = False
	for line in text.splitlines():
		if line.startswith("|"):
			cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
			if in_table:
				found[-1].append(cells)
			else:
				found.append([cells])
			in_table = True
		else:
			in_table = False
	return [(table[0], table[2:]) for table in found]


class DocTablesTest(TestCase):
	def accounts(self, cell: str, ranges: dict[str, str]) -> tuple[str, ...]:
		"""The accounts of a cell such as "8400 bis 8409"; a range must be the DATEV range of the defaults."""
		match = ACCOUNT_CELL.fullmatch(cell)
		self.assertIsNotNone(match, cell)
		assert match is not None
		first, last = match["first"], match["last"]
		self.assertEqual(ranges.get(first), last, f"{cell}: range of the defaults")
		return with_ranges((first,), ranges)

	def account_list(self, cell: str, ranges: dict[str, str]) -> tuple[str, ...]:
		return tuple(account for part in cell.split(", ") for account in self.accounts(part, ranges))

	def test_rule_tables_show_every_rule(self):
		for chart, (mapping, _, ranges) in CHARTS.items():
			((header, rows),) = tables(section(f"### Vorgabe {chart}"))
			self.assertEqual(header, ["Konto", "Bezeichnung laut Kontenrahmen 2026", "Kz", "Seite"])
			shown: list[str] = []
			for account_cell, _, kz_cell, side_cell in rows:
				match = KZ_CELL.fullmatch(kz_cell)
				self.assertIsNotNone(match, kz_cell)
				assert match is not None
				rate = Decimal(match["rate"].replace(",", ".")) if match["rate"] else None
				for account in self.accounts(account_cell, ranges):
					with self.subTest(chart=chart, account=account):
						# "zusätzlich Kz 50" reports the debit balance, the reduction of the base
						also_side = Side.DEBIT if match["also"] else None
						expected = AccountRule(
							account, match["kz"], SIDES[side_cell], rate, match["also"], also_side
						)
						self.assertEqual(mapping.rule_for(account), expected)
						if rate is not None:
							self.assertEqual(match["tax"], mapping.catalogue[match["kz"]].tax_kennzahl)
					shown.append(account)
			self.assertCountEqual(shown, [rule.account_number for rule in mapping.rules], chart)

	def test_check_table_shows_every_check(self):
		((header, rows),) = tables(section("### Verprobungen"))
		self.assertEqual(
			header[:4], ["Verprobung", "Grundlagen SKR03", "Grundlagen SKR04", "Steuerkonto SKR03 / SKR04"]
		)
		self.assertEqual(len(rows), len(SKR03.checks))
		for row, skr03, skr04 in zip(rows, SKR03.checks, SKR04.checks, strict=True):
			label, bases03, bases04, taxes = row[:4]
			with self.subTest(check=label):
				self.assertEqual(label, skr03.label)
				self.assertEqual(label, skr04.label)
				self.assertEqual(self.account_list(bases03, SKR03_RANGES), skr03.base_accounts)
				self.assertEqual(self.account_list(bases04, SKR04_RANGES), skr04.base_accounts)
				tax03, tax04 = taxes.split(" / ")
				self.assertEqual(self.account_list(tax03, SKR03_RANGES), skr03.tax_accounts)
				self.assertEqual(self.account_list(tax04, SKR04_RANGES), skr04.tax_accounts)

	def test_watched_tables_show_every_watched_account(self):
		found = tables(section("### Beobachtete Konten"))
		self.assertEqual([header[0] for header, _ in found], list(CHARTS))
		for (_, rows), (chart, (mapping, _, ranges)) in zip(found, CHARTS.items(), strict=True):
			shown = tuple(account for row in rows for account in self.accounts(row[0], ranges))
			self.assertEqual(shown, mapping.watched, chart)

	def test_ignored_tables_show_every_ignored_account_with_a_reason(self):
		found = tables(section("### Bewusst ohne Kennzahl"))
		self.assertEqual([header[0] for header, _ in found], list(CHARTS))
		for (header, rows), (chart, (_, ignored, ranges)) in zip(found, CHARTS.items(), strict=True):
			self.assertEqual(header[2], "Grund", chart)
			shown = tuple(account for row in rows for account in self.accounts(row[0], ranges))
			self.assertEqual(shown, with_ranges(ignored, ranges), chart)
			for row in rows:
				self.assertTrue(row[2], f"{chart} {row[0]}: reason")
