"""Whether the installed ERiC runtimes still transmit: the Mindestversionsliste of ELSTER and the plugin of the
coming year.

The Annahmeserver check the version of each ERiC library that processed a delivery: it must not be lower than its
Mindestversion, which ELSTER sets per platform for the plugin of each datenartVersion and for the other libraries,
and below it nothing can be sent (ERiC-Entwicklerhandbuch 44.3.6.0, cited as HB, Kap. 5.4.2). The licence obliges
the Softwarehersteller to check regularly whether the LfSt offers a new version or update of ERiC (Lizenzvertrag,
§ 5 Abs. 4) and to use the version it marks as Mindestversion (§ 5 Abs. 6).

The ERiC download page of the ELSTER developer area names the releases only after login. The „Mindestversionsliste“
it links is public (ERiC download page as of 23 November 2026): a YAML file at MINIMUM_LIST_URL with its own
version, then per Betriebssystem a bibliothekListe of libraries, each with its name, its Mindestversion as four
numbers separated by commas and, for the library every installation needs, verpflichtend: true, and a
datenartversionListe with the Mindestversionen of single datenartVersionen. ERiC for Linux x86_64 is the section
„Linux Intel“, whose libraries are named <library>.linux-so for the file <library>.so.

The libraries of a package carry product versions of their own, which can differ from the version of the release
(HB Kap. 4.3: ericapi.dll 37, 1, 2, 0 and eSigner.dll 54.0.0.1 in ERiC-37.1.3.0), and an update raises only the
versions of the libraries it changes (HB Kap. 3.5.4.1). So each library of an installation is compared by the
product version EricVersion() reported for it when the installation was probed (steuerbote.eric.runtime), and a
datenartVersion steuerbote sends by the version of its plugin, the library the Mindestversion of a datenartVersion
is set for (HB Kap. 5.4.2).

The list does not name the newest release. A new year comes with the main release, planned for mid November
(HB Kap. 2.3), and in April the Mindestversion rises (HB Kap. 2.3 and 5.4.2; on 27 April 2026 to the November
release ERiC 43, ERiC download page as of 23 November 2026), so from mid November the plugin of the coming year is
checked as well.

This module is pure Python and never imports Frappe. Its messages are German, for the operator.
"""

import email.utils
import json
import re
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

from steuerbote.eric.datenart import of_version, ustva
from steuerbote.eric.runtime import LIBRARY, Check, Installation, plugin_check, year_check

MINIMUM_LIST_URL = "https://www.elster.de/elsterweb/attachments/eric/eric_mindestversionsliste.yaml"
SYSTEM = "Linux Intel"
"""The Betriebssystem of the list for ERiC under Linux x86_64."""
LIBRARY_SUFFIX = ".linux-so"
"""How the section of Linux Intel names a library <library>.so."""
FETCH_TIMEOUT_SECONDS = 10.0
MAX_LIST_BYTES = 1 << 20
"""Far more than the list of 23 November 2026 with its 79 KB."""
MAIN_RELEASE_DUE = (11, 15)
"""Month and day from which the main release with the coming year is due: „Mitte November“ (HB Kap. 2.3)."""
SHOWN = 5
"""How many shortfalls of one runtime a check names before it counts the rest."""

type Version = tuple[int, int, int, int]

_VERSION = re.compile(r" *(\d+) *[.,] *(\d+) *[.,] *(\d+) *[.,] *(\d+) *")
_PAIR = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*):(?: +(?P<value>.*))?")
_UNSUPPORTED = tuple("[{&*!|>%@`")
"""Flow collections, anchors, aliases, tags, block scalars, directives and reserved indicators, none of which the
list uses."""
_UNREAD = (
	"die Versionen seiner Bibliotheken sind unbekannt, weil die Einrichtung sie nicht gelesen hat; das Verzeichnis "
	"der Version entfernen und sie neu einrichten"
)


class MinimumListError(ValueError):
	pass


@dataclass(frozen=True, slots=True)
class Minimum:
	name: str
	"""The file of a library under Linux, such as libericapi.so, or a datenartVersion, such as UStVA_2026."""
	version: Version
	mandatory: bool = False
	"""Whether every installation needs the library (verpflichtend: true)."""


