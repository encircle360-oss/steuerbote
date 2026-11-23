"""The year check of the annual filings: the data of each Datenart against its Jahresdokumentation, schema and the
Datenartversionmatrix.

The tests without the ERiC documentation write one that agrees with the data of 2026 (agreeing.Documentation) and change
one fact in it or in the data; DocumentationTest checks every Datenart against the ERiC documentation itself.
"""

import io
import runpy
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from unittest import TestCase, mock

from steuerbote.elster import ust2a_xml, vorsatz
from steuerbote.elster.erklaerung import Field, Form, FormCatalogue, Rule
from steuerbote.elster.tests import eric_schema
from steuerbote.eric.datenart import bilanz, gewst, kst, ust
from steuerbote.jahresmeldung import yearcheck
from steuerbote.jahresmeldung.documentation import read, read_schema
from steuerbote.jahresmeldung.tests import agreeing, files
from steuerbote.jahresmeldung.tests.agreeing import Documentation
from steuerbote.jahresmeldung.tests.files import Documented
from steuerbote.jahresmeldung.yearcheck import (
	KST_CHECK,
	IncomeTax,
	Table,
	conjuncts,
	form_catalogue_differences,
	latest,
	main,
	missing,
	selection,
)
from steuerbote.kst import years as kst_years
from steuerbote.kst.years import RuleExpectation
from steuerbote.ustjahr import form as ustjahr_form
from steuerbote.ustjahr import rules as ustjahr_rules
from steuerbote.ustva import kennzahlen
from steuerbote.ustva import yearcheck as ustva_yearcheck
from steuerbote.ustva import years as ustva_years
from steuerbote.ustva.documentation import DocumentationError
from steuerbote.ustva.tests import eric_documentation

APP_ROOT = Path(__file__).resolve().parents[3]
E50 = "Jahresdokumentation_E50_2026.ods"
E30 = "Jahresdokumentation_E30_2025.ods"
USTVA_CONTEXT = "Umsatzsteuervoranmeldung"
UST_2026, KST_2025, GEWST_2025, BILANZ_6_9 = ust(2026), kst(2025), gewst(2025), bilanz("6.9")


class SyntheticTestCase(TestCase):
	def setUp(self):
		self.directory = Path(tempfile.mkdtemp(prefix="steuerbote-jahresmeldung-yearcheck-"))
		self.addCleanup(shutil.rmtree, self.directory)
		self.documentation = Documentation.agreeing()

	def jd(self, kind=UST_2026) -> Documented:
		return self.documentation.jahresdokumentationen[kind]

	def written(self) -> Path:
		return self.documentation.write(self.directory)

	def run_main(self, *arguments: str) -> tuple[int, list[str], str]:
		stdout, stderr = io.StringIO(), io.StringIO()
		code = main([str(self.written()), *arguments], stdout, stderr)
		return code, stdout.getvalue().splitlines(), stderr.getvalue()

	def assertLines(self, *lines: str, arguments: tuple[str, ...] = ()) -> None:
		code, found, errors = self.run_main(*arguments)
		self.assertEqual((found, errors), (list(lines), ""))
		self.assertEqual(code, 1 if lines else 0)


class AgreementTest(SyntheticTestCase):
	def test_prints_nothing_where_the_documentation_says_what_the_data_say(self):
		self.assertLines()
		self.assertLines(arguments=("2026",))
		self.assertLines(arguments=("UStVA", "USt", "KSt", "GewSt", "Bilanz", "2026"))

	def test_checks_the_directory_dokumentation_itself_as_well(self):
		stdout, stderr = io.StringIO(), io.StringIO()
		self.assertEqual(main([str(self.written())], stdout, stderr), 0)


class SelectionTest(TestCase):
	def names(self, *arguments: str) -> list[tuple[str, tuple[int | str, ...]]]:
		return [(module.name, keys) for module, keys in selection(arguments)]

	def test_without_arguments_every_datenart_checks_the_years_of_its_tables(self):
		self.assertEqual(
			self.names(), [("UStVA", ()), ("USt", ()), ("KSt", ()), ("GewSt", ()), ("Bilanz", ())]
		)

	def test_takes_the_datenarten_in_any_case_and_the_years_for_each(self):
		self.assertEqual(
			self.names("kst", "UStVA", "2026", "2027", "KSt"),
			[("KSt", (2026, 2027)), ("UStVA", (2026, 2027))],
		)

	def test_a_version_of_the_taxonomy_goes_to_the_bilanz_alone(self):
		self.assertEqual(self.names("6.10"), [("Bilanz", ("6.10",))])
		self.assertEqual(self.names("2026", "6.10")[-1], ("Bilanz", (2026, "6.10")))
		self.assertEqual(self.names("2026", "6.10")[0], ("UStVA", (2026,)))

	def test_refuses_a_version_for_another_datenart_and_what_is_neither(self):
		with self.assertRaisesRegex(
			ValueError, "6.10 is a version of the HGB-Taxonomie, which only Bilanz takes"
		):
			selection(("KSt", "6.10"))
		with self.assertRaisesRegex(
			ValueError, "zwanzig is no Datenart \\(UStVA, USt, KSt, GewSt, Bilanz\\)"
		):
			selection(("zwanzig",))


