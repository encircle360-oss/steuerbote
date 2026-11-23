"""The XBRL instance of the Offenlegung for the Unternehmensregister, built from the statement, the Angaben and the
master data of the Annual Accounts (steuerbote/hgb/tests/companies.py)."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.hgb.disclosure import Mode, Signature, publication
from steuerbote.hgb.instance import REGISTER_SCHEME, SLOTS, Code, InstanceError, Notes, build
from steuerbote.hgb.notes import (
	CATALOGUE,
	AdvanceKind,
	Answer,
	Contingency,
	ContingentLiability,
	NoteAnswer,
	OfficerAdvance,
	OfficerGroup,
	RegisterData,
	catalogue,
)
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
from steuerbote.jahresmeldung.corrections import RevisionStatus
from steuerbote.xbrl.facts import Item, Period, Tuple
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


G = "de-gcd:genInfo."


def gcd_items(instance) -> dict[str, object]:
	"""The items of the GCD outside tuples by concept."""
	return {
		fact.concept.removeprefix(G): fact.value
		for fact in instance.facts
		if isinstance(fact, Item) and fact.concept.startswith(G)
	}


def chosen(instance, concept: str) -> tuple[str, ...]:
	"""The values a choice of the GCD holds, without the name of the choice."""
	(found,) = (
		fact for fact in instance.facts if isinstance(fact, Tuple) and fact.concept == f"{G}{concept}"
	)
	return tuple(child.concept.removeprefix(f"{G}{concept}.") for child in found.children)


def tuples(instance) -> set[str]:
	return {fact.concept.removeprefix(G) for fact in instance.facts if isinstance(fact, Tuple)}


class ReportTest(TestCase):
	"""The GCD, the master data of the report („Stammdatenmodul“, Arbeitshilfe): which of its fields the register
	needs is unverified, so the instance states every field a festgestellter Jahresabschluss of a small GmbH fills."""

	def test_a_final_jahresabschluss_of_the_first_disclosure(self):
		"""Art des Berichts „Jahresabschluss“, Fertigstellungsstatus „endgültig“, Status „erstmalig“, Bilanzart
		„Jahresabschluss“ (de-gcd-2025-04-01)."""
		instance = kleinst()
		self.assertEqual(chosen(instance, "report.id.reportType"), ("reportType.JA",))
		self.assertEqual(chosen(instance, "report.id.reportStatus"), ("reportStatus.E",))
		self.assertEqual(chosen(instance, "report.id.revisionStatus"), ("revisionStatus.E",))
		self.assertEqual(chosen(instance, "report.id.statementType"), ("statementType.E",))

	def test_the_day_of_the_feststellung(self):
		"""„Das Datum der Feststellung oder der Billigung ... ist anzugeben.“ (§ 328 Abs. 1a Satz 1 HGB)"""
		self.assertEqual(
			gcd_items(kleinst())["report.id.reportStatus.reportStatus.dateofapproval"], date(2027, 5, 12)
		)

	def test_a_changed_jahresabschluss_names_its_status(self):
		"""„Wird der Jahresabschluss ... geändert, so ist auch die Änderung ... offenzulegen.“ (§ 325 Abs. 1b Satz 1
		HGB) Which status the register expects of it is unverified; the Annual Accounts name it."""
		instance = kleinst(gcd=replace(KLEINST_GCD, revision=RevisionStatus.CHANGED))
		self.assertEqual(chosen(instance, "report.id.revisionStatus"), ("revisionStatus.G",))

	def test_the_parts_a_kleinst_and_klein_transmit(self):
		"""„Berichtsbestandteile“: the Bilanz and the „Angaben unterhalb der Bilanz“, and for klein the Anhang,
		„andere Anhangangaben“ (§ 326 Abs. 1 Satz 1 und Abs. 2 Satz 1 HGB)."""
		self.assertEqual(
			chosen(kleinst(), "report.id.reportElement"), ("reportElements.B", "reportElements.H")
		)
		self.assertEqual(
			chosen(klein(), "report.id.reportElement"),
			("reportElements.B", "reportElements.H", "reportElements.SA"),
		)

	def test_the_angaben_of_section_264_1a_stand_under_the_balance_sheet(self):
		for instance in (kleinst(), klein()):
			self.assertEqual(chosen(instance, "report.id.reportElement.allocation.genInfo"), ("toBalance",))

	def test_a_kleinst_states_its_angaben_under_the_balance_sheet(self):
		"""„wenn sie ... unter der Bilanz angeben“ (§ 264 Abs. 1 Satz 5 HGB): „Allokation der Angaben nach MicroBilG“."""
		self.assertEqual(
			chosen(kleinst(), "report.id.reportElement.allocation.notesMicroBilG"), ("toBalance",)
		)
		self.assertNotIn("report.id.reportElement.allocation.notesMicroBilG", tuples(klein()))

	def test_a_jahresabschluss_of_the_kerntaxonomie_under_commercial_law(self):
		"""„deutsches Handelsrecht“ (HGBM), Branche „Kerntaxonomie“ (K), „nicht konsolidiert/ Einzelabschluss“ (EA)."""
		instance = klein()
		self.assertEqual(chosen(instance, "report.id.accountingStandard"), ("accountingStandard.HGBM",))
		self.assertEqual(chosen(instance, "report.id.specialAccountingStandard"), ("K",))
		self.assertEqual(chosen(instance, "report.id.consolidationRange"), ("consolidationRange.EA",))

	def test_the_format_of_the_income_statement_it_withholds(self):
		"""The Annual Accounts prepare the Gesamtkostenverfahren (steuerbote/hgb/schemes.py)."""
		self.assertEqual(chosen(kleinst(), "report.id.incomeStatementFormat"), ("incomeStatementFormat.GKV",))

	def test_whether_the_balance_sheet_shows_a_bilanzgewinn(self):
		"""„Bilanz enthält Ausweis des Bilanzgewinns/Bilanzverlustes“ (§ 268 Abs. 1 Satz 2 HGB)."""
		self.assertIs(gcd_items(klein())["report.id.incomeStatementendswithBalProfit"], False)
		after = statement(
			2026,
			KLEIN,
			KLEIN_2026,
			parents=PARENTS,
			prior=companies.KLEIN_2025,
			presentation=ProfitPresentation.AFTER_PARTIAL_APPROPRIATION,
		)
		self.assertIs(gcd_items(klein(statement=after))["report.id.incomeStatementendswithBalProfit"], True)
		self.assertIs(gcd_items(kleinst())["report.id.incomeStatementendswithBalProfit"], False)

	def test_the_fiscal_year_and_the_previous_one(self):
		found = gcd_items(kleinst())
		self.assertEqual(
			(
				found["report.period.fiscalYearBegin"],
				found["report.period.fiscalYearEnd"],
				found["report.period.balSheetClosingDate"],
				found["report.period.fiscalPreviousYearBegin"],
				found["report.period.fiscalPreviousYearEnd"],
				found["report.period.balSheetClosingDatePreviousYear"],
			),
			(
				date(2026, 1, 1),
				date(2026, 12, 31),
				date(2026, 12, 31),
				date(2025, 1, 1),
				date(2025, 12, 31),
				date(2025, 12, 31),
			),
		)

	def test_the_first_fiscal_year_names_no_previous_one(self):
		instance = kleinst(
			statement=statement(2026, KLEINST, KLEINST_2026, parents=PARENTS),
			gcd=replace(KLEINST_GCD, periods=FIRST_YEAR),
		)
		found = gcd_items(instance)
		self.assertEqual(found["report.period.fiscalYearBegin"], date(2026, 1, 1))
		self.assertFalse([concept for concept in found if "PreviousYear" in concept])

	def test_no_audit_for_a_small_company(self):
		"""„Der Jahresabschluß und der Lagebericht von Kapitalgesellschaften, die nicht kleine im Sinne des § 267
		Abs. 1 sind, sind durch einen Abschlußprüfer zu prüfen.“ (§ 316 Abs. 1 Satz 1 HGB)"""
		for instance in (kleinst(), klein()):
			self.assertEqual(chosen(instance, "report.audit.noAudit"), ("noAuditRequi",))

	def test_the_day_the_file_is_written(self):
		self.assertEqual(gcd_items(kleinst())["doc.id.generationDate"], date(2027, 7, 1))
		unwritten = gcd_items(kleinst(gcd=replace(KLEINST_GCD, generated_on=None)))
		self.assertNotIn("doc.id.generationDate", unwritten)

	def test_every_item_of_the_gcd_refers_to_the_fiscal_year(self):
		found = [fact for fact in klein().facts if isinstance(fact, Item) and fact.concept.startswith(G)]
		self.assertTrue(found)
		for fact in found:
			with self.subTest(concept=fact.concept):
				self.assertIs(fact.period, Period.WIRTSCHAFTSJAHR)


class CompanyTest(TestCase):
	"""What the GCD states of the company: firm, legal form, register, class, seat and address."""

	def test_the_firm(self):
		self.assertEqual(gcd_items(kleinst())["company.id.name"], "Beispiel Werkstatt GmbH")

	def test_a_gmbh_also_for_an_ug(self):
		"""Of legalStatus.UG the taxonomy says „Nicht vorgesehen für Bundesanzeiger, Erfassung unter "Gesellschaft mit
		beschränkter Haftung"“ (documentation label of de-gcd-2025-04-01-label-de.xml)."""
		self.assertEqual(chosen(kleinst(), "company.id.legalStatus"), ("legalStatus.GMBH",))

	def test_the_register_entry(self):
		"""„Registerart“ Handelsregister, „Amtsgericht, HR-Eintrag“ and the „Handelsregisternummer“ (§ 264 Abs. 1a
		HGB)."""
		instance = kleinst()
		self.assertEqual(chosen(instance, "company.id.Incorporation.Type"), ("Type.HR",))
		self.assertEqual(gcd_items(instance)["company.id.Incorporation.court"], "Amtsgericht Musterstadt")
		(numbers,) = (fact for fact in instance.facts if fact.concept == f"{G}company.id.idNo")
		self.assertEqual(
			tuple((child.concept, child.value) for child in numbers.children),
			((f"{G}company.id.idNo.type.companyId.HRN", "HRB 12345"),),
		)

	def test_the_size_class_and_the_scheme_of_the_balance_sheet(self):
		"""The class of § 267a or § 267 HGB (SizeClass.gcd) and „Berichtsumfang entspricht für die Bilanz mindestens
		(Größenklassenschema)“."""
		self.assertEqual(chosen(kleinst(), "company.id.sizeClass"), ("sizeClass.KstK",))
		self.assertEqual(chosen(kleinst(), "company.id.reportedSizeClassBs"), ("Kst",))
		self.assertEqual(chosen(klein(), "company.id.sizeClass"), ("sizeClass.KK",))
		self.assertEqual(chosen(klein(), "company.id.reportedSizeClassBs"), ("K",))

	def test_the_seat_and_the_address(self):
		found = gcd_items(kleinst())
		self.assertEqual(
			(
				found["company.id.location"],
				found["company.id.location.street"],
				found["company.id.location.houseNo"],
				found["company.id.location.zipCode"],
				found["company.id.location.city"],
				found["company.id.location.country"],
			),
			("Musterstadt", "Musterweg", "12", "12345", "Musterstadt", "Deutschland"),
		)

	def test_without_an_address_only_the_seat(self):
		found = gcd_items(kleinst(gcd=replace(KLEINST_GCD, address=None)))
		self.assertEqual(found["company.id.location"], "Musterstadt")
		self.assertFalse([concept for concept in found if concept.startswith("company.id.location.")])

	def test_the_day_of_the_founding(self):
		self.assertEqual(gcd_items(kleinst())["company.id.FoundationDate"], date(2024, 3, 1))
		self.assertNotIn(
			"company.id.FoundationDate", gcd_items(kleinst(gcd=replace(KLEINST_GCD, founded_on=None)))
		)

	def test_a_company_in_liquidation_says_so(self):
		"""„Befindet sich die Gesellschaft in Liquidation oder Abwicklung, ist auch diese Tatsache anzugeben.“ (§ 264
		Abs. 1a Satz 2 HGB): „Unternehmensstatus“ „in Liquidation“."""
		register = replace(KLEINST_NOTES.register, in_liquidation=True)
		instance = kleinst(notes=replace(KLEINST_NOTES, register=register))
		self.assertEqual(chosen(instance, "company.id.CompanyStatus"), ("companyStatus.L",))
		self.assertNotIn("company.id.CompanyStatus", tuples(kleinst()))

	def test_no_kapitalmarktorientierte_company(self):
		"""„Eine Kapitalgesellschaft im Sinn des § 264d gilt stets als große.“ (§ 267 Abs. 3 Satz 2 HGB), so neither a
		Kleinst nor klein is one."""
		found = gcd_items(klein())
		self.assertIs(found["company.disclosureCriterion.scope.CapitalMarketOrientationHGBs264d"], False)