@dataclass(frozen=True, slots=True)
class MinimumList:
	"""The section of Linux Intel of a Mindestversionsliste."""

	version: str
	"""The version of the list itself, such as 2.26.4.1, no version of ERiC."""
	libraries: tuple[Minimum, ...]
	datenartversionen: tuple[Minimum, ...] = ()

	@property
	def eric(self) -> Minimum | None:
		"""The Mindestversion of libericapi.so, the library of the API of ERiC."""
		return next((minimum for minimum in self.libraries if minimum.name == LIBRARY), None)

	def to_json(self) -> str:
		return json.dumps(
			{
				"version": self.version,
				"libraries": [_row(minimum) for minimum in self.libraries],
				"datenartversionen": [_row(minimum) for minimum in self.datenartversionen],
			},
			ensure_ascii=False,
			separators=(",", ":"),
		)

	@classmethod
	def from_json(cls, text: str) -> MinimumList:
		try:
			data = json.loads(text)
			if not isinstance(data["version"], str):
				raise TypeError("the version of the list is no text")
			return cls(
				data["version"],
				tuple(_from_row(row) for row in data["libraries"]),
				tuple(_from_row(row) for row in data["datenartversionen"]),
			)
		except (ValueError, KeyError, TypeError) as error:
			raise MinimumListError(
				f"Die gespeicherte Mindestversionsliste ist nicht lesbar: {error}"
			) from error


@dataclass(frozen=True, slots=True)
class FetchedList:
	text: str
	last_modified: datetime | None
	"""When the server says the list changed last (Last-Modified), in UTC."""


def parse_version(text: str) -> Version:
	"""A version of four numbers as the list writes it (43,2,6,0) and EricVersion a product version (44, 3, 6, 0 or
	54.0.0.1)."""
	match = _VERSION.fullmatch(text)
	if match is None:
		raise ValueError(f"{text!r} is no version of four numbers")
	major, minor, build, doc = (int(part) for part in match.groups())
	return major, minor, build, doc


def format_version(version: Version) -> str:
	return ".".join(str(part) for part in version)


def parse_list(text: str) -> MinimumList:
	"""The section of Linux Intel of the Mindestversionsliste; MinimumListError for a list of another form."""
	document = _load(text)
	version = document.get("version")
	if not isinstance(version, str):
		raise MinimumListError("Die Mindestversionsliste nennt keine eigene Version (version).")
	systems = document.get("betriebssystemListe")
	if not isinstance(systems, list):
		raise MinimumListError(f"Die Mindestversionsliste {version} hat keine betriebssystemListe.")
	system = next(
		(entry for entry in systems if isinstance(entry, dict) and entry.get("betriebssystem") == SYSTEM),
		None,
	)
	if system is None:
		raise MinimumListError(f"Die Mindestversionsliste {version} nennt kein Betriebssystem „{SYSTEM}“.")
	libraries = system.get("bibliothekListe")
	if not isinstance(libraries, list):
		raise MinimumListError(f"Die Mindestversionsliste {version} hat für {SYSTEM} keine bibliothekListe.")
	datenartversionen = system.get("datenartversionListe") or []
	if not isinstance(datenartversionen, list):
		raise MinimumListError(f"Die datenartversionListe von {SYSTEM} ist keine Liste.")
	return MinimumList(
		version,
		tuple(_minimum(entry, "bibliothekListe") for entry in libraries),
		tuple(_minimum(entry, "datenartversionListe") for entry in datenartversionen),
	)


def make_opener() -> urllib.request.OpenerDirector:
	"""An opener with the certificate store of the system and the proxies of the environment that follows no
	redirect."""
	return urllib.request.build_opener(_NoRedirect())


def fetch_list(
	opener: urllib.request.OpenerDirector | None = None, timeout_seconds: float = FETCH_TIMEOUT_SECONDS
) -> FetchedList:
	"""The Mindestversionsliste from MINIMUM_LIST_URL, fetched with a plain GET without credentials or cookies.

	Errors pass to the caller: urllib's URLError and HTTPError, also for a redirect, TimeoutError, a body that is no
	UTF-8, and MinimumListError for a body longer than MAX_LIST_BYTES.
	"""
	request = urllib.request.Request(MINIMUM_LIST_URL)
	with (opener or make_opener()).open(request, timeout=timeout_seconds) as answer:
		body = answer.read(MAX_LIST_BYTES + 1)
		last_modified = answer.headers.get("Last-Modified")
	if len(body) > MAX_LIST_BYTES:
		raise MinimumListError(f"Die Mindestversionsliste ist größer als {MAX_LIST_BYTES >> 20} MiB.")
	return FetchedList(body.decode("utf-8"), _http_date(last_modified))