class CommandTest(SyntheticTestCase):
	def test_ends_with_2_when_the_documentation_lacks_a_file_and_prints_what_it_found(self):
		self.jd().row("USt2A", "Felder", Name="E3000601")["Vordruckzeile"] = "4"
		code, found, errors = self.run_main("USt", "2026", "2025")
		self.assertEqual(code, 2)
		self.assertEqual(
			found,
			["USt 2026, field E3000601: Vordruckzeile 3; Jahresdokumentation_E50_2026.ods: Vordruckzeile 4"],
		)
		self.assertIn("Jahresdokumentation_E50_2025.ods cannot be read as a spreadsheet", errors)

	def test_goes_on_with_the_other_datenarten_after_a_missing_file(self):
		del self.documentation.jahresdokumentationen[UST_2026]
		self.documentation.matrix = [row for row in self.documentation.matrix if row[1] != "GewSt"]
		code, found, errors = self.run_main()
		self.assertEqual(
			(code, found),
			(
				2,
				[
					"GewSt 2026, plugin: GewSt_2026, checkGewSt_2026; Datenartversionmatrix.ods: no row of GewSt_2026"
				],
			),
		)
		self.assertIn("Jahresdokumentation_E50_2026.ods cannot be read", errors)

	def test_ends_with_2_without_the_documentation(self):
		stdout, stderr = io.StringIO(), io.StringIO()
		self.assertEqual(main([str(self.directory / "leer")], stdout, stderr), 2)
		self.assertIn("holds no ERiC documentation with Datenarten", stderr.getvalue())

	def test_refuses_what_is_no_datenart_year_or_version(self):
		with mock.patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit) as exited:
			main([str(self.directory), "zwanzig"])
		self.assertEqual(exited.exception.code, 2)

	def test_names_the_years_the_documentation_holds_beyond_the_tables_without_years(self):
		self.documentation.jahresdokumentationen[ust(2027)] = Documented(information=["Einstellungen"])
		self.documentation.jahresdokumentationen[kst(2027)] = Documented(information=["Einstellungen"])
		lines = (
			"USt 2027: not in YEARS of steuerbote/ustjahr/years.py; Jahresdokumentation_E50_2027.ods: documented",
			"KSt 2027: not in YEARS of steuerbote/kst/years.py; Jahresdokumentation_E30_2027.ods: documented",
		)
		self.assertLines(*lines)
		self.assertLines(arguments=("2026",))

	def test_names_a_year_of_the_ustva_beyond_its_table(self):
		latest = ustva_years.LATEST_YEAR
		eric_documentation.write(
			self.directory, eric_documentation.documented(ustva_yearcheck.data_for(latest), latest + 1)
		)
		code, found, _ = self.run_main("UStVA")
		self.assertEqual(
			(code, found),
			(
				1,
				[
					f"UStVA {latest + 1}: not in YEARS of steuerbote/ustva/years.py; "
					f"Jahresdokumentation_UStVA_{latest + 1}.ods: documented"
				],
			),
		)

	def test_runs_as_a_module(self):
		with (
			mock.patch.object(sys, "argv", ["yearcheck", str(self.written()), "2026"]),
			mock.patch.object(sys, "stdout", io.StringIO()) as stdout,
			self.assertRaises(SystemExit) as exited,
		):
			runpy.run_path(yearcheck.__file__, run_name="__main__")
		self.assertEqual((exited.exception.code, stdout.getvalue()), (0, ""))


class UStVATest(SyntheticTestCase):
	def test_prints_the_lines_of_the_year_check_of_the_ustva(self):
		self.documentation.ustva.field(USTVA_CONTEXT, "Kz66")["Vordruckzeile"] = "37"
		self.assertLines(
			"UStVA 2026, catalogue 2026, Kz 66: line 38; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 37",
			arguments=("UStVA",),
		)

	def test_compares_the_latest_data_with_the_documentation_of_a_new_year(self):
		latest = ustva_years.LATEST_YEAR
		new = latest + 1
		eric_documentation.write(
			self.directory, eric_documentation.documented(ustva_yearcheck.data_for(latest), new)
		)
		code, found, _ = self.run_main("UStVA", str(new))
		self.assertEqual(code, 1)
		self.assertEqual(
			found[:2],
			[
				f"UStVA {new} is missing in YEARS of steuerbote/ustva/years.py, CATALOGUES of "
				"steuerbote/ustva/kennzahlen.py, SCHEMAS of steuerbote/elster/ustva_xml.py, LAYOUTS of "
				"steuerbote/dauerfrist/form.py; the latest data take its place:",
				f"UStVA {new}, schema {latest}, version: {latest}; UStVA-{new}.xsd: {new}",
			],
		)


class ProvisionalUStVATest(SyntheticTestCase):
	"""A provisional year of the UStVA comes from the documentation of a later release of ERiC (steuerbote/ustva/years.py):
	a run without years passes over it where the documentation holds no Jahresdokumentation of it, a year named needs
	it."""

	def setUp(self):
		super().setUp()
		year = ustva_years.LATEST_YEAR + 1
		provisional = ustva_years.Year(
			year, None, None, None, provisional=True, documentation="Beta ERiC 99.1.0.0", form_year=year - 1
		)
		table = MappingProxyType({**ustva_years.YEARS, year: provisional})
		for target in (ustva_years, ustva_yearcheck):
			patcher = mock.patch.object(target, "YEARS", table)
			patcher.start()
			self.addCleanup(patcher.stop)
		self.year = year

	def test_a_run_without_years_passes_over_it(self):
		self.assertLines(arguments=("UStVA",))
		self.assertLines()

	def test_a_year_named_needs_its_jahresdokumentation(self):
		code, found, errors = self.run_main("UStVA", str(self.year))
		self.assertEqual((code, found), (2, []))
		self.assertIn(f"Jahresdokumentation_UStVA_{self.year}.ods cannot be read", errors)


