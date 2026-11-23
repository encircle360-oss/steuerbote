"""What Kleinst states under the balance sheet and klein in its Anhang."""

from unittest import TestCase

from steuerbote.hgb.notes import (
	CATALOGUE,
	EXEMPT_FOR_KLEIN,
	NotesError,
	Placement,
	Requirement,
	catalogue,
)
from steuerbote.hgb.size import SizeClass


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
