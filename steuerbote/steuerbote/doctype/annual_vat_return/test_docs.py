"""docs/umsatzsteuererklaerung.md describes the Annual VAT Return as its files and the core hold it, read without a
bench."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.steuerbote.doctype.annual_vat_return import bridge, revenue
from steuerbote.ustjahr import years

APP = Path(__file__).resolve().parents[3]
DOCS = APP.parent / "docs"
PAGE = DOCS / "umsatzsteuererklaerung.md"
ARCHITECTURE = DOCS / "architektur.md"
DIRECTORY = Path(__file__).resolve().parent
CORE = APP / "ustjahr"
TRANSLATIONS = APP / "translations" / "de.csv"
LAYOUT_FIELDS = frozenset({"Section Break", "Column Break"})
FINDING_CODE = re.compile(r'Finding\(\s*"([A-Z0-9-]+)"')
# The codes of the own checks of rules.check(), which it names in a table.
OWN_CHECKS = ("VOLLE-EURO", "VORZEICHEN", "STELLEN", "LAENGE", "PARAGRAF-FEHLT")


def documented(text: str) -> set[str]:
	"""The names a page writes as code outside its code blocks."""
	prose = re.sub(r"^```.*?^```$", "", text, flags=re.DOTALL | re.MULTILINE)
	return set(re.findall(r"`([^`]+)`", prose))


def codes_of(path: Path) -> set[str]:
	return set(FINDING_CODE.findall(path.read_text(encoding="utf-8")))


class PageTest(TestCase):
	def setUp(self):
		self.text = PAGE.read_text(encoding="utf-8")
		self.names = documented(self.text)

	def test_names_every_field_of_the_return(self):
		definition = json.loads((DIRECTORY / "annual_vat_return.json").read_text(encoding="utf-8"))
		fields = {
			field["fieldname"]
			for field in definition["fields"]
			if field["fieldtype"] not in LAYOUT_FIELDS
			and field["fieldname"] not in ("naming_series", "amended_from")
		}
		sums = {name for name in bridge.SUM_FIELDS if name.startswith("line_")}
		self.assertEqual(sorted(fields - self.names - sums), [])
		self.assertIn("`line_41` bis `line_122`", self.text)

	def test_names_every_code_a_finding_of_the_return_takes(self):
		codes = codes_of(DIRECTORY / "bridge.py")
		for module in ("soll.py", "reconciliation.py"):
			codes |= codes_of(CORE / module)
		codes |= {"NACHSTEUER-ZEILE", "SB-NEU-BERECHNEN", revenue.CODE, *OWN_CHECKS}
		self.assertIn("SB-VERPROBUNG", codes)
		self.assertIn("ZEITRAUM-FEHLT", codes)
		self.assertEqual(sorted(codes - self.names), [])

	def test_names_the_deadlines_of_2026(self):
		for advisor in (False, True):
			with self.subTest(advisor=advisor):
				self.assertIn(f"{years.filing_deadline(2026, advisor):%d.%m.%Y}", self.text)

	def test_names_the_accounts_of_the_payments_of_each_chart(self):
		for accounts in bridge.PAYMENT_ACCOUNTS.values():
			for account in accounts:
				with self.subTest(account=account):
					self.assertIn(account, self.text)

	def test_names_each_cause_of_a_period_as_the_form_shows_it(self):
		with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
			german = dict(csv.reader(file))
		rows = set(re.findall(r"^\| ([^|]+) \| [^|]+ \|$", self.text, re.MULTILINE))
		self.assertEqual(sorted({german[cause] for cause in bridge.CAUSES.values()} - rows), [])

	def test_says_that_mein_elster_imports_no_umsatzsteuererklaerung(self):
		self.assertIn("Mein ELSTER importiert keine Umsatzsteuererklärung", self.text)

	def test_the_architecture_names_the_module_and_links_its_page(self):
		text = ARCHITECTURE.read_text(encoding="utf-8")
		self.assertIn("| `annual_vat_return/` mit `steuerbote/ustjahr_sources.py` |", text)
		self.assertIn("](umsatzsteuererklaerung.md)", text)
