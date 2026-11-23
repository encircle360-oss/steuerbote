"""The profiles of the E-Bilanz and the Offenlegung, against the mini taxonomy (steuerbote/xbrl/tests/mini.py), with
the reports of steuerbote/xbrl/tests/test_checks.py."""

from datetime import date
from unittest import TestCase

from steuerbote.xbrl import checks, writer
from steuerbote.xbrl.checks import Code, Facets
from steuerbote.xbrl.facts import Item, Period, Periods, nil
from steuerbote.xbrl.profiles import DISCLOSURE, FISCAL, PROFILES, ProfileError
from steuerbote.xbrl.taxonomy import NOT_PERMITTED_COMMERCIAL, View
from steuerbote.xbrl.tests import mini
from steuerbote.xbrl.tests.test_checks import (
	BVV_FACTS,
	ENTITY,
	KLEINST,
	LEAVES,
	PERIODS,
	PRIOR,
	complete,
	disclosure,
	euros,
	kontensaldo,
	replaced,
	report_6_10,
	without,
)

A = "de-gaap-ci:"
ST = Period.STICHTAG
WJ = Period.WIRTSCHAFTSJAHR


def fiscal_findings(report, taxonomy):
	facets = Facets.of(report)
	return (
		*checks.components(report, taxonomy, facets),
		*checks.mussfelder(report, taxonomy, facets),
		*checks.admissibility(report, taxonomy, facets),
		*checks.prior_year(report, taxonomy, facets),
		*checks.calculation(report, taxonomy),
		*checks.oberpositionen(report, taxonomy),
		*checks.summenmussfelder(report, taxonomy),
		*checks.kontensalden(report, taxonomy, facets),
		*checks.contexts(writer.instance(report, taxonomy)),
	)


def disclosure_findings(report, taxonomy, published):
	return (
		*checks.admissibility(report, taxonomy, Facets.of(report), purposes=(NOT_PERMITTED_COMMERCIAL,)),
		*checks.published(report, taxonomy, published),
		*checks.closing_dates(report, taxonomy),
		*checks.calculation(report, taxonomy),
		*checks.oberpositionen(report, taxonomy),
		*checks.contexts(writer.instance(report, taxonomy)),
	)


class ViewsTest(TestCase):
	def test_the_e_bilanz_takes_the_fiscal_view(self):
		"""„GAAP steuerlicher Einzelabschluss“, always with the GCD (Technischer Leitfaden zur HGB-Taxonomie 6.9, A.5 and
		B.3), for every size: the entry point of the MicroBilG is not one Steuerbote writes."""
		self.assertEqual((FISCAL.name, FISCAL.label), ("fiscal", "E-Bilanz"))
		self.assertEqual(FISCAL.views, (View.FISCAL,))
		self.assertEqual(FISCAL.view(), View.FISCAL)
		self.assertEqual(FISCAL.view(kleinst=True), View.FISCAL)

	def test_the_offenlegung_the_einzelabschluss_or_that_of_the_microbilg(self):
		"""„de-gaap-ci-2025-04-01 ... Einzelabschluss“ and „de-gaap-ci-2025-04-01-microbilg ... Einzelabschluss
		MicroBilG“, each with de-gcd-2025-04-01 („Arbeitshilfe für die Einreichung von Jahresabschlüssen/Finanzberichten
		im XBRL-Format“, Stand September 2025)."""
		self.assertEqual((DISCLOSURE.name, DISCLOSURE.label), ("disclosure", "Offenlegung"))
		self.assertEqual(DISCLOSURE.view(), View.COMMERCIAL)
		self.assertEqual(DISCLOSURE.view(kleinst=True), View.COMMERCIAL_MICROBILG)
		self.assertEqual(PROFILES, (FISCAL, DISCLOSURE))


