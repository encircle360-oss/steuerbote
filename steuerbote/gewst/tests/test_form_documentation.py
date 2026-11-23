"""The Vordrucke of the Gewerbesteuer against the ERiC documentation 44.3.6.0; skipped without it, see
steuerbote/kst/tests/jahresdokumentation.py.

Each EZ is compared with the Jahresdokumentation E20 of its documentation year, 2025 for the provisional 2026: the
Vordrucke of the sheet „Allg. Information“, the fields of the sheets „GewSt1A - Felder“, „BEG - Felder“ and „GewSt1A -
Kennzahlen“ with the leaves of E20-2025.xsd, the rules Steuerbote checks and the Rechtsformen. The labels of the
fields are the Drucktext of the printed form.
"""

import re
from unittest import TestCase

from steuerbote.gewst.form import CATALOGUES, FORMS, RECHTSFORMEN
from steuerbote.gewst.years import YEARS
from steuerbote.kst.tests import jahresdokumentation as jd

FORM_LINE = re.compile(
	r"(?P<form>\w+) - max\. lfd\. Nr\. Vordruck: (?P<count>\d+)(?P<mandatory> - Pflichtvordruck)?"
)
CATEGORY = re.compile(r"- (?P<code>\d+) \[[^\]]*\] (?P<categories>.*)")
PAIR = re.compile(r"(\w+): (\w+)")
VORDRUCKE = tuple(form.name for form in FORMS if form.name != "Vorsatz")


def documented_years():
	for year in YEARS.values():
		yield year.year, year.documentation_year


class FormsTest(TestCase):
	def test_the_vordrucke_are_those_of_allg_information_in_the_order_of_the_schema(self):
		for ez, year in documented_years():
			with self.subTest(ez=ez):
				documented = {
					match["form"]: (int(match["count"]), bool(match["mandatory"]))
					for line in jd.lines(jd.GEWST, year, "Allg. Information")
					if (match := FORM_LINE.fullmatch(line.strip()))
				}
				self.assertEqual(
					{form.name: (form.count, form.mandatory) for form in FORMS},
					{form.name: documented[form.name] for form in FORMS},
				)
				order = jd.form_order(jd.GEWST, year)
				names = {form.name for form in FORMS}
				self.assertEqual([form.name for form in FORMS], [name for name in order if name in names])


class FieldsTest(TestCase):
	def test_each_field_is_that_of_the_jahresdokumentation_in_its_order(self):
		for ez, year in documented_years():
			catalogue = CATALOGUES[ez]
			kennzahlen = {
				f"GewSt1A/{row['Feldname']}": f"{row['Sachbereich']}.{row['Kennzahl']}"
				for row in jd.sheet(jd.GEWST, year, "GewSt1A - Kennzahlen")
			}
			for form in VORDRUCKE:
				with self.subTest(ez=ez, form=form):
					documented = [
						(
							row["Kontext"],
							row["Name"],
							row["Vordruckzeile"] or None,
							row["Formatkennzeichen"],
							int(row["Max. Länge"]) if row["Formatkennzeichen"] == "C" else None,
							row["Pflichtfeld"] == "Ja",
							kennzahlen.get(f"{form}/{row['Kontext']}/{row['Name']}"),
							row["Format als regulärer Ausdruck"],
							" ".join(row["Beschreibung"].split()),
						)
						for row in jd.sheet(jd.GEWST, year, f"{form} - Felder")
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
						if field.form == form
					]
					self.assertEqual(ours, documented)
					self.assertEqual(
						tuple((f.context, f.feldkennung) for f in catalogue.fields if f.form == form),
						jd.leaves(jd.GEWST, year, form),
					)

	def test_the_beschreibung_of_each_field_is_its_drucktext(self):
		for ez, year in documented_years():
			for form in VORDRUCKE:
				with self.subTest(ez=ez, form=form):
					for row in jd.sheet(jd.GEWST, year, f"{form} - Felder"):
						self.assertEqual(
							" ".join(row["Beschreibung"].split()), " ".join(row["Drucktext"].split())
						)


class RulesTest(TestCase):
	def test_each_rule_is_that_of_the_jahresdokumentation(self):
		for ez, year in documented_years():
			documented = {
				row["Fehlercode"]: row
				for form in VORDRUCKE
				for row in jd.sheet(jd.GEWST, year, f"{form} - Regeln")
			}
			for rule in CATALOGUES[ez].rules:
				with self.subTest(ez=ez, code=rule.code):
					row = documented[rule.code]
					self.assertEqual(rule.name, row["Name"])
					self.assertEqual(
						rule.fields,
						tuple(part.strip() for part in " ".join(row["Geprüfte Felder"].split()).split(",")),
					)
					self.assertEqual(rule.hint, row["Regelart"] == "Hinweis")


class RechtsformenTest(TestCase):
	def test_the_categories_are_those_of_rechtsform_gewerbesteuer_v2(self):
		for ez, year in documented_years():
			with self.subTest(ez=ez):
				(row,) = (
					row
					for row in jd.sheet(jd.GEWST, year, "Benutzerdefinierte Typen")
					if row["Name"] == "RECHTSFORM_GEWERBESTEUER_V2" and row["Version"] == "2"
				)
				documented = {
					match["code"]: dict(PAIR.findall(match["categories"]))
					for line in row["Format"].split("\n")
					if (match := CATEGORY.match(line.strip()))
				}
				for code, categories in RECHTSFORMEN[ez].items():
					self.assertEqual(dict(categories), documented[code])
