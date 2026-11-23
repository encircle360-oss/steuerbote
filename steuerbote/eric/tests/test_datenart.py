"""The Datenarten of steuerbote.eric.datenart, also against the ERiC documentation 44.3.6.0: its examples, its
schemas, its Datenartversionmatrix and the Jahresdokumentation ZMDO, read as steuerbote/elster/tests/eric_schema.py
finds them."""

from pathlib import Path
from types import MappingProxyType
from unittest import TestCase

from lxml import etree

from steuerbote.elster.tests import eric_schema
from steuerbote.eric.datenart import (
	FREIZEICHNUNGSDOKUMENT,
	UEBERTRAGUNGSPROTOKOLL,
	ZMDO,
	Datenart,
	gewst,
	kst,
	of_version,
	ust,
	ustva,
)
from steuerbote.ustva import years

ELSTER = "{http://www.elster.de/elsterxml/schema/v11}"
XS = "{http://www.w3.org/2001/XMLSchema}"
DOC = Path(__file__).resolve().parents[3] / "docs" / "zm.md"


def doc_table(heading: str) -> list[list[str]]:
	"""The cells of each row of the table under the heading of docs/zm.md, without its head."""
	text = DOC.read_text(encoding="utf-8")
	section = text[text.index(f"\n{heading}\n") + len(heading) + 2 :]
	section = section[: section.find("\n#")]
	lines = [line for line in section.splitlines() if line.startswith("|")]
	return [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines[2:]]


class DescriptionTest(TestCase):
	def test_the_ustva_is_an_elster_anmeldung_of_its_year_for_the_finanzamt(self):
		self.assertEqual(
			ustva(2026),
			Datenart(
				name="UStVA",
				version="UStVA_2026",
				verfahren="ElsterAnmeldung",
				vorgang="send-Auth",
				recipient_id="F",
				recipient=None,
				plugin="checkUStVA_2026",
				schema="Datenarten/ElsterAnmeldung/UStVA/Schema/2026/UStVA-2026.xsd",
				namespace="http://finkonsens.de/elster/elsteranmeldung/ustva/v2026",
				root="Anmeldungssteuern",
				root_version="2026",
				year=2026,
			),
		)

	def test_zmdo_is_an_elster_extern_without_a_year_for_bf(self):
		"""ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 8-28: Verfahren ElsterExtern, Datenart ZMDO, send-Auth „Ja“,
		send-NoSig „Nein“, <Empfaenger> with the attribute id "L"; Tabelle 2-13: AZ „Unabhängig“."""
		self.assertEqual(
			ZMDO,
			Datenart(
				name="ZMDO",
				version="ZMDO",
				verfahren="ElsterExtern",
				vorgang="send-Auth",
				recipient_id="L",
				recipient="BF",
				plugin="checkZMDO",
				schema="Datenarten/ElsterExtern/ZMDO/Schema/5/zm_000005.xsd",
				namespace="http://www.elster.de/elsterxml/schema/v11",
				root="zm",
				root_version="000005",
				year=None,
			),
		)

	def test_names_the_plugin_library_under_linux(self):
		"""lib<eric_plugin_bibliothek>.so (Entwicklerhandbuch, Kap. 3.1.6.1)."""
		self.assertEqual(
			(ustva(2027).plugin_library, ZMDO.plugin_library), ("libcheckUStVA_2027.so", "libcheckZMDO.so")
		)

	def test_the_ustva_takes_its_names_from_the_year_table(self):
		for year in (*years.YEARS, 2027):
			with self.subTest(year=year):
				self.assertEqual(
					(ustva(year).version, ustva(year).plugin, ustva(year).plugin_library),
					(years.datenart_version(year), years.plugin(year), years.plugin_library(year)),
				)

	def test_finds_the_datenart_of_a_datenart_version(self):
		self.assertEqual(of_version("UStVA_2026"), ustva(2026))
		self.assertEqual(of_version("UStVA_2027"), ustva(2027))
		self.assertEqual(of_version("ZMDO"), ZMDO)

	def test_refuses_other_datenart_versions(self):
		for version in (
			"ESt_2026",
			"UStVA_26",
			"UStVA_2026 ",
			"ustva_2026",
			"UStVA-2026",
			"",
			"zmdo",
			"ZMDO_5",
		):
			with self.subTest(version=version), self.assertRaises(ValueError):
				of_version(version)


