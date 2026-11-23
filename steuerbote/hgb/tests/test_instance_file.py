"""The file of the Offenlegung: the instance as a report of the profile DISCLOSURE, its checks and the document the
writer of steuerbote/xbrl/writer.py makes of it, against the mini taxonomy of steuerbote/hgb/tests/taxonomy.py and the
files of steuerbote/hgb/tests/fixtures written from the invented companies."""

from dataclasses import replace
from decimal import Decimal
from unittest import TestCase

from steuerbote.hgb import instance
from steuerbote.hgb.instance import HeldBackError, InstanceError
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import Finding, Severity
from steuerbote.hgb.tests import companies
from steuerbote.hgb.tests import taxonomy as mini
from steuerbote.hgb.tests.companies import GOLDEN, canonical, golden
from steuerbote.xbrl import writer
from steuerbote.xbrl.checks import Code
from steuerbote.xbrl.facts import Item, Period, amount
from steuerbote.xbrl.taxonomy import View

ST = Period.STICHTAG
PRIOR = Period.VORJAHR_STICHTAG


def built(name: str) -> instance.Instance:
	return companies.instances()[name]


def changed(name: str, *, without: tuple[tuple[str, Period], ...] = (), adding: tuple[Item, ...] = ()):
	"""An instance of the invented companies without some of its items and with others."""
	original = built(name)
	kept = tuple(
		fact
		for fact in original.facts
		if not (isinstance(fact, Item) and (fact.concept, fact.period) in without)
	)
	return replace(original, facts=(*kept, *adding))


def codes(findings) -> set[str]:
	return {str(finding.code) for finding in findings}


class ReportTest(TestCase):
	"""The instance as a report of the profile DISCLOSURE: its facts for the entry points of its view, in full
	euros."""

	def test_the_facts_for_the_entry_points_of_the_view(self):
		for name in GOLDEN:
			offenlegung = built(name)
			taxonomy = mini.view(offenlegung.view)
			report = instance.report(offenlegung, taxonomy)
			with self.subTest(name=name):
				self.assertEqual(report.schema_refs, writer.entry_points(taxonomy))
				self.assertEqual(report.entity, offenlegung.entity)
				self.assertEqual(report.periods, offenlegung.periods)
				self.assertEqual(report.facts, offenlegung.facts)

	def test_the_amounts_in_full_euros(self):
		"""The statement in full euros (steuerbote/hgb/statement.py, in_full_euros()); that the register wants them
		so is unverified."""
		offenlegung = built("klein")
		self.assertEqual(instance.report(offenlegung, mini.view(offenlegung.view)).monetary_decimals, 0)

	def test_refuses_the_view_of_the_other_class(self):
		with self.assertRaises(InstanceError):
			instance.report(built("klein"), mini.view(View.COMMERCIAL_MICROBILG))
		with self.assertRaises(InstanceError):
			instance.report(built("kleinst"), mini.view(View.COMMERCIAL))

	def test_refuses_the_taxonomy_of_another_version(self):
		other = replace(mini.view(View.COMMERCIAL), version="7.0")
		with self.assertRaises(InstanceError):
			instance.report(built("klein"), other)