def angaben(instance) -> dict[tuple[str, Period], object]:
	"""The items of the GAAP module outside the balance sheet by concept without prefix and period."""
	return {
		(concept.removeprefix(A), period): value
		for (concept, period), value in items(instance).items()
		if (concept.startswith(A) and not concept.startswith(f"{A}bs."))
		or concept.startswith(f"{A}bs.contingLiab")
	}


def text(instance, concept: str) -> str:
	return angaben(instance)[(concept, Period.WIRTSCHAFTSJAHR)]


def answered(notes: Notes, code: str, answer: Answer, text: str = "", amount: Decimal | None = None) -> Notes:
	others = tuple(entry for entry in notes.answers if entry.code != code)
	return replace(notes, answers=(*others, NoteAnswer(code, answer, text, amount)))


WJ = Period.WIRTSCHAFTSJAHR
BELOW = "notesBelowBalanceSheet.geninfo"


class RegisterDataTest(TestCase):
	"""„In dem Jahresabschluss sind die Firma, der Sitz, das Registergericht und die Nummer, unter der die
	Gesellschaft in das Handelsregister eingetragen ist, anzugeben.“ (§ 264 Abs. 1a Satz 1 HGB), as
	notesBelowBalanceSheet.geninfo.* (RegisterData.concepts())."""

	def test_firm_seat_court_and_number_under_the_balance_sheet(self):
		found = angaben(kleinst())
		self.assertEqual(
			(
				found[(f"{BELOW}.company", WJ)],
				found[(f"{BELOW}.location", WJ)],
				found[(f"{BELOW}.court", WJ)],
				found[(f"{BELOW}.number", WJ)],
			),
			("Beispiel Werkstatt GmbH", "Musterstadt", "Amtsgericht Musterstadt", "HRB 12345"),
		)
		self.assertNotIn((f"{BELOW}.liquidationOrWindingUp", WJ), found)
		self.assertEqual(angaben(klein())[(f"{BELOW}.number", WJ)], "HRB 67890")

	def test_a_company_in_liquidation_says_so(self):
		"""„Befindet sich die Gesellschaft in Liquidation oder Abwicklung, ist auch diese Tatsache anzugeben.“ (§ 264
		Abs. 1a Satz 2 HGB)"""
		register = replace(KLEINST_NOTES.register, in_liquidation=True)
		found = angaben(kleinst(notes=replace(KLEINST_NOTES, register=register)))
		self.assertEqual(
			found[(f"{BELOW}.liquidationOrWindingUp", WJ)], "Die Gesellschaft befindet sich in Liquidation."
		)


