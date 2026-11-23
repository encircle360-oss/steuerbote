"""The balance sheet of § 266 HGB and the income statement of § 275 HGB with the concepts of taxonomy 6.9."""

from unittest import TestCase

from steuerbote.hgb import size
from steuerbote.hgb.schemes import (
	BALANCE_SHEETS,
	LEVELS,
	BalanceSheetScheme,
	Direction,
	Level,
	SchemeError,
	VermerkKind,
	balance_sheet_scheme,
)
from steuerbote.hgb.size import SizeClass, UnknownYearError

# § 266 Abs. 2 and 3 HGB, as read on gesetze-im-internet.de on 23 November 2026, with the items § 42 Abs. 3 GmbHG
# shows separately and those §§ 268 and 272 HGB add.
AKTIVA = (
	("A.", "Anlagevermögen", "bs.ass.fixAss"),
	("I.", "Immaterielle Vermögensgegenstände", "bs.ass.fixAss.intan"),
	(
		"1.",
		"Selbst geschaffene gewerbliche Schutzrechte und ähnliche Rechte und Werte",
		"bs.ass.fixAss.intan.selfmade",
	),
	(
		"2.",
		"entgeltlich erworbene Konzessionen, gewerbliche Schutzrechte und ähnliche Rechte und Werte sowie Lizenzen "
		"an solchen Rechten und Werten",
		"bs.ass.fixAss.intan.concessionBrands",
	),
	("3.", "Geschäfts- oder Firmenwert", "bs.ass.fixAss.intan.goodwill"),
	("4.", "geleistete Anzahlungen", "bs.ass.fixAss.intan.advPaym"),
	("II.", "Sachanlagen", "bs.ass.fixAss.tan"),
	(
		"1.",
		"Grundstücke, grundstücksgleiche Rechte und Bauten einschließlich der Bauten auf fremden Grundstücken",
		"bs.ass.fixAss.tan.landBuildings",
	),
	("2.", "technische Anlagen und Maschinen", "bs.ass.fixAss.tan.machinery"),
	("3.", "andere Anlagen, Betriebs- und Geschäftsausstattung", "bs.ass.fixAss.tan.otherEquipm"),
	("4.", "geleistete Anzahlungen und Anlagen im Bau", "bs.ass.fixAss.tan.inConstrAdvPaym"),
	("III.", "Finanzanlagen", "bs.ass.fixAss.fin"),
	("1.", "Anteile an verbundenen Unternehmen", "bs.ass.fixAss.fin.sharesInAffil"),
	("2.", "Ausleihungen an verbundene Unternehmen", "bs.ass.fixAss.fin.loansToAffil"),
	("3.", "Beteiligungen", "bs.ass.fixAss.fin.particip"),
	(
		"4.",
		"Ausleihungen an Unternehmen, mit denen ein Beteiligungsverhältnis besteht",
		"bs.ass.fixAss.fin.loansToParticip",
	),
	("5.", "Wertpapiere des Anlagevermögens", "bs.ass.fixAss.fin.securities"),
	("6.", "sonstige Ausleihungen", "bs.ass.fixAss.fin.otherLoans"),
	("", "Ausleihungen an Gesellschafter", "bs.ass.fixAss.fin.loansToSharehold"),
	("B.", "Umlaufvermögen", "bs.ass.currAss"),
	("I.", "Vorräte", "bs.ass.currAss.inventory"),
	("1.", "Roh-, Hilfs- und Betriebsstoffe", "bs.ass.currAss.inventory.material"),
	("2.", "unfertige Erzeugnisse, unfertige Leistungen", "bs.ass.currAss.inventory.inProgress"),
	("3.", "fertige Erzeugnisse und Waren", "bs.ass.currAss.inventory.finishedAndMerch"),
	("4.", "geleistete Anzahlungen", "bs.ass.currAss.inventory.advPaymPaid"),
	("II.", "Forderungen und sonstige Vermögensgegenstände", "bs.ass.currAss.receiv"),
	("1.", "Forderungen aus Lieferungen und Leistungen", "bs.ass.currAss.receiv.trade"),
	("2.", "Forderungen gegen verbundene Unternehmen", "bs.ass.currAss.receiv.affil"),
	(
		"3.",
		"Forderungen gegen Unternehmen, mit denen ein Beteiligungsverhältnis besteht",
		"bs.ass.currAss.receiv.particip",
	),
	("4.", "sonstige Vermögensgegenstände", "bs.ass.currAss.receiv.other"),
	("", "Forderungen gegen Gesellschafter", "bs.ass.currAss.receiv.shareholders"),
	("III.", "Wertpapiere", "bs.ass.currAss.securities"),
	("1.", "Anteile an verbundenen Unternehmen", "bs.ass.currAss.securities.affil"),
	("2.", "sonstige Wertpapiere", "bs.ass.currAss.securities.other"),
	(
		"IV.",
		"Kassenbestand, Bundesbankguthaben, Guthaben bei Kreditinstituten und Schecks",
		"bs.ass.currAss.cashEquiv",
	),
	("C.", "Rechnungsabgrenzungsposten", "bs.ass.prepaidExp"),
	("D.", "Aktive latente Steuern", "bs.ass.defTax"),
	("E.", "Aktiver Unterschiedsbetrag aus der Vermögensverrechnung", "bs.ass.SurplusFromOffsetting"),
	("", "Nicht durch Eigenkapital gedeckter Fehlbetrag", "bs.ass.deficitNotCoveredByCapital"),
)
PASSIVA = (
	("A.", "Eigenkapital", "bs.eqLiab.equity"),
	("I.", "Gezeichnetes Kapital", "bs.eqLiab.equity.subscribed"),
	("II.", "Kapitalrücklage", "bs.eqLiab.equity.capRes"),
	("III.", "Gewinnrücklagen", "bs.eqLiab.equity.revenueRes"),
	("1.", "gesetzliche Rücklage", "bs.eqLiab.equity.revenueRes.legal"),
	(
		"2.",
		"Rücklage für Anteile an einem herrschenden oder mehrheitlich beteiligten Unternehmen",
		"bs.eqLiab.equity.revenueRes.sharesParentComp",
	),
	("3.", "satzungsmäßige Rücklagen", "bs.eqLiab.equity.revenueRes.statutory"),
	("4.", "andere Gewinnrücklagen", "bs.eqLiab.equity.revenueRes.other"),
	("IV.", "Gewinnvortrag/Verlustvortrag", "bs.eqLiab.equity.retainedEarnings"),
	("V.", "Jahresüberschuss/Jahresfehlbetrag", "bs.eqLiab.equity.netIncome"),
	("IV.", "Bilanzgewinn/Bilanzverlust", "bs.eqLiab.equity.profitLoss"),
	("", "Nicht durch Eigenkapital gedeckter Fehlbetrag", "bs.eqLiab.equity.deficitNotCoveredByCapital"),
	("B.", "Rückstellungen", "bs.eqLiab.accruals"),
	("1.", "Rückstellungen für Pensionen und ähnliche Verpflichtungen", "bs.eqLiab.accruals.pensions"),
	("2.", "Steuerrückstellungen", "bs.eqLiab.accruals.tax"),
	("3.", "sonstige Rückstellungen", "bs.eqLiab.accruals.other"),
	("C.", "Verbindlichkeiten", "bs.eqLiab.liab"),
	("1.", "Anleihen", "bs.eqLiab.liab.securities"),
	("2.", "Verbindlichkeiten gegenüber Kreditinstituten", "bs.eqLiab.liab.bank"),
	("3.", "erhaltene Anzahlungen auf Bestellungen", "bs.eqLiab.liab.advPaym"),
	("4.", "Verbindlichkeiten aus Lieferungen und Leistungen", "bs.eqLiab.liab.trade"),
	(
		"5.",
		"Verbindlichkeiten aus der Annahme gezogener Wechsel und der Ausstellung eigener Wechsel",
		"bs.eqLiab.liab.notes",
	),
	("6.", "Verbindlichkeiten gegenüber verbundenen Unternehmen", "bs.eqLiab.liab.assocComp"),
	(
		"7.",
		"Verbindlichkeiten gegenüber Unternehmen, mit denen ein Beteiligungsverhältnis besteht",
		"bs.eqLiab.liab.particip",
	),
	("8.", "sonstige Verbindlichkeiten", "bs.eqLiab.liab.other"),
	("", "Verbindlichkeiten gegenüber Gesellschaftern", "bs.eqLiab.liab.shareholders"),
	("D.", "Rechnungsabgrenzungsposten", "bs.eqLiab.defIncome"),
	("E.", "Passive latente Steuern", "bs.eqLiab.defTax"),
)
SEPARATE_SHAREHOLDER_ITEMS = (
	"bs.ass.fixAss.fin.loansToSharehold",
	"bs.ass.currAss.receiv.shareholders",
	"bs.eqLiab.liab.shareholders",
)