class UStFormCatalogueTest(SyntheticTestCase):
	def field(self, element: str) -> dict[str, str]:
		return self.jd().row("USt2A", "Felder", Name=element)

	def test_finds_another_versionslabel_namespace_and_version(self):
		self.jd().information[0] = "Dokumentation erzeugt für VZ 2026 ERiC 45.1 (Versionslabel 11.0)"
		self.jd().information[-1] = "Für Nutzdaten muss der Namensraum 'urn:anders' angegeben werden."
		self.documentation.schemas[UST_2026]["namespace"] = "urn:schema"
		self.documentation.schemas[UST_2026]["version"] = "2027"
		self.assertLines(
			f"USt 2026, source: {E50} (Versionslabel 9.0); {E50}: Versionslabel 11.0",
			f"USt 2026, namespace: {UST_2026.namespace}; {E50}: urn:anders",
			f"USt 2026, namespace: {UST_2026.namespace}; E50-2026.xsd: urn:schema",
			"USt 2026, version: 2026; E50-2026.xsd: 2027",
			arguments=("USt",),
		)

	def test_finds_a_documentation_without_versionslabel_and_namespace(self):
		self.jd().information[:] = [
			line for line in self.jd().information if "Versionslabel" not in line and "Namensraum" not in line
		]
		self.assertLines(
			f"USt 2026, source: {E50} (Versionslabel 9.0); {E50}: Versionslabel none",
			f"USt 2026, namespace: {UST_2026.namespace}; {E50}: none",
			arguments=("USt",),
		)

	def test_finds_vordrucke_listed_otherwise_or_not_at_all(self):
		information = self.jd().information
		information[information.index("UN - max. lfd. Nr. Vordruck: 1")] = "UN - max. lfd. Nr. Vordruck: 2"
		information.remove("FV - max. lfd. Nr. Vordruck: 1")
		information.append("ZM - max. lfd. Nr. Vordruck: 1 - Pflichtvordruck")
		self.assertLines(
			f"USt 2026, Vordruck UN: max. lfd. Nr. 1; {E50}: max. lfd. Nr. 2",
			f"USt 2026, Vordruck FV: max. lfd. Nr. 1; {E50}: not listed",
			f"USt 2026, Vordruck ZM: not in the catalogue; {E50}: Pflichtvordruck",
			arguments=("USt",),
		)

	def test_finds_fields_the_year_dropped_added_or_ordered_otherwise(self):
		fields = self.jd().rows("USt2A", "Felder")
		fields.remove(self.field("E3000601"))
		fields.insert(0, {"Name": "E3999999", "Kontext": "Neu"})
		fields[1], fields[2] = fields[2], fields[1]
		_, found, _ = self.run_main("USt")
		self.assertEqual(
			found,
			[
				f"USt 2026, USt2A, E3000601: a field; {E50}: no such field",
				f"USt 2026, USt2A, E3999999: no such field; {E50}: a field",
				f"USt 2026, USt2A, order: E3000401 before E3000901; {E50}: E3000901 before E3000401",
			],
		)

	def test_finds_the_fields_of_the_schema_in_another_place_or_order(self):
		leaves = self.documentation.schemas[UST_2026]["vordrucke"]["USt2A"]
		leaves[0] = ("Anders", *leaves[0][1:])
		leaves[1], leaves[2] = leaves[2], leaves[1]
		self.assertLines(
			"USt 2026, USt2A, Ber_Erkl/E3000601: a field; E50-2026.xsd: no such field",
			"USt 2026, USt2A, Anders/E3000601: no such field; E50-2026.xsd: a field",
			"USt 2026, USt2A, order: Allg/Unternehmen/E3000401 before Allg/Unternehmen/E3000901; E50-2026.xsd: "
			"Allg/Unternehmen/E3000901 before Allg/Unternehmen/E3000401",
			arguments=("USt",),
		)

	def test_finds_a_schema_without_a_vordruck_of_the_catalogue(self):
		del self.documentation.schemas[UST_2026]["vordrucke"]["USt2A"]
		self.assertLines(
			"USt 2026, Vordruck USt2A: in the catalogue; E50-2026.xsd: no element USt2A", arguments=("USt",)
		)

	def test_finds_the_vordrucke_of_the_schema_in_another_order_or_number(self):
		vordrucke = self.documentation.schemas[UST_2026]["vordrucke"]
		self.documentation.schemas[UST_2026]["vordrucke"] = {
			name: vordrucke[name] for name in ("UN", "USt2A", "FV", "Vorsatz") if name in vordrucke
		} | {"UN": [], "FV": []}
		self.documentation.schemas[UST_2026]["occurs"] = {"UN": "2"}
		self.assertLines(
			"USt 2026, order of the Vordrucke: USt2A before UN; E50-2026.xsd: UN before USt2A",
			"USt 2026, Vordruck UN: max. lfd. Nr. 1; E50-2026.xsd: maxOccurs 2",
			arguments=("USt",),
		)

	def test_finds_each_column_of_a_field_that_differs(self):
		row = self.field("E3001001")
		row.update(
			{
				"Kontext": "Allg/Anders",
				"Formatkennzeichen": "X",
				"Vordruckzeile": "8",
				"Pflichtfeld": "Ja",
				"max. Zeilen": "2",
				"Beschreibung": "Art der  Firma",
				"Max. Länge": "30",
				"Format als regulärer Ausdruck": "[a-z]+",
			}
		)
		where = "USt 2026, field E3001001"
		self.assertLines(
			f"{where}: Kontext Allg/Unternehmen; {E50}: Kontext Allg/Anders",
			f"{where}: Formatkennzeichen C; {E50}: Formatkennzeichen X",
			f"{where}: Vordruckzeile 7; {E50}: Vordruckzeile 8",
			f"{where}: Pflichtfeld Nein; {E50}: Pflichtfeld Ja",
			f"{where}: max. Zeilen 1; {E50}: max. Zeilen 2",
			f"{where}: Beschreibung Art des Unternehmens; {E50}: Beschreibung Art der Firma",
			f"{where}: Max. Länge 999; {E50}: Max. Länge 30",
			f"{where}: Format als regulärer Ausdruck {ust2a_xml.SCHEMAS[2026].field('E3001001').pattern}; {E50}: "
			"Format als regulärer Ausdruck [a-z]+",
			arguments=("USt",),
		)

	def test_takes_the_year_for_the_placeholder_of_a_beschreibung(self):
		row = self.field("E3011301")
		row["Beschreibung"] = row["Beschreibung"].replace("2026", "$VZ$")
		self.assertLines(arguments=("USt",))

	def test_compares_the_lines_of_the_mitwirkung_with_those_the_jd_gives_them(self):
		self.field("E3002501")["Vordruckzeile"] = "128"
		self.field("E3002602")["Vordruckzeile"] = "127"
		self.assertLines(
			f"USt 2026, field E3002501: Vordruckzeile 23; {E50}: Vordruckzeile 128",
			f"USt 2026, field E3002602: Vordruckzeile 123; {E50}: Vordruckzeile 127",
			arguments=("USt",),
		)

	def test_finds_another_kennzahl_and_other_values_of_a_list(self):
		self.jd().row("USt2A", "Kennzahlen", Kennzahl="110")["Kennzahl"] = "111"
		listing = next(field_ for field_ in ust2a_xml.SCHEMAS[2026].fields if field_.options)
		self.documentation.schemas[UST_2026]["complex_enumerations"][f"{listing.feldkennung}_CType"] = ["X"]
		_, found, _ = self.run_main("USt")
		self.assertEqual(
			found,
			[
				f"USt 2026, field E3000601: Kennzahl 110; {E50}: Kennzahl 111",
				f"USt 2026, field {listing.feldkennung}: values {', '.join(listing.options)}; E50-2026.xsd: values X",
			],
		)

	def test_a_field_without_a_line_of_the_form_has_none(self):
		catalogue = ust2a_xml.SCHEMAS[2026]
		fields = tuple(
			replace(field_, line=None) if field_.feldkennung == "E3000601" else field_
			for field_ in catalogue.fields
		)
		with mock.patch.object(
			ust2a_xml, "SCHEMAS", MappingProxyType({2026: replace(catalogue, fields=fields)})
		):
			self.assertLines(
				f"USt 2026, field E3000601: Vordruckzeile none; {E50}: Vordruckzeile 3", arguments=("USt",)
			)


