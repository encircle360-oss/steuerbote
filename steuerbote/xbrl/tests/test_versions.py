"""The table of the HGB-Taxonomien: which versions Steuerbote writes and for which fiscal years."""

from datetime import date
from unittest import TestCase

from steuerbote.eric import releases
from steuerbote.eric.datenart import bilanz
from steuerbote.xbrl.versions import (
	BASE_URL,
	LATEST,
	TAXONOMIES,
	UnknownTaxonomyError,
	allowed_for,
	for_fiscal_year,
	version_of,
)


class TableTest(TestCase):
	def test_writes_6_9(self):
		self.assertEqual(tuple(TAXONOMIES), ("6.9",))
		self.assertEqual(LATEST.version, "6.9")

	def test_holds_each_version_under_its_own_number(self):
		self.assertEqual([entry.version for entry in TAXONOMIES.values()], list(TAXONOMIES))

	def test_names_the_bmf_letter_that_publishes_6_9(self):
		"""BMF letter of 10 June 2025, „Veröffentlichung der Taxonomien 6.9 vom 1. April 2025“."""
		entry = TAXONOMIES["6.9"]
		self.assertEqual(entry.released, date(2025, 4, 1))
		self.assertEqual(entry.letter_date, date(2025, 6, 10))
		self.assertEqual(entry.reference, "IV C 6 - S 2133-b/00064/002/006")
		self.assertEqual(entry.bstbl, "BStBl I S. 1450")
		self.assertEqual(
			entry.letter,
			"BMF letter of 10 June 2025 (GZ IV C 6 - S 2133-b/00064/002/006, BStBl I S. 1450)",
		)

	def test_names_the_package_esteuer_publishes_with_its_checksum(self):
		entry = TAXONOMIES["6.9"]
		self.assertEqual(
			entry.archive_url,
			"https://www.esteuer.de/download/taxonomie_20250618/german-gaap-taxonomy-v6.9-2025-04-01-xbrl.zip",
		)
		self.assertEqual(
			entry.archive_sha256, "accd62202d73c036910fee118b30730f0392934afc9730617788e30a0480df87"
		)
		self.assertEqual(entry.archive_name, "german-gaap-taxonomy-v6.9-2025-04-01-xbrl.zip")

	def test_is_read_only(self):
		with self.assertRaises(TypeError):
			TAXONOMIES["6.10"] = TAXONOMIES["6.9"]  # type: ignore[index]
		with self.assertRaises(AttributeError):
			TAXONOMIES["6.9"].version = "6.10"  # type: ignore[misc]

	def test_the_table_agrees_with_the_taxonomy_of_the_plugin_checks(self):
		"""Laufzeitumgebung prüfen names the plugin of the E-Bilanz of a fiscal year from releases.BILANZ_TAXONOMIES;
		both tables say the same for a calendar fiscal year."""
		for year, version in releases.BILANZ_TAXONOMIES.items():
			with self.subTest(year=year):
				self.assertEqual(for_fiscal_year(date(year, 1, 1), date(year, 12, 31)).version, version)


class ModulesTest(TestCase):
	"""Taxonomy modules, namespaces and entry points as the Technischer Leitfaden 6.9 names them (A.5, A.6, B.3)."""

	def setUp(self):
		self.entry = TAXONOMIES["6.9"]

	def test_names_the_modules_after_the_date_of_the_taxonomy(self):
		self.assertEqual((self.entry.gcd, self.entry.gaap), ("de-gcd-2025-04-01", "de-gaap-ci-2025-04-01"))

	def test_the_namespaces_live_under_xbrl_de(self):
		self.assertEqual(BASE_URL, "http://www.xbrl.de/taxonomies/")
		self.assertEqual(self.entry.gcd_namespace, "http://www.xbrl.de/taxonomies/de-gcd-2025-04-01")
		self.assertEqual(self.entry.gaap_namespace, "http://www.xbrl.de/taxonomies/de-gaap-ci-2025-04-01")

	def test_names_the_entry_points_by_their_path_in_the_package(self):
		self.assertEqual(self.entry.gcd_shell, "de-gcd-2025-04-01/de-gcd-2025-04-01-shell.xsd")
		self.assertEqual(
			self.entry.fiscal_shell, "de-gaap-ci-2025-04-01/de-gaap-ci-2025-04-01-shell-fiscal.xsd"
		)
		self.assertEqual(self.entry.commercial_shell, "de-gaap-ci-2025-04-01/de-gaap-ci-2025-04-01-shell.xsd")
		self.assertEqual(
			self.entry.microbilg_shell, "de-gaap-ci-2025-04-01/de-gaap-ci-2025-04-01-shell-microbilg.xsd"
		)

	def test_an_instance_references_an_entry_point_by_its_absolute_url(self):
		"""A.6: „Die Referenzen auf die Einstiegsschemas der Taxonomie ... sollten als Internetadressen (absolute
		URLs) mit dem Präfix "http://www.xbrl.de/taxonomies/" angegeben werden.“"""
		self.assertEqual(
			self.entry.url(self.entry.gcd_shell),
			"http://www.xbrl.de/taxonomies/de-gcd-2025-04-01/de-gcd-2025-04-01-shell.xsd",
		)

	def test_the_datenart_carries_the_version(self):
		self.assertEqual(self.entry.datenart, bilanz("6.9"))
		self.assertEqual(
			(self.entry.datenart.version, self.entry.datenart.plugin), ("Bilanz_6.9", "checkBilanz_6_9")
		)

	def test_the_operator_names_the_package_and_its_checksum_in_common_site_config(self):
		self.assertEqual(
			("steuerbote_taxonomy_6_9", "steuerbote_taxonomy_6_9_sha256"),
			(self.entry.config_key, self.entry.config_sha256_key),
		)


