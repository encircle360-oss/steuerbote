"""Reading the Jahresdokumentationen, schemas and the Datenartversionmatrix of the ERiC documentation as data: written
for the tests (files.py), and the ERiC documentation 44.3.6.0 itself, skipped without it (eric_schema.py)."""

import shutil
import tempfile
from functools import cache
from pathlib import Path
from unittest import TestCase

from steuerbote.elster.erklaerung import Form
from steuerbote.elster.tests import eric_schema
from steuerbote.eric.datenart import ZMDO, bilanz, gewst, kst, ust, ustva
from steuerbote.jahresmeldung import documentation
from steuerbote.jahresmeldung.documentation import (
	Jahresdokumentation,
	Leaf,
	Text,
	datenart_versions,
	directory,
	find,
	jahresdokumentation_name,
	jahresdokumentation_path,
	matrix_rows,
	read,
	read_schema,
	schema_path,
	taxonomies,
	years,
)
from steuerbote.jahresmeldung.tests import files
from steuerbote.jahresmeldung.tests.files import Documented
from steuerbote.ustva.documentation import DocumentationError

NAMESPACE = "http://finkonsens.de/elster/elstererklaerung/ust/e50/v2026"


def documented() -> Documented:
	"""A Jahresdokumentation in the form of Jahresdokumentation_E50_2026.ods, with invented fields and rules."""
	result = Documented(
		information=[
			"Deltadokumentation für Datenart E50 (E50) für Anwendung eric",
			"Dokumentation erzeugt für VZ 2026 ERiC 44.3 (Versionslabel 9.0) verglichen mit VZ 2025 ERiC 42.4.4.0 "
			"(Versionslabel 14.0)",
			"",
			"Vordrucke",
			"USt2A - max. lfd. Nr. Vordruck: 1 - Pflichtvordruck",
			"UN - max. lfd. Nr. Vordruck: 3",
			"",
			f"Für Nutzdaten muss der Namensraum '{NAMESPACE}' angegeben werden.",
			"Für Nutzdaten muss der Namensraum 'http://finkonsens.de/elster/elstererklaerung/ust/e50/v2025' "
			"angegeben werden. (alt)",
		]
	)
	result.rows("USt2A", "Kontexte").extend(
		[{"Kontext": "/USt2A/Allg", "max. Wiederholbarkeit": "1", "Änderungsinformation": "KEIN_DELTA"}]
	)
	result.rows("USt2A", "Felder").extend(
		[
			{"Kontext": "Ber_Erkl", "Name": "E3000601", "Formatkennzeichen": "J", "Vordruckzeile": "3"},
			{"Kontext": "", "Name": "Informationsteil", "Internes ERiC Feld": "Ja"},
			{"Kontext": "", "Name": "WJ", "Indexfeld": "Ja"},
			{"Kontext": "Allg", "Name": "E3000401", "Änderungsinformation": "GELOESCHT"},
		]
	)
	result.rows("USt2A", "Regeln").extend(
		[
			{
				"Name": "USt_30002",
				"Fehlercode": "30002",
				"Prüfbedingung": "FeldAngegeben(E3000601)",
				"Regelart": "Fehler",
			},
			{"Name": "USt_30003", "Fehlercode": "30003", "Regelart": "Hinweis"},
			{"Name": "USt_30003", "Fehlercode": "30003", "Änderungsinformation": "GEAENDERT_ALTE_VERSION"},
		]
	)
	result.rows("USt2A", "Kennzahlen").append({"Feldname": "Ber_Erkl/E3000601", "Kennzahl": "10"})
	result.texts["USt2A"] = [
		["", "Umsatzsteuererklärung", "", "", "B 1", "USt2A", "/USt2A[1]"],
		[],
		[
			"3",
			"",
			"",
			"Berichtigte Steuererklärung",
			"FK E3000601",
			"USt2A/Ber_Erkl",
			"/USt2A[1]/Ber_Erkl[1]",
		],
		["", "", "Allgemein", "", "B Allgemein"],
	]
	result.rows("UN", "Regeln").append({"Name": "USt_30087", "Fehlercode": "30087", "Regelart": "Fehler"})
	result.others["Benutzerdefinierte Typen"] = [{"Name": "LAND_OF_WORLD_2020", "Version": "1"}]
	return result