def shortfalls(installation: Installation, minimum_list: MinimumList) -> tuple[str, ...]:
	"""What of the installation falls short of the list: each library or plugin of a datenartVersion of steuerbote
	below its Mindestversion, each mandatory library it lacks, and the libraries whose version it did not read.

	A library the list names but the installation lacks is no shortfall unless it is mandatory; a library the list
	does not name has no Mindestversion.
	"""
	compared = [(minimum, minimum.name, minimum.name) for minimum in minimum_list.libraries]
	compared += [
		(minimum, plugin, f"{plugin} ({minimum.name})")
		for minimum in minimum_list.datenartversionen
		if (plugin := _plugin_of(minimum.name)) is not None
	]
	below: list[str] = []
	missing: list[str] = []
	unread: dict[str, None] = {}
	for minimum, library, label in compared:
		if not installation.has_plugin(library):
			if minimum.mandatory:
				missing.append(f"{library} fehlt")
			continue
		version = _product_version(installation, library)
		if version is None:
			unread[library] = None
		elif version < minimum.version:
			below.append(
				f"{label} {format_version(version)} statt mindestens {format_version(minimum.version)}"
			)
	if not unread:
		return (*below, *missing)
	if not installation.library_versions:
		return (*missing, _UNREAD)
	return (*below, *missing, f"ohne gelesene Version: {_some(list(unread))}")


def minimum_check(installed: tuple[Installation, ...], minimum_list: MinimumList | None) -> Check:
	"""Whether every installed runtime reaches the Mindestversionsliste, noticed once per list and failing runtimes."""
	if minimum_list is None:
		return Check(
			"minimum",
			False,
			"Die Mindestversionsliste von ELSTER ist noch nicht geladen; die wöchentliche Prüfung der "
			"ERiC-Versionen lädt sie.",
		)
	name = f"Mindestversionsliste {minimum_list.version}"
	if not installed:
		return Check("minimum", False, f"Ohne ERiC-Laufzeit gibt es nichts mit der {name} zu vergleichen.")
	failing = [
		(installation, found)
		for installation in installed
		if (found := shortfalls(installation, minimum_list))
	]
	if failing:
		detail = "; ".join(
			f"ERiC {installation.version}: {_some(list(found))}" for installation, found in failing
		)
		return Check(
			"minimum",
			False,
			f"Abgleich mit der {name}: {detail}. Mit einer Bibliothek unter ihrer Mindestversion ist kein Datenversand "
			"möglich (ERiC-Entwicklerhandbuch, Kap. 5.4.2).",
			f"minimum {minimum_list.version} "
			+ " ".join(installation.version for installation, _ in failing),
		)
	verb = "erreicht" if len(installed) == 1 else "erreichen"
	eric = minimum_list.eric
	floor = f" ({LIBRARY} ab {format_version(eric.version)})" if eric is not None else ""
	versions = _enumeration([installation.version for installation in installed])
	return Check("minimum", True, f"ERiC {versions} {verb} die Mindestversionen der {name}{floor}.")


def next_year_check(installed: tuple[Installation, ...], today: date) -> Check:
	"""Whether a released runtime has the plugin of the coming year, which is due from mid November."""
	year = today.year + 1
	check = plugin_check(
		installed, ustva(year), "plugin_next", f"das Jahr {year}", notice=f"next-year {year}"
	)
	if check.ok or (today.month, today.day) >= MAIN_RELEASE_DUE:
		return check
	if any(installation.has_plugin(ustva(year).plugin_library) for installation in installed):
		return replace(check, ok=True, notice="")
	return Check(
		"plugin_next",
		True,
		f"Das Jahr {year} bringt erst das Hauptrelease von ERiC, das für Mitte November {today.year} geplant ist "
		"(ERiC-Entwicklerhandbuch, Kap. 2.3).",
	)