class FiscalYearTest(TestCase):
	"""„Die Taxonomien sind grundsätzlich für die Bilanzen der Wirtschaftsjahre zu verwenden, die nach dem 31. Dezember
	2025 beginnen (Wirtschaftsjahr 2026 oder 2026/2027). ... Es wird nicht beanstandet, wenn diese auch für das
	Wirtschaftsjahr 2025 oder 2025/2026 verwendet werden.“ (BMF letter of 10 June 2025); „Taxonomie letztmalig zu
	verwenden für Wirtschaftsjahre, die vor dem 31.12. xxxx enden“: 2027 (Übersicht über die Verwendung der
	Taxonomie-Versionen, Stand 03.06.2026)."""

	def test_6_9_is_the_taxonomy_of_the_fiscal_year_2026(self):
		self.assertEqual(for_fiscal_year(date(2026, 1, 1), date(2026, 12, 31)).version, "6.9")

	def test_and_of_a_fiscal_year_2026_2027(self):
		self.assertEqual(for_fiscal_year(date(2026, 7, 1), date(2027, 6, 30)).version, "6.9")

	def test_and_of_a_short_first_fiscal_year_in_2026(self):
		self.assertEqual(for_fiscal_year(date(2026, 3, 15), date(2026, 12, 31)).version, "6.9")

	def test_a_fiscal_year_2025_may_take_it_but_need_not(self):
		with self.assertRaises(UnknownTaxonomyError):
			for_fiscal_year(date(2025, 1, 1), date(2025, 12, 31))
		self.assertEqual(
			[entry.version for entry in allowed_for(date(2025, 1, 1), date(2025, 12, 31))], ["6.9"]
		)
		self.assertEqual(
			[entry.version for entry in allowed_for(date(2025, 7, 1), date(2026, 6, 30))], ["6.9"]
		)

	def test_a_fiscal_year_beginning_on_31_december_2025_may_take_it_but_need_not(self):
		with self.assertRaises(UnknownTaxonomyError):
			for_fiscal_year(date(2025, 12, 31), date(2026, 12, 30))
		self.assertEqual(
			[entry.version for entry in allowed_for(date(2025, 12, 31), date(2026, 12, 30))], ["6.9"]
		)

	def test_a_fiscal_year_beginning_on_31_december_2024_may_not_take_it(self):
		self.assertEqual([entry.version for entry in allowed_for(date(2024, 12, 31), date(2025, 12, 30))], [])

	def test_6_9_ends_with_the_fiscal_years_that_end_before_31_december_2027(self):
		self.assertEqual(for_fiscal_year(date(2026, 12, 31), date(2027, 12, 30)).version, "6.9")
		self.assertEqual([entry.version for entry in allowed_for(date(2027, 1, 1), date(2027, 12, 31))], [])
		with self.assertRaisesRegex(UnknownTaxonomyError, "2027-01-01 to 2027-12-31"):
			for_fiscal_year(date(2027, 1, 1), date(2027, 12, 31))

	def test_a_fiscal_year_ends_after_it_begins(self):
		with self.assertRaises(ValueError):
			for_fiscal_year(date(2026, 12, 31), date(2026, 1, 1))


class VersionOfTest(TestCase):
	def test_finds_a_version_by_its_number(self):
		self.assertIs(version_of("6.9"), TAXONOMIES["6.9"])

	def test_an_unknown_version_names_the_known_ones(self):
		with self.assertRaisesRegex(UnknownTaxonomyError, "6.9"):
			version_of("7.0")
