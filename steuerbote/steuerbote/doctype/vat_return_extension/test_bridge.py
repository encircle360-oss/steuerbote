"""The bridge between the Dauerfristverlängerung and the core: which filed VAT Returns make the base, which
Voranmeldungszeiträume it lacks, the base and Kz 38, and form USt 1 H from the values of the document."""

from datetime import date
from decimal import Decimal
from types import MappingProxyType
from unittest import TestCase

from steuerbote.dauerfrist import Context, FormError, Ust1H
from steuerbote.dauerfrist.form import LATEST_YEAR, NO_LAYOUT
from steuerbote.setup.start import PriorFiling
from steuerbote.steuerbote.doctype.vat_return_extension import bridge
from steuerbote.steuerbote.doctype.vat_return_extension.bridge import (
	Activity,
	BaseError,
	BaseProblem,
	FiledReturn,
	Override,
	Sondervorauszahlung,
)
from steuerbote.steuerbote.doctype.vat_return_settings.rules import PeriodRule, SettingsError
from steuerbote.ustva import Period

SVZ = Context.UMSATZSTEUERSONDERVORAUSZAHLUNG
DF = Context.DAUERFRISTVERLAENGERUNG
WHOLE_YEAR = Activity(12, this_year=False)


def d(value: str) -> Decimal:
	return Decimal(value)


def filed(period: Period, name: str, kz83: str = "1.00", kz39: str = "0") -> FiledReturn:
	return FiledReturn(period, name, d(kz83), d(kz39))


def months(year: int, first: int, last: int) -> tuple[Period, ...]:
	return tuple(Period.month(year, month) for month in range(first, last + 1))


# USt 5 E 2026, Beispiel: Kz 83 of the Voranmeldungen of the previous year sums up to 39.000 €, and the one for
# December credited the Sondervorauszahlung of 5.000 € in Kz 39.
MARCH = filed(Period.month(2026, 3), "UStVA-2026-00002", "19000.00")
DECEMBER = filed(Period.month(2026, 12), "UStVA-2026-00003", "20000.00", "5000.00")


class LatestPerPeriodTest(TestCase):
	def test_keeps_the_latest_filing_of_each_period(self):
		corrected = filed(Period.month(2026, 3), "UStVA-2026-00004", "19500.00")
		self.assertEqual(bridge.latest_per_period([DECEMBER, corrected, MARCH]), (corrected, DECEMBER))

	def test_lists_the_periods_in_the_order_of_the_year(self):
		quarter = filed(Period.quarter(2026, 1), "UStVA-2026-00001")
		october = filed(Period.month(2026, 10), "UStVA-2026-00009")
		self.assertEqual(bridge.latest_per_period([october, DECEMBER, quarter]), (quarter, october, DECEMBER))

	def test_takes_any_iterable(self):
		self.assertEqual(bridge.latest_per_period(iter([MARCH])), (MARCH,))
		self.assertEqual(bridge.latest_per_period([]), ())


class BaseRowsTest(TestCase):
	def test_a_row_per_filed_return_with_its_period_kz83_and_kz39(self):
		self.assertEqual(
			bridge.base_rows([MARCH, DECEMBER]),
			[
				{
					"period_label": "März 2026",
					"period_code": "03",
					"vat_return": "UStVA-2026-00002",
					"prior_filing": None,
					"kz83": d("19000.00"),
					"kz39": d("0"),
				},
				{
					"period_label": "Dezember 2026",
					"period_code": "12",
					"vat_return": "UStVA-2026-00003",
					"prior_filing": None,
					"kz83": d("20000.00"),
					"kz39": d("5000.00"),
				},
			],
		)

	def test_a_voranmeldung_filed_before_steuerbote_names_its_record(self):
		before = FiledReturn(
			Period.quarter(2026, 4), "VVS-2026-00004", d("-500.00"), d("1781.00"), prior=True
		)
		self.assertEqual(
			bridge.base_rows([before]),
			[
				{
					"period_label": "IV. Kalendervierteljahr 2026",
					"period_code": "44",
					"vat_return": None,
					"prior_filing": "VVS-2026-00004",
					"kz83": d("-500.00"),
					"kz39": d("1781.00"),
				}
			],
		)

	def test_the_amounts_of_the_rows_feed_the_base(self):
		rows = [{"kz83": 19000.0, "kz39": 0}, {"kz83": "20000", "kz39": 5000.0}, {"kz83": None, "kz39": None}]
		self.assertEqual(bridge.base_amounts(rows), ([d("19000.00"), d("20000.00"), d("0.00")], d("5000.00")))


