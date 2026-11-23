"""The XML schemas of the public ERiC documentation, for the tests against them.

The schemas carry no licence that allows passing them on, so they are not part of the repository. The tests
read them from the unzipped ERiC documentation 44.3.6.0 (``DOWNLOAD``), whose directory the environment
variable STEUERBOTE_ERIC_DOC_DIR names: the directory the zip was unzipped into, or its directory
Dokumentation. Without the variable the tests against the schemas are skipped, except in a CI, which has to
run them. The workflow downloads the zip and checks its SHA-256 first, see docs/entwicklung.md. The same goes
for the spreadsheets of the documentation that the tests compare with the rules written down in the code.

A provisional year comes from the documentation of a beta, which the CI does not pin: 2027 from ERiC 45.1.5.0
(``BETA_DOWNLOAD``, steuerbote/ustva/years.py). The tests of such a year take its files from the same directory
through ``ustva_year`` and are skipped, in a CI too, while it holds a release that knows nothing of the year.
"""

import os
import zipfile
from functools import cache
from pathlib import Path
from unittest import SkipTest

from lxml import etree

VARIABLE = "STEUERBOTE_ERIC_DOC_DIR"
VERSION = "44.3.6.0"
DOWNLOAD = f"https://download.elster.de/download/eric/eric_44/ERiC-{VERSION}-Dokumentation.zip"
BETA_VERSION = "45.1.5.0"
BETA_DOWNLOAD = f"https://download.elster.de/download/eric/eric_45/ERiC-{BETA_VERSION}-Dokumentation.zip"
# The zip as download.elster.de serves it, last modified on 16 October 2026.
BETA_SHA256 = "9b43f426d006e1b892bbc9cd15d789c18dc3017f7f0d4d5c0399dfbf48b30b64"


def documentation() -> Path:
	"""The directory Dokumentation of the unzipped ERiC documentation; skips the test without it."""
	configured = os.environ.get(VARIABLE)
	if not configured:
		message = (
			f"{VARIABLE} is not set: the XML is not checked against the ERiC schemas. "
			f"Unzip {DOWNLOAD} and set {VARIABLE} to its directory."
		)
		if os.environ.get("CI"):
			raise RuntimeError(message)
		raise SkipTest(message)
	root = Path(configured)
	for candidate in (root, *sorted(root.glob("ERiC-*/Dokumentation"))):
		if (candidate / "ElsterBasisSchema" / "Schema").is_dir():
			return candidate
	raise FileNotFoundError(f"{VARIABLE}={configured} holds no unzipped ERiC documentation")


def _ustva() -> Path:
	return documentation() / "Datenarten" / "ElsterAnmeldung" / "UStVA"


def ustva_year(year: int) -> Path:
	"""The directory Dokumentation once it holds the UStVA of the year, its Jahresdokumentation and its schema; skips
	the test, in a CI too, while it holds a release that knows nothing of the year."""
	root = documentation()
	ustva = root / "Datenarten" / "ElsterAnmeldung" / "UStVA"
	files = (
		ustva / "Jahresdokumentation" / f"Jahresdokumentation_UStVA_{year}.ods",
		ustva / "Schema" / str(year) / f"UStVA-{year}.xsd",
	)
	missing = [path.name for path in files if not path.is_file()]
	if missing:
		raise SkipTest(
			f"{root} holds no {' and no '.join(missing)}: the UStVA of {year} is not checked against the ERiC "
			f"documentation. Unzip {BETA_DOWNLOAD} (SHA-256 {BETA_SHA256}) and set {VARIABLE} to its directory."
		)
	return root


def nutzdaten_xsd(year: int) -> Path:
	"""UStVA-<year>.xsd: the schema of Anmeldungssteuern, which the import file follows."""
	return _ustva() / "Schema" / str(year) / f"UStVA-{year}.xsd"


@cache
def nutzdaten_schema(year: int) -> etree.XMLSchema:
	return etree.XMLSchema(etree.parse(str(nutzdaten_xsd(year))))