class DirectoryTestCase(TestCase):
	def setUp(self):
		self.directory = Path(tempfile.mkdtemp(prefix="steuerbote-jahresdokumentation-"))
		self.addCleanup(shutil.rmtree, self.directory)


class PathsTest(DirectoryTestCase):
	def test_finds_the_directory_dokumentation_by_its_datenarten(self):
		dokumentation = self.directory / "ERiC-44.3.6.0" / "Dokumentation"
		(dokumentation / "Datenarten" / "ElsterErklaerung").mkdir(parents=True)
		self.assertEqual(find(self.directory), dokumentation)
		self.assertEqual(find(dokumentation), dokumentation)
		with self.assertRaisesRegex(DocumentationError, "holds no ERiC documentation with Datenarten"):
			find(dokumentation / "Datenarten")

	def test_names_the_jahresdokumentation_of_each_datenart(self):
		for kind, path in (
			(
				ust(2026),
				"Datenarten/ElsterErklaerung/USt/Jahresdokumentation/Jahresdokumentation_E50_2026.ods",
			),
			(
				kst(2025),
				"Datenarten/ElsterErklaerung/KSt/Jahresdokumentation/Jahresdokumentation_E30_2025.ods",
			),
			(
				gewst(2025),
				"Datenarten/ElsterErklaerung/GewSt/Jahresdokumentation/Jahresdokumentation_E20_2025.ods",
			),
			(
				ustva(2026),
				"Datenarten/ElsterAnmeldung/UStVA/Jahresdokumentation/Jahresdokumentation_UStVA_2026.ods",
			),
			(
				bilanz("6.10"),
				"Datenarten/ElsterBilanz/Bilanz/Jahresdokumentation/Jahresdokumentation_Bilanz_Taxonomie_6_10.ods",
			),
		):
			with self.subTest(datenart=kind.version):
				self.assertEqual(jahresdokumentation_path(self.directory, kind), self.directory / path)
				self.assertEqual(directory(self.directory, kind), (self.directory / path).parent.parent)

	def test_a_datenart_of_no_year_has_no_jahresdokumentation_of_a_year(self):
		with self.assertRaisesRegex(ValueError, "the Datenart ZMDO has a Jahresdokumentation of no year"):
			jahresdokumentation_name(ZMDO)

	def test_names_the_schema_as_the_datenart_does(self):
		self.assertEqual(
			schema_path(self.directory, kst(2025)),
			self.directory / "Datenarten/ElsterErklaerung/KSt/Schema/2025/E30-2025.xsd",
		)

	def test_finds_the_years_of_the_jahresdokumentationen_of_a_datenart(self):
		folder = jahresdokumentation_path(self.directory, ust(2026)).parent
		folder.mkdir(parents=True)
		for name in (
			"Jahresdokumentation_E50_2026.ods",
			"Jahresdokumentation_E50_2021.ods",
			"Jahresdokumentation_50_2020.ods",
			"Jahresdokumentation_E30_2025.ods",
			"Jahresdokumentation_E50_2027.ods.bak",
		):
			(folder / name).touch()
		self.assertEqual(years(self.directory, ust(1999)), (2021, 2026))
		self.assertEqual(years(self.directory, kst(2026)), ())

	def test_finds_the_taxonomies_of_the_jahresdokumentationen_of_the_bilanz(self):
		folder = jahresdokumentation_path(self.directory, bilanz("6.9")).parent
		folder.mkdir(parents=True)
		for version in ("6_10", "6_9", "5_0"):
			(folder / f"Jahresdokumentation_Bilanz_Taxonomie_{version}.ods").touch()
		(folder / "Jahresdokumentation_Bilanz_Taxonomie_7.ods").touch()
		self.assertEqual(taxonomies(self.directory, bilanz("6.9")), ("5.0", "6.9", "6.10"))


