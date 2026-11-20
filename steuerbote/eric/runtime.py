"""The ERiC runtime an operator installs: one directory per version, described by a manifest.

ERiC comes per platform as a signed JAR file, a ZIP archive, from the ELSTER developer area after login
and acceptance of the licence (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 3 and 3.1; ERiC-Tutorial, Kap. 2.5).
Unpacked, it holds ERiC-<version>/<os>/ with the libraries in lib and the plugins below it (Kap. 3.1.4,
Tabellen 3-2 and 3-3; the include path C:\\Eric\\ERiC-<version>\\Windows-x86\\include in Kap. 4.3), so
Linux-x86_64/lib is all steuerbote needs. Steuerbote never downloads ERiC: the operator provides the
archive and its SHA-256, and the checksum is verified before anything is unpacked.

Each version gets a directory of its own, because libraries of different packages must not be mixed
(Kap. 3.1.6.2), with its manifest steuerbote-runtime.json: the hashes of archive and files, the years of
its UStVA plugins and whether it is a beta. A version directory appears only complete, by renaming it
into place. The plugin commonData is always required (Kap. 3.1.6.1), the plugin of a year is
checkUStVA_<Jahr> (Datenartversionmatrix.ods) as the year table steuerbote/ustva/years.py names it, and
EricInitialisiere searches the library directory for plugins recursively (Kap. 4.1.1). ERiC runs on Linux x86_64
with glibc 2.28 or newer (Kap. 2.4.4.5).

A main release in November starts with a beta, from which no real case can be sent; its major number is
odd and the beta is its first delivery, <major>.1 (Kap. 2.3 with the graphic of the release cycle, and
Kap. 3.1.1). A beta checks and sends test cases, only a real send is refused (Kap. 5.4.3). Each April the
Mindestversion rises and older releases are rejected (Kap. 5.4.2), so a year uses the newest released
runtime with its plugin, and a beta only for a check or a test send of a year that no released runtime
knows yet.

Messages are German, for the operator. This module is pure Python and never imports Frappe.
"""

import hashlib
import hmac
import json
import os
import platform
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from steuerbote.eric.header import ILLUSTRATION_HERSTELLER_ID
from steuerbote.ustva.years import plugin_library, plugin_year

MANIFEST = "steuerbote-runtime.json"
PLATFORM = "Linux-x86_64"
LIBRARY = "libericapi.so"
COMMON_DATA = "libcommonData.so"
LOG_DIRECTORY = "log"
MIN_GLIBC = (2, 28)
MAX_ARCHIVE_BYTES = 1 << 30
MAX_EXTRACTED_BYTES = 4 << 30
"""Guards against an archive that unpacks to far more than the libraries of ERiC take."""

_CHUNK = 1 << 20
_VERSION = re.compile(r"\d+\.\d+\.\d+\.\d+")
_PACKAGE = re.compile(r"ERiC-(?P<version>\d+\.\d+\.\d+\.\d+)(?:-.*)?")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GLIBC = re.compile(r"glibc (?P<major>\d+)\.(?P<minor>\d+)")


class RuntimeInstallError(Exception):
	pass


@dataclass(frozen=True, slots=True)
class RuntimeInfo:
	"""What the worker needs to run ERiC once."""

	version: str
	lib_dir: Path
	"""The directory with libericapi.so."""
	plugin_dir: Path
	"""The pluginPfad of EricInitialisiere, searched recursively."""
	log_dir: Path
	"""Where ERiC writes eric.log."""
	hersteller_id: str
	confirmed_privacy_notice: bool = False
	"""Whether the ERiC Settings record that the privacy notices of the tax administration were confirmed,
	which the licence requires before ERiC is used (Lizenzvertrag, § 5 Abs. 1 und 2)."""

	def to_dict(self) -> dict[str, str | bool]:
		return {
			"version": self.version,
			"lib_dir": str(self.lib_dir),
			"plugin_dir": str(self.plugin_dir),
			"log_dir": str(self.log_dir),
			"hersteller_id": self.hersteller_id,
			"confirmed_privacy_notice": self.confirmed_privacy_notice,
		}

	@classmethod
	def from_dict(cls, data: object) -> RuntimeInfo:
		if not isinstance(data, Mapping):
			raise ValueError("a runtime is a JSON object")
		values = {
			name: data.get(name) for name in ("version", "lib_dir", "plugin_dir", "log_dir", "hersteller_id")
		}
		wrong = sorted(name for name, value in values.items() if not isinstance(value, str))
		if wrong:
			raise ValueError(f"the runtime needs text in {', '.join(wrong)}")
		confirmed = data.get("confirmed_privacy_notice", False)
		if not isinstance(confirmed, bool):
			raise ValueError("confirmed_privacy_notice of the runtime is true or false")
		return cls(
			values["version"],
			Path(values["lib_dir"]),
			Path(values["plugin_dir"]),
			Path(values["log_dir"]),
			values["hersteller_id"],
			confirmed,
		)


