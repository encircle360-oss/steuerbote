"""The loader of the HGB-Taxonomie against the mini taxonomy (steuerbote/xbrl/tests/mini.py)."""

import shutil
import tempfile
from functools import cache
from pathlib import Path
from unittest import TestCase

from steuerbote.xbrl.taxonomy import (
	Balance,
	Content,
	Kind,
	Particle,
	PeriodType,
	Taxonomy,
	TaxonomyError,
	View,
	load,
)
from steuerbote.xbrl.tests import mini

GAAP = "de-gaap-ci"
GCD = "de-gcd"


@cache
def package() -> Path:
	"""The mini taxonomy, written once for every test that only reads it."""
	directory = Path(tempfile.mkdtemp(prefix="steuerbote-xbrl-mini-"))
	return mini.write(directory)


@cache
def view(name: View = View.FISCAL) -> Taxonomy:
	return load(package(), mini.VERSION, name)


def tearDownModule():
	if package.cache_info().currsize:
		shutil.rmtree(package(), ignore_errors=True)


class CopiedPackage(TestCase):
	"""A test that changes a file of the package works on a copy of its own."""

	def setUp(self):
		self.directory = Path(tempfile.mkdtemp(prefix="steuerbote-xbrl-copy-"))
		self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
		self.package = mini.write(self.directory / "package")

	def edit(self, name: str, old: str, new: str) -> None:
		path = next(self.package.rglob(name))
		text = path.read_text(encoding="utf-8")
		self.assertIn(old, text)
		path.write_text(text.replace(old, new), encoding="utf-8")


class ConceptsTest(TestCase):
	"""Concepts as the schemas of the modules declare them: „type, periodType, balance, abstract, nillable“ and the
	substitution group that makes an element an item or a tuple (XBRL 2.1, 5.1)."""

	def test_a_concept_is_named_by_the_prefix_of_its_module_and_its_name(self):
		concept = view().concept(f"{GAAP}:bs.ass.fixAss.tan")
		self.assertEqual(concept.name, f"{GAAP}:bs.ass.fixAss.tan")
		self.assertEqual(concept.local_name, "bs.ass.fixAss.tan")
		self.assertEqual(concept.namespace, mini.GAAP_NS)

	def test_reads_type_period_balance_and_whether_it_is_abstract_or_nillable(self):
		concept = view().concept(f"{GAAP}:bs.ass.fixAss.tan")
		self.assertEqual(
			(
				concept.kind,
				concept.item_type,
				concept.period_type,
				concept.balance,
				concept.abstract,
				concept.nillable,
			),
			(Kind.ITEM, "xbrli:monetaryItemType", PeriodType.INSTANT, Balance.DEBIT, False, True),
		)
		income = view().concept(f"{GAAP}:is.netIncome.netSales")
		self.assertEqual((income.period_type, income.balance), (PeriodType.DURATION, Balance.CREDIT))
		abstract = view().concept(f"{GCD}:genInfo")
		self.assertEqual((abstract.abstract, abstract.balance), (True, None))

	def test_knows_monetary_and_other_numeric_items(self):
		self.assertTrue(view().concept(f"{GAAP}:bs.ass").monetary)
		count = view().concept(f"{GCD}:genInfo.company.id.shareholder.currentnumber")
		self.assertEqual((count.monetary, count.numeric), (False, True))
		name = view().concept(f"{GCD}:genInfo.company.id.name")
		self.assertEqual((name.monetary, name.numeric), (False, False))

	def test_an_element_in_the_substitution_group_of_a_head_is_an_item(self):
		"""The choice values of a tuple belong to the substitution group of its head (Leitfaden A.8, B.14.1)."""
		value = view().concept(f"{GCD}:genInfo.report.id.reportStatus.reportStatus.E")
		self.assertEqual(value.kind, Kind.ITEM)
		self.assertEqual(value.substitution_group, f"{GCD}:genInfo.report.id.reportStatus.head")

	def test_the_hypercube_and_its_dimensions_are_concepts_of_their_own_kind(self):
		self.assertEqual(view().concept(f"{GAAP}:cube_.nt.ass.gross").kind, Kind.HYPERCUBE)
		self.assertEqual(view().concept(f"{GAAP}:dim_taxTrans").kind, Kind.DIMENSION)
		self.assertEqual(view().concept(f"{GAAP}:dim_taxBal").kind, Kind.ITEM)

	def test_the_concepts_of_the_dimensions_schema_share_the_namespace_of_the_gaap_module(self):
		self.assertEqual(view().concept(f"{GAAP}:all").namespace, mini.GAAP_NS)

	def test_an_unknown_concept_is_named_in_the_error(self):
		with self.assertRaisesRegex(TaxonomyError, "bs.ass.unknown"):
			view().concept(f"{GAAP}:bs.ass.unknown")
		self.assertFalse(view().has(f"{GAAP}:bs.ass.unknown"))
		self.assertTrue(view().has(f"{GAAP}:bs.ass"))

	def test_a_name_without_a_prefix_is_one_of_the_gaap_module(self):
		"""The Bilanzzuordnung and the schemes of the HGB name positions without a prefix."""
		self.assertIs(view().concept("bs.ass"), view().concept(f"{GAAP}:bs.ass"))

	def test_knows_the_namespaces_of_its_modules(self):
		self.assertEqual(dict(view().namespaces), {GCD: mini.GCD_NS, GAAP: mini.GAAP_NS})


