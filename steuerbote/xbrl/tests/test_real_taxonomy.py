"""The loader against the HGB-Taxonomie 6.9 of esteuer.de and the examples of the ERiC documentation 44.3.6.0.

The numbers of Mussfelder are those of a GmbH with the Gesamtkostenverfahren and the fiscal year 2026, counted as the
Technischer Leitfaden 6.9 decides them: admissible are the positions of a presentation network that are no abstract
ones, valid in the fiscal year (B.14.4.1), for a Körperschaft (B.4.2), for the GKV (B.14.3.1.15) and permitted for a
Steuerbilanz and for the Finanzverwaltung (A.9.3, B.14.6); of those the fiscalRequirement counts while
fiscalValidSince and fiscalValidThrough leave it (B.14.4.2).
"""

import hashlib
from collections import Counter
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from unittest import TestCase

from lxml import etree

from steuerbote.elster.tests.eric_schema import documentation
from steuerbote.hgb import notes, schemes
from steuerbote.hgb.size import SizeClass
from steuerbote.xbrl import taxonomy
from steuerbote.xbrl.checks import Code
from steuerbote.xbrl.profiles import FISCAL
from steuerbote.xbrl.taxonomy import IncomeStatementFormat, LegalForm, Requirement, View
from steuerbote.xbrl.tests import instances, real

BEGIN = date(2026, 1, 1)
END = date(2026, 12, 31)
XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"
LINK = "{http://www.xbrl.org/2003/linkbase}"
XLINK = "{http://www.w3.org/1999/xlink}"


def counted(names: Iterable[str]) -> tuple[int, Counter]:
	"""The admissible positions among the names, and how many of them carry each fiscal requirement."""
	loaded = real.view()
	admissible = [
		concept
		for name in dict.fromkeys(names)
		if not (concept := loaded.concept(name)).abstract
		and concept.valid_for(BEGIN, END)
		and concept.applies_to(LegalForm.KST)
		and concept.suits(IncomeStatementFormat.GKV)
		and concept.permitted_for(taxonomy.NOT_PERMITTED_SUBMISSION)
		and concept.permitted_for(taxonomy.NOT_PERMITTED_FISCAL)
	]
	requirements = Counter(
		concept.fiscal.requirement
		for concept in admissible
		if concept.required_for(BEGIN, END) or concept.fiscal.requirement is Requirement.RECHNERISCH_NOTWENDIG
	)
	return len(admissible), requirements


class PackageTest(TestCase):
	def test_the_archive_is_the_one_esteuer_publishes(self):
		self.assertEqual(hashlib.sha256(real.archive().read_bytes()).hexdigest(), real.VERSION.archive_sha256)

	def test_installs_with_every_view_unchanged(self):
		self.assertEqual(taxonomy.verify(real.installation()), ())
		self.assertEqual(len(real.installation().files), 279)

	def test_each_view_starts_from_its_entry_points(self):
		for view in View:
			with self.subTest(view=view):
				self.assertEqual(real.view(view).entry_points, view.entry_points(real.VERSION))

	def test_the_gaap_module_has_its_tuples(self):
		"""„GAAP 6.9 in numbers: 3,089 concepts and 41 tuples“ (research note on the E-Bilanz, 2.2)."""
		kinds = Counter(
			concept.kind for concept in real.view().concepts.values() if concept.prefix == "de-gaap-ci"
		)
		self.assertEqual(kinds[taxonomy.Kind.TUPLE], 41)


