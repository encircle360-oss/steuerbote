"""The XML schemas of the public ERiC documentation, for the tests against them.

The schemas carry no licence that allows passing them on, so they are not part of the repository. The tests
read them from the unzipped ERiC documentation 44.3.6.0 (``DOWNLOAD``), whose directory the environment
variable STEUERBOTE_ERIC_DOC_DIR names: the directory the zip was unzipped into, or its directory
Dokumentation. Without the variable the tests against the schemas are skipped, except in a CI, which has to
run them. The workflow downloads the zip and checks its SHA-256 first, see docs/entwicklung.md.
"""

import os
from functools import cache
from pathlib import Path
from unittest import SkipTest

from lxml import etree

VARIABLE = "STEUERBOTE_ERIC_DOC_DIR"
VERSION = "44.3.6.0"
DOWNLOAD = f"https://download.elster.de/download/eric/eric_44/ERiC-{VERSION}-Dokumentation.zip"


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
