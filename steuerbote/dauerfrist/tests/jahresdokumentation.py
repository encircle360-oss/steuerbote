"""Jahresdokumentation_UStVA_<year>.ods of the ERiC documentation, read for the tests of the form model.

Like the XML schemas, the Jahresdokumentation carries no licence that allows passing it on, so the tests read
it from the unzipped ERiC documentation that STEUERBOTE_ERIC_DOC_DIR names, see
steuerbote/elster/tests/eric_schema.py. The file is an OpenDocument spreadsheet: a zip whose content.xml
holds one table per sheet.
"""

import zipfile
from functools import cache
from pathlib import Path

from lxml import etree

from steuerbote.elster.tests import eric_schema

TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
CELLS = (f"{{{TABLE}}}table-cell", f"{{{TABLE}}}covered-table-cell")
# Versions of a rule or field that a year replaced or dropped stay in the sheets, marked so.
OUTDATED = frozenset({"GELOESCHT", "GEAENDERT_ALTE_VERSION"})
# More columns than any sheet has; empty cells at the end of a row repeat up to the last column of the sheet.
MAX_COLUMNS = 64


def path(year: int) -> Path:
	ustva = eric_schema.documentation() / "Datenarten" / "ElsterAnmeldung" / "UStVA"
	return ustva / "Jahresdokumentation" / f"Jahresdokumentation_UStVA_{year}.ods"


@cache
def sheet(year: int, name: str) -> tuple[dict[str, str], ...]:
	"""The current rows of a sheet as dicts by the heads of its first row."""
	with zipfile.ZipFile(path(year)) as archive:
		root = etree.fromstring(archive.read("content.xml"))
	for table in root.iter(f"{{{TABLE}}}table"):
		if table.get(f"{{{TABLE}}}name") == name:
			head, *rows = (_cells(row) for row in table.iter(f"{{{TABLE}}}table-row"))
			records = (
				dict(zip(head, row + [""] * (len(head) - len(row)), strict=False)) for row in rows if row
			)
			return tuple(record for record in records if record.get("Änderungsinformation") not in OUTDATED)
	raise KeyError(f"Jahresdokumentation_UStVA_{year}.ods has no sheet {name}")


def _cells(row: etree._Element) -> list[str]:
	cells: list[str] = []
	for cell in row:
		if cell.tag in CELLS:
			text = "\n".join("".join(paragraph.itertext()) for paragraph in cell.iter(f"{{{TEXT}}}p"))
			repeat = int(cell.get(f"{{{TABLE}}}number-columns-repeated", "1"))
			cells.extend([text] * min(repeat, MAX_COLUMNS))
	while cells and not cells[-1]:
		cells.pop()
	return cells
