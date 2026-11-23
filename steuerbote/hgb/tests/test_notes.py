"""What Kleinst states under the balance sheet and klein in its Anhang."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.hgb.notes import (
	CATALOGUE,
	EXEMPT_FOR_KLEIN,
	REVIEW_ITEMS,
	AdvanceKind,
	Answer,
	Contingency,
	ContingentLiability,
	NoteAnswer,
	NoteCode,
	NotesError,
	OfficerAdvance,
	OfficerGroup,
	Placement,
	RegisterData,
	Requirement,
	advances,
	answer_problems,
	catalogue,
	contingencies,
	entry_problems,
	register_problems,
)
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import Severity


def codes(entries) -> list[str]:
	return [entry.item.code for entry in entries]


class KleinstTest(TestCase):
	"""§ 264 Abs. 1 Satz 5 HGB: no Anhang for a Kleinst that states three things under its balance sheet."""

	def test_states_the_angaben_of_section_264_under_the_balance_sheet(self):
		entries = catalogue(SizeClass.KLEINST)
		self.assertEqual(codes(entries), ["HAFTUNGSVERHAELTNISSE", "ORGANKREDITE", "ZUSAETZLICHE-ANGABEN"])
		self.assertEqual({entry.placement for entry in entries}, {Placement.UNDER_BALANCE_SHEET})
		self.assertEqual({entry.requirement for entry in entries}, {Requirement.IF_APPLICABLE})
		self.assertEqual({entry.published for entry in entries}, {True})

	def test_cites_the_numbers_of_section_264_and_the_rules_they_point_to(self):
		self.assertEqual(
			[entry.item.reference for entry in catalogue(SizeClass.KLEINST)],
			[
				"§ 264 Abs. 1 Satz 5 Nr. 1, § 268 Abs. 7, § 251 HGB",
				"§ 264 Abs. 1 Satz 5 Nr. 2, § 285 Nr. 9 Buchst. c HGB",
				"§ 264 Abs. 2 Satz 2 und 4 HGB",
			],
		)

	def test_explains_an_eigenkapital_of_zero_under_the_balance_sheet(self):
		entries = catalogue(SizeClass.KLEINST, equity_zero=True)
		entry = entries[-1]
		self.assertEqual(
			(entry.item.code, entry.requirement, entry.placement),
			("EIGENKAPITAL-NULL", Requirement.REQUIRED, Placement.UNDER_BALANCE_SHEET),
		)
		self.assertIn("Bundesamt für Justiz", entry.item.reference)
		self.assertNotIn("EIGENKAPITAL-NULL", codes(catalogue(SizeClass.KLEIN, equity_zero=True)))

	def test_names_the_concepts_of_the_taxonomy_for_the_angaben(self):
		self.assertEqual(
			[entry.item.concept for entry in catalogue(SizeClass.KLEINST, equity_zero=True)],
			["bs.contingLiab", "nt.relationships.creditsToMembers", "ntmi.other", "ntmi.other"],
		)

	def test_the_angabe_on_own_shares_is_for_an_aktiengesellschaft_only(self):
		self.assertNotIn("EIGENE-AKTIEN", codes(catalogue(SizeClass.KLEINST)))
		(own_shares,) = [item for item in CATALOGUE if item.code == "EIGENE-AKTIEN"]
		self.assertEqual(
			(own_shares.kleinst, own_shares.klein, own_shares.reference),
			(None, None, "§ 264 Abs. 1 Satz 5 Nr. 3 HGB, § 160 Abs. 3 Satz 2 AktG"),
		)


class KleinTest(TestCase):
	"""§§ 284 to 288 HGB: the Anhang of klein without what § 288 Abs. 1 and § 274a HGB spare it."""

	def setUp(self):
		self.entries = catalogue(SizeClass.KLEIN)

	def test_holds_the_items_of_the_anhang_in_the_order_of_the_law(self):
		self.assertEqual(
			codes(self.entries),
			[
				"ZUSAETZLICHE-ANGABEN",
				"DARSTELLUNGSSTETIGKEIT",
				"VORJAHRESBETRAEGE",
				"MITZUGEHOERIGKEIT",
				"HAFTUNGSVERHAELTNISSE",
				"AUSSERPLANMAESSIGE-ABSCHREIBUNGEN",
				"BEWERTUNGSMETHODEN",
				"METHODENABWEICHUNGEN",
				"FREMDKAPITALZINSEN",
				"VERBINDLICHKEITEN",
				"FINANZIELLE-VERPFLICHTUNGEN",
				"ARBEITNEHMER",
				"ORGANKREDITE",
				"FIRMENWERT",
				"MUTTERUNTERNEHMEN",
				"ZEITWERT",
				"BEWERTUNGSEINHEITEN",
				"VERRECHNUNG",
				"AUSSERGEWOEHNLICHES",
			],
		)
		self.assertEqual({entry.placement for entry in self.entries}, {Placement.NOTES})

	def test_requires_the_methods_and_the_average_number_of_arbeitnehmer_and_the_rest_where_it_applies(self):
		self.assertEqual(
			[entry.item.code for entry in self.entries if entry.requirement is Requirement.REQUIRED],
			["BEWERTUNGSMETHODEN", "ARBEITNEHMER"],
		)

	def test_publishes_the_anhang_without_what_concerns_the_income_statement(self):
		self.assertEqual(
			[entry.item.code for entry in self.entries if not entry.published],
			["AUSSERPLANMAESSIGE-ABSCHREIBUNGEN", "AUSSERGEWOEHNLICHES"],
		)

	def test_cites_the_law_of_each_item(self):
		references = {entry.item.code: entry.item.reference for entry in self.entries}
		self.assertEqual(references["ARBEITNEHMER"], "§ 285 Nr. 7, § 288 Abs. 1 Nr. 2 HGB")
		self.assertEqual(references["MUTTERUNTERNEHMEN"], "§ 285 Nr. 14a, § 288 Abs. 1 Nr. 3 HGB")
		self.assertEqual(references["VERBINDLICHKEITEN"], "§ 285 Nr. 1 HGB")
		for entry in self.entries:
			with self.subTest(code=entry.item.code):
				self.assertRegex(entry.item.reference, r"^§ \d+")
				self.assertTrue(entry.item.label)

	def test_spares_klein_what_section_288_and_section_274a_spare_it(self):
		self.assertEqual(
			EXEMPT_FOR_KLEIN,
			(
				"§ 264c Abs. 2 Satz 9 HGB",
				"§ 265 Abs. 4 Satz 2 HGB",
				"§ 284 Abs. 2 Nr. 3 HGB",
				"§ 284 Abs. 3 HGB",
				"§ 285 Nr. 2, 3, 4, 8, 9 Buchst. a und b, Nr. 10 bis 12, 14, 15, 15a, 17 bis 19, 21, 22, 24, 26 bis 30a, "
				"32 bis 34 HGB",
				"die Trennung nach Gruppen bei § 285 Nr. 7 HGB",
				"der Ort des Konzernabschlusses bei § 285 Nr. 14a HGB",
				"§ 268 Abs. 4 Satz 2, Abs. 5 Satz 3 und Abs. 6 HGB",
				"§ 274 HGB",
			),
		)


class ClassesTest(TestCase):
	def test_has_a_catalogue_for_kleinst_and_klein_only(self):
		for size_class in (SizeClass.MITTELGROSS, SizeClass.GROSS):
			with self.subTest(size_class=size_class), self.assertRaises(NotesError):
				catalogue(size_class)

	def test_codes_are_unique_and_every_item_serves_a_class(self):
		item_codes = [item.code for item in CATALOGUE]
		self.assertEqual(len(item_codes), len(set(item_codes)))
		for item in CATALOGUE:
			with self.subTest(code=item.code):
				self.assertTrue(item.kleinst or item.klein or item.code == "EIGENE-AKTIEN")


YES, NO, NOT_APPLICABLE = Answer.YES, Answer.NO, Answer.NOT_APPLICABLE


def answers(size_class, **given) -> list[NoteAnswer]:
	"""An answer to every item of the class: nein, unless ``given`` names another for its code."""
	result = []
	for entry in catalogue(size_class):
		answer = given.get(entry.item.code.replace("-", "_"))
		if answer is None:
			answer = (
				NoteAnswer(entry.item.code, YES, text="Lineare Abschreibung.")
				if entry.requirement is Requirement.REQUIRED
				else NoteAnswer(entry.item.code, NO)
			)
		result.append(answer)
	return result


class AnswersTest(TestCase):
	"""The Annual Accounts answer each Angabe with ja, nein or entfällt, and a ja with a text or an amount."""

	def test_a_complete_set_of_answers_raises_nothing(self):
		for size_class in (SizeClass.KLEINST, SizeClass.KLEIN):
			with self.subTest(size_class=size_class):
				self.assertEqual(answer_problems(catalogue(size_class), answers(size_class)), ())

	def test_an_item_without_an_answer_holds_the_jahresabschluss_back(self):
		given = answers(SizeClass.KLEIN)[1:]
		(finding,) = answer_problems(catalogue(SizeClass.KLEIN), given)
		self.assertEqual(
			(finding.code, finding.severity, finding.reference, finding.concept),
			(NoteCode.UNANSWERED, Severity.ERROR, "§ 264 Abs. 2 Satz 2 und 4 HGB", "ZUSAETZLICHE-ANGABEN"),
		)
		self.assertIn("Zusätzliche Angaben", finding.text)

	def test_a_required_item_needs_a_ja(self):
		for answer in (NO, NOT_APPLICABLE):
			with self.subTest(answer=answer):
				given = answers(SizeClass.KLEIN, ARBEITNEHMER=NoteAnswer("ARBEITNEHMER", answer))
				(finding,) = answer_problems(catalogue(SizeClass.KLEIN), given)
				self.assertEqual((finding.code, finding.concept), (NoteCode.DENIED, "ARBEITNEHMER"))

	def test_an_item_where_it_applies_takes_nein_or_entfaellt(self):
		given = answers(SizeClass.KLEINST, ORGANKREDITE=NoteAnswer("ORGANKREDITE", NOT_APPLICABLE))
		self.assertEqual(answer_problems(catalogue(SizeClass.KLEINST), given), ())

	def test_a_ja_needs_a_text_or_an_amount(self):
		empty = answers(
			SizeClass.KLEINST, HAFTUNGSVERHAELTNISSE=NoteAnswer("HAFTUNGSVERHAELTNISSE", YES, text="  ")
		)
		(finding,) = answer_problems(catalogue(SizeClass.KLEINST), empty)
		self.assertEqual((finding.code, finding.concept), (NoteCode.EMPTY, "HAFTUNGSVERHAELTNISSE"))
		amount = answers(SizeClass.KLEIN, ARBEITNEHMER=NoteAnswer("ARBEITNEHMER", YES, amount=Decimal("0")))
		self.assertEqual(answer_problems(catalogue(SizeClass.KLEIN), amount), ())

	def test_an_answer_to_an_item_the_class_does_not_owe_is_refused(self):
		given = [
			*answers(SizeClass.KLEINST),
			NoteAnswer("BEWERTUNGSMETHODEN", YES, text="Anschaffungskosten."),
		]
		(finding,) = answer_problems(catalogue(SizeClass.KLEINST), given)
		self.assertEqual((finding.code, finding.concept), (NoteCode.UNKNOWN, "BEWERTUNGSMETHODEN"))

	def test_an_item_answered_twice_is_refused(self):
		given = [*answers(SizeClass.KLEINST), NoteAnswer("ORGANKREDITE", NO)]
		(finding,) = answer_problems(catalogue(SizeClass.KLEINST), given)
		self.assertEqual((finding.code, finding.concept), (NoteCode.TWICE, "ORGANKREDITE"))

	def test_an_eigenkapital_of_zero_needs_its_explanation(self):
		entries = catalogue(SizeClass.KLEINST, equity_zero=True)
		(finding,) = answer_problems(entries, answers(SizeClass.KLEINST))
		self.assertEqual((finding.code, finding.concept), (NoteCode.UNANSWERED, "EIGENKAPITAL-NULL"))

	def test_takes_a_decimal_amount(self):
		with self.assertRaises(TypeError):
			NoteAnswer("ARBEITNEHMER", YES, amount=3)  # type: ignore[arg-type]


GUARANTEE = ContingentLiability(
	Contingency.GUARANTEES, Decimal("20000.00"), securities="Grundschuld auf dem Betriebsgrundstück"
)
PENSION_GUARANTEE = ContingentLiability(Contingency.GUARANTEES, Decimal("5000.00"), pensions=True)
GROUP_COLLATERAL = ContingentLiability(
	Contingency.COLLATERAL,
	Decimal("12000.00"),
	securities="Sicherungsübereignung eines Fahrzeugs",
	group=True,
)
LOAN = OfficerAdvance(
	OfficerGroup.MANAGEMENT,
	AdvanceKind.LOAN,
	Decimal("10000.00"),
	Decimal("3.5"),
	"Laufzeit bis 2029, jährliche Tilgung",
	repaid=Decimal("2000.00"),
)
ADVANCE = OfficerAdvance(
	OfficerGroup.MANAGEMENT, AdvanceKind.ADVANCE, Decimal("1500.00"), Decimal("0"), "Reisekostenvorschuss"
)
BOARD_LOAN = OfficerAdvance(
	OfficerGroup.ADVISORY_BOARD,
	AdvanceKind.LOAN,
	Decimal("4000.00"),
	Decimal("2"),
	"unbesichert",
	waived=Decimal("500"),
)


class ContingenciesTest(TestCase):
	"""§ 268 Abs. 7 HGB: each kind of § 251 separately, with its securities, pensions and group noted apart."""

	def test_adds_up_each_kind_of_section_251_separately_in_its_order(self):
		self.assertEqual(
			[
				(total.kind, total.amount)
				for total in contingencies((GROUP_COLLATERAL, GUARANTEE, PENSION_GUARANTEE))
			],
			[(Contingency.GUARANTEES, Decimal("25000.00")), (Contingency.COLLATERAL, Decimal("12000.00"))],
		)

	def test_notes_the_pensions_the_group_and_the_securities_of_each_kind(self):
		guarantees, collateral = contingencies((GUARANTEE, PENSION_GUARANTEE, GROUP_COLLATERAL))
		self.assertEqual(
			(guarantees.pensions, guarantees.group, guarantees.securities),
			(Decimal("5000.00"), Decimal("0"), ("Grundschuld auf dem Betriebsgrundstück",)),
		)
		self.assertEqual(
			(collateral.pensions, collateral.group, collateral.securities),
			(Decimal("0"), Decimal("12000.00"), ("Sicherungsübereignung eines Fahrzeugs",)),
		)

	def test_names_the_wording_and_the_concepts_of_the_taxonomy_of_each_kind(self):
		self.assertEqual(
			[(kind.value, kind.concept) for kind in Contingency],
			[
				("Verbindlichkeiten aus der Begebung und Übertragung von Wechseln", "bs.contingLiab.notes"),
				("Verbindlichkeiten aus Bürgschaften", "bs.contingLiab.guarantees"),
				("Verbindlichkeiten aus Wechsel- und Scheckbürgschaften", "bs.contingLiab.guaranteesNotes"),
				("Verbindlichkeiten aus Gewährleistungsverträgen", "bs.contingLiab.warranty"),
				(
					"Haftungsverhältnisse aus der Bestellung von Sicherheiten für fremde Verbindlichkeiten",
					"bs.contingLiab.collateralisation",
				),
			],
		)
		self.assertEqual(
			(Contingency.WARRANTIES.pensions_concept, Contingency.WARRANTIES.group_concept),
			("bs.contingLiab.warranty.pension", "bs.contingLiab.warranty.assoc"),
		)

	def test_takes_decimal_amounts(self):
		with self.assertRaises(TypeError):
			ContingentLiability(Contingency.GUARANTEES, 100)  # type: ignore[arg-type]


class AdvancesTest(TestCase):
	"""§ 285 Nr. 9 Buchst. c HGB: Vorschüsse und Kredite, jeweils für jede Personengruppe."""

	def test_adds_up_the_advances_of_each_group_in_its_order(self):
		self.assertEqual(
			[
				(total.group, total.amount, total.repaid, total.waived)
				for total in advances((BOARD_LOAN, LOAN, ADVANCE))
			],
			[
				(OfficerGroup.MANAGEMENT, Decimal("11500.00"), Decimal("2000.00"), Decimal("0")),
				(OfficerGroup.ADVISORY_BOARD, Decimal("4000.00"), Decimal("0"), Decimal("500")),
			],
		)

	def test_names_the_rates_and_the_conditions_of_each_group(self):
		(management,) = advances((LOAN, ADVANCE))
		self.assertEqual(management.interest_rates, (Decimal("3.5"), Decimal("0")))
		self.assertEqual(
			management.conditions, ("Laufzeit bis 2029, jährliche Tilgung", "Reisekostenvorschuss")
		)

	def test_names_each_group_as_the_law_does(self):
		self.assertEqual(
			[group.value for group in OfficerGroup],
			[
				"Mitglieder des Geschäftsführungsorgans",
				"Mitglieder des Aufsichtsrats",
				"Mitglieder des Beirats",
				"Mitglieder einer ähnlichen Einrichtung",
			],
		)

	def test_takes_decimal_amounts(self):
		with self.assertRaises(TypeError):
			OfficerAdvance(OfficerGroup.MANAGEMENT, AdvanceKind.LOAN, Decimal("1"), 3.5, "x")  # type: ignore[arg-type]


class EntryProblemsTest(TestCase):
	def test_complete_entries_raise_nothing(self):
		self.assertEqual(entry_problems((GUARANTEE, GROUP_COLLATERAL), (LOAN, ADVANCE, BOARD_LOAN)), ())

	def test_an_advance_needs_its_rate_and_its_essential_conditions(self):
		no_rate = OfficerAdvance(
			OfficerGroup.MANAGEMENT, AdvanceKind.LOAN, Decimal("100"), None, "unbesichert"
		)
		no_conditions = OfficerAdvance(
			OfficerGroup.MANAGEMENT, AdvanceKind.LOAN, Decimal("100"), Decimal("1"), " "
		)
		findings = entry_problems((), (no_rate, no_conditions))
		self.assertEqual(
			[(finding.code, finding.severity, finding.reference) for finding in findings],
			[
				(NoteCode.NO_RATE, Severity.ERROR, "§ 285 Nr. 9 Buchst. c HGB"),
				(NoteCode.NO_CONDITIONS, Severity.ERROR, "§ 285 Nr. 9 Buchst. c HGB"),
			],
		)

	def test_amounts_cannot_be_negative(self):
		findings = entry_problems(
			(ContingentLiability(Contingency.WARRANTIES, Decimal("-1")),),
			(
				OfficerAdvance(
					OfficerGroup.MANAGEMENT,
					AdvanceKind.LOAN,
					Decimal("1"),
					Decimal("-1"),
					"x",
					repaid=Decimal("-2"),
				),
			),
		)
		self.assertEqual(
			[(finding.code, finding.reference) for finding in findings],
			[
				(NoteCode.NEGATIVE, "§ 268 Abs. 7, § 251 HGB"),
				(NoteCode.NEGATIVE, "§ 285 Nr. 9 Buchst. c HGB"),
			],
		)


REGISTER = RegisterData("Beispiel Werkstatt GmbH", "Musterstadt", "Amtsgericht Musterstadt", "HRB 12345")


class RegisterDataTest(TestCase):
	"""§ 264 Abs. 1a HGB: Firma, Sitz, Registergericht and Registernummer, and a Liquidation, in every class."""

	def test_complete_data_raise_nothing(self):
		self.assertEqual(register_problems(REGISTER), ())

	def test_names_what_is_missing_in_one_error(self):
		(finding,) = register_problems(RegisterData("Beispiel Werkstatt GmbH", " ", "", "HRB 12345"))
		self.assertEqual(
			(finding.code, finding.severity, finding.reference),
			(NoteCode.REGISTER, Severity.ERROR, "§ 264 Abs. 1a HGB"),
		)
		self.assertIn("Sitz, Registergericht", finding.text)

	def test_names_the_concepts_of_the_taxonomy_for_each_field(self):
		self.assertEqual(
			RegisterData.concepts(),
			{
				"firma": "notesBelowBalanceSheet.geninfo.company",
				"sitz": "notesBelowBalanceSheet.geninfo.location",
				"registergericht": "notesBelowBalanceSheet.geninfo.court",
				"registernummer": "notesBelowBalanceSheet.geninfo.number",
				"in_liquidation": "notesBelowBalanceSheet.geninfo.liquidationOrWindingUp",
			},
		)
		self.assertFalse(REGISTER.in_liquidation)


class ReviewItemsTest(TestCase):
	def test_leaves_the_equity_of_a_kleinst_the_classification_of_section_285_nr_31_and_the_catalogue_to_review(
		self,
	):
		self.assertEqual(
			[(item.code, item.reference) for item in REVIEW_ITEMS],
			[
				("KLEINST-EIGENKAPITAL", "§ 266 Abs. 1 Satz 4 HGB, § 42 Abs. 1 GmbHG"),
				("AUSSERGEWOEHNLICHES", "§ 285 Nr. 31, § 326 Abs. 1 Satz 2 HGB"),
				("KATALOG", "§ 264 Abs. 1 Satz 5, §§ 284 bis 288 HGB"),
			],
		)
		for item in REVIEW_ITEMS:
			with self.subTest(code=item.code):
				self.assertIn("Steuerberatung", item.text)
