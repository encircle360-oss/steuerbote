"""Validate instances of both profiles with Arelle against the HGB-Taxonomie 6.9, for the XBRL job of the CI.

    python -m steuerbote.xbrl.tests.arelle_validation [ARCHIVE] [--keep DIRECTORY]

ARCHIVE is the package of esteuer.de (steuerbote/xbrl/versions.py), by default the one the environment variable
STEUERBOTE_TAXONOMY_6_9 names; STEUERBOTE_ERIC_DOC_DIR names the unzipped ERiC documentation 44.3.6.0, whose examples
the script writes again. Arelle (arelle-release in requirements-dev.txt) validates, offline:

- the examples of the ERiC documentation on the Kerntaxonomie it calls valid, read into the facts of
  steuerbote/xbrl/facts.py (steuerbote/xbrl/tests/instances.py) and written by steuerbote/xbrl/writer.py in the view
  FISCAL;
- the Offenlegung of an invented GmbH as a Kleinstkapitalgesellschaft and as a small company, with both closing dates
  and the data of § 264 Abs. 1a HGB, in the views of the profile DISCLOSURE, after the checks of that profile.

Each passes XBRL 2.1, XBRL Dimensions 1.0 and the calculations of XBRL 2.1. The documents of the taxonomy refer to each
other by absolute URLs under http://www.xbrl.de/taxonomies/, which the server of XBRL Deutschland does not serve
(Technischer Leitfaden zur HGB-Taxonomie 6.9, A.6), so the script makes the unpacked package a taxonomy package whose
catalog rewrites them to its files (XBRL International, Taxonomy Packages 1.0). Every message of Arelle of the level
warning or above fails the run with exit code 1; without the archive or the documentation the exit code is 2.
"""

import argparse
import os
import sys
import tempfile
import zipfile
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

from arelle import CntlrCmdLine

from steuerbote.elster.tests.eric_schema import VARIABLE as DOCUMENTATION_VARIABLE
from steuerbote.elster.tests.eric_schema import documentation
from steuerbote.xbrl import writer
from steuerbote.xbrl.facts import Entity, Fact, Item, Period, Periods
from steuerbote.xbrl.profiles import DISCLOSURE, FISCAL
from steuerbote.xbrl.taxonomy import Installation, View, install_from_archive
from steuerbote.xbrl.tests import instances
from steuerbote.xbrl.tests.real import VARIABLE, VERSION
from steuerbote.xbrl.tests.test_real_taxonomy import EricExamplesTest

CATALOG = """<?xml version="1.0" encoding="UTF-8"?>
<catalog xmlns="urn:oasis:names:tc:entity:xmlns:xml:catalog">
	<rewriteURI uriStartString="http://www.xbrl.de/taxonomies/" rewritePrefix="../"/>
</catalog>
"""
TAXONOMY_PACKAGE = f"""<?xml version="1.0" encoding="UTF-8"?>
<tp:taxonomyPackage xmlns:tp="http://xbrl.org/2016/taxonomy-package" xml:lang="de">
	<tp:identifier>urn:steuerbote:hgb-taxonomie:{VERSION.version}</tp:identifier>
	<tp:name>HGB-Taxonomie {VERSION.version}</tp:name>
	<tp:version>{VERSION.released.isoformat()}</tp:version>
</tp:taxonomyPackage>
"""
# Invented: a Steuernummer of the test Finanzamt 9198 of the ERiC documentation, and the GmbH of the Offenlegung.
ENTITY = Entity.steuernummer("9198011310010")
PERIODS = Periods(date(2026, 1, 1), date(2026, 12, 31), None, date(2025, 1, 1), date(2025, 12, 31))
REGISTER = {
	"notesBelowBalanceSheet.geninfo.company": "Beispiel GmbH",
	"notesBelowBalanceSheet.geninfo.location": "Musterstadt",
	"notesBelowBalanceSheet.geninfo.court": "Amtsgericht Musterstadt",
	"notesBelowBalanceSheet.geninfo.number": "HRB 99999",
}
KLEINST = {
	"bs.ass": ("100000.00", "90000.00"),
	"bs.ass.fixAss": ("60000.00", "50000.00"),
	"bs.ass.currAss": ("40000.00", "40000.00"),
	"bs.eqLiab": ("100000.00", "90000.00"),
	"bs.eqLiab.equity": ("70000.00", "60000.00"),
	"bs.eqLiab.liab": ("30000.00", "30000.00"),
}
"""The Bilanz of a Kleinstkapitalgesellschaft with its letters (§ 266 Abs. 1 Satz 4 HGB), this year and the last."""
KLEIN = KLEINST | {
	"bs.ass.fixAss.tan": ("60000.00", "50000.00"),
	"bs.ass.currAss.receiv": ("10000.00", "15000.00"),
	"bs.ass.currAss.cashEquiv": ("30000.00", "25000.00"),
	"bs.eqLiab.equity.subscribed": ("25000.00", "25000.00"),
	"bs.eqLiab.equity.retainedEarnings": ("20000.00", "10000.00"),
	"bs.eqLiab.equity.netIncome": ("25000.00", "25000.00"),
}
"""The Bilanz of a small company with its letters and roman numerals (§ 266 Abs. 1 Satz 3 HGB)."""


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__.partition("\n")[0])
	parser.add_argument("archive", nargs="?", type=Path, default=os.environ.get(VARIABLE))
	parser.add_argument(
		"--keep", type=Path, help="the directory to keep the package, the instances and the logs in"
	)
	options = parser.parse_args(argv)
	if options.archive is None or not os.environ.get(DOCUMENTATION_VARIABLE):
		sys.stderr.write(f"Name the archive of the taxonomy and set {DOCUMENTATION_VARIABLE}.\n")
		return 2
	with tempfile.TemporaryDirectory(prefix="steuerbote-arelle-") as temporary:
		directory = options.keep or Path(temporary)
		directory.mkdir(parents=True, exist_ok=True)
		installation = install_from_archive(Path(options.archive), VERSION.archive_sha256, directory, VERSION)
		package = taxonomy_package(installation, directory / f"hgb-taxonomie-{VERSION.version}.zip")
		failed = 0
		for name, data in documents(installation):
			path = directory / name
			path.write_bytes(data)
			messages = validate(package, path)
			sys.stdout.write(f"{name}: {'gültig' if not messages else f'{len(messages)} Meldungen'}\n")
			sys.stdout.writelines(f"  {message}\n" for message in messages)
			failed += bool(messages)
		return 1 if failed else 0