class MussfelderTest(TestCase):
	"""The Mussfelder of a small GmbH, as the research note on the E-Bilanz counts them (2.5) and the contract binds
	them (3.2)."""

	def test_the_bilanz(self):
		admissible, requirements = counted(
			name for name, _ in real.view().presentation[taxonomy.BALANCE_SHEET].walk()
		)
		self.assertEqual(admissible, 727)
		self.assertEqual(
			(
				requirements[Requirement.MUSSFELD],
				requirements[Requirement.SUMMENMUSSFELD],
				requirements[Requirement.RECHNERISCH_NOTWENDIG],
			),
			(82, 49, 153),
		)

	def test_the_guv_of_the_gesamtkostenverfahren(self):
		admissible, requirements = counted(
			name for name, _ in real.view().presentation[taxonomy.INCOME_STATEMENT].walk()
		)
		self.assertEqual(admissible, 681)
		self.assertEqual(
			(
				requirements[Requirement.MUSSFELD],
				requirements[Requirement.SUMMENMUSSFELD],
				requirements[Requirement.RECHNERISCH_NOTWENDIG],
			),
			(155, 59, 129),
		)

	def test_the_betriebsvermoegensvergleich(self):
		admissible, requirements = counted(
			name for name, _ in real.view().presentation[taxonomy.TRANSFERS_TAX_ASSETS].walk()
		)
		self.assertEqual(admissible, 7)
		self.assertEqual(
			(requirements[Requirement.MUSSFELD], requirements[Requirement.SUMMENMUSSFELD]), (5, 2)
		)

	def test_the_anlagenspiegel_per_row_and_its_rows(self):
		table = real.view().table(taxonomy.FIXED_ASSETS_GROSS)
		admissible, requirements = counted(table.primary_items)
		self.assertEqual(admissible, 29)
		self.assertEqual(
			(
				requirements[Requirement.MUSSFELD],
				requirements[Requirement.SUMMENMUSSFELD],
				requirements[Requirement.RECHNERISCH_NOTWENDIG],
			),
			(13, 4, 6),
		)
		(rows,) = (
			dimension for dimension in table.dimensions if dimension.domain == "de-gaap-ci:bs.ass.fixAss"
		)
		admissible, requirements = counted(rows.members)
		self.assertEqual(admissible, 135)
		self.assertEqual(
			(
				requirements[Requirement.MUSSFELD],
				requirements[Requirement.SUMMENMUSSFELD],
				requirements[Requirement.RECHNERISCH_NOTWENDIG],
			),
			(31, 21, 38),
		)

	def test_the_gcd(self):
		_, requirements = counted(name for name, _ in real.view().presentation[taxonomy.GCD].walk())
		self.assertEqual(requirements[Requirement.MUSSFELD], 52)


class TablesTest(TestCase):
	def test_the_anlagenspiegel_has_its_dimensions(self):
		"""The Anlagenspiegel „Bruttomethode“ with the „Dimensionen: Wertentwicklung, Gliederung der Anlagen, steuerliche
		Überleitung“ (Leitfaden A.14.1)."""
		table = real.view().table(taxonomy.FIXED_ASSETS_GROSS)
		self.assertEqual(table.hypercube, "de-gaap-ci:cube_.nt.ass.gross")
		self.assertEqual(table.context_element, "scenario")
		self.assertEqual(
			{dimension.name: dimension.members[:3] for dimension in table.dimensions},
			{
				"de-gaap-ci:dim_taxTrans": (
					"de-gaap-ci:dim_taxBal",
					"de-gaap-ci:dim_comBal",
					"de-gaap-ci:dim_diffComToTaxBal",
				),
				"de-gaap-ci:dim_changes.nt.ass.gross": (
					"de-gaap-ci:bs.ass.fixAss",
					"de-gaap-ci:bs.ass.fixAss.intan",
					"de-gaap-ci:bs.ass.fixAss.intan.selfmade",
				),
			},
		)
		self.assertEqual(table.primary_parent("de-gaap-ci:grossCost.beginning"), "de-gaap-ci:gross")

	def test_no_primary_item_belongs_to_two_tables(self):
		items = Counter(item for table in real.view().tables for item in table.primary_items)
		self.assertEqual([item for item, count in items.items() if count > 1], [])


