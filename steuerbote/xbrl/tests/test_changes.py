"""What a version of the HGB-Taxonomie changes against the one before, and „Auf neue Taxonomie heben“ of a
Bilanzzuordnung (steuerbote/xbrl/changes.py): the data of 6.10 against both packages of esteuer.de, the lift on an
invented SKR04 mapping on the mini taxonomies of 6.9 and 6.10 (steuerbote/xbrl/tests/mini.py)."""

from dataclasses import replace
from unittest import TestCase

from lxml import etree

from steuerbote.ustva import WatchLevel
from steuerbote.xbrl import changes
from steuerbote.xbrl.changes import CHANGES, Changes, LiftError, between, lift
from steuerbote.xbrl.mapping import Excluded, Mapping, Part, Rule, Watched, check
from steuerbote.xbrl.taxonomy import Fiscal, LegalForm, View
from steuerbote.xbrl.tests import mini, real
from steuerbote.xbrl.versions import TAXONOMIES, UnknownTaxonomyError

GAAP = "de-gaap-ci:"
CRYPTO = "bs.ass.currAss.cashEquiv.cryptoAssets"
DIGITAL = "bs.ass.currAss.cashEquiv.digitalAssets"
OLD_EQUIPMENT = "bs.ass.fixAss.tan.oldEquipment"
BANK = "bs.ass.currAss.cashEquiv.bank"
BANK_LIABILITY = "bs.eqLiab.liab.bank"
GRUNDSTEUER = "is.netIncome.otherTaxes.GrSt"
MINI_CHANGES = Changes(
	"6.9",
	"6.10",
	renamed={f"{GAAP}{CRYPTO}": f"{GAAP}{DIGITAL}"},
	removed=frozenset({f"{GAAP}{OLD_EQUIPMENT}"}),
	added=frozenset(
		{f"{GAAP}{DIGITAL}", f"{GAAP}{GRUNDSTEUER}", f"{GAAP}detailedInformation.accountbalances.notPossible"}
	),
	mussfelder=(f"{GAAP}{GRUNDSTEUER}",),
	source="steuerbote/xbrl/tests/mini.py",
)
"""What the mini taxonomy of 6.10 changes against that of 6.9, invented as it is."""
# An invented SKR04 company on the mini taxonomy 6.9.
SKR04 = Mapping(
	"SKR04",
	rules=(
		Rule("0440", OLD_EQUIPMENT),
		Rule("1350", CRYPTO),
		Rule("1800", BANK, opposite=BANK_LIABILITY),
		Rule("2900", "bs.eqLiab.equity.subscribed.corp"),
		Rule("4400", "is.netIncome.netSales"),
		Rule("5400", "is.netIncome.materialServices"),
	),
	watched=(Watched("1360", WatchLevel.HINT),),
	excluded=(Excluded("9000", "Saldenvorträge der Klasse 9"),),
)
PARTS = {
	"0440": Part.BALANCE_SHEET,
	"1350": Part.BALANCE_SHEET,
	"1800": Part.BALANCE_SHEET,
	"2900": Part.BALANCE_SHEET,
	"4400": Part.INCOME_STATEMENT,
	"5400": Part.INCOME_STATEMENT,
}


def target() -> object:
	return mini.view(View.FISCAL, mini.VERSION_6_10)