class FormCatalogueTest(SyntheticTestCase):
	"""The comparison of a form catalogue of its own, as KSt and GewSt will have them."""

	def catalogue(self, **changes: object) -> FormCatalogue:
		fields = (
			Field("KSt1", "", "E8000015", "Organgesellschaft", "X", line=1, rows=1),
			Field(
				"KSt1",
				"Allgemein",
				"E8000101",
				"Bezeichnung",
				"C",
				line=1,
				kennzahl="11",
				length=150,
				required=True,
			),
		)
		arguments = {
			"datenart": kst(2025),
			"source": f"{E30} (Versionslabel 7.0)",
			"forms": (Form("KSt1", 1, True), Form("Vorsatz", 1, True)),
			"fields": fields,
			"rules": (
				Rule("8900001", "KSt1_Regel", "Text"),
				Rule("8900002", "KSt1_Hinweis", "Text", hint=True),
			),
		}
		return FormCatalogue(**(arguments | changes))

	def documented(self) -> Documented:
		result = Documented(
			information=[
				"Dokumentation erzeugt für VZ 2025 ERiC 44.3 (Versionslabel 7.0)",
				"KSt1 - max. lfd. Nr. Vordruck: 1 - Pflichtvordruck",
				"Vorsatz - max. lfd. Nr. Vordruck: 1 - Pflichtvordruck",
				f"Für Nutzdaten muss der Namensraum '{kst(2025).namespace}' angegeben werden.",
			]
		)
		result.rows("KSt1", "Felder").extend(
			[
				{
					"Kontext": "",
					"Name": "E8000015",
					"Beschreibung": "Organgesellschaft",
					"Formatkennzeichen": "X",
					"Vordruckzeile": "1",
					"max. Zeilen": "1",
				},
				{
					"Kontext": "Allgemein",
					"Name": "E8000101",
					"Beschreibung": "Bezeichnung",
					"Formatkennzeichen": "C",
					"Vordruckzeile": "1",
					"max. Zeilen": "1",
					"Max. Länge": "150",
					"Pflichtfeld": "Ja",
				},
			]
		)
		result.rows("KSt1", "Kennzahlen").append({"Feldname": "Allgemein/E8000101", "Kennzahl": "11"})
		result.rows("KSt1", "Regeln").extend(
			[
				{"Name": "KSt1_Regel", "Fehlercode": "8900001", "Regelart": "Fehler"},
				{"Name": "KSt1_Hinweis", "Fehlercode": "8900002", "Regelart": "Hinweis"},
			]
		)
		return result

	def differences(
		self, catalogue: FormCatalogue, documented: Documented, own_year: bool = True
	) -> list[str]:
		jd = read(files.write(self.directory / E30, documented))
		xsd = read_schema(
			files.write_schema(
				self.directory / "E30-2025.xsd",
				"E30",
				kst(2025).namespace,
				"2025",
				{"KSt1": [("", "E8000015", "JaX"), ("Allgemein", "E8000101", "String")], "Vorsatz": []},
			),
			"E30",
		)
		return [
			str(difference)
			for difference in form_catalogue_differences("KSt 2025", catalogue, jd, xsd, own_year)
		]

	def test_finds_nothing_where_the_documentation_agrees(self):
		self.assertEqual(self.differences(self.catalogue(), self.documented()), [])

	def test_takes_a_source_that_names_the_file_and_its_versionslabel_in_either_way(self):
		for source in (f"{E30} (Versionslabel 7.0)", f"{E30}, Versionslabel 7.0, provisionally for 2026"):
			with self.subTest(source=source):
				self.assertEqual(self.differences(self.catalogue(source=source), self.documented()), [])
		self.assertEqual(
			self.differences(self.catalogue(source=f"{E30}, Versionslabel 7.01"), self.documented()),
			[f"KSt 2025, source: {E30}, Versionslabel 7.01; {E30}: Versionslabel 7.0"],
		)

	def test_takes_a_kennzahl_with_or_without_its_sachbereich_and_a_beschreibung_with_or_without_the_year(
		self,
	):
		documented = self.documented()
		documented.row("KSt1", "Kennzahlen", Kennzahl="11")["Sachbereich"] = "13"
		documented.row("KSt1", "Felder", Name="E8000015")["Beschreibung"] = "Organgesellschaft $VZ$"
		first, second = self.catalogue().fields
		for kennzahl, label in (("11", "Organgesellschaft 2025"), ("13.11", "Organgesellschaft $VZ$")):
			fields = (replace(first, label=label), replace(second, kennzahl=kennzahl))
			with self.subTest(kennzahl=kennzahl):
				self.assertEqual(self.differences(self.catalogue(fields=fields), documented), [])
		fields = (first, replace(second, kennzahl="12.11"))
		self.assertEqual(
			self.differences(self.catalogue(fields=fields), documented),
			[
				f"KSt 2025, field E8000015: Beschreibung Organgesellschaft; {E30}: Beschreibung Organgesellschaft 2025",
				f"KSt 2025, field E8000101: Kennzahl 12.11; {E30}: Kennzahl 13.11",
			],
		)

	def test_leaves_out_the_indexfeld_of_the_documentation_and_the_schema(self):
		documented = self.documented()
		documented.rows("KSt1", "Felder").insert(0, {"Kontext": "", "Name": "WJ", "Indexfeld": "Ja"})
		jd = read(files.write(self.directory / E30, documented))
		leaves = [("", "WJ", "Index"), ("", "E8000015", "JaX"), ("Allgemein", "E8000101", "String")]
		path = self.directory / "E30-2025.xsd"
		xsd = read_schema(
			files.write_schema(path, "E30", kst(2025).namespace, "2025", {"KSt1": leaves, "Vorsatz": []}),
			"E30",
		)
		self.assertEqual(list(form_catalogue_differences("KSt 2025", self.catalogue(), jd, xsd)), [])

	def test_finds_rules_named_otherwise_of_another_regelart_or_missing(self):
		catalogue = self.catalogue(
			rules=(
				Rule("8900001", "KSt1_Anders", "Text"),
				Rule("8900002", "KSt1_Hinweis", "Text"),
				Rule("8900003", "Neu", ""),
			)
		)
		self.assertEqual(
			self.differences(catalogue, self.documented()),
			[
				f"KSt 2025, rule 8900001: KSt1_Anders, Fehler; {E30}: KSt1_Regel, Fehler",
				f"KSt 2025, rule 8900002: KSt1_Hinweis, Fehler; {E30}: KSt1_Hinweis, Hinweis",
				f"KSt 2025, rule 8900003: Neu, Fehler; {E30}: no such rule",
			],
		)

	def test_finds_a_vordruck_the_documentation_does_not_have(self):
		catalogue = self.catalogue(
			forms=(Form("KSt1", 1, True), Form("GK", 2), Form("Vorsatz", 1, True)),
			fields=(*self.catalogue().fields, Field("GK", "", "E8002001", "Gewinn", "N", line=1)),
		)
		self.assertEqual(
			self.differences(catalogue, self.documented()),
			[
				f"KSt 2025, Vordruck GK: max. lfd. Nr. 2; {E30}: not listed",
				"KSt 2025, Vordruck GK: in the catalogue; E30-2025.xsd: no element GK",
				f"KSt 2025, GK: its fields; {E30}: no Vordruck GK",
			],
		)

	def test_a_provisional_year_takes_neither_namespace_nor_version_of_the_documentation(self):
		catalogue = self.catalogue(datenart=kst(2026))
		self.assertEqual(self.differences(catalogue, self.documented(), own_year=False), [])
		self.assertEqual(
			self.differences(catalogue, self.documented())[:2],
			[
				f"KSt 2025, namespace: {kst(2026).namespace}; {E30}: {kst(2025).namespace}",
				f"KSt 2025, namespace: {kst(2026).namespace}; E30-2025.xsd: {kst(2025).namespace}",
			],
		)