def before(
	period: Period, name: str, kz83: str, kz39: str = "0.00", filed_on: date = date(2026, 3, 10)
) -> PriorFiling:
	return PriorFiling(period, name, filed_on, d(kz83), d(kz39))


class WithPriorTest(TestCase):
	"""The Voranmeldungen filed before Steuerbote count as filed, as their records hold them."""

	def test_a_year_filed_outside_steuerbote_makes_the_base(self):
		prior = [before(period, f"VVS-2026-{period.code}", "2500.00") for period in months(2026, 1, 11)]
		prior.append(before(Period.month(2026, 12), "VVS-2026-12", "-2000.00", "4000.00"))
		returns = bridge.with_prior([], prior)
		self.assertEqual(len(returns), 12)
		self.assertTrue(all(filed_return.prior for filed_return in returns))
		self.assertEqual(bridge.gaps(GapsTest.MONTHLY, 2026, returns), ())
		kz83, kz39 = bridge.base_amounts(bridge.base_rows(returns))
		result = bridge.sondervorauszahlung(kz83, kz39, WHOLE_YEAR, None)
		self.assertEqual(
			(result.computed_base, result.base, result.kz38), (d("29500.00"), d("29500.00"), d("2681"))
		)

	def test_a_return_filed_through_steuerbote_comes_first(self):
		prior = [
			before(Period.quarter(2026, 1), "VVS-2026-00001", "300.00"),
			before(Period.month(2026, 3), "VVS-2026-00002", "100.00"),
			before(Period.month(2026, 4), "VVS-2026-00003", "400.00"),
		]
		self.assertEqual(
			bridge.with_prior([MARCH, DECEMBER], prior),
			(
				MARCH,
				FiledReturn(Period.month(2026, 4), "VVS-2026-00003", d("400.00"), prior=True),
				DECEMBER,
			),
		)

	def test_the_latest_filing_before_steuerbote_of_a_period_counts(self):
		prior = [
			before(Period.month(2026, 5), "VVS-2026-00005", "100.00"),
			before(Period.month(2026, 5), "VVS-2026-00009", "150.00", filed_on=date(2026, 8, 1)),
		]
		self.assertEqual(
			bridge.with_prior([], prior),
			(FiledReturn(Period.month(2026, 5), "VVS-2026-00009", d("150.00"), prior=True),),
		)


