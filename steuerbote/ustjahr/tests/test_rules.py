"""The rules of Jahresdokumentation_E50_2026.ods that Steuerbote checks without ERiC, and its own checks.

The expected findings name every rule a case sets off, in the order of the JD, so a test fails as soon as a rule
fires that the case does not intend.
"""

import re
from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.ustjahr.calculation import entries
from steuerbote.ustjahr.form import CATALOGUES, Finding, Format, Severity
from steuerbote.ustjahr.rules import (
	DIGITS,
	EUROS,
	KU_BEFORE,
	KU_JANUARY,
	KU_LIMIT,
	KU_MIXED,
	KU_SWITCH,
	KU_SWITCH_ONLY,
	KZ_133,
	KZ_742,
	LEFT_TO_ERIC,
	LENGTH,
	LOCAL_RULES,
	MANDATORY,
	MESSAGES,
	NIL,
	OFFSET,
	PARAGRAPH,
	RATE,
	RULE,
	SIGN,
	SUM_ALONE,
	SUM_DIFFERS,
	SUM_MISSING,
	SUM_TOLERANCE,
	TOGETHER,
	VERZICHT,
	VERZICHT_HINT,
	Pattern,
	Rate,
	SumAlone,
	SumDiffers,
	SumMissing,
	Together,
	check,
)
from steuerbote.ustva.rounding import ZERO
from steuerbote.ustva.years import UnknownYearError

CATALOGUE = CATALOGUES[2026]
D = Decimal
# The amounts of the example Beispiele/USt_2026.xml of the ERiC documentation and invented details of a company.
AMOUNTS = entries(
	CATALOGUE,
	{"E3003405": D("5276"), "E3003406": D("1002.44"), "E3003703": D("-14292"), "E3003704": D("-1000.44")},
	D("902.00"),
)
DETAILS = {
	"E3000401": "DE123456789",
	"E3000901": "Muster GmbH",
	"E3001101": "Musterstraße",
	"E3001203": "1",
	"E3001206": "12345",
	"E3001207": "Musterstadt",
	"E3002203": "1",
}
CLEAN = {**DETAILS, **AMOUNTS}
TAXED = {"E3003303": D("1000"), "E3003304": D("190.00")}


def run(
	*, without: tuple[str, ...] = (), today: date | None = None, **changes: object
) -> tuple[Finding, ...]:
	values = {key: value for key, value in CLEAN.items() if key not in without}
	values.update(changes)
	return check(2026, values, today)


def filing(values: dict[str, Decimal], soll: str = "0.00", **details: object) -> dict[str, object]:
	"""The given amounts with the sums of the form, the details of the company and further details."""
	return {**DETAILS, **entries(CATALOGUE, values, D(soll)), **details}


def codes(found: tuple[Finding, ...]) -> list[str]:
	return [finding.code for finding in found]


SAMPLES = {
	Format.EUROS: D("100"),
	Format.UNSIGNED_EUROS: D("100"),
	Format.CENTS: D("19.00"),
	Format.UNSIGNED_CENTS: D("19.00"),
	Format.YES: True,
	Format.CROSS: True,
	Format.LIST: "1",
	Format.TEXT: "Text",
	Format.DATE: date(2026, 7, 1),
	Format.DAYS: (date(2026, 3, 1), date(2026, 6, 30)),
}


def sample(element: str) -> object:
	"""A value of the field that is not zero."""
	return SAMPLES[CATALOGUE.field(element).format]


class CleanReturnTest(TestCase):
	def test_a_return_that_keeps_the_rules_has_no_findings(self):
		self.assertEqual(run(), ())

	def test_findings_keep_the_order_of_the_jahresdokumentation(self):
		self.assertEqual(codes(run(without=("E3000901", "E3011401"))), ["30096", "30620"])

	def test_each_finding_has_the_severity_of_its_rule(self):
		(finding,) = run(without=("E3000401",))
		self.assertEqual((finding.code, finding.severity), ("30008", Severity.HINT))
		self.assertFalse(finding.blocking)