class ErklaerungTest(TestCase):
	"""The Umsatzsteuererklärung, the Körperschaftsteuererklärung and the Gewerbesteuererklärung: Datenarten of the
	Verfahren ElsterErklaerung for the Finanzamt, send-Auth only from VZ 2017 (ERiC-Entwicklerhandbuch 44.3.6.0,
	Tabellen 7-9, 7-13 and 7-15), each with its Unterfallart (Tabelle 2-12) and a Freizeichnungsdokument after an
	authenticated send (Kap. 5.1.4.3)."""

	def test_the_ust_is_an_elster_erklaerung_of_its_year_for_the_finanzamt(self):
		self.assertEqual(
			ust(2026),
			Datenart(
				name="USt",
				version="USt_2026",
				verfahren="ElsterErklaerung",
				vorgang="send-Auth",
				recipient_id="F",
				recipient=None,
				plugin="checkUSt_2026",
				schema="Datenarten/ElsterErklaerung/USt/Schema/2026/E50-2026.xsd",
				namespace="http://finkonsens.de/elster/elstererklaerung/ust/e50/v2026",
				root="E50",
				root_version="2026",
				year=2026,
				printout="Freizeichnungsdokument",
				preview_on_check=True,
				nutzdaten_datenlieferant=False,
				unterfallart="50",
				taxonomy=None,
			),
		)

	def test_the_kst_is_the_datenart_version_of_unterfallart_30(self):
		"""Datenartversionmatrix.ods: KSt_30_<Jahr> with checkKSt_<Jahr>, „UFA = 30“."""
		self.assertEqual(
			kst(2026),
			Datenart(
				name="KSt",
				version="KSt_30_2026",
				verfahren="ElsterErklaerung",
				vorgang="send-Auth",
				recipient_id="F",
				recipient=None,
				plugin="checkKSt_2026",
				schema="Datenarten/ElsterErklaerung/KSt/Schema/2026/E30-2026.xsd",
				namespace="http://finkonsens.de/elster/elstererklaerung/kst/e30/v2026",
				root="E30",
				root_version="2026",
				year=2026,
				printout="Freizeichnungsdokument",
				preview_on_check=True,
				nutzdaten_datenlieferant=False,
				unterfallart="30",
				taxonomy=None,
			),
		)

	def test_the_gewst_is_an_elster_erklaerung_of_its_year_for_the_finanzamt(self):
		self.assertEqual(
			gewst(2026),
			Datenart(
				name="GewSt",
				version="GewSt_2026",
				verfahren="ElsterErklaerung",
				vorgang="send-Auth",
				recipient_id="F",
				recipient=None,
				plugin="checkGewSt_2026",
				schema="Datenarten/ElsterErklaerung/GewSt/Schema/2026/E20-2026.xsd",
				namespace="http://finkonsens.de/elster/elstererklaerung/gewst/e20/v2026",
				root="E20",
				root_version="2026",
				year=2026,
				printout="Freizeichnungsdokument",
				preview_on_check=True,
				nutzdaten_datenlieferant=False,
				unterfallart="20",
				taxonomy=None,
			),
		)

	def test_the_ustva_and_the_zm_keep_their_uebertragungsprotokoll_and_their_preview(self):
		"""Kap. 5.1.4.4: the other Datenarten get an Übertragungsprotokoll; neither has a Vorsatz or a taxonomy."""
		for kind in (ustva(2026), ZMDO):
			with self.subTest(datenart=kind.version):
				self.assertEqual(
					(
						kind.printout,
						kind.preview_on_check,
						kind.nutzdaten_datenlieferant,
						kind.unterfallart,
						kind.taxonomy,
					),
					(UEBERTRAGUNGSPROTOKOLL, True, False, None, None),
				)
		self.assertEqual(
			(UEBERTRAGUNGSPROTOKOLL, FREIZEICHNUNGSDOKUMENT),
			("Übertragungsprotokoll", "Freizeichnungsdokument"),
		)

	def test_names_the_plugin_libraries_under_linux(self):
		self.assertEqual(
			[kind.plugin_library for kind in (ust(2026), kst(2025), gewst(2025))],
			["libcheckUSt_2026.so", "libcheckKSt_2025.so", "libcheckGewSt_2025.so"],
		)

	def test_finds_the_erklaerung_of_a_datenart_version(self):
		self.assertEqual(of_version("USt_2026"), ust(2026))
		self.assertEqual(of_version("KSt_30_2025"), kst(2025))
		self.assertEqual(of_version("GewSt_2027"), gewst(2027))

	def test_refuses_other_datenart_versions_of_the_erklaerungen(self):
		for version in (
			"KSt_2026",
			"KSt_32_2016",
			"KSt_33_2016",
			"KStZ_2025",
			"GewStZ_2025",
			"USt_26",
			"UST_2026",
			"USt-2026",
			"GewSt_2026 ",
		):
			with self.subTest(version=version), self.assertRaises(ValueError):
				of_version(version)


