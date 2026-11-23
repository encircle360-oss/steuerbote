"""The catalogue of form USt 2 A against the ERiC documentation 44.3.6.0; skipped without it, see jahresdokumentation.py.

The documentation holds Jahresdokumentation_E50_2026.ods, cited as JD, and the schema E50-2026.xsd. The catalogue
is data in steuerbote/ustjahr/form.py; these tests compare each fact with the file it comes from.
"""

import re
from unittest import TestCase

from steuerbote.ustjahr.form import CATALOGUES, Format
from steuerbote.ustjahr.tests import jahresdokumentation as jd
from steuerbote.ustva.documentation import Row

CATALOGUE = CATALOGUES[2026]
YEAR = 2026
# The JD gives the Mitwirkung the lines 23 and 123; the form prints it in lines 127 to 129 (form.py).
MITWIRKUNG = "Mitwirk/"
JD_LINES_OF_THE_MITWIRKUNG = {"E3002602": "123"}
JD_LINE_OF_THE_MITWIRKUNG = "23"
LAST_BUYER_TAXES = ("E3101702", "E3102302")

_SUM = re.compile(r"\[(E\d{7})\]!=Summe\(([E\d,]+)\)")
# Differences such as [E3010201]!=[E3009801]-[E3009901]-[E3010001], and lines brought forward: [E3009201]!=[E3006001].
_DIFFERENCE = re.compile(r"\[(E\d{7})\](?:!=|UngleichMitToleranz10)((?:\[E\d{7}\]-?)+)$")
_TOGETHER = re.compile(r"FelderNichtGemeinsamAngegeben\((E\d{7}),(E\d{7})\)$")
_RATE = re.compile(r"\[(E\d{7})\]UngleichMitToleranz1\{0\.(\d\d)\*\[(E\d{7})\]\}$")


def condition(row: Row) -> str:
	return re.sub(r"\s+", "", row["Prüfbedingung"])


class FieldsTest(TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.rows = {row["Name"]: row for row in jd.fields(YEAR)}

	def test_the_fields_are_those_of_the_jd_in_its_order(self):
		self.assertEqual([field.element for field in CATALOGUE.fields], list(self.rows))

	def test_each_field_has_the_context_format_and_label_of_the_jd(self):
		for field in CATALOGUE.fields:
			row = self.rows[field.element]
			with self.subTest(element=field.element):
				self.assertEqual(field.context, row["Kontext"])
				self.assertEqual(field.format.value, row["Formatkennzeichen"])
				self.assertEqual(field.label, " ".join(row["Beschreibung"].split()))
				self.assertEqual(field.mandatory, row["Pflichtfeld"] == "Ja")
				if field.format is Format.TEXT:
					self.assertEqual(str(field.length), row["Max. Länge"])

	def test_each_field_has_the_line_of_the_jd_but_the_mitwirkung(self):
		for field in CATALOGUE.fields:
			row = self.rows[field.element]
			with self.subTest(element=field.element):
				if field.context.startswith(MITWIRKUNG):
					expected = JD_LINES_OF_THE_MITWIRKUNG.get(field.element, JD_LINE_OF_THE_MITWIRKUNG)
					self.assertEqual(row["Vordruckzeile"], expected)
				else:
					self.assertEqual(row["Vordruckzeile"], str(field.line))

	def test_the_grundstuecke_repeat_as_often_as_the_jd_allows(self):
		for field in CATALOGUE.fields:
			with self.subTest(element=field.element):
				self.assertEqual(self.rows[field.element]["max. Zeilen"], "1")
		contexts = {row["Kontext"]: row for row in jd.sheet(YEAR, "USt2A - Kontexte")}
		repeated = {field.context: field.repeat for field in CATALOGUE.fields if field.repeat != 1}
		for context, repeat in repeated.items():
			self.assertEqual(contexts[f"/USt2A/{context}"]["max. Wiederholbarkeit"], str(repeat))
		self.assertEqual(
			{row["Kontext"] for row in contexts.values() if row["max. Wiederholbarkeit"] != "1"},
			{f"/USt2A/{context}" for context in repeated},
		)

	def test_the_kennzahlen_are_those_of_the_sheet_kennzahlen(self):
		documented = {row["Feldname"]: row["Kennzahl"] for row in jd.sheet(YEAR, jd.KENNZAHLEN)}
		ours = {
			f"{field.context}/{field.element}": field.kennzahl for field in CATALOGUE.fields if field.kennzahl
		}
		self.assertEqual(ours, documented)

	def test_the_fields_are_the_leaves_of_ust2a_in_the_schema(self):
		self.assertEqual(tuple((field.context, field.element) for field in CATALOGUE.fields), jd.leaves(YEAR))


class RulesTest(TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.rules = jd.sheet(YEAR, jd.RULES)

	def test_the_rules_are_those_of_the_jd_in_its_order(self):
		self.assertEqual(
			[(rule.code, rule.name, rule.context, rule.severity.value) for rule in CATALOGUE.rules],
			[(row["Fehlercode"], row["Name"], row["Kontext"], row["Regelart"]) for row in self.rules],
		)

	def test_the_sums_are_those_the_rules_check(self):
		elements = {field.element for field in CATALOGUE.fields}
		documented: dict[str, tuple[tuple[str, int], ...]] = {}
		for row in self.rules:
			text = condition(row)
			if match := _SUM.search(text):
				parts = tuple((element, 1) for element in match[2].split(","))
			elif match := _DIFFERENCE.search(text):
				first, *rest = re.findall(r"E\d{7}", match[2])
				parts = ((first, 1), *((element, -1) for element in rest))
			else:
				continue
			# Line 123 takes its amount from Anlage UN, which the catalogue does not hold.
			if {match[1], *(element for element, _ in parts)} <= elements:
				documented[match[1]] = parts
		self.assertEqual(
			{field.element: field.parts for field in CATALOGUE.fields if field.parts}, documented
		)

	def test_the_pairs_of_base_and_tax_are_those_the_rules_file_together(self):
		documented = set()
		for row in self.rules:
			if match := _TOGETHER.search(condition(row)):
				first, second = (CATALOGUE.field(element) for element in (match[1], match[2]))
				if first.format.whole_euros and second.format.amount and not second.format.whole_euros:
					documented.add((first.element, second.element))
		ours = {(field.element, field.tax) for field in CATALOGUE.fields if field.tax is not None}
		self.assertEqual(ours, documented)

	def test_the_rate_lines_are_those_the_rules_check_within_one_euro(self):
		"""ERiC checks the taxes of the last buyer in a Dreiecksgeschäft against the rate too (30660, 30661), but
		they are the taxes the Voranmeldung reported in Kz 69, not a tax the form derives."""
		documented = {}
		for row in self.rules:
			if match := _RATE.search(condition(row)):
				documented[match[1]] = (str(int(match[2])), match[3])
		ours = {
			field.element: (str(field.rate), field.base)
			for field in CATALOGUE.fields
			if field.rate is not None
		}
		booked = {element: documented.pop(element) for element in LAST_BUYER_TAXES}
		self.assertEqual(ours, documented)
		for element, (_rate, base) in booked.items():
			with self.subTest(element=element):
				self.assertEqual(
					(CATALOGUE.field(element).base, CATALOGUE.field(element).ustva), (base, "69")
				)