class ContingenciesTest(TestCase):
	"""„Für die in § 251 bezeichneten Haftungsverhältnisse sind ... die Haftungsverhältnisse jeweils gesondert unter
	Angabe der gewährten Pfandrechte und sonstigen Sicherheiten anzugeben und ... Verpflichtungen betreffend die
	Altersversorgung und Verpflichtungen gegenüber verbundenen oder assoziierten Unternehmen jeweils gesondert zu
	vermerken.“ (§ 268 Abs. 7 HGB) A Kleinst states them under the balance sheet (§ 264 Abs. 1 Satz 5 Nr. 1 HGB),
	klein in the Anhang, each kind at the Abschlussstichtag in full euros under bs.contingLiab."""

	def test_each_kind_with_its_total(self):
		found = angaben(kleinst())
		self.assertEqual(found[("bs.contingLiab", ST)], Decimal("15000"))
		self.assertEqual(found[("bs.contingLiab.guarantees", ST)], Decimal("15000"))
		self.assertNotIn(("bs.contingLiab", PRIOR), found)

	def test_the_part_towards_the_group_and_for_pensions_separately(self):
		found = angaben(klein())
		self.assertEqual(found[("bs.contingLiab", ST)], Decimal("80000"))
		self.assertEqual(found[("bs.contingLiab.warranty", ST)], Decimal("30000"))
		self.assertEqual(found[("bs.contingLiab.collateralisation", ST)], Decimal("50000"))
		self.assertEqual(found[("bs.contingLiab.collateralisation.assoc", ST)], Decimal("50000"))
		self.assertNotIn(("bs.contingLiab.collateralisation.pension", ST), found)
		self.assertNotIn(("bs.contingLiab.warranty.assoc", ST), found)

	def test_in_full_euros_adding_up_to_their_total(self):
		contingent = (
			ContingentLiability(Contingency.GUARANTEES, Decimal("1000.60"), pensions=True),
			ContingentLiability(Contingency.WARRANTIES, Decimal("500.60")),
		)
		found = angaben(kleinst(notes=replace(KLEINST_NOTES, contingent=contingent)))
		self.assertEqual(found[("bs.contingLiab", ST)], Decimal("1501"))
		self.assertEqual(
			found[("bs.contingLiab.guarantees", ST)] + found[("bs.contingLiab.warranty", ST)], Decimal("1501")
		)
		self.assertEqual(
			found[("bs.contingLiab.guarantees.pension", ST)], found[("bs.contingLiab.guarantees", ST)]
		)

	def test_the_securities_granted_in_the_text(self):
		self.assertIn(
			"Verbindlichkeiten aus Bürgschaften, gewährte Pfandrechte und sonstige Sicherheiten: Abtretung von "
			"Forderungen aus Lieferungen und Leistungen",
			text(kleinst(), "ntmi.other"),
		)
		self.assertIn(
			"Haftungsverhältnisse aus der Bestellung von Sicherheiten für fremde Verbindlichkeiten, gewährte "
			"Pfandrechte und sonstige Sicherheiten: Grundschuld auf dem Geschäftsgebäude",
			text(klein(), "nt.otherInfo.contingLiab"),
		)

	def test_a_total_without_its_kinds(self):
		notes = answered(
			replace(KLEINST_NOTES, contingent=()),
			"HAFTUNGSVERHAELTNISSE",
			Answer.YES,
			amount=Decimal("700.40"),
		)
		found = angaben(kleinst(notes=notes))
		self.assertEqual(found[("bs.contingLiab", ST)], Decimal("700"))
		self.assertNotIn(("bs.contingLiab.guarantees", ST), found)

	def test_where_the_gcd_says_they_stand(self):
		"""„Allokation der Haftungsverhältnisse“: under the balance sheet or in the Anhang."""
		self.assertEqual(
			chosen(kleinst(), "report.id.reportElement.allocation.contingencies"), ("toBalance",)
		)
		self.assertEqual(chosen(klein(), "report.id.reportElement.allocation.contingencies"), ("inNotes",))
		notes = answered(replace(KLEINST_NOTES, contingent=()), "HAFTUNGSVERHAELTNISSE", Answer.NO)
		self.assertNotIn("report.id.reportElement.allocation.contingencies", tuples(kleinst(notes=notes)))