@dataclass(frozen=True, slots=True)
class Installation:
	"""An installed version as its manifest describes it."""

	version: str
	path: Path
	archive_sha256: str
	files: Mapping[str, str]
	"""SHA-256 of each file, by its path below lib."""
	years: tuple[int, ...]
	beta: bool
	installed_at: str
	installed_by: str

	@property
	def lib_dir(self) -> Path:
		return self.path / "lib"

	def runtime(
		self, *, log_dir: Path, hersteller_id: str, confirmed_privacy_notice: bool = False
	) -> RuntimeInfo:
		return RuntimeInfo(
			self.version, self.lib_dir, self.lib_dir, log_dir, hersteller_id, confirmed_privacy_notice
		)


@dataclass(frozen=True, slots=True)
class Check:
	name: str
	ok: bool
	detail: str


def is_beta(version: str) -> bool:
	"""True for the first delivery of a main release, the beta that sends test cases only."""
	if not _VERSION.fullmatch(version):
		raise ValueError(f"{version!r} is no ERiC version <major>.<minor>.<build>.<doc>")
	major, minor = (int(part) for part in version.split(".")[:2])
	return major % 2 == 1 and minor == 1


def install_from_archive(
	archive_path: Path,
	sha256: str,
	target_root: Path,
	*,
	installed_by: str = "",
	probe: Callable[[RuntimeInfo], object] | None = None,
) -> RuntimeInfo:
	"""Install the Linux x86_64 libraries of an ERiC archive into target_root/<version>.

	The checksum is verified first. probe, given the unpacked runtime, may load it before it is
	activated; any exception it raises cancels the installation. Installing the same archive again
	returns the installed runtime; another archive of an installed version is refused.
	"""
	expected = sha256.strip().lower()
	if not _SHA256.fullmatch(expected):
		raise RuntimeInstallError("Die SHA-256-Summe besteht aus 64 Hexadezimalziffern.")
	try:
		archive_file = archive_path.open("rb")
	except OSError as error:
		raise RuntimeInstallError(f"Das Archiv {archive_path} lässt sich nicht lesen: {error}") from error
	with archive_file:
		if os.fstat(archive_file.fileno()).st_size > MAX_ARCHIVE_BYTES:
			raise RuntimeInstallError(f"Das Archiv ist größer als {MAX_ARCHIVE_BYTES >> 20} MiB.")
		digest = hashlib.sha256()
		while chunk := archive_file.read(_CHUNK):
			digest.update(chunk)
		if not hmac.compare_digest(digest.hexdigest(), expected):
			raise RuntimeInstallError(
				f"Die SHA-256-Summe des Archivs ist {digest.hexdigest()}, erwartet war {expected}."
			)
		archive_file.seek(0)
		try:
			archive = zipfile.ZipFile(archive_file)
		except zipfile.BadZipFile as error:
			raise RuntimeInstallError(f"Das Archiv ist kein ZIP-Archiv (JAR): {error}") from error
		with archive:
			return _install(archive, archive_path.name, expected, target_root, installed_by, probe)