class MandatoryTest(TestCase):
	def test_kz_816_line_125_and_kz_820_are_mandatory(self):
		for element, code, name, line in (
			("E3011101", "30070", "Kz 816", 124),
			("E3011301", "30915", "E3011301", 125),
			("E3011401", "30620", "Kz 820", 126),
		):
			with self.subTest(element=element):
				found = {finding.code: finding for finding in run(without=(element,))}
				self.assertEqual(
					found[code], Finding(code, Severity.ERROR, MANDATORY, (name, line), (element,))
				)

	def test_the_name_of_the_company_is_mandatory(self):
		(finding,) = run(without=("E3000901",))
		self.assertEqual(finding, Finding("30096", Severity.ERROR, MANDATORY, ("E3000901", 5), ("E3000901",)))
		self.assertEqual(finding.text, "E3000901 in line 5 is mandatory.")

	def test_kz_133_is_mandatory_unless_only_section_19_applies(self):
		(finding,) = run(without=("E3002203",))
		self.assertEqual(finding, Finding("30093", Severity.ERROR, KZ_133, (), ("E3002203",)))
		kleinunternehmer = filing({"E3104701": D("20000")})
		del kleinunternehmer["E3002203"]
		self.assertEqual(codes(check(2026, kleinunternehmer)), [])

	def test_a_return_needs_an_amount_of_the_form(self):
		"""Rule 30449; its list of amounts leaves out the taxes that their bases bring along."""
		values = {**DETAILS, "E3011101": ZERO, "E3011301": D("100.00"), "E3011401": D("-100.00")}
		self.assertEqual(check(2026, values), (Finding("30449", Severity.ERROR, NIL, (), ("E3003303",)),))
		self.assertEqual(check(2026, filing({}, "100.00")), ())
		values.update({"E3011301": ZERO, "E3011401": ZERO})
		self.assertEqual(check(2026, values), ())


class SumsTest(TestCase):
	def test_a_sum_that_does_not_follow_from_its_lines(self):
		found = run(
			E3006001=D("3.00"),
			E3009201=D("3.00"),
			E3009801=D("3.00"),
			E3010201=D("3.00"),
			E3010601=D("3.00"),
			E3011101=D("3.00"),
			E3011401=D("-899.00"),
		)
		self.assertEqual(
			found,
			(Finding("30314", Severity.ERROR, SUM_DIFFERS, ("E3006001", 41, "3,00", "2,00"), ("E3006001",)),),
		)

	def test_a_sum_missing_although_its_lines_are_given(self):
		found = run(without=("E3006001",))
		self.assertEqual(codes(found), ["30364", "30452"])
		self.assertEqual(
			found[0], Finding("30364", Severity.ERROR, SUM_MISSING, ("E3006001", 41), ("E3006001",))
		)

	def test_a_sum_given_although_none_of_its_lines_is(self):
		found = run(E3006901=D("0.00"))
		self.assertEqual(codes(found), ["30150", "30901"])
		self.assertEqual(
			found[1], Finding("30901", Severity.ERROR, SUM_ALONE, ("E3006901", 93), ("E3006901",))
		)

	def test_a_line_brought_forward(self):
		self.assertEqual(codes(run(E3009201=D("2.01"))), ["30232", "30630"])
		self.assertEqual(codes(run(without=("E3009201",))), ["30142", "30905"])
		emptied = run(without=("E3006001", "E3003405", "E3003406", "E3003703", "E3003704"))
		self.assertEqual(codes(emptied), ["30452", "30449"])

	def test_kz_816_may_be_10_euros_away_from_line_122_less_line_123(self):
		"""Rule 30636 with „UngleichMitToleranz10“."""
		self.assertEqual(run(E3011101=D("11.99"), E3011401=D("-890.01")), ())
		found = run(E3011101=D("12.01"), E3011401=D("-889.99"))
		self.assertEqual(
			found,
			(
				Finding(
					"30636", Severity.ERROR, SUM_TOLERANCE, ("Kz 816", 124, "12,01", "2,00"), ("E3011101",)
				),
			),
		)

	def test_kz_820_is_kz_816_less_line_125(self):
		self.assertEqual(codes(run(E3011401=D("-899.99"))), ["30638"])

	def test_kz_816_and_kz_820_without_their_lines(self):
		values = {**DETAILS, "E3003303": ZERO, "E3003304": ZERO, "E3011101": D("5.00"), "E3011301": ZERO}
		self.assertEqual(codes(check(2026, {**values, "E3011401": D("5.00")})), ["30364", "30910"])
		values = {**DETAILS, "E3003303": ZERO, "E3003304": ZERO, "E3011401": D("5.00")}
		self.assertEqual(codes(check(2026, values)), ["30364", "30070", "30915", "30911"])