class TableTest(TestCase):
	def test_every_version_but_the_first_has_the_changes_against_the_one_before(self):
		versions = list(TAXONOMIES)
		self.assertEqual(list(CHANGES), versions[1:])
		for later, earlier in zip(versions[1:], versions, strict=False):
			with self.subTest(version=later):
				self.assertEqual(
					(CHANGES[later].source_version, CHANGES[later].target_version), (earlier, later)
				)

	def test_6_10_renames_no_position(self):
		"""Every conceptRename of the versioning reports of the package 6.10 keeps the local name, only the namespace
		of the module moves from 2025-04-01 to 2026-04-01; the Änderungsnachweis names no rename in GCD and GAAP."""
		self.assertEqual(dict(CHANGES["6.10"].renamed), {})

	def test_6_10_removes_43_concepts_and_adds_39(self):
		found = CHANGES["6.10"]
		self.assertEqual((len(found.removed), len(found.added)), (43, 39))
		for name in (
			"de-gcd:genInfo.report.id.reportElement.reportElements.transmissionNotYetPossible",
			"de-gaap-ci:bs.ass.currAss.receiv.unpaidCapitalPartners",
			"de-gaap-ci:bs.ass.currAss.receiv.unpaidCapitalPartners.misc",
			"de-gaap-ci:fpl.additions.costOfRightsEStG4j",
		):
			with self.subTest(name=name):
				self.assertIn(name, found.removed)
		for name in (
			"de-gaap-ci:detailedInformation.accountbalances.notPossible",
			"de-gaap-ci:is.netIncome.otherTaxes.GrSt",
			"de-gaap-ci:nt.RegisterEStG5Abs1S2",
			"de-gcd:genInfo.company.id.shareholder.idNotAssigned",
		):
			with self.subTest(name=name):
				self.assertIn(name, found.added)
		self.assertFalse(found.removed & found.added)

	def test_6_10_has_one_new_mussfeld_the_grundsteuer(self):
		"""„Die neue Position „Grundsteuer“ [is.netIncome.otherTaxes.GrSt] ... erhält die Mussfeld-Auszeichnung sowie
		alle drei Rechtsformauszeichnungen.“ (Änderungsnachweis zum Taxonomie-Update 2026, 3.)"""
		self.assertEqual(CHANGES["6.10"].mussfelder, ("de-gaap-ci:is.netIncome.otherTaxes.GrSt",))

	def test_names_its_sources(self):
		self.assertIn("Änderungsnachweis", CHANGES["6.10"].source)
		self.assertIn("versioning", CHANGES["6.10"].source)

	def test_the_changes_between_two_versions(self):
		self.assertEqual(between("6.9", "6.10"), (CHANGES["6.10"],))
		self.assertEqual(between("6.9", "6.9"), ())
		with self.assertRaisesRegex(LiftError, "6.10 to 6.9"):
			between("6.10", "6.9")
		with self.assertRaises(UnknownTaxonomyError):
			between("6.9", "7.0")


class RealPackagesTest(TestCase):
	"""The changes of 6.10 against the packages 6.9 and 6.10 of esteuer.de (steuerbote/xbrl/tests/real.py)."""

	@classmethod
	def setUpClass(cls):
		cls.earlier, cls.later = real.view(), real.view_6_10()

	def test_the_removed_and_the_added_concepts(self):
		found = CHANGES["6.10"]
		self.assertEqual(found.removed, frozenset(self.earlier.concepts) - frozenset(self.later.concepts))
		self.assertEqual(found.added, frozenset(self.later.concepts) - frozenset(self.earlier.concepts))
		for view in (View.COMMERCIAL, View.COMMERCIAL_MICROBILG):
			with self.subTest(view=view):
				self.assertEqual(
					found.removed,
					frozenset(real.view(view).concepts) - frozenset(real.view_6_10(view).concepts),
				)

	def test_the_new_mussfelder_of_a_kapitalgesellschaft(self):
		def mandatory(taxonomy, name: str) -> bool:
			concept = taxonomy.concepts.get(name)
			return (
				concept is not None
				and concept.fiscal.requirement is not None
				and concept.fiscal.requirement.mandatory
			)

		new = tuple(
			name
			for name, concept in self.later.concepts.items()
			if mandatory(self.later, name)
			and not mandatory(self.earlier, name)
			and concept.applies_to(LegalForm.KST)
		)
		self.assertEqual(new, CHANGES["6.10"].mussfelder)

	def test_the_versioning_reports_rename_no_local_name(self):
		package = real.installation_6_10().package
		renames = 0
		for module in ("de-gaap-ci-2026-04-01", "de-gcd-2026-04-01"):
			path = (
				package
				/ "versioning"
				/ module
				/ f"{module}-shell{'-fiscal' if 'gaap' in module else ''}-with-2025-04-01-versioning.xml"
			)
			root = etree.parse(str(path)).getroot()
			for rename in root.iter("{http://xbrl.org/2013/versioning-concept-use}conceptRename"):
				names = [part.get("name").partition(":")[2] for part in rename]
				with self.subTest(names=names):
					self.assertEqual(names[0], names[1])
				renames += 1
		self.assertGreater(renames, 200)