class LabelsAndParentsTest(TestCase):
	def test_the_fiscal_view_has_the_labels_of_the_tax_administration(self):
		name = "bs.eqLiab.liab.particip.otherShareholder"
		self.assertIn("davon gegenüber anderen Gesellschaftern", real.view(View.COMMERCIAL).label(name))
		self.assertNotIn("davon", real.view().label(name))

	def test_every_position_of_bilanz_and_guv_adds_up_to_one_position(self):
		"""The hierarchy the statement of the Jahresabschluss sums up along (steuerbote/hgb/statement.py)."""
		for view, income in (
			(View.COMMERCIAL, taxonomy.INCOME_STATEMENT),
			(View.COMMERCIAL_MICROBILG, taxonomy.INCOME_STATEMENT_MICROBILG),
		):
			with self.subTest(view=view):
				parents = real.view(view).parents((taxonomy.BALANCE_SHEET, income))
				self.assertEqual(parents["bs.ass.currAss.cashEquiv.bank"], "bs.ass.currAss.cashEquiv")
				self.assertNotIn("bs.ass", parents)


def examples() -> Path:
	return documentation() / "Datenarten" / "ElsterBilanz" / "Bilanz" / "Beispiele" / "Taxonomie_6_9"


class EricExamplesTest(TestCase):
	"""The examples of Datenarten/ElsterBilanz/Bilanz/Beispiele/Taxonomie_6_9 that reference the fiscal entry point
	report concepts of the fiscal view only, each in one of its presentation networks (Leitfaden B.11), and members of
	its dimensions; the domain of a typed dimension inside a typedMember is no concept."""

	VALID = (
		"SteuerbilanzAutoverkaeufer_PersG.xml",
		"SteuerbilanzAutoverkaeufer-Eroeffnung_PersG.xml",
		"HandelsbilanzGastronom_PersG.xml",
		"Anlagenspiegel_brutto_mitUeberleitung.xml",
		"Anlagenspiegel_brutto_ohneUeberleitung.xml",
	)
	"""The examples on the Kerntaxonomie the documentation calls valid, „Beispiel für ein gültiges, auf der
	Kerntaxonomie basierendes ... E-Bilanz-Dokument“ (ERiC E-Bilanz-Dokumentation für HGB-Taxonomie 6.9, Kap. 5), but
	SteuerbilanzKoerperschaftMitGeschaeftsbetrieb.xml, whose Kontensalden are given per Betrieb gewerblicher Art in a
	typed dimension that the facts of Steuerbote do not model."""

	def test_the_valid_examples_pass_the_checks_of_the_e_bilanz(self):
		"""Read into the facts of Steuerbote and written again, none of them has a finding that blocks: the checks are
		no stricter than ERiC where its examples show what it takes."""
		for name in self.VALID:
			with self.subTest(example=name):
				report = instances.read(examples() / name, real.view())
				findings = FISCAL.check(report, real.view())
				self.assertEqual([finding for finding in findings if finding.blocking], [])

	def test_the_example_with_a_structural_error_fails_them(self):
		"""SteuerbilanzAutoverkaeufer-StrukturellerFehler.xml, „Beispiel für einen ... ungültigen Datensatz ..., dessen
		Zurückweisung aufgrund eines „strukturellen Fehlers“ erfolgt“ (Kap. 5), reports the Ergebnisverwendung without
		announcing it (Leitfaden B.9.2)."""
		report = instances.read(
			examples() / "SteuerbilanzAutoverkaeufer-StrukturellerFehler.xml", real.view()
		)
		findings = FISCAL.check(report, real.view())
		self.assertEqual(
			[(finding.code, finding.concept) for finding in findings if finding.blocking],
			[(Code.COMPONENT, "de-gaap-ci:incomeUse.gainLoss")],
		)

	def test_report_concepts_of_the_fiscal_view(self):
		loaded = real.view()
		prefixes = {namespace: prefix for prefix, namespace in loaded.namespaces.items()}
		checked = []
		for path in sorted(examples().glob("*.xml")):
			instance = etree.parse(str(path)).getroot().find(f".//{XBRLI}xbrl")
			references = [element.get(f"{XLINK}href", "") for element in instance.iter(f"{LINK}schemaRef")]
			if not any(reference.endswith(real.VERSION.fiscal_shell) for reference in references):
				continue
			checked.append(path.name)
			names = {
				f"{prefixes[qname.namespace]}:{qname.localname}"
				for element in instance.iter()
				if isinstance(element.tag, str) and (qname := etree.QName(element)).namespace in prefixes
			} - {"de-gaap-ci:dim_keyType"}
			members = {member.text for member in instance.iter(f"{XBRLDI}explicitMember")}
			with self.subTest(example=path.name):
				self.assertEqual(sorted(name for name in names if not loaded.has(name)), [])
				self.assertEqual(sorted(name for name in names if not loaded.presented(name)), [])
				self.assertEqual(sorted(member for member in members if not loaded.has(member)), [])
		self.assertIn("Anlagenspiegel_brutto_ohneUeberleitung.xml", checked)
		self.assertEqual(len(checked), 8)


