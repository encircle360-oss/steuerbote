"""The Veranlagungszeiträume of the Körperschaftsteuer: the rates and limits of each, its forms and its files."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.kst.years import (
	LATEST_YEAR,
	YEARS,
	RuleExpectation,
	datenart_version,
	factor,
	jahresdokumentation,
	namespace,
	plugin,
	schema,
	statutory_loss_share,
	statutory_rate,
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
			YEARS[2026].rate = Decimal("10")  # type: ignore[misc]


class RatesTest(TestCase):
	"""§ 23 Absatz 1 KStG, § 4 SolZG."""

	def test_2026_takes_15_percent_of_the_zve(self):
		self.assertEqual(YEARS[2026].rate, Decimal("15"))

	def test_the_rate_falls_by_one_point_a_year_from_2028_to_10_percent_from_2032(self):
		rates = {vz: statutory_rate(vz) for vz in (2026, 2027, 2028, 2029, 2030, 2031, 2032, 2040)}
		self.assertEqual(
			rates,
			{
				2026: Decimal("15"),
				2027: Decimal("15"),
				2028: Decimal("14"),
				2029: Decimal("13"),
				2030: Decimal("12"),
				2031: Decimal("11"),
				2032: Decimal("10"),
				2040: Decimal("10"),
			},
		)

	def test_every_year_takes_the_rate_of_the_statute(self):
		for year in YEARS.values():
			with self.subTest(year=year.year):
				self.assertEqual(year.rate, statutory_rate(year.year))
				self.assertEqual(year.loss_share, statutory_loss_share(year.year))

	def test_the_solidaritaetszuschlag_is_5_5_percent_without_a_freigrenze(self):
		self.assertEqual(YEARS[2026].solz_rate, Decimal("5.5"))


class LimitsTest(TestCase):
	def test_the_verlustabzug_of_10d_estg(self):
		year = YEARS[2026]
		self.assertEqual(year.loss_carry_back, Decimal("1000000"))
		self.assertEqual(year.loss_unlimited, Decimal("1000000"))
		self.assertEqual(year.loss_share, Decimal("70"))

	def test_the_share_beyond_one_million_falls_to_60_percent_from_2028(self):
		self.assertEqual(statutory_loss_share(2027), Decimal("70"))
		self.assertEqual(statutory_loss_share(2028), Decimal("60"))
		self.assertEqual(statutory_loss_share(2035), Decimal("60"))

	def test_the_limits_of_the_zuwendungen(self):
		year = YEARS[2026]
		self.assertEqual(year.donation_income_percent, Decimal("20"))
		self.assertEqual(year.donation_turnover_per_mille, Decimal("4"))

	def test_paragraph_8b(self):
		year = YEARS[2026]
		self.assertEqual(year.p8b_percent, Decimal("5"))
		self.assertEqual(year.p8b_minimum_holding, Decimal("10"))

	def test_the_limited_deductions(self):
		year = YEARS[2026]
		self.assertEqual(year.gift_limit, Decimal("50"))
		self.assertEqual(year.entertainment_deductible_percent, Decimal("70"))
		self.assertEqual(year.supervisory_board_percent, Decimal("50"))

	def test_the_investitionsabzugsbetrag_and_the_zinsschranke(self):
		year = YEARS[2026]
		self.assertEqual(year.iab_percent, Decimal("50"))
		self.assertEqual(year.iab_profit_limit, Decimal("200000"))
		self.assertEqual(year.iab_total_limit, Decimal("200000"))
		self.assertEqual(year.interest_barrier, Decimal("3000000"))

	def test_the_vorauszahlungen_are_due_on_the_tenth_of_march_june_september_and_december(self):
		self.assertEqual(
			YEARS[2026].prepayment_dates,
			(date(2026, 3, 10), date(2026, 6, 10), date(2026, 9, 10), date(2026, 12, 10)),
		)

	def test_cites_the_statutes(self):
		sources = " ".join(YEARS[2026].sources)
		for citation in (
			"§ 23 Absatz 1 KStG",
			"§ 4 SolZG",
			"§ 10d Absatz 1 und 2 EStG",
			"§ 9 Absatz 1 Nummer 2 KStG",
			"§ 8b Absatz 3 bis 5 KStG",
			"§ 4 Absatz 5 Satz 1 Nummer 1 und 2 EStG",
			"§ 10 Nummer 4 KStG",
			"§ 7g Absatz 1 EStG",
			"§ 4h Absatz 2 Satz 1 Buchstabe a EStG",
			"§ 37 Absatz 1 Satz 1 EStG",
			"Jahresdokumentation_E30_2025.ods",
		):
			with self.subTest(citation=citation):
				self.assertIn(citation, sources)


class FilingTest(TestCase):
	"""datenartVersion KSt_30_<Jahr>, plugin checkKSt_<Jahr> (Datenartversionmatrix.ods of ERiC 44.3.6.0)."""

	def test_2026_is_provisional_and_takes_the_forms_of_2025(self):
		year = YEARS[2026]
		self.assertTrue(year.provisional)
		self.assertEqual(year.documentation_year, 2025)

	def test_names_the_datenart_and_the_plugin_of_the_year(self):
		self.assertEqual(YEARS[2026].datenart_version, "KSt_30_2026")
		self.assertEqual(YEARS[2026].plugin, "checkKSt_2026")
		self.assertEqual(datenart_version(2025), "KSt_30_2025")
		self.assertEqual(plugin(2025), "checkKSt_2025")

	def test_names_the_files_and_the_namespace_of_a_jahresdokumentation(self):
		self.assertEqual(jahresdokumentation(2025), "Jahresdokumentation_E30_2025.ods")
		self.assertEqual(schema(2025), "E30-2025.xsd")
		self.assertEqual(namespace(2025), "http://finkonsens.de/elster/elstererklaerung/kst/e30/v2025")

	def test_a_provisional_year_reads_the_files_of_its_documentation_year(self):
		year = YEARS[2026]
		self.assertEqual(year.jahresdokumentation, "Jahresdokumentation_E30_2025.ods")
		self.assertEqual(year.schema, "E30-2025.xsd")

	def test_a_year_with_its_own_documentation_reads_its_own_files(self):
		year = replace(YEARS[2026], year=2099, documentation_year=2099, provisional=False)
		self.assertEqual(year.jahresdokumentation, "Jahresdokumentation_E30_2099.ods")
		self.assertEqual(year.datenart_version, "KSt_30_2099")


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


class RuleExpectationTest(TestCase):
	"""What a module of the core expects of a rule of the Jahresdokumentation it computes."""

	def test_writes_a_percentage_as_the_factor_of_the_jahresdokumentation(self):
		self.assertEqual(factor(Decimal("15")), "0.15")
		self.assertEqual(factor(Decimal("70")), "0.7")
		self.assertEqual(factor(Decimal("5.5")), "0.055")
		self.assertEqual(factor(Decimal("20")), "0.2")
		self.assertEqual(factor(Decimal("0.4")), "0.004")
		self.assertEqual(factor(Decimal("100")), "1")

	def test_finds_its_terms_whatever_the_blanks_and_line_breaks(self):
		expectation = RuleExpectation("8900331", "ZVE", ("Abrunden([E8007504]*0.15)",))
		condition = "FeldAngegeben(E8007502)\nund [E8007502] != Abrunden([E8007504] * 0.15)"
		self.assertEqual(expectation.missing_terms(condition), ())

	def test_names_the_terms_the_condition_lacks(self):
		expectation = RuleExpectation("8900331", "ZVE", ("Abrunden([E8007504]*0.15)", "[E8007502]"))
		self.assertEqual(
			expectation.missing_terms("[E8007502] != Abrunden([E8007504] * 0.14)"),
			("Abrunden([E8007504]*0.15)",),
		)

	def test_names_its_sheet(self):
		self.assertEqual(RuleExpectation("8900331", "ZVE", ()).sheet, "ZVE - Regeln")

	def test_a_term_is_written_without_blanks(self):
		with self.assertRaisesRegex(ValueError, "without blanks"):
			RuleExpectation("8900331", "ZVE", ("Abrunden([E8007504] * 0.15)",))
