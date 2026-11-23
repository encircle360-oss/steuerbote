"""The XBRL instance of the Offenlegung for the Unternehmensregister, built from the statement, the Angaben and the
master data of the Annual Accounts (steuerbote/hgb/tests/companies.py)."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.hgb.disclosure import Mode, publication
from steuerbote.hgb.instance import REGISTER_SCHEME, InstanceError, Notes, build
from steuerbote.hgb.notes import RegisterData
from steuerbote.hgb.schemes import balance_sheet_scheme
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import Balance, ProfitPresentation, in_full_euros
from steuerbote.hgb.statement import build as statement
from steuerbote.hgb.tests import companies
from steuerbote.hgb.tests.companies import (
	BANK,
	FIRST_YEAR,
	KLEIN_2026,
	KLEIN_DISCLOSURE,
	KLEIN_GCD,
	KLEIN_NOTES,
	KLEINST_2025,
	KLEINST_2026,
	KLEINST_DISCLOSURE,
	KLEINST_GCD,
	KLEINST_NOTES,
	PARENTS,
	SUBSCRIBED,
	klein_statement,
	kleinst_statement,
)
from steuerbote.xbrl.facts import Item, Period
from steuerbote.xbrl.taxonomy import View
from steuerbote.xbrl.versions import TAXONOMIES

A = "de-gaap-ci:"
ST = Period.STICHTAG
PRIOR = Period.VORJAHR_STICHTAG
KLEINST = SizeClass.KLEINST
KLEIN = SizeClass.KLEIN


def kleinst(**changes):
	return build(
		changes.pop("statement", kleinst_statement()),
		changes.pop("size", KLEINST),
		changes.pop("notes", KLEINST_NOTES),
		changes.pop("disclosure", KLEINST_DISCLOSURE),
		changes.pop("gcd", KLEINST_GCD),
	)


def klein(**changes):
	return build(
		changes.pop("statement", klein_statement()),
		changes.pop("size", KLEIN),
		changes.pop("notes", KLEIN_NOTES),
		changes.pop("disclosure", KLEIN_DISCLOSURE),
		changes.pop("gcd", KLEIN_GCD),
	)


def items(instance) -> dict[tuple[str, Period], object]:
	"""The items outside tuples by concept and period."""
	return {(fact.concept, fact.period): fact.value for fact in instance.facts if isinstance(fact, Item)}


def balance_sheet(instance) -> dict[tuple[str, Period], Decimal]:
	return {
		(concept.removeprefix(A), period): value
		for (concept, period), value in items(instance).items()
		if concept.startswith(f"{A}bs.") and not concept.startswith(f"{A}bs.contingLiab")
	}


def concepts(instance, period: Period = ST) -> set[str]:
	return {concept for concept, at in balance_sheet(instance) if at is period}


def positions(size_class: SizeClass) -> set[str]:
	return {position.concept for position in balance_sheet_scheme(2026).visible(size_class)}


class ViewTest(TestCase):
	"""„de-gaap-ci-2025-04-01 ... Einzelabschluss“ and „de-gaap-ci-2025-04-01-microbilg ... Einzelabschluss
	MicroBilG“, each with de-gcd-2025-04-01 („Arbeitshilfe für die Einreichung von Jahresabschlüssen/Finanzberichten
	im XBRL-Format“ of the Unternehmensregister, Stand September 2025): the views of the profile DISCLOSURE."""

	def test_a_kleinst_takes_the_view_of_the_microbilg(self):
		self.assertIs(kleinst().view, View.COMMERCIAL_MICROBILG)

	def test_klein_the_view_of_the_einzelabschluss(self):
		self.assertIs(klein().view, View.COMMERCIAL)

	def test_the_taxonomy_of_the_fiscal_year(self):
		"""The register has taken 6.9 since 15 October 2025 (steuerbote/xbrl/versions.py); WJ 2026 is its year."""
		self.assertIs(kleinst().version, TAXONOMIES["6.9"])
		self.assertIs(klein().version, TAXONOMIES["6.9"])

	def test_the_class_and_the_mode_of_the_disclosure(self):
		instance = kleinst()
		self.assertEqual((instance.size_class, instance.mode), (KLEINST, Mode.HINTERLEGUNG))
		published = kleinst(disclosure=publication(KLEINST, Mode.OFFENLEGUNG))
		self.assertIs(published.mode, Mode.OFFENLEGUNG)
		self.assertEqual((klein().size_class, klein().mode), (KLEIN, Mode.OFFENLEGUNG))

	def test_the_periods_of_the_master_data(self):
		self.assertEqual(kleinst().periods, KLEINST_GCD.periods)

	def test_every_context_names_the_company_by_its_register(self):
		"""Which identifier the register expects is unverified: Registergericht and Registernummer name the company it
		keeps (§ 3 Abs. 2 URV)."""
		entity = kleinst().entity
		self.assertEqual(REGISTER_SCHEME, "http://www.handelsregister.de")
		self.assertEqual(
			(entity.scheme, entity.identifier), (REGISTER_SCHEME, "Amtsgericht Musterstadt HRB 12345")
		)

	def test_collapses_the_spaces_of_the_register(self):
		register = RegisterData(
			"Beispiel Werkstatt GmbH", "Musterstadt", " Amtsgericht  Musterstadt ", "HRB  12345"
		)
		entity = kleinst(notes=replace(KLEINST_NOTES, register=register)).entity
		self.assertEqual(entity.identifier, "Amtsgericht Musterstadt HRB 12345")


class SchemeLevelTest(TestCase):
	"""„Kleinstkapitalgesellschaften (§ 267a) brauchen nur eine verkürzte Bilanz aufzustellen, in die nur die in den
	Absätzen 2 und 3 mit Buchstaben bezeichneten Posten gesondert und in der vorgeschriebenen Reihenfolge aufgenommen
	werden.“ (§ 266 Abs. 1 Satz 4 HGB) Klein the positions „mit Buchstaben und römischen Zahlen“ (Satz 3), and the
	register shows every position reported, „lediglich die Positionen, zu denen Werte berichtet werden, sowie deren
	übergeordnete Positionen“ (Arbeitshilfe)."""

	def test_a_kleinst_reports_the_letters_and_the_totals(self):
		reported = concepts(kleinst()) - {"bs.eqLiab.liab.upTo1year", "bs.eqLiab.liab.above1year"}
		reported -= {"bs.eqLiab.liab.ofWhichToShareholders"}
		self.assertEqual(
			reported,
			{
				"bs.ass",
				"bs.ass.fixAss",
				"bs.ass.currAss",
				"bs.ass.prepaidExp",
				"bs.eqLiab",
				"bs.eqLiab.equity",
				"bs.eqLiab.accruals",
				"bs.eqLiab.liab",
			},
		)
		self.assertLessEqual(reported - {"bs.ass", "bs.eqLiab"}, positions(KLEINST))

	def test_klein_reports_the_letters_and_roman_numerals(self):
		reported = concepts(klein())
		self.assertLessEqual(
			{
				"bs.ass.fixAss.intan",
				"bs.ass.fixAss.tan",
				"bs.ass.fixAss.fin",
				"bs.ass.currAss.inventory",
				"bs.ass.currAss.receiv",
				"bs.ass.currAss.cashEquiv",
				"bs.eqLiab.equity.subscribed",
				"bs.eqLiab.equity.capRes",
				"bs.eqLiab.equity.revenueRes",
				"bs.eqLiab.equity.retainedEarnings",
				"bs.eqLiab.equity.netIncome",
			},
			reported,
		)
		self.assertNotIn("bs.ass.fixAss.tan.landBuildings", reported)
		self.assertNotIn("bs.eqLiab.liab.bank", reported)
		self.assertNotIn("bs.eqLiab.accruals.tax", reported)

	def test_nothing_of_the_income_statement(self):
		"""„nur die Bilanz und den Anhang“, „nur die Bilanz“ (§ 326 Abs. 1 Satz 1 und Abs. 2 Satz 1 HGB)."""
		for instance in (kleinst(), klein()):
			self.assertFalse([concept for concept, _ in items(instance) if concept.startswith(f"{A}is.")])

	def test_the_amounts_of_the_statement_in_full_euros(self):
		"""In full euros, as in_full_euros() of steuerbote/hgb/statement.py gives them; that the register wants them
		is unverified."""
		full = in_full_euros(kleinst_statement()).balance_sheet
		reported = balance_sheet(kleinst())
		for line in full.aktiva + full.passiva:
			if line.shown:
				with self.subTest(position=line.position.concept):
					self.assertEqual(reported[(line.position.concept, ST)], line.amount)
					self.assertEqual(reported[(line.position.concept, PRIOR)], line.prior)
		self.assertEqual(reported[("bs.ass", ST)], full.aktiva_total)
		self.assertEqual(reported[("bs.eqLiab", PRIOR)], full.prior_passiva_total)
		for value in reported.values():
			self.assertEqual(value, value.quantize(Decimal("1")))

	def test_the_totals_of_both_sides_agree(self):
		reported = balance_sheet(klein())
		self.assertEqual(reported[("bs.ass", ST)], reported[("bs.eqLiab", ST)])
		self.assertEqual(reported[("bs.ass", PRIOR)], reported[("bs.eqLiab", PRIOR)])


class ClosingDatesTest(TestCase):
	"""„In der Bilanz sowie in der Gewinn- und Verlustrechnung ist zu jedem Posten der entsprechende Betrag des
	vorhergehenden Geschäftsjahrs anzugeben.“ (§ 265 Abs. 2 Satz 1 HGB)"""

	def test_each_posten_at_both_closing_dates(self):
		for instance in (kleinst(), klein()):
			self.assertEqual(concepts(instance, ST), concepts(instance, PRIOR))

	def test_a_posten_without_an_amount_in_either_year_is_left_out(self):
		"""„Ein Posten der Bilanz ..., der keinen Betrag ausweist, braucht nicht aufgeführt zu werden, es sei denn, daß
		im vorhergehenden Geschäftsjahr unter diesem Posten ein Betrag ausgewiesen wurde.“ (§ 265 Abs. 8 HGB)"""
		reported = concepts(klein())
		self.assertNotIn("bs.ass.currAss.securities", reported)
		self.assertNotIn("bs.eqLiab.defIncome", reported)
		self.assertNotIn("bs.ass.deficitNotCoveredByCapital", reported)

	def test_a_posten_of_the_previous_year_only_shows_zero_this_year(self):
		prior = (
			*KLEINST_2025,
			Balance("bs.eqLiab.defIncome", Decimal("-500.00")),
			Balance(BANK, Decimal("500.00")),
		)
		instance = kleinst(statement=statement(2026, KLEINST, KLEINST_2026, parents=PARENTS, prior=prior))
		reported = balance_sheet(instance)
		self.assertEqual(reported[("bs.eqLiab.defIncome", ST)], Decimal("0"))
		self.assertEqual(reported[("bs.eqLiab.defIncome", PRIOR)], Decimal("500"))

	def test_the_first_fiscal_year_has_no_previous_year(self):
		"""A company in its first fiscal year has no previous year to give."""
		instance = kleinst(
			statement=statement(2026, KLEINST, KLEINST_2026, parents=PARENTS),
			gcd=replace(KLEINST_GCD, periods=FIRST_YEAR),
		)
		self.assertEqual(concepts(instance, PRIOR), set())
		self.assertIn("bs.ass", concepts(instance))


class VermerkeTest(TestCase):
	"""A class notes a Vermerk at a position it shows (steuerbote/hgb/schemes.py), as the „davon“ concept of the
	taxonomy that stands under the position it covers (``scope``)."""

	def test_the_remaining_terms_of_the_liabilities_at_c(self):
		"""„Der Betrag der Verbindlichkeiten mit einer Restlaufzeit bis zu einem Jahr und der Betrag der
		Verbindlichkeiten mit einer Restlaufzeit von mehr als einem Jahr sind bei jedem gesondert ausgewiesenen Posten
		zu vermerken.“ (§ 268 Abs. 5 Satz 1 HGB)"""
		reported = balance_sheet(kleinst())
		self.assertEqual(reported[("bs.eqLiab.liab.upTo1year", ST)], Decimal("9172"))
		self.assertEqual(reported[("bs.eqLiab.liab.above1year", ST)], Decimal("9000"))
		self.assertEqual(reported[("bs.eqLiab.liab.upTo1year", PRIOR)], Decimal("7551"))
		self.assertEqual(reported[("bs.eqLiab.liab.above1year", PRIOR)], Decimal("12000"))
		self.assertEqual(
			reported[("bs.eqLiab.liab", ST)],
			reported[("bs.eqLiab.liab.upTo1year", ST)] + reported[("bs.eqLiab.liab.above1year", ST)],
		)

	def test_the_liabilities_to_shareholders(self):
		"""„werden sie unter anderen Posten ausgewiesen, so muß diese Eigenschaft vermerkt werden“ (§ 42 Abs. 3
		GmbHG)."""
		reported = balance_sheet(kleinst())
		self.assertEqual(reported[("bs.eqLiab.liab.ofWhichToShareholders", ST)], Decimal("3000"))
		self.assertEqual(reported[("bs.eqLiab.liab.ofWhichToShareholders", PRIOR)], Decimal("2000"))

	def test_klein_notes_the_receivables_over_one_year_at_b_ii(self):
		"""„Der Betrag der Forderungen mit einer Restlaufzeit von mehr als einem Jahr ist bei jedem gesondert
		ausgewiesenen Posten zu vermerken.“ (§ 268 Abs. 4 Satz 1 HGB)"""
		reported = balance_sheet(klein())
		self.assertEqual(reported[("bs.ass.currAss.receiv.above1year", ST)], Decimal("20000"))
		self.assertEqual(reported[("bs.ass.currAss.receiv.above1year", PRIOR)], Decimal("0"))

	def test_a_vermerk_without_an_amount_in_either_year_is_left_out(self):
		self.assertNotIn("bs.ass.currAss.receiv.shareholder", concepts(klein()))
		self.assertNotIn("bs.ass.fixAss.fin.LoansToShareholder", concepts(klein()))

	def test_a_kleinst_states_no_vermerk_under_a_position_it_does_not_show(self):
		"""A Kleinst notes the receivables from shareholders at „B.“, but the taxonomy has their „davon“ concept
		only under „B. II.“, which a Kleinst does not show; it is no position of the instance."""
		reported = concepts(kleinst())
		self.assertNotIn("bs.ass.currAss.receiv.shareholder", reported)
		self.assertNotIn("bs.ass.currAss.receiv", reported)


class SubscribedCapitalTest(TestCase):
	"""„Die nicht eingeforderten ausstehenden Einlagen auf das gezeichnete Kapital sind von dem Posten „Gezeichnetes
	Kapital“ offen abzusetzen; der verbleibende Betrag ist als Posten „Eingefordertes Kapital“ in der Hauptspalte der
	Passivseite auszuweisen“ (§ 272 Abs. 1 Satz 2 HGB): the Nennbetrag less the uncalled contributions, which the
	taxonomy takes as positive amounts it subtracts (weight -1 in the calculation linkbase of 6.9)."""

	def test_klein_offsets_the_uncalled_contributions_in_the_vorspalte(self):
		reported = balance_sheet(klein())
		for period in (ST, PRIOR):
			with self.subTest(period=period):
				self.assertEqual(reported[("bs.eqLiab.equity.subscribed.corp", period)], Decimal("50000"))
				self.assertEqual(
					reported[("bs.eqLiab.equity.subscribed.unpaidCap", period)], Decimal("12500")
				)
				self.assertEqual(reported[("bs.eqLiab.equity.subscribed", period)], Decimal("37500"))

	def test_own_shares_at_their_nennbetrag_as_well(self):
		"""„Der Nennbetrag ... von erworbenen eigenen Anteilen ist in der Vorspalte offen von dem Posten „Gezeichnetes
		Kapital“ abzusetzen.“ (§ 272 Abs. 1a Satz 1 HGB)"""
		books = (
			*KLEIN_2026,
			Balance(companies.OWN_SHARES, Decimal("5000.00")),
			Balance(BANK, Decimal("-5000.00")),
		)
		instance = klein(
			statement=statement(2026, KLEIN, books, parents=PARENTS),
			gcd=replace(KLEIN_GCD, periods=FIRST_YEAR),
		)
		reported = balance_sheet(instance)
		self.assertEqual(reported[("bs.eqLiab.equity.subscribed.ownSharesdeducted", ST)], Decimal("5000"))
		self.assertEqual(reported[("bs.eqLiab.equity.subscribed.corp", ST)], Decimal("50000"))
		self.assertEqual(reported[("bs.eqLiab.equity.subscribed", ST)], Decimal("32500"))

	def test_without_a_deduction_only_the_gezeichnetes_kapital(self):
		books = tuple(balance for balance in KLEIN_2026 if balance.concept != companies.UNCALLED)
		books = (*books, Balance(BANK, Decimal("-12500.00")))
		instance = klein(
			statement=statement(2026, KLEIN, books, parents=PARENTS),
			gcd=replace(KLEIN_GCD, periods=FIRST_YEAR),
		)
		reported = concepts(instance)
		self.assertIn("bs.eqLiab.equity.subscribed", reported)
		self.assertNotIn("bs.eqLiab.equity.subscribed.corp", reported)
		self.assertNotIn("bs.eqLiab.equity.subscribed.unpaidCap", reported)

	def test_a_kleinst_shows_only_its_eigenkapital(self):
		self.assertNotIn("bs.eqLiab.equity.subscribed", concepts(kleinst()))


class ResultTest(TestCase):
	def test_the_fehlbetrag_stands_on_the_aktiva_and_within_the_eigenkapital(self):
		"""„Ist das Eigenkapital durch Verluste aufgebraucht ... gesondert unter der Bezeichnung „Nicht durch
		Eigenkapital gedeckter Fehlbetrag“ auszuweisen.“ (§ 268 Abs. 3 HGB)"""
		books = (
			Balance(BANK, Decimal("1000.00")),
			Balance(SUBSCRIBED, Decimal("-25000.00")),
			Balance("bs.eqLiab.equity.retainedEarnings", Decimal("30000.00")),
			Balance("bs.eqLiab.liab.trade", Decimal("-6000.00"), remaining_term=companies.SHORT),
		)
		instance = klein(
			statement=statement(2026, KLEIN, books, parents=PARENTS),
			gcd=replace(KLEIN_GCD, periods=FIRST_YEAR),
		)
		reported = balance_sheet(instance)
		self.assertEqual(reported[("bs.ass.deficitNotCoveredByCapital", ST)], Decimal("5000"))
		self.assertEqual(reported[("bs.eqLiab.equity.deficitNotCoveredByCapital", ST)], Decimal("5000"))
		self.assertEqual(reported[("bs.eqLiab.equity", ST)], Decimal("0"))
		self.assertEqual(reported[("bs.ass", ST)], Decimal("6000"))

	def test_the_bilanzgewinn_after_part_of_the_appropriation(self):
		"""„so tritt an die Stelle der Posten „Jahresüberschuß/Jahresfehlbetrag“ und „Gewinnvortrag/Verlustvortrag“
		der Posten „Bilanzgewinn/Bilanzverlust“; ein vorhandener Gewinn- oder Verlustvortrag ist ... in der Bilanz
		gesondert anzugeben“ (§ 268 Abs. 1 Satz 2 HGB)."""
		after = statement(
			2026,
			KLEIN,
			KLEIN_2026,
			parents=PARENTS,
			prior=companies.KLEIN_2025,
			presentation=ProfitPresentation.AFTER_PARTIAL_APPROPRIATION,
		)
		reported = balance_sheet(klein(statement=after))
		self.assertEqual(reported[("bs.eqLiab.equity.profitLoss", ST)], Decimal("352000"))
		self.assertEqual(reported[("bs.eqLiab.equity.profitLoss.retainedEarnings", ST)], Decimal("245000"))
		self.assertNotIn(("bs.eqLiab.equity.netIncome", ST), reported)
		self.assertNotIn(("bs.eqLiab.equity.retainedEarnings", ST), reported)

	def test_a_position_above_a_reported_one_is_reported_even_at_zero(self):
		"""„Ist eine Unterposition werthaltig angegeben, so sind auch ihre Oberpositionen werthaltig zu berichten“
		(Technischer Leitfaden zur HGB-Taxonomie 6.9, B.14.10): an Umlaufvermögen whose parts add up to nothing."""
		books = (
			Balance("bs.ass.fixAss.tan.otherEquipm", Decimal("1000.00")),
			Balance("bs.ass.currAss.inventory.finishedAndMerch", Decimal("300.00")),
			Balance(BANK, Decimal("-300.00")),
			Balance(SUBSCRIBED, Decimal("-1000.00")),
		)
		instance = klein(
			statement=statement(2026, KLEIN, books, parents=PARENTS),
			gcd=replace(KLEIN_GCD, periods=FIRST_YEAR),
		)
		reported = balance_sheet(instance)
		self.assertEqual(reported[("bs.ass.currAss", ST)], Decimal("0"))
		self.assertEqual(reported[("bs.ass.currAss.inventory", ST)], Decimal("300"))
		self.assertEqual(reported[("bs.ass.currAss.cashEquiv", ST)], Decimal("-300"))


class InputTest(TestCase):
	"""build() takes the statement of the class, the Publication of the class and the periods of the statement."""

	def test_refuses_a_statement_of_another_class(self):
		with self.assertRaisesRegex(InstanceError, "statement"):
			kleinst(statement=klein_statement())

	def test_refuses_the_publication_of_another_class(self):
		with self.assertRaisesRegex(InstanceError, "publication"):
			klein(disclosure=KLEINST_DISCLOSURE)

	def test_refuses_a_class_steuerbote_does_not_prepare(self):
		books = statement(
			2026, SizeClass.MITTELGROSS, KLEIN_2026, parents=PARENTS, prior=companies.KLEIN_2025
		)
		with self.assertRaisesRegex(InstanceError, "Kleinst and klein"):
			build(books, SizeClass.MITTELGROSS, KLEIN_NOTES, publication(SizeClass.MITTELGROSS), KLEIN_GCD)

	def test_refuses_periods_of_another_year(self):
		other = replace(
			KLEINST_GCD,
			periods=replace(
				FIRST_YEAR, fiscal_year_begin=date(2027, 1, 1), fiscal_year_end=date(2027, 12, 31)
			),
		)
		with self.assertRaisesRegex(InstanceError, "2027"):
			kleinst(statement=statement(2026, KLEINST, KLEINST_2026, parents=PARENTS), gcd=other)

	def test_refuses_a_previous_year_the_periods_do_not_have(self):
		with self.assertRaisesRegex(InstanceError, "previous year"):
			kleinst(gcd=replace(KLEINST_GCD, periods=FIRST_YEAR))

	def test_refuses_periods_with_a_previous_year_the_statement_does_not_have(self):
		with self.assertRaisesRegex(InstanceError, "previous year"):
			kleinst(statement=statement(2026, KLEINST, KLEINST_2026, parents=PARENTS))

	def test_refuses_a_register_without_court_and_number(self):
		register = RegisterData("Beispiel Werkstatt GmbH", "Musterstadt", " ", "")
		with self.assertRaisesRegex(InstanceError, "Registergericht"):
			kleinst(notes=Notes(register))