class ReadTest(DirectoryTestCase):
	def setUp(self):
		super().setUp()
		self.jd = read(files.write(self.directory / "Jahresdokumentation_E50_2026.ods", documented()))

	def test_reads_the_information_its_versionslabel_namespace_and_vordrucke(self):
		self.assertEqual(self.jd.file, "Jahresdokumentation_E50_2026.ods")
		self.assertEqual(
			self.jd.information[0], "Deltadokumentation für Datenart E50 (E50) für Anwendung eric"
		)
		self.assertNotIn("", self.jd.information)
		self.assertEqual(self.jd.versionslabel, "9.0")
		self.assertEqual(self.jd.namespace, NAMESPACE)
		self.assertEqual(self.jd.forms, (Form("USt2A", 1, True), Form("UN", 3, False)))

	def test_reads_each_vordruck_with_the_current_rows_of_its_sheets(self):
		self.assertEqual(list(self.jd.vordrucke), ["USt2A", "UN"])
		ust2a = self.jd.vordruck("USt2A")
		self.assertEqual([row["Name"] for row in ust2a.fields], ["E3000601", "Informationsteil", "WJ"])
		self.assertEqual([row["Name"] for row in ust2a.filed_fields], ["E3000601", "WJ"])
		self.assertEqual(ust2a.index_fields, ("WJ",))
		self.assertEqual([row["Kontext"] for row in ust2a.contexts], ["/USt2A/Allg"])
		self.assertEqual(ust2a.kennzahlen[0]["Kennzahl"], "10")
		self.assertEqual([row["Regelart"] for row in ust2a.rules], ["Fehler", "Hinweis"])
		un = self.jd.vordruck("UN")
		self.assertEqual((un.fields, un.texts, len(un.rules), un.index_fields), ((), (), 1, ()))

	def test_finds_the_rules_of_a_fehlercode(self):
		ust2a = self.jd.vordruck("USt2A")
		self.assertEqual(
			[row["Prüfbedingung"] for row in ust2a.rules_of("30002")], ["FeldAngegeben(E3000601)"]
		)
		self.assertEqual(len(ust2a.rules_of("30003")), 1)
		self.assertEqual(ust2a.rules_of("30087"), ())

	def test_lists_every_rule_with_its_vordruck(self):
		self.assertEqual(
			[(vordruck, rule["Fehlercode"]) for vordruck, rule in self.jd.rules],
			[("USt2A", "30002"), ("USt2A", "30003"), ("UN", "30087")],
		)

	def test_reads_the_texts_with_their_line_depth_key_and_place(self):
		self.assertEqual(
			self.jd.vordruck("USt2A").texts,
			(
				Text("", 0, "Umsatzsteuererklärung", "B 1", "USt2A", "/USt2A[1]"),
				Text(
					"3",
					2,
					"Berichtigte Steuererklärung",
					"FK E3000601",
					"USt2A/Ber_Erkl",
					"/USt2A[1]/Ber_Erkl[1]",
				),
				Text("", 1, "Allgemein", "B Allgemein"),
			),
		)
		self.assertEqual(
			[text.feldkennung for text in self.jd.vordruck("USt2A").texts], [None, "E3000601", None]
		)

	def test_keeps_every_sheet_with_a_head_row_by_its_name(self):
		self.assertEqual(
			list(self.jd.sheets),
			[
				"USt2A - Kontexte",
				"USt2A - Felder",
				"USt2A - Regeln",
				"USt2A - Kennzahlen",
				"UN - Regeln",
				"Benutzerdefinierte Typen",
			],
		)
		self.assertEqual(self.jd.sheet("Benutzerdefinierte Typen")[0]["Name"], "LAND_OF_WORLD_2020")
		self.assertEqual(self.jd.sheet("USt2A - Felder"), self.jd.vordruck("USt2A").fields)
		self.assertEqual(self.jd.structural_errors, ())

	def test_names_a_vordruck_or_sheet_it_does_not_have(self):
		with self.assertRaisesRegex(
			DocumentationError, "Jahresdokumentation_E50_2026.ods has no Vordruck FV"
		):
			self.jd.vordruck("FV")
		with self.assertRaisesRegex(
			DocumentationError, "Jahresdokumentation_E50_2026.ods has no sheet Zeichensatz"
		):
			self.jd.sheet("Zeichensatz")

	def test_is_read_only(self):
		with self.assertRaises(TypeError):
			self.jd.vordrucke["FV"] = self.jd.vordruck("UN")  # type: ignore[index]
		with self.assertRaises(AttributeError):
			self.jd.file = "Jahresdokumentation_E50_2027.ods"  # type: ignore[misc]

	def test_a_documentation_without_versionslabel_namespace_or_vordrucke_has_none(self):
		bare = read(files.write(self.directory / "bare.ods", Documented(information=["Einstellungen"])))
		self.assertEqual(
			(bare.versionslabel, bare.namespace, bare.forms, dict(bare.vordrucke)), (None, None, (), {})
		)

	def test_reads_the_structural_errors_of_the_bilanz(self):
		bilanz_jd = Documented(information=["Dokumentation erzeugt für Version v6_9 Versionslabel 1.6"])
		bilanz_jd.others["Strukturelle Fehler"] = [{"Fehlercode": "170105000", "Fehlertext": "XML"}]
		jd = read(files.write(self.directory / "bilanz.ods", bilanz_jd))
		self.assertEqual(
			([row["Fehlercode"] for row in jd.structural_errors], jd.versionslabel), (["170105000"], "1.6")
		)

	def test_refuses_a_text_without_the_key_of_a_field_or_block(self):
		broken = documented()
		broken.texts["USt2A"].append(["4", "Name", "", "Kontext"])
		with self.assertRaisesRegex(
			DocumentationError, "broken.ods, sheet USt2A - Texte, row 5 names no field FK and no block B"
		):
			read(files.write(self.directory / "broken.ods", broken))

	def test_refuses_a_file_without_allgemeine_information_or_that_is_no_spreadsheet(self):
		files.write_matrix(self.directory, [])
		with self.assertRaisesRegex(
			DocumentationError, "Datenartversionmatrix.ods has no sheet Allg. Information"
		):
			read(self.directory / "Datenartversionmatrix.ods")
		with self.assertRaisesRegex(DocumentationError, "fehlt.ods cannot be read as a spreadsheet"):
			read(self.directory / "fehlt.ods")