class GapsTest(TestCase):
	MONTHLY = (PeriodRule(2026, "monthly"),)

	def test_names_each_period_without_a_filed_return(self):
		gaps = bridge.gaps(self.MONTHLY, 2026, [MARCH, DECEMBER])
		self.assertEqual(gaps, (*months(2026, 1, 2), *months(2026, 4, 11)))

	def test_a_year_with_every_return_filed_lacks_nothing(self):
		returns = [filed(period, period.code) for period in months(2026, 1, 12)]
		self.assertEqual(bridge.gaps(self.MONTHLY, 2026, returns), ())

	def test_follows_the_rhythm_of_the_settings(self):
		rules = (PeriodRule(2026, "quarterly"), PeriodRule(2026, "monthly", 10))
		returns = [filed(Period.quarter(2026, 2), "Q2"), filed(Period.month(2026, 11), "N")]
		self.assertEqual(
			bridge.gaps(rules, 2026, returns),
			(
				Period.quarter(2026, 1),
				Period.quarter(2026, 3),
				Period.month(2026, 10),
				Period.month(2026, 12),
			),
		)

	def test_months_without_a_voranmeldung_lack_nothing(self):
		rules = (PeriodRule(2026, "none"), PeriodRule(2026, "monthly", 10))
		returns = [filed(period, period.code) for period in months(2026, 10, 12)]
		self.assertEqual(bridge.gaps(rules, 2026, returns), ())

	def test_names_the_months_the_settings_set_no_filing_period_for(self):
		rules = (PeriodRule(2026, "monthly", 7),)
		returns = [filed(period, period.code) for period in months(2026, 7, 12)]
		self.assertEqual(bridge.gaps(rules, 2026, returns), months(2026, 1, 6))

	def test_a_filed_return_covers_its_months_whatever_the_settings_say_now(self):
		rules = (PeriodRule(2027, "monthly"),)
		returns = [filed(Period.quarter(2026, 1), "Q1")]
		self.assertEqual(bridge.gaps(rules, 2026, returns), months(2026, 4, 12))

	def test_starts_with_the_month_the_company_began_in(self):
		self.assertEqual(
			bridge.gaps(self.MONTHLY, 2026, [DECEMBER], first_month=11), (Period.month(2026, 11),)
		)

	def test_the_quarter_the_company_began_in_counts_whole(self):
		rules = (PeriodRule(2026, "quarterly"),)
		self.assertEqual(
			bridge.gaps(rules, 2026, [], first_month=5),
			(Period.quarter(2026, 2), Period.quarter(2026, 3), Period.quarter(2026, 4)),
		)

	def test_passes_on_what_is_no_year(self):
		with self.assertRaisesRegex(SettingsError, "four-digit year"):
			bridge.gaps(self.MONTHLY, 999, [])


class ActivityTest(TestCase):
	def test_a_company_without_a_date_of_establishment_was_active_all_year(self):
		self.assertEqual(bridge.activity(2027, None), WHOLE_YEAR)

	def test_a_company_that_began_before_the_previous_year_was_active_all_year(self):
		self.assertEqual(bridge.activity(2027, date(2019, 3, 1)), WHOLE_YEAR)

	def test_counts_the_months_of_the_previous_year_from_the_start(self):
		self.assertEqual(bridge.activity(2027, date(2026, 5, 15)), Activity(8, this_year=False))
		self.assertEqual(bridge.activity(2027, date(2026, 1, 1)), WHOLE_YEAR)

	def test_counts_the_months_of_the_year_for_a_start_in_the_year(self):
		self.assertEqual(bridge.activity(2027, date(2027, 3, 15)), Activity(10, this_year=True))

	def test_refuses_a_start_after_the_year(self):
		with self.assertRaises(BaseError) as caught:
			bridge.activity(2027, date(2028, 1, 1))
		self.assertIs(caught.exception.problem, BaseProblem.BEGAN_LATER)


class OverrideTest(TestCase):
	def test_takes_effect_with_a_reason(self):
		self.assertEqual(
			bridge.override_of(55000.0, " Januar bis Juni im Altsystem "),
			Override(d("55000.00"), "Januar bis Juni im Altsystem"),
		)

	def test_a_reason_makes_zero_an_override(self):
		self.assertEqual(
			bridge.override_of(0, "Keine Vorauszahlungen"), Override(d("0.00"), "Keine Vorauszahlungen")
		)

	def test_nothing_entered_is_no_override(self):
		self.assertIsNone(bridge.override_of(None, None))
		self.assertIsNone(bridge.override_of(0.0, "  "))

	def test_an_amount_without_a_reason_is_refused(self):
		with self.assertRaises(BaseError) as caught:
			bridge.override_of(55000.0, "")
		self.assertIs(caught.exception.problem, BaseProblem.MISSING_REASON)

	def test_a_surplus_is_a_negative_base(self):
		self.assertEqual(bridge.override_of("-1200.5", "Überschuss").amount, d("-1200.50"))