class PairTest(TestCase):
	def test_a_base_and_its_tax_go_together(self):
		found = run(
			without=("E3003406",),
			E3006001=D("-1000.44"),
			E3009201=D("-1000.44"),
			E3009801=D("-1000.44"),
			E3010201=D("-1000.44"),
			E3010601=D("-1000.44"),
			E3011101=D("-1000.44"),
			E3011401=D("-1902.44"),
		)
		self.assertEqual(
			found,
			(Finding("30650", Severity.ERROR, TOGETHER, ("Kz 178", "E3003406"), ("E3003405", "E3003406")),),
		)
		self.assertEqual(found[0].text, "Kz 178 and E3003406 go together: give both or neither.")

	def test_the_ergaenzende_angaben_and_their_text_go_together(self):
		self.assertEqual(codes(run(E3002201="1")), ["30917"])
		self.assertEqual(codes(run(E3002201="1", E3002202="Erläuterung")), ["30937"])

	def test_kz_789_needs_kz_742(self):
		"""New in 2026, rules 30013 and 30014: the Erwerb of the first buyer (§ 25b Absatz 3 UStG) and his Lieferung."""
		self.assertEqual(codes(check(2026, filing({"E3100801": D("1000")}))), ["30013"])
		self.assertEqual(check(2026, filing({"E3100801": D("1000"), "E3101801": D("1100")})), ())
		found = check(2026, filing({"E3100801": D("1000"), "E3101801": D("900")}))
		self.assertEqual(
			found, (Finding("30014", Severity.ERROR, KZ_742, ("900", "1000"), ("E3101801", "E3100801")),)
		)


class RateTest(TestCase):
	def test_a_tax_within_one_euro_of_its_rate_passes(self):
		self.assertEqual(check(2026, filing({"E3003303": D("10000"), "E3003304": D("1901.00")})), ())
		self.assertEqual(check(2026, filing({"E3003303": D("10000"), "E3003304": D("1899.00")})), ())

	def test_a_tax_more_than_one_euro_off_its_rate_fails(self):
		(finding,) = check(2026, filing({"E3003303": D("10000"), "E3003304": D("1901.01")}))
		expected = ("E3003304", 24, "19", "1.901,01", "1.900,00")
		self.assertEqual(finding, Finding("30639", Severity.ERROR, RATE, expected, ("E3003304", "E3003303")))
		self.assertEqual(
			finding.text,
			"The tax E3003304 in line 24 is more than one euro away from 19 % of its base: 1.901,01 instead of about "
			"1.900,00.",
		)

	def test_the_taxes_of_the_last_buyer_in_a_dreiecksgeschaeft_are_checked_too(self):
		self.assertEqual(
			codes(check(2026, filing({"E3102301": D("1000"), "E3102302": D("75.00")}))), ["30661"]
		)


class SalesTest(TestCase):
	def test_a_verzicht_on_an_exemption_needs_taxed_sales(self):
		"""New in 2026: rules 30015 and 30016 on line 75."""
		found = check(2026, filing({"E3105201": D("1000"), "E3002801": D("1000")}))
		self.assertEqual(found, (Finding("30015", Severity.ERROR, VERZICHT, (), ("E3105201",)),))
		found = check(2026, filing({"E3105201": D("1000"), "E3003303": D("500"), "E3003304": D("95.00")}))
		self.assertEqual(found, (Finding("30016", Severity.HINT, VERZICHT_HINT, (), ("E3105201",)),))
		self.assertEqual(
			check(2026, filing({"E3105201": D("500"), "E3003303": D("500"), "E3003304": D("95.00")})), ()
		)

	def test_a_refund_offset_needs_a_refund(self):
		"""Rule 30011: Kz 129 only with Kz 820 below zero, unless the return is a correction."""
		self.assertEqual(run(E3001701=True), ())
		found = check(2026, filing(TAXED, E3001701=True))
		self.assertEqual(found, (Finding("30011", Severity.ERROR, OFFSET, (), ("E3001701",)),))
		self.assertEqual(codes(check(2026, filing(TAXED, E3001701=True, E3000601=True))), ["30002"])


