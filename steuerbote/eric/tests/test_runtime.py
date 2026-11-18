import hashlib
import json
import shutil
import tempfile
import warnings
import zipfile
from collections.abc import Mapping
from pathlib import Path
from unittest import TestCase, mock

from steuerbote.eric import runtime
from steuerbote.eric.runtime import (
	MANIFEST,
	RuntimeInfo,
	RuntimeInstallError,
	detect,
	install_from_archive,
	installations,
	is_beta,
	platform_check,
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
ELSEWHERE = {
	"META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\n",
	f"{ROOT}/Linux-x86_64/include/ericapi.h": b"/* header */",
	f"{ROOT}/Linux-x86_64/bin/ericSystemCheck": b"tool",
	f"{ROOT}/Linux-x86_64/Beispiel/ericdemo-python/eric.py": b"demo",
	f"{ROOT}/Windows-x86_64/dll/ericapi.dll": b"MZ",
}


def sha256(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


class ArchiveTestCase(TestCase):
	def setUp(self):
		self.directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-runtime-"))
		self.addCleanup(shutil.rmtree, self.directory)
		self.root = self.directory / "eric"

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
	def install_version(self, version: str, years: tuple[int, ...]) -> None:
		root = f"ERiC-{version}/Linux-x86_64/lib"
		members = {f"{root}/libericapi.so": b"ericapi", f"{root}/plugins2/libcommonData.so": b"commonData"}
		members |= {f"{root}/plugins2/libcheckUStVA_{year}.so": str(year).encode() for year in years}
		path, checksum = self.jar(members, name=f"ERiC-{version}-Linux-x86_64.jar")
		install_from_archive(path, checksum, self.root)

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
		self.assertEqual(detect(self.root, year=2026).version, "44.3.6.0")
		self.assertEqual(detect(self.root, year=2024).version, "44.1.4.0")
		self.assertEqual(detect(self.root).version, "44.3.6.0")

	def test_a_beta_only_when_allowed(self):
		self.assertIsNone(detect(self.root, year=2027))
		self.assertEqual(detect(self.root, year=2027, allow_beta=True).version, "45.1.5.0")
		self.assertEqual(detect(self.root, year=2026, allow_beta=True).version, "45.1.5.0")

	def test_no_runtime_for_a_year_without_its_plugin(self):
		self.assertIsNone(detect(self.root, year=2023, allow_beta=True))
		self.assertIsNone(detect(self.directory / "nowhere"))

	def test_passes_log_directory_and_hersteller_id_on(self):
		info = detect(self.root, year=2026, log_dir=self.directory / "logs" / "run", hersteller_id="12345")
		self.assertEqual((info.log_dir, info.hersteller_id), (self.directory / "logs" / "run", "12345"))


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


class StatusTest(ArchiveTestCase):
	def checks(self, **options) -> dict[str, tuple[bool, str]]:
		return {check.name: (check.ok, check.detail) for check in status(self.root, **options)}

	def test_without_a_runtime(self):
		checks = self.checks(year=2026, hersteller_id="")
		self.assertEqual(list(checks), ["platform", "runtime", "libraries", "plugin", "hersteller_id"])
		self.assertEqual(
			{name: ok for name, (ok, _) in checks.items() if name != "platform"},
			{"runtime": False, "libraries": False, "plugin": False, "hersteller_id": False},
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

	def test_names_the_problems(self):
		self.install(LIBRARIES)
		(self.root / "44.3.6.0" / "lib" / "libericapi.so").write_bytes(b"changed")
		checks = self.checks(year=2027, hersteller_id="74931")
		self.assertEqual(checks["libraries"], (False, "ERiC 44.3.6.0: verändert: libericapi.so"))
		self.assertFalse(checks["plugin"][0])
		self.assertIn("libcheckUStVA_2027.so", checks["plugin"][1])
		self.assertFalse(checks["hersteller_id"][0])

	def test_a_beta_serves_a_year_for_test_sends_only(self):
		root = "ERiC-45.1.5.0/Linux-x86_64/lib"
		members = {
			f"{root}/libericapi.so": b"ericapi",
			f"{root}/plugins2/libcommonData.so": b"commonData",
			f"{root}/plugins2/libcheckUStVA_2027.so": b"2027",
		}
		path, checksum = self.jar(members, name="ERiC-45.1.5.0-Linux-x86_64.jar")
		install_from_archive(path, checksum, self.root)
		ok, detail = self.checks(year=2027, hersteller_id="12345")["plugin"]
		self.assertFalse(ok)
		self.assertIn("Beta", detail)

	def test_without_a_year_the_plugin_check_is_left_out(self):
		self.assertNotIn("plugin", self.checks(hersteller_id="12345"))


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
			},
		)
		self.assertEqual(RuntimeInfo.from_dict(data), self.INFO)

	def test_refuses_data_of_the_wrong_shape(self):
		for data in ([], self.INFO.to_dict() | {"lib_dir": 1}, {"version": "44.3.6.0"}):
			with self.subTest(data=data), self.assertRaises(ValueError):
				RuntimeInfo.from_dict(data)