class SchemaTest(DirectoryTestCase):
	def schema(self, **changes: object) -> Path:
		arguments = {
			"root": "E50",
			"namespace": NAMESPACE,
			"version": "2026",
			"vordrucke": {
				"USt2A": [
					("Ber_Erkl", "E3000601", "Ja1BaseCType"),
					("Allg/Adr", "E3001209", "Land_SType"),
					("", "E3011101", "Zahl_SType"),
				],
				"Vorsatz": [("", "StNr", "StNr_SType")],
			},
			"enumerations": {"Land_SType": ["DE", "AT"]},
		}
		return files.write_schema(self.directory / "E50-2026.xsd", **(arguments | changes))

	def test_reads_namespace_version_and_the_leaves_of_each_vordruck_in_their_order(self):
		schema = read_schema(self.schema(), "E50")
		self.assertEqual((schema.file, schema.namespace, schema.version), ("E50-2026.xsd", NAMESPACE, "2026"))
		self.assertEqual(
			dict(schema.vordrucke),
			{
				"USt2A": (
					Leaf("Ber_Erkl", "E3000601", "Ja1BaseCType"),
					Leaf("Allg/Adr", "E3001209", "Land_SType"),
					Leaf("", "E3011101", "Zahl_SType"),
				),
				"Vorsatz": (Leaf("", "StNr", "StNr_SType"),),
			},
		)
		self.assertEqual(dict(schema.enumerations), {"Land_SType": ("DE", "AT")})
		self.assertEqual(dict(schema.repeats), {})

	def test_reads_the_maxoccurs_of_each_vordruck_and_context_that_repeats(self):
		occurs = {"USt2A": "2", "USt2A/Allg": "99", "USt2A/Allg/Adr": "unbounded", "Vorsatz": "1"}
		schema = read_schema(self.schema(occurs=occurs), "E50")
		self.assertEqual(
			dict(schema.repeats), {"USt2A": "2", "USt2A/Allg": "99", "USt2A/Allg/Adr": "unbounded"}
		)
		self.assertEqual(len(schema.vordrucke["USt2A"]), 3)

	def test_takes_the_values_of_a_complex_type_of_simple_content_as_well(self):
		schema = read_schema(self.schema(complex_enumerations={"Liste_CType": ["1", "2"]}), "E50")
		self.assertEqual(schema.enumerations["Liste_CType"], ("1", "2"))
		self.assertEqual(len(schema.vordrucke["USt2A"]), 3)

	def test_a_schema_without_its_root_or_version_has_neither(self):
		self.assertEqual(dict(read_schema(self.schema(), "E30").vordrucke), {})
		self.assertIsNone(read_schema(self.schema(), "E30").version)
		self.assertIsNone(read_schema(self.schema(version=None), "E50").version)

	def test_refuses_a_file_that_is_no_schema(self):
		broken = self.directory / "kaputt.xsd"
		broken.write_text("<xs:schema", encoding="utf-8")
		for path in (broken, self.directory / "fehlt.xsd"):
			with (
				self.subTest(path=path.name),
				self.assertRaisesRegex(DocumentationError, "cannot be read as a schema"),
			):
				read_schema(path, "E50")