class ReportTest(TestCase):
	def test_a_report_references_the_entry_points_of_its_view(self):
		taxonomy = mini.view(View.COMMERCIAL)
		facts = (euros("bs.ass", "100"),)
		report = DISCLOSURE.report(taxonomy, ENTITY, PRIOR, facts)
		self.assertEqual(report.schema_refs, writer.entry_points(taxonomy))
		self.assertEqual((report.entity, report.periods, report.facts), (ENTITY, PRIOR, facts))
		self.assertEqual(report.monetary_decimals, 2)
		self.assertEqual(
			DISCLOSURE.report(taxonomy, ENTITY, PRIOR, facts, monetary_decimals=0).monetary_decimals, 0
		)
		self.assertEqual(
			FISCAL.report(mini.view(), ENTITY, PERIODS, complete().facts).schema_refs,
			complete().schema_refs,
		)

	def test_refuses_the_view_of_another_profile(self):
		with self.assertRaisesRegex(ProfileError, "E-Bilanz takes the view fiscal, not commercial"):
			FISCAL.report(mini.view(View.COMMERCIAL), ENTITY, PERIODS, ())
		with self.assertRaisesRegex(
			ProfileError, "Offenlegung takes the view commercial or commercial-microbilg"
		):
			DISCLOSURE.check(complete(), mini.view(), published=KLEINST)

	def test_refuses_a_report_of_another_view(self):
		with self.assertRaisesRegex(ProfileError, "references the entry points of another view"):
			DISCLOSURE.check(disclosure(), mini.view(View.COMMERCIAL), published=KLEINST)


class FiscalTest(TestCase):
	"""The E-Bilanz: the components its GCD announces, the Mussfelder with NIL, the positions admissible for the
	Finanzverwaltung, no previous year in a Steuerbilanz, the calculation linkbase, the Oberpositionen, the
	Summenmussfelder and the contexts (steuerbote/xbrl/checks.py)."""

	def test_the_e_bilanz_of_the_gmbh_passes(self):
		self.assertEqual(FISCAL.check(complete(), mini.view()), ())

	def test_runs_every_check_of_the_finanzverwaltung(self):
		report = complete(
			euros("bs.ass.consolidationDifference", "0"),
			euros("bs.ass", "90", Period.VORJAHR_STICHTAG),
			euros("bs.eqLiab.liab.bank.upTo1year", "10"),
			periods=PRIOR,
		)
		report = replaced(
			without(report, *(fact.concept for fact in BVV_FACTS)),
			euros("is.netIncome.tax", "25", WJ),
			nil(f"{A}bs.ass.fixAss.intan.concessionBrands", ST),
			nil(f"{A}bs.eqLiab.liab.bank", ST),
		)
		expected = fiscal_findings(report, mini.view())
		self.assertEqual(FISCAL.check(report, mini.view()), expected)
		self.assertEqual(
			{finding.code for finding in expected},
			{
				Code.COMPONENT,
				Code.MUSSFELD,
				Code.NOT_PERMITTED,
				Code.PRIOR_YEAR,
				Code.CALCULATION,
				Code.OBERPOSITION,
				Code.SUMMENMUSSFELD,
			},
		)

	def test_publishes_nothing(self):
		with self.assertRaisesRegex(ProfileError, "only the Offenlegung names what it publishes"):
			FISCAL.check(complete(), mini.view(), published=KLEINST)

	def test_checks_the_kontensalden_of_6_10(self):
		"""Technischer Leitfaden zur HGB-Taxonomie 6.10, B.12.1: a Kontensaldo for each valued position of Bilanz and
		GuV without a valued one below it."""
		view = mini.view(View.FISCAL, mini.VERSION_6_10)
		report = report_6_10(*(kontensaldo(position, value) for position, value in LEAVES[1:]))
		found = FISCAL.check(report, view)
		self.assertEqual(found, fiscal_findings(report, view))
		self.assertIn(
			(Code.ACCOUNT_BALANCE_MISSING, f"{A}bs.ass.fixAss.intan.concessionBrands"),
			[(finding.code, finding.concept) for finding in found],
		)