class KleinstAngabenTest(TestCase):
	"""„Kleinstkapitalgesellschaften (§ 267a) brauchen den Jahresabschluss nicht um einen Anhang zu erweitern, wenn
	sie 1. die in § 268 Absatz 7 genannten Angaben, 2. die in § 285 Nummer 9 Buchstabe c genannten Angaben ... unter
	der Bilanz angeben.“ (§ 264 Abs. 1 Satz 5 HGB)"""

	def test_the_vorschuesse_and_kredite_to_the_management(self):
		"""„die gewährten Vorschüsse und Kredite unter Angabe der Zinssätze, der wesentlichen Bedingungen und der
		gegebenenfalls im Geschäftsjahr zurückgezahlten oder erlassenen Beträge sowie die zugunsten dieser Personen
		eingegangenen Haftungsverhältnisse“, „jeweils für jede Personengruppe“ (§ 285 Nr. 9 Buchst. c HGB)."""
		self.assertEqual(
			text(kleinst(), "nt.relationships.creditsToMembers"),
			"Mitglieder des Geschäftsführungsorgans: Vorschüsse und Kredite 8.000 €, Zinssatz 3,5 % im Jahr; "
			"wesentliche Bedingungen: Laufzeit bis zum 31. Dezember 2028, Tilgung in Jahresraten; im Geschäftsjahr "
			"zurückgezahlt 2.000 €.",
		)

	def test_the_rates_and_guarantees_of_several_advances(self):
		advances = (
			OfficerAdvance(
				OfficerGroup.MANAGEMENT, AdvanceKind.ADVANCE, Decimal("1000.00"), Decimal("0"), "Reisekosten"
			),
			OfficerAdvance(
				OfficerGroup.MANAGEMENT,
				AdvanceKind.LOAN,
				Decimal("2000.40"),
				Decimal("4.00"),
				"Laufzeit drei Jahre",
				waived=Decimal("100.00"),
				guarantees="Bürgschaft gegenüber der Hausbank",
			),
			OfficerAdvance(
				OfficerGroup.ADVISORY_BOARD, AdvanceKind.LOAN, Decimal("500"), Decimal("2.5"), "jederzeit"
			),
		)
		notes = answered(
			replace(KLEINST_NOTES, advances=advances), "ORGANKREDITE", Answer.YES, "Alle sind besichert."
		)
		self.assertEqual(
			text(kleinst(notes=notes), "nt.relationships.creditsToMembers"),
			"Mitglieder des Geschäftsführungsorgans: Vorschüsse und Kredite 3.000 €, Zinssätze 0 % und 4 % im Jahr; "
			"wesentliche Bedingungen: Reisekosten; Laufzeit drei Jahre; im Geschäftsjahr erlassen 100 €; zu ihren "
			"Gunsten eingegangene Haftungsverhältnisse: Bürgschaft gegenüber der Hausbank.\n\n"
			"Mitglieder des Beirats: Vorschüsse und Kredite 500 €, Zinssatz 2,5 % im Jahr; wesentliche Bedingungen: "
			"jederzeit.\n\n"
			"Alle sind besichert.",
		)

	def test_the_vermerke_it_cannot_report_stand_under_the_balance_sheet(self):
		"""The taxonomy has the „davon“ concept of the receivables from shareholders only under „B. II.“, which a
		Kleinst does not show, so the Vermerk at „B.“ stands as text."""
		self.assertIn(
			"B. Umlaufvermögen, davon Forderungen gegen Gesellschafter: 2.500 € (Vorjahr: 1.500 €)",
			text(kleinst(), "ntmi.other"),
		)

	def test_the_first_year_states_no_previous_year_in_the_text(self):
		instance = kleinst(
			statement=statement(2026, KLEINST, KLEINST_2026, parents=PARENTS),
			gcd=replace(KLEINST_GCD, periods=FIRST_YEAR),
		)
		self.assertIn(
			"B. Umlaufvermögen, davon Forderungen gegen Gesellschafter: 2.500 €\n",
			text(instance, "ntmi.other"),
		)

	def test_zusaetzliche_angaben_and_why_the_eigenkapital_is_zero(self):
		"""„sind nach Satz 2 erforderliche zusätzliche Angaben unter der Bilanz zu machen“ (§ 264 Abs. 2 Satz 4 HGB);
		„Kleinstkapitalgesellschaften haben unter der Bilanz darzulegen, warum gegebenenfalls das Stammkapital
		aufgebraucht und daher das Eigenkapital mit Null ausgewiesen ist.“ (Bundesamt für Justiz, FAQ zu Inhalts- und
		Formverstößen)"""
		books = (
			Balance(BANK, Decimal("1000.00")),
			Balance(SUBSCRIBED, Decimal("-25000.00")),
			Balance("bs.eqLiab.equity.retainedEarnings", Decimal("30000.00")),
			Balance("bs.eqLiab.liab.trade", Decimal("-6000.00"), remaining_term=companies.SHORT),
		)
		notes = answered(
			answered(
				KLEINST_NOTES,
				"ZUSAETZLICHE-ANGABEN",
				Answer.YES,
				"Die Gesellschafterin hat einen Rangrücktritt erklärt.",
			),
			"EIGENKAPITAL-NULL",
			Answer.YES,
			"Das Stammkapital ist durch die Verluste der Anlaufjahre aufgebraucht.",
		)
		instance = kleinst(
			statement=statement(2026, KLEINST, books, parents=PARENTS),
			notes=notes,
			gcd=replace(KLEINST_GCD, periods=FIRST_YEAR),
		)
		self.assertEqual(instance.findings, ())
		paragraphs = text(instance, "ntmi.other").split("\n\n")
		self.assertIn("Die Gesellschafterin hat einen Rangrücktritt erklärt.", paragraphs)
		self.assertIn("Das Stammkapital ist durch die Verluste der Anlaufjahre aufgebraucht.", paragraphs)
		self.assertLess(
			paragraphs.index("Die Gesellschafterin hat einen Rangrücktritt erklärt."),
			paragraphs.index("Das Stammkapital ist durch die Verluste der Anlaufjahre aufgebraucht."),
		)

	def test_a_zero_eigenkapital_asks_for_its_explanation(self):
		books = (
			Balance(BANK, Decimal("1000.00")),
			Balance(SUBSCRIBED, Decimal("-25000.00")),
			Balance("bs.eqLiab.equity.retainedEarnings", Decimal("30000.00")),
			Balance("bs.eqLiab.liab.trade", Decimal("-6000.00"), remaining_term=companies.SHORT),
		)
		instance = kleinst(
			statement=statement(2026, KLEINST, books, parents=PARENTS),
			gcd=replace(KLEINST_GCD, periods=FIRST_YEAR),
		)
		self.assertIn("EIGENKAPITAL-NULL", {finding.concept for finding in instance.findings})

	def test_the_signatures_with_place_and_day(self):
		"""„Der Jahresabschluß ist vom Kaufmann unter Angabe des Datums zu unterzeichnen.“ (§ 245 Satz 1 HGB) „Nach
		§ 245 HGB ist beim Jahresabschluss die Angabe aller Unterzeichner sowie des Datums erforderlich.“
		(Publikations-Plattform, „Übermittlung von Jahresabschlüssen“) A Kleinst has no Anhang, so they close the
		text under its balance sheet."""
		self.assertTrue(
			text(kleinst(), "ntmi.other").endswith(
				"Musterstadt, 12. Mai 2027: gez. Erika Beispiel, Geschäftsführerin"
			)
		)
		self.assertFalse(
			[concept for concept, _ in angaben(kleinst()) if concept.startswith("nt.directorsSign")]
		)

	def test_an_angabe_answered_no_states_nothing(self):
		notes = answered(replace(KLEINST_NOTES, advances=()), "ORGANKREDITE", Answer.NO)
		self.assertNotIn(("nt.relationships.creditsToMembers", WJ), angaben(kleinst(notes=notes)))