@cache
def envelope_schema(year: int) -> etree.XMLSchema:
	"""elster11_UStVA_<year>_extern.xsd, with the ElsterBasisSchema it includes by relative paths."""
	return etree.XMLSchema(
		etree.parse(str(_ustva() / "Schema" / str(year) / f"elster11_UStVA_{year}_extern.xsd"))
	)


def example(year: int) -> bytes:
	"""The documentation's example of a Voranmeldung in its envelope, Beispiele/UStVA_<year>.xml."""
	return (_ustva() / "Beispiele" / f"UStVA_{year}.xml").read_bytes()


# The examples of form USt 1 H by the context they file.
UST1H_EXAMPLES = {"Dauerfristverlaengerung": "Df", "Umsatzsteuersondervorauszahlung": "SoVZ"}


def ust1h_example(year: int, context: str) -> bytes:
	"""The documentation's example of a context of form USt 1 H in its envelope: Beispiele/UStVA_Df_<year>.xml
	for the Antrag auf Dauerfristverlängerung, Beispiele/UStVA_SoVZ_<year>.xml for the Anmeldung der
	Sondervorauszahlung."""
	return (_ustva() / "Beispiele" / f"UStVA_{UST1H_EXAMPLES[context]}_{year}.xml").read_bytes()


ELSTER_XML = "http://www.elster.de/elsterxml/schema/v11"
XSD = "http://www.w3.org/2001/XMLSchema"
ODS_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
ODS_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"


def _zmdo() -> Path:
	return documentation() / "Datenarten" / "ElsterExtern" / "ZMDO"


def zm_xsd() -> Path:
	"""zm_000005.xsd: the schema of the Nutzdaten of the Datenart ZMDO, which declares no namespace."""
	return _zmdo() / "Schema" / "5" / "zm_000005.xsd"


@cache
def zm_schema() -> etree.XMLSchema:
	"""zm_000005.xsd in the namespace of ElsterXML 11, in which ERiC takes the Nutzdaten.

	elster11_Zm_000005_extern.xsd includes the schema into that namespace; this schema does the same for the
	element zm alone.
	"""
	wrapper = (
		f'<xs:schema xmlns:xs="{XSD}" xmlns="{ELSTER_XML}" targetNamespace="{ELSTER_XML}" '
		f'elementFormDefault="qualified"><xs:include schemaLocation="{zm_xsd().as_uri()}"/></xs:schema>'
	)
	return etree.XMLSchema(etree.fromstring(wrapper))


@cache
def zm_envelope_schema() -> etree.XMLSchema:
	"""elster11_Zm_000005_extern.xsd, with the ElsterBasisSchema it includes by relative paths."""
	return etree.XMLSchema(etree.parse(str(_zmdo() / "Schema" / "5" / "elster11_Zm_000005_extern.xsd")))


def zm_example() -> bytes:
	"""The documentation's example of a ZM in its envelope, Beispiele/ZMDO_5_send-Auth.xml."""
	return (_zmdo() / "Beispiele" / "ZMDO_5_send-Auth.xml").read_bytes()


def zm_fields() -> list[dict[str, str]]:
	"""The sheet „ZMDO - Felder“ of Jahresdokumentation_ZMDO_2.ods, a row per field."""
	return sheet(_zmdo() / "Jahresdokumentation" / "Jahresdokumentation_ZMDO_2.ods", "ZMDO - Felder")


def sheet(path: Path, name: str) -> list[dict[str, str]]:
	"""The rows of a sheet of a spreadsheet in the OpenDocument format, by the texts of its first row.

	A cell gives the text of its paragraphs, one per line; the blanks that the format writes as elements of their
	own are left out, which none of the cells the tests read has.
	"""
	with zipfile.ZipFile(path) as archive:
		content = etree.fromstring(archive.read("content.xml"))
	(table,) = (
		table for table in content.iter(f"{{{ODS_TABLE}}}table") if table.get(f"{{{ODS_TABLE}}}name") == name
	)
	rows = [_cells(row) for row in table.iter(f"{{{ODS_TABLE}}}table-row")]
	head, *body = rows
	return [dict(zip(head, cells, strict=False)) for cells in body if any(cells)]