class ErklaerungDocumentationTest(TestCase):
	"""The Datenarten of the Erklärungen against the ERiC documentation 44.3.6.0, which has KSt and GewSt up to 2025."""

	KINDS = (ust(2026), kst(2025), gewst(2025))
	EXAMPLES = MappingProxyType({"USt": "USt_2026.xml", "KSt": "kst_2025_ok.xml", "GewSt": "GewSt_2025.xml"})

	def jahresdokumentation(self, kind: Datenart) -> Path:
		return (
			eric_schema.erklaerung_directory(kind.name)
			/ "Jahresdokumentation"
			/ f"Jahresdokumentation_{kind.root}_{kind.year}.ods"
		)

	def test_the_examples_go_as_the_datenarten_describe_them(self):
		for kind in self.KINDS:
			with self.subTest(datenart=kind.version):
				path = eric_schema.erklaerung_directory(kind.name) / "Beispiele" / self.EXAMPLES[kind.name]
				root = etree.parse(str(path)).getroot()
				header = root.find(f"{ELSTER}TransferHeader")
				self.assertEqual(
					[header.findtext(ELSTER + name) for name in ("Verfahren", "DatenArt", "Vorgang")],
					[kind.verfahren, kind.name, kind.vorgang],
				)
				(recipient,) = root.find(f"{ELSTER}DatenTeil").iter(f"{ELSTER}Empfaenger")
				self.assertEqual(recipient.get("id"), kind.recipient_id)
				((first,),) = root.iter(f"{ELSTER}Nutzdaten")
				self.assertEqual(
					(first.tag, first.get("version")),
					(f"{{{kind.namespace}}}{kind.root}", kind.root_version),
				)
				self.assertEqual(
					first.findtext(f"{{{kind.namespace}}}Vorsatz/{{{kind.namespace}}}Unterfallart"),
					kind.unterfallart,
				)

	def test_the_datenartversionmatrix_names_their_datenart_version_and_plugin(self):
		rows = eric_schema.datenart_versions()
		for kind in (*self.KINDS, ust(2027), kst(2026), gewst(2026)):
			with self.subTest(datenart=kind.version):
				(row,) = (
					row
					for row in rows
					if (row["Verfahren"], row["Datenart(en)"]) == (kind.verfahren, kind.name)
					and row["datenartVersion-Parameter"].replace("<Jahr>", str(kind.year)) == kind.version
				)
				self.assertEqual(row["Plugin-Bibliothek"].replace("<Jahr>", str(kind.year)), kind.plugin)

	def test_the_schemas_hold_the_root_version_and_namespace_of_their_nutzdaten(self):
		for kind in self.KINDS:
			with self.subTest(datenart=kind.version):
				xsd = etree.parse(str(eric_schema.documentation() / kind.schema)).getroot()
				self.assertEqual(xsd.get("targetNamespace"), kind.namespace)
				(element,) = (element for element in xsd if element.get("name") == kind.root)
				self.assertEqual(element.tag, f"{XS}element")
				(version,) = (
					attribute
					for attribute in xsd.iter(f"{XS}attribute")
					if attribute.get("name") == "version"
				)
				self.assertEqual(version.get("fixed"), kind.root_version)

	def test_the_jahresdokumentation_names_namespace_root_and_unterfallart(self):
		for kind in self.KINDS:
			with self.subTest(datenart=kind.version):
				path = self.jahresdokumentation(kind)
				information = eric_schema.lines(path, "Allg. Information")
				self.assertIn(
					f"Für Nutzdaten muss der Namensraum '{kind.namespace}' angegeben werden.", information
				)
				self.assertIn(
					f"Als Name des Nutzdaten-Wurzelelements wird der Datenartname '{kind.root}' verwendet.",
					information,
				)
				fields = {
					row["Name"]: row["Format als regulärer Ausdruck"]
					for row in eric_schema.sheet(path, "Vorsatz - Felder")
				}
				self.assertEqual(fields["Unterfallart"], f"^(?=.{{2,2}}$){kind.unterfallart}")