class AnhangTest(TestCase):
	"""„Auf kleine Kapitalgesellschaften (§ 267 Abs. 1) ist § 325 Abs. 1 mit der Maßgabe anzuwenden, daß die
	Mitglieder des vertretungsberechtigten Organs nur die Bilanz und den Anhang zu übermitteln haben. Der Anhang braucht
	die die Gewinn- und Verlustrechnung betreffenden Angaben nicht zu enthalten.“ (§ 326 Abs. 1 HGB)"""

	def test_each_angabe_under_its_position_of_the_anhang(self):
		found = angaben(klein())
		self.assertTrue(
			found[("nt.genInfo.measurement", WJ)].startswith("Die immateriellen Vermögensgegenstände")
		)

	def test_two_angaben_of_one_position_one_after_the_other(self):
		self.assertEqual(
			text(klein(), "nt.otherInfo.contingLiab").split("\n\n"),
			[
				"Haftungsverhältnisse aus der Bestellung von Sicherheiten für fremde Verbindlichkeiten, gewährte "
				"Pfandrechte und sonstige Sicherheiten: Grundschuld auf dem Geschäftsgebäude",
				"Aus Mietverträgen für Lagerflächen bestehen sonstige finanzielle Verpflichtungen von 96.000 €.",
			],
		)

	def test_an_amount_the_taxonomy_takes_as_text_follows_it(self):
		self.assertEqual(
			text(klein(), "nt.bsInfo.totalAmountLiabOver5Years"),
			"Verbindlichkeiten gegenüber Kreditinstituten mit einer Restlaufzeit von mehr als fünf Jahren, durch eine "
			"Grundschuld auf dem Geschäftsgebäude gesichert (120.000 €)",
		)
		notes = answered(KLEIN_NOTES, "VERBINDLICHKEITEN", Answer.YES, amount=Decimal("99.50"))
		self.assertEqual(text(klein(notes=notes), "nt.bsInfo.totalAmountLiabOver5Years"), "100 €")

	def test_the_average_number_of_employees(self):
		"""„die durchschnittliche Zahl der während des Geschäftsjahrs beschäftigten Arbeitnehmer“ (§ 285 Nr. 7 HGB,
		without the groups for klein, § 288 Abs. 1 Nr. 2 HGB), „Durchschnittliche Zahl der Beschäftigten“."""
		(employees,) = (fact for fact in klein().facts if fact.concept == f"{A}nt.employeesAveragePeriod")
		self.assertEqual((employees.period, employees.value, employees.decimals), (WJ, Decimal("23.75"), 2))
		notes = answered(KLEIN_NOTES, "ARBEITNEHMER", Answer.YES, amount=Decimal("24"))
		(whole,) = (
			fact for fact in klein(notes=notes).facts if fact.concept == f"{A}nt.employeesAveragePeriod"
		)
		self.assertEqual((whole.value, whole.decimals), (Decimal("24"), 0))

	def test_the_number_of_employees_needs_its_number(self):
		notes = answered(KLEIN_NOTES, "ARBEITNEHMER", Answer.YES, "Im Jahresdurchschnitt 24 Arbeitnehmer.")
		instance = klein(notes=notes)
		(finding,) = (finding for finding in instance.findings if finding.code == Code.NUMBER)
		self.assertEqual(finding.concept, "ARBEITNEHMER")
		self.assertFalse([fact for fact in instance.facts if fact.concept == f"{A}nt.employeesAveragePeriod"])

	def test_what_concerns_the_income_statement_is_withheld(self):
		texts = " ".join(str(value) for value in angaben(klein()).values())
		self.assertNotIn("einmaligen Ertrag", texts)

	def test_an_angabe_answered_entfaellt_states_nothing(self):
		self.assertNotIn(("nt.assocComp.parentsNameSmall", WJ), angaben(klein()))

	def test_the_signatures_of_the_geschaeftsfuehrung(self):
		"""„Unterschrift der Geschäftsleitung“ with its place, its day and each person, whom the Bundesamt für Justiz
		expects named with the day (§ 245 Satz 1 HGB)."""
		instance = klein()
		found = angaben(instance)
		self.assertEqual(found[("nt.directorsSign.place", WJ)], "Musterstadt")
		self.assertEqual(found[("nt.directorsSign.date", WJ)], date(2027, 6, 30))
		signed = [fact for fact in instance.facts if fact.concept == f"{A}nt.directorsSign.type"]
		self.assertEqual(
			[
				(
					fact.children[0].value,
					fact.children[1].children[0].value,
					len(fact.children[1].children),
				)
				for fact in signed
			],
			[("Geschäftsführerin", "Erika Beispiel", 1), ("Geschäftsführer", "Max Muster", 1)],
		)

	def test_signatures_of_different_days_name_each_day(self):
		signatures = (
			Signature("Erika Beispiel", "Geschäftsführerin", "Musterstadt", date(2027, 6, 30)),
			Signature("Max Muster", "Geschäftsführer", "Musterdorf", date(2027, 7, 2)),
		)
		instance = klein(notes=replace(KLEIN_NOTES, signatures=signatures))
		found = angaben(instance)
		self.assertNotIn(("nt.directorsSign.date", WJ), found)
		self.assertNotIn(("nt.directorsSign.place", WJ), found)
		persons = [fact.children[1] for fact in instance.facts if fact.concept == f"{A}nt.directorsSign.type"]
		self.assertEqual(
			[[child.value for child in person.children] for person in persons],
			[["Erika Beispiel", "Musterstadt, 30. Juni 2027"], ["Max Muster", "Musterdorf, 2. Juli 2027"]],
		)

	def test_without_signatures_no_block(self):
		instance = klein(notes=replace(KLEIN_NOTES, signatures=()))
		self.assertFalse(
			[concept for concept, _ in angaben(instance) if concept.startswith("nt.directorsSign")]
		)