class LiftTest(TestCase):
	"""„Auf neue Taxonomie heben“ of an invented SKR04 mapping from the mini taxonomy 6.9 to that of 6.10: the renamed
	position applied, the removed one left to decide as a watched account, the new Mussfeld listed."""

	def setUp(self):
		self.lifted = lift(SKR04, "6.10", taxonomy=target(), parts=PARTS, changes=(MINI_CHANGES,))

	def test_names_the_positions_of_the_new_version(self):
		self.assertEqual(self.lifted.mapping.taxonomy_version, "6.10")
		self.assertEqual(self.lifted.mapping.chart, "SKR04")
		self.assertEqual(check(self.lifted.mapping, target(), PARTS), ())

	def test_applies_the_rename(self):
		self.assertEqual(self.lifted.renamed, (("1350", CRYPTO, DIGITAL),))
		self.assertEqual(self.lifted.mapping.place_of("1350"), Rule("1350", DIGITAL))

	def test_leaves_a_removed_position_to_decide_as_a_blocking_watched_account(self):
		(decision,) = self.lifted.to_decide
		self.assertEqual((decision.rule, decision.position), (Rule("0440", OLD_EQUIPMENT), OLD_EQUIPMENT))
		self.assertIn("6.10", decision.text)
		self.assertEqual(self.lifted.mapping.place_of("0440"), Watched("0440", WatchLevel.BLOCKING))

	def test_lists_the_new_mussfeld(self):
		self.assertEqual(self.lifted.mussfelder, (GRUNDSTEUER,))

	def test_keeps_every_other_place(self):
		for number in ("1360", "1800", "2900", "4400", "5400", "9000"):
			with self.subTest(number=number):
				self.assertEqual(self.lifted.mapping.place_of(number), SKR04.place_of(number))
		self.assertEqual(self.lifted.mapping.numbers, SKR04.numbers)

	def test_a_removed_position_for_the_opposite_balance_is_left_to_decide_too(self):
		mapping = Mapping("SKR04", rules=(Rule("1800", BANK, opposite=OLD_EQUIPMENT),))
		(decision,) = lift(mapping, "6.10", changes=(MINI_CHANGES,)).to_decide
		self.assertEqual(decision.position, OLD_EQUIPMENT)

	def test_a_position_the_new_view_refuses_is_left_to_decide(self):
		view = target()
		refused = replace(
			view.concepts[f"{GAAP}is.netIncome.materialServices"],
			fiscal=Fiscal(legal_forms=frozenset({LegalForm.PG})),
		)
		narrowed = replace(view, concepts={**view.concepts, refused.name: refused})
		lifted = lift(SKR04, "6.10", taxonomy=narrowed, parts=PARTS, changes=(MINI_CHANGES,))
		self.assertEqual(
			[(decision.rule.account_number, decision.position) for decision in lifted.to_decide],
			[("0440", OLD_EQUIPMENT), ("5400", "is.netIncome.materialServices")],
		)
		self.assertIn("Kapitalgesellschaft", lifted.to_decide[1].text)

	def test_without_the_new_view_the_changes_alone_decide(self):
		lifted = lift(SKR04, "6.10", changes=(MINI_CHANGES,))
		self.assertEqual([decision.rule.account_number for decision in lifted.to_decide], ["0440"])

	def test_lifts_with_the_changes_of_the_table_by_default(self):
		lifted = lift(Mapping("SKR04", rules=(Rule("1800", BANK),)), "6.10")
		self.assertEqual(
			(lifted.mapping.taxonomy_version, lifted.renamed, lifted.to_decide), ("6.10", (), ())
		)
		self.assertEqual(lifted.mussfelder, (GRUNDSTEUER,))

	def test_refuses_a_target_that_is_not_later(self):
		with self.assertRaisesRegex(LiftError, "6.9"):
			lift(SKR04, "6.9")
		with self.assertRaisesRegex(LiftError, "6.10 to 6.9"):
			lift(lift(SKR04, "6.10", changes=(MINI_CHANGES,)).mapping, "6.9")

	def test_refuses_changes_of_other_versions(self):
		with self.assertRaisesRegex(LiftError, "6.8"):
			lift(SKR04, "6.10", changes=(replace(MINI_CHANGES, source_version="6.8"),))
		with self.assertRaisesRegex(LiftError, "lead to 6.10, not to 6.9"):
			lift(SKR04, "6.9", changes=(MINI_CHANGES,))


	def test_the_module_says_where_its_data_come_from(self):
		for part in ("Änderungsnachweis", "conceptRename", "Watched"):
			with self.subTest(part=part):
				self.assertIn(part, changes.__doc__)
