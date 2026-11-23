"""The Erhebungszeiträume of the Gewerbesteuer: the Messzahl, the Hinzurechnungen and Kürzungen, the files."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.gewst.years import (
	LATEST_YEAR,
	YEARS,
	datenart_version,
	jahresdokumentation,
	namespace,
	plugin,
	schema,
	statutory_ev_rent_percent,
	statutory_minimum_hebesatz,
	year_of,
)
from steuerbote.ustva.years import UnknownYearError

UNKNOWN_YEAR = LATEST_YEAR + 1


class YearTableTest(TestCase):
	def test_computes_2026(self):
		self.assertEqual(tuple(YEARS), (2026,))
		self.assertEqual(LATEST_YEAR, 2026)

	def test_holds_each_year_under_its_own_number(self):
		self.assertEqual([year.year for year in YEARS.values()], list(YEARS))

	def test_is_read_only(self):
		with self.assertRaises(TypeError):
			YEARS[UNKNOWN_YEAR] = YEARS[2026]  # type: ignore[index]
		with self.assertRaises(AttributeError):
			YEARS[2026].messzahl = Decimal("5")  # type: ignore[misc]


class GewerbeertragTest(TestCase):
	def test_the_messzahl_is_3_5_percent(self):
		self.assertEqual(YEARS[2026].messzahl, Decimal("3.5"))

	def test_a_quarter_of_the_financing_parts_beyond_200_000_euro_is_added_back(self):
		year = YEARS[2026]
		self.assertEqual(year.financing_allowance, Decimal("200000"))
		self.assertEqual(year.financing_percent, Decimal("25"))

	def test_the_parts_of_rents_and_licences(self):
		year = YEARS[2026]
		self.assertEqual(year.movable_rent_percent, Decimal("20"))
		self.assertEqual(year.movable_rent_ev_percent, Decimal("10"))
		self.assertEqual(year.immovable_rent_percent, Decimal("50"))
		self.assertEqual(year.licence_percent, Decimal("25"))

	def test_the_half_for_electric_vehicles_ends_with_2030(self):
		self.assertEqual(statutory_ev_rent_percent(2030), Decimal("10"))
		self.assertEqual(statutory_ev_rent_percent(2031), Decimal("20"))

	def test_a_holding_of_15_percent_cuts_its_dividends(self):
		self.assertEqual(YEARS[2026].participation_minimum, Decimal("15"))

	def test_the_limits_of_the_zuwendungen(self):
		year = YEARS[2026]
		self.assertEqual(year.donation_profit_percent, Decimal("20"))
		self.assertEqual(year.donation_turnover_per_mille, Decimal("4"))

	def test_the_fehlbetraege_of_10a(self):
		year = YEARS[2026]
		self.assertEqual(year.loss_unlimited, Decimal("1000000"))
		self.assertEqual(year.loss_share, Decimal("60"))


class HebesatzTest(TestCase):
	def test_the_minimum_is_200_percent_in_2026_and_280_percent_from_2027(self):
		self.assertEqual(YEARS[2026].minimum_hebesatz, Decimal("200"))
		self.assertEqual(statutory_minimum_hebesatz(2026), Decimal("200"))
		self.assertEqual(statutory_minimum_hebesatz(2027), Decimal("280"))
		self.assertEqual(statutory_minimum_hebesatz(2030), Decimal("280"))

	def test_every_year_takes_the_figures_of_the_statute(self):
		for year in YEARS.values():
			with self.subTest(year=year.year):
				self.assertEqual(year.minimum_hebesatz, statutory_minimum_hebesatz(year.year))
				self.assertEqual(year.movable_rent_ev_percent, statutory_ev_rent_percent(year.year))

	def test_the_vorauszahlungen_fall_on_the_15th_of_february_may_august_and_november(self):
		year = YEARS[2026]
		self.assertEqual(
			year.prepayment_dates,
			(date(2026, 2, 15), date(2026, 5, 15), date(2026, 8, 15), date(2026, 11, 15)),
		)
		self.assertEqual(year.prepayment_minimum, Decimal("50"))

	def test_cites_the_statutes(self):
		sources = " ".join(YEARS[2026].sources)
		for citation in (
			"§ 8 Nummer 1 GewStG",
			"§ 36 Absatz 4 Satz 3 GewStG",
			"§ 9 Nummer 1 Satz 1 GewStG",
			"§ 36 Absatz 4b GewStG",
			"§ 9 Nummer 2a und 7 GewStG",
			"§ 9 Nummer 5 GewStG",
			"§ 10a GewStG",
			"§ 11 GewStG",
			"§ 16 Absatz 4 Satz 2 GewStG",
			"§ 36 Absatz 5b GewStG",
			"§ 19 Absatz 1 und 5 GewStG",
			"Jahresdokumentation_E20_2025.ods",
		):
			with self.subTest(citation=citation):
				self.assertIn(citation, sources)


class FilingTest(TestCase):
	"""datenartVersion GewSt_<Jahr>, plugin checkGewSt_<Jahr> (Datenartversionmatrix.ods of ERiC 44.3.6.0)."""

	def test_2026_is_provisional_and_takes_the_forms_of_2025(self):
		year = YEARS[2026]
		self.assertTrue(year.provisional)
		self.assertEqual(year.documentation_year, 2025)
		self.assertEqual(year.jahresdokumentation, "Jahresdokumentation_E20_2025.ods")
		self.assertEqual(year.schema, "E20-2025.xsd")

	def test_names_the_datenart_the_plugin_the_files_and_the_namespace(self):
		self.assertEqual(YEARS[2026].datenart_version, "GewSt_2026")
		self.assertEqual(YEARS[2026].plugin, "checkGewSt_2026")
		self.assertEqual(datenart_version(2025), "GewSt_2025")
		self.assertEqual(plugin(2025), "checkGewSt_2025")
		self.assertEqual(jahresdokumentation(2025), "Jahresdokumentation_E20_2025.ods")
		self.assertEqual(schema(2025), "E20-2025.xsd")
		self.assertEqual(namespace(2025), "http://finkonsens.de/elster/elstererklaerung/gewst/e20/v2025")

	def test_a_year_with_its_own_documentation_reads_its_own_files(self):
		year = replace(YEARS[2026], year=2099, documentation_year=2099, provisional=False)
		self.assertEqual(year.jahresdokumentation, "Jahresdokumentation_E20_2099.ods")


class UnknownYearTest(TestCase):
	def test_refuses_a_year_without_data_with_the_known_years(self):
		with self.assertRaises(UnknownYearError) as caught:
			year_of(UNKNOWN_YEAR)
		self.assertEqual(
			str(caught.exception), f"Steuerbote has no data for {UNKNOWN_YEAR}; known years: 2026"
		)
		self.assertIs(year_of(2026), YEARS[2026])

	def test_takes_years_only(self):
		for year in ("2026", 2026.0, True, None):
			with self.subTest(year=year), self.assertRaisesRegex(TypeError, "year must be an int"):
				year_of(year)  # type: ignore[arg-type]