class TuplesTest(TestCase):
	"""A tuple is a group of items: „Positionen mit Auswahlwerten“ are tuples whose content is a choice of the
	substitutes of an abstract head (Leitfaden A.8, B.14.1), others a sequence of their parts (B.5)."""

	def test_a_tuple_has_the_content_of_its_complex_type(self):
		concept = view().concept(f"{GAAP}:detailedInformation.accountBalances")
		self.assertEqual(concept.kind, Kind.TUPLE)
		self.assertEqual((concept.item_type, concept.period_type), (None, None))
		self.assertEqual(
			concept.content,
			Content(
				"sequence",
				1,
				1,
				(
					Particle(f"{GAAP}:detailedInformation.accountbalances.positionName", 1, 1),
					Particle(f"{GAAP}:detailedInformation.accountbalances.accountNumber", 1, 1),
					Particle(f"{GAAP}:detailedInformation.accountbalances.accountDescription", 1, 1),
					Particle(f"{GAAP}:detailedInformation.accountbalances.amount", 1, 1),
				),
			),
		)

	def test_a_part_of_a_sequence_may_be_left_out_or_repeated(self):
		content = view().concept(f"{GAAP}:hbst.transfer").content
		self.assertEqual(
			content.particles,
			(Particle(f"{GAAP}:hbst.transfer.kind", 1, 1), Particle(f"{GAAP}:hbst.transfer.bsAss", 0, None)),
		)

	def test_a_choice_names_the_head_whose_substitutes_it_takes(self):
		content = view().concept(f"{GCD}:genInfo.report.id.reportStatus").content
		self.assertEqual(
			content, Content("choice", 1, 1, (Particle(f"{GCD}:genInfo.report.id.reportStatus.head", 1, 1),))
		)
		self.assertEqual(
			view().substitutes(f"{GCD}:genInfo.report.id.reportStatus.head"),
			(
				f"{GCD}:genInfo.report.id.reportStatus.reportStatus.E",
				f"{GCD}:genInfo.report.id.reportStatus.reportStatus.V",
			),
		)

	def test_a_multiple_choice_may_repeat(self):
		"""„Positionen zur Mehrfachauswahl (Es muss mindestens einer der vorgegebenen Auswahlwerte angegeben werden,
		d.h. es können auch mehrere Auswahlwerte angegeben werden.)“ (Leitfaden A.8)"""
		content = view().concept(f"{GCD}:genInfo.report.id.reportElement").content
		self.assertEqual((content.group, content.min_occurs, content.max_occurs), ("choice", 1, None))

	def test_names_the_concepts_a_tuple_takes(self):
		self.assertEqual(
			view().parts(f"{GCD}:genInfo.report.id.statementType"),
			(
				f"{GCD}:genInfo.report.id.statementType.statementType.E",
				f"{GCD}:genInfo.report.id.statementType.statementType.EB",
			),
		)
		self.assertEqual(
			view().parts(f"{GCD}:genInfo.company.id.idNo"),
			(
				f"{GCD}:genInfo.company.id.idNo.type.companyId.ST13",
				f"{GCD}:genInfo.company.id.idNo.type.companyId.BF4",
			),
		)

	def test_knows_the_tuples_each_part_belongs_to(self):
		self.assertEqual(
			view().tuples_of(f"{GCD}:genInfo.company.id.shareholder.name"),
			(f"{GCD}:genInfo.company.id.shareholder",),
		)
		self.assertEqual(
			view().tuples_of(f"{GCD}:genInfo.report.id.reportStatus.reportStatus.E"),
			(f"{GCD}:genInfo.report.id.reportStatus",),
		)
		self.assertEqual(view().tuples_of(f"{GAAP}:bs.ass"), ())