def taxonomy_package(installation: Installation, path: Path) -> Path:
	"""The unpacked package as a taxonomy package, its catalog mapping the URLs of www.xbrl.de to its files."""
	top = path.stem
	with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
		archive.writestr(f"{top}/META-INF/catalog.xml", CATALOG)
		archive.writestr(f"{top}/META-INF/taxonomyPackage.xml", TAXONOMY_PACKAGE)
		for name in sorted(installation.files):
			archive.write(installation.package / name, f"{top}/{name}")
	return path


def documents(installation: Installation) -> Iterator[tuple[str, bytes]]:
	"""Each instance to validate with its file name."""
	fiscal = installation.view(View.FISCAL)
	examples = documentation() / "Datenarten" / "ElsterBilanz" / "Bilanz" / "Beispiele" / "Taxonomie_6_9"
	for name in EricExamplesTest.VALID:
		report = instances.read(examples / name, fiscal)
		yield (
			f"fiscal-{name}",
			writer.write(FISCAL.report(fiscal, report.entity, report.periods, report.facts), fiscal),
		)
	for kleinst, positions in ((True, KLEINST), (False, KLEIN)):
		taxonomy = installation.view(DISCLOSURE.view(kleinst=kleinst))
		report = DISCLOSURE.report(taxonomy, ENTITY, PERIODS, disclosure(positions))
		findings = DISCLOSURE.check(report, taxonomy, published=(*positions, *REGISTER))
		blocking = [finding.text for finding in findings if finding.blocking]
		if blocking:
			raise SystemExit("\n".join(blocking))
		yield f"disclosure-{'kleinst' if kleinst else 'klein'}.xbrl", writer.write(report, taxonomy)


def disclosure(positions: dict[str, tuple[str, str]]) -> tuple[Fact, ...]:
	balance_sheet = tuple(
		Item(f"de-gaap-ci:{concept}", period, Decimal(value))
		for concept, values in positions.items()
		for value, period in zip(values, (Period.STICHTAG, Period.VORJAHR_STICHTAG), strict=True)
	)
	register = tuple(
		Item(f"de-gaap-ci:{concept}", Period.WIRTSCHAFTSJAHR, text) for concept, text in REGISTER.items()
	)
	return (*balance_sheet, *register)


def validate(package: Path, instance: Path) -> list[str]:
	"""The messages of Arelle of the level warning or above about the instance."""
	log = instance.with_suffix(".log")
	log.unlink(missing_ok=True)
	controller = CntlrCmdLine.parseAndRun(
		[
			"--packages",
			str(package),
			"--file",
			str(instance),
			"--validate",
			"--calc",
			"c10",
			"--workOffline",
			"--logLevel",
			"warning",
			"--logFile",
			str(log),
		]
	)
	controller.close()
	return (
		[line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
		if log.exists()
		else []
	)


if __name__ == "__main__":
	sys.exit(main())