def rows(root):
	return [(position.marker, position.label, position.concept) for position in root.walk()][1:]


class BalanceSheetSchemeTest(TestCase):
	def setUp(self):
		self.scheme = balance_sheet_scheme(2026)

	def test_holds_the_positions_of_section_266_in_their_order(self):
		self.assertEqual(rows(self.scheme.aktiva), list(AKTIVA))
		self.assertEqual(rows(self.scheme.passiva), list(PASSIVA))

	def test_levels_follow_the_letters_and_numerals_of_the_law(self):
		levels = {Level.LETTER: "ABCDE", Level.ROMAN: ("I", "II", "III", "IV", "V")}
		for position in self.scheme.positions():
			with self.subTest(concept=position.concept):
				marker = position.marker.rstrip(".")
				if position.level is Level.LETTER and marker:
					self.assertIn(marker, levels[Level.LETTER])
				elif position.level is Level.ROMAN and marker:
					self.assertIn(marker, levels[Level.ROMAN])
				elif position.level is Level.ARABIC and marker:
					self.assertTrue(marker.isdigit())
		self.assertIs(self.scheme.position("bs.ass.deficitNotCoveredByCapital").level, Level.LETTER)
		self.assertIs(self.scheme.position("bs.eqLiab.equity.profitLoss").level, Level.ROMAN)
		self.assertIs(self.scheme.position("bs.eqLiab.equity.deficitNotCoveredByCapital").level, Level.ROMAN)
		for concept in SEPARATE_SHAREHOLDER_ITEMS:
			self.assertIs(self.scheme.position(concept).level, Level.ARABIC)

	def test_every_position_is_an_ancestor_concept_of_the_positions_under_it(self):
		for root in (self.scheme.aktiva, self.scheme.passiva):
			for position in root.walk():
				for child in position.children:
					with self.subTest(child=child.concept):
						self.assertTrue(child.concept.startswith(position.concept + "."))

	def test_names_each_concept_once(self):
		concepts = [position.concept for position in self.scheme.positions()]
		self.assertEqual(len(concepts), len(set(concepts)))
		self.assertEqual((self.scheme.aktiva.concept, self.scheme.passiva.concept), ("bs.ass", "bs.eqLiab"))

	def test_assets_are_on_the_debit_side_and_equity_and_liabilities_on_the_credit_side(self):
		self.assertEqual({position.direction for position in self.scheme.aktiva.walk()}, {Direction.DEBIT})
		self.assertEqual({position.direction for position in self.scheme.passiva.walk()}, {Direction.CREDIT})

	def test_cites_the_law_of_each_position(self):
		for position in self.scheme.positions():
			with self.subTest(concept=position.concept):
				self.assertRegex(position.reference, r"^§ \d+[a-z]? Abs\. \d")
		self.assertEqual(
			self.scheme.position("bs.ass.fixAss.intan.goodwill").reference, "§ 266 Abs. 2 A. I. 3. HGB"
		)
		self.assertEqual(self.scheme.position("bs.eqLiab.liab.other").reference, "§ 266 Abs. 3 C. 8. HGB")
		for concept in SEPARATE_SHAREHOLDER_ITEMS:
			self.assertEqual(self.scheme.position(concept).reference, "§ 42 Abs. 3 GmbHG")
		self.assertEqual(
			self.scheme.position("bs.eqLiab.equity.profitLoss").reference, "§ 268 Abs. 1 Satz 2 HGB"
		)
		self.assertEqual(
			self.scheme.position("bs.ass.deficitNotCoveredByCapital").reference, "§ 268 Abs. 3 HGB"
		)

	def test_computes_the_totals_the_result_of_the_year_and_the_deficit(self):
		computed = {position.concept for position in self.scheme.positions() if position.computed}
		self.assertEqual(
			computed,
			{
				"bs.ass",
				"bs.eqLiab",
				"bs.eqLiab.equity.netIncome",
				"bs.ass.deficitNotCoveredByCapital",
				"bs.eqLiab.equity.deficitNotCoveredByCapital",
			},
		)

	def test_finds_a_position_by_its_concept(self):
		self.assertEqual(self.scheme.position("bs.ass.currAss.cashEquiv").marker, "IV.")
		with self.assertRaises(SchemeError):
			self.scheme.position("bs.ass.currAss.cashEquiv.bank")
		self.assertTrue(self.scheme.has("bs.ass.currAss"))
		self.assertFalse(self.scheme.has("bs.ass.other"))

	def test_knows_the_position_above_each(self):
		self.assertEqual(self.scheme.parent("bs.ass.fixAss.intan.goodwill").concept, "bs.ass.fixAss.intan")
		self.assertEqual(self.scheme.parent("bs.ass.fixAss").concept, "bs.ass")
		self.assertIsNone(self.scheme.parent("bs.ass"))


