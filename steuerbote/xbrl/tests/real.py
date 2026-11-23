"""The HGB-Taxonomie 6.9 of esteuer.de, for the tests against the real package.

The package carries no licence that allows passing it on, so it is not part of the repository. The tests read it from
the archive esteuer.de publishes (steuerbote/xbrl/versions.py), whose path the environment variable
STEUERBOTE_TAXONOMY_6_9 names, as the operator names it in common_site_config.json. Without the variable the tests
against the package are skipped, except in a CI, which has to run them; the workflow downloads the archive and checks
its SHA-256 first. Installed once per run into a directory of its own, the package serves every test that reads it.
"""

import atexit
import os
import shutil
import tempfile
from functools import cache
from pathlib import Path
from unittest import SkipTest

from steuerbote.xbrl.taxonomy import Installation, Taxonomy, View, install_from_archive
from steuerbote.xbrl.versions import TAXONOMIES

VERSION = TAXONOMIES["6.9"]
VARIABLE = "STEUERBOTE_TAXONOMY_6_9"


def archive() -> Path:
	"""The archive of the package 6.9; skips the test without it."""
	configured = os.environ.get(VARIABLE)
	if not configured:
		message = (
			f"{VARIABLE} is not set: nothing is checked against the HGB-Taxonomie 6.9. Download {VERSION.archive_url} "
			f"and set {VARIABLE} to its path."
		)
		if os.environ.get("CI"):
			raise RuntimeError(message)
		raise SkipTest(message)
	return Path(configured)


@cache
def installation() -> Installation:
	"""The package installed as „Taxonomie einrichten“ installs it, into a directory removed at the end of the run."""
	path = archive()
	directory = Path(tempfile.mkdtemp(prefix="steuerbote-xbrl-6-9-"))
	atexit.register(shutil.rmtree, directory, ignore_errors=True)
	return install_from_archive(path, VERSION.archive_sha256, directory, VERSION)


@cache
def view(name: View = View.FISCAL) -> Taxonomy:
	return installation().view(name)


VERSION_6_10 = TAXONOMIES["6.10"]
VARIABLE_6_10 = "STEUERBOTE_TAXONOMY_6_10"


def archive_6_10() -> Path:
	"""The archive of the package 6.10, which the environment variable STEUERBOTE_TAXONOMY_6_10 names; skips the test
	without it, except in a CI."""
	configured = os.environ.get(VARIABLE_6_10)
	if not configured:
		message = (
			f"{VARIABLE_6_10} is not set: nothing is checked against the HGB-Taxonomie 6.10. Download "
			f"{VERSION_6_10.archive_url} and set {VARIABLE_6_10} to its path."
		)
		if os.environ.get("CI"):
			raise RuntimeError(message)
		raise SkipTest(message)
	return Path(configured)


@cache
def installation_6_10() -> Installation:
	"""The package 6.10 installed as „Taxonomie einrichten“ installs it, into a directory removed at the end of the
	run."""
	path = archive_6_10()
	directory = Path(tempfile.mkdtemp(prefix="steuerbote-xbrl-6-10-"))
	atexit.register(shutil.rmtree, directory, ignore_errors=True)
	return install_from_archive(path, VERSION_6_10.archive_sha256, directory, VERSION_6_10)


@cache
def view_6_10(name: View = View.FISCAL) -> Taxonomy:
	return installation_6_10().view(name)