class KleinunternehmerTest(TestCase):
	"""The rules of line 53 and of Kz 136, the date of a switch from the Kleinunternehmer-Regelung (§ 19 UStG)."""

	def found(self, values: dict[str, Decimal], switch: date | None = None) -> tuple[Finding, ...]:
		details = {} if switch is None else {"E3001601": switch}
		return check(2026, filing(values, **details))

	def test_sales_under_section_19_next_to_taxed_sales_without_a_switch(self):
		"""Rule 30098 hints at Kz 133, which a return of a Kleinunternehmer does not need."""
		found = self.found({"E3104701": D("20000"), **TAXED})
		self.assertEqual(codes(found), ["30098", "30424"])
		self.assertEqual(found[1], Finding("30424", Severity.ERROR, KU_MIXED, (), ("E3104701", "E3001601")))

	def test_sales_above_the_limit_of_section_19(self):
		found = self.found({"E3104701": D("100001")})
		self.assertEqual(codes(found), ["30098", "30413"])
		self.assertEqual(found[1], Finding("30413", Severity.ERROR, KU_LIMIT, ("100001",), ("E3104701",)))
		self.assertEqual(codes(self.found({"E3104701": D("100000")})), ["30098"])

	def test_a_switch_during_the_year(self):
		switch = date(2026, 7, 1)
		self.assertEqual(self.found({"E3104701": D("20000"), **TAXED}, switch), ())
		only = self.found({"E3104701": D("20000")}, switch)
		self.assertEqual(
			only, (Finding("30412", Severity.ERROR, KU_SWITCH_ONLY, (), ("E3001601", "E3104701")),)
		)
		before = self.found(TAXED, switch)
		self.assertEqual(before, (Finding("30414", Severity.ERROR, KU_BEFORE, (), ("E3001601", "E3104701")),))
		neither = self.found({"E3006201": D("10.00")}, switch)
		self.assertEqual(
			neither, (Finding("30007", Severity.ERROR, KU_SWITCH, (), ("E3001601", "E3104701")),)
		)

	def test_a_switch_on_the_first_of_january_leaves_no_sales_under_section_19(self):
		january = date(2026, 1, 1)
		self.assertEqual(
			self.found({"E3104701": D("20000")}, january),
			(Finding("30423", Severity.ERROR, KU_JANUARY, (), ("E3001601", "E3104701")),),
		)
		self.assertEqual(
			self.found({"E3104701": D("20000"), **TAXED}, january),
			(Finding("30422", Severity.ERROR, KU_JANUARY, (), ("E3001601", "E3104701")),),
		)
		self.assertEqual(self.found(TAXED, january), ())

	def test_a_kleinunternehmer_takes_no_vorsteuer(self):
		"""Rule 30705 of line 53: Vorsteuer next to sales under § 19 UStG without a switch."""
		self.assertEqual(
			codes(self.found({"E3104701": D("20000"), "E3006201": D("10.00")})), ["30098", "30705"]
		)

	def test_the_date_of_a_switch_lies_in_the_year(self):
		self.assertEqual(codes(self.found(TAXED, date(2025, 7, 1))), ["30006"])


class PatternTest(TestCase):
	"""Rules made of fields given or not share one message: the code and the condition of the rule."""

	def test_a_hausnummerzusatz_needs_a_hausnummer(self):
		found = run(without=("E3001203",), E3001204="a")
		self.assertEqual(codes(found), ["30092", "30097"])
		self.assertEqual(
			found[0],
			Finding(
				"30092",
				Severity.ERROR,
				RULE,
				("30092", "FeldAngegeben(E3001204) Und FeldNichtAngegeben(E3001203)"),
				("E3001204", "E3001203"),
			),
		)
		self.assertEqual(
			found[0].text,
			"ERiC rule 30092 applies: FeldAngegeben(E3001204) Und FeldNichtAngegeben(E3001203).",
		)

	def test_a_street_without_a_hausnummer_is_a_hint(self):
		self.assertEqual(
			[(f.code, f.severity) for f in run(without=("E3001203",))], [("30097", Severity.HINT)]
		)

	def test_an_address_needs_street_plz_and_city(self):
		self.assertEqual(codes(run(without=("E3001206",))), ["30675"])
		self.assertEqual(codes(run(without=("E3001101", "E3001203", "E3001206", "E3001207"))), ["30094"])

	def test_a_foreign_address_without_kz_125(self):
		self.assertEqual(codes(run(E3001209="Österreich")), ["30675", "30677"])

	def test_the_flags_and_amounts_of_section_15a_go_together(self):
		self.assertEqual(codes(check(2026, filing({}, E3007601=True))), ["30925", "30931"])
		self.assertEqual(codes(check(2026, filing({"E3008701": D("10.00")}))), ["30926"])
		reasoned = filing({"E3008701": D("10.00")}, E3007601=True, E3007801=True)
		self.assertEqual(check(2026, reasoned), ())

	def test_the_reasons_of_section_15a(self):
		flagged = {"E3007601": True}
		amount = {"E3008701": D("10.00")}
		self.assertEqual(codes(check(2026, filing(amount, **flagged, E3007901=True))), ["30933"])
		self.assertEqual(codes(check(2026, filing(amount, **flagged, E3008001=True))), ["30931", "30934"])
		both = filing(amount, **flagged, E3007901=True, E3008401=True)
		self.assertEqual(codes(check(2026, both)), ["30935"])
		text = filing(amount, **flagged, E3007901=True, E3008402="Umbau")
		self.assertEqual(codes(check(2026, text)), ["30933", "30936"])

	def test_vorsteuer_without_the_tax_it_answers(self):
		for element, code in (
			("E3006503", "30948"),
			("E3006502", "30949"),
			("E3006801", "30951"),
			("E3006301", "30312"),
		):
			with self.subTest(element=element):
				self.assertEqual(codes(check(2026, filing({element: D("10.00")}))), [code])

	def test_the_minderungen_of_section_17_need_their_bases(self):
		self.assertEqual(codes(check(2026, filing({"E3106101": D("100")}))), ["30940"])
		self.assertEqual(codes(check(2026, filing({"E3007001": D("10.00")}))), ["30942"])

	def test_a_negative_amount_without_its_minderung_is_a_hint(self):
		self.assertEqual(
			codes(check(2026, filing({"E3003303": D("-100"), "E3003304": D("-19.00")}))), ["30941"]
		)
		self.assertEqual(codes(check(2026, filing({"E3006201": D("-10.00")}))), ["30943"])

	def test_the_geschaeftsveraeusserung_im_ganzen(self):
		self.assertEqual(codes(check(2026, filing({"E3105602": D("10000")}))), ["30807"])
		self.assertEqual(codes(run(E3105602=ZERO)), ["30807", "30815"])

	def test_a_return_of_a_kleinunternehmer_names_the_way_of_taxation_in_vain(self):
		self.assertEqual(codes(check(2026, filing({"E3104701": D("20000")}))), ["30098"])