class UStRulesTest(SyntheticTestCase):
	def rule(self, code: str) -> dict[str, str]:
		return self.jd().row("USt2A", "Regeln", Fehlercode=code)

	def test_finds_a_rule_named_otherwise_in_another_context_or_regelart(self):
		self.rule("30002").update({"Name": "USt_Anders", "Kontext": "Ber_Erkl", "Regelart": "Hinweis"})
		ours = ustjahr_form.CATALOGUES[2026].rule("30002")
		self.assertLines(
			f"USt 2026, rule 30002: {ours.name} in {ours.context or 'USt2A'}, {ours.severity.value}; {E50}: USt_Anders in "
			"Ber_Erkl, Hinweis",
			arguments=("USt",),
		)

	def test_finds_a_rule_the_year_dropped_and_one_it_added(self):
		rules = self.jd().rows("USt2A", "Regeln")
		dropped = self.rule("30087")
		rules.remove(dropped)
		rules.append({"Kontext": "", "Name": "USt_39999", "Fehlercode": "39999", "Regelart": "Fehler"})
		ours = ustjahr_form.CATALOGUES[2026].rule("30087")
		self.assertLines(
			f"USt 2026, rule 30087: {ours.name} in {ours.context or 'USt2A'}, {ours.severity.value}; {E50}: no such rule",
			f"USt 2026, rule 39999: no such rule; {E50}: USt_39999 in USt2A, Fehler",
			"USt 2026, rule 30087: left to ERiC; Jahresdokumentation_E50_2026.ods: no such rule",
			f"USt 2026, rule 39999: neither checked by steuerbote/ustjahr/rules.py nor left to ERiC; {E50}: Fehler USt_39999",
			arguments=("USt",),
		)

	def test_finds_a_rule_steuerbote_checks_whose_condition_changed_or_that_is_gone(self):
		checked = ustjahr_rules.LOCAL_RULES[2026][0]
		self.rule(checked.code)["Prüfbedingung"] = "FeldAngegeben(E3999999)"
		other = ustjahr_rules.LOCAL_RULES[2026][1]
		self.jd().rows("USt2A", "Regeln").remove(self.rule(other.code))
		_, found, _ = self.run_main("USt")
		self.assertIn(
			f"USt 2026, rule {checked.code}: checked as {' '.join(checked.condition.split())}; {E50}: FeldAngegeben(E3999999)",
			found,
		)
		self.assertIn(
			f"USt 2026, rule {other.code}: checked by steuerbote/ustjahr/rules.py; {E50}: no such rule", found
		)

	def test_a_condition_written_otherwise_is_the_same_condition(self):
		checked = next(rule for rule in ustjahr_rules.LOCAL_RULES[2026] if " und " in rule.condition)
		self.rule(checked.code)["Prüfbedingung"] = checked.condition.replace(" und ", " Und\n ")
		self.assertLines(arguments=("USt",))


class ConjunctsTest(TestCase):
	def test_splits_at_und_outside_brackets_whatever_the_case_and_the_blanks(self):
		self.assertEqual(
			conjuncts("FeldAngegeben(E3000601) Und\n(Wert(E3000701) und [E3000801] > 0)"),
			{"feldangegeben(e3000601)", "(wert(e3000701)und[e3000801]>0)"},
		)

	def test_sorts_the_fields_of_a_list(self):
		self.assertEqual(
			conjuncts("KeinFeldAngegeben(E3000902, E3000901)"),
			conjuncts("keinfeldangegeben(E3000901,E3000902)"),
		)


class VorsatzTest(SyntheticTestCase):
	def test_finds_a_text_of_the_vorsatz_of_another_length_optional_or_missing(self):
		rows = self.jd().rows("Vorsatz", "Felder")
		self.jd().row("Vorsatz", "Felder", Name="AbsName").update({"Max. Länge": "40", "Pflichtfeld": "Nein"})
		rows.remove(self.jd().row("Vorsatz", "Felder", Name="Copyright"))
		self.jd().row("Vorsatz", "Felder", Name="AbsOrt")["Pflichtfeld"] = ""
		length, _ = vorsatz.TEXTS["AbsOrt"]
		self.assertLines(
			f"USt 2026, Vorsatz, AbsName: Max. Länge 45, Pflichtfeld Ja; {E50}: Max. Länge 40, Pflichtfeld Nein",
			f"USt 2026, Vorsatz, AbsOrt: Max. Länge {length}, Pflichtfeld Ja; {E50}: Max. Länge {length}, Pflichtfeld Nein",
			f"USt 2026, Vorsatz, Copyright: Max. Länge 50, Pflichtfeld Ja; {E50}: no such field",
			arguments=("USt",),
		)

	def test_finds_a_documentation_without_the_vorsatz(self):
		del self.jd(KST_2025).vordrucke["Vorsatz"]
		self.assertLines(f"KSt 2026, Vorsatz: its texts; {E30}: no Vordruck Vorsatz", arguments=("KSt",))


class PluginTest(SyntheticTestCase):
	def test_finds_a_datenart_the_matrix_has_no_row_of(self):
		self.documentation.matrix = [row for row in self.documentation.matrix if row[1] != "GewSt"]
		self.assertLines(
			"GewSt 2026, plugin: GewSt_2026, checkGewSt_2026; Datenartversionmatrix.ods: no row of GewSt_2026",
			arguments=("GewSt",),
		)

	def matrix(self, **rows: tuple[str, ...]) -> None:
		"""The matrix with the rows of some datenartVersion-Parameter replaced, such as USt_<Jahr>."""
		replaced = {name.replace("Jahr", "<Jahr>").replace("_6_9", "_6.9"): row for name, row in rows.items()}
		self.documentation.matrix = [replaced.get(row[3], row) for row in self.documentation.matrix]

	def test_finds_another_plugin_and_a_year_the_matrix_names_no_more(self):
		self.matrix(
			USt_Jahr=("ElsterErklaerung", "USt", "<Jahr>: 2021, 2022", "USt_<Jahr>", "checkUStE_<Jahr>"),
			KSt_30_Jahr=("ElsterErklaerung", "KSt", "<Jahr>: ab 2027", "KSt_30_<Jahr>", "checkKSt_<Jahr>"),
			Bilanz_6_9=("ElsterBilanz", "Bilanz", "Taxonomie 6.9", "Bilanz_6.9", ""),
		)
		self.assertLines(
			"USt 2026, plugin: USt_2026, checkUSt_2026; Datenartversionmatrix.ods: Plugin-Bibliothek checkUStE_2026",
			"USt 2026, plugin: for 2026; Datenartversionmatrix.ods: Jahr / Version <Jahr>: 2021, 2022",
			"KSt 2026, plugin: for 2026; Datenartversionmatrix.ods: Jahr / Version <Jahr>: ab 2027",
			"Bilanz 6.9, plugin: Bilanz_6.9, checkBilanz_6_9; Datenartversionmatrix.ods: Plugin-Bibliothek none",
			"Bilanz 6.9, plugin: for 6.9; Datenartversionmatrix.ods: Jahr / Version Taxonomie 6.9",
			arguments=("USt", "KSt", "Bilanz"),
		)

	def test_a_year_the_matrix_lists_or_names_in_no_known_way(self):
		self.matrix(
			USt_Jahr=("ElsterErklaerung", "USt", "<Jahr>: 2025, 2026", "USt_<Jahr>", "checkUSt_<Jahr>"),
			GewSt_Jahr=("ElsterErklaerung", "GewSt", "", "GewSt_<Jahr>", "checkGewSt_<Jahr>"),
		)
		self.assertLines(
			"GewSt 2026, plugin: for 2026; Datenartversionmatrix.ods: Jahr / Version none",
			arguments=("USt", "GewSt"),
		)