class SondervorauszahlungTest(TestCase):
	def test_follows_the_example_of_the_anleitung(self):
		self.assertEqual(
			bridge.sondervorauszahlung([d("19000.00"), d("20000.00")], d("5000.00"), WHOLE_YEAR, None),
			Sondervorauszahlung(
				kz83=d("39000.00"),
				kz39=d("5000.00"),
				computed_base=d("44000.00"),
				base=d("44000.00"),
				kz38=d("4000"),
			),
		)

	def test_the_base_by_hand_replaces_the_base_from_the_voranmeldungen(self):
		result = bridge.sondervorauszahlung(
			[d("19000.00"), d("20000.00")], d("5000.00"), WHOLE_YEAR, Override(d("55000.00"), "Altsystem")
		)
		self.assertEqual(
			(result.computed_base, result.base, result.kz38), (d("44000.00"), d("55000.00"), d("5000"))
		)

	def test_a_surplus_files_zero(self):
		result = bridge.sondervorauszahlung([d("-800.00"), d("300.00")], d("0"), WHOLE_YEAR, None)
		self.assertEqual((result.base, result.kz38), (d("-500.00"), d("0")))

	def test_a_start_in_the_previous_year_converts_the_vorauszahlungen_into_an_annual_sum(self):
		result = bridge.sondervorauszahlung(
			[d("1900.00"), d("3800.00")], d("0"), Activity(2, this_year=False), None
		)
		self.assertEqual(
			(result.kz83, result.computed_base, result.kz38), (d("5700.00"), d("34200"), d("3109"))
		)

	def test_a_start_in_the_year_takes_the_average_month_of_the_vorauszahlungen_expected(self):
		result = bridge.sondervorauszahlung(
			[], d("0"), Activity(10, this_year=True), Override(d("15000.00"), "Planung für 2027")
		)
		self.assertEqual(
			result,
			Sondervorauszahlung(
				kz83=d("0"), kz39=d("0"), computed_base=None, base=d("15000.00"), kz38=d("1500")
			),
		)

	def test_a_start_in_the_year_needs_the_vorauszahlungen_expected(self):
		with self.assertRaises(BaseError) as caught:
			bridge.sondervorauszahlung([], d("0"), Activity(10, this_year=True), None)
		self.assertIs(caught.exception.problem, BaseProblem.EXPECTED_NEEDED)

	def test_without_a_filed_return_the_base_is_entered_by_hand(self):
		with self.assertRaises(BaseError) as caught:
			bridge.sondervorauszahlung([], d("0"), WHOLE_YEAR, None)
		self.assertIs(caught.exception.problem, BaseProblem.NO_RETURNS)
		result = bridge.sondervorauszahlung([], d("0"), WHOLE_YEAR, Override(d("44000.00"), "Altsystem"))
		self.assertEqual((result.computed_base, result.base, result.kz38), (None, d("44000.00"), d("4000")))

	def test_passes_on_what_the_core_refuses(self):
		with self.assertRaisesRegex(ValueError, "Kz 39 takes no negative amount"):
			bridge.sondervorauszahlung([d("100.00")], d("-5.00"), WHOLE_YEAR, None)


class AmountsKeptTest(TestCase):
	"""Before a filing, base and Kz 38 are computed again from the table of the base and the base by hand."""

	computed = MappingProxyType(
		{
			"kz83": d("39000.00"),
			"kz39": d("5000.00"),
			"months_active": 12,
			"computed_base": d("44000.00"),
			"base": d("44000.00"),
			"sondervorauszahlung": d("4000"),
		}
	)

	def test_a_form_holds_what_its_base_gives(self):
		stored = {**self.computed, "kz83": 39000.0, "base": "44000", "months_active": 12, "remarks": "x"}
		self.assertTrue(bridge.amounts_kept(self.computed, stored))

	def test_a_value_that_differs_is_found(self):
		for field in self.computed:
			with self.subTest(field=field):
				self.assertFalse(bridge.amounts_kept(self.computed, {**self.computed, field: 1}))


