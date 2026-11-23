"""Reading the Jahresdokumentation and the schema of a year from the unzipped ERiC documentation."""

import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from unittest import TestCase, mock

from steuerbote.ustva.documentation import (
	FIELDS,
	RULES,
	USTVA,
	DocumentationError,
	find,
	jahresdokumentation_path,
	read,
	read_xsd,
	records,
	schema_path,
	sheets,
	tables,
)
from steuerbote.ustva.tests import eric_documentation
from steuerbote.ustva.yearcheck import data_for

NAMESPACES = (
	'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
	'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
	'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
)
# A sheet as LibreOffice writes one: repeated and covered cells, runs of blanks, a tab, a line break, a span, two
# paragraphs in a cell, an element between the cells that is none, an empty row, a short row, a row with more
# cells than heads and the outdated versions.
CONTENT = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content {NAMESPACES} office:version="1.2"><office:body><office:spreadsheet>
<table:table table:name="Anmeldungssteuern - Felder">
<table:table-row>
<table:table-cell><text:p>Kontext</text:p></table:table-cell>
<table:table-cell><text:p>Name</text:p></table:table-cell>
<table:table-cell><text:p>Format</text:p></table:table-cell>
<table:table-cell><text:p>Änderungsinformation</text:p></table:table-cell>
<table:table-cell table:number-columns-repeated="1020"/>
</table:table-row>
<table:table-row>
<table:table-cell><text:p>Steuerfall/Umsatzsteuervoranmeldung</text:p></table:table-cell>
<table:table-cell><text:p>Kz81</text:p></table:table-cell>
<table:table-cell><text:p>zwei <text:s/>Blanks, <text:s text:c="3"/>vier</text:p></table:table-cell>
<table:table-cell><text:p>KEIN_DELTA</text:p></table:table-cell>
</table:table-row>
<table:table-row>
<table:table-cell><text:p>Steuerfall</text:p></table:table-cell>
<table:table-cell><text:p>Kz<text:span>86</text:span></text:p></table:table-cell>
<text:soft-page-break/>
<table:table-cell><text:p>eins</text:p><text:p>zwei<text:tab/>drei<text:line-break/>vier</text:p></table:table-cell>
<table:covered-table-cell table:number-columns-repeated="2"/>
<table:table-cell><text:p>zu viel</text:p></table:table-cell>
</table:table-row>
<table:table-row><table:table-cell table:number-columns-repeated="1024"/></table:table-row>
<table:table-row><table:table-cell><text:p>kurz</text:p></table:table-cell></table:table-row>
<table:table-row>
<table:table-cell><text:p>Steuerfall</text:p></table:table-cell>
<table:table-cell><text:p>Kz23</text:p></table:table-cell>
<table:table-cell table:number-columns-repeated="1"/>
<table:table-cell><text:p>GELOESCHT</text:p></table:table-cell>
</table:table-row>
<table:table-row>
<table:table-cell><text:p>Steuerfall</text:p></table:table-cell>
<table:table-cell><text:p>Kz22 (alt)</text:p></table:table-cell>
<table:table-cell/>
<table:table-cell><text:p>GEAENDERT_ALTE_VERSION</text:p></table:table-cell>
</table:table-row>
</table:table>
<table:table table:name="Leer"/>
<table:table table:name="Anmeldungssteuern - Regeln">
<table:table-row><table:table-cell><text:p>Kontext</text:p></table:table-cell></table:table-row>
</table:table>
</office:spreadsheet></office:body></office:document-content>
"""


class DirectoryTestCase(TestCase):
	def setUp(self):
		self.directory = Path(tempfile.mkdtemp(prefix="steuerbote-documentation-"))
		self.addCleanup(shutil.rmtree, self.directory)

	def ods(self, content: str | bytes, name: str = "Jahresdokumentation_UStVA_2026.ods") -> Path:
		path = self.directory / name
		with zipfile.ZipFile(path, "w") as archive:
			archive.writestr("content.xml", content)
		return path


class FindTest(DirectoryTestCase):
	def dokumentation(self, parent: Path) -> Path:
		documentation = parent / "Dokumentation"
		(documentation / USTVA).mkdir(parents=True)
		return documentation

	def test_takes_the_directory_dokumentation_itself(self):
		documentation = self.dokumentation(self.directory)
		self.assertEqual(find(documentation), documentation)

	def test_takes_the_directory_the_package_was_unzipped_into(self):
		documentation = self.dokumentation(self.directory / "ERiC-44.3.6.0")
		self.assertEqual(find(self.directory), documentation)

	def test_refuses_a_directory_without_the_documentation(self):
		with self.assertRaisesRegex(
			DocumentationError, "holds no ERiC documentation with Datenarten/ElsterAnmeldung/UStVA"
		):
			find(self.directory)

	def test_refuses_the_documentation_of_several_versions(self):
		self.dokumentation(self.directory / "ERiC-44.3.6.0")
		self.dokumentation(self.directory / "ERiC-45.1.5.0")
		with self.assertRaisesRegex(
			DocumentationError, "several ERiC versions, name one of .*44.3.6.0.*45.1.5.0"
		):
			find(self.directory)

	def test_takes_the_directory_that_holds_another_marker(self):
		documentation = self.directory / "ERiC-44.3.6.0" / "Dokumentation"
		(documentation / "Datenarten" / "ElsterBilanz").mkdir(parents=True)
		self.assertEqual(find(self.directory, PurePosixPath("Datenarten")), documentation)
		with self.assertRaisesRegex(
			DocumentationError, "holds no ERiC documentation with Datenarten/ElsterAnmeldung"
		):
			find(self.directory)

	def test_names_the_files_of_a_year(self):
		ustva = self.directory / USTVA
		self.assertEqual(
			jahresdokumentation_path(self.directory, 2026),
			ustva / "Jahresdokumentation" / "Jahresdokumentation_UStVA_2026.ods",
		)
		self.assertEqual(schema_path(self.directory, 2026), ustva / "Schema" / "2026" / "UStVA-2026.xsd")


class SheetsTest(DirectoryTestCase):
	def setUp(self):
		super().setUp()
		self.rows = sheets(self.ods(CONTENT), FIELDS, RULES, "Leer")

	def test_reads_the_current_rows_by_the_heads_of_their_sheet(self):
		self.assertEqual(
			[dict(row) for row in self.rows[FIELDS]],
			[
				{
					"Kontext": "Steuerfall/Umsatzsteuervoranmeldung",
					"Name": "Kz81",
					"Format": "zwei  Blanks,    vier",
					"Änderungsinformation": "KEIN_DELTA",
				},
				{
					"Kontext": "Steuerfall",
					"Name": "Kz86",
					"Format": "eins\nzwei\tdrei\nvier",
					"Änderungsinformation": "",
				},
				{"Kontext": "kurz", "Name": "", "Format": "", "Änderungsinformation": ""},
			],
		)

	def test_a_sheet_with_heads_alone_or_without_rows_has_no_rows(self):
		self.assertEqual(self.rows[RULES], ())
		self.assertEqual(self.rows["Leer"], ())

	def test_rows_are_read_only(self):
		with self.assertRaises(TypeError):
			self.rows[FIELDS][0]["Name"] = "Kz86"  # type: ignore[index]

	def test_names_the_sheets_it_misses(self):
		with self.assertRaisesRegex(DocumentationError, "has no sheet Zeichensatz, Kennzahlen"):
			sheets(self.ods(CONTENT), FIELDS, "Zeichensatz", "Kennzahlen")

	def test_refuses_a_file_that_is_no_spreadsheet(self):
		not_a_zip = self.directory / "kaputt.ods"
		not_a_zip.write_bytes(b"no zip")
		without_content = self.directory / "leer.ods"
		with zipfile.ZipFile(without_content, "w") as archive:
			archive.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
		for path in (
			self.directory / "fehlt.ods",
			not_a_zip,
			without_content,
			self.ods("<unclosed>", "xml.ods"),
		):
			with self.subTest(path=path.name), self.assertRaisesRegex(DocumentationError, "cannot be read"):
				sheets(path, FIELDS)


class TablesTest(DirectoryTestCase):
	"""The rows of a sheet as they are, for the sheets without a head row such as "Allg. Information"."""

	def test_gives_each_row_as_the_texts_of_its_cells_without_the_empty_ones_at_its_end(self):
		rows = tables(self.ods(CONTENT), FIELDS)[FIELDS]
		self.assertEqual(rows[0], ("Kontext", "Name", "Format", "Änderungsinformation"))
		self.assertEqual(rows[2], ("Steuerfall", "Kz86", "eins\nzwei\tdrei\nvier", "", "", "zu viel"))
		self.assertEqual(rows[3], ())
		self.assertEqual(rows[4], ("kurz",))

	def test_keeps_the_rows_of_every_version(self):
		rows = tables(self.ods(CONTENT), FIELDS)[FIELDS]
		self.assertEqual([row[-1] for row in rows[5:]], ["GELOESCHT", "GEAENDERT_ALTE_VERSION"])

	def test_gives_the_named_sheets_or_every_sheet_in_its_order(self):
		path = self.ods(CONTENT)
		self.assertEqual(list(tables(path, RULES, "Leer")), ["Leer", RULES])
		self.assertEqual(list(tables(path)), [FIELDS, "Leer", RULES])
		self.assertEqual(tables(path)["Leer"], ())

	def test_names_the_sheets_it_misses(self):
		with self.assertRaisesRegex(DocumentationError, "has no sheet Zeichensatz$"):
			tables(self.ods(CONTENT), FIELDS, "Zeichensatz")

	def test_refuses_a_file_that_is_no_spreadsheet(self):
		with self.assertRaisesRegex(DocumentationError, "kaputt.ods cannot be read as a spreadsheet"):
			tables(self.directory / "kaputt.ods")


class RecordsTest(TestCase):
	def test_takes_the_rows_of_a_sheet_by_the_heads_of_its_first_row(self):
		self.assertEqual(
			[dict(row) for row in records((("Name", "Kontext"), ("Kz81", "Steuerfall"), ("Kz86",)))],
			[{"Name": "Kz81", "Kontext": "Steuerfall"}, {"Name": "Kz86", "Kontext": ""}],
		)

	def test_leaves_out_empty_rows_and_the_versions_a_year_dropped_or_replaced(self):
		rows = (
			("Name", "Änderungsinformation"),
			(),
			("Kz23", "GELOESCHT"),
			("Kz22", "GEAENDERT_ALTE_VERSION"),
		)
		self.assertEqual(records(rows), ())
		self.assertEqual(records(()), ())


class XsdTest(DirectoryTestCase):
	def xsd(self, text: str) -> Path:
		path = self.directory / "UStVA-2026.xsd"
		path.write_text(text, encoding="utf-8")
		return path

	def test_reads_namespace_version_and_the_elements_of_each_context(self):
		data = data_for(2026)
		path = self.directory / "schema.xsd"
		path.write_bytes(eric_documentation.schema(eric_documentation.documented(data)))
		xsd = read_xsd(path)
		self.assertEqual(xsd.namespace, data.schema.namespace)
		self.assertEqual(xsd.version, "2026")
		self.assertEqual(
			list(xsd.contexts),
			["Umsatzsteuervoranmeldung", "Dauerfristverlaengerung", "Umsatzsteuersondervorauszahlung"],
		)
		self.assertEqual(xsd.contexts["Umsatzsteuervoranmeldung"][-1], ("Kz500_Begruendung", "String_SType"))
		self.assertEqual(
			[name for name, _ in xsd.contexts["Umsatzsteuervoranmeldung"]], list(data.schema.elements)
		)

	def test_a_schema_without_its_root_has_neither_version_nor_contexts(self):
		xsd = read_xsd(
			self.xsd(
				'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:x">'
				'<xs:element name="Anderes" type="Anderes_CType"/>'
				'<xs:complexType><xs:sequence><xs:element name="ohne Namen"/></xs:sequence></xs:complexType>'
				"</xs:schema>"
			)
		)
		self.assertEqual((xsd.namespace, xsd.version, dict(xsd.contexts)), ("urn:x", None, {}))

	def test_a_root_without_version_or_steuerfall_has_neither(self):
		xsd = read_xsd(
			self.xsd(
				'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
				'<xs:element name="Anmeldungssteuern" type="A_CType"/>'
				'<xs:complexType name="A_CType"><xs:sequence><xs:element name="Erstellungsdatum"/></xs:sequence>'
				"</xs:complexType></xs:schema>"
			)
		)
		self.assertEqual((xsd.namespace, xsd.version, dict(xsd.contexts)), (None, None, {}))

	def test_a_context_of_a_simple_type_has_no_elements(self):
		xsd = read_xsd(
			self.xsd(
				'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
				'<xs:element name="Anmeldungssteuern" type="A_CType"/>'
				'<xs:complexType name="A_CType"><xs:sequence><xs:element name="Steuerfall" type="S_CType"/>'
				'</xs:sequence></xs:complexType><xs:complexType name="S_CType"><xs:sequence>'
				'<xs:element name="Umsatzsteuervoranmeldung" type="String_SType"/></xs:sequence></xs:complexType>'
				"</xs:schema>"
			)
		)
		self.assertEqual(dict(xsd.contexts), {"Umsatzsteuervoranmeldung": ()})

	def test_refuses_a_file_that_is_no_schema(self):
		for path in (self.directory / "fehlt.xsd", self.xsd("<xs:schema")):
			with (
				self.subTest(path=path.name),
				self.assertRaisesRegex(DocumentationError, "cannot be read as a schema"),
			):
				read_xsd(path)


class ReadTest(DirectoryTestCase):
	def test_reads_both_files_of_the_year(self):
		data = data_for(2026)
		documented = eric_documentation.documented(data)
		year = read(eric_documentation.write(self.directory, documented), 2026)
		self.assertEqual(
			(year.year, year.jahresdokumentation, year.schema),
			(2026, "Jahresdokumentation_UStVA_2026.ods", "UStVA-2026.xsd"),
		)
		self.assertEqual(year.fields[0]["Name"], "Jahr")
		self.assertEqual(len(year.rules), len(documented.rules) - 1)
		self.assertEqual(year.xsd.version, "2026")
		self.assertEqual(year.matrix, "Datenartversionmatrix.ods")
		self.assertEqual([row["Datenart(en)"] for row in year.datenart_versions], ["LStA", "UStVA", "ZMDO"])

	def test_refuses_a_sheet_without_a_column_the_check_reads(self):
		documented = eric_documentation.documented(data_for(2026))
		for row in documented.rules:
			row["Regel"] = row.pop("Regelart")
		documentation = self.directory / "ERiC-44.3.6.0" / "Dokumentation"
		with mock.patch.object(
			eric_documentation, "RULE_HEADS", (*eric_documentation.RULE_HEADS[:4], "Regel")
		):
			eric_documentation.write(self.directory, documented)
		with self.assertRaisesRegex(
			DocumentationError,
			"Jahresdokumentation_UStVA_2026.ods, sheet Anmeldungssteuern - Regeln, has no column Regelart",
		):
			read(documentation, 2026)

	def test_refuses_a_documentation_without_the_datenartversionmatrix(self):
		documentation = eric_documentation.write(
			self.directory, eric_documentation.documented(data_for(2026))
		)
		(documentation / "Datenartversionmatrix.ods").unlink()
		with self.assertRaisesRegex(DocumentationError, "Datenartversionmatrix.ods cannot be read"):
			read(documentation, 2026)

	def test_refuses_a_year_the_documentation_does_not_have(self):
		documentation = eric_documentation.write(
			self.directory, eric_documentation.documented(data_for(2026))
		)
		with self.assertRaisesRegex(DocumentationError, "Jahresdokumentation_UStVA_2025.ods cannot be read"):
			read(documentation, 2025)
