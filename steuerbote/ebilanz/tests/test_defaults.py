"""The defaults of the Bilanzzuordnung for SKR03 and SKR04 per version of the HGB-Taxonomie, with the version of the
defaults (steuerbote/ebilanz/defaults.py)."""

import hashlib
from unittest import TestCase

from steuerbote.ebilanz import defaults
from steuerbote.ebilanz.defaults import (
	CHARTS,
	DATEV_EDITION,
	DEFAULTS,
	REVISIONS,
	defaults_for,
	defaults_version,
)
from steuerbote.mappings.transfer import canonical_json
from steuerbote.xbrl import mapping
from steuerbote.xbrl.mapping import Defaults
from steuerbote.xbrl.tests import real
from steuerbote.xbrl.versions import TAXONOMIES

DIGESTS = {
	"SKR03 Taxonomie 6.9 2026.0": "15628a4764c7c1ca0ae085ab0c50a1b8dce1c7275884704fb5015eb354a6ca95",
	"SKR04 Taxonomie 6.9 2026.0": "15628a4764c7c1ca0ae085ab0c50a1b8dce1c7275884704fb5015eb354a6ca95",
}
"""The SHA-256 of the canonical JSON of the rows of each version of the defaults."""


class TablesTest(TestCase):
	def test_every_table_holds_exactly_the_versions_of_the_taxonomy(self):
		"""Every table keyed by the version holds exactly the versions of TAXONOMIES (steuerbote/xbrl/versions.py)."""
		self.assertEqual(set(DEFAULTS), set(TAXONOMIES))
		self.assertEqual(set(REVISIONS), set(TAXONOMIES))

	def test_each_version_has_the_defaults_of_skr03_and_skr04(self):
		self.assertEqual(CHARTS, frozenset({"SKR03", "SKR04"}))
		for version, charts in DEFAULTS.items():
			with self.subTest(version=version):
				self.assertEqual(set(charts), CHARTS)
				for chart, entry in charts.items():
					self.assertIsInstance(entry, Defaults)
					self.assertEqual((entry.chart, entry.taxonomy_version), (chart, version))

	def test_a_revision_of_0_holds_no_rows(self):
		"""Revision 0 is the empty table of the Bilanzzuordnung before the defaults of the DATEV charts: a mapping that
		took it over takes the first defaults with Vorgaben aktualisieren as changes of the defaults."""
		for version, revision in REVISIONS.items():
			for chart, entry in DEFAULTS[version].items():
				with self.subTest(version=version, chart=chart):
					self.assertGreaterEqual(revision, 0)
					if revision == 0:
						self.assertEqual((entry.rules, entry.watched, entry.excluded), ((), (), ()))

	def test_the_tables_are_read_only(self):
		with self.assertRaises(TypeError):
			DEFAULTS["6.10"] = DEFAULTS["6.9"]  # type: ignore[index]
		with self.assertRaises(TypeError):
			REVISIONS["6.9"] = 1  # type: ignore[index]


class DefaultsForTest(TestCase):
	def test_gives_the_defaults_of_a_chart_for_a_version(self):
		self.assertIs(defaults_for("SKR04", "6.9"), DEFAULTS["6.9"]["SKR04"])

	def test_a_chart_without_defaults_has_none(self):
		with self.assertRaisesRegex(
			KeyError, "no defaults of the Bilanzzuordnung for chart 'Eigener Kontenrahmen'"
		):
			defaults_for("Eigener Kontenrahmen", "6.9")
		with self.assertRaisesRegex(KeyError, "no defaults of the Bilanzzuordnung for the HGB-Taxonomie 6.8"):
			defaults_for("SKR03", "6.8")


class DefaultsVersionTest(TestCase):
	def test_the_version_names_the_chart_the_taxonomy_the_datev_edition_and_the_revision(self):
		self.assertEqual((DATEV_EDITION, dict(REVISIONS)), (2026, {"6.9": 0}))
		self.assertEqual(
			[defaults_version(chart, "6.9") for chart in sorted(CHARTS)],
			["SKR03 Taxonomie 6.9 2026.0", "SKR04 Taxonomie 6.9 2026.0"],
		)

	def test_a_chart_without_defaults_has_no_version(self):
		with self.assertRaisesRegex(
			KeyError, "no defaults of the Bilanzzuordnung for chart 'Eigener Kontenrahmen'"
		):
			defaults_version("Eigener Kontenrahmen", "6.9")

	def test_a_version_always_means_the_same_defaults(self):
		for version, charts in DEFAULTS.items():
			for chart, entry in charts.items():
				with self.subTest(version=version, chart=chart):
					digest = hashlib.sha256(canonical_json(entry.rows()).encode("utf-8")).hexdigest()
					self.assertEqual(
						digest,
						DIGESTS.get(defaults_version(chart, version)),
						f"The defaults of {chart} for the taxonomy {version} changed: raise REVISIONS[{version!r}] in "
						"steuerbote/ebilanz/defaults.py and pin the digest of the new version in DIGESTS.",
					)

	def test_the_docstring_describes_the_format_of_the_tables(self):
		for part in ("DefaultRule", "DefaultWatched", "DefaultExcluded", "REVISIONS", "defaults_version"):
			with self.subTest(part=part):
				self.assertIn(part, defaults.__doc__)


class PositionsTest(TestCase):
	"""Against the package of each version (steuerbote/xbrl/tests/real.py)."""

	def test_every_position_of_the_defaults_passes_the_checks_of_the_mapping(self):
		taxonomy = real.view()
		for chart, entry in DEFAULTS[taxonomy.version].items():
			with self.subTest(chart=chart):
				numbers = [rule.accounts.first for rule in entry.rules]
				self.assertEqual(
					[problem.message for problem in mapping.check(entry.for_accounts(numbers), taxonomy)], []
				)