class FormTest(TestCase):
	def doc(self, **values: object) -> dict[str, object]:
		"""The values of an Anmeldung der Sondervorauszahlung 2026 as the document holds them."""
		return {
			"year": 2026,
			"context": SVZ.value,
			"sondervorauszahlung": 4000.0,
			"is_correction": 0,
			"no_sepa_mandate": 0,
			"offset_requested": 0,
			"supplementary_code": "",
			"kz500_begruendung": None,
			**values,
		}

	def test_builds_the_anmeldung_der_sondervorauszahlung(self):
		form = bridge.form(self.doc(is_correction=1, offset_requested=1, no_sepa_mandate=1))
		self.assertEqual(
			form,
			Ust1H(2026, SVZ, d("4000"), corrected=True, no_sepa_mandate=True, offset_requested=True),
		)
		self.assertEqual(
			form.texts(), {"Jahr": "2026", "Kz10": "1", "Kz26": "1", "Kz29": "1", "Kz38": "4000"}
		)

	def test_builds_the_antrag_alone_without_kz38(self):
		self.assertEqual(bridge.form(self.doc(context=DF.value)).texts(), {"Jahr": "2026"})

	def test_carries_kz500_with_its_begruendung(self):
		form = bridge.form(self.doc(supplementary_code="2", kz500_begruendung="Siehe Anlage"))
		self.assertEqual((form.supplementary_code, form.begruendung), ("2", "Siehe Anlage"))

	def test_carries_the_code_of_the_key_kz500_keeps(self):
		for wording, code in bridge.SUPPLEMENTARY_INFORMATION.items():
			with self.subTest(wording=wording):
				form = bridge.form(self.doc(supplementary_code=wording, kz500_begruendung="Siehe Anlage"))
				self.assertEqual(form.texts()["Kz500"], code)

	def test_passes_on_what_the_form_refuses(self):
		with self.assertRaises(FormError) as caught:
			bridge.form(self.doc(offset_requested=1))
		self.assertEqual(caught.exception.rule.code, "11085150")

	def test_the_antrag_alone_takes_no_yes_field(self):
		with self.assertRaisesRegex(FormError, "carries no Kennzahl 10"):
			bridge.form(self.doc(context=DF.value, is_correction=1))

	def test_a_year_without_its_form_is_refused_by_the_core(self):
		with self.assertRaises(FormError) as caught:
			bridge.form(self.doc(year=LATEST_YEAR + 1))
		self.assertEqual(caught.exception.template, NO_LAYOUT)

	def test_builds_the_anmeldung_der_sondervorauszahlung_2027(self):
		form = bridge.form(
			self.doc(year=2027, is_correction=1, supplementary_code="1", kz500_begruendung="Anlage")
		)
		self.assertEqual(
			form, Ust1H(2027, SVZ, d("4000"), corrected=True, supplementary_code="1", begruendung="Anlage")
		)
		self.assertEqual(
			form.texts(),
			{"Jahr": "2027", "Kz10": "1", "Kz38": "4000", "Kz500": "1", "Kz500_Begruendung": "Anlage"},
		)


class OverdueTest(TestCase):
	"""A draft whose due date has passed: the Antrag is due by § 48 Abs. 1 Satz 1 UStDV, the Sondervorauszahlung by
	§ 48 Abs. 1 Satz 5 and Abs. 2 Satz 1 UStDV."""

	def test_a_draft_after_its_due_date_is_overdue(self):
		self.assertTrue(bridge.overdue(date(2026, 2, 10), date(2026, 2, 11), docstatus=0))

	def test_on_its_due_date_it_is_not(self):
		self.assertFalse(bridge.overdue(date(2026, 2, 10), date(2026, 2, 10), docstatus=0))

	def test_a_filed_form_or_one_without_due_date_is_not(self):
		self.assertFalse(bridge.overdue(date(2026, 2, 10), date(2026, 11, 25), docstatus=1))
		self.assertFalse(bridge.overdue(None, date(2026, 11, 25), docstatus=0))