def checks(
	installed: tuple[Installation, ...], minimum_list: MinimumList | None, today: date
) -> tuple[Check, ...]:
	"""What „Laufzeitumgebung prüfen“ adds to steuerbote.eric.runtime.status: the Mindestversionsliste and the
	plugin of the coming year."""
	return minimum_check(installed, minimum_list), next_year_check(installed, today)


def notices(
	installed: tuple[Installation, ...], minimum_list: MinimumList | None, today: date
) -> tuple[Check, ...]:
	"""The failing checks the System Managers hear of: the plugin of the current year, the Mindestversionsliste and,
	from mid November, the plugin of the coming year. A site without a runtime uses no ERiC and hears of nothing."""
	if not installed:
		return ()
	found = (year_check(installed, today.year), *checks(installed, minimum_list, today))
	return tuple(check for check in found if not check.ok and check.notice)


def due(found: Iterable[Check], notified: Iterable[str]) -> tuple[Check, ...]:
	"""The checks among found whose notice has not been sent yet."""
	sent = set(notified)
	return tuple(check for check in found if check.notice not in sent)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
	"""Ends the fetch at a redirect: the list counts only from the address ELSTER publishes."""

	def redirect_request(self, req, fp, code, msg, headers, newurl):
		raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


def _http_date(value: str | None) -> datetime | None:
	if not value:
		return None
	try:
		moment = email.utils.parsedate_to_datetime(value)
	except TypeError, ValueError:
		return None
	return moment.astimezone(UTC) if moment.tzinfo else moment.replace(tzinfo=UTC)


def _row(minimum: Minimum) -> list[str | bool]:
	return [minimum.name, format_version(minimum.version), minimum.mandatory]


def _from_row(row: object) -> Minimum:
	name, version, mandatory = row
	if not isinstance(name, str) or not isinstance(version, str) or not isinstance(mandatory, bool):
		raise TypeError(f"{row!r} is no row of name, version and mandatory")
	return Minimum(name, parse_version(version), mandatory)


def _minimum(entry: object, where: str) -> Minimum:
	if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
		raise MinimumListError(f"Ein Eintrag der {where} von {SYSTEM} hat keinen Namen (name).")
	name = entry["name"]
	version = entry.get("version")
	if not isinstance(version, str):
		raise MinimumListError(f"„{name}“ in der {where} von {SYSTEM} hat keine Version (version).")
	try:
		parsed = parse_version(version)
	except ValueError:
		raise MinimumListError(
			f"„{name}“ in der {where} von {SYSTEM} hat die Version „{version}“, keine aus vier Zahlen."
		) from None
	mandatory = entry.get("verpflichtend", "false")
	if not isinstance(mandatory, str) or mandatory.lower() not in ("true", "false"):
		raise MinimumListError(f"„{name}“ in der {where} von {SYSTEM} hat verpflichtend: {mandatory}.")
	if where == "bibliothekListe" and name.endswith(LIBRARY_SUFFIX):
		name = name.removesuffix(LIBRARY_SUFFIX) + ".so"
	return Minimum(name, parsed, mandatory.lower() == "true")


def _plugin_of(datenart_version: str) -> str | None:
	"""The plugin file of a datenartVersion steuerbote sends, None for any other."""
	try:
		return of_version(datenart_version).plugin_library
	except ValueError:
		return None


def _product_version(installation: Installation, library: str) -> Version | None:
	reported = installation.library_versions.get(library)
	if reported is None:
		return None
	try:
		return parse_version(reported)
	except ValueError:
		return None


def _some(items: list[str]) -> str:
	if len(items) <= SHOWN:
		return ", ".join(items)
	return f"{', '.join(items[:SHOWN])} und {len(items) - SHOWN} weitere"


def _enumeration(items: list[str]) -> str:
	return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} und {items[-1]}"


# The subset of YAML the Mindestversionsliste is written in: block mappings and block sequences, keys, plain and
# quoted scalars, comments. Anything beyond it ends the reading with the line it stands in.


@dataclass(frozen=True, slots=True)
class _Line:
	number: int
	indent: int
	"""The column of the dash of an entry, or of the key."""
	entry: bool
	"""Whether the line begins an entry of a sequence, with a dash."""
	column: int
	"""The column of what follows the dash, or of the key."""
	key: str | None
	"""None for an entry that is a scalar, which only a sequence holds."""
	value: str | None
	"""None for a key whose value is the block below it, or for an empty value."""


