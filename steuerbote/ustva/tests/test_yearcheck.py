"""The year check: the data of a year against its Jahresdokumentation, its schema and the Datenartversionmatrix.

The tests without the ERiC documentation write one that agrees with the data of 2026 (eric_documentation.py) and
change one fact in it or in the data; DocumentationTest checks every year of the year table against the ERiC
documentation itself.
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

from steuerbote.dauerfrist.form import Context
from steuerbote.elster.tests import eric_schema
from steuerbote.ustva import kennzahlen, yearcheck
from steuerbote.ustva.documentation import read
from steuerbote.ustva.kennzahlen import Kind
from steuerbote.ustva.tests import eric_documentation
from steuerbote.ustva.yearcheck import Data, Difference, check, data_for, differences, main, missing
from steuerbote.ustva.years import LATEST_YEAR, YEARS

APP_ROOT = Path(__file__).resolve().parents[3]
DF = Context.DAUERFRISTVERLAENGERUNG.value
SVZ = Context.UMSATZSTEUERSONDERVORAUSZAHLUNG.value
USTVA = "Umsatzsteuervoranmeldung"
UNKNOWN_YEAR = LATEST_YEAR + 1


def kennzahl(data: Data, number: str, **changes: object) -> Data:
	"""The data with one Kennzahl of the catalogue changed."""
	catalogue = dict(data.catalogue)
	catalogue[number] = replace(catalogue[number], **changes)
	return replace(data, catalogue=MappingProxyType(catalogue))


class SyntheticTestCase(TestCase):
	def setUp(self):
		self.directory = Path(tempfile.mkdtemp(prefix="steuerbote-yearcheck-"))
		self.addCleanup(shutil.rmtree, self.directory)
		self.data = data_for(2026)
		self.documented = eric_documentation.documented(self.data)

	def written(self) -> Path:
		return eric_documentation.write(self.directory, self.documented)

	def assertFound(self, *lines: str, data: Data | None = None) -> None:
		found = differences(read(self.written(), self.documented.year), data or self.data)
		self.assertEqual([str(difference) for difference in found], list(lines))

	def elements(self, context: str) -> list[tuple[str, str]]:
		return self.documented.contexts[context]

	def without(self, rows: list[dict[str, str]], name: str) -> None:
		rows[:] = [row for row in rows if row["Name"] != name]


class AgreementTest(SyntheticTestCase):
	def test_finds_nothing_where_the_documentation_says_what_the_data_say(self):
		self.assertFound()

	def test_checks_a_year_in_the_directory_the_documentation_was_unzipped_into(self):
		self.written()
		self.assertEqual(check(self.directory, 2026), ())

	def test_a_difference_names_both_sides_and_the_file(self):
		difference = Difference(
			"catalogue 2026, Kz 66", "line 38", "Jahresdokumentation_UStVA_2026.ods", "Vordruckzeile 37"
		)
		self.assertEqual(
			str(difference),
			"catalogue 2026, Kz 66: line 38; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 37",
		)


class CatalogueFieldsTest(SyntheticTestCase):
	def test_finds_a_kennzahl_on_another_line(self):
		self.assertFound(
			"catalogue 2026, Kz 66: line 37; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 38",
			data=kennzahl(self.data, "66", line=37),
		)

	def test_finds_a_field_without_vordruckzeile(self):
		self.documented.field(USTVA, "Kz66")["Vordruckzeile"] = ""
		self.assertFound(
			"catalogue 2026, Kz 66: line 38; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile none"
		)

	def test_finds_a_kennzahl_of_another_kind(self):
		self.documented.field(USTVA, "Kz66")["Formatkennzeichen"] = "N"
		self.assertFound(
			"catalogue 2026, Kz 66: kind tax; Jahresdokumentation_UStVA_2026.ods: Formatkennzeichen N"
		)

	def test_finds_a_formatkennzeichen_the_writer_does_not_take(self):
		self.documented.field(USTVA, "Kz10")["Formatkennzeichen"] = "X"
		self.assertFound(
			"catalogue 2026, Kz 10: kind flag; Jahresdokumentation_UStVA_2026.ods: Formatkennzeichen X"
		)
		self.documented.field(USTVA, "Kz10")["Formatkennzeichen"] = ""
		self.assertFound(
			"catalogue 2026, Kz 10: kind flag; Jahresdokumentation_UStVA_2026.ods: Formatkennzeichen none"
		)

	def test_finds_a_kennzahl_the_year_dropped_and_one_it_added(self):
		self.documented.field(USTVA, "Kz500")["Name"] = "Kz23"
		self.assertFound(
			"catalogue 2026, Kz 23: not in the catalogue; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 55",
			"catalogue 2026, Kz 500: line 55; Jahresdokumentation_UStVA_2026.ods: no field Kz500",
		)

	def test_the_hersteller_id_is_no_kennzahl_of_the_form(self):
		self.documented.field(USTVA, "Kz09")["Vordruckzeile"] = "9"
		self.assertFound()


class CatalogueRulesTest(SyntheticTestCase):
	def test_finds_a_pair_no_rule_files_together(self):
		self.without(self.documented.rules, "UStVA_Kz35_36_Gemeinsam")
		self.assertFound(
			"catalogue 2026, Kz 35 and Kz 36: a base and its tax; Jahresdokumentation_UStVA_2026.ods: "
			"no rule files them together"
		)

	def test_finds_kennzahlen_a_rule_files_together_that_are_no_pair(self):
		self.documented.rules.append(
			{
				"Kontext": f"Steuerfall/{USTVA}",
				"Name": "UStVA_Kz45_21_Gemeinsam",
				"Fehlercode": "110085098",
				"Prüfbedingung": "FelderNichtGemeinsamAngegeben( Kz45 ,Kz21 )",
				"Regelart": "Fehler",
			}
		)
		self.assertFound(
			"catalogue 2026, Kz 21 and Kz 45: no base and its tax; Jahresdokumentation_UStVA_2026.ods: "
			"filed together, rule 110085098 UStVA_Kz45_21_Gemeinsam"
		)

	def test_finds_kz83_without_its_rule(self):
		self.without(self.documented.rules, "UStVA_Kz83_Pflichtfeld")
		self.assertFound(
			"catalogue 2026, Kz 83: always written; Jahresdokumentation_UStVA_2026.ods: no rule makes it mandatory"
		)

	def test_finds_another_mandatory_kennzahl(self):
		self.documented.rules.append(
			{
				"Kontext": f"Steuerfall/{USTVA}",
				"Name": "UStVA_Kz81_Pflichtfeld",
				"Fehlercode": "110085097",
				"Prüfbedingung": "FeldNichtAngegeben(Kz81) UND KontextAngegeben(RegelKontext)",
				"Regelart": "Fehler",
			}
		)
		self.assertFound(
			"catalogue 2026, Kz 81: written with an amount only; Jahresdokumentation_UStVA_2026.ods: "
			"mandatory, rule 110085097 UStVA_Kz81_Pflichtfeld"
		)

	def test_reads_the_rules_of_its_context_only(self):
		self.documented.rule("UStVA_Kz83_Pflichtfeld")["Kontext"] = "Steuerfall"
		self.assertFound(
			"catalogue 2026, Kz 83: always written; Jahresdokumentation_UStVA_2026.ods: no rule makes it mandatory"
		)


class CatalogueSchemaTest(SyntheticTestCase):
	def test_finds_a_kennzahl_without_element_and_an_element_without_kennzahl(self):
		elements = self.elements(USTVA)
		elements[:] = [(name, type_name) for name, type_name in elements if name != "Kz66"] + [
			("Kz99", "String_SType")
		]
		self.assertFound(
			"catalogue 2026, Kz 66: line 38; UStVA-2026.xsd: no element Kz66",
			"catalogue 2026, Kz 99: not in the catalogue; UStVA-2026.xsd: element of type String_SType",
			"schema 2026, Umsatzsteuervoranmeldung, Kz66: an element; UStVA-2026.xsd: no such element",
			"schema 2026, Umsatzsteuervoranmeldung, Kz99: no such element; UStVA-2026.xsd: an element",
		)

	def test_finds_an_element_of_another_kind(self):
		elements = self.elements(USTVA)
		elements[:] = [(name, "GanzzahlOhneFuehrNull_SType" if name == "Kz83" else t) for name, t in elements]
		self.assertFound("catalogue 2026, Kz 83: kind tax; UStVA-2026.xsd: type GanzzahlOhneFuehrNull_SType")
		elements[:] = [(name, "String_SType" if name == "Kz83" else t) for name, t in elements]
		self.assertFound("catalogue 2026, Kz 83: kind tax; UStVA-2026.xsd: type String_SType")

	def test_finds_a_schema_without_the_context(self):
		del self.documented.contexts[USTVA]
		self.assertFound(
			"catalogue 2026: its Kennzahlen; UStVA-2026.xsd: no element Umsatzsteuervoranmeldung",
			"schema 2026, Umsatzsteuervoranmeldung: its elements; UStVA-2026.xsd: no element Umsatzsteuervoranmeldung",
		)


class SchemaTest(SyntheticTestCase):
	def test_finds_another_namespace_and_version(self):
		self.documented.namespace = "http://finkonsens.de/elster/elsteranmeldung/ustva/v2099"
		self.documented.version = "2099"
		self.assertFound(
			"schema 2026, namespace: http://finkonsens.de/elster/elsteranmeldung/ustva/v2026; UStVA-2026.xsd: "
			"http://finkonsens.de/elster/elsteranmeldung/ustva/v2099",
			"schema 2026, version: 2026; UStVA-2026.xsd: 2099",
		)

	def test_finds_a_schema_without_namespace_and_version(self):
		root = self.written()
		xsd = root / "Datenarten/ElsterAnmeldung/UStVA/Schema/2026/UStVA-2026.xsd"
		text = xsd.read_text(encoding="utf-8")
		text = text.replace(f' targetNamespace="{self.data.schema.namespace}"', "").replace(
			' fixed="2026"', ""
		)
		xsd.write_text(text, encoding="utf-8")
		found = differences(read(root, 2026), self.data)
		self.assertEqual(
			[str(difference) for difference in found],
			[
				f"schema 2026, namespace: {self.data.schema.namespace}; UStVA-2026.xsd: none",
				"schema 2026, version: 2026; UStVA-2026.xsd: none",
			],
		)

	def test_finds_elements_in_another_order(self):
		elements = self.elements(USTVA)
		names = [name for name, _ in elements]
		i, j = names.index("Kz93"), names.index("Kz90")
		elements[i], elements[j] = elements[j], elements[i]
		self.assertFound(
			"schema 2026, Umsatzsteuervoranmeldung, order: Kz93 before Kz90; UStVA-2026.xsd: Kz90 before Kz93"
		)

	def test_finds_a_kennzahl_without_sign_whose_type_takes_one(self):
		elements = self.elements(USTVA)
		elements[:] = [
			(name, "DezimalzahlOhneFuehrNull_SType" if name == "Kz37" else t) for name, t in elements
		]
		self.assertFound(
			"schema 2026, Kz 37: without sign; UStVA-2026.xsd: type DezimalzahlOhneFuehrNull_SType"
		)

	def test_finds_a_sign_the_formatkennzeichen_does_not_allow_or_does(self):
		self.documented.field(USTVA, "Kz50")["Formatkennzeichen"] = "N"
		self.documented.field(USTVA, "Kz81")["Formatkennzeichen"] = "U"
		self.assertFound(
			"schema 2026, Kz 50: without sign; Jahresdokumentation_UStVA_2026.ods: Formatkennzeichen N",
			"schema 2026, Kz 81: with sign; Jahresdokumentation_UStVA_2026.ods: Formatkennzeichen U",
		)

	def test_finds_a_kennzahl_whose_formatkennzeichen_is_missing(self):
		self.documented.field(USTVA, "Kz37")["Formatkennzeichen"] = ""
		self.assertFound(
			"catalogue 2026, Kz 37: kind tax; Jahresdokumentation_UStVA_2026.ods: Formatkennzeichen none",
			"schema 2026, Kz 37: without sign; Jahresdokumentation_UStVA_2026.ods: Formatkennzeichen none",
		)


class LayoutTest(SyntheticTestCase):
	def test_finds_each_column_of_a_field_that_differs(self):
		self.documented.field(SVZ, "Kz38")["Max. Länge"] = "14"
		self.documented.field(DF, "Kz09")["Format als regulärer Ausdruck"] = "^(?=.{5,5}$)[0-9]+"
		self.documented.field(DF, "Jahr")["Vordruckzeile"] = "1"
		self.documented.field(DF, "WIdNr")["Formatkennzeichen"] = "O"
		self.documented.field(DF, "Steuernummer")["Min. Länge"] = ""
		self.assertFound(
			"layout 2026, Dauerfristverlaengerung, Jahr: Vordruckzeile none; Jahresdokumentation_UStVA_2026.ods: "
			"Vordruckzeile 1",
			"layout 2026, Dauerfristverlaengerung, Steuernummer: Min. Länge 13; Jahresdokumentation_UStVA_2026.ods: "
			"Min. Länge none",
			"layout 2026, Dauerfristverlaengerung, WIdNr: Formatkennzeichen C; Jahresdokumentation_UStVA_2026.ods: "
			"Formatkennzeichen O",
			"layout 2026, Dauerfristverlaengerung, Kz09: Format als regulärer Ausdruck "
			r"^(?=.{5,95}$)([0-9]{5})|([0-9]{5}\*.{0,85}\*.{0,85}\*.{0,85}\*.{0,85}\*.{0,85}); "
			"Jahresdokumentation_UStVA_2026.ods: Format als regulärer Ausdruck ^(?=.{5,5}$)[0-9]+",
			"layout 2026, Umsatzsteuersondervorauszahlung, Kz38: Max. Länge 13; Jahresdokumentation_UStVA_2026.ods: "
			"Max. Länge 14",
		)

	def test_finds_a_field_the_year_dropped_and_one_it_added(self):
		self.documented.field(DF, "Kz500")["Name"] = "Kz23"
		self.assertFound(
			"layout 2026, Dauerfristverlaengerung, Kz500: an element; Jahresdokumentation_UStVA_2026.ods: "
			"no such element",
			"layout 2026, Dauerfristverlaengerung, Kz23: no such element; Jahresdokumentation_UStVA_2026.ods: "
			"an element",
		)

	def test_finds_fields_in_another_order(self):
		fields = self.documented.fields
		kz26, kz29 = self.documented.field(SVZ, "Kz26"), self.documented.field(SVZ, "Kz29")
		i, j = fields.index(kz26), fields.index(kz29)
		fields[i], fields[j] = kz29, kz26
		self.assertFound(
			"layout 2026, Umsatzsteuersondervorauszahlung, order: Kz26 before Kz29; "
			"Jahresdokumentation_UStVA_2026.ods: Kz29 before Kz26"
		)

	def test_finds_a_context_without_fields(self):
		self.documented.fields[:] = [
			row for row in self.documented.fields if row["Kontext"] != f"Steuerfall/{DF}"
		]
		self.assertFound(
			"layout 2026, Dauerfristverlaengerung: its fields; Jahresdokumentation_UStVA_2026.ods: "
			"no field of the context"
		)

	def test_finds_the_elements_of_a_context_in_the_schema(self):
		self.without_element(DF, "Kz500_Begruendung")
		del self.documented.contexts[SVZ]
		self.assertFound(
			"layout 2026, Dauerfristverlaengerung, Kz500_Begruendung: an element; UStVA-2026.xsd: no such element",
			"layout 2026, Umsatzsteuersondervorauszahlung: its elements; UStVA-2026.xsd: "
			"no element Umsatzsteuersondervorauszahlung",
		)

	def without_element(self, context: str, name: str) -> None:
		elements = self.elements(context)
		elements[:] = [element for element in elements if element[0] != name]

	def test_finds_rules_the_year_dropped_added_or_changed(self):
		self.without(self.documented.rules, "Svz_Kz29_ohne_Kz10")
		self.documented.rule("Kz26_Hinweis", f"Steuerfall/{SVZ}")["Fehlercode"] = "11085199"
		self.documented.rules.append(
			{
				"Kontext": f"Steuerfall/{DF}",
				"Name": "Df_Neu",
				"Fehlercode": "110085000",
				"Prüfbedingung": "KontextAngegeben(RegelKontext)",
				"Regelart": "Hinweis",
			}
		)
		self.assertFound(
			"layout 2026, rule Df_Neu of Steuerfall/Dauerfristverlaengerung: no such rule; "
			"Jahresdokumentation_UStVA_2026.ods: 110085000, Hinweis",
			"layout 2026, rule Kz26_Hinweis of Steuerfall/Umsatzsteuersondervorauszahlung: 11085155, Hinweis; "
			"Jahresdokumentation_UStVA_2026.ods: 11085199, Hinweis",
			"layout 2026, rule Svz_Kz29_ohne_Kz10 of Steuerfall/Umsatzsteuersondervorauszahlung: 11085150, Fehler; "
			"Jahresdokumentation_UStVA_2026.ods: no such rule",
		)

	def test_a_rule_of_the_steuerfall_counts_when_it_names_a_context_of_the_form(self):
		self.documented.rule("UStVA_Df_oder_Svz", "Steuerfall")["Prüfbedingung"] = (
			"KontextAngegeben(Unternehmer)"
		)
		self.assertFound(
			"layout 2026, rule UStVA_Df_oder_Svz of Steuerfall: 110085099, Fehler; "
			"Jahresdokumentation_UStVA_2026.ods: no such rule"
		)


class DatenartVersionTest(SyntheticTestCase):
	def test_finds_another_datenart_version_or_plugin(self):
		self.documented.datenart("UStVA").update(
			{"datenartVersion-Parameter": "UStVA2_<Jahr>", "Plugin-Bibliothek": "checkUStVA2_<Jahr>"}
		)
		self.assertFound(
			"plugin 2026: UStVA_2026; Datenartversionmatrix.ods: datenartVersion-Parameter UStVA2_2026",
			"plugin 2026: checkUStVA_2026; Datenartversionmatrix.ods: Plugin-Bibliothek checkUStVA2_2026",
		)

	def test_finds_a_year_the_matrix_names_no_more(self):
		self.documented.datenart("UStVA")["Jahr / Version"] = "<Jahr>: ab 2027"
		self.assertFound(
			"plugin 2026: the year 2026; Datenartversionmatrix.ods: Jahr / Version <Jahr>: ab 2027"
		)
		self.documented.datenart("UStVA")["Jahr / Version"] = ""
		self.assertFound("plugin 2026: the year 2026; Datenartversionmatrix.ods: Jahr / Version none")

	def test_finds_a_matrix_without_the_rows(self):
		self.documented.datenart("UStVA")["Plugin-Bibliothek"] = ""
		self.assertFound("plugin 2026: checkUStVA_2026; Datenartversionmatrix.ods: Plugin-Bibliothek none")
		self.documented.datenart_versions[:] = [self.documented.datenart("LStA")]
		self.assertFound(
			"plugin 2026: checkUStVA_2026; Datenartversionmatrix.ods: no row of the Datenart UStVA",
			"ZMDO: no year, ZMDO, checkZMDO; Datenartversionmatrix.ods: no row of the Datenart ZMDO",
		)

	def test_finds_a_zmdo_of_a_year_or_version(self):
		self.documented.datenart("ZMDO").update(
			{"Jahr / Version": "<Version>: 6", "datenartVersion-Parameter": "ZMDO_6"}
		)
		self.assertFound(
			"ZMDO: no year, ZMDO, checkZMDO; Datenartversionmatrix.ods: <Version>: 6, ZMDO_6, checkZMDO"
		)


class YearInTheMakingTest(TestCase):
	def test_a_year_of_every_table_misses_nothing(self):
		for year in YEARS:
			with self.subTest(year=year):
				self.assertEqual(missing(year), ())
				self.assertEqual(data_for(year).catalogue_year, year)

	def test_names_every_table_a_new_year_is_missing_in(self):
		self.assertEqual(
			missing(UNKNOWN_YEAR),
			(
				"YEARS of steuerbote/ustva/years.py",
				"CATALOGUES of steuerbote/ustva/kennzahlen.py",
				"SCHEMAS of steuerbote/elster/ustva_xml.py",
				"LAYOUTS of steuerbote/dauerfrist/form.py",
			),
		)

	def test_takes_the_parts_of_the_latest_year_for_those_a_new_year_lacks(self):
		self.assertEqual(data_for(UNKNOWN_YEAR), data_for(LATEST_YEAR))
		with mock.patch.object(
			yearcheck,
			"CATALOGUES",
			MappingProxyType({**kennzahlen.CATALOGUES, UNKNOWN_YEAR: kennzahlen.KENNZAHLEN}),
		):
			data = data_for(UNKNOWN_YEAR)
			self.assertEqual(data.catalogue_year, UNKNOWN_YEAR)
			self.assertEqual(
				missing(UNKNOWN_YEAR)[1:],
				("SCHEMAS of steuerbote/elster/ustva_xml.py", "LAYOUTS of steuerbote/dauerfrist/form.py"),
			)
		self.assertEqual(data.schema.year, LATEST_YEAR)
		self.assertEqual(data.layout.year, LATEST_YEAR)


class CommandTest(SyntheticTestCase):
	def run_main(self, *arguments: str) -> tuple[int, str, str]:
		stdout, stderr = io.StringIO(), io.StringIO()
		code = main(list(arguments), stdout, stderr)
		return code, stdout.getvalue(), stderr.getvalue()

	def test_prints_nothing_for_years_that_agree_with_their_documentation(self):
		for year in YEARS:
			eric_documentation.write(self.directory, eric_documentation.documented(data_for(year)))
		self.assertEqual(self.run_main(str(self.directory), "2026"), (0, "", ""))
		self.assertEqual(self.run_main(str(self.directory)), (0, "", ""))

	def test_prints_each_difference_on_a_line_of_its_own(self):
		self.documented.field(USTVA, "Kz66")["Vordruckzeile"] = "37"
		self.documented.field(USTVA, "Kz61")["Vordruckzeile"] = "40"
		code, stdout, stderr = self.run_main(str(self.written()), "2026")
		self.assertEqual((code, stderr), (1, ""))
		self.assertEqual(
			stdout.splitlines(),
			[
				"catalogue 2026, Kz 61: line 39; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 40",
				"catalogue 2026, Kz 66: line 38; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 37",
			],
		)

	def test_compares_the_latest_data_with_the_documentation_of_a_new_year(self):
		self.documented = eric_documentation.documented(data_for(LATEST_YEAR), UNKNOWN_YEAR)
		code, stdout, _ = self.run_main(str(self.written()), str(UNKNOWN_YEAR))
		self.assertEqual(code, 1)
		self.assertEqual(
			stdout.splitlines(),
			[
				f"{UNKNOWN_YEAR} is missing in YEARS of steuerbote/ustva/years.py, CATALOGUES of "
				"steuerbote/ustva/kennzahlen.py, SCHEMAS of steuerbote/elster/ustva_xml.py, LAYOUTS of "
				"steuerbote/dauerfrist/form.py; the latest data take its place:",
				f"schema {LATEST_YEAR}, version: {LATEST_YEAR}; UStVA-{UNKNOWN_YEAR}.xsd: {UNKNOWN_YEAR}",
			],
		)

	def test_ends_with_2_when_the_documentation_of_a_year_is_missing(self):
		directory = str(self.written())
		code, stdout, stderr = self.run_main(directory, "2026", "2025")
		self.assertEqual((code, stdout), (2, ""))
		self.assertIn("Jahresdokumentation_UStVA_2025.ods cannot be read", stderr)
		self.assertEqual(self.run_main(str(self.directory / "leer"))[0], 2)

	def test_prints_what_it_found_before_the_documentation_ran_out(self):
		self.documented.field(USTVA, "Kz66")["Vordruckzeile"] = "37"
		code, stdout, _ = self.run_main(str(self.written()), "2026", "2025")
		self.assertEqual(code, 2)
		self.assertEqual(
			stdout, "catalogue 2026, Kz 66: line 38; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 37\n"
		)

	def test_refuses_what_is_no_year(self):
		with mock.patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit) as exited:
			main([str(self.directory), "zwanzig"])
		self.assertEqual(exited.exception.code, 2)

	def test_runs_as_a_module(self):
		with (
			mock.patch.object(sys, "argv", ["yearcheck", str(self.written()), "2026"]),
			mock.patch.object(sys, "stdout", io.StringIO()) as stdout,
			self.assertRaises(SystemExit) as exited,
		):
			runpy.run_path(yearcheck.__file__, run_name="__main__")
		self.assertEqual((exited.exception.code, stdout.getvalue()), (0, ""))


class DocumentationTest(TestCase):
	"""Every year of the year table against the ERiC documentation; skipped without it, see eric_schema.py."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.documentation = eric_schema.documentation()

	def test_every_year_agrees_with_its_documentation(self):
		for year in YEARS:
			with self.subTest(year=year):
				self.assertEqual([str(difference) for difference in check(self.documentation, year)], [])

	def test_finds_deliberately_altered_entries_of_the_catalogue(self):
		altered = kennzahl(kennzahl(data_for(2026), "66", line=37), "37", kind=Kind.BASE)
		self.assertEqual(
			[str(difference) for difference in differences(read(self.documentation, 2026), altered)],
			[
				"catalogue 2026, Kz 37: kind base; Jahresdokumentation_UStVA_2026.ods: Formatkennzeichen %",
				"catalogue 2026, Kz 66: line 37; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 38",
				"catalogue 2026, Kz 37: kind base; UStVA-2026.xsd: "
				"type DezimalzahlNichtNegOhneFuehrNull_MaxL14_MaxVK11_MinNK2_MaxNK2_SType",
			],
		)

	def test_the_command_names_an_altered_entry_of_the_catalogue(self):
		catalogue = dict(kennzahlen.CATALOGUES)
		catalogue[2026] = kennzahl(data_for(2026), "66", line=37).catalogue
		stdout = io.StringIO()
		with mock.patch.object(yearcheck, "CATALOGUES", MappingProxyType(catalogue)):
			code = main([str(self.documentation), "2026"], stdout, io.StringIO())
		self.assertEqual(
			(code, stdout.getvalue()),
			(1, "catalogue 2026, Kz 66: line 37; Jahresdokumentation_UStVA_2026.ods: Vordruckzeile 38\n"),
		)

	def test_runs_as_a_command_that_prints_nothing_for_2026(self):
		completed = subprocess.run(  # noqa: S603 - this interpreter, a fixed module and the documentation of the test
			[sys.executable, "-m", "steuerbote.ustva.yearcheck", str(self.documentation), "2026"],
			capture_output=True,
			cwd=APP_ROOT,
			timeout=120,
			check=False,
		)
		self.assertEqual((completed.returncode, completed.stdout, completed.stderr), (0, b"", b""))