def installations(target_root: Path) -> tuple[Installation, ...]:
	"""The complete installations below target_root, newest version first."""
	if not target_root.is_dir():
		return ()
	found = [
		installation
		for path in target_root.iterdir()
		if _VERSION.fullmatch(path.name) and (installation := _read_manifest(path)) is not None
	]
	return tuple(sorted(found, key=lambda installation: _version_key(installation.version), reverse=True))


def detect(
	target_root: Path,
	*,
	year: int | None = None,
	allow_beta: bool = False,
	log_dir: Path | None = None,
	hersteller_id: str = "",
	confirmed_privacy_notice: bool = False,
) -> RuntimeInfo | None:
	"""The runtime for the year: the newest released installation with its plugin, else, if allow_beta, the
	newest beta with it.

	A beta refuses real cases only (Kap. 5.4.3), so Prüfen and Testsenden pass allow_beta=True and Senden
	passes False. Prüfen and Testsenden still get the released runtime whenever one knows the year, the one
	that Senden uses.
	"""
	with_plugin = [
		installation
		for installation in installations(target_root)
		if year is None or year in installation.years
	]
	chosen = next((installation for installation in with_plugin if not installation.beta), None)
	if chosen is None and allow_beta and with_plugin:
		chosen = with_plugin[0]
	if chosen is None:
		return None
	return chosen.runtime(
		log_dir=log_dir or target_root / LOG_DIRECTORY,
		hersteller_id=hersteller_id,
		confirmed_privacy_notice=confirmed_privacy_notice,
	)


def verify(installation: Installation) -> tuple[str, ...]:
	"""What differs from the manifest: changed, missing and unknown files below lib."""
	present = {
		path.relative_to(installation.lib_dir).as_posix(): path
		for path in installation.lib_dir.rglob("*")
		if path.is_file()
	}
	expected = installation.files
	changed = [
		name for name in sorted(expected) if name in present and _file_sha256(present[name]) != expected[name]
	]
	missing = [name for name in sorted(expected) if name not in present]
	unknown = sorted(present.keys() - expected.keys())
	return (
		*(f"verändert: {name}" for name in changed),
		*(f"fehlt: {name}" for name in missing),
		*(f"unbekannt: {name}" for name in unknown),
	)


def platform_check(system: str, machine: str, libc: str | None) -> Check:
	"""Whether ERiC for Linux x86_64 can run here; libc as os.confstr("CS_GNU_LIBC_VERSION") names it."""
	if system != "linux" or machine != "x86_64":
		return Check("platform", False, f"ERiC läuft nur unter Linux x86_64, nicht unter {system} {machine}.")
	match = _GLIBC.fullmatch(libc or "")
	if match is None:
		return Check("platform", False, "Keine glibc gefunden; ERiC braucht glibc 2.28 oder neuer.")
	version = (int(match["major"]), int(match["minor"]))
	if version < MIN_GLIBC:
		return Check("platform", False, f"ERiC braucht glibc 2.28 oder neuer, hier ist {libc}.")
	return Check("platform", True, f"Linux x86_64 mit {libc}.")


def status(target_root: Path, *, year: int | None = None, hersteller_id: str = "") -> tuple[Check, ...]:
	"""The checks of the status page: platform, runtime, libraries, plugin of the year, Hersteller-ID."""
	checks = [platform_check(*_platform())]
	installed = installations(target_root)
	newest = next((installation for installation in installed if not installation.beta), None)
	if newest is None:
		checks.append(
			Check("runtime", False, "Keine ERiC-Laufzeit eingerichtet, die echte Fälle senden darf.")
		)
		checks.append(Check("libraries", False, "Ohne ERiC-Laufzeit gibt es keine Bibliotheken zu prüfen."))
	else:
		checks.append(Check("runtime", True, f"ERiC {newest.version} ist eingerichtet."))
		problems = verify(newest)
		checks.append(
			Check("libraries", False, f"ERiC {newest.version}: {', '.join(problems)}")
			if problems
			else Check(
				"libraries",
				True,
				f"Alle {len(newest.files)} Bibliotheken von ERiC {newest.version} sind unverändert.",
			)
		)
	if year is not None:
		checks.append(_plugin_check(installed, year))
	checks.append(_hersteller_id_check(hersteller_id))
	return tuple(checks)


