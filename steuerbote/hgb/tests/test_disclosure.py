"""What a GmbH or UG publishes of its Jahresabschluss, by when, after which Feststellung, and what being late costs."""

from unittest import TestCase

from steuerbote.hgb.disclosure import DisclosureError, Mode, Part, default_mode, modes, publication
from steuerbote.hgb.size import SizeClass


class ModesTest(TestCase):
	"""§ 326 Abs. 2 HGB: a Kleinst may deposit its balance sheet instead of having it published."""

	def test_a_kleinst_may_deposit_or_publish_and_deposits_unless_told_otherwise(self):
		self.assertEqual(modes(SizeClass.KLEINST), (Mode.HINTERLEGUNG, Mode.OFFENLEGUNG))
		self.assertIs(default_mode(SizeClass.KLEINST), Mode.HINTERLEGUNG)

	def test_every_other_class_publishes(self):
		for size_class in (SizeClass.KLEIN, SizeClass.MITTELGROSS, SizeClass.GROSS):
			with self.subTest(size_class=size_class):
				self.assertEqual(modes(size_class), (Mode.OFFENLEGUNG,))
				self.assertIs(default_mode(size_class), Mode.OFFENLEGUNG)

	def test_refuses_a_hinterlegung_for_a_company_above_kleinst(self):
		with self.assertRaises(DisclosureError):
			publication(SizeClass.KLEIN, Mode.HINTERLEGUNG)


class PublicationTest(TestCase):
	def test_a_kleinst_transmits_its_balance_sheet_with_the_angaben_under_it(self):
		deposited = publication(SizeClass.KLEINST)
		self.assertEqual(
			(
				deposited.mode,
				deposited.parts,
				deposited.below_balance_sheet,
				deposited.public,
				deposited.notice,
				deposited.reference,
			),
			(Mode.HINTERLEGUNG, (Part.BILANZ,), True, False, True, "§ 326 Abs. 2, § 9 Abs. 6 Satz 3 HGB"),
		)
		published = publication(SizeClass.KLEINST, Mode.OFFENLEGUNG)
		self.assertEqual(
			(published.public, published.notice, published.reference), (True, False, "§ 326 Abs. 2 HGB")
		)

	def test_klein_publishes_balance_sheet_and_anhang_without_what_concerns_the_income_statement(self):
		small = publication(SizeClass.KLEIN)
		self.assertEqual(
			(small.parts, small.notes_without_income_statement, small.public, small.reference),
			((Part.BILANZ, Part.ANHANG), True, True, "§ 326 Abs. 1 HGB"),
		)

	def test_no_class_steuerbote_prepares_publishes_an_income_statement_a_lagebericht_or_an_audit(self):
		for size_class in (SizeClass.KLEINST, SizeClass.KLEIN):
			with self.subTest(size_class=size_class):
				parts = publication(size_class).parts
				self.assertNotIn(Part.GUV, parts)
				self.assertNotIn(Part.LAGEBERICHT, parts)
				self.assertTrue(publication(size_class).prepared)

	def test_the_larger_classes_publish_everything_and_are_not_prepared_by_steuerbote(self):
		for size_class, reference in (
			(SizeClass.MITTELGROSS, "§ 325 Abs. 1, § 327 HGB"),
			(SizeClass.GROSS, "§ 325 Abs. 1 HGB"),
		):
			with self.subTest(size_class=size_class):
				larger = publication(size_class)
				self.assertEqual(
					(larger.parts, larger.prepared, larger.reference),
					(
						(Part.BILANZ, Part.GUV, Part.ANHANG, Part.LAGEBERICHT, Part.BESTAETIGUNGSVERMERK),
						False,
						reference,
					),
				)

	def test_names_each_part_as_the_law_does(self):
		self.assertEqual(
			[part.value for part in Part],
			[
				"Bilanz",
				"Gewinn- und Verlustrechnung",
				"Anhang",
				"Lagebericht",
				"Bestätigungsvermerk oder Vermerk über dessen Versagung",
			],
		)