class UStYearInTheMakingTest(SyntheticTestCase):
	def test_compares_the_latest_data_with_the_documentation_of_a_new_year(self):
		self.documentation.jahresdokumentationen[ust(2027)] = self.documentation.jahresdokumentationen.pop(
			UST_2026
		)
		self.documentation.schemas[ust(2027)] = self.documentation.schemas.pop(UST_2026) | {"version": "2027"}
		self.assertLines(
			"USt 2027 is missing in YEARS of steuerbote/ustjahr/years.py, CATALOGUES of steuerbote/ustjahr/form.py, "
			"LOCAL_RULES of steuerbote/ustjahr/rules.py, LEFT_TO_ERIC of steuerbote/ustjahr/rules.py, ROLE_FIELDS of "
			"steuerbote/ustjahr/defaults.py, ANNUAL_ACCOUNTS of steuerbote/ustjahr/defaults.py, REVISIONS of "
			"steuerbote/ustjahr/defaults.py, SCHEMAS of steuerbote/elster/ust2a_xml.py; the latest data take its place:",
			f"USt 2027, source: {E50} (Versionslabel 9.0); Jahresdokumentation_E50_2027.ods: Versionslabel 9.0",
			"USt 2027, version: 2026; E50-2027.xsd: 2027",
			arguments=("USt", "2027"),
		)


class IncomeTaxTest(SyntheticTestCase):
	def rule(self, code: str, kind=KST_2025) -> dict[str, str]:
		(row,) = (
			row
			for kinds in self.jd(kind).vordrucke.values()
			for row in kinds.get("Regeln", [])
			if row["Fehlercode"] == code
		)
		return row

	def lines(self, check: IncomeTax, directory: Path | None = None) -> list[str]:
		return list(check.check(self.documentation.write(directory or self.directory), 2026))

	def test_finds_a_term_the_prüfbedingung_of_a_rule_lacks(self):
		row = self.rule("8900331")
		row["Prüfbedingung"] = row["Prüfbedingung"].replace("0.15", "0.14")
		self.assertLines(
			f"KSt 2026, rule 8900331 of ZVE: Abrunden([E8007504]*0.15); {E30}: not in its Prüfbedingung",
			arguments=("KSt",),
		)

	def test_finds_a_rule_that_is_gone_there_twice_or_whose_vordruck_is_gone(self):
		self.jd(KST_2025).rows("ZVE", "Regeln").remove(self.rule("8900331"))
		self.jd(KST_2025).rows("Z", "Regeln").append(dict(self.rule("8900204")))
		del self.jd(KST_2025).vordrucke["KSt1F"]
		_, found, _ = self.run_main("KSt")
		self.assertIn(
			f"KSt 2026, rule 8900331 of ZVE: computed in steuerbote/kst/chain.py; {E30}: no such rules", found
		)
		self.assertIn(
			f"KSt 2026, rule 8900204 of Z: computed in steuerbote/kst/losses.py; {E30}: 2 such rules", found
		)
		self.assertIn(
			f"KSt 2026, rule 8920021 of KSt1F: computed in steuerbote/kst/einlagekonto.py; {E30}: no Vordruck KSt1F",
			found,
		)

	def test_compares_a_provisional_year_with_the_newest_jahresdokumentation_up_to_it(self):
		newer = agreeing.income_tax_jahresdokumentation(KST_CHECK, 2026, "1.0")
		self.documentation.jahresdokumentationen[kst(2026)] = newer
		self.documentation.schemas[kst(2026)] = agreeing.income_tax_schema(KST_CHECK, 2026)
		self.documentation.jahresdokumentationen[kst(2027)] = Documented(information=["Einstellungen"])
		row = next(row for row in newer.rows("ZVE", "Regeln") if row["Fehlercode"] == "8900331")
		row["Prüfbedingung"] = "[E8007502] != Abrunden([E8007504] * 0.14)"
		self.assertLines(
			"KSt 2026, Jahresdokumentation: Jahresdokumentation_E30_2025.ods, provisionally; "
			"Datenarten/ElsterErklaerung/KSt/Jahresdokumentation: Jahresdokumentation_E30_2026.ods, the newest up to 2026",
			"KSt 2026, rule 8900331 of ZVE: Abrunden([E8007504]*0.15); Jahresdokumentation_E30_2026.ods: not in its "
			"Prüfbedingung",
			"KSt 2026, source: Jahresdokumentation_E30_2025.ods, Versionslabel 7.0, provisionally for 2026; "
			"Jahresdokumentation_E30_2026.ods: Versionslabel 1.0",
			arguments=("KSt", "2026"),
		)

	def test_a_provisional_year_needs_a_jahresdokumentation_up_to_it(self):
		del self.documentation.jahresdokumentationen[GEWST_2025]
		code, found, errors = self.run_main("GewSt")
		self.assertEqual((code, found), (2, []))
		self.assertIn(
			"Datenarten/ElsterErklaerung/GewSt/Jahresdokumentation holds no Jahresdokumentation up to 2026",
			errors,
		)

	def test_a_year_in_the_making_compares_the_latest_data_with_the_newest_jahresdokumentation(self):
		self.assertLines(
			"GewSt 2027 is missing in YEARS of steuerbote/gewst/years.py, CATALOGUES of steuerbote/gewst/form.py, "
			"RECHTSFORMEN of steuerbote/gewst/form.py, SCHEMAS of steuerbote/elster/gewst_xml.py; the latest data take "
			"its place:",
			arguments=("GewSt", "2027"),
		)

	def test_a_final_year_takes_its_own_jahresdokumentation(self):
		final = replace(kst_years.YEARS[2026], documentation_year=2026, provisional=False)
		check = replace(KST_CHECK, years=MappingProxyType({2026: final}))
		own = agreeing.income_tax_jahresdokumentation(KST_CHECK, 2026, "1.0")
		self.documentation.jahresdokumentationen[kst(2026)] = own
		self.documentation.schemas[kst(2026)] = agreeing.income_tax_schema(KST_CHECK, 2026)
		self.assertEqual(
			self.lines(check),
			[
				"KSt 2026, source: Jahresdokumentation_E30_2025.ods, Versionslabel 7.0, provisionally for 2026; "
				"Jahresdokumentation_E30_2026.ods: Versionslabel 1.0"
			],
		)
		del self.documentation.jahresdokumentationen[kst(2026)]
		with self.assertRaisesRegex(DocumentationError, "Jahresdokumentation_E30_2026.ods cannot be read"):
			self.lines(check, self.directory / "ohne")

	def test_compares_the_catalogue_of_kst_with_its_jahresdokumentation(self):
		field_ = next(field_ for field_ in KST_CHECK.catalogues[2026].fields if field_.kennzahl)
		kennzahl = field_.kennzahl.rpartition(".")[2]
		row = next(
			row
			for row in self.jd(KST_2025).rows(field_.form, "Kennzahlen")
			if row["Feldname"].endswith(field_.feldkennung)
		)
		row["Sachbereich"] = "99"
		self.assertLines(
			f"KSt 2026, field {field_.feldkennung}: Kennzahl {field_.kennzahl}; {E30}: Kennzahl 99.{kennzahl}",
			arguments=("KSt",),
		)

	def test_finds_a_vordruck_without_its_indexfeld_and_a_context_that_repeats_otherwise(self):
		rows = self.jd(KST_2025).rows("GK", "Felder")
		rows.remove(self.jd(KST_2025).row("GK", "Felder", Name="WJ"))
		self.documentation.schemas[KST_2025]["vordrucke"]["GK"].pop(0)
		occurs = self.documentation.schemas[KST_2025]["occurs"]
		occurs["KSt1/AE/Einzel"] = "98"
		del occurs["WA/AE/Einzel"]
		self.assertLines(
			"KSt 2026, context KSt1/AE/Einzel: repeats up to 99; E30-2025.xsd: repeats up to 98",
			"KSt 2026, context WA/AE/Einzel: repeats up to 99; E30-2025.xsd: does not repeat",
			f"KSt 2026, Indexfeld: GK, KSt1F; {E30}: KSt1F",
			arguments=("KSt",),
		)

	def test_finds_rechtsformen_of_other_categories_and_a_type_the_documentation_names_otherwise(self):
		(types,) = self.jd(KST_2025).others["Benutzerdefinierte Typen"]
		types["Format"] = (
			types["Format"]
			.replace("[Rechtsform 370] RF_Gruppe: 1", "[Rechtsform 370] RF_Gruppe: 2")
			.replace(" - 350 ", " - 351 ")
		)
		self.jd(GEWST_2025).others["Benutzerdefinierte Typen"][0]["Version"] = "3"
		self.assertLines(
			f"KSt 2026, RECHTSFORM_KOERPERSCHAFTEN_V3, 350: NurG 1, RF_Gruppe 1; {E30}: no such Rechtsform",
			f"KSt 2026, RECHTSFORM_KOERPERSCHAFTEN_V3, 370: NurG 1, RF_Gruppe 1; {E30}: NurG 1, RF_Gruppe 2",
			"GewSt 2026, RECHTSFORM_GEWERBESTEUER_V2: the categories of the Rechtsformen; "
			"Jahresdokumentation_E20_2025.ods: no type RECHTSFORM_GEWERBESTEUER_V2 of version 2",
			arguments=("KSt", "GewSt"),
		)

	def test_the_rules_of_gewst_come_from_its_chain(self):
		row = self.rule("40954", GEWST_2025)
		row["Prüfbedingung"] = "[E4051501]!=Abrunden(0.9*[E4051201]))"
		self.assertLines(
			"GewSt 2026, rule 40954 of BEG: [E4051501]!=Abrunden(0.95*[E4051201])); Jahresdokumentation_E20_2025.ods: "
			"not in its Prüfbedingung",
			arguments=("GewSt",),
		)