class BalanceSheetYearsTest(TestCase):
	def test_holds_the_years_of_the_size_thresholds(self):
		self.assertEqual(tuple(BALANCE_SHEETS), tuple(size.YEARS))
		for year, scheme in BALANCE_SHEETS.items():
			with self.subTest(year=year):
				self.assertIsInstance(scheme, BalanceSheetScheme)
				self.assertEqual(scheme.year, year)

	def test_names_the_concepts_of_the_taxonomy_6_9(self):
		self.assertEqual(balance_sheet_scheme(2026).taxonomy, "6.9")

	def test_refuses_a_year_it_does_not_know(self):
		with self.assertRaises(UnknownYearError):
			balance_sheet_scheme(2027)
		with self.assertRaises(TypeError):
			balance_sheet_scheme("2026")  # type: ignore[arg-type]


class SizeClassFormTest(TestCase):
	"""§ 266 Abs. 1 HGB: Kleinst shows the letters, klein the letters and roman numerals, the others every item."""

	def setUp(self):
		self.scheme = balance_sheet_scheme(2026)

	def concepts(self, size_class):
		return [position.concept for position in self.scheme.visible(size_class)]

	def test_kleinst_shows_the_positions_with_letters(self):
		self.assertEqual(
			self.concepts(SizeClass.KLEINST),
			[
				"bs.ass.fixAss",
				"bs.ass.currAss",
				"bs.ass.prepaidExp",
				"bs.ass.defTax",
				"bs.ass.SurplusFromOffsetting",
				"bs.ass.deficitNotCoveredByCapital",
				"bs.eqLiab.equity",
				"bs.eqLiab.accruals",
				"bs.eqLiab.liab",
				"bs.eqLiab.defIncome",
				"bs.eqLiab.defTax",
			],
		)

	def test_klein_shows_the_letters_and_the_roman_numerals(self):
		self.assertEqual(
			self.concepts(SizeClass.KLEIN),
			[
				"bs.ass.fixAss",
				"bs.ass.fixAss.intan",
				"bs.ass.fixAss.tan",
				"bs.ass.fixAss.fin",
				"bs.ass.currAss",
				"bs.ass.currAss.inventory",
				"bs.ass.currAss.receiv",
				"bs.ass.currAss.securities",
				"bs.ass.currAss.cashEquiv",
				"bs.ass.prepaidExp",
				"bs.ass.defTax",
				"bs.ass.SurplusFromOffsetting",
				"bs.ass.deficitNotCoveredByCapital",
				"bs.eqLiab.equity",
				"bs.eqLiab.equity.subscribed",
				"bs.eqLiab.equity.capRes",
				"bs.eqLiab.equity.revenueRes",
				"bs.eqLiab.equity.retainedEarnings",
				"bs.eqLiab.equity.netIncome",
				"bs.eqLiab.equity.profitLoss",
				"bs.eqLiab.equity.deficitNotCoveredByCapital",
				"bs.eqLiab.accruals",
				"bs.eqLiab.liab",
				"bs.eqLiab.defIncome",
				"bs.eqLiab.defTax",
			],
		)

	def test_mittelgross_and_gross_show_every_position(self):
		every = [
			position.concept for position in self.scheme.positions() if position.level is not Level.TOTAL
		]
		self.assertEqual(self.concepts(SizeClass.MITTELGROSS), every)
		self.assertEqual(self.concepts(SizeClass.GROSS), every)

	def test_cites_the_sentence_of_section_266_for_each_class(self):
		self.assertEqual(
			{size_class: form.reference for size_class, form in LEVELS.items()},
			{
				SizeClass.KLEINST: "§ 266 Abs. 1 Satz 4 HGB",
				SizeClass.KLEIN: "§ 266 Abs. 1 Satz 3 HGB",
				SizeClass.MITTELGROSS: "§ 266 Abs. 1 Satz 2 HGB",
				SizeClass.GROSS: "§ 266 Abs. 1 Satz 2 HGB",
			},
		)

	def test_knows_whether_a_class_shows_a_position(self):
		self.assertTrue(self.scheme.shows("bs.ass.currAss.receiv", SizeClass.KLEIN))
		self.assertFalse(self.scheme.shows("bs.ass.currAss.receiv", SizeClass.KLEINST))
		self.assertFalse(self.scheme.shows("bs.ass", SizeClass.GROSS))