class SlotsTest(TestCase):
	"""Every Angabe a class publishes has its place in the taxonomy, and nothing else has one."""

	def test_each_published_angabe_of_a_kleinst_stands_under_the_balance_sheet(self):
		entries = catalogue(KLEINST, equity_zero=True)
		self.assertEqual(
			tuple(slot.code for slot in SLOTS[KLEINST]),
			tuple(entry.item.code for entry in entries if entry.published),
		)

	def test_each_published_angabe_of_klein_stands_in_the_anhang(self):
		entries = catalogue(KLEIN)
		self.assertEqual(
			tuple(slot.code for slot in SLOTS[KLEIN]),
			tuple(entry.item.code for entry in entries if entry.published),
		)

	def test_a_kleinst_takes_the_concepts_of_the_catalogue(self):
		by_code = {item.code: item.concept for item in CATALOGUE}
		for slot in SLOTS[KLEINST]:
			with self.subTest(code=slot.code):
				self.assertIn(by_code[slot.code], (slot.text, slot.amount))

	def test_the_published_concepts_hold_every_place_of_an_angabe(self):
		for size_class, instance in ((KLEINST, kleinst()), (KLEIN, klein())):
			published = set(instance.published)
			for slot in SLOTS[size_class]:
				with self.subTest(code=slot.code):
					self.assertLessEqual(
						{concept for concept in (slot.text, slot.amount) if concept}, published
					)
			self.assertLessEqual(set(RegisterData.concepts().values()), published)
			for kind in Contingency:
				self.assertLessEqual({kind.concept, kind.pensions_concept, kind.group_concept}, published)

	def test_the_published_concepts_are_the_facts_of_the_gaap_module(self):
		for instance in (kleinst(), klein()):
			reported = {
				fact.concept.removeprefix(A)
				for fact in _all_facts(instance.facts)
				if fact.concept.startswith(A)
			}
			self.assertLessEqual(reported, set(instance.published))


