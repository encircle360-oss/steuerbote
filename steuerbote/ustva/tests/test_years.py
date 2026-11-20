"""The year table: which years Steuerbote files and what each of them needs."""

from datetime import date
from unittest import TestCase

from steuerbote import ustva
from steuerbote.dauerfrist import form
from steuerbote.dauerfrist.form import NO_LAYOUT, FormError, layout_for
from steuerbote.elster import ustva_xml
from steuerbote.elster.ustva_xml import NO_SCHEMA, XmlError, schema_for
from steuerbote.ustva import kennzahlen
from steuerbote.ustva.kennzahlen import catalogue_for
from steuerbote.ustva.mapping import AccountRule, Mapping, Side
from steuerbote.ustva.years import (
	LATEST_YEAR,
	YEARS,
	UnknownYearError,
	Year,
	datenart_version,
	plugin,
	plugin_library,
	plugin_year,
	year_of,
)

UNKNOWN_YEAR = LATEST_YEAR + 1


class YearTableTest(TestCase):
	def test_files_2026(self):
		self.assertEqual(tuple(YEARS), (2026,))
		self.assertEqual(LATEST_YEAR, 2026)

	def test_holds_each_year_under_its_own_number_in_order(self):
		self.assertEqual([year.year for year in YEARS.values()], list(YEARS))
		self.assertEqual(list(YEARS), sorted(YEARS))

	def test_names_the_bmf_letter_of_the_forms_of_2026(self):
		year = YEARS[2026]
		self.assertEqual(year.letter_date, date(2025, 12, 29))
		self.assertEqual(year.reference, "III C 3 - S 7344/00039/007/036")
		self.assertEqual(
			year.letter,
			"BMF letter of 29 December 2025 (GZ III C 3 - S 7344/00039/007/036)",
		)
		self.assertTrue(year.url.startswith("https://www.bundesfinanzministerium.de/"))
		self.assertIn("2025-12-29-vordruckmuster-USt-voranmeldung-2026.pdf", year.url)

	def test_the_data_of_each_year_cite_its_bmf_letter(self):
		for year in YEARS.values():
			for module in (kennzahlen, form):
				with self.subTest(year=year.year, module=module.__name__):
					self.assertIn(year.letter, " ".join((module.__doc__ or "").split()))

	def test_is_read_only(self):
		with self.assertRaises(TypeError):
			YEARS[UNKNOWN_YEAR] = YEARS[LATEST_YEAR]  # type: ignore[index]
		with self.assertRaises(AttributeError):
			YEARS[2026].year = UNKNOWN_YEAR  # type: ignore[misc]


class PartsTest(TestCase):
	"""Every table of a year holds exactly the years of the table, so a new year fails here until it is whole."""

	def test_every_table_holds_exactly_the_years(self):
		for name, table in (
			("CATALOGUES of steuerbote/ustva/kennzahlen.py", kennzahlen.CATALOGUES),
			("SCHEMAS of steuerbote/elster/ustva_xml.py", ustva_xml.SCHEMAS),
			("LAYOUTS of steuerbote/dauerfrist/form.py", form.LAYOUTS),
		):
			with self.subTest(table=name):
				self.assertEqual(sorted(table), list(YEARS))

	def test_every_part_of_a_year_belongs_to_that_year(self):
		for year in YEARS:
			with self.subTest(year=year):
				self.assertEqual(schema_for(year).year, year)
				self.assertEqual(layout_for(year).year, year)
				self.assertEqual(Mapping("test", (), year=year).catalogue, catalogue_for(year))

	def test_the_latest_year_is_the_latest_of_every_table(self):
		self.assertEqual(kennzahlen.LATEST_YEAR, LATEST_YEAR)
		self.assertEqual(form.LATEST_YEAR, LATEST_YEAR)
		self.assertEqual(max(ustva_xml.SCHEMAS), LATEST_YEAR)


class UnknownYearTest(TestCase):
	"""A year without data fails as it always did, with the errors the Frappe layer turns into hints."""

	def test_the_table_refuses_the_year_with_the_known_years(self):
		with self.assertRaises(UnknownYearError) as caught:
			year_of(UNKNOWN_YEAR)
		known = ", ".join(str(year) for year in YEARS)
		self.assertEqual(
			str(caught.exception), f"Steuerbote has no data for {UNKNOWN_YEAR}; known years: {known}"
		)
		self.assertIs(year_of(2026), YEARS[2026])

	def test_the_table_takes_years_only(self):
		for year in ("2026", 2026.0, True, None):
			with self.subTest(year=year), self.assertRaisesRegex(TypeError, "year must be an int"):
				year_of(year)  # type: ignore[arg-type]

	def test_is_the_error_of_the_catalogue_and_of_the_package(self):
		self.assertIs(kennzahlen.UnknownYearError, UnknownYearError)
		self.assertIs(ustva.UnknownYearError, UnknownYearError)
		self.assertTrue(issubclass(UnknownYearError, ValueError))

	def test_every_part_refuses_the_year_with_its_own_error(self):
		with self.assertRaisesRegex(UnknownYearError, f"no Kennzahlen catalogue for {UNKNOWN_YEAR}"):
			catalogue_for(UNKNOWN_YEAR)
		with self.assertRaisesRegex(UnknownYearError, str(UNKNOWN_YEAR)):
			Mapping("test", (AccountRule("8400", "81", Side.CREDIT),)).for_year(UNKNOWN_YEAR)
		with self.assertRaises(XmlError) as schema:
			schema_for(UNKNOWN_YEAR)
		self.assertEqual((schema.exception.template, schema.exception.values), (NO_SCHEMA, (UNKNOWN_YEAR,)))
		with self.assertRaises(FormError) as layout:
			layout_for(UNKNOWN_YEAR)
		self.assertEqual((layout.exception.template, layout.exception.values), (NO_LAYOUT, (UNKNOWN_YEAR,)))


class NamesTest(TestCase):
	"""datenartVersion UStVA_<Jahr> and plugin checkUStVA_<Jahr> (Datenartversionmatrix.ods)."""

	def test_names_the_datenart_version_and_plugin_of_a_year(self):
		year = YEARS[2026]
		self.assertEqual(year.datenart_version, "UStVA_2026")
		self.assertEqual(year.plugin, "checkUStVA_2026")
		self.assertEqual(year.plugin_library, "libcheckUStVA_2026.so")

	def test_names_them_for_a_year_without_data_too(self):
		self.assertEqual(datenart_version(UNKNOWN_YEAR), f"UStVA_{UNKNOWN_YEAR}")
		self.assertEqual(plugin(UNKNOWN_YEAR), f"checkUStVA_{UNKNOWN_YEAR}")
		self.assertEqual(plugin_library(UNKNOWN_YEAR), f"libcheckUStVA_{UNKNOWN_YEAR}.so")

	def test_reads_the_year_of_a_plugin_library(self):
		self.assertEqual(plugin_year("libcheckUStVA_2027.so"), 2027)
		self.assertEqual(plugin_year(plugin_library(2016)), 2016)
		for name in ("libcommonData.so", "libcheckZMDO.so", "libcheckUStVA_27.so", "libcheckUStVA_2027.so.1"):
			with self.subTest(name=name):
				self.assertIsNone(plugin_year(name))

	def test_a_year_names_them_from_its_number_alone(self):
		year = Year(2099, date(2098, 12, 1), "TEST", "https://example.org/")
		self.assertEqual((year.datenart_version, year.plugin), ("UStVA_2099", "checkUStVA_2099"))
		self.assertEqual(year.letter, "BMF letter of 1 December 2098 (GZ TEST)")