class DaysTest(TestCase):
	"""Lines 19 and 20, the spans of a business that did not last the whole year."""

	def test_a_span_of_the_whole_year_is_a_hint(self):
		self.assertEqual(codes(run(E3001401=(date(2026, 1, 1), date(2026, 12, 31)))), ["30676"])

	def test_the_second_span_needs_the_first_and_begins_after_it(self):
		self.assertEqual(codes(run(E3001501=(date(2026, 3, 1), date(2026, 6, 30)))), ["30086"])
		spans = {
			"E3001401": (date(2026, 1, 1), date(2026, 4, 30)),
			"E3001501": (date(2026, 3, 1), date(2026, 12, 31)),
		}
		self.assertEqual(codes(run(**spans)), ["30081"])

	def test_a_return_filed_during_its_year_without_a_span_is_a_hint(self):
		self.assertEqual(codes(run(today=date(2026, 12, 1))), ["30089"])
		self.assertEqual(run(today=date(2027, 1, 4)), ())
		self.assertEqual(run(today=date(2026, 12, 1), E3001401=(date(2026, 3, 1), date(2026, 12, 31))), ())


class MoreRulesTest(TestCase):
	def test_the_rules_of_the_less_common_lines(self):
		self.assertEqual(codes(check(2026, filing({"E3005001": D("100"), "E3005002": ZERO}))), ["30916"])
		luf = {"E3005005": D("1000"), "E3005006": D("50.00"), "E3005801": D("500")}
		self.assertEqual(codes(check(2026, filing(luf))), ["30946"])

	def test_the_limit_of_10000_euros_of_lines_77_and_78(self):
		"""§ 3a Absatz 5 Satz 3 and § 3c Absatz 4 Satz 1 UStG, as USt 2 E 2026 explains lines 77 and 78."""
		self.assertEqual(codes(check(2026, filing({"E3105101": D("10001")}))), ["30809"])
		self.assertEqual(codes(check(2026, filing({"E3105102": D("10001")}))), ["30812"])
		both = {"E3105101": D("100"), "E3105102": D("100"), "E3003303": D("500"), "E3003304": D("95.00")}
		self.assertEqual(codes(check(2026, filing(both))), ["30813"])
		self.assertEqual(
			codes(check(2026, filing({"E3105101": D("600"), "E3003303": D("500"), "E3003304": D("95.00")}))),
			["30816"],
		)
		self.assertEqual(codes(check(2026, filing({"E3105101": D("600")}))), ["30017"])

	def test_the_mitwirkung_of_a_steuerberatung(self):
		self.assertEqual(codes(run(E3002506="4711")), ["30944", "30945"])
		mitwirkung = {
			"E3002506": "4711",
			"E3002501": "Muster",
			"E3002503": "Weg 1",
			"E3002504": "12345 Ort",
			"E3002602": True,
		}
		self.assertEqual(run(**mitwirkung), ())