class BilanzTest(SyntheticTestCase):
	def test_checks_the_version_of_the_fiscal_year_of_a_year(self):
		self.documentation.matrix.remove(
			("ElsterBilanz", "Bilanz", "HGB-Taxonomie 6.9", "Bilanz_6.9", "checkBilanz_6_9")
		)
		self.assertLines(
			"Bilanz 6.9, plugin: Bilanz_6.9, checkBilanz_6_9; Datenartversionmatrix.ods: no row of Bilanz_6.9",
			arguments=("Bilanz", "2026"),
		)

	def test_a_year_without_its_taxonomy_takes_the_versions_the_letters_allow(self):
		self.assertLines(
			"Bilanz 2025 is missing in BILANZ_TAXONOMIES of steuerbote/eric/releases.py; the latest data take its place:",
			arguments=("Bilanz", "2025"),
		)

	def test_names_a_fiscal_year_no_version_serves(self):
		self.assertLines(
			"Bilanz 2028 is missing in BILANZ_TAXONOMIES of steuerbote/eric/releases.py; the latest data take its place:",
			"Bilanz 2028: no HGB-Taxonomie of TAXONOMIES of steuerbote/xbrl/versions.py for the fiscal year; "
			"Datenartversionmatrix.ods: the newest is 6.9",
			arguments=("Bilanz", "2028"),
		)
		self.documentation.matrix = [row for row in self.documentation.matrix if row[1] != "Bilanz"]
		_, found, _ = self.run_main("Bilanz", "2028")
		self.assertEqual(found[-1].rpartition(": ")[2], "the newest is none")

	def test_compares_a_new_version_with_its_documentation(self):
		self.documentation.jahresdokumentationen[bilanz("6.11")] = agreeing.bilanz_jahresdokumentation("6.10")
		self.assertLines(
			"Bilanz 6.11 is missing in TAXONOMIES of steuerbote/xbrl/versions.py; the latest data take its place:",
			"Bilanz 6.11, plugin: Bilanz_6.11, checkBilanz_6_11; Datenartversionmatrix.ods: no row of Bilanz_6.11",
			arguments=("6.11",),
		)

	def test_names_the_versions_the_documentation_holds_beyond_taxonomies(self):
		self.documentation.jahresdokumentationen[bilanz("6.10")] = agreeing.bilanz_jahresdokumentation("6.10")
		self.documentation.jahresdokumentationen[bilanz("6.11")] = agreeing.bilanz_jahresdokumentation("6.10")
		self.documentation.matrix.extend(
			(
				("ElsterBilanz", "Bilanz", "HGB-Taxonomie 6.10", "Bilanz_6.10", "checkBilanz_6_10"),
				("ElsterBilanz", "Bilanz", "HGB-Taxonomie 7.0", "Bilanz_7.0", "checkBilanz_7_0"),
				("ElsterBilanz", "Bilanz", "HGB-Taxonomie 6.11", "Bilanz_6.11", "checkBilanz_6_11"),
			)
		)
		self.assertLines(
			"Bilanz 6.11: not in TAXONOMIES of steuerbote/xbrl/versions.py; Jahresdokumentation_Bilanz_Taxonomie_6_11.ods: "
			"documented",
			"Bilanz 7.0: not in TAXONOMIES of steuerbote/xbrl/versions.py; Datenartversionmatrix.ods: documented",
			arguments=("Bilanz",),
		)

	def test_compares_6_10_with_its_documentation(self):
		"""The documentation of ERiC 45.1.5.0 holds Jahresdokumentation_Bilanz_Taxonomie_6_10.ods and the row of
		Bilanz_6.10 in its matrix."""
		self.documentation.jahresdokumentationen[bilanz("6.10")] = agreeing.bilanz_jahresdokumentation("6.10")
		self.documentation.matrix.append(
			("ElsterBilanz", "Bilanz", "HGB-Taxonomie 6.10", "Bilanz_6.10", "checkBilanz_6_10")
		)
		self.assertLines(arguments=("6.10",))
		self.assertLines(arguments=("Bilanz", "2027"))
		self.assertLines(arguments=("Bilanz",))

	def test_leaves_a_version_newer_than_the_documentation_to_a_request(self):
		"""The documentation of ERiC 44.3.6.0 ends with the taxonomy 6.9 (Entwicklerhandbuch, Tabelle 9-19): without a
		version the command leaves 6.10 out, and named it ends with 2 for its missing Jahresdokumentation."""
		self.assertLines(arguments=("Bilanz",))
		code, found, errors = self.run_main("6.10")
		self.assertEqual((code, found), (2, []))
		self.assertIn("Jahresdokumentation_Bilanz_Taxonomie_6_10.ods", errors)

	def test_leaves_out_nothing_where_the_documentation_documents_no_version(self):
		del self.documentation.jahresdokumentationen[BILANZ_6_9]
		self.documentation.matrix = [row for row in self.documentation.matrix if row[1] != "Bilanz"]
		code, _, errors = self.run_main("Bilanz")
		self.assertEqual(code, 2)
		for name in (
			"Jahresdokumentation_Bilanz_Taxonomie_6_9.ods",
			"Jahresdokumentation_Bilanz_Taxonomie_6_10.ods",
		):
			self.assertIn(name, errors)

	def test_leaves_out_nothing_where_the_matrix_cannot_be_read(self):
		root = self.written()
		(root / "Datenartversionmatrix.ods").unlink()
		stdout, stderr = io.StringIO(), io.StringIO()
		self.assertEqual(main([str(root), "Bilanz"], stdout, stderr), 2)
		self.assertIn("Jahresdokumentation_Bilanz_Taxonomie_6_10.ods", stderr.getvalue())

	def test_compares_the_rules_a_module_of_the_e_bilanz_computes(self):
		def expected_rules(version: str) -> tuple[RuleExpectation, ...]:
			return (
				RuleExpectation("170205010", "Kontext", ("[gaap:bs.ass]!=[gaap:bs.eqLiab]",)),
				RuleExpectation("170205015", "Header", (f"version{version}",)),
			)

		with mock.patch.object(yearcheck, "BILANZ_EXPECTING", (expected_rules,)):
			self.assertLines(
				"Bilanz 6.9, rule 170205015 of Header: version6.9; Jahresdokumentation_Bilanz_Taxonomie_6_9.ods: "
				"not in its Prüfbedingung",
				arguments=("Bilanz",),
			)


