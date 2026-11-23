"""The year table of the Umsatzsteuererklärung: which years Steuerbote files and what each of them needs."""

from datetime import date
from unittest import TestCase

from steuerbote.ustjahr import defaults, form, rules
from steuerbote.ustjahr.years import (
	LATEST_YEAR,
	YEARS,
	Year,
	datenart_version,
	filing_deadline,
	plugin,
	plugin_library,
	year_of,
)
from steuerbote.ustva import years as ustva_years
from steuerbote.ustva.years import UnknownYearError

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
		self.assertEqual(year.reference, "III C 3 - S 7344/00040/008/034")
		self.assertEqual(year.letter, "BMF letter of 29 December 2025 (GZ III C 3 - S 7344/00040/008/034)")
		self.assertTrue(year.url.startswith("https://www.bundesfinanzministerium.de/"))
		self.assertIn("2025-12-29-muster-USt-erklaerung-2026.pdf", year.url)

	def test_the_annual_return_has_a_letter_of_its_own(self):
		"""The BMF published the forms of the Voranmeldung and of the annual return in two letters of the same day."""
		annual, ustva = YEARS[2026], ustva_years.YEARS[2026]
		self.assertEqual(annual.letter_date, ustva.letter_date)
		self.assertNotEqual(annual.reference, ustva.reference)

	def test_is_read_only(self):
		with self.assertRaises(TypeError):
			YEARS[UNKNOWN_YEAR] = YEARS[LATEST_YEAR]  # type: ignore[index]
		with self.assertRaises(AttributeError):
			YEARS[2026].year = UNKNOWN_YEAR  # type: ignore[misc]


class PartsTest(TestCase):
	"""Every table of a year holds exactly the years of the table, so a new year fails here until it is whole."""

	def test_every_table_holds_exactly_the_years(self):
		for name, table in (
			("CATALOGUES of steuerbote/ustjahr/form.py", form.CATALOGUES),
			("LOCAL_RULES of steuerbote/ustjahr/rules.py", rules.LOCAL_RULES),
			("LEFT_TO_ERIC of steuerbote/ustjahr/rules.py", rules.LEFT_TO_ERIC),
			("ROLE_FIELDS of steuerbote/ustjahr/defaults.py", defaults.ROLE_FIELDS),
			("ANNUAL_ACCOUNTS of steuerbote/ustjahr/defaults.py", defaults.ANNUAL_ACCOUNTS),
			("REVISIONS of steuerbote/ustjahr/defaults.py", defaults.REVISIONS),
		):
			with self.subTest(table=name):
				self.assertEqual(sorted(table), list(YEARS))

	def test_the_data_of_each_year_cite_its_bmf_letter(self):
		for year in YEARS.values():
			for module in (form, defaults):
				with self.subTest(year=year.year, module=module.__name__):
					self.assertIn(year.letter, " ".join((module.__doc__ or "").split()))

	def test_the_latest_year_is_the_latest_of_every_table(self):
		for table in (
			form.CATALOGUES,
			rules.LOCAL_RULES,
			rules.LEFT_TO_ERIC,
			defaults.ROLE_FIELDS,
			defaults.ANNUAL_ACCOUNTS,
			defaults.REVISIONS,
		):
			self.assertEqual(max(table), LATEST_YEAR)


class UnknownYearTest(TestCase):
	def test_the_table_refuses_the_year_with_the_known_years(self):
		with self.assertRaises(UnknownYearError) as caught:
			year_of(UNKNOWN_YEAR)
		self.assertEqual(
			str(caught.exception),
			f"Steuerbote has no data for the Umsatzsteuererklärung {UNKNOWN_YEAR}; known years: 2026",
		)
		self.assertIs(year_of(2026), YEARS[2026])

	def test_the_table_takes_years_only(self):
		for year in ("2026", 2026.0, True, None):
			with self.subTest(year=year), self.assertRaisesRegex(TypeError, "year must be an int"):
				year_of(year)  # type: ignore[arg-type]


class NamesTest(TestCase):
	"""datenartVersion USt_<Jahr> and plugin checkUSt_<Jahr> (Datenartversionmatrix.ods)."""

	def test_names_the_datenart_version_and_plugin_of_a_year(self):
		year = YEARS[2026]
		self.assertEqual(year.datenart_version, "USt_2026")
		self.assertEqual(year.plugin, "checkUSt_2026")
		self.assertEqual(year.plugin_library, "libcheckUSt_2026.so")

	def test_names_them_for_a_year_without_data_too(self):
		self.assertEqual(datenart_version(UNKNOWN_YEAR), f"USt_{UNKNOWN_YEAR}")
		self.assertEqual(plugin(UNKNOWN_YEAR), f"checkUSt_{UNKNOWN_YEAR}")
		self.assertEqual(plugin_library(UNKNOWN_YEAR), f"libcheckUSt_{UNKNOWN_YEAR}.so")

	def test_a_year_names_them_from_its_number_alone(self):
		year = Year(2099, date(2098, 12, 1), "TEST", "https://example.org/")
		self.assertEqual((year.datenart_version, year.plugin), ("USt_2099", "checkUSt_2099"))
		self.assertEqual(year.letter, "BMF letter of 1 December 2098 (GZ TEST)")


class FilingDeadlineTest(TestCase):
	"""§ 149 Absatz 2 to 4 AO, moved by § 108 Absatz 3 AO."""

	def test_is_due_seven_months_after_the_year_moved_off_the_saturday(self):
		self.assertEqual(date(2027, 7, 31).weekday(), 5)
		self.assertEqual(filing_deadline(2026), date(2027, 8, 2))

	def test_with_a_steuerberatung_is_due_on_the_last_day_of_february_of_the_second_year(self):
		self.assertEqual(filing_deadline(2026, advisor=True), date(2028, 2, 29))
		self.assertEqual(filing_deadline(2027, advisor=True), date(2029, 2, 28))

	def test_a_holiday_of_the_company_moves_it_to_the_next_working_day(self):
		self.assertEqual(filing_deadline(2026, holidays=frozenset({date(2027, 8, 2)})), date(2027, 8, 3))
		self.assertEqual(filing_deadline(2026, holidays={date(2027, 8, 4)}), date(2027, 8, 2))

	def test_the_day_the_finanzamt_orders_replaces_both(self):
		ordered = date(2027, 9, 30)
		self.assertEqual(filing_deadline(2026, requested=ordered), ordered)
		self.assertEqual(filing_deadline(2026, advisor=True, requested=ordered), ordered)

	def test_the_day_the_finanzamt_orders_moves_off_a_weekend_too(self):
		self.assertEqual(filing_deadline(2026, advisor=True, requested=date(2027, 10, 2)), date(2027, 10, 4))

	def test_takes_years_only(self):
		for year in ("2026", 2026.0, True):
			with self.subTest(year=year), self.assertRaisesRegex(TypeError, "year must be an int"):
				filing_deadline(year)  # type: ignore[arg-type]