class OwnChecksTest(TestCase):
	"""Checks of Steuerbote that no rule of the JD states, before the rules."""

	def test_lines_46_52_and_54_name_their_paragraph(self):
		found = check(2026, filing({"E3104502": D("1000")}))
		self.assertEqual(
			found, (Finding("PARAGRAF-FEHLT", Severity.ERROR, PARAGRAPH, (52,), ("E3104502", "E3104501")),)
		)
		self.assertEqual(check(2026, filing({"E3104502": D("1000")}, E3104501="14")), ())

	def test_a_field_without_sign_takes_no_negative_amount(self):
		found = check(2026, filing({"E3102901": D("-1.00")}))
		self.assertEqual(
			found[0], Finding("VORZEICHEN", Severity.ERROR, SIGN, ("Kz 317", 39, "-1.00"), ("E3102901",))
		)

	def test_an_amount_has_at_most_twelve_digits_before_the_comma(self):
		found = check(2026, filing({"E3002801": D("1000000000000")}))
		expected = ("Kz 157", 30, 12, "1000000000000")
		self.assertEqual(found[0], Finding("STELLEN", Severity.ERROR, DIGITS, expected, ("E3002801",)))
		self.assertEqual(check(2026, filing({"E3002801": D("999999999999")})), ())

	def test_the_umfang_der_verwendung_has_fifteen(self):
		self.assertEqual(run(E3007404=D("999999999999999.99")), ())
		(finding,) = run(E3007404=D("1000000000000000.00"))
		expected = ("E3007404", 95, 15, "1000000000000000.00")
		self.assertEqual(finding, Finding("STELLEN", Severity.ERROR, DIGITS, expected, ("E3007404",)))

	def test_a_whole_euro_field_takes_no_cents(self):
		found = run(E3003405=D("5276.50"))
		self.assertEqual(
			found[0], Finding("VOLLE-EURO", Severity.ERROR, EUROS, ("Kz 178", 25, "5276.50"), ("E3003405",))
		)

	def test_a_text_takes_its_length(self):
		found = run(E3001203="12345")
		self.assertEqual(
			found[0], Finding("LAENGE", Severity.ERROR, LENGTH, ("E3001203", 9, 4, 5), ("E3001203",))
		)

	def test_refuses_values_of_the_wrong_field_or_type(self):
		with self.assertRaisesRegex(ValueError, "Form USt 2 A 2026 has no field E9999999"):
			run(E9999999=D("1"))
		with self.assertRaisesRegex(TypeError, "E3003405 takes a Decimal, not float"):
			run(E3003405=5276.0)
		with self.assertRaisesRegex(TypeError, "E3000901 takes a str, not int"):
			run(E3000901=1)
		with self.assertRaisesRegex(TypeError, "E3001601 takes a date, not str"):
			run(E3001601="2026-07-01")
		with self.assertRaisesRegex(TypeError, "E3001401 takes a span of two dates"):
			run(E3001401=date(2026, 3, 1))
		with self.assertRaisesRegex(TypeError, "E3000601 takes True"):
			run(E3000601="1")