class CheckTest(TestCase):
	"""The checks of the profile DISCLOSURE with the concepts the class publishes: the positions admissible in a
	Handelsbilanz, what the class shows, both closing dates, the calculation, the Oberpositionen and the contexts
	(steuerbote/xbrl/profiles.py)."""

	def test_the_invented_companies_pass_every_check(self):
		for name, offenlegung in companies.instances().items():
			with self.subTest(name=name):
				self.assertEqual(instance.check(offenlegung, mini.view(offenlegung.view)), ())

	def test_a_position_the_class_does_not_show(self):
		"""„nur die in den Absätzen 2 und 3 mit Buchstaben bezeichneten Posten“ (§ 266 Abs. 1 Satz 4 HGB)"""
		offenlegung = changed(
			"kleinst",
			adding=(
				amount("de-gaap-ci:bs.ass.fixAss.tan", ST, Decimal("18401")),
				amount("de-gaap-ci:bs.ass.fixAss.tan", PRIOR, Decimal("21000")),
			),
		)
		found = instance.check(offenlegung, mini.view(offenlegung.view))
		self.assertEqual(
			{(finding.code, finding.concept) for finding in found},
			{(Code.NOT_PUBLISHED, "de-gaap-ci:bs.ass.fixAss.tan")},
		)

	def test_a_total_its_positions_do_not_make(self):
		offenlegung = changed(
			"klein",
			without=(("de-gaap-ci:bs.ass.prepaidExp", ST),),
			adding=(amount("de-gaap-ci:bs.ass.prepaidExp", ST, Decimal("4801")),),
		)
		found = instance.check(offenlegung, mini.view(offenlegung.view))
		self.assertEqual(
			{(finding.code, finding.concept) for finding in found}, {(Code.CALCULATION, "de-gaap-ci:bs.ass")}
		)

	def test_a_posten_without_its_previous_year(self):
		"""„In der Bilanz ... ist zu jedem Posten der entsprechende Betrag des vorhergehenden Geschäftsjahrs
		anzugeben.“ (§ 265 Abs. 2 Satz 1 HGB)"""
		offenlegung = changed("kleinst", without=(("de-gaap-ci:bs.ass.prepaidExp", PRIOR),))
		found = instance.check(offenlegung, mini.view(offenlegung.view))
		self.assertIn(
			(Code.PRIOR_YEAR_AMOUNT, "de-gaap-ci:bs.ass.prepaidExp"),
			{(finding.code, finding.concept) for finding in found},
		)

	def test_refuses_the_view_of_the_other_class(self):
		with self.assertRaises(InstanceError):
			instance.check(built("kleinst"), mini.view(View.COMMERCIAL))


class WriteTest(TestCase):
	"""The document of the Offenlegung, one XML file of one order on the Publikations-Plattform
	(steuerbote/hgb/upload.py)."""

	def test_the_files_of_the_invented_companies(self):
		for name in GOLDEN:
			offenlegung = built(name)
			with self.subTest(name=name):
				self.assertEqual(
					canonical(instance.write(offenlegung, mini.view(offenlegung.view))),
					canonical(golden(name)),
				)

	def test_the_same_jahresabschluss_gives_the_same_bytes(self):
		for name in GOLDEN:
			with self.subTest(name=name):
				first = instance.write(built(name), mini.view(built(name).view))
				self.assertEqual(instance.write(built(name), mini.view(built(name).view)), first)

	def test_the_document_of_the_writer(self):
		offenlegung = built("kleinst")
		taxonomy = mini.view(offenlegung.view)
		self.assertEqual(
			instance.write(offenlegung, taxonomy),
			writer.write(instance.report(offenlegung, taxonomy), taxonomy),
		)

	def test_what_holds_the_jahresabschluss_back_holds_the_file_back(self):
		notes = replace(companies.KLEIN_NOTES, answers=companies.KLEIN_NOTES.answers[1:])
		held = instance.build(
			companies.klein_statement(),
			SizeClass.KLEIN,
			notes,
			companies.KLEIN_DISCLOSURE,
			companies.KLEIN_GCD,
		)
		with self.assertRaises(HeldBackError) as raised:
			instance.write(held, mini.view(held.view))
		self.assertEqual(raised.exception.findings, held.findings)
		self.assertIn("JA-ANGABE-OFFEN", str(raised.exception))

	def test_what_the_checks_of_the_profile_find_holds_it_back(self):
		offenlegung = changed(
			"kleinst", adding=(amount("de-gaap-ci:bs.ass.fixAss.tan", ST, Decimal("18401")),)
		)
		with self.assertRaises(HeldBackError) as raised:
			instance.write(offenlegung, mini.view(offenlegung.view))
		self.assertEqual(codes(raised.exception.findings), {Code.NOT_PUBLISHED, Code.PRIOR_YEAR_AMOUNT})
		self.assertIn(Code.NOT_PUBLISHED, str(raised.exception))

	def test_a_hint_holds_nothing_back(self):
		hint = Finding("JA-HINWEIS", Severity.HINT, "Ein Hinweis.", "§ 264 Abs. 1 HGB")
		offenlegung = replace(built("kleinst"), findings=(hint,))
		self.assertEqual(
			instance.write(offenlegung, mini.view(offenlegung.view)),
			instance.write(built("kleinst"), mini.view(offenlegung.view)),
		)

	def test_refuses_the_view_of_the_other_class(self):
		with self.assertRaises(InstanceError):
			instance.write(built("klein"), mini.view(View.COMMERCIAL_MICROBILG))
