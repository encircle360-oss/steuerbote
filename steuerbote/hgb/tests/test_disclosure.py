"""What a GmbH or UG publishes of its Jahresabschluss, by when, after which Feststellung, and what being late costs."""

from datetime import date
from unittest import TestCase

from steuerbote.hgb.disclosure import (
	DeadlineKind,
	Director,
	DisclosureCode,
	DisclosureError,
	Mode,
	Part,
	Signature,
	adoption_deadline,
	adoption_problems,
	deadline_kept,
	default_mode,
	disclosure_deadline,
	modes,
	preparation_deadline,
	publication,
	transmission_problems,
)
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import Severity

END_2026 = date(2026, 12, 31)


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


class PreparationDeadlineTest(TestCase):
	"""§ 264 Abs. 1 Satz 3 und 4 HGB: in the first three months of the next fiscal year, six for a small company."""

	def test_a_small_company_draws_up_within_six_months(self):
		for size_class in (SizeClass.KLEINST, SizeClass.KLEIN):
			with self.subTest(size_class=size_class):
				deadline = preparation_deadline(END_2026, size_class)
				self.assertEqual(
					(deadline.kind, deadline.due, deadline.reference, deadline.assumed_class),
					(DeadlineKind.AUFSTELLUNG, date(2027, 6, 30), "§ 264 Abs. 1 Satz 3 und 4 HGB", False),
				)

	def test_a_larger_company_within_three_months(self):
		self.assertEqual(preparation_deadline(END_2026, SizeClass.MITTELGROSS).due, date(2027, 3, 31))

	def test_without_a_class_the_shorter_period_applies(self):
		deadline = preparation_deadline(END_2026, None)
		self.assertEqual((deadline.due, deadline.assumed_class), (date(2027, 3, 31), True))

	def test_counts_the_months_from_the_day_after_any_closing_date(self):
		self.assertEqual(preparation_deadline(date(2026, 11, 15), SizeClass.GROSS).due, date(2027, 2, 15))
		self.assertEqual(preparation_deadline(date(2026, 8, 31), SizeClass.KLEIN).due, date(2027, 2, 28))
		self.assertEqual(preparation_deadline(date(2027, 3, 30), SizeClass.GROSS).due, date(2027, 6, 30))
		self.assertEqual(preparation_deadline(date(2026, 8, 30), SizeClass.KLEIN).due, date(2027, 2, 28))


class AdoptionDeadlineTest(TestCase):
	"""§ 42a Abs. 2 Satz 1 GmbHG: Feststellung within eight months, eleven for a small company."""

	def test_a_small_company_adopts_within_eleven_months(self):
		for size_class in (SizeClass.KLEINST, SizeClass.KLEIN):
			with self.subTest(size_class=size_class):
				deadline = adoption_deadline(END_2026, size_class)
				self.assertEqual(
					(deadline.kind, deadline.due, deadline.reference),
					(DeadlineKind.FESTSTELLUNG, date(2027, 11, 30), "§ 42a Abs. 2 Satz 1 GmbHG"),
				)

	def test_a_larger_company_within_eight_months(self):
		self.assertEqual(adoption_deadline(END_2026, SizeClass.GROSS).due, date(2027, 8, 31))

	def test_without_a_class_the_eight_months_apply(self):
		deadline = adoption_deadline(END_2026, None)
		self.assertEqual((deadline.due, deadline.assumed_class), (date(2027, 8, 31), True))


class DisclosureDeadlineTest(TestCase):
	"""§ 325 Abs. 1a Satz 1 HGB: „spätestens ein Jahr nach dem Abschlussstichtag“."""

	def test_is_due_one_year_after_the_closing_date(self):
		deadline = disclosure_deadline(END_2026)
		self.assertEqual(
			(deadline.kind, deadline.due, deadline.reference, deadline.on_weekend),
			(DeadlineKind.OFFENLEGUNG, date(2027, 12, 31), "§ 325 Abs. 1a Satz 1 HGB", False),
		)
		self.assertEqual(disclosure_deadline(date(2026, 6, 30)).due, date(2027, 6, 30))

	def test_a_closing_date_on_29_february_ends_a_year_later_on_28_february(self):
		self.assertEqual(disclosure_deadline(date(2028, 2, 29)).due, date(2029, 2, 28))

	def test_keeps_a_day_on_a_weekend_and_says_so(self):
		deadline = disclosure_deadline(date(2027, 12, 31))
		self.assertEqual((deadline.due, deadline.on_weekend), (date(2028, 12, 31), True))
		saturday = disclosure_deadline(date(2026, 7, 31))
		self.assertEqual((saturday.due, saturday.on_weekend), (date(2027, 7, 31), True))


