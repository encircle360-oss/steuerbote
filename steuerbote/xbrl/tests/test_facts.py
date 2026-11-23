"""The facts of a report, before any XML: periods, entity, items with their dimensions or NIL, tuples."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.xbrl.facts import (
	STEUERNUMMER,
	Entity,
	Item,
	Period,
	Periods,
	Report,
	Tuple,
	amount,
	choice,
	nil,
)

PERIODS = Periods(date(2026, 1, 1), date(2026, 12, 31))
PRIOR = Periods(
	date(2026, 1, 1),
	date(2026, 12, 31),
	prior_fiscal_year_begin=date(2025, 1, 1),
	prior_fiscal_year_end=date(2025, 12, 31),
)
# Invented: a Steuernummer of the test Finanzamt 9198 of the ERiC documentation.
ENTITY = Entity(STEUERNUMMER, "9198011310010")


class PeriodsTest(TestCase):
	"""„Stichtagsbezogene Positionen müssen im Datensatz stichtagsbezogenen Kontexten zugordnet sein ...
	periodenbezogene Positionen periodenbezogenen Kontexten“ (Technischer Leitfaden 6.9, B.8), at the Bilanzstichtag
	and over the fiscal year (B.8.1, B.8.2), and for the previous year where a Handelsbilanz shows it (B.8.3)."""

	def test_the_closing_date_is_the_end_of_the_fiscal_year(self):
		self.assertEqual(PERIODS.balance_sheet_date, date(2026, 12, 31))
		self.assertEqual(PERIODS.dates(Period.STICHTAG), (None, date(2026, 12, 31)))
		self.assertEqual(PERIODS.dates(Period.WIRTSCHAFTSJAHR), (date(2026, 1, 1), date(2026, 12, 31)))

	def test_an_eroeffnungsbilanz_has_its_closing_date_at_the_beginning(self):
		"""The example SteuerbilanzAutoverkaeufer-Eroeffnung_PersG.xml of the ERiC documentation: stichtag 20250101 in
		a fiscal year from 01.01.2025 to 31.12.2025."""
		opening = Periods(date(2025, 1, 1), date(2025, 12, 31), balance_sheet_date=date(2025, 1, 1))
		self.assertEqual(opening.dates(Period.STICHTAG), (None, date(2025, 1, 1)))
		self.assertEqual(opening.dates(Period.WIRTSCHAFTSJAHR), (date(2025, 1, 1), date(2025, 12, 31)))

	def test_the_previous_year(self):
		self.assertEqual(PRIOR.prior_balance_sheet_date, date(2025, 12, 31))
		self.assertEqual(PRIOR.dates(Period.VORJAHR_STICHTAG), (None, date(2025, 12, 31)))
		self.assertEqual(PRIOR.dates(Period.VORJAHR), (date(2025, 1, 1), date(2025, 12, 31)))

	def test_without_a_previous_year_there_is_no_period_of_it(self):
		for period in (Period.VORJAHR, Period.VORJAHR_STICHTAG):
			with self.subTest(period=period), self.assertRaisesRegex(ValueError, "Vorjahr"):
				PERIODS.dates(period)

	def test_knows_which_periods_are_instants_and_which_the_previous_year(self):
		self.assertEqual(
			[(period, period.instant, period.prior) for period in Period],
			[
				(Period.STICHTAG, True, False),
				(Period.WIRTSCHAFTSJAHR, False, False),
				(Period.VORJAHR_STICHTAG, True, True),
				(Period.VORJAHR, False, True),
			],
		)

	def test_a_fiscal_year_ends_after_it_begins(self):
		with self.assertRaises(ValueError):
			Periods(date(2026, 12, 31), date(2026, 1, 1))
		with self.assertRaises(ValueError):
			Periods(
				date(2026, 1, 1),
				date(2026, 12, 31),
				prior_fiscal_year_begin=date(2025, 12, 31),
				prior_fiscal_year_end=date(2025, 1, 1),
			)

	def test_the_previous_year_ends_before_the_fiscal_year_begins(self):
		with self.assertRaisesRegex(ValueError, "before"):
			Periods(
				date(2026, 1, 1),
				date(2026, 12, 31),
				prior_fiscal_year_begin=date(2025, 6, 1),
				prior_fiscal_year_end=date(2026, 5, 31),
			)

	def test_the_previous_year_needs_both_its_days(self):
		with self.assertRaisesRegex(ValueError, "both"):
			Periods(date(2026, 1, 1), date(2026, 12, 31), prior_fiscal_year_begin=date(2025, 1, 1))


class EntityTest(TestCase):
	def test_the_e_bilanz_names_the_company_by_its_steuernummer(self):
		"""„<xbrli:identifier scheme="http://www.rzf-nrw.de/Steuernummer">5192050001276</xbrli:identifier>“ in every
		context of the examples of the ERiC documentation; ST13 is the Steuernummer in the 13-digit format of ELSTER
		(Leitfaden B.14.3.1.18)."""
		self.assertEqual(STEUERNUMMER, "http://www.rzf-nrw.de/Steuernummer")
		self.assertEqual(Entity.steuernummer("9198011310010"), ENTITY)

	def test_a_steuernummer_has_13_digits(self):
		for value in ("919801131001", "91980113100100", "9198O11310010"):
			with self.subTest(value=value), self.assertRaisesRegex(ValueError, "13"):
				Entity.steuernummer(value)

	def test_an_entity_has_a_scheme_and_an_identifier(self):
		with self.assertRaises(ValueError):
			Entity("", "9198011310010")
		with self.assertRaises(ValueError):
			Entity(STEUERNUMMER, " ")


class ItemTest(TestCase):
	def test_an_item_reports_a_value_of_a_concept_for_a_period(self):
		item = amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal("100.00"))
		self.assertEqual(item, Item("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal("100.00")))
		self.assertFalse(item.nil)

	def test_nil_is_an_item_without_a_value(self):
		"""„Nicht aus der Buchführung mit Werten zu belegende Mussfelder ... müssen im Datensatz „leer“ (technisch mit
		„NIL“) übermittelt werden.“ (Leitfaden B.14.2.3)"""
		item = nil("de-gaap-ci:bs.ass.fixAss", Period.STICHTAG)
		self.assertTrue(item.nil)
		self.assertIsNone(item.value)

	def test_names_the_concept_with_its_prefix(self):
		with self.assertRaisesRegex(ValueError, "prefix"):
			Item("bs.ass", Period.STICHTAG, Decimal(1))

	def test_money_is_decimal(self):
		for value in (1.5, 100):
			with self.subTest(value=value), self.assertRaises(TypeError):
				amount("de-gaap-ci:bs.ass", Period.STICHTAG, value)  # type: ignore[arg-type]

	def test_takes_the_values_of_xbrl_items(self):
		for value in (Decimal("1.00"), "Text", True, date(2026, 1, 1), 3):
			with self.subTest(value=value):
				self.assertEqual(
					Item("de-gcd:genInfo.company.id.name", Period.WIRTSCHAFTSJAHR, value).value, value
				)

	def test_refuses_a_float(self):
		with self.assertRaises(TypeError):
			Item("de-gaap-ci:bs.ass", Period.STICHTAG, 1.0)  # type: ignore[arg-type]

	def test_dimensions_are_kept_in_the_order_of_their_names(self):
		item = Item(
			"de-gaap-ci:gross",
			Period.WIRTSCHAFTSJAHR,
			Decimal("10.00"),
			dimensions=(
				("de-gaap-ci:dim_taxTrans", "de-gaap-ci:dim_taxBal"),
				("de-gaap-ci:dim_changes.nt.ass.gross", "de-gaap-ci:bs.ass.fixAss.tan"),
			),
		)
		self.assertEqual(
			item.dimensions,
			(
				("de-gaap-ci:dim_changes.nt.ass.gross", "de-gaap-ci:bs.ass.fixAss.tan"),
				("de-gaap-ci:dim_taxTrans", "de-gaap-ci:dim_taxBal"),
			),
		)
		self.assertEqual(
			item.dimension("de-gaap-ci:dim_changes.nt.ass.gross"), "de-gaap-ci:bs.ass.fixAss.tan"
		)
		self.assertIsNone(item.dimension("de-gaap-ci:dim_other"))

	def test_a_dimension_takes_one_member(self):
		with self.assertRaisesRegex(ValueError, "dim_taxTrans"):
			Item(
				"de-gaap-ci:gross",
				Period.WIRTSCHAFTSJAHR,
				Decimal(1),
				dimensions=(
					("de-gaap-ci:dim_taxTrans", "de-gaap-ci:dim_taxBal"),
					("de-gaap-ci:dim_taxTrans", "de-gaap-ci:dim_comBal"),
				),
			)

	def test_dimensions_and_members_are_named_with_their_prefix(self):
		with self.assertRaisesRegex(ValueError, "prefix"):
			Item(
				"de-gaap-ci:gross",
				Period.WIRTSCHAFTSJAHR,
				Decimal(1),
				dimensions=(("dim_taxTrans", "de-gaap-ci:x"),),
			)

	def test_decimals_are_whole_numbers(self):
		self.assertEqual(Item("de-gcd:x", Period.WIRTSCHAFTSJAHR, Decimal(1), decimals=0).decimals, 0)
		with self.assertRaises(TypeError):
			Item("de-gcd:x", Period.WIRTSCHAFTSJAHR, Decimal(1), decimals=1.5)  # type: ignore[arg-type]


class TupleTest(TestCase):
	def test_a_tuple_groups_its_facts(self):
		"""„Eine Position mit Auswahlwerten ist eine Datenstruktur (technisch: Tupel), welche die Auswahlwerte als in
		der Datenstruktur geschachtelte Felder enthält.“ (Leitfaden A.8)"""
		account = Tuple(
			"de-gaap-ci:detailedInformation.accountBalances",
			(
				Item(
					"de-gaap-ci:detailedInformation.accountbalances.positionName",
					Period.WIRTSCHAFTSJAHR,
					"de-gaap-ci:bs.ass",
				),
				Item(
					"de-gaap-ci:detailedInformation.accountbalances.amount",
					Period.WIRTSCHAFTSJAHR,
					Decimal("10.00"),
				),
			),
		)
		self.assertEqual(len(account.children), 2)
		self.assertFalse(account.nil)

	def test_a_nil_tuple_has_no_facts(self):
		self.assertTrue(Tuple("de-gcd:genInfo.company.id.shareholder", nil=True).nil)
		with self.assertRaisesRegex(ValueError, "NIL"):
			Tuple(
				"de-gcd:genInfo.company.id.shareholder", (nil("de-gcd:x", Period.WIRTSCHAFTSJAHR),), nil=True
			)

	def test_a_tuple_holds_facts(self):
		with self.assertRaises(TypeError):
			Tuple("de-gcd:genInfo.company.id.shareholder", ("Name",))  # type: ignore[arg-type]

	def test_a_choice_reports_its_values_as_empty_strings(self):
		"""„übermittelte Strings sollen mit einer Länge von 0 übermittelt werden (ggf. Übermittlung mit NIL, wenn
		Position Mussfeld, aber nicht zu berichten)“ (Leitfaden B.14.1)."""
		self.assertEqual(
			choice(
				"de-gcd:genInfo.report.id.reportElement",
				"de-gcd:genInfo.report.id.reportElement.reportElements.B",
				"de-gcd:genInfo.report.id.reportElement.reportElements.GuV",
				unreported=("de-gcd:genInfo.report.id.reportElement.reportElements.EB",),
			),
			Tuple(
				"de-gcd:genInfo.report.id.reportElement",
				(
					Item(
						"de-gcd:genInfo.report.id.reportElement.reportElements.B", Period.WIRTSCHAFTSJAHR, ""
					),
					Item(
						"de-gcd:genInfo.report.id.reportElement.reportElements.GuV",
						Period.WIRTSCHAFTSJAHR,
						"",
					),
					Item(
						"de-gcd:genInfo.report.id.reportElement.reportElements.EB",
						Period.WIRTSCHAFTSJAHR,
						None,
					),
				),
			),
		)


class ReportTest(TestCase):
	def report(self, *facts) -> Report:
		return Report(
			ENTITY,
			PRIOR,
			("http://www.xbrl.de/taxonomies/de-gcd-2025-04-01/de-gcd-2025-04-01-shell.xsd",),
			facts,
		)

	def test_names_every_item_with_the_tuple_around_it(self):
		account = Tuple(
			"de-gaap-ci:detailedInformation.accountBalances",
			(
				Item(
					"de-gaap-ci:detailedInformation.accountbalances.amount",
					Period.WIRTSCHAFTSJAHR,
					Decimal("1.00"),
				),
			),
		)
		bank = amount("de-gaap-ci:bs.ass.currAss.cashEquiv.bank", Period.STICHTAG, Decimal("1.00"))
		report = self.report(bank, account)
		self.assertEqual(list(report.items()), [(bank, ()), (account.children[0], (account,))])
		self.assertEqual(list(report.tuples()), [(account, ())])

	def test_names_the_contexts_its_items_refer_to(self):
		dimensional = Item(
			"de-gaap-ci:gross",
			Period.WIRTSCHAFTSJAHR,
			Decimal("1.00"),
			dimensions=(("de-gaap-ci:dim_taxTrans", "de-gaap-ci:dim_taxBal"),),
		)
		report = self.report(
			amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal("1.00")),
			amount("de-gaap-ci:bs.ass", Period.VORJAHR_STICHTAG, Decimal("2.00")),
			dimensional,
		)
		self.assertEqual(
			report.contexts(),
			{
				(Period.STICHTAG, ()),
				(Period.VORJAHR_STICHTAG, ()),
				(Period.WIRTSCHAFTSJAHR, dimensional.dimensions),
			},
		)

	def test_the_monetary_items_have_two_decimals_by_default(self):
		"""„Die monetären Wertangaben müssen auf zwei Nachkommastellen genau angegeben sein“ (Leitfaden B.7)."""
		self.assertEqual(self.report().monetary_decimals, 2)

	def test_a_report_holds_facts(self):
		with self.assertRaises(TypeError):
			self.report("bs.ass")

	def test_a_report_references_an_entry_point(self):
		with self.assertRaisesRegex(ValueError, "entry point"):
			Report(ENTITY, PERIODS, (), ())
