"""Jahresdokumentation_E50_<Jahr>.ods and E50-<Jahr>.xsd of the ERiC documentation, read for the tests of the catalogue.

Like the other files of the ERiC documentation, they carry no licence that allows passing them on, so the tests read
them from the unzipped documentation that STEUERBOTE_ERIC_DOC_DIR names (steuerbote/elster/tests/eric_schema.py), in
Datenarten/ElsterErklaerung/USt below its directory Dokumentation, with the reader of the annual filings
(steuerbote/jahresmeldung/documentation.py). Without that directory the tests are skipped with a message.
"""

from functools import cache
from pathlib import Path
from unittest import SkipTest

from steuerbote.elster.tests import eric_schema
from steuerbote.eric.datenart import ust as datenart
from steuerbote.jahresmeldung import documentation
from steuerbote.jahresmeldung.documentation import Jahresdokumentation
from steuerbote.ustva.documentation import Row

MAIN_FORM = "USt2A"
FIELDS = "USt2A - Felder"
KENNZAHLEN = "USt2A - Kennzahlen"
RULES = "USt2A - Regeln"


def ust() -> Path:
	"""Datenarten/ElsterErklaerung/USt of the documentation; skips the test without it."""
	directory = documentation.directory(eric_schema.documentation(), datenart(2026))
	if not directory.is_dir():
		raise SkipTest(
			f"{directory} is missing: the catalogue of form USt 2 A is not checked against the ERiC documentation. "
			f"Unzip */Datenarten/ElsterErklaerung/* of {eric_schema.DOWNLOAD} as well."
		)
	return directory


def jahresdokumentation(year: int) -> Path:
	ust()
	return documentation.jahresdokumentation_path(eric_schema.documentation(), datenart(year))


def schema(year: int) -> Path:
	ust()
	return documentation.schema_path(eric_schema.documentation(), datenart(year))


@cache
def read(year: int) -> Jahresdokumentation:
	"""The Jahresdokumentation of the year, read once per run."""
	return documentation.read(jahresdokumentation(year))


def sheet(year: int, name: str) -> tuple[Row, ...]:
	"""The current rows of a sheet of the Jahresdokumentation of the year."""
	return read(year).sheet(name)


def fields(year: int) -> tuple[Row, ...]:
	"""The fields of USt2A that a filing holds: those of the sheet "USt2A - Felder" but ERiC's internal ones."""
	return read(year).vordruck(MAIN_FORM).filed_fields


@cache
def leaves(year: int) -> tuple[tuple[str, str], ...]:
	"""The context and name of each leaf of USt2A in the schema, in the order of its sequences."""
	schema_of_the_year = documentation.read_schema(schema(year), datenart(year).root)
	return tuple((leaf.context, leaf.name) for leaf in schema_of_the_year.vordrucke[MAIN_FORM])