class MatrixTest(DirectoryTestCase):
	ROWS = (
		("ElsterErklaerung", "KSt", "<Jahr>: ab 2015", "KSt_30_<Jahr>", "checkKSt_<Jahr>"),
		("ElsterErklaerung", "KSt", "<Jahr>: 2015, 2016", "KSt_32_<Jahr>", "checkKSt_<Jahr>"),
		("ElsterErklaerung", "USt", "<Jahr>: ab 2015", "USt_<Jahr>", "checkUSt_<Jahr>"),
		("ElsterBilanz", "Bilanz", "HGB-Taxonomie 6.9", "Bilanz_6.9", "checkBilanz_6_9"),
		("ElsterExtern", "ZMDO", "", "ZMDO", "checkZMDO"),
	)

	def setUp(self):
		super().setUp()
		files.write_matrix(self.directory, self.ROWS)
		self.rows = datenart_versions(self.directory)

	def test_reads_the_rows_of_the_datenartversionen(self):
		self.assertEqual([row["Datenart(en)"] for row in self.rows], ["KSt", "KSt", "USt", "Bilanz", "ZMDO"])

	def test_finds_the_rows_of_the_datenartversion_of_a_datenart(self):
		for kind, plugins in (
			(kst(2026), ["checkKSt_<Jahr>"]),
			(ust(2026), ["checkUSt_<Jahr>"]),
			(bilanz("6.9"), ["checkBilanz_6_9"]),
			(bilanz("6.10"), []),
			(ZMDO, ["checkZMDO"]),
			(gewst(2026), []),
		):
			with self.subTest(datenart=kind.version):
				self.assertEqual([row["Plugin-Bibliothek"] for row in matrix_rows(self.rows, kind)], plugins)

	def test_refuses_a_documentation_without_the_matrix(self):
		(self.directory / "Datenartversionmatrix.ods").unlink()
		with self.assertRaisesRegex(
			DocumentationError, "Datenartversionmatrix.ods cannot be read as a spreadsheet"
		):
			datenart_versions(self.directory)


@cache
def real(kind_version: str) -> Jahresdokumentation:
	"""A Jahresdokumentation of the ERiC documentation, read once per run."""
	kinds = {kind.version: kind for kind in (ust(2026), kst(2025), gewst(2025), ustva(2026), bilanz("6.9"))}
	return read(
		jahresdokumentation_path(documentation.find(eric_schema.documentation()), kinds[kind_version])
	)