def _all_facts(facts):
	for fact in facts:
		yield fact
		if isinstance(fact, Tuple):
			yield from _all_facts(fact.children)


class FindingsTest(TestCase):
	"""What holds the file back: whatever holds the Jahresabschluss back, and what the file cannot carry."""

	def test_the_invented_companies_are_complete(self):
		self.assertEqual(kleinst().findings, ())
		self.assertEqual(klein().findings, ())

	def test_an_unanswered_angabe(self):
		notes = replace(KLEIN_NOTES, answers=KLEIN_NOTES.answers[1:])
		codes = {finding.code for finding in klein(notes=notes).findings}
		self.assertIn("JA-ANGABE-OFFEN", codes)

	def test_an_advance_without_its_rate(self):
		advance = replace(KLEINST_NOTES.advances[0], interest_rate=None)
		codes = {
			finding.code for finding in kleinst(notes=replace(KLEINST_NOTES, advances=(advance,))).findings
		}
		self.assertIn("JA-ORGANKREDIT-ZINSSATZ", codes)

	def test_register_data_without_the_seat(self):
		register = replace(KLEINST_NOTES.register, sitz=" ")
		codes = {
			finding.code for finding in kleinst(notes=replace(KLEINST_NOTES, register=register)).findings
		}
		self.assertIn("JA-REGISTERANGABEN", codes)

	def test_the_errors_of_the_statement_of_both_years(self):
		books = (*KLEINST_2026, Balance("bs.ass.other", Decimal("10.00")))
		instance = kleinst(statement=statement(2026, KLEINST, books, parents=PARENTS, prior=KLEINST_2025))
		codes = {finding.code for finding in instance.findings}
		self.assertIn("JA-RECHENPOSTEN", codes)
		self.assertIn("JA-BILANZ-UNGLEICH", codes)
		self.assertTrue(all(finding.blocking for finding in instance.findings))

	def test_a_feststellung_within_the_fiscal_year(self):
		codes = {
			finding.code
			for finding in kleinst(gcd=replace(KLEINST_GCD, adopted_on=date(2026, 12, 31))).findings
		}
		self.assertEqual(codes, {"JA-FESTSTELLUNG-DATUM"})

	def test_entries_of_an_angabe_answered_otherwise(self):
		notes = answered(KLEINST_NOTES, "HAFTUNGSVERHAELTNISSE", Answer.NO)
		(finding,) = kleinst(notes=notes).findings
		self.assertEqual((finding.code, finding.concept), (Code.ENTRIES, "HAFTUNGSVERHAELTNISSE"))
		self.assertNotIn(("bs.contingLiab", ST), angaben(kleinst(notes=notes)))
		notes = answered(KLEINST_NOTES, "ORGANKREDITE", Answer.NOT_APPLICABLE)
		(finding,) = kleinst(notes=notes).findings
		self.assertEqual((finding.code, finding.concept), (Code.ENTRIES, "ORGANKREDITE"))

	def test_an_amount_beside_entries_of_another_total(self):
		notes = answered(KLEINST_NOTES, "HAFTUNGSVERHAELTNISSE", Answer.YES, amount=Decimal("14000.00"))
		(finding,) = kleinst(notes=notes).findings
		self.assertEqual((finding.code, finding.amount), (Code.AMOUNT, Decimal("14000.00")))
		agreeing = answered(KLEINST_NOTES, "HAFTUNGSVERHAELTNISSE", Answer.YES, amount=Decimal("15000.00"))
		self.assertEqual(kleinst(notes=agreeing).findings, ())

	def test_characters_the_file_cannot_take(self):
		"""Texts keep to the characters of ELSTER, the writer refuses others (steuerbote/xbrl/writer.py); the common
		typographic ones are replaced (steuerbote/elster/charset.py)."""
		register = replace(KLEINST_NOTES.register, firma="Łódź Werkstatt GmbH")
		instance = kleinst(notes=replace(KLEINST_NOTES, register=register))
		(finding,) = instance.findings
		self.assertEqual(finding.code, Code.CHARACTERS)
		self.assertIn("U+0141", finding.text)
		self.assertIn("U+017A", finding.text)
		self.assertEqual(gcd_items(instance)["company.id.name"], "ód Werkstatt GmbH")

	def test_typographic_characters_are_replaced_and_lines_kept(self):
		notes = answered(
			KLEIN_NOTES,
			"BEWERTUNGSMETHODEN",
			Answer.YES,
			"Waren zum \N{DOUBLE LOW-9 QUOTATION MARK}gleitenden\N{LEFT DOUBLE QUOTATION MARK} Durchschnitt.\n"
			"Forderungen \N{EN DASH} zum Nennwert.",
		)
		instance = klein(notes=notes)
		self.assertEqual(instance.findings, ())
		self.assertEqual(
			text(instance, "nt.genInfo.measurement"),
			'Waren zum "gleitenden" Durchschnitt.\nForderungen - zum Nennwert.',
		)