def _install(
	archive: zipfile.ZipFile,
	archive_name: str,
	archive_sha256: str,
	target_root: Path,
	installed_by: str,
	probe: Callable[[RuntimeInfo], object] | None,
) -> RuntimeInfo:
	members, prefix = _library_members(archive)
	version = _version(prefix, archive_name)
	names = {path.as_posix() for path in members.values()}
	if LIBRARY not in names:
		raise RuntimeInstallError(f"Im Archiv fehlt die Basisbibliothek {PLATFORM}/lib/{LIBRARY}.")
	if not any(PurePosixPath(name).name == COMMON_DATA for name in names):
		raise RuntimeInstallError(f"Im Archiv fehlt das Plugin {COMMON_DATA}, das ERiC immer braucht.")
	if sum(info.file_size for info in members) > MAX_EXTRACTED_BYTES:
		raise RuntimeInstallError(
			f"Die Bibliotheken im Archiv sind entpackt größer als {MAX_EXTRACTED_BYTES >> 30} GiB."
		)

	target = target_root / version
	installed = _read_manifest(target)
	if installed is not None and installed.archive_sha256 == archive_sha256:
		return installed.runtime(log_dir=target_root / LOG_DIRECTORY, hersteller_id="")
	if target.exists():
		raise RuntimeInstallError(f"ERiC {version} ist bereits aus einem anderen Archiv eingerichtet.")

	target_root.mkdir(parents=True, exist_ok=True)
	partial = Path(tempfile.mkdtemp(prefix=f".{version}-", dir=target_root))
	try:
		files = {
			path.as_posix(): _extract(archive, info, partial / "lib" / path) for info, path in members.items()
		}
		if probe is not None:
			with tempfile.TemporaryDirectory(prefix="steuerbote-eric-probe-") as log_dir:
				probe(RuntimeInfo(version, partial / "lib", partial / "lib", Path(log_dir), ""))
		manifest = {
			"version": version,
			"archive": archive_name,
			"archive_sha256": archive_sha256,
			"beta": is_beta(version),
			"years": sorted(
				year for name in files if (year := plugin_year(PurePosixPath(name).name)) is not None
			),
			"files": files,
			"installed_at": datetime.now(UTC).isoformat(timespec="seconds"),
			"installed_by": installed_by,
		}
		(partial / MANIFEST).write_text(
			json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
		)
		partial.rename(target)
	except RuntimeInstallError:
		shutil.rmtree(partial, ignore_errors=True)
		raise
	except Exception as error:
		shutil.rmtree(partial, ignore_errors=True)
		raise RuntimeInstallError(
			f"Die Einrichtung von ERiC {version} ist fehlgeschlagen: {error}"
		) from error
	return RuntimeInfo(version, target / "lib", target / "lib", target_root / LOG_DIRECTORY, "")


def _library_members(
	archive: zipfile.ZipFile,
) -> tuple[dict[zipfile.ZipInfo, PurePosixPath], tuple[str, ...]]:
	"""The entries below <prefix>/Linux-x86_64/lib with their paths below lib, and the prefix."""
	members: dict[zipfile.ZipInfo, PurePosixPath] = {}
	seen: set[str] = set()
	prefixes = set()
	for info in archive.infolist():
		parts = info.filename.split("/")
		start = next(
			(
				index
				for index in range(len(parts) - 2)
				if parts[index] == PLATFORM and parts[index + 1] == "lib"
			),
			None,
		)
		if start is None or info.is_dir():
			continue
		inside = parts[start + 2 :]
		if any(part in ("", ".", "..") or "\\" in part for part in inside):
			raise RuntimeInstallError(f"Unzulässiger Pfad im Archiv: {info.filename}")
		if stat.S_IFMT(info.external_attr >> 16) not in (0, stat.S_IFREG):
			raise RuntimeInstallError(f"Das Archiv enthält einen Link oder eine Sonderdatei: {info.filename}")
		if info.filename in seen:
			raise RuntimeInstallError(f"Das Archiv enthält {info.filename} doppelt.")
		seen.add(info.filename)
		prefixes.add(tuple(parts[:start]))
		members[info] = PurePosixPath(*inside)
	if not members:
		raise RuntimeInstallError(
			f"Das Archiv enthält keine ERiC-Bibliotheken für Linux x86_64 ({PLATFORM}/lib)."
		)
	if len(prefixes) > 1:
		raise RuntimeInstallError(
			"Das Archiv enthält Bibliotheken mehrerer Pakete; ERiC-Versionen dürfen nicht gemischt werden."
		)
	return members, prefixes.pop()


