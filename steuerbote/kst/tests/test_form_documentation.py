"""The Vordrucke of the Körperschaftsteuer against the ERiC documentation 44.3.6.0; skipped without it, see
jahresdokumentation.py.

Each VZ is compared with the Jahresdokumentation E30 of its documentation year, 2025 for the provisional 2026: the
Vordrucke of the sheet „Allg. Information“, the fields of the sheets „<Vordruck> - Felder“ and „<Vordruck> -
Kennzahlen“ with the leaves of E30-2025.xsd, the rules Steuerbote checks with the sheets „<Vordruck> - Regeln“ and the
Rechtsformen with the sheet „Benutzerdefinierte Typen“. The labels of the fields are the Drucktext of the printed form.
"""

import re
from unittest import TestCase

from steuerbote.kst.form import CATALOGUES, FORMS, INDEXED, RECHTSFORMEN, WJ
from steuerbote.kst.tests import jahresdokumentation as jd
from steuerbote.kst.years import YEARS

CURRENT = (jd.KST,)
FORM_LINE = re.compile(
	r"(?P<form>\w+) - max\. lfd\. Nr\. Vordruck: (?P<count>\d+)(?P<mandatory> - Pflichtvordruck)?"
)
CATEGORY = re.compile(r"- (?P<code>\d+) \[[^\]]*\] (?P<categories>.*)")
PAIR = re.compile(r"(\w+): (\w+)")


def documented_years():
	for year in YEARS.values():
		yield year.year, year.documentation_year


def fields(year: int, form: str) -> list:
	return [row for row in jd.sheet(jd.KST, year, f"{form} - Felder") if row["Indexfeld"] != "Ja"]


class FormsTest(TestCase):
	def test_the_vordrucke_are_those_of_allg_information(self):
		for vz, year in documented_years():
			with self.subTest(vz=vz):
				documented = {
					match["form"]: (int(match["count"]), bool(match["mandatory"]))
					for line in jd.lines(jd.KST, year, "Allg. Information")
					if (match := FORM_LINE.fullmatch(line.strip()))
				}
				self.assertEqual(
					{form.name: (form.count, form.mandatory) for form in FORMS},
					{form.name: documented[form.name] for form in FORMS},
				)

	def test_the_vordrucke_follow_the_order_of_the_schema(self):
		for vz, year in documented_years():
			with self.subTest(vz=vz):
				order = jd.form_order(jd.KST, year)
				self.assertEqual(
					[form.name for form in FORMS], [name for name in order if name in {f.name for f in FORMS}]
				)

	def test_anlage_gk_and_kst_1_f_carry_the_indexfeld_wj(self):
		for vz, year in documented_years():
			with self.subTest(vz=vz):
				indexed = {
					form.name: row
					for form in FORMS[:-1]
					for row in jd.sheet(jd.KST, year, f"{form.name} - Felder")
					if row["Indexfeld"] == "Ja"
				}
				self.assertEqual(set(indexed), INDEXED)
				for row in indexed.values():
					self.assertEqual(
						(row["Name"], row["Format als regulärer Ausdruck"]), ("WJ", r"\QWJ1\E|\QWJ2\E")
					)
				self.assertEqual(WJ, ("WJ1", "WJ2"))


class FieldsTest(TestCase):
	def test_each_field_is_that_of_the_jahresdokumentation_in_its_order(self):
		for vz, year in documented_years():
			catalogue = CATALOGUES[vz]
			for form in FORMS[:-1]:
				with self.subTest(vz=vz, form=form.name):
					kennzahlen = {
						row["Feldname"]: f"{row['Sachbereich']}.{row['Kennzahl']}"
						for row in jd.sheet(jd.KST, year, f"{form.name} - Kennzahlen")
					}
					documented = [
						(
							row["Kontext"],
							row["Name"],
							row["Vordruckzeile"] or None,
							row["Formatkennzeichen"],
							int(row["Max. Länge"]) if row["Formatkennzeichen"] == "C" else None,
							row["Pflichtfeld"] == "Ja",
							kennzahlen.get(
								f"{row['Kontext']}/{row['Name']}" if row["Kontext"] else row["Name"]
							),
							row["Format als regulärer Ausdruck"],
							" ".join(row["Beschreibung"].split()),
						)
						for row in fields(year, form.name)
					]
					ours = [
						(
							field.context,
							field.feldkennung,
							field.line,
							field.format,
							field.length,
							field.required,
							field.kennzahl,
							field.pattern,
							field.label,
						)
						for field in catalogue.fields
						if field.form == form.name
					]
					self.assertEqual(ours, documented)

	def test_the_beschreibung_of_each_field_is_its_drucktext(self):
		for vz, year in documented_years():
			for form in FORMS[:-1]:
				with self.subTest(vz=vz, form=form.name):
					for row in fields(year, form.name):
						self.assertEqual(
							" ".join(row["Beschreibung"].split()), " ".join(row["Drucktext"].split())
						)

	def test_the_fields_are_the_leaves_of_each_vordruck_in_the_schema(self):
		for vz, year in documented_years():
			catalogue = CATALOGUES[vz]
			for form in FORMS[:-1]:
				with self.subTest(vz=vz, form=form.name):
					leaves = tuple(leaf for leaf in jd.leaves(jd.KST, year, form.name) if leaf[1] != "WJ")
					self.assertEqual(
						tuple((f.context, f.feldkennung) for f in catalogue.fields if f.form == form.name),
						leaves,
					)


class RulesTest(TestCase):
	def test_each_rule_is_that_of_the_jahresdokumentation(self):
		for vz, year in documented_years():
			documented = {
				row["Fehlercode"]: row
				for form in FORMS[:-1]
				for row in jd.sheet(jd.KST, year, f"{form.name} - Regeln")
			}
			for rule in CATALOGUES[vz].rules:
				with self.subTest(vz=vz, code=rule.code):
					row = documented[rule.code]
					self.assertEqual(rule.name, row["Name"])
					self.assertEqual(
						rule.fields,
						tuple(part.strip() for part in " ".join(row["Geprüfte Felder"].split()).split(",")),
					)
					self.assertEqual(rule.hint, row["Regelart"] == "Hinweis")


class RechtsformenTest(TestCase):
	def test_the_categories_are_those_of_rechtsform_koerperschaften_v3(self):
		for vz, year in documented_years():
			with self.subTest(vz=vz):
				(row,) = (
					row
					for row in jd.sheet(jd.KST, year, "Benutzerdefinierte Typen")
					if row["Name"] == "RECHTSFORM_KOERPERSCHAFTEN_V3" and row["Version"] == "3"
				)
				documented = {
					match["code"]: dict(PAIR.findall(match["categories"]))
					for line in row["Format"].split("\n")
					if (match := CATEGORY.match(line.strip()))
				}
				for code, categories in RECHTSFORMEN[vz].items():
					self.assertEqual(dict(categories), documented[code])