def _load(text: str) -> dict[str, object]:
	lines = _lines(text)
	if not lines:
		return {}
	if lines[0].entry:
		raise _error(lines[0].number, "die Liste beginnt mit einem Eintrag statt mit einem Schlüssel")
	document, position = _mapping(lines, 0, lines[0].indent, entry=False)
	if position < len(lines):
		raise _error(lines[position].number, "unerwartete Einrückung")
	return document


def _lines(text: str) -> list[_Line]:
	lines: list[_Line] = []
	for number, raw in enumerate(text.splitlines(), start=1):
		if "\t" in raw:
			raise _error(number, "ein Tabulator statt Leerzeichen")
		content = raw.strip(" ")
		if not content or content.startswith("#") or (not lines and content == "---"):
			continue
		indent = len(raw) - len(raw.lstrip(" "))
		rest = content
		entry = rest.startswith("- ")
		column = indent
		if entry:
			after = rest[2:].lstrip(" ")
			column = indent + len(rest) - len(after)
			rest = after
		match = _PAIR.fullmatch(rest)
		if match is not None:
			lines.append(
				_Line(number, indent, entry, column, match["key"], _scalar(match["value"] or "", number))
			)
		elif entry:
			lines.append(_Line(number, indent, entry, column, None, _scalar(rest, number)))
		else:
			raise _error(number, "kein Schlüssel mit Doppelpunkt")
	return lines


def _scalar(text: str, number: int) -> str | None:
	"""A plain or quoted scalar, without a comment after it; None for nothing but a comment."""
	text = text.strip(" ")
	if not text or text.startswith("#"):
		return None
	if text.startswith(_UNSUPPORTED):
		raise _error(
			number,
			f"„{text}“: Anker, Verweise, Tags, Blockskalare und Flussschreibweise liest Steuerbote nicht",
		)
	if text[0] not in "'\"":
		return text.split(" #", 1)[0].rstrip(" ")
	quote = text[0]
	end = 1
	while (end := text.find(quote, end)) != -1 and quote == "'" and text[end + 1 : end + 2] == "'":
		end += 2
	rest = text[end + 1 :].strip(" ") if end != -1 else None
	if rest is None or (rest and not rest.startswith("#")):
		raise _error(number, f"die Anführung in „{text}“ endet nicht")
	inner = text[1:end]
	if quote == '"' and "\\" in inner:
		raise _error(number, f"„{text}“: Escape-Sequenzen liest Steuerbote nicht")
	return inner.replace("''", "'") if quote == "'" else inner


def _mapping(lines: list[_Line], position: int, column: int, *, entry: bool) -> tuple[dict[str, object], int]:
	"""The mapping whose keys stand in the column, from lines[position] on; with entry, its first key follows the
	dash of that line."""
	mapping: dict[str, object] = {}
	first = True
	while position < len(lines):
		line = lines[position]
		if not (first and entry) and (line.entry or line.indent != column):
			break
		first = False
		if line.key in mapping:
			raise _error(line.number, f"„{line.key}“ steht zweimal")
		position += 1
		if line.value is not None:
			mapping[line.key] = line.value
		elif position < len(lines) and (
			lines[position].indent > column or (lines[position].entry and lines[position].indent == column)
		):
			mapping[line.key], position = _block(lines, position)
		else:
			mapping[line.key] = None
	return mapping, position


def _block(lines: list[_Line], position: int) -> tuple[object, int]:
	line = lines[position]
	if line.entry:
		return _sequence(lines, position, line.indent)
	return _mapping(lines, position, line.indent, entry=False)


def _sequence(lines: list[_Line], position: int, indent: int) -> tuple[list[object], int]:
	sequence: list[object] = []
	while position < len(lines) and lines[position].entry and lines[position].indent == indent:
		line = lines[position]
		if line.key is None:
			sequence.append(line.value)
			position += 1
		else:
			item, position = _mapping(lines, position, line.column, entry=True)
			sequence.append(item)
	return sequence, position


def _error(number: int, problem: str) -> MinimumListError:
	return MinimumListError(
		f"Die Mindestversionsliste hat nicht die erwartete Form: Zeile {number}: {problem}."
	)