RECEIVABLES = VermerkKind.RECEIVABLES_OVER_ONE_YEAR
UP_TO_ONE = VermerkKind.LIABILITIES_UP_TO_ONE_YEAR
OVER_ONE = VermerkKind.LIABILITIES_OVER_ONE_YEAR
SHAREHOLDERS = VermerkKind.SHAREHOLDERS
LIABILITY_ITEMS = (
	"bs.eqLiab.liab.bank",
	"bs.eqLiab.liab.advPaym",
	"bs.eqLiab.liab.trade",
	"bs.eqLiab.liab.notes",
	"bs.eqLiab.liab.assocComp",
	"bs.eqLiab.liab.particip",
	"bs.eqLiab.liab.shareholders",
)
RECEIVABLE_ITEMS = (
	"bs.ass.currAss.receiv.trade",
	"bs.ass.currAss.receiv.affil",
	"bs.ass.currAss.receiv.particip",
	"bs.ass.currAss.receiv.other",
	"bs.ass.currAss.receiv.shareholders",
)


class VermerkeTest(TestCase):
	"""The „davon“ amounts each class notes at its positions."""

	def setUp(self):
		self.scheme = balance_sheet_scheme(2026)

	def shown(self, size_class):
		return {
			position.concept: [vermerk.kind for vermerk in self.scheme.vermerke(position.concept, size_class)]
			for position in self.scheme.visible(size_class)
			if self.scheme.vermerke(position.concept, size_class)
		}

	def test_kleinst_notes_the_remaining_terms_and_the_shareholders_at_its_letters(self):
		self.assertEqual(
			self.shown(SizeClass.KLEINST),
			{
				"bs.ass.fixAss": [SHAREHOLDERS],
				"bs.ass.currAss": [RECEIVABLES, SHAREHOLDERS],
				"bs.eqLiab.liab": [UP_TO_ONE, OVER_ONE, SHAREHOLDERS],
			},
		)

	def test_klein_notes_them_at_its_roman_numerals_and_adds_capital_and_profit_carried_forward(self):
		self.assertEqual(
			self.shown(SizeClass.KLEIN),
			{
				"bs.ass.fixAss.fin": [SHAREHOLDERS],
				"bs.ass.currAss.receiv": [RECEIVABLES, SHAREHOLDERS],
				"bs.eqLiab.equity.subscribed": [VermerkKind.UNCALLED_CAPITAL],
				"bs.eqLiab.equity.profitLoss": [VermerkKind.PROFIT_CARRIED_FORWARD],
				"bs.eqLiab.liab": [UP_TO_ONE, OVER_ONE, SHAREHOLDERS],
			},
		)

	def test_the_larger_classes_note_the_remaining_terms_at_each_item(self):
		expected = {
			"bs.ass.fixAss.fin": [SHAREHOLDERS],
			"bs.ass.currAss.receiv": [SHAREHOLDERS],
			**{concept: [RECEIVABLES] for concept in RECEIVABLE_ITEMS},
			"bs.eqLiab.equity.subscribed": [VermerkKind.UNCALLED_CAPITAL],
			"bs.eqLiab.equity.profitLoss": [VermerkKind.PROFIT_CARRIED_FORWARD],
			"bs.eqLiab.liab": [SHAREHOLDERS],
			"bs.eqLiab.liab.securities": [VermerkKind.CONVERTIBLE, UP_TO_ONE, OVER_ONE],
			**{concept: [UP_TO_ONE, OVER_ONE] for concept in LIABILITY_ITEMS},
			"bs.eqLiab.liab.other": [VermerkKind.TAXES, VermerkKind.SOCIAL_SECURITY, UP_TO_ONE, OVER_ONE],
		}
		self.assertEqual(self.shown(SizeClass.MITTELGROSS), expected)
		self.assertEqual(self.shown(SizeClass.GROSS), expected)

	def test_names_the_concept_of_each_vermerk_where_it_is_shown(self):
		def concepts(concept, size_class):
			return [vermerk.concept for vermerk in self.scheme.vermerke(concept, size_class)]

		self.assertEqual(
			concepts("bs.ass.currAss", SizeClass.KLEINST),
			["bs.ass.currAss.receiv.above1year", "bs.ass.currAss.receiv.shareholder"],
		)
		self.assertEqual(
			concepts("bs.eqLiab.liab", SizeClass.KLEIN),
			["bs.eqLiab.liab.upTo1year", "bs.eqLiab.liab.above1year", "bs.eqLiab.liab.ofWhichToShareholders"],
		)
		self.assertEqual(
			concepts("bs.eqLiab.liab.bank", SizeClass.GROSS),
			["bs.eqLiab.liab.bank.upTo1year", "bs.eqLiab.liab.bank.above1year"],
		)
		self.assertEqual(
			concepts("bs.eqLiab.liab.other", SizeClass.GROSS),
			[
				"bs.eqLiab.liab.other.theroffTax",
				"bs.eqLiab.liab.other.thereoffSocSec",
				"bs.eqLiab.liab.other.upTo1year",
				"bs.eqLiab.liab.other.above1year",
			],
		)
		self.assertEqual(
			concepts("bs.ass.fixAss.fin", SizeClass.KLEIN), ["bs.ass.fixAss.fin.LoansToShareholder"]
		)
		self.assertEqual(
			concepts("bs.eqLiab.equity.profitLoss", SizeClass.KLEIN),
			["bs.eqLiab.equity.profitLoss.retainedEarnings"],
		)

	def test_a_vermerk_covers_the_position_it_names_as_its_scope(self):
		for position in self.scheme.positions():
			for vermerk in position.vermerke:
				with self.subTest(position=position.concept, vermerk=vermerk.kind):
					scope = self.scheme.position(vermerk.scope)
					self.assertIn(scope, list(position.walk()))
		currAss = self.scheme.position("bs.ass.currAss")
		self.assertEqual({vermerk.scope for vermerk in currAss.vermerke}, {"bs.ass.currAss.receiv"})
		self.assertEqual(
			{vermerk.scope for vermerk in self.scheme.position("bs.ass.fixAss").vermerke},
			{"bs.ass.fixAss.fin"},
		)
		self.assertEqual(
			{vermerk.scope for vermerk in self.scheme.position("bs.eqLiab.liab").vermerke}, {"bs.eqLiab.liab"}
		)

	def test_cites_the_law_of_each_vermerk(self):
		references = {
			RECEIVABLES: "§ 268 Abs. 4 Satz 1 HGB",
			UP_TO_ONE: "§ 268 Abs. 5 Satz 1 HGB",
			OVER_ONE: "§ 268 Abs. 5 Satz 1 HGB",
			SHAREHOLDERS: "§ 42 Abs. 3 GmbHG",
			VermerkKind.CONVERTIBLE: "§ 266 Abs. 3 C. 1. HGB",
			VermerkKind.TAXES: "§ 266 Abs. 3 C. 8. HGB",
			VermerkKind.SOCIAL_SECURITY: "§ 266 Abs. 3 C. 8. HGB",
			VermerkKind.UNCALLED_CAPITAL: "§ 272 Abs. 1 Satz 2 HGB",
			VermerkKind.PROFIT_CARRIED_FORWARD: "§ 268 Abs. 1 Satz 2 HGB",
		}
		for position in self.scheme.positions():
			for vermerk in position.vermerke:
				with self.subTest(position=position.concept, vermerk=vermerk.kind):
					self.assertEqual(vermerk.reference, references[vermerk.kind])
					self.assertTrue(vermerk.label.startswith(("davon ", "nicht eingeforderte")))

	def test_the_shareholder_vermerke_take_the_separate_items_and_the_davon_concepts_of_the_taxonomy(self):
		liabilities = self.scheme.vermerke("bs.eqLiab.liab", SizeClass.KLEIN)[-1]
		self.assertEqual(
			liabilities.members,
			(
				"bs.eqLiab.liab.shareholders",
				"bs.eqLiab.liab.trade.shareholders",
				"bs.eqLiab.liab.other.shareholders",
			),
		)
		receivables = self.scheme.vermerke("bs.ass.currAss.receiv", SizeClass.KLEIN)[-1]
		self.assertEqual(
			receivables.members,
			("bs.ass.currAss.receiv.shareholders", "bs.ass.currAss.receiv.other.shareholders"),
		)
		loans = self.scheme.vermerke("bs.ass.fixAss.fin", SizeClass.KLEIN)[0]
		self.assertEqual(
			loans.members, ("bs.ass.fixAss.fin.loansToSharehold", "bs.ass.fixAss.fin.otherLoans.partners")
		)

	def test_a_position_the_class_does_not_show_notes_nothing(self):
		self.assertEqual(self.scheme.vermerke("bs.ass.currAss.receiv", SizeClass.KLEINST), ())