class DeadlineKeptTest(TestCase):
	"""§ 325 Abs. 4 Satz 2 HGB: the day of transmission counts, and only for the festgestellter Jahresabschluss."""

	def test_a_transmission_up_to_the_last_day_keeps_the_deadline(self):
		self.assertTrue(deadline_kept(END_2026, date(2027, 12, 31), date(2027, 11, 30)))
		self.assertFalse(deadline_kept(END_2026, date(2028, 1, 1), date(2027, 11, 30)))

	def test_a_transmission_before_the_feststellung_keeps_nothing(self):
		self.assertFalse(deadline_kept(END_2026, date(2027, 6, 1), date(2027, 7, 1)))
		self.assertFalse(deadline_kept(END_2026, date(2027, 6, 1), None))


ADOPTED = date(2027, 5, 10)
DIRECTORS = (
	Director("Erika Beispiel"),
	Director("Max Muster", start=date(2025, 3, 1)),
	Director("Paul Vorgänger", end=date(2026, 6, 30)),
)
SIGNATURES = (
	Signature("Erika Beispiel", "Geschäftsführerin", "Musterstadt", ADOPTED),
	Signature("  max muster ", "Geschäftsführer", "Musterstadt", ADOPTED),
)


def coded(findings) -> list[tuple[str, str]]:
	return [(finding.code, finding.concept) for finding in findings]


class AdoptionProblemsTest(TestCase):
	"""What has to be there before the disclosure: the Feststellung and the signature of every Geschäftsführer."""

	def test_a_festgestellter_jahresabschluss_signed_by_every_geschaeftsfuehrer_raises_nothing(self):
		self.assertEqual(adoption_problems(END_2026, ADOPTED, DIRECTORS, SIGNATURES), ())

	def test_without_its_feststellung_it_cannot_be_disclosed(self):
		(finding,) = adoption_problems(END_2026, None, DIRECTORS, SIGNATURES)
		self.assertEqual(
			(finding.code, finding.severity, finding.reference),
			(
				DisclosureCode.NOT_ADOPTED,
				Severity.ERROR,
				"§ 325 Abs. 1 Satz 1 Nr. 1, § 328 Abs. 1a Satz 1 HGB",
			),
		)

	def test_a_feststellung_before_the_end_of_the_fiscal_year_is_refused(self):
		self.assertEqual(
			coded(adoption_problems(END_2026, END_2026, DIRECTORS, SIGNATURES)),
			[(DisclosureCode.ADOPTED_EARLY, "")],
		)

	def test_every_geschaeftsfuehrer_in_office_signs_with_a_date(self):
		findings = adoption_problems(END_2026, ADOPTED, DIRECTORS, SIGNATURES[:1])
		self.assertEqual(coded(findings), [(DisclosureCode.UNSIGNED, "Max Muster")])
		self.assertEqual(
			findings[0].reference, "§ 245 Satz 1 HGB; Bundesamt für Justiz, FAQ zu Inhalts- und Formverstößen"
		)
		undated = (SIGNATURES[0], Signature("Max Muster", "Geschäftsführer", "Musterstadt", None))
		self.assertEqual(
			coded(adoption_problems(END_2026, ADOPTED, DIRECTORS, undated)),
			[(DisclosureCode.UNDATED, "Max Muster")],
		)

	def test_a_signature_cannot_date_from_the_fiscal_year_itself(self):
		early = (SIGNATURES[0], Signature("Max Muster", "Geschäftsführer", "Musterstadt", END_2026))
		self.assertEqual(
			coded(adoption_problems(END_2026, ADOPTED, DIRECTORS, early)),
			[(DisclosureCode.SIGNED_EARLY, "Max Muster")],
		)

	def test_a_geschaeftsfuehrer_out_of_office_on_the_day_of_the_feststellung_need_not_sign(self):
		self.assertTrue(DIRECTORS[2].in_office(date(2026, 6, 30)))
		self.assertFalse(DIRECTORS[2].in_office(ADOPTED))
		self.assertFalse(DIRECTORS[1].in_office(date(2025, 2, 28)))


class TransmissionProblemsTest(TestCase):
	def test_a_transmission_after_the_feststellung_with_a_dated_signature_raises_nothing(self):
		self.assertEqual(transmission_problems(ADOPTED, date(2027, 6, 1), SIGNATURES), ())

	def test_a_transmission_before_the_feststellung_is_refused(self):
		(finding,) = transmission_problems(ADOPTED, date(2027, 5, 9), SIGNATURES)
		self.assertEqual(
			(finding.code, finding.reference),
			(DisclosureCode.BEFORE_ADOPTION, "§ 325 Abs. 1 Satz 1 Nr. 1, Abs. 4 Satz 2 HGB"),
		)
		self.assertEqual(
			coded(transmission_problems(None, date(2027, 5, 9), SIGNATURES)),
			[(DisclosureCode.BEFORE_ADOPTION, "")],
		)

	def test_a_transmission_needs_a_dated_signature(self):
		undated = (Signature("Erika Beispiel", "Geschäftsführerin", "Musterstadt", None),)
		self.assertEqual(
			coded(transmission_problems(ADOPTED, date(2027, 6, 1), undated)),
			[(DisclosureCode.NO_SIGNATURE, "")],
		)
