import csv
import errno
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import warnings
import zipfile
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, mock

from steuerbote.eric import runtime
from steuerbote.eric.datenart import ZMDO, ustva
from steuerbote.eric.runtime import (
	MANIFEST,
	NO_GLIBC,
	OLD_GLIBC,
	OTHER_PACKAGE,
	PLATFORM_MESSAGES,
	UNSUPPORTED_SITE,
	Check,
	RuntimeInfo,
	RuntimeInstallError,
	RuntimeIntegrityError,
	UnsupportedPlatform,
	detect,
	install_from_archive,
	installations,
	is_beta,
	platform_check,
	platform_refusal,
	record_listed_versions,
	status,
	verify,
)

ROOT = "ERiC-44.3.6.0"
LIB = f"{ROOT}/Linux-x86_64/lib"
LIBRARIES = {
	f"{LIB}/libericapi.so": b"ericapi",
	f"{LIB}/libericxerces.so": b"xerces",
	f"{LIB}/libeSigner.so": b"esigner",
	f"{LIB}/plugins2/libcommonData.so": b"commonData",
	f"{LIB}/plugins2/libcheckUStVA_2025.so": b"2025",
	f"{LIB}/plugins2/libcheckUStVA_2026.so": b"2026",
}
# The plugin of the Zusammenfassende Meldung, the same for every year (Datenartversionmatrix.ods).
ZMDO_PLUGIN = {f"{LIB}/plugins2/libcheckZMDO.so": b"zmdo"}
ELSEWHERE = {
	"META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\n",
	f"{ROOT}/Linux-x86_64/include/ericapi.h": b"/* header */",
	f"{ROOT}/Linux-x86_64/bin/ericSystemCheck": b"tool",
	f"{ROOT}/Linux-x86_64/Beispiel/ericdemo-python/eric.py": b"demo",
	f"{ROOT}/Windows-x86_64/dll/ericapi.dll": b"MZ",
}
# ERiC needs Linux x86_64 with glibc 2.28 or newer; the tests that install take it as the platform of the site,
# whatever platform runs them: sys.platform, machine and glibc as os.confstr names it.
SUPPORTED_SITE = ("linux", "x86_64", "glibc 2.41")
TRANSLATIONS = Path(__file__).parents[2] / "translations" / "de.csv"
PLACEHOLDER = re.compile(r"\{\d+\}")