def _version(prefix: tuple[str, ...], archive_name: str) -> str:
	for candidate in (*reversed(prefix), Path(archive_name).stem):
		match = _PACKAGE.fullmatch(candidate)
		if match:
			return match["version"]
	raise RuntimeInstallError(
		f"Die Version von ERiC steht weder im Archiv (ERiC-<version>/) noch im Dateinamen {archive_name}."
	)


def _extract(archive: zipfile.ZipFile, info: zipfile.ZipInfo, destination: Path) -> str:
	destination.parent.mkdir(parents=True, exist_ok=True)
	digest = hashlib.sha256()
	try:
		with archive.open(info) as source, destination.open("xb") as target:
			while chunk := source.read(_CHUNK):
				digest.update(chunk)
				target.write(chunk)
	except zipfile.BadZipFile as error:
		raise RuntimeInstallError(f"Der Eintrag {info.filename} im Archiv ist beschädigt: {error}") from error
	destination.chmod(0o644)
	return digest.hexdigest()


def _read_manifest(path: Path) -> Installation | None:
	try:
		data = json.loads((path / MANIFEST).read_text(encoding="utf-8"))
		installation = Installation(
			version=data["version"],
			path=path,
			archive_sha256=data["archive_sha256"],
			files=MappingProxyType(dict(data["files"])),
			years=tuple(data["years"]),
			beta=data["beta"],
			installed_at=data["installed_at"],
			installed_by=data["installed_by"],
		)
	except OSError, ValueError, KeyError, TypeError:
		return None
	return installation if installation.version == path.name else None


def _plugin_check(installed: tuple[Installation, ...], year: int) -> Check:
	plugin = plugin_library(year)
	with_plugin = [installation for installation in installed if year in installation.years]
	released = next((installation for installation in with_plugin if not installation.beta), None)
	if released is not None:
		return Check("plugin", True, f"ERiC {released.version} prüft und sendet das Jahr {year}.")
	if with_plugin:
		return Check(
			"plugin",
			False,
			f"Das Jahr {year} kennt nur die Beta ERiC {with_plugin[0].version}: Prüfen und Testsenden, kein Senden.",
		)
	return Check("plugin", False, f"Für das Jahr {year} fehlt ERiC mit dem Plugin {plugin}.")


def _hersteller_id_check(hersteller_id: str) -> Check:
	if not re.fullmatch(r"\d{5}", hersteller_id):
		return Check("hersteller_id", False, "Die eigene Hersteller-ID (fünf Ziffern) ist nicht eingetragen.")
	if hersteller_id == ILLUSTRATION_HERSTELLER_ID:
		return Check(
			"hersteller_id",
			False,
			f"Die Hersteller-ID {hersteller_id} dient nur der Illustration und ist gesperrt.",
		)
	return Check("hersteller_id", True, f"Hersteller-ID {hersteller_id}.")


def _platform() -> tuple[str, str, str | None]:
	libc = os.confstr("CS_GNU_LIBC_VERSION") if "CS_GNU_LIBC_VERSION" in os.confstr_names else None
	return sys.platform, platform.machine(), libc


def _file_sha256(path: Path) -> str:
	digest = hashlib.sha256()
	with path.open("rb") as file:
		while chunk := file.read(_CHUNK):
			digest.update(chunk)
	return digest.hexdigest()


def _version_key(version: str) -> tuple[int, ...]:
	return tuple(int(part) for part in version.split("."))
