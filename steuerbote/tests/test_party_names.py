"""Every place that shows a customer or supplier to a person names it with its name and its ID, read from the files
without a bench: ERPNext names partners by a number of a naming series as well as by their names, so neither the ID
nor the name alone tells a bookkeeper who is meant (R3-F-01). steuerbote.vatid.partners.party_label makes the text;
the readers of the site and the bridges pass ID and name to it instead of falling back from the one to the other."""

import re
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[1]
# A name that falls back to the ID, or the ID to the name: the text then reads as a bare number for a partner named
# by a naming series.
FALLBACK = re.compile(
	r"(customer_name|supplier_name|party_name)\W{0,3}\s+or\s+\w+\W{0,3}(customer|supplier|party|name)\b"
)


def sources() -> list[Path]:
	return sorted(
		path
		for path in APP.rglob("*.py")
		if "tests" not in path.parts and not path.name.startswith("test_") and "patches" not in path.parts
	)


class PartyNamesTest(TestCase):
	def test_no_reader_falls_back_from_the_name_of_a_partner_to_its_id(self):
		found = [
			f"{path.relative_to(APP)}:{number}"
			for path in sources()
			for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
			if FALLBACK.search(line)
		]
		self.assertEqual(found, [])

	def test_the_readers_of_partners_name_them_with_the_label(self):
		for name in (
			"invoices.py",
			"suppliers.py",
			"steuerbote/partner_vat_ids.py",
			"steuerbote/report/ustva_kennzahlen/ustva_kennzahlen.py",
			"steuerbote/doctype/recapitulative_statement/bridge.py",
			"steuerbote/doctype/recapitulative_statement/recapitulative_statement.py",
			"steuerbote/doctype/vat_id_confirmation/confirming.py",
		):
			with self.subTest(module=name):
				self.assertIn("party_label(", (APP / name).read_text(encoding="utf-8"))