class DiscoveryTest(CopiedPackage):
	"""The files of an entry point are those it reaches by import, include and linkbaseRef, and the schemas its
	linkbases locate (XBRL 2.1, 3.2, „discoverable taxonomy set“)."""

	def test_reaches_a_schema_of_another_module_by_a_relative_path(self):
		self.assertIn(mini.HGBROLE, load(self.package, mini.VERSION, View.FISCAL).roles)

	def test_leaves_the_schemas_of_xbrl_org_to_the_validator(self):
		"""The package refers to the schemas of XBRL 2.1 and XBRL Dimensions at www.xbrl.org, which it does not hold."""
		self.assertTrue(load(self.package, mini.VERSION, View.FISCAL).has(f"{GAAP}:bs.ass"))

	def test_maps_an_absolute_url_of_xbrl_de_to_the_package(self):
		"""A.6: references to the taxonomy as absolute URLs under http://www.xbrl.de/taxonomies/."""
		self.edit(
			f"{mini.GAAP}-shell.xsd",
			f'schemaLocation="{mini.GAAP}.xsd"',
			f'schemaLocation="http://www.xbrl.de/taxonomies/{mini.GAAP}/{mini.GAAP}.xsd"',
		)
		self.assertTrue(load(self.package, mini.VERSION, View.COMMERCIAL).has(f"{GAAP}:bs.ass"))

	def test_a_reference_within_its_own_file_reaches_no_other(self):
		self.edit(
			f"{mini.GAAP}-presentation-balanceSheet.xml",
			f'xlink:href="{mini.GAAP}.xsd#balanceSheet"',
			'xlink:href="#balanceSheet"',
		)
		self.assertTrue(load(self.package, mini.VERSION, View.FISCAL).has(f"{GAAP}:bs.ass"))

	def test_a_missing_file_is_named(self):
		(self.package / mini.GAAP / f"{mini.GAAP}-calculation-balanceSheet.xml").unlink()
		with self.assertRaisesRegex(TaxonomyError, "calculation-balanceSheet.xml"):
			load(self.package, mini.VERSION, View.FISCAL)

	def test_a_missing_entry_point_is_named(self):
		(self.package / mini.GAAP / f"{mini.GAAP}-shell-microbilg.xsd").unlink()
		with self.assertRaisesRegex(TaxonomyError, "shell-microbilg.xsd"):
			load(self.package, mini.VERSION, View.COMMERCIAL_MICROBILG)

	def test_refuses_a_reference_outside_the_package(self):
		self.edit(
			f"{mini.GAAP}-shell.xsd",
			f'schemaLocation="{mini.GAAP}.xsd"',
			'schemaLocation="../../etc/passwd.xsd"',
		)
		with self.assertRaisesRegex(TaxonomyError, "outside"):
			load(self.package, mini.VERSION, View.COMMERCIAL)

	def test_refuses_a_file_that_is_no_xml(self):
		(self.package / mini.GAAP / f"{mini.GAAP}-presentation-balanceSheet.xml").write_text(
			"kein XML", encoding="utf-8"
		)
		with self.assertRaisesRegex(TaxonomyError, "presentation-balanceSheet.xml"):
			load(self.package, mini.VERSION, View.FISCAL)

	def test_the_schemas_of_a_namespace_agree_on_its_prefix(self):
		self.edit(f"{mini.GAAP}-dimensions.xsd", 'xmlns:de-gaap-ci="', 'xmlns:other="')
		with self.assertRaisesRegex(TaxonomyError, "prefix other, other schemas with de-gaap-ci"):
			load(self.package, mini.VERSION, View.FISCAL)

	def test_refuses_a_schema_with_concepts_of_a_namespace_without_a_prefix(self):
		self.edit(f"{mini.GAAP}-dimensions.xsd", 'xmlns:de-gaap-ci="', 'xmlns="')
		with self.assertRaisesRegex(TaxonomyError, "declares no prefix"):
			load(self.package, mini.VERSION, View.FISCAL)

	def test_refuses_a_qname_with_a_prefix_its_schema_does_not_declare(self):
		self.edit(
			f"{mini.GCD}.xsd",
			'id="de-gcd_genInfo" substitutionGroup="xbrli:item"',
			'id="de-gcd_genInfo" substitutionGroup="nowhere:item"',
		)
		with self.assertRaisesRegex(TaxonomyError, "nowhere:item"):
			load(self.package, mini.VERSION, View.FISCAL)

	def test_an_element_in_no_group_of_items_or_tuples_is_no_concept(self):
		"""The domain of a typed dimension, and a part of a reference such as hgbref:legalFormEU."""
		self.edit(
			"hgbrole-2025-04-01.xsd",
			"</xs:schema>",
			'<xs:element name="legalFormEU" id="ref_legalFormEU" substitutionGroup="link:part" type="xs:string"/>'
			"</xs:schema>",
		)
		loaded = load(self.package, mini.VERSION, View.FISCAL)
		self.assertFalse(loaded.has(f"{GAAP}:dim_keyType"))
		self.assertFalse(loaded.has("de-hgbrole:legalFormEU"))
		self.assertEqual(set(loaded.namespaces), {GCD, GAAP})

	def test_a_substitution_group_names_an_element_of_the_taxonomy(self):
		self.edit(
			f"{mini.GCD}.xsd",
			'substitutionGroup="de-gcd:genInfo.report.id.reportStatus.head"',
			'substitutionGroup="de-gcd:genInfo.report.id.unknown.head"',
		)
		with self.assertRaisesRegex(TaxonomyError, "unknown.head"):
			load(self.package, mini.VERSION, View.FISCAL)

	def test_refuses_a_cycle_of_substitution_groups(self):
		self.edit(
			f"{mini.GCD}.xsd",
			'id="de-gcd_genInfo.report.id.reportStatus.head" substitutionGroup="xbrli:item"',
			'id="de-gcd_genInfo.report.id.reportStatus.head" substitutionGroup="de-gcd:genInfo.report.id.reportStatus.reportStatus.E"',
		)
		with self.assertRaisesRegex(TaxonomyError, "cycle"):
			load(self.package, mini.VERSION, View.FISCAL)


class ViewsTest(TestCase):
	def test_each_view_starts_from_the_gcd_and_one_gaap_entry_point(self):
		"""„Von den oben aufgeführten Einstiegsschemata ist immer genau eines zusammen mit dem Einstiegsschema für die
		GCD, „de-gcd-2025-04-01-shell.xsd", zu referenzieren.“ (Leitfaden B.3)"""
		version = mini.VERSION
		self.assertEqual(View.FISCAL.entry_points(version), (version.gcd_shell, version.fiscal_shell))
		self.assertEqual(View.COMMERCIAL.entry_points(version), (version.gcd_shell, version.commercial_shell))
		self.assertEqual(
			View.COMMERCIAL_MICROBILG.entry_points(version), (version.gcd_shell, version.microbilg_shell)
		)

	def test_a_loaded_view_names_its_version_and_entry_points(self):
		loaded = view(View.COMMERCIAL)
		self.assertEqual((loaded.version, loaded.view), ("6.9", View.COMMERCIAL))
		self.assertEqual(loaded.entry_points, View.COMMERCIAL.entry_points(mini.VERSION))