class EveryRuleTest(TestCase):
	"""Each rule of a shape sets itself off in a case built from its fields, and keeps quiet without that case.

	The clean return gives the start, and a field set to None is left out. The cases of the other test classes pin
	the rules with their exact findings.
	"""

	def rules(self, *shapes: type) -> list:
		found = [rule for rule in LOCAL_RULES[2026] if isinstance(rule, shapes)]
		self.assertTrue(found)
		return found

	def found(self, values: dict[str, object]) -> dict[str, Finding]:
		given = {element: value for element, value in values.items() if value is not None}
		return {finding.code: finding for finding in check(2026, given)}

	def assertFires(self, code: str, values: dict[str, object], template: str) -> None:
		found = self.found(values)
		self.assertIn(code, found)
		self.assertEqual(found[code].template, template)

	def assertQuiet(self, code: str, values: dict[str, object]) -> None:
		self.assertNotIn(code, self.found(values))

	def test_each_pair(self):
		for rule in self.rules(Together):
			first, second = rule.elements
			with self.subTest(code=rule.code):
				self.assertFires(rule.code, {**CLEAN, first: sample(first)} | {second: None}, TOGETHER)
				self.assertQuiet(rule.code, {**CLEAN, first: sample(first), second: sample(second)})

	def test_each_rate_line(self):
		for rule in self.rules(Rate):
			exact = D("1000") * rule.rate / 100
			with self.subTest(code=rule.code):
				self.assertFires(
					rule.code, {**CLEAN, rule.base: D("1000"), rule.tax: exact + D("1.01")}, RATE
				)
				self.assertQuiet(rule.code, {**CLEAN, rule.base: D("1000"), rule.tax: exact + D("1.00")})

	def test_each_sum_that_differs_from_its_lines(self):
		for rule in self.rules(SumDiffers):
			(part, _sign), *_ = rule.parts
			values = {part: sample(part), **CLEAN}
			expected = sum((sign * values.get(element, ZERO) for element, sign in rule.parts), ZERO)
			template = SUM_TOLERANCE if rule.tolerance else SUM_DIFFERS
			with self.subTest(code=rule.code):
				self.assertFires(rule.code, {**values, rule.total: expected + D("50.00")}, template)
				self.assertQuiet(rule.code, {**values, rule.total: expected + rule.tolerance})

	def test_each_sum_missing_although_a_line_is_given(self):
		for rule in self.rules(SumMissing):
			(part, _sign), *_ = rule.parts
			with self.subTest(code=rule.code):
				self.assertFires(rule.code, {**CLEAN, part: sample(part)} | {rule.total: None}, SUM_MISSING)
				self.assertQuiet(rule.code, {**CLEAN, part: sample(part), rule.total: sample(rule.total)})

	def test_each_sum_given_although_none_of_its_lines_is(self):
		for rule in self.rules(SumAlone):
			alone = {**CLEAN, rule.total: sample(rule.total)} | dict.fromkeys(part for part, _ in rule.parts)
			(part, _sign), *_ = rule.parts
			with self.subTest(code=rule.code):
				self.assertFires(rule.code, alone, SUM_ALONE)
				self.assertQuiet(rule.code, {**alone, part: sample(part)})

	def test_each_pattern(self):
		for rule in self.rules(Pattern):
			values = {**CLEAN, **{element: sample(element) for element in (*rule.given, *rule.all_of)}}
			values |= dict.fromkeys((*rule.absent, *rule.none_of, *rule.not_all_of[:1]))
			if rule.any_of:
				values[rule.any_of[0]] = sample(rule.any_of[0])
			if rule.given:
				quiet = values | {rule.given[0]: None}
			elif rule.any_of:
				quiet = values | dict.fromkeys(rule.any_of)
			elif rule.all_of:
				quiet = values | {rule.all_of[0]: None}
			elif rule.absent:
				quiet = {**values, rule.absent[0]: sample(rule.absent[0])}
			else:
				quiet = {**values, rule.none_of[0]: sample(rule.none_of[0])}
			with self.subTest(code=rule.code):
				self.assertFires(rule.code, values, MANDATORY if rule.mandatory else RULE)
				self.assertQuiet(rule.code, quiet)


class ConditionTest(TestCase):
	"""Each local rule states its condition in the words of the JD; test_documentation.py compares them with the JD."""

	def condition(self, code: str) -> str:
		(rule,) = (rule for rule in LOCAL_RULES[2026] if rule.code == code)
		return rule.condition

	def assertConditions(self, conditions: dict[str, str]) -> None:
		for code, condition in conditions.items():
			with self.subTest(code=code):
				self.assertEqual(self.condition(code), condition)

	def test_of_a_pair_and_of_a_rate_line(self):
		self.assertConditions(
			{
				"30649": "FelderNichtGemeinsamAngegeben(E3003303, E3003304)",
				"30013": (
					"MindestensEinFeldAngegeben(E3100801, E3101801) Und "
					"FelderNichtGemeinsamAngegeben(E3100801, E3101801)"
				),
				"30642": (
					"FeldAngegeben(E3004402) Und FeldAngegeben(E3004401) Und [E3004402] UngleichMitToleranz1 "
					"{0.07 * [E3004401]}"
				),
			}
		)

	def test_of_the_sums(self):
		self.assertConditions(
			{
				"30232": "FeldAngegeben(E3009201) Und FeldAngegeben(E3006001) Und [E3009201] != [E3006001]",
				"30142": "FeldAngegeben(E3006001) Und FeldNichtAngegeben(E3009201)",
				"30452": "FeldAngegeben(E3009201) Und FeldNichtAngegeben(E3006001)",
				"30356": (
					"FeldAngegeben(E3102401) Und MindestensEinFeldAngegeben(E3101702, E3102302, E3102304) Und "
					"[E3102401] != Summe(E3101702, E3102302, E3102304)"
				),
				"30406": "FeldNichtAngegeben(E3102401) Und MindestensEinFeldAngegeben(E3101702, E3102302, E3102304)",
				"30802": "FeldAngegeben(E3102401) Und KeinFeldAngegeben(E3101702, E3102302, E3102304)",
				"30638": (
					"FeldAngegeben(E3011401) Und MindestensEinFeldAngegeben(E3011101, E3011301) Und "
					"[E3011401] != [E3011101]-[E3011301]"
				),
				"30636": (
					"FeldAngegeben(E3011101) Und MindestensEinFeldAngegeben(E3010601, E3010602) Und "
					"[E3011101] UngleichMitToleranz10 [E3010601]-[E3010602]"
				),
				"30910": "FeldAngegeben(E3011101) Und [E3011101] != 0 Und KeinFeldAngegeben(E3010601, E3010602)",
			}
		)

	def test_of_patterns_and_of_rules_written_out(self):
		self.assertConditions(
			{
				"30096": "KontextAngegeben(/USt2A) Und FeldNichtAngegeben(E3000901)",
				"30937": "AlleFelderAngegeben(E3002201, E3002202)",
				"30944": (
					"MindestensEinFeldAngegeben(E3002506) Und "
					"NichtAlleFelderOderKeinFeldAngegeben(E3002501, E3002503, E3002504)"
				),
				"30014": "AlleFelderAngegeben(E3100801, E3101801) Und [E3101801] < [E3100801]",
			}
		)

	def test_every_condition_names_fields_of_the_form(self):
		"""Rule 30449 names three amounts of Anlage UN as well."""
		elements = {field.element for field in CATALOGUE.fields}
		for rule in LOCAL_RULES[2026]:
			with self.subTest(code=rule.code):
				named = set(re.findall(r"E\d{7}", rule.condition))
				self.assertTrue(named)
				expected = {"E3201101", "E3201902", "E3201901"} if rule.code == "30449" else set()
				self.assertEqual(named - elements, expected)