class DisclosureTest(TestCase):
	"""The Offenlegung of a small company or a Kleinstkapitalgesellschaft: positions admissible in a Handelsbilanz, only
	what the class publishes, each Posten for both closing dates, the calculation linkbase, the Oberpositionen, which
	the register shows, and the contexts (steuerbote/xbrl/checks.py)."""

	def test_the_offenlegung_of_the_kleinst_passes(self):
		taxonomy = mini.view(View.COMMERCIAL_MICROBILG)
		self.assertEqual(DISCLOSURE.check(disclosure(), taxonomy, published=KLEINST), ())

	def test_runs_every_check_of_the_offenlegung(self):
		taxonomy = mini.view(View.COMMERCIAL_MICROBILG)
		report = replaced(
			disclosure(
				nil(f"{A}bs.eqLiab.equity.netIncome.taxBalanceGenerally", ST),
				euros("bs.eqLiab.liab.bank.upTo1year", "10"),
			),
			euros("bs.ass", "95", Period.VORJAHR_STICHTAG),
		)
		expected = disclosure_findings(report, taxonomy, KLEINST)
		self.assertEqual(DISCLOSURE.check(report, taxonomy, published=KLEINST), expected)
		self.assertEqual(
			{finding.code for finding in expected},
			{
				Code.NOT_PERMITTED,
				Code.NOT_PUBLISHED,
				Code.PRIOR_YEAR_AMOUNT,
				Code.CALCULATION,
				Code.OBERPOSITION,
			},
		)

	def test_not_the_checks_of_the_finanzverwaltung(self):
		"""The Mussfelder are those of the „Taxonomie Steuer“ (Technischer Leitfaden zur HGB-Taxonomie 6.9, B.14.2), and
		which data of the GCD the register needs is unverified: the Offenlegung asks for none, and announces no
		component."""
		taxonomy = mini.view(View.COMMERCIAL_MICROBILG)
		report = disclosure()
		self.assertNotEqual(checks.mussfelder(report, taxonomy, Facets.of(report)), ())
		self.assertEqual(DISCLOSURE.check(report, taxonomy, published=KLEINST), ())

	def test_the_first_fiscal_year_has_no_previous_year(self):
		"""A GmbH founded on 1 March 2026 discloses its first Bilanz without a previous year."""
		taxonomy = mini.view(View.COMMERCIAL_MICROBILG)
		first = Periods(date(2026, 3, 1), date(2026, 12, 31))
		facts = (
			euros("bs.ass", "100"),
			euros("bs.ass.fixAss", "100"),
			euros("bs.eqLiab", "100"),
			euros("bs.eqLiab.equity", "100"),
			Item("de-gcd:genInfo.company.id.name", WJ, "Beispiel GmbH"),
		)
		report = DISCLOSURE.report(taxonomy, ENTITY, first, facts)
		self.assertEqual(DISCLOSURE.check(report, taxonomy, published=KLEINST), ())

	def test_names_what_it_publishes(self):
		with self.assertRaisesRegex(ProfileError, "names the concepts its class shows"):
			DISCLOSURE.check(disclosure(), mini.view(View.COMMERCIAL_MICROBILG))

	def test_amounts_in_full_euros(self):
		"""Whether the register wants full euros is unverified (steuerbote/hgb/statement.py); a report in full euros
		passes the same checks."""
		taxonomy = mini.view(View.COMMERCIAL_MICROBILG)
		report = DISCLOSURE.report(taxonomy, ENTITY, PRIOR, disclosure().facts, monetary_decimals=0)
		self.assertEqual(DISCLOSURE.check(report, taxonomy, published=KLEINST), ())
		self.assertIn(b'decimals="0">100</de-gaap-ci:bs.ass>', writer.write(report, taxonomy))