class HelpersTest(TestCase):
	def test_names_the_tables_a_key_is_missing_in(self):
		tables = (Table("YEARS", "years.py", {2026: None}), Table("TAXONOMIES", "versions.py", ("6.9",)))
		self.assertEqual(missing(2027, tables), ("YEARS of years.py", "TAXONOMIES of versions.py"))
		self.assertEqual(missing("6.9", tables), ("YEARS of years.py",))

	def test_takes_the_latest_entry_for_a_year_in_the_making(self):
		self.assertEqual(
			(latest({2025: "a", 2026: "b"}, 2025), latest({2025: "a", 2026: "b"}, 2027)), ("a", "b")
		)


class DocumentationTest(TestCase):
	"""Every Datenart against the ERiC documentation; skipped without it, see eric_schema.py."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.documentation = eric_schema.documentation()

	def run_main(self, *arguments: str) -> tuple[int, str, str]:
		stdout, stderr = io.StringIO(), io.StringIO()
		code = main([str(self.documentation), *arguments], stdout, stderr)
		return code, stdout.getvalue(), stderr.getvalue()

	def test_every_datenart_agrees_with_its_documentation(self):
		self.assertEqual(self.run_main(), (0, "", ""))

	def test_finds_deliberately_altered_data(self):
		later = replace(kst_years.YEARS[2026], rate=kst_years.statutory_rate(2028))
		catalogue = dict(kennzahlen.CATALOGUES)
		catalogue[2026] = MappingProxyType({**catalogue[2026], "66": replace(catalogue[2026]["66"], line=37)})
		with (
			mock.patch("steuerbote.kst.chain.year_of", return_value=later),
			mock.patch.object(ustva_yearcheck, "CATALOGUES", MappingProxyType(catalogue)),
		):
			code, stdout, _ = self.run_main("KSt", "UStVA", "2026")
		self.assertEqual(
			(code, stdout.splitlines()),
			(
				1,
				[
					"KSt 2026, rule 8900331 of ZVE: Abrunden([E8007504]*0.14); Jahresdokumentation_E30_2025.ods: not in "
					"its Prüfbedingung",
					"UStVA 2026, catalogue 2026, Kz 66: line 37; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 38",
				],
			),
		)

	def test_runs_as_a_command_that_prints_nothing_for_44_3_6_0(self):
		completed = subprocess.run(  # noqa: S603 - this interpreter, a fixed module and the documentation of the test
			[sys.executable, "-m", "steuerbote.jahresmeldung.yearcheck", str(self.documentation)],
			capture_output=True,
			cwd=APP_ROOT,
			timeout=300,
			check=False,
		)
		self.assertEqual((completed.returncode, completed.stdout, completed.stderr), (0, b"", b""))


class BetaDocumentationTest(TestCase):
	"""The UStVA against the documentation of the beta ERiC 45.1.5.0, which holds 2026 and 2027; skipped with a
	documentation that holds no UStVA 2027, see eric_schema.ustva_year."""

	def test_the_ustva_and_form_ust_1_h_agree_with_it_in_2026_and_2027(self):
		stdout, stderr = io.StringIO(), io.StringIO()
		code = main([str(eric_schema.ustva_year(2027)), "UStVA"], stdout, stderr)
		self.assertEqual((code, stdout.getvalue(), stderr.getvalue()), (0, "", ""))