class RealDocumentationTest(TestCase):
	"""The reader against the ERiC documentation 44.3.6.0; skipped without it, see eric_schema.py."""

	def test_finds_the_directory_dokumentation(self):
		self.assertEqual(find(eric_schema.documentation()), eric_schema.documentation())

	def test_reads_the_jahresdokumentation_e50_2026(self):
		jd = real("USt_2026")
		ust2a = jd.vordruck("USt2A")
		self.assertEqual((jd.versionslabel, jd.namespace), ("9.0", ust(2026).namespace))
		self.assertEqual(
			jd.forms,
			(Form("USt2A", 1, True), Form("UN", 1, False), Form("FV", 1, False), Form("Vorsatz", 1, True)),
		)
		self.assertEqual((len(ust2a.filed_fields), len(ust2a.kennzahlen), len(ust2a.rules)), (176, 88, 175))

	def test_reads_the_vordrucke_of_the_jahresdokumentationen_e30_and_e20_2025(self):
		self.assertEqual(real("KSt_30_2025").versionslabel, "7.0")
		self.assertLessEqual(
			{"KSt1", "GK", "ZVE", "WA", "Verluste", "Z", "AESt", "KSt1F", "Vorsatz"},
			set(real("KSt_30_2025").vordrucke),
		)
		self.assertEqual(real("GewSt_2025").versionslabel, "11.0")
		self.assertLessEqual({"GewSt1A", "BEG", "BEKGW", "EMU", "Vorsatz"}, set(real("GewSt_2025").vordrucke))

	def test_anlage_gk_and_kst_1_f_number_their_instances_with_the_indexfeld_wj(self):
		jd = real("KSt_30_2025")
		filed = ("KSt1", "GK", "ZVE", "Z", "Verluste", "WA", "KSt1F")
		self.assertEqual(
			{name: jd.vordruck(name).index_fields for name in filed if jd.vordruck(name).index_fields},
			{"GK": ("WJ",), "KSt1F": ("WJ",)},
		)

	def test_the_texts_of_the_fields_of_an_erklaerung_are_those_of_its_filed_fields(self):
		for kind_version in ("USt_2026", "KSt_30_2025", "GewSt_2025"):
			for vordruck in real(kind_version).vordrucke.values():
				if vordruck.texts:
					with self.subTest(datenart=kind_version, vordruck=vordruck.name):
						self.assertEqual(
							{text.feldkennung for text in vordruck.texts if text.feldkennung},
							{row["Name"] for row in vordruck.filed_fields},
						)

	def test_reads_the_rules_of_the_bilanz_and_its_structural_errors(self):
		jd = real("Bilanz_6.9")
		self.assertEqual(jd.forms, (Form("Kontext", 1, True), Form("Header", 1, False)))
		self.assertEqual(
			(len(jd.vordruck("Kontext").rules), len(jd.vordruck("Header").rules), len(jd.structural_errors)),
			(270, 1, 171),
		)
		self.assertEqual(
			[row["Name"] for row in jd.vordruck("Kontext").rules_of("170205010")], ["AktivaUngleichPassiva"]
		)

	def test_reads_the_schema_e50_2026_and_the_rows_of_the_matrix(self):
		root = eric_schema.documentation()
		schema = read_schema(schema_path(root, ust(2026)), "E50")
		self.assertEqual((schema.namespace, schema.version), (ust(2026).namespace, "2026"))
		self.assertEqual(list(schema.vordrucke), ["USt2A", "UN", "FV", "Vorsatz"])
		self.assertEqual(len(schema.vordrucke["USt2A"]), 176)
		self.assertEqual(schema.repeats["USt2A/Ber_VoSt_15a/Grdst_erstm_Verw/Ang_Grdst"], "99")
		e30 = read_schema(schema_path(root, kst(2025)), "E30")
		self.assertEqual((e30.repeats["GK"], e30.repeats["KSt1/AE/Einzel"]), ("2", "99"))
		(row,) = matrix_rows(datenart_versions(root), kst(2026))
		self.assertEqual(
			(row["Jahr / Version"], row["Plugin-Bibliothek"]), ("<Jahr>: ab 2015", "checkKSt_<Jahr>")
		)
