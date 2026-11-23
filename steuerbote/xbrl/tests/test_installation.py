"""The parsed taxonomy as JSON, and the installation of the package the operator names, against the mini taxonomy."""

import hashlib
import json
import os
import shutil
import stat
import tempfile
import warnings
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, mock

from steuerbote.eric.runtime import Check
from steuerbote.xbrl import taxonomy
from steuerbote.xbrl.taxonomy import (
	FORMAT,
	MANIFEST,
	TaxonomyError,
	View,
	dumps,
	install_from_archive,
	installations,
	installed,
	load,
	loads,
	status,
	verify,
)
from steuerbote.xbrl.tests import mini
from steuerbote.xbrl.versions import TAXONOMIES

VERSION = mini.VERSION


def sha256(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


class Directory(TestCase):
	def setUp(self):
		self.directory = Path(tempfile.mkdtemp(prefix="steuerbote-xbrl-install-"))
		self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
		self.root = self.directory / "taxonomy"


class CacheTest(Directory):
	"""The parsed view as JSON, so that a site reads it without parsing the package again (contract 2.7: „caches the
	parsed taxonomy as JSON“)."""

	def setUp(self):
		super().setUp()
		self.package = mini.write(self.directory / "package")

	def test_a_view_comes_back_as_it_was(self):
		for view in View:
			with self.subTest(view=view):
				loaded = load(self.package, VERSION, view)
				self.assertEqual(loads(dumps(loaded)), loaded)

	def test_what_comes_back_answers_as_the_view(self):
		loaded = load(self.package, VERSION, View.FISCAL)
		again = loads(dumps(loaded))
		self.assertEqual(again.tables, loaded.tables)
		self.assertEqual(
			again.substitutes("de-gcd:genInfo.report.id.reportStatus.head"),
			loaded.substitutes("de-gcd:genInfo.report.id.reportStatus.head"),
		)
		self.assertEqual(again.label("bs.eqLiab.equity.subscribed.corp"), "Gezeichnetes Kapital")
		self.assertTrue(again.presented("bs.ass"))

	def test_the_same_view_gives_the_same_text(self):
		self.assertEqual(
			dumps(load(self.package, VERSION, View.FISCAL)), dumps(load(self.package, VERSION, View.FISCAL))
		)

	def test_names_its_format(self):
		self.assertEqual(json.loads(dumps(load(self.package, VERSION, View.FISCAL)))["format"], FORMAT)

	def test_refuses_another_format(self):
		data = json.loads(dumps(load(self.package, VERSION, View.FISCAL)))
		data["format"] = FORMAT + 1
		with self.assertRaisesRegex(TaxonomyError, "format"):
			loads(json.dumps(data))

	def test_refuses_what_is_no_cache(self):
		for text in ("kein JSON", "[]", '{"format": 1}'):
			with self.subTest(text=text), self.assertRaises(TaxonomyError):
				loads(text)


class ArchiveCase(Directory):
	"""A test with archives of the mini taxonomy."""

	def archive(
		self,
		members: dict[str, bytes] | None = None,
		*,
		prefix: str = "",
		changed: dict[str, bytes] | None = None,
		**special,
	) -> tuple[Path, str]:
		package = mini.write(self.directory / f"source-{len(list(self.directory.glob('source-*')))}")
		for name, data in (changed or {}).items():
			(package / name).write_bytes(data)
		path = self.directory / VERSION.archive_name
		with zipfile.ZipFile(path, "w") as archive:
			for file in sorted(package.rglob("*")):
				if file.is_file():
					archive.write(file, prefix + file.relative_to(package).as_posix())
			for member, data in (members or {}).items():
				archive.writestr(member, data)
			for member, mode in special.get("modes", {}).items():
				info = zipfile.ZipInfo(member)
				info.external_attr = mode << 16
				archive.writestr(info, b"target")
			with warnings.catch_warnings(action="ignore", category=UserWarning):
				for member in special.get("duplicates", ()):
					archive.writestr(member, b"again")
		return path, sha256(path.read_bytes())

	def install(self, **options):
		path, checksum = self.archive(**options.pop("archive", {}))
		return install_from_archive(path, checksum, self.root, VERSION, **options)

	def assertRefused(self, fragment: str, **archive) -> None:
		path, checksum = self.archive(**archive)
		with self.assertRaises(TaxonomyError) as raised:
			install_from_archive(path, checksum, self.root, VERSION)
		self.assertIn(fragment, str(raised.exception))
		self.assertEqual(sorted(self.root.rglob("*")) if self.root.exists() else [], [])


class InstallTest(ArchiveCase):
	"""The operator downloads the package from esteuer.de and names it with its SHA-256 in common_site_config.json, as
	ERiC (steuerbote/eric/runtime.py); „Taxonomie einrichten“ checks the checksum before anything is unpacked, unpacks
	the package outside the site and keeps the parsed views as JSON."""

	def test_unpacks_the_package_and_keeps_each_view(self):
		installation = self.install(installed_by="administrator@example.com")
		directory = self.root / "6.9"
		self.assertEqual(installation.path, directory)
		self.assertEqual(installation.version, "6.9")
		self.assertEqual(installation.installed_by, "administrator@example.com")
		self.assertTrue((directory / "package" / mini.GCD / f"{mini.GCD}-shell.xsd").is_file())
		self.assertEqual(
			sorted(path.name for path in directory.iterdir()),
			sorted(["package", MANIFEST, *(f"{view.value}.json" for view in View)]),
		)
		for view in View:
			with self.subTest(view=view):
				self.assertEqual(installation.view(view), load(directory / "package", VERSION, view))

	def test_the_manifest_names_archive_checksum_files_and_views(self):
		path, checksum = self.archive()
		installation = install_from_archive(path, checksum, self.root, VERSION)
		manifest = json.loads((installation.path / MANIFEST).read_text(encoding="utf-8"))
		self.assertEqual(
			(manifest["version"], manifest["archive"], manifest["archive_sha256"], manifest["format"]),
			("6.9", VERSION.archive_name, checksum, FORMAT),
		)
		package = installation.path / "package"
		self.assertEqual(
			manifest["files"],
			{
				file.relative_to(package).as_posix(): sha256(file.read_bytes())
				for file in sorted(package.rglob("*"))
				if file.is_file()
			},
		)
		self.assertEqual(
			manifest["views"],
			{view.value: sha256((installation.path / f"{view.value}.json").read_bytes()) for view in View},
		)

	def test_the_installation_is_found_again(self):
		installation = self.install()
		self.assertEqual(installed(self.root, VERSION), installation)
		self.assertEqual(installations(self.root), (installation,))
		self.assertIsNone(installed(self.directory / "elsewhere", VERSION))
		self.assertEqual(installations(self.directory / "elsewhere"), ())

	def test_takes_a_package_below_a_directory_of_the_archive(self):
		installation = self.install(archive={"prefix": "xbrl/", "members": {"liesmich.txt": b"Hinweise"}})
		self.assertTrue((installation.path / "package" / mini.GCD / f"{mini.GCD}-shell.xsd").is_file())
		self.assertFalse((installation.path / "package" / "liesmich.txt").exists())
		self.assertTrue(installation.view(View.FISCAL).has("bs.ass"))

	def test_installing_the_same_archive_again_keeps_the_installation(self):
		path, checksum = self.archive()
		first = install_from_archive(path, checksum, self.root, VERSION)
		again = install_from_archive(path, checksum, self.root, VERSION, installed_by="someone@example.com")
		self.assertEqual(again, first)

	def test_refuses_another_archive_of_an_installed_version(self):
		self.install()
		path, checksum = self.archive(members={f"{mini.GCD}/zusatz.txt": b"anders"})
		with self.assertRaisesRegex(TaxonomyError, "aus einem anderen Archiv"):
			install_from_archive(path, checksum, self.root, VERSION)

	def test_refuses_the_same_archive_over_changed_files(self):
		path, checksum = self.archive()
		installation = install_from_archive(path, checksum, self.root, VERSION)
		(installation.path / "package" / mini.GCD / f"{mini.GCD}-shell.xsd").write_text(
			"verändert", encoding="utf-8"
		)
		with self.assertRaisesRegex(TaxonomyError, "weichen vom Manifest ab"):
			install_from_archive(path, checksum, self.root, VERSION)

	def test_the_same_archive_of_an_older_format_reads_the_package_again(self):
		path, checksum = self.archive()
		installation = install_from_archive(path, checksum, self.root, VERSION)
		manifest_path = installation.path / MANIFEST
		manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
		manifest["format"] = FORMAT - 1
		manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
		(installation.path / "fiscal.json").write_text("{}", encoding="utf-8")
		self.assertEqual(installed(self.root, VERSION).format, FORMAT - 1)
		renewed = install_from_archive(path, checksum, self.root, VERSION)
		self.assertEqual(renewed.format, FORMAT)
		self.assertEqual(verify(renewed), ())
		self.assertTrue(renewed.view(View.FISCAL).has("bs.ass"))

	def test_checks_the_checksum_before_anything_is_unpacked(self):
		path, _ = self.archive()
		with self.assertRaisesRegex(TaxonomyError, f"erwartet war {'0' * 64}"):
			install_from_archive(path, "0" * 64, self.root, VERSION)
		self.assertFalse(self.root.exists())

	def test_the_checksum_is_a_sha256_in_hex(self):
		path, checksum = self.archive()
		for value in ("", "ab" * 31, "xy" * 32):
			with self.subTest(value=value), self.assertRaisesRegex(TaxonomyError, "64 Hexadezimalziffern"):
				install_from_archive(path, value, self.root, VERSION)
		self.assertEqual(
			install_from_archive(path, f" {checksum.upper()} ", self.root, VERSION).version, "6.9"
		)

	def test_refuses_an_archive_it_cannot_read(self):
		with self.assertRaisesRegex(TaxonomyError, "lässt sich nicht lesen"):
			install_from_archive(self.directory / "fehlt.zip", "ab" * 32, self.root, VERSION)

	def test_refuses_a_file_that_is_no_zip(self):
		path = self.directory / "taxonomie.zip"
		path.write_bytes(b"kein Archiv")
		with self.assertRaisesRegex(TaxonomyError, "kein ZIP-Archiv"):
			install_from_archive(path, sha256(path.read_bytes()), self.root, VERSION)

	def test_refuses_an_archive_far_larger_than_the_package(self):
		path, checksum = self.archive()
		with (
			mock.patch.object(taxonomy, "MAX_ARCHIVE_BYTES", 1024),
			self.assertRaisesRegex(TaxonomyError, "größer"),
		):
			install_from_archive(path, checksum, self.root, VERSION)

	def test_refuses_an_archive_that_unpacks_to_far_more(self):
		path, checksum = self.archive()
		with (
			mock.patch.object(taxonomy, "MAX_EXTRACTED_BYTES", 1024),
			self.assertRaisesRegex(TaxonomyError, "entpackt größer"),
		):
			install_from_archive(path, checksum, self.root, VERSION)

	def test_refuses_an_archive_of_far_more_files(self):
		path, checksum = self.archive()
		with mock.patch.object(taxonomy, "MAX_MEMBERS", 3), self.assertRaisesRegex(TaxonomyError, "Dateien"):
			install_from_archive(path, checksum, self.root, VERSION)

	def test_refuses_paths_out_of_the_package(self):
		for member in (f"{mini.GCD}/../../aussen.xml", "/absolut.xml", f"{mini.GCD}\\fenster.xml"):
			with self.subTest(member=member):
				self.assertRefused("Unzulässiger Pfad", members={member: b"x"})

	def test_refuses_links_and_special_files(self):
		self.assertRefused(
			"Link oder eine Sonderdatei", modes={f"{mini.GCD}/verweis.xml": stat.S_IFLNK | 0o777}
		)

	def test_refuses_a_file_twice(self):
		self.assertRefused("doppelt", duplicates=(f"{mini.GCD}/{mini.GCD}-shell.xsd",))

	def test_refuses_an_archive_without_the_entry_points_of_the_version(self):
		path = self.directory / "anders.zip"
		with zipfile.ZipFile(path, "w") as archive:
			archive.writestr(f"{mini.GCD}/{mini.GCD}-shell.xsd", b"<xs:schema/>")
		with self.assertRaisesRegex(TaxonomyError, "HGB-Taxonomie 6.9 nicht.*shell-fiscal.xsd"):
			install_from_archive(path, sha256(path.read_bytes()), self.root, VERSION)
		self.assertEqual(sorted(self.root.rglob("*")) if self.root.exists() else [], [])

	def test_refuses_a_package_the_loader_cannot_read(self):
		self.assertRefused(
			"lässt sich nicht lesen",
			changed={f"{mini.GAAP}/{mini.GAAP}-presentation-balanceSheet.xml": b"<kaputt"},
		)

	def test_skips_the_directories_of_the_archive(self):
		installation = self.install(archive={"members": {f"{mini.GCD}/": b""}})
		self.assertTrue(installation.view(View.FISCAL).has("bs.ass"))

	def test_a_failure_while_unpacking_leaves_nothing_behind(self):
		path, checksum = self.archive()
		with (
			mock.patch.object(taxonomy, "_extract", side_effect=OSError("Datenträger voll")),
			self.assertRaisesRegex(TaxonomyError, "fehlgeschlagen: Datenträger voll"),
		):
			install_from_archive(path, checksum, self.root, VERSION)
		self.assertEqual(sorted(self.root.rglob("*")), [])

	def test_refuses_a_damaged_entry(self):
		path, _ = self.archive()
		with zipfile.ZipFile(path) as archive:
			names = archive.namelist()
		stored = self.directory / "beschädigt.zip"
		with zipfile.ZipFile(path) as source, zipfile.ZipFile(stored, "w", zipfile.ZIP_STORED) as target:
			for name in names:
				target.writestr(name, source.read(name))
		data = bytearray(stored.read_bytes())
		position = data.index(b"Bilanzsumme, Summe Aktiva")
		data[position] ^= 0x20
		stored.write_bytes(bytes(data))
		with self.assertRaisesRegex(TaxonomyError, "beschädigt"):
			install_from_archive(stored, sha256(bytes(data)), self.root, VERSION)


class InstallationFilesTest(ArchiveCase):
	def test_verify_names_changed_missing_and_unknown_files(self):
		installation = self.install()
		package = installation.path / "package"
		(package / mini.GCD / f"{mini.GCD}-shell.xsd").write_text("verändert", encoding="utf-8")
		(package / mini.GAAP / f"{mini.GAAP}-shell.xsd").unlink()
		(package / mini.GAAP / "fremd.xml").write_text("fremd", encoding="utf-8")
		(installation.path / "fiscal.json").write_text("{}", encoding="utf-8")
		(package / "verweis.xml").symlink_to(package / mini.GCD / f"{mini.GCD}-shell.xsd")
		self.assertEqual(
			verify(installation),
			(
				f"verändert: package/{mini.GCD}/{mini.GCD}-shell.xsd",
				"verändert: fiscal.json",
				f"fehlt: package/{mini.GAAP}/{mini.GAAP}-shell.xsd",
				f"unbekannt: package/{mini.GAAP}/fremd.xml",
				"Link: package/verweis.xml",
			),
		)

	def test_verify_names_a_missing_view_and_a_special_file(self):
		installation = self.install()
		(installation.path / "fiscal.json").unlink()
		os.mkfifo(installation.package / "rohr")
		self.assertEqual(verify(installation), ("fehlt: fiscal.json", "unbekannt: package/rohr"))
		with self.assertRaisesRegex(TaxonomyError, "fehlt"):
			installation.view(View.FISCAL)

	def test_a_view_whose_file_changed_is_not_read(self):
		installation = self.install()
		(installation.path / "commercial.json").write_text(
			dumps(installation.view(View.FISCAL)), encoding="utf-8"
		)
		with self.assertRaisesRegex(TaxonomyError, "verändert"):
			installation.view(View.COMMERCIAL)

	def test_a_view_of_an_older_format_asks_for_the_installation_again(self):
		installation = self.install()
		with self.assertRaisesRegex(TaxonomyError, "Taxonomie einrichten"):
			replace(installation, format=FORMAT - 1).view(View.FISCAL)

	def test_a_directory_without_its_manifest_is_no_installation(self):
		installation = self.install()
		(installation.path / MANIFEST).unlink()
		self.assertIsNone(installed(self.root, VERSION))
		(self.root / "unvollständig").mkdir()
		self.assertEqual(installations(self.root), ())

	def test_a_manifest_of_another_version_is_no_installation(self):
		installation = self.install()
		manifest_path = installation.path / MANIFEST
		manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
		manifest["version"] = "6.8"
		manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
		self.assertIsNone(installed(self.root, VERSION))
		manifest_path.write_text("kein JSON", encoding="utf-8")
		self.assertIsNone(installed(self.root, VERSION))


class StatusTest(ArchiveCase):
	"""What „Laufzeitumgebung prüfen“ reports of the taxonomy of each version: named in common_site_config.json,
	installed from that archive, and unchanged."""

	def configured(self, checksum: str | None) -> dict:
		return {VERSION.version: None if checksum is None else (Path("/srv/taxonomie/paket.zip"), checksum)}

	def status_of(self, checksum: str | None) -> Check:
		"""The check of the version of the mini taxonomy among those of every version."""
		(check,) = (
			found
			for found in status(self.root, self.configured(checksum))
			if found.name == f"taxonomy_{VERSION.version.replace('.', '_')}"
		)
		return check

	def test_an_installed_and_unchanged_taxonomy_is_reported(self):
		path, checksum = self.archive()
		install_from_archive(path, checksum, self.root, VERSION)
		check = self.status_of(checksum)
		self.assertEqual(
			(check.name, check.ok, check.detail),
			("taxonomy_6_9", True, "Die HGB-Taxonomie 6.9 ist eingerichtet und unverändert."),
		)

	def test_a_taxonomy_the_bench_does_not_name(self):
		check = self.status_of(None)
		self.assertFalse(check.ok)
		self.assertEqual(
			check.detail,
			"Die HGB-Taxonomie 6.9 ist nicht eingerichtet: steuerbote_taxonomy_6_9 und steuerbote_taxonomy_6_9_sha256 "
			"in common_site_config.json nennen ihr Paket nicht.",
		)

	def test_a_named_taxonomy_not_yet_installed(self):
		check = self.status_of("ab" * 32)
		self.assertFalse(check.ok)
		self.assertEqual(
			check.detail, "Die HGB-Taxonomie 6.9 ist noch nicht eingerichtet: „Taxonomie einrichten“."
		)

	def test_a_taxonomy_installed_from_another_archive(self):
		self.install()
		check = self.status_of("ab" * 32)
		self.assertFalse(check.ok)
		self.assertIn("aus einem anderen Archiv eingerichtet", check.detail)

	def test_a_taxonomy_whose_files_changed(self):
		path, checksum = self.archive()
		installation = install_from_archive(path, checksum, self.root, VERSION)
		(installation.path / "fiscal.json").write_text("{}", encoding="utf-8")
		check = self.status_of(checksum)
		self.assertFalse(check.ok)
		self.assertEqual(check.detail, "Die HGB-Taxonomie 6.9 weicht vom Manifest ab: verändert: fiscal.json")

	def test_a_taxonomy_of_an_older_format(self):
		path, checksum = self.archive()
		installation = install_from_archive(path, checksum, self.root, VERSION)
		manifest_path = installation.path / MANIFEST
		manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
		manifest["format"] = FORMAT - 1
		manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
		check = self.status_of(checksum)
		self.assertFalse(check.ok)
		self.assertIn("„Taxonomie einrichten“", check.detail)

	def test_reports_every_version_of_the_table(self):
		self.assertEqual([check.name for check in status(self.root, {})], ["taxonomy_6_9", "taxonomy_6_10"])
		self.assertEqual(tuple(TAXONOMIES), ("6.9", "6.10"))
