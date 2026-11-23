"""The loader of the HGB-Taxonomie against the mini taxonomy (steuerbote/xbrl/tests/mini.py)."""

import shutil
import tempfile
from dataclasses import replace
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path
from unittest import TestCase

from steuerbote.xbrl import taxonomy
from steuerbote.xbrl.taxonomy import (
	Arc,
	Balance,
	Content,
	DefinitionArc,
	IncomeStatementFormat,
	Kind,
	LegalForm,
	Network,
	Particle,
	PeriodType,
	Requirement,
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


class LinkbasesTest(CopiedPackage):
	"""What the linkbases of a view say, and what they leave to other views."""

	def test_reads_no_linkbase_of_an_entry_point_it_does_not_take(self):
		"""The Konzernsicht (-shell-group.xsd) is no entry point of the E-Bilanz or the Offenlegung (Leitfaden B.3)."""
		for name in View:
			with self.subTest(view=name):
				network = load(self.package, mini.VERSION, name).presentation[mini.BALANCE_SHEET]
				self.assertNotIn(f"{GAAP}:bs.ass.groupOnly", network)
				self.assertIn(f"{GAAP}:bs.ass", network)

	def test_a_locator_names_a_concept_of_the_taxonomy(self):
		self.edit(
			f"{mini.GAAP}-presentation-balanceSheet.xml",
			f"{mini.GAAP}.xsd#de-gaap-ci_bs.ass.fixAss.tan",
			f"{mini.GAAP}.xsd#de-gaap-ci_bs.ass.fixAss.missing",
		)
		with self.assertRaisesRegex(TaxonomyError, "bs.ass.fixAss.missing"):
			load(self.package, mini.VERSION, View.FISCAL)

	def test_an_arc_connects_labels_of_its_own_link(self):
		self.edit(
			f"{mini.GAAP}-presentation-balanceSheet.xml",
			'xlink:to="de-gaap-ci_bs.ass.fixAss"',
			'xlink:to="de-gaap-ci_bs.ass.nowhere"',
		)
		with self.assertRaisesRegex(TaxonomyError, "bs.ass.nowhere"):
			load(self.package, mini.VERSION, View.FISCAL)

	def test_a_prohibited_arc_takes_its_relationship_away(self):
		"""XBRL 2.1, Kap. 3.5.3.9.7.5: an arc with use="prohibited" and at least the priority of an equivalent one
		removes the relationship; the fiscal labels prohibit those of the commercial view so."""
		self.edit(
			f"{mini.GAAP}-presentation-balanceSheet.xml",
			"</link:presentationLink>",
			'<link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child" '
			'xlink:from="de-gaap-ci_bs.ass.fixAss" xlink:to="de-gaap-ci_bs.ass.fixAss.tan" order="5" use="prohibited" '
			'priority="1"/></link:presentationLink>',
		)
		network = load(self.package, mini.VERSION, View.FISCAL).presentation[mini.BALANCE_SHEET]
		self.assertNotIn(
			f"{GAAP}:bs.ass.fixAss.tan", [arc.child for arc in network.children(f"{GAAP}:bs.ass.fixAss")]
		)

	def test_a_prohibition_of_lower_priority_leaves_the_relationship(self):
		self.edit(
			f"{mini.GAAP}-presentation-balanceSheet.xml",
			"</link:presentationLink>",
			'<link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child" '
			'xlink:from="de-gaap-ci_bs.ass.fixAss" xlink:to="de-gaap-ci_bs.ass.fixAss.tan" order="5" use="prohibited" '
			'priority="-1"/></link:presentationLink>',
		)
		network = load(self.package, mini.VERSION, View.FISCAL).presentation[mini.BALANCE_SHEET]
		self.assertIn(
			f"{GAAP}:bs.ass.fixAss.tan", [arc.child for arc in network.children(f"{GAAP}:bs.ass.fixAss")]
		)

	def test_a_prohibition_reaches_only_an_equivalent_relationship(self):
		"""Relationships with another order are not equivalent (XBRL 2.1, Kap. 3.5.3.9.7.4)."""
		self.edit(
			f"{mini.GAAP}-presentation-balanceSheet.xml",
			"</link:presentationLink>",
			'<link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child" '
			'xlink:from="de-gaap-ci_bs.ass.fixAss" xlink:to="de-gaap-ci_bs.ass.fixAss.tan" order="6" use="prohibited" '
			'priority="1"/></link:presentationLink>',
		)
		network = load(self.package, mini.VERSION, View.FISCAL).presentation[mini.BALANCE_SHEET]
		self.assertIn(
			f"{GAAP}:bs.ass.fixAss.tan", [arc.child for arc in network.children(f"{GAAP}:bs.ass.fixAss")]
		)


class LabelsTest(TestCase):
	"""German labels of the roles Steuerbote shows: label, terse label, the terse label of 60 characters of the fiscal
	view and the guidance of the tax administration („Erläuterungen der Finanzverwaltung“, Leitfaden B.6)."""

	def test_the_label_of_a_concept(self):
		self.assertEqual(view(View.COMMERCIAL).label(f"{GAAP}:bs.ass.fixAss.tan"), "Sachanlagen")
		self.assertEqual(view().label(f"{GCD}:genInfo.company.id.name"), "Name des Unternehmens")

	def test_the_labels_of_the_other_roles(self):
		loaded = view()
		self.assertEqual(
			loaded.label(f"{GAAP}:bs.ass.fixAss.intan.concessionBrands", taxonomy.TERSE_LABEL), "Konzessionen"
		)
		self.assertEqual(
			loaded.label(f"{GAAP}:bs.ass.fixAss.intan.concessionBrands", taxonomy.TERSE60_LABEL),
			"Konzessionen, Rechte, Lizenzen",
		)
		self.assertEqual(
			loaded.label(f"{GAAP}:bs.ass.fixAss.tan", taxonomy.GUIDANCE),
			"Grundstücke, Bauten, Maschinen und Ausstattung.",
		)

	def test_a_role_without_a_label_falls_back_to_the_standard_label(self):
		self.assertEqual(view().label(f"{GAAP}:bs.ass", taxonomy.TERSE_LABEL), "Bilanzsumme, Summe Aktiva")

	def test_a_concept_without_a_label_shows_its_name(self):
		self.assertEqual(view().label(f"{GAAP}:dim_keyType"), "dim_keyType")

	def test_reads_german_labels_only(self):
		labels = view().labels[f"{GCD}:genInfo.company.id.name"]
		self.assertNotIn("(English)", " ".join(labels.values()))

	def test_leaves_out_the_documentation(self):
		self.assertNotIn(taxonomy.DOCUMENTATION, view().labels[f"{GAAP}:bs.ass"])

	def test_the_fiscal_view_takes_the_labels_of_the_tax_administration(self):
		"""de-gaap-ci-2025-04-01-label-fiscal-de.xml prohibits labels of the commercial view and puts its own in their
		place; shell-fiscal.xsd reads it, shell.xsd does not (Leitfaden A.3: „bei den Bezeichnern (Standard- und
		Terse-Label) mehr Abweichungen“)."""
		corp = f"{GAAP}:bs.eqLiab.equity.subscribed.corp"
		self.assertEqual(
			(view().label(corp), view().label(corp, taxonomy.TERSE_LABEL)),
			("Gezeichnetes Kapital", "Gez. Kapital"),
		)
		self.assertEqual(
			(view(View.COMMERCIAL).label(corp), view(View.COMMERCIAL).label(corp, taxonomy.TERSE_LABEL)),
			("Gezeichnetes Kapital (Kapitalgesellschaft)", "Gez. Kapital (KapG)"),
		)
		self.assertEqual(view().label(f"{GAAP}:bs.ass.fixAss.tan"), "Sachanlagen (steuerlich)")


class ReferencesTest(TestCase):
	"""The properties the references give a concept (Leitfaden A.9): legal form, GuV format and the fiscal requirement
	from the reference-fiscal linkbases, the validity from the reference linkbases."""

	def test_reads_the_fiscal_requirement(self):
		self.assertEqual(view().concept(f"{GAAP}:bs.ass.fixAss.tan").fiscal.requirement, Requirement.MUSSFELD)
		self.assertEqual(view().concept(f"{GAAP}:bs.ass").fiscal.requirement, Requirement.SUMMENMUSSFELD)
		self.assertEqual(
			view().concept(f"{GAAP}:bs.ass.currAss.cashEquiv.bank").fiscal.requirement,
			Requirement.RECHNERISCH_NOTWENDIG,
		)
		self.assertIsNone(view().concept(f"{GAAP}:bs.eqLiab.liab.bank.upTo1year").fiscal.requirement)

	def test_names_the_requirements_that_must_be_reported(self):
		"""„Summenmussfelder sind stets zu übermitteln“ (Leitfaden A.9.3); „Mussfeld, Kontennachweis erwünscht“ is a
		Mussfeld that the taxonomy 6.9 no longer uses (A.10.2)."""
		self.assertEqual(
			{requirement for requirement in Requirement if requirement.mandatory},
			{Requirement.MUSSFELD, Requirement.MUSSFELD_KONTENNACHWEIS, Requirement.SUMMENMUSSFELD},
		)
		self.assertEqual(Requirement.MUSSFELD_KONTENNACHWEIS.value, "Mussfeld, Kontennachweis erwünscht")

	def test_reads_the_legal_forms_a_concept_is_for(self):
		"""„Bei den den Kapitalgesellschaften zuzuordnenden Rechtsform-Arten, dürfen nur Positionen mit der Auszeichnung
		„legalFormKSt“ = „true“ und Positionen, die keiner Rechtsform zugeordnet sind, übermittelt werden.“ (Leitfaden
		B.4.2)"""
		corp = view().concept(f"{GAAP}:bs.eqLiab.equity.subscribed.corp")
		partners = view().concept(f"{GAAP}:bs.eqLiab.equity.subscribed.limitedLiablePartners")
		self.assertEqual(corp.fiscal.legal_forms, frozenset({LegalForm.KST}))
		self.assertEqual((corp.applies_to(LegalForm.KST), corp.applies_to(LegalForm.PG)), (True, False))
		self.assertEqual(
			(partners.applies_to(LegalForm.KST), partners.applies_to(LegalForm.PG)), (False, True)
		)

	def test_a_false_legal_form_is_none(self):
		tax = view().concept(f"{GAAP}:is.netIncome.tax")
		self.assertEqual(tax.fiscal.legal_forms, frozenset({LegalForm.KST, LegalForm.PG}))
		self.assertFalse(tax.applies_to(LegalForm.EU))

	def test_a_concept_of_no_legal_form_is_for_all(self):
		dimension_key = view().concept(f"{GAAP}:dim_taxBal")
		self.assertEqual(dimension_key.fiscal.legal_forms, frozenset(LegalForm))
		self.assertTrue(
			view().concept(f"{GCD}:genInfo.report.id.reportStatus.head").applies_to(LegalForm.KST)
		)

	def test_reads_the_guv_format_a_concept_is_for(self):
		"""„Der Eintrag „neutral“ kennzeichnet für beide Varianten gültige Positionen.“ (Leitfaden A.9.1, B.14.3.1.15)"""
		material = view().concept(f"{GAAP}:is.netIncome.materialServices")
		cost_of_sales = view().concept(f"{GAAP}:is.netIncome.costOfSales")
		sales = view().concept(f"{GAAP}:is.netIncome.netSales")
		self.assertEqual(material.fiscal.operating_results, frozenset({"GKV"}))
		self.assertEqual(
			[
				(concept.suits(IncomeStatementFormat.GKV), concept.suits(IncomeStatementFormat.UKV))
				for concept in (material, cost_of_sales, sales)
			],
			[(True, False), (False, True), (True, True)],
		)
		self.assertTrue(
			view().concept(f"{GCD}:genInfo.report.id.reportStatus.head").suits(IncomeStatementFormat.UKV)
		)

	def test_reads_the_purposes_a_concept_is_not_permitted_for(self):
		"""Leitfaden A.9.3 and B.14.6: „notPermittedFor“ „steuerlich“ and „Einreichung an Finanzverwaltung“."""
		selfmade = view().concept(f"{GAAP}:bs.ass.fixAss.intan.selfmade")
		consolidation = view().concept(f"{GAAP}:bs.ass.consolidationDifference")
		self.assertEqual(selfmade.fiscal.not_permitted_for, frozenset({taxonomy.NOT_PERMITTED_FISCAL}))
		self.assertEqual(
			consolidation.fiscal.not_permitted_for, frozenset({taxonomy.NOT_PERMITTED_SUBMISSION})
		)
		self.assertEqual(taxonomy.NOT_PERMITTED_SUBMISSION, "Einreichung an Finanzverwaltung")
		self.assertEqual(taxonomy.NOT_PERMITTED_FISCAL, "steuerlich")
		self.assertFalse(selfmade.permitted_for(taxonomy.NOT_PERMITTED_FISCAL))
		self.assertTrue(selfmade.permitted_for(taxonomy.NOT_PERMITTED_SUBMISSION))
		self.assertFalse(consolidation.permitted_for(taxonomy.NOT_PERMITTED_SUBMISSION))

	def test_a_mussfeld_counts_from_its_fiscal_valid_since(self):
		"""Leitfaden B.14.4.2: „Die Position ist kein Mussfeld, wenn ... Der „Beginn des Wirtschaftsjahres" ... liegt vor
		dem Datum in fiscalValidSince.“"""
		cash = view().concept(f"{GAAP}:bs.ass.currAss.cashEquiv.cash")
		self.assertEqual(cash.fiscal.required_since, date(2027, 1, 1))
		self.assertFalse(cash.required_for(date(2026, 1, 1), date(2026, 12, 31)))
		self.assertTrue(cash.required_for(date(2027, 1, 1), date(2027, 12, 31)))
		self.assertTrue(
			view().concept(f"{GAAP}:bs.ass.fixAss.tan").required_for(date(2026, 1, 1), date(2026, 12, 31))
		)
		self.assertFalse(
			view()
			.concept(f"{GAAP}:bs.ass.currAss.cashEquiv.bank")
			.required_for(date(2026, 1, 1), date(2026, 12, 31))
		)

	def test_a_concept_may_be_reported_from_valid_since_to_valid_through(self):
		"""Leitfaden B.14.4.1: not reported „wenn der „Beginn des Wirtschaftsjahres“ ... vor dem unter „ValidSince“
		angegebenen Datum liegt“ or „wenn der „Bilanzstichtag“ ... nach dem unter „ValidThrough“ angegebenen Datum
		liegt“."""
		old = view().concept(f"{GAAP}:bs.ass.fixAss.tan.oldEquipment")
		crypto = view().concept(f"{GAAP}:bs.ass.currAss.cashEquiv.cryptoAssets")
		self.assertEqual((old.valid_since, old.valid_through), (None, date(2020, 12, 31)))
		self.assertTrue(old.valid_for(date(2020, 1, 1), date(2020, 12, 31)))
		self.assertFalse(old.valid_for(date(2020, 1, 1), date(2021, 1, 1)))
		self.assertFalse(crypto.valid_for(date(2026, 1, 1), date(2026, 12, 31)))
		self.assertTrue(crypto.valid_for(date(2027, 1, 1), date(2027, 12, 31)))
		self.assertTrue(view().concept(f"{GAAP}:bs.ass").valid_for(date(2026, 1, 1), date(2026, 12, 31)))

	def test_a_mussfeld_that_may_not_be_reported_is_none(self):
		"""Leitfaden B.14.4.1: „ist in diesem Fall auch eine eventuelle Mussfeldkennzeichnung nicht mehr gültig“."""
		old = view().concept(f"{GAAP}:bs.ass.fixAss.tan.oldEquipment")
		self.assertFalse(
			replace(old, fiscal=replace(old.fiscal, requirement=Requirement.MUSSFELD)).required_for(
				date(2026, 1, 1), date(2026, 12, 31)
			)
		)

	def test_reads_the_positions_only_for_special_balance_sheets(self):
		"""„onlyPermittedForSoBil_ErgBil“ (Leitfaden A.9.3)."""
		self.assertFalse(view().concept(f"{GAAP}:bs.ass").fiscal.special_balance_only)


class ReferencesFilesTest(CopiedPackage):
	def test_a_concept_has_one_fiscal_requirement(self):
		self.edit(
			f"{mini.GAAP}-reference-fiscal.xml",
			"<hgbref:fiscalRequirement>Summenmussfeld</hgbref:fiscalRequirement>",
			"<hgbref:fiscalRequirement>Summenmussfeld</hgbref:fiscalRequirement>"
			"<hgbref:fiscalRequirement>Mussfeld</hgbref:fiscalRequirement>",
		)
		with self.assertRaisesRegex(TaxonomyError, "fiscalRequirement"):
			load(self.package, mini.VERSION, View.FISCAL)

	def test_refuses_an_unknown_fiscal_requirement(self):
		self.edit(
			f"{mini.GAAP}-reference-fiscal.xml",
			"<hgbref:fiscalRequirement>Summenmussfeld</hgbref:fiscalRequirement>",
			"<hgbref:fiscalRequirement>Kannfeld</hgbref:fiscalRequirement>",
		)
		with self.assertRaisesRegex(TaxonomyError, "Kannfeld"):
			load(self.package, mini.VERSION, View.FISCAL)

	def test_refuses_a_date_that_is_none(self):
		self.edit(f"{mini.GAAP}-reference.xml", "2020-12-31", "31.12.2020")
		with self.assertRaisesRegex(TaxonomyError, "31.12.2020"):
			load(self.package, mini.VERSION, View.FISCAL)

	def test_takes_the_narrowest_validity_of_several_references(self):
		self.edit(
			f"{mini.GAAP}-reference.xml",
			"<hgbref:ValidThrough>2020-12-31</hgbref:ValidThrough>",
			"<hgbref:ValidThrough>2020-12-31</hgbref:ValidThrough><hgbref:ValidThrough>2019-12-31</hgbref:ValidThrough>"
			"<hgbref:ValidSince>2001-01-01</hgbref:ValidSince><hgbref:ValidSince>2002-01-01</hgbref:ValidSince>",
		)
		old = load(self.package, mini.VERSION, View.FISCAL).concept(f"{GAAP}:bs.ass.fixAss.tan.oldEquipment")
		self.assertEqual((old.valid_since, old.valid_through), (date(2002, 1, 1), date(2019, 12, 31)))


class NetworksFilesTest(CopiedPackage):
	def test_the_order_of_an_arc_is_a_number(self):
		self.edit(f"{mini.GAAP}-presentation-balanceSheet.xml", 'order="5"', 'order="fünf"')
		with self.assertRaisesRegex(TaxonomyError, "order fünf"):
			load(self.package, mini.VERSION, View.FISCAL)


class NetworksTest(TestCase):
	"""The presentation and calculation networks of each role (XBRL 2.1, Kap. 5.2.4 and 5.2.5), the order of the arcs
	and the weights of the calculation."""

	def test_presentation_orders_the_children_of_a_position(self):
		network = view().presentation[mini.BALANCE_SHEET]
		self.assertEqual(
			[arc.child for arc in network.children(f"{GAAP}:bs.ass")],
			[f"{GAAP}:bs.ass.fixAss", f"{GAAP}:bs.ass.currAss", f"{GAAP}:bs.ass.consolidationDifference"],
		)
		self.assertEqual(network.roots(), (f"{GAAP}:bs.ass", f"{GAAP}:bs.eqLiab"))

	def test_a_presentation_names_the_parent_of_a_position(self):
		network = view().presentation[mini.BALANCE_SHEET]
		self.assertEqual(
			network.parent(f"{GAAP}:bs.eqLiab.liab.bank.upTo1year"), f"{GAAP}:bs.eqLiab.liab.bank"
		)
		self.assertIsNone(network.parent(f"{GAAP}:bs.ass"))
		self.assertEqual(
			network.ancestors(f"{GAAP}:bs.ass.fixAss.intan.selfmade"),
			(f"{GAAP}:bs.ass.fixAss.intan", f"{GAAP}:bs.ass.fixAss", f"{GAAP}:bs.ass"),
		)

	def test_walks_a_network_depth_first_in_its_order(self):
		network = view().presentation[mini.INCOME_STATEMENT]
		self.assertEqual(
			list(network.walk()),
			[
				(f"{GAAP}:is.netIncome", 0),
				(f"{GAAP}:is.netIncome.netSales", 1),
				(f"{GAAP}:is.netIncome.materialServices", 1),
				(f"{GAAP}:is.netIncome.costOfSales", 1),
				(f"{GAAP}:is.netIncome.tax", 1),
			],
		)

	def test_calculation_weights_each_child(self):
		network = view().calculation[mini.INCOME_STATEMENT]
		self.assertEqual(
			[(arc.child, arc.weight) for arc in network.children(f"{GAAP}:is.netIncome")],
			[
				(f"{GAAP}:is.netIncome.netSales", Decimal(1)),
				(f"{GAAP}:is.netIncome.materialServices", Decimal(-1)),
				(f"{GAAP}:is.netIncome.costOfSales", Decimal(-1)),
				(f"{GAAP}:is.netIncome.tax", Decimal(-1)),
			],
		)

	def test_a_davon_position_has_no_calculation(self):
		"""„davon-Positionen“ are presented under their position but not calculated (BMF letter of 28 September 2011,
		Anlage)."""
		self.assertIn(f"{GAAP}:bs.eqLiab.liab.bank.upTo1year", view().presentation[mini.BALANCE_SHEET])
		self.assertNotIn(f"{GAAP}:bs.eqLiab.liab.bank.upTo1year", view().calculation[mini.BALANCE_SHEET])

	def test_the_descendants_of_a_position(self):
		network = view().calculation[mini.BALANCE_SHEET]
		self.assertEqual(
			network.descendants(f"{GAAP}:bs.ass.currAss"),
			(
				f"{GAAP}:bs.ass.currAss.cashEquiv",
				f"{GAAP}:bs.ass.currAss.cashEquiv.bank",
				f"{GAAP}:bs.ass.currAss.cashEquiv.cash",
				f"{GAAP}:bs.ass.currAss.cashEquiv.cryptoAssets",
			),
		)

	def test_the_views_differ_in_the_networks_of_their_entry_points(self):
		self.assertIn(mini.INCOME_STATEMENT, view(View.COMMERCIAL).presentation)
		self.assertNotIn(mini.INCOME_STATEMENT_MICROBILG, view(View.COMMERCIAL).presentation)
		self.assertIn(mini.INCOME_STATEMENT_MICROBILG, view(View.COMMERCIAL_MICROBILG).presentation)
		self.assertNotIn(mini.INCOME_STATEMENT, view(View.COMMERCIAL_MICROBILG).presentation)

	def test_the_order_of_an_arc_is_a_decimal(self):
		arc = view().presentation[mini.BALANCE_SHEET].children(f"{GAAP}:bs.ass")[0]
		self.assertEqual(arc.order, Decimal(1))

	def test_a_concept_under_two_parents_has_none_to_name(self):
		network = Network(
			mini.BALANCE_SHEET,
			(
				Arc(f"{GAAP}:bs.ass", f"{GAAP}:bs.ass.fixAss"),
				Arc(f"{GAAP}:bs.eqLiab", f"{GAAP}:bs.ass.fixAss"),
			),
		)
		self.assertEqual(len(network.parents(f"{GAAP}:bs.ass.fixAss")), 2)
		with self.assertRaisesRegex(TaxonomyError, "has the parents de-gaap-ci:bs.ass, de-gaap-ci:bs.eqLiab"):
			network.parent(f"{GAAP}:bs.ass.fixAss")
		self.assertEqual(
			list(network.walk()),
			[(f"{GAAP}:bs.ass", 0), (f"{GAAP}:bs.ass.fixAss", 1), (f"{GAAP}:bs.eqLiab", 0)],
		)

	def test_a_concept_is_transmittable_in_a_presentation_of_its_view(self):
		"""„Es dürfen nur solche Positionen übermittelt werden, die in dem Presentation Network erfasst sind, welches im
		Zuge der „taxonomy discovery“ ... des jeweiligen Einstiegsschemas aufgebaut wird.“ (Leitfaden B.11)"""
		self.assertTrue(view().presented(f"{GAAP}:bs.ass"))
		self.assertTrue(view().presented(f"{GCD}:genInfo.company.id.name"))
		self.assertFalse(view().presented(f"{GAAP}:bs.ass.groupOnly"))
		self.assertFalse(view(View.COMMERCIAL_MICROBILG).presented(f"{GAAP}:is.netIncome.netSales"))


class DefinitionTest(TestCase):
	def test_keeps_the_arcs_of_the_definition_linkbases_by_role(self):
		arcs = view().definition[mini.FIXED_ASSETS_TABLE]
		self.assertIn(
			DefinitionArc(
				taxonomy.ALL,
				f"{GAAP}:table.nt.ass.gross",
				f"{GAAP}:cube_.nt.ass.gross",
				Decimal(1),
				context_element="scenario",
			),
			arcs,
		)
		self.assertIn(
			DefinitionArc(
				taxonomy.DOMAIN_MEMBER, f"{GAAP}:bs.ass.fixAss", f"{GAAP}:bs.ass.fixAss.tan", Decimal(4)
			),
			arcs,
		)


class TablesTest(TestCase):
	"""The Tabellenbereiche: a hypercube with its dimensions and primary items, as the definition linkbases define it
	(Leitfaden A.14; XBRL Dimensions 1.0). „Alle Dimensionen der HGB-Taxonomie sind Szenario-Dimensionen“ (A.14.2.1)."""

	def setUp(self):
		(self.table,) = view().tables
		self.dimensions = {dimension.name: dimension for dimension in self.table.dimensions}

	def test_the_anlagenspiegel_is_a_table_of_its_role(self):
		self.assertEqual(self.table.role, mini.FIXED_ASSETS_TABLE)
		self.assertEqual(self.table.hypercube, f"{GAAP}:cube_.nt.ass.gross")
		self.assertEqual(self.table.primary, f"{GAAP}:table.nt.ass.gross")
		self.assertEqual(self.table.context_element, "scenario")
		self.assertIs(view().table(mini.FIXED_ASSETS_TABLE), self.table)

	def test_names_its_dimensions_in_their_order(self):
		self.assertEqual(
			[dimension.name for dimension in self.table.dimensions],
			[f"{GAAP}:dim_taxTrans", f"{GAAP}:dim_changes.nt.ass.gross"],
		)

	def test_a_dimension_takes_its_domain_and_the_members_below(self):
		"""„Positionen des Anlagevermögens“ [dim_changes.nt.ass.gross] takes the positions of the Anlagevermögen, the
		„steuerliche Überleitung“ [dim_taxTrans] Steuerbilanzwert, Handelsbilanzwert and Überleitungswert (A.14.1,
		B.14.12.1)."""
		positions = self.dimensions[f"{GAAP}:dim_changes.nt.ass.gross"]
		self.assertEqual(positions.domain, f"{GAAP}:bs.ass.fixAss")
		self.assertEqual(
			positions.members,
			(
				f"{GAAP}:bs.ass.fixAss",
				f"{GAAP}:bs.ass.fixAss.intan",
				f"{GAAP}:bs.ass.fixAss.intan.concessionBrands",
				f"{GAAP}:bs.ass.fixAss.intan.selfmade",
				f"{GAAP}:bs.ass.fixAss.tan",
			),
		)
		self.assertEqual(
			self.dimensions[f"{GAAP}:dim_taxTrans"].members,
			(f"{GAAP}:dim_taxBal", f"{GAAP}:dim_comBal", f"{GAAP}:dim_diffComToTaxBal"),
		)

	def test_a_member_knows_the_member_it_belongs_to(self):
		positions = self.dimensions[f"{GAAP}:dim_changes.nt.ass.gross"]
		self.assertEqual(
			positions.parent(f"{GAAP}:bs.ass.fixAss.intan.selfmade"), f"{GAAP}:bs.ass.fixAss.intan"
		)
		self.assertIsNone(positions.parent(f"{GAAP}:bs.ass.fixAss"))

	def test_names_its_primary_items(self):
		self.assertEqual(
			self.table.primary_items,
			(
				f"{GAAP}:table.nt.ass.gross",
				f"{GAAP}:piTitle.nt.ass.gross",
				f"{GAAP}:all",
				f"{GAAP}:gross",
				f"{GAAP}:grossCost.beginning",
				f"{GAAP}:gross.addition",
				f"{GAAP}:accDepr",
				f"{GAAP}:accDepr.DeprPeriod",
				f"{GAAP}:all_Prev_period",
			),
		)
		self.assertEqual(self.table.primary_parent(f"{GAAP}:grossCost.beginning"), f"{GAAP}:gross")

	def test_finds_the_tables_of_a_primary_item(self):
		self.assertEqual(view().tables_of(f"{GAAP}:gross"), (self.table,))
		self.assertEqual(view().tables_of(f"{GAAP}:bs.ass"), ())

	def test_an_unusable_member_is_left_out(self):
		"""„xbrldt:usable="false"“ excludes a member from the valid values of its dimension (XBRL Dimensions 1.0,
		Kap. 2.5.3.1.1)."""
		arcs = tuple(
			replace(arc, usable=False)
			if arc.arcrole == taxonomy.DOMAIN_MEMBER and arc.target == f"{GAAP}:bs.ass.fixAss.intan"
			else arc
			for arc in view().definition[mini.FIXED_ASSETS_TABLE]
		)
		loaded = replace(view(), definition={mini.FIXED_ASSETS_TABLE: arcs})
		positions = next(
			d for d in loaded.tables[0].dimensions if d.name == f"{GAAP}:dim_changes.nt.ass.gross"
		)
		self.assertNotIn(f"{GAAP}:bs.ass.fixAss.intan", positions.members)
		self.assertIn(f"{GAAP}:bs.ass.fixAss.intan.selfmade", positions.members)

	def test_an_unknown_table_is_named(self):
		with self.assertRaisesRegex(TaxonomyError, "notesTableOther"):
			view().table(f"{mini.ROLE}notesTableOther")


class ParentsTest(TestCase):
	"""What each position adds up to, by name without the prefix of the GAAP module: the hierarchy the balance sheet and
	the GuV of the Jahresabschluss sum up along (steuerbote/hgb/statement.py)."""

	def test_names_the_parent_of_each_position_in_the_calculation_of_the_roles(self):
		parents = view(View.COMMERCIAL).parents((mini.BALANCE_SHEET, mini.INCOME_STATEMENT))
		self.assertEqual(parents["bs.ass.currAss.cashEquiv.bank"], "bs.ass.currAss.cashEquiv")
		self.assertEqual(parents["bs.ass.fixAss"], "bs.ass")
		self.assertEqual(parents["is.netIncome.tax"], "is.netIncome")
		self.assertNotIn("bs.ass", parents)

	def test_a_davon_position_adds_up_to_nothing(self):
		self.assertNotIn("bs.eqLiab.liab.bank.upTo1year", view().parents((mini.BALANCE_SHEET,)))

	def test_a_role_without_a_calculation_is_named(self):
		with self.assertRaisesRegex(TaxonomyError, "detailedInformation"):
			view().parents((mini.DETAILED_INFORMATION,))

	def test_a_position_with_two_parents_has_none(self):
		calculation = dict(view().calculation)
		calculation[mini.INCOME_STATEMENT] = Network(
			mini.INCOME_STATEMENT, (Arc(f"{GAAP}:is.netIncome", f"{GAAP}:bs.ass.fixAss"),)
		)
		with self.assertRaisesRegex(TaxonomyError, "bs.ass.fixAss adds up to bs.ass and to is.netIncome"):
			replace(view(), calculation=calculation).parents((mini.BALANCE_SHEET, mini.INCOME_STATEMENT))

	def test_names_a_position_of_another_module_with_its_prefix(self):
		calculation = {
			mini.BALANCE_SHEET: Network(
				mini.BALANCE_SHEET, (Arc(f"{GCD}:genInfo", f"{GCD}:genInfo.company.id.name"),)
			)
		}
		parents = replace(view(), calculation=calculation).parents((mini.BALANCE_SHEET,))
		self.assertEqual(parents, {f"{GCD}:genInfo.company.id.name": f"{GCD}:genInfo"})


class RolesTest(TestCase):
	def test_names_the_roles_of_the_components(self):
		"""The presentation link roles of the components of the Kerntaxonomie (Leitfaden B.14.10)."""
		self.assertEqual(taxonomy.BALANCE_SHEET, mini.BALANCE_SHEET)
		self.assertEqual(taxonomy.INCOME_STATEMENT, mini.INCOME_STATEMENT)
		self.assertEqual(taxonomy.INCOME_STATEMENT_MICROBILG, mini.INCOME_STATEMENT_MICROBILG)
		self.assertEqual(taxonomy.TRANSFERS_TAX_ASSETS, mini.TRANSFERS_TAX_ASSETS)
		self.assertEqual(taxonomy.NOTES, mini.NOTES)
		self.assertEqual(taxonomy.DETAILED_INFORMATION, mini.DETAILED_INFORMATION)
		self.assertEqual(taxonomy.TRANSFERS_COMMERCIAL_CODE_TO_TAX, mini.TRANSFERS_TO_TAX)
		self.assertEqual(taxonomy.FIXED_ASSETS_GROSS, mini.FIXED_ASSETS_TABLE)
		self.assertEqual(taxonomy.APPROPRIATION_PROFITS, f"{mini.ROLE}appropriationProfits")
		self.assertEqual(taxonomy.GCD, mini.GCD_ROLE)