def _cells(row: etree._Element) -> list[str]:
	cells = []
	for cell in row:
		text = "\n".join("".join(paragraph.itertext()) for paragraph in cell.iter(f"{{{ODS_TEXT}}}p"))
		# A row ends in empty cells that the format repeats up to the last column of the sheet.
		repeat = 1 if not text else int(cell.get(f"{{{ODS_TABLE}}}number-columns-repeated", "1"))
		cells.extend([text] * repeat)
	return cells


def erklaerung_directory(name: str) -> Path:
	"""The directory of a Datenart of the Verfahren ElsterErklaerung, such as USt, KSt or GewSt."""
	return documentation() / "Datenarten" / "ElsterErklaerung" / name


def lines(path: Path, name: str) -> list[str]:
	"""The text of the first cell of each row of a sheet, such as „Allg. Information“, which has no head row."""
	with zipfile.ZipFile(path) as archive:
		content = etree.fromstring(archive.read("content.xml"))
	(table,) = (
		table for table in content.iter(f"{{{ODS_TABLE}}}table") if table.get(f"{{{ODS_TABLE}}}name") == name
	)
	return [
		cells[0] for row in table.iter(f"{{{ODS_TABLE}}}table-row") if (cells := _cells(row)) and cells[0]
	]


def bilanz_directory() -> Path:
	"""The directory of the Datenart Bilanz of the Verfahren ElsterBilanz."""
	return documentation() / "Datenarten" / "ElsterBilanz" / "Bilanz"


def bilanz_example(taxonomy: str, name: str = "HandelsbilanzLandwirt_GmbH.xml") -> bytes:
	"""An example of an E-Bilanz of the taxonomy in its envelope, Beispiele/Taxonomie_<major>_<minor>/<name>."""
	return (bilanz_directory() / "Beispiele" / f"Taxonomie_{taxonomy.replace('.', '_')}" / name).read_bytes()


@cache
def erklaerung_envelope_schema(name: str, root: str, year: int) -> etree.XMLSchema:
	"""elster11_<root>_<year>_extern.xsd of an Erklärung, with the ElsterBasisSchema it includes by relative paths."""
	schema = erklaerung_directory(name) / "Schema" / str(year) / f"elster11_{root}_{year}_extern.xsd"
	return etree.XMLSchema(etree.parse(str(schema)))


XBRL_INSTANCE_SCHEMA = "http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd"
# Takes any element xbrli:xbrl: the XBRL instance is the plugin's to check, the wrapper is the schema's.
XBRL_STAND_IN = (
	f'<xs:schema xmlns:xs="{XSD}" targetNamespace="http://www.xbrl.org/2003/instance" elementFormDefault="qualified">'
	'<xs:element name="xbrl"><xs:complexType><xs:sequence>'
	'<xs:any processContents="skip" namespace="##any" minOccurs="0" maxOccurs="unbounded"/>'
	'</xs:sequence><xs:anyAttribute processContents="skip"/></xs:complexType></xs:element></xs:schema>'
)


class _XbrlStandIn(etree.Resolver):
	def resolve(self, system_url, public_id, context):
		if system_url == XBRL_INSTANCE_SCHEMA:
			return self.resolve_string(XBRL_STAND_IN, context)
		return None


@cache
def bilanz_envelope_schema() -> etree.XMLSchema:
	"""ebilanz_000002.xsd with the ElsterBasisSchema that ebilanz_elster_000001.xsd includes.

	The schema imports the XBRL instance schema by its address on xbrl.org, which the documentation does not hold
	and the tests do not fetch; a stand-in that takes any element xbrli:xbrl replaces it.
	"""
	parser = etree.XMLParser(no_network=True)
	parser.resolvers.add(_XbrlStandIn())
	return etree.XMLSchema(etree.parse(str(bilanz_directory() / "Schema" / "ebilanz_000002.xsd"), parser))