class TableTest(TestCase):
	def test_every_rule_of_the_year_is_checked_or_left_to_eric_with_its_reason(self):
		local = [rule.code for rule in LOCAL_RULES[2026]]
		self.assertEqual(len(local), len(set(local)))
		self.assertEqual(set(local) | set(LEFT_TO_ERIC[2026]), {rule.code for rule in CATALOGUE.rules})
		self.assertEqual(set(local) & set(LEFT_TO_ERIC[2026]), set())
		self.assertEqual(sorted(LEFT_TO_ERIC[2026]), ["30087", "30088", "30225", "30313", "30938", "30939"])
		for reason in LEFT_TO_ERIC[2026].values():
			self.assertTrue(reason)

	def test_local_rules_keep_the_order_of_the_jahresdokumentation(self):
		order = [rule.code for rule in CATALOGUE.rules]
		local = [rule.code for rule in LOCAL_RULES[2026]]
		self.assertEqual(local, sorted(local, key=order.index))

	def test_the_rules_the_contract_names_are_checked(self):
		local = {rule.code for rule in LOCAL_RULES[2026]}
		required = {
			*("30096", "30093", "30070", "30915", "30620", "30449"),
			*("30630", "30632", "30634", "30636", "30638"),
			*("30905", "30907", "30909", "30910", "30911", "30912", "30913", "30914"),
			*("30649", "30650", "30651", "30652", "30653", "30654", "30655"),
			*("30091", "30115", "30120", "30125", "30131", "30137", "30139", "30147"),
			*(
				"30639",
				"30640",
				"30641",
				"30642",
				"30643",
				"30644",
				"30656",
				"30658",
				"30660",
				"30661",
				"30012",
			),
			*("30007", "30013", "30014", "30015", "30016"),
			*("30412", "30413", "30414", "30422", "30423", "30424"),
		}
		self.assertLessEqual(required, local)

	def test_a_year_without_rules_is_refused(self):
		with self.assertRaisesRegex(UnknownYearError, "2027"):
			check(2027, {})


class MessagesTest(TestCase):
	def test_lists_every_template_once_for_the_translations(self):
		templates = (
			MANDATORY,
			TOGETHER,
			SUM_DIFFERS,
			SUM_TOLERANCE,
			SUM_MISSING,
			SUM_ALONE,
			RATE,
			RULE,
			NIL,
			KZ_133,
			KZ_742,
			VERZICHT,
			VERZICHT_HINT,
			KU_SWITCH,
			KU_SWITCH_ONLY,
			KU_LIMIT,
			KU_BEFORE,
			KU_JANUARY,
			KU_MIXED,
			OFFSET,
			PARAGRAPH,
			SIGN,
			DIGITS,
			LENGTH,
			EUROS,
		)
		self.assertEqual(sorted(MESSAGES), sorted(templates))
		self.assertEqual(len(set(MESSAGES)), len(MESSAGES))