class JahresabschlussTest(TestCase):
	"""What steuerbote/hgb names of the taxonomy 6.9 for the Jahresabschluss and its Offenlegung: the positions and
	Vermerke of the balance sheet of § 266 HGB and of the income statement of § 275 HGB by both methods, the Angaben of
	the catalogue of Kleinst and klein, the Haftungsverhältnisse of § 251 HGB and the data of § 264 Abs. 1a HGB."""

	@staticmethod
	def concepts() -> set[str]:
		balance_sheet = schemes.balance_sheet_scheme(2026)
		positions = [
			*balance_sheet.positions(),
			*(
				position
				for method in schemes.Method
				for position in schemes.income_statement_scheme(2026, method).positions()
			),
		]
		names = {position.concept for position in positions}
		names |= {name for position in positions for name in position.terms}
		for position in positions:
			for vermerk in position.vermerke:
				names |= {vermerk.concept, *vermerk.members}
		names |= {
			entry.item.concept
			for size_class in (SizeClass.KLEINST, SizeClass.KLEIN)
			for entry in notes.catalogue(size_class)
			if entry.item.concept
		}
		for contingency in notes.Contingency:
			names |= {contingency.concept, contingency.pensions_concept, contingency.group_concept}
		return names | set(notes.RegisterData.concepts().values())

	def test_each_concept_is_a_presented_concept_of_the_views_of_the_offenlegung(self):
		"""„Every concept needs a label and a presentation position“ for the register (research note on the
		Offenlegung, 3.1, after the „Arbeitshilfe für die Einreichung von Jahresabschlüssen/Finanzberichten im
		XBRL-Format“, Stand September 2025): each concept steuerbote/hgb names is presented in both commercial views and
		in the fiscal one, which takes the same balances."""
		concepts = self.concepts()
		self.assertGreater(len(concepts), 150)
		for view in View:
			with self.subTest(view=view):
				loaded = real.view(view)
				self.assertEqual(sorted(name for name in concepts if not loaded.presented(name)), [])

	def test_the_schemes_follow_the_calculation_linkbase(self):
		"""Each position of the schemes adds up, through parents(), to the position the scheme puts it under, as
		steuerbote/hgb/statement.py sums the balances along them."""
		parents = real.view(View.COMMERCIAL).parents((taxonomy.BALANCE_SHEET, taxonomy.INCOME_STATEMENT))
		for scheme in (
			schemes.balance_sheet_scheme(2026),
			*(schemes.income_statement_scheme(2026, method) for method in schemes.Method),
		):
			with self.subTest(scheme=str(scheme)):
				for position in scheme.positions():
					above = scheme.parent(position.concept)
					ancestors = []
					current = position.concept
					while current in parents:
						current = parents[current]
						ancestors.append(current)
					if above is not None:
						self.assertIn(above.concept, ancestors, position.concept)