def sha256(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


class ArchiveTestCase(TestCase):
	site: tuple[str, str, str | None] | None = SUPPORTED_SITE
	"""The platform of the site the tests install on; None for the one that runs them."""

	def setUp(self):
		self.directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-runtime-"))
		self.addCleanup(shutil.rmtree, self.directory)
		self.root = self.directory / "eric"
		if self.site is not None:
			site = mock.patch.object(runtime, "_platform", return_value=self.site)
			site.start()
			self.addCleanup(site.stop)

	def jar(
		self, members: Mapping[str, bytes], name: str = "ERiC-44.3.6.0-Linux-x86_64.jar", **special
	) -> tuple[Path, str]:
		path = self.directory / name
		with zipfile.ZipFile(path, "w") as archive:
			for member, data in members.items():
				archive.writestr(member, data)
			for member, mode in special.get("modes", {}).items():
				info = zipfile.ZipInfo(member)
				info.external_attr = mode << 16
				archive.writestr(info, b"target")
			with warnings.catch_warnings(action="ignore", category=UserWarning):
				for member in special.get("duplicates", ()):
					archive.writestr(member, b"again")
		return path, sha256(path.read_bytes())

	def install(self, members: Mapping[str, bytes] = LIBRARIES | ELSEWHERE, **options) -> RuntimeInfo:
		path, checksum = self.jar(members)
		return install_from_archive(path, checksum, self.root, **options)

	def install_version(self, version: str, years: tuple[int, ...], plugins: tuple[str, ...] = ()) -> None:
		root = f"ERiC-{version}/Linux-x86_64/lib"
		members = {f"{root}/libericapi.so": b"ericapi", f"{root}/plugins2/libcommonData.so": b"commonData"}
		members |= {f"{root}/plugins2/libcheckUStVA_{year}.so": str(year).encode() for year in years}
		members |= {f"{root}/plugins2/lib{plugin}.so": plugin.encode() for plugin in plugins}
		path, checksum = self.jar(members, name=f"ERiC-{version}-Linux-x86_64.jar")
		install_from_archive(path, checksum, self.root)

	def assertRefused(self, members: Mapping[str, bytes], fragment: str, **special) -> None:
		path, checksum = self.jar(members, **special)
		with self.assertRaises(RuntimeInstallError) as raised:
			install_from_archive(path, checksum, self.root)
		self.assertIn(fragment, str(raised.exception))
		self.assertEqual(list(self.root.iterdir()) if self.root.exists() else [], [])


class InstallTest(ArchiveTestCase):
	def test_extracts_only_the_linux_libraries(self):
		info = self.install()
		version_dir = self.root / "44.3.6.0"
		self.assertEqual(
			sorted(str(path.relative_to(version_dir)) for path in version_dir.rglob("*") if path.is_file()),
			[
				"lib/libeSigner.so",
				"lib/libericapi.so",
				"lib/libericxerces.so",
				"lib/plugins2/libcheckUStVA_2025.so",
				"lib/plugins2/libcheckUStVA_2026.so",
				"lib/plugins2/libcommonData.so",
				MANIFEST,
			],
		)
		self.assertEqual((version_dir / "lib/libericapi.so").read_bytes(), b"ericapi")
		self.assertEqual(
			info,
			RuntimeInfo(
				version="44.3.6.0",
				lib_dir=version_dir / "lib",
				plugin_dir=version_dir / "lib",
				log_dir=self.root / "log",
				hersteller_id="",
			),
		)

	def test_writes_a_manifest_with_the_hashes(self):
		path, checksum = self.jar(LIBRARIES)
		install_from_archive(path, checksum.upper(), self.root, installed_by="Administrator")
		manifest = json.loads((self.root / "44.3.6.0" / MANIFEST).read_text())
		self.assertEqual(manifest["version"], "44.3.6.0")
		self.assertEqual(manifest["archive"], path.name)
		self.assertEqual(manifest["archive_sha256"], checksum)
		self.assertEqual(manifest["years"], [2025, 2026])
		self.assertIs(manifest["beta"], False)
		self.assertEqual(manifest["installed_by"], "Administrator")
		self.assertRegex(manifest["installed_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$")
		self.assertEqual(
			manifest["files"],
			{member.removeprefix(f"{LIB}/"): sha256(data) for member, data in LIBRARIES.items()},
		)

	def test_reads_the_version_from_the_archive_name_when_the_root_has_none(self):
		members = {member.replace(f"{ROOT}/", ""): data for member, data in LIBRARIES.items()}
		path, checksum = self.jar(members, name="ERiC-45.2.1.0-Linux-x86_64.jar")
		self.assertEqual(install_from_archive(path, checksum, self.root).version, "45.2.1.0")

	def test_probes_the_runtime_before_activating_it(self):
		probed = []

		def probe(info: RuntimeInfo) -> None:
			probed.append(info)
			self.assertTrue((info.lib_dir / "libericapi.so").is_file())
			self.assertFalse((self.root / "44.3.6.0").exists())

		self.install(probe=probe)
		(info,) = probed
		self.assertNotEqual(info.lib_dir, self.root / "44.3.6.0" / "lib")
		self.assertFalse(info.log_dir.exists())

	def test_records_the_product_versions_the_probe_reads(self):
		"""EricVersion names each library with its product version (EricVersion.xsd), which can differ from the version
		of the release (ERiC-Entwicklerhandbuch, Kap. 4.3); the Mindestversionsliste is compared with them."""
		versions = {
			"libericapi.so": "44, 3, 6, 0",
			"plugins2/libcheckUStVA_2026.so": "44, 3, 6, 0",
			"libeSigner.so": 65,
		}
		self.install(probe=lambda info: versions)
		manifest = json.loads((self.root / "44.3.6.0" / MANIFEST).read_text())
		self.assertEqual(
			manifest["library_versions"],
			{"libericapi.so": "44, 3, 6, 0", "libcheckUStVA_2026.so": "44, 3, 6, 0"},
		)
		(installation,) = installations(self.root)
		self.assertEqual(dict(installation.library_versions), manifest["library_versions"])

	def test_without_an_answer_of_the_probe_no_version_is_recorded(self):
		self.install(probe=lambda info: None)
		manifest = json.loads((self.root / "44.3.6.0" / MANIFEST).read_text())
		self.assertEqual(manifest["library_versions"], {})

	def test_reads_a_manifest_without_product_versions(self):
		self.install()
		path = self.root / "44.3.6.0" / MANIFEST
		manifest = json.loads(path.read_text())
		del manifest["library_versions"]
		for library_versions in (None, ["libericapi.so"], {"libericapi.so": 44}):
			with self.subTest(library_versions=library_versions):
				if library_versions is not None:
					manifest["library_versions"] = library_versions
				path.write_text(json.dumps(manifest))
				(installation,) = installations(self.root)
				self.assertEqual(dict(installation.library_versions), {})

	def test_records_the_product_versions_of_the_versionsinformationen_beside_those_of_the_probe(self):
		"""The Versionsinformationen of the package name the product version of every library, EricVersion only of
		those ERiC loaded (ERiC-Entwicklerhandbuch, Kap. 4.3 with footnote 21); steuerbote.eric.releases reads them."""
		self.install(LIBRARIES, probe=lambda info: {"libericapi.so": "44, 3, 4, 0", "libeSigner.so": ""})
		path = self.root / "44.3.6.0" / MANIFEST
		before = json.loads(path.read_text())
		(installation,) = installations(self.root)
		self.assertEqual((dict(installation.listed_versions), installation.listed_versions_source), ({}, ""))
		listed = {
			"libericapi.so": "44, 3, 4, 0",
			"libericxerces.so": "26, 8, 11, 0",
			"libeSigner.so": "65, 0, 1, 5",
			"libcommonData.so": "44, 3, 4, 0",
			"libcheckUStVA_2025.so": "44, 3, 2, 0",
			"libcheckUStVA_2026.so": "44, 3, 2, 0",
		}
		source = "https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Linux-x86_64.version.txt"
		recorded = record_listed_versions(installation, listed, source)
		manifest = json.loads(path.read_text())
		self.assertEqual(manifest, before | {"listed_versions": listed, "listed_versions_source": source})
		self.assertEqual(recorded, installations(self.root)[0])
		self.assertEqual(
			(
				dict(recorded.listed_versions),
				recorded.listed_versions_source,
				dict(recorded.library_versions),
			),
			(listed, source, {"libericapi.so": "44, 3, 4, 0", "libeSigner.so": ""}),
		)
		self.assertEqual(verify(recorded), ())

	def test_recording_the_versions_replaces_the_manifest_in_one_step(self):
		"""A run reads the manifest while a weekly check records the versions, so the manifest is never half written;
		it keeps its permissions."""
		self.install(LIBRARIES)
		path = self.root / "44.3.6.0" / MANIFEST
		path.chmod(0o640)
		before = path.read_bytes()
		(installation,) = installations(self.root)
		with (
			mock.patch.object(runtime.os, "replace", side_effect=OSError("No space left on device")),
			self.assertRaises(OSError),
		):
			record_listed_versions(installation, {"libericapi.so": "44, 3, 4, 0"}, "kopie")
		self.assertEqual(path.read_bytes(), before)
		self.assertEqual(sorted(entry.name for entry in path.parent.iterdir()), ["lib", MANIFEST])
		record_listed_versions(installation, {"libericapi.so": "44, 3, 4, 0"}, "kopie")
		self.assertEqual(path.stat().st_mode & 0o777, 0o640)
		self.assertEqual(sorted(entry.name for entry in path.parent.iterdir()), ["lib", MANIFEST])

	def test_a_manifest_that_vanished_is_no_installation_to_record_in(self):
		self.install(LIBRARIES)
		(installation,) = installations(self.root)
		shutil.rmtree(installation.path)
		with self.assertRaises(OSError):
			record_listed_versions(installation, {"libericapi.so": "44, 3, 4, 0"}, "kopie")

	def test_reads_a_manifest_without_the_versions_of_the_versionsinformationen(self):
		self.install()
		path = self.root / "44.3.6.0" / MANIFEST
		manifest = json.loads(path.read_text())
		for listed_versions, source in ((["libericapi.so"], 7), ({"libericapi.so": 44}, None)):
			with self.subTest(listed_versions=listed_versions):
				path.write_text(
					json.dumps(
						manifest | {"listed_versions": listed_versions, "listed_versions_source": source}
					)
				)
				(installation,) = installations(self.root)
				self.assertEqual(
					(dict(installation.listed_versions), installation.listed_versions_source), ({}, "")
				)

	def test_a_failing_probe_leaves_nothing_behind(self):
		def probe(info: RuntimeInfo) -> None:
			raise OSError("libgcc_s.so.1: cannot open shared object file")

		with self.assertRaises(RuntimeInstallError) as raised:
			self.install(probe=probe)
		self.assertIn("libgcc_s.so.1", str(raised.exception))
		self.assertEqual(list(self.root.iterdir()), [])

	def test_installing_the_same_archive_again_keeps_the_runtime(self):
		path, checksum = self.jar(LIBRARIES)
		first = install_from_archive(path, checksum, self.root)
		self.assertEqual(install_from_archive(path, checksum, self.root), first)

	def test_never_mixes_another_archive_into_an_installed_version(self):
		self.install()
		path, checksum = self.jar(LIBRARIES | {f"{LIB}/libotto.so": b"otto"})
		with self.assertRaises(RuntimeInstallError) as raised:
			install_from_archive(path, checksum, self.root)
		self.assertIn("bereits", str(raised.exception))


class RefusalTest(ArchiveTestCase):
	def test_refuses_a_wrong_checksum_before_extracting(self):
		path, _ = self.jar(LIBRARIES)
		with self.assertRaises(RuntimeInstallError) as raised:
			install_from_archive(path, "0" * 64, self.root)
		self.assertIn("SHA-256", str(raised.exception))
		self.assertFalse(self.root.exists())

	def test_refuses_a_checksum_of_another_shape(self):
		path, checksum = self.jar(LIBRARIES)
		for wrong in ("", checksum[:-1], checksum + "0", "g" * 64):
			with self.subTest(checksum=wrong), self.assertRaises(RuntimeInstallError):
				install_from_archive(path, wrong, self.root)

	def test_refuses_a_missing_archive(self):
		with self.assertRaises(RuntimeInstallError) as raised:
			install_from_archive(self.directory / "fehlt.jar", "0" * 64, self.root)
		self.assertIn("fehlt.jar", str(raised.exception))

	def test_refuses_an_archive_above_the_limit(self):
		path, checksum = self.jar(LIBRARIES)
		with (
			mock.patch.object(runtime, "MAX_ARCHIVE_BYTES", path.stat().st_size - 1),
			self.assertRaises(RuntimeInstallError),
		):
			install_from_archive(path, checksum, self.root)

	def test_refuses_a_file_that_is_no_zip_archive(self):
		path = self.directory / "ERiC-44.3.6.0-Linux-x86_64.jar"
		path.write_bytes(b"no archive")
		with self.assertRaises(RuntimeInstallError) as raised:
			install_from_archive(path, sha256(b"no archive"), self.root)
		self.assertIn("ZIP", str(raised.exception))

	def test_refuses_an_archive_without_linux_libraries(self):
		self.assertRefused(ELSEWHERE, "Linux-x86_64/lib")

	def test_refuses_an_archive_without_the_base_library_or_common_data(self):
		self.assertRefused(
			{member: data for member, data in LIBRARIES.items() if "libericapi" not in member},
			"libericapi.so",
		)
		self.assertRefused(
			{member: data for member, data in LIBRARIES.items() if "commonData" not in member},
			"libcommonData.so",
		)

	def test_refuses_paths_that_leave_the_library_directory(self):
		for member in (f"{LIB}/../../../evil.so", f"{LIB}/plugins2/./x.so", f"{LIB}/plugins2\\x.so"):
			with self.subTest(member=member):
				self.assertRefused(LIBRARIES | {member: b"evil"}, "Pfad")

	def test_refuses_links_and_special_files(self):
		self.assertRefused(LIBRARIES, "Link", modes={f"{LIB}/plugins2/link.so": 0o120777})

	def test_refuses_an_entry_that_appears_twice(self):
		self.assertRefused(LIBRARIES, "doppelt", duplicates=(f"{LIB}/libericapi.so",))

	def test_refuses_libraries_of_two_packages(self):
		other = {member.replace(ROOT, "ERiC-43.5.1.0"): data for member, data in LIBRARIES.items()}
		self.assertRefused(LIBRARIES | other, "Pakete")

	def test_refuses_an_archive_without_a_version(self):
		members = {member.replace(f"{ROOT}/", ""): data for member, data in LIBRARIES.items()}
		path, checksum = self.jar(members, name="eric-linux.jar")
		with self.assertRaises(RuntimeInstallError) as raised:
			install_from_archive(path, checksum, self.root)
		self.assertIn("Version", str(raised.exception))

	def test_refuses_an_archive_that_unpacks_above_the_limit(self):
		path, checksum = self.jar(LIBRARIES)
		with mock.patch.object(runtime, "MAX_EXTRACTED_BYTES", 10), self.assertRaises(RuntimeInstallError):
			install_from_archive(path, checksum, self.root)
		self.assertEqual(list(self.root.iterdir()) if self.root.exists() else [], [])

	def test_a_damaged_entry_leaves_nothing_behind(self):
		path, _ = self.jar(LIBRARIES)
		data = bytearray(path.read_bytes())
		position = data.index(b"ericapi")
		data[position] ^= 0xFF
		path.write_bytes(bytes(data))
		with self.assertRaises(RuntimeInstallError) as raised:
			install_from_archive(path, sha256(bytes(data)), self.root)
		self.assertIn("beschädigt", str(raised.exception))
		self.assertEqual(list(self.root.iterdir()), [])


class UnsupportedSiteTest(ArchiveTestCase):
	"""ERiC for Linux runs on Intel 64 and AMD64 (ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 2-1) with glibc 2.28 or
	newer (Kap. 2.4.4.5). On any other site the probe would fail only once the libraries are unpacked, so the
	installation refuses the site before it reads the archive."""

	site = None

	def test_refuses_a_site_on_arm64_before_it_reads_the_archive_or_writes_a_file(self):
		path, checksum = self.jar(LIBRARIES)
		probed = []
		for archive in (path, self.directory / "fehlt.jar"):
			with (
				self.subTest(archive=archive.name),
				mock.patch.object(runtime.platform, "machine", return_value="aarch64"),
				self.assertRaises(UnsupportedPlatform) as raised,
			):
				install_from_archive(archive, checksum, self.root, probe=probed.append)
			self.assertEqual(
				(raised.exception.template, raised.exception.values),
				(UNSUPPORTED_SITE, (sys.platform, "aarch64")),
			)
			self.assertEqual(
				str(raised.exception),
				f"ERiC runs on Linux x86_64 only; this site runs on {sys.platform} aarch64.",
			)
			self.assertIsInstance(raised.exception, RuntimeInstallError)
			self.assertFalse(self.root.exists())
		self.assertEqual(probed, [])

	def test_refuses_a_site_without_glibc_or_with_one_older_than_2_28(self):
		path, checksum = self.jar(LIBRARIES)
		for libc, template, values in (
			(None, NO_GLIBC, ()),
			("glibc 2.27", OLD_GLIBC, ("glibc 2.27",)),
		):
			with (
				self.subTest(libc=libc),
				mock.patch.object(runtime, "_platform", return_value=("linux", "x86_64", libc)),
				self.assertRaises(UnsupportedPlatform) as raised,
			):
				install_from_archive(path, checksum, self.root)
			self.assertEqual((raised.exception.template, raised.exception.values), (template, values))
			self.assertFalse(self.root.exists())

	def test_installs_on_linux_x86_64_with_glibc_2_28(self):
		path, checksum = self.jar(LIBRARIES)
		with mock.patch.object(runtime, "_platform", return_value=("linux", "x86_64", "glibc 2.28")):
			self.assertEqual(install_from_archive(path, checksum, self.root).version, "44.3.6.0")


class OtherPackageTest(ArchiveTestCase):
	"""ELSTER ships ERiC as a package per platform, ERiC-<version>-<os>.jar, which unpacks to the directory <os> below
	ERiC-<version> (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 3.1, Kap. 3.1.2 with Tabelle 3-1, Kap. 3.1.4 with
	Tabelle 3-2). Steuerbote installs the one for Linux-x86_64 only and refuses another, by its name or by what it holds,
	before it unpacks a file."""

	def assertRefusedAs(self, path: Path, checksum: str, other: str) -> None:
		with self.assertRaises(UnsupportedPlatform) as raised:
			install_from_archive(path, checksum, self.root)
		self.assertEqual(
			(raised.exception.template, raised.exception.values), (OTHER_PACKAGE, (path.name, other))
		)
		self.assertEqual(
			str(raised.exception),
			f"{path.name} is the ERiC package for {other}; Steuerbote installs only the one for Linux x86_64.",
		)
		self.assertFalse(self.root.exists())

	def test_refuses_a_package_whose_name_names_another_platform(self):
		"""Even with libraries for Linux inside: the name is what the operator chose and what the manifest records."""
		for other in ("AIX-ppc64", "Darwin-universal", "Linux-ppc64le", "Windows-x86", "Windows-x86_64"):
			with self.subTest(other=other):
				self.assertRefusedAs(*self.jar(LIBRARIES, name=f"ERiC-44.3.6.0-{other}.jar"), other)

	def test_refuses_a_package_named_for_another_platform_before_reading_it(self):
		missing = self.directory / "ERiC-44.3.6.0-Windows-x86_64.jar"
		self.assertRefusedAs(missing, "0" * 64, "Windows-x86_64")

	def test_refuses_a_package_that_holds_another_platform(self):
		for other, members in (
			("Windows-x86_64", {f"{ROOT}/Windows-x86_64/dll/ericapi.dll": b"MZ"}),
			("Linux-ppc64le", {f"{ROOT}/Linux-ppc64le/lib/libericapi.so": b"ericapi"}),
		):
			with self.subTest(other=other):
				self.assertRefusedAs(
					*self.jar(members | {"META-INF/MANIFEST.MF": b""}, name="eric.jar"), other
				)

	def test_a_name_without_a_platform_of_eric_leaves_the_platform_to_the_content(self):
		"""Only the platforms of Tabelle 3-1 count in a name, so a copy saved under another name installs by what it
		holds, here Linux-x86_64 beside another platform."""
		for name in ("ERiC-44.3.6.0-Linux-x86_64 (1).jar", "ERiC-44.3.6.0.jar", "eric.jar"):
			with self.subTest(name=name):
				path, checksum = self.jar(LIBRARIES | ELSEWHERE, name=name)
				self.assertEqual(install_from_archive(path, checksum, self.root).version, "44.3.6.0")
				shutil.rmtree(self.root)


class BetaTest(TestCase):
	def test_the_first_delivery_of_a_main_release_is_the_beta(self):
		self.assertTrue(is_beta("45.1.5.0"))
		self.assertFalse(is_beta("45.2.1.0"))
		self.assertFalse(is_beta("44.1.4.0"))
		self.assertFalse(is_beta("44.3.6.0"))

	def test_refuses_another_version_format(self):
		with self.assertRaises(ValueError):
			is_beta("44.3")


class InstallationsTest(ArchiveTestCase):
	def setUp(self):
		super().setUp()
		self.install_version("44.3.6.0", (2025, 2026))
		self.install_version("44.1.4.0", (2024, 2025, 2026))
		self.install_version("45.1.5.0", (2026, 2027))

	def test_lists_complete_installations_newest_first(self):
		(self.root / ".44.9.9.9-partial").mkdir()
		(self.root / "44.9.9.8").mkdir()
		(self.root / "44.9.9.7").mkdir()
		(self.root / "44.9.9.7" / MANIFEST).write_text("{no json")
		(self.root / "44.9.9.6").mkdir()
		(self.root / "44.9.9.6" / MANIFEST).write_text(json.dumps({"version": "44.9.9.5"}))
		(self.root / "log").mkdir()
		listed = installations(self.root)
		self.assertEqual(
			[installation.version for installation in listed], ["45.1.5.0", "44.3.6.0", "44.1.4.0"]
		)
		self.assertEqual([installation.beta for installation in listed], [True, False, False])
		self.assertEqual(listed[1].years, (2025, 2026))
		self.assertEqual(listed[1].lib_dir, self.root / "44.3.6.0" / "lib")

	def test_lists_nothing_without_a_root(self):
		self.assertEqual(installations(self.directory / "nowhere"), ())

	def test_a_year_uses_the_newest_runtime_that_is_no_beta(self):
		self.assertEqual(detect(self.root, datenart=ustva(2026)).version, "44.3.6.0")
		self.assertEqual(detect(self.root, datenart=ustva(2024)).version, "44.1.4.0")
		self.assertEqual(detect(self.root).version, "44.3.6.0")

	def test_a_beta_only_when_allowed_and_no_released_runtime_knows_the_year(self):
		self.assertIsNone(detect(self.root, datenart=ustva(2027)))
		self.assertEqual(detect(self.root, datenart=ustva(2027), allow_beta=True).version, "45.1.5.0")
		self.assertEqual(detect(self.root, datenart=ustva(2026), allow_beta=True).version, "44.3.6.0")
		self.assertEqual(detect(self.root, allow_beta=True).version, "44.3.6.0")

	def test_no_runtime_for_a_year_without_its_plugin(self):
		self.assertIsNone(detect(self.root, datenart=ustva(2023), allow_beta=True))
		self.assertIsNone(detect(self.directory / "nowhere"))

	def test_passes_log_directory_hersteller_id_and_the_confirmation_on(self):
		info = detect(
			self.root,
			datenart=ustva(2026),
			log_dir=self.directory / "logs" / "run",
			hersteller_id="12345",
			confirmed_privacy_notice=True,
		)
		self.assertEqual(
			(info.log_dir, info.hersteller_id, info.confirmed_privacy_notice),
			(self.directory / "logs" / "run", "12345", True),
		)

	def test_a_runtime_confirms_nothing_unless_told(self):
		self.assertFalse(detect(self.root, datenart=ustva(2026)).confirmed_privacy_notice)
		self.assertFalse(detect(self.root, datenart=ustva(2027), allow_beta=True).confirmed_privacy_notice)


class ZmdoInstallationsTest(ArchiveTestCase):
	"""The Zusammenfassende Meldung needs a runtime with the plugin checkZMDO, whatever its year."""

	def setUp(self):
		super().setUp()
		self.install_version("44.3.6.0", (2025, 2026))
		self.install_version("44.1.4.0", (2024, 2025, 2026), ("checkZMDO",))
		self.install_version("45.1.5.0", (2026, 2027), ("checkZMDO",))

	def test_takes_the_newest_released_runtime_with_check_zmdo(self):
		self.assertEqual(detect(self.root, datenart=ZMDO).version, "44.1.4.0")
		self.assertEqual(detect(self.root, datenart=ZMDO, allow_beta=True).version, "44.1.4.0")
		self.assertEqual(detect(self.root, datenart=ustva(2026)).version, "44.3.6.0")

	def test_a_beta_only_when_allowed_and_no_released_runtime_has_check_zmdo(self):
		shutil.rmtree(self.root / "44.1.4.0")
		self.assertIsNone(detect(self.root, datenart=ZMDO))
		self.assertEqual(detect(self.root, datenart=ZMDO, allow_beta=True).version, "45.1.5.0")


class VerifyTest(ArchiveTestCase):
	def test_an_untouched_installation_has_no_problems(self):
		self.install(LIBRARIES)
		(installation,) = installations(self.root)
		self.assertEqual(verify(installation), ())

	def test_names_changed_missing_and_unknown_files(self):
		self.install(LIBRARIES)
		lib = self.root / "44.3.6.0" / "lib"
		(lib / "libericapi.so").write_bytes(b"changed")
		(lib / "plugins2" / "libcheckUStVA_2025.so").unlink()
		(lib / "plugins" / "libcheckUStVA_2019.so").parent.mkdir()
		(lib / "plugins" / "libcheckUStVA_2019.so").write_bytes(b"foreign")
		(installation,) = installations(self.root)
		self.assertEqual(
			verify(installation),
			(
				"verändert: libericapi.so",
				"fehlt: plugins2/libcheckUStVA_2025.so",
				"unbekannt: plugins/libcheckUStVA_2019.so",
			),
		)

	def test_names_links_and_special_files_which_the_installation_never_makes(self):
		self.install(LIBRARIES)
		lib = self.root / "44.3.6.0" / "lib"
		elsewhere = self.directory / "elsewhere"
		elsewhere.mkdir()
		(elsewhere / "libericapi.so").write_bytes(b"ericapi")
		(lib / "libericapi.so").unlink()
		(lib / "libericapi.so").symlink_to(elsewhere / "libericapi.so")
		(lib / "plugins3").symlink_to(elsewhere, target_is_directory=True)
		os.mkfifo(lib / "plugins2" / "libcheckLStA_2026.so")
		(installation,) = installations(self.root)
		self.assertEqual(
			verify(installation),
			(
				"fehlt: libericapi.so",
				"unbekannt: plugins2/libcheckLStA_2026.so",
				"Link: libericapi.so",
				"Link: plugins3",
			),
		)


class IntegrityTest(ArchiveTestCase):
	"""Every run takes an installation only as its manifest describes it, so a planted or changed library of ERiC is
	never loaded, and the worker never receives certificate and PIN for it."""

	def setUp(self):
		super().setUp()
		self.archive = self.jar(LIBRARIES | ZMDO_PLUGIN)
		install_from_archive(*self.archive, self.root)
		self.lib = self.root / "44.3.6.0" / "lib"

	def assertRefusedToRun(self, *problems: str) -> None:
		for datenart in (ustva(2026), ZMDO):
			with self.subTest(datenart=datenart.name), self.assertRaises(RuntimeIntegrityError) as raised:
				detect(self.root, datenart=datenart, allow_beta=True, hersteller_id="12345")
			self.assertEqual((raised.exception.version, raised.exception.problems), ("44.3.6.0", problems))
			self.assertIn("ERiC 44.3.6.0", str(raised.exception))
			self.assertIn(problems[0], str(raised.exception))

	def test_an_untouched_runtime_runs(self):
		self.assertEqual(detect(self.root, datenart=ustva(2026)).version, "44.3.6.0")
		self.assertEqual(detect(self.root, datenart=ZMDO).version, "44.3.6.0")

	def test_a_changed_library_is_never_loaded(self):
		(self.lib / "libericapi.so").write_bytes(b"planted")
		self.assertRefusedToRun("verändert: libericapi.so")

	def test_a_planted_plugin_is_never_loaded(self):
		(self.lib / "plugins2" / "libcheckLStA_2026.so").write_bytes(b"planted")
		self.assertRefusedToRun("unbekannt: plugins2/libcheckLStA_2026.so")

	def test_a_missing_library_is_noticed_before_eric_is_loaded(self):
		(self.lib / "plugins2" / "libcommonData.so").unlink()
		self.assertRefusedToRun("fehlt: plugins2/libcommonData.so")

	def test_a_link_in_place_of_a_library_is_never_loaded(self):
		elsewhere = self.directory / "libericapi.so"
		elsewhere.write_bytes(b"ericapi")
		(self.lib / "libericapi.so").unlink()
		(self.lib / "libericapi.so").symlink_to(elsewhere)
		self.assertRefusedToRun("fehlt: libericapi.so", "Link: libericapi.so")

	def test_installing_the_same_archive_again_refuses_a_changed_runtime(self):
		(self.lib / "libericapi.so").write_bytes(b"planted")
		with self.assertRaises(RuntimeInstallError) as raised:
			install_from_archive(*self.archive, self.root)
		self.assertIn("verändert: libericapi.so", str(raised.exception))
		self.assertIn(str(self.root / "44.3.6.0"), str(raised.exception))


class PlatformTest(TestCase):
	def test_linux_x86_64_with_glibc_from_2_28(self):
		self.assertTrue(platform_check("linux", "x86_64", "glibc 2.28").ok)
		self.assertTrue(platform_check("linux", "x86_64", "glibc 2.41").ok)

	def test_refuses_other_platforms_and_old_or_missing_glibc(self):
		for system, machine, libc in (
			("darwin", "x86_64", None),
			("linux", "aarch64", "glibc 2.41"),
			("linux", "x86_64", "glibc 2.27"),
			("linux", "x86_64", None),
			("linux", "x86_64", "musl"),
		):
			with self.subTest(system=system, machine=machine, libc=libc):
				check = platform_check(system, machine, libc)
				self.assertFalse(check.ok)
				self.assertEqual(check.name, "platform")

	def test_names_what_refuses_a_platform_for_the_installation_to_translate(self):
		for site, template, values in (
			(("darwin", "arm64", None), UNSUPPORTED_SITE, ("darwin", "arm64")),
			(("linux", "aarch64", "glibc 2.41"), UNSUPPORTED_SITE, ("linux", "aarch64")),
			(("linux", "x86_64", None), NO_GLIBC, ()),
			(("linux", "x86_64", "musl"), NO_GLIBC, ()),
			(("linux", "x86_64", "glibc 2.27"), OLD_GLIBC, ("glibc 2.27",)),
		):
			with self.subTest(site=site):
				refusal = platform_refusal(*site)
				self.assertEqual((refusal.template, refusal.values), (template, values))
		self.assertIsNone(platform_refusal("linux", "x86_64", "glibc 2.28"))

	def test_the_status_page_shows_the_platform_in_german_as_the_installation_decides(self):
		"""„Laufzeitumgebung prüfen“ shows the texts of the operator, which are German, for the platform the installation
		takes and for each it refuses."""
		for site, ok, detail in (
			(("linux", "x86_64", "glibc 2.41"), True, "Linux x86_64 mit glibc 2.41."),
			(
				("linux", "aarch64", "glibc 2.41"),
				False,
				"ERiC läuft nur unter Linux x86_64, nicht unter linux aarch64.",
			),
			(("linux", "x86_64", None), False, "Keine glibc gefunden; ERiC braucht glibc 2.28 oder neuer."),
			(
				("linux", "x86_64", "glibc 2.27"),
				False,
				"ERiC braucht glibc 2.28 oder neuer, hier ist glibc 2.27.",
			),
		):
			with self.subTest(site=site):
				self.assertEqual(platform_check(*site), Check("platform", ok, detail))
				self.assertEqual(platform_refusal(*site) is None, ok)


class SiteTest(TestCase):
	"""The platform of the site as the status page and the installation read it: the system as sys.platform names it,
	the machine and the glibc that os.confstr names."""

	def test_reads_the_machine_and_the_glibc_of_the_site(self):
		with (
			mock.patch.object(runtime.platform, "machine", return_value="aarch64"),
			mock.patch.object(runtime.os, "confstr", return_value="glibc 2.41") as confstr,
		):
			self.assertEqual(runtime._platform(), (sys.platform, "aarch64", "glibc 2.41"))
		confstr.assert_called_once_with("CS_GNU_LIBC_VERSION")

	def test_a_site_whose_c_library_names_no_glibc_has_none(self):
		"""musl knows the name CS_GNU_LIBC_VERSION but not its value, so os.confstr raises OSError there, and a system
		without the name raises ValueError; platform.libc_ver of the standard library expects both as well."""
		for error in (
			OSError(errno.EINVAL, "Invalid argument"),
			ValueError("unrecognized configuration name"),
		):
			with self.subTest(error=error), mock.patch.object(runtime.os, "confstr", side_effect=error):
				self.assertIsNone(runtime._platform()[2])


class PlatformMessagesTest(TestCase):
	def test_every_refusal_of_a_platform_is_listed_for_its_translation(self):
		self.assertEqual(set(PLATFORM_MESSAGES), {UNSUPPORTED_SITE, NO_GLIBC, OLD_GLIBC, OTHER_PACKAGE})

	def test_every_refusal_of_a_platform_reads_in_german_with_its_placeholders(self):
		with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
			german = dict(csv.reader(file))
		self.assertEqual(sorted(set(PLATFORM_MESSAGES) - german.keys()), [])
		for template in PLATFORM_MESSAGES:
			with self.subTest(template=template):
				self.assertCountEqual(PLACEHOLDER.findall(german[template]), PLACEHOLDER.findall(template))


class StatusTest(ArchiveTestCase):
	def checks(self, **options) -> dict[str, tuple[bool, str]]:
		return {check.name: (check.ok, check.detail) for check in status(self.root, **options)}

	def test_without_a_runtime(self):
		checks = self.checks(year=2026, hersteller_id="")
		self.assertEqual(
			list(checks), ["platform", "runtime", "libraries", "plugin", "zmdo", "hersteller_id"]
		)
		self.assertEqual(
			{name: ok for name, (ok, _) in checks.items() if name != "platform"},
			{"runtime": False, "libraries": False, "plugin": False, "zmdo": False, "hersteller_id": False},
		)

	def test_with_a_runtime_for_the_year_and_a_hersteller_id(self):
		self.install(LIBRARIES)
		checks = self.checks(year=2026, hersteller_id="12345")
		self.assertEqual(checks["runtime"], (True, "ERiC 44.3.6.0 ist eingerichtet."))
		self.assertEqual(
			checks["libraries"], (True, "Alle 6 Bibliotheken von ERiC 44.3.6.0 sind unverändert.")
		)
		self.assertEqual(checks["plugin"], (True, "ERiC 44.3.6.0 prüft und sendet das Jahr 2026."))
		self.assertEqual(checks["hersteller_id"], (True, "Hersteller-ID 12345."))

	def test_names_the_plugin_check_zmdo_of_the_zusammenfassende_meldung(self):
		self.install(LIBRARIES)
		self.assertEqual(
			self.checks(hersteller_id="12345")["zmdo"],
			(False, "Für die Zusammenfassende Meldung (ZMDO) fehlt ERiC mit dem Plugin libcheckZMDO.so."),
		)
		shutil.rmtree(self.root)
		self.install(LIBRARIES | ZMDO_PLUGIN)
		self.assertEqual(
			self.checks(hersteller_id="12345")["zmdo"],
			(True, "ERiC 44.3.6.0 prüft und sendet die Zusammenfassende Meldung (ZMDO)."),
		)

	def test_names_the_problems(self):
		self.install(LIBRARIES)
		(self.root / "44.3.6.0" / "lib" / "libericapi.so").write_bytes(b"changed")
		checks = self.checks(year=2027, hersteller_id="74931")
		self.assertEqual(checks["libraries"], (False, "ERiC 44.3.6.0: verändert: libericapi.so"))
		self.assertFalse(checks["plugin"][0])
		self.assertIn("libcheckUStVA_2027.so", checks["plugin"][1])
		self.assertFalse(checks["hersteller_id"][0])

	def test_a_beta_serves_a_year_for_checks_and_test_sends_only(self):
		root = "ERiC-45.1.5.0/Linux-x86_64/lib"
		members = {
			f"{root}/libericapi.so": b"ericapi",
			f"{root}/plugins2/libcommonData.so": b"commonData",
			f"{root}/plugins2/libcheckUStVA_2027.so": b"2027",
		}
		path, checksum = self.jar(members, name="ERiC-45.1.5.0-Linux-x86_64.jar")
		install_from_archive(path, checksum, self.root)
		self.assertEqual(
			self.checks(year=2027, hersteller_id="12345")["plugin"],
			(False, "Das Jahr 2027 kennt nur die Beta ERiC 45.1.5.0: Prüfen und Testsenden, kein Senden."),
		)

	def test_a_beta_serves_the_zusammenfassende_meldung_for_checks_and_test_sends_only(self):
		root = "ERiC-45.1.5.0/Linux-x86_64/lib"
		members = {
			f"{root}/libericapi.so": b"ericapi",
			f"{root}/plugins2/libcommonData.so": b"commonData",
			f"{root}/plugins2/libcheckZMDO.so": b"zmdo",
		}
		path, checksum = self.jar(members, name="ERiC-45.1.5.0-Linux-x86_64.jar")
		install_from_archive(path, checksum, self.root)
		self.assertEqual(
			self.checks(hersteller_id="12345")["zmdo"],
			(
				False,
				"Die Zusammenfassende Meldung (ZMDO) kennt nur die Beta ERiC 45.1.5.0: Prüfen und Testsenden, "
				"kein Senden.",
			),
		)

	def test_the_plugin_of_the_year_is_noticed_while_it_fails(self):
		"""The weekly check of the versions tells the System Managers once of each failing check with a notice."""
		self.install(LIBRARIES)
		failing = {check.name: check.notice for check in status(self.root, year=2027, hersteller_id="12345")}
		self.assertEqual(failing["plugin"], "year 2027")
		self.assertEqual({name for name, notice in failing.items() if notice}, {"plugin"})
		passing = {check.name: check.notice for check in status(self.root, year=2026, hersteller_id="12345")}
		self.assertEqual(passing["plugin"], "")

	def test_without_a_year_the_plugin_check_is_left_out(self):
		checks = self.checks(hersteller_id="12345")
		self.assertNotIn("plugin", checks)
		self.assertIn("zmdo", checks)


class RuntimeInfoTest(TestCase):
	INFO = RuntimeInfo(
		"44.3.6.0", Path("/eric/44.3.6.0/lib"), Path("/eric/44.3.6.0/lib"), Path("/log"), "12345"
	)

	def test_crosses_the_process_boundary_as_json(self):
		data = json.loads(json.dumps(self.INFO.to_dict()))
		self.assertEqual(
			data,
			{
				"version": "44.3.6.0",
				"lib_dir": "/eric/44.3.6.0/lib",
				"plugin_dir": "/eric/44.3.6.0/lib",
				"log_dir": "/log",
				"hersteller_id": "12345",
				"confirmed_privacy_notice": False,
			},
		)
		self.assertEqual(RuntimeInfo.from_dict(data), self.INFO)
		confirmed = replace(self.INFO, confirmed_privacy_notice=True)
		self.assertEqual(RuntimeInfo.from_dict(json.loads(json.dumps(confirmed.to_dict()))), confirmed)

	def test_without_the_confirmation_nothing_is_confirmed(self):
		data = self.INFO.to_dict()
		del data["confirmed_privacy_notice"]
		self.assertFalse(RuntimeInfo.from_dict(data).confirmed_privacy_notice)

	def test_refuses_data_of_the_wrong_shape(self):
		for data in (
			[],
			self.INFO.to_dict() | {"lib_dir": 1},
			{"version": "44.3.6.0"},
			self.INFO.to_dict() | {"confirmed_privacy_notice": "ja"},
		):
			with self.subTest(data=data), self.assertRaises(ValueError):
				RuntimeInfo.from_dict(data)