class DocumentationTest(TestCase):
	"""What the descriptions say, against the files of the ERiC documentation."""

	def test_the_examples_go_as_the_datenarten_describe_them(self):
		for kind, example in ((ustva(2026), eric_schema.example(2026)), (ZMDO, eric_schema.zm_example())):
			with self.subTest(datenart=kind.version):
				root = etree.fromstring(example)
				header = root.find(f"{ELSTER}TransferHeader")
				self.assertEqual(
					[header.findtext(ELSTER + name) for name in ("Verfahren", "DatenArt", "Vorgang")],
					[kind.verfahren, kind.name, kind.vorgang],
				)
				(recipient,) = root.find(f"{ELSTER}DatenTeil").iter(f"{ELSTER}Empfaenger")
				self.assertEqual(recipient.get("id"), kind.recipient_id)
				if kind.recipient is not None:
					self.assertEqual(recipient.text, kind.recipient)
				((first,),) = root.iter(f"{ELSTER}Nutzdaten")
				self.assertEqual(
					(first.tag, first.get("version")),
					(f"{{{kind.namespace}}}{kind.root}", kind.root_version),
				)

	def test_the_datenartversionmatrix_names_their_datenart_version_and_plugin(self):
		"""Datenartversionmatrix.ods: UStVA_<Jahr> with checkUStVA_<Jahr>, ZMDO with checkZMDO and no year."""
		rows = {(row["Verfahren"], row["Datenart(en)"]): row for row in eric_schema.datenart_versions()}
		for kind in (ustva(2026), ZMDO):
			with self.subTest(datenart=kind.version):
				row = rows[(kind.verfahren, kind.name)]
				self.assertEqual(
					(
						row["datenartVersion-Parameter"].replace("<Jahr>", str(kind.year)),
						row["Plugin-Bibliothek"].replace("<Jahr>", str(kind.year)),
					),
					(kind.version, kind.plugin),
				)
		self.assertEqual(rows[(ZMDO.verfahren, ZMDO.name)]["Jahr / Version"], "")

	def test_the_schemas_hold_the_root_and_version_of_their_nutzdaten(self):
		for kind in (ustva(2026), ZMDO):
			with self.subTest(datenart=kind.version):
				xsd = etree.parse(str(eric_schema.documentation() / kind.schema)).getroot()
				(element,) = (
					element for element in xsd.iter(f"{XS}element") if element.get("name") == kind.root
				)
				self.assertEqual(element.getparent(), xsd)
				(version,) = (
					attribute
					for attribute in xsd.iter(f"{XS}attribute")
					if attribute.get("name") == "version"
				)
				fixed = [version.get("fixed")] if version.get("fixed") else []
				enumerated = [value.get("value") for value in version.iter(f"{XS}enumeration")]
				self.assertEqual(fixed + enumerated, [kind.root_version])

	def test_the_nutzdaten_of_the_ustva_declare_the_namespace_of_their_schema(self):
		xsd = etree.parse(str(eric_schema.documentation() / ustva(2026).schema)).getroot()
		self.assertEqual(xsd.get("targetNamespace"), ustva(2026).namespace)

	def test_zm_000005_takes_the_namespace_of_the_delivery_that_includes_it(self):
		"""zm_000005.xsd declares no namespace; elster11_Zm_000005_extern.xsd includes it into that of ElsterXML 11."""
		schema = eric_schema.documentation() / ZMDO.schema
		self.assertIsNone(etree.parse(str(schema)).getroot().get("targetNamespace"))
		envelope = etree.parse(str(schema.with_name("elster11_Zm_000005_extern.xsd"))).getroot()
		self.assertEqual(envelope.get("targetNamespace"), ZMDO.namespace)
		self.assertIn(
			schema.name,
			[Path(include.get("schemaLocation")).name for include in envelope.iter(f"{XS}include")],
		)

	def test_the_jahresdokumentation_sends_zmdo_to_bf(self):
		"""Jahresdokumentation_ZMDO_2.ods: EmpfaengerTyp L and EmpfaengerName BF with the NutzdatenHeader version 11."""
		fields = {row["Name"]: row["Format als regulärer Ausdruck"] for row in eric_schema.zm_fields()}
		self.assertEqual(fields["EmpfaengerTyp"], rf"\Q{ZMDO.recipient_id}\E")
		self.assertIn(rf"\Q{ZMDO.recipient}\E", fields["EmpfaengerName"].split("|"))


class DocsTest(TestCase):
	def test_the_documentation_names_what_the_transmission_of_the_zm_needs(self):
		"""docs/zm.md, „Was die Übermittlung braucht“."""
		cells = {row[0]: row[1] for row in doc_table("### Was die Übermittlung braucht")}
		expected = {
			"Verfahren": ZMDO.verfahren,
			"Datenart": ZMDO.name,
			"Vorgang": ZMDO.vorgang,
			"datenartVersion": ZMDO.version,
			"Plugin": ZMDO.plugin,
		}
		self.assertEqual({name: cells[name].split("`")[1] for name in expected}, expected)
		self.assertIn(f"`{ZMDO.plugin_library}`", cells["Plugin"])
		self.assertIn(
			f'`<Empfaenger id="{ZMDO.recipient_id}">{ZMDO.recipient}</Empfaenger>`',
			cells["Empfänger im NutzdatenHeader"],
		)
