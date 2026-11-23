"""The Mindestversionsliste of ELSTER, compared with the installed runtimes, and the plugins of the coming year.

fixtures/eric_mindestversionsliste.yaml is an excerpt of the list as ELSTER published it at
releases.MINIMUM_LIST_URL on 23 November 2026 (list version 2.26.4.1, SHA-256 of the whole file
b8a2cff42586eb02605c855126b720e766002908a5b2f2c98f208e1ee0a95426): the first libraries of each Betriebssystem and
those of Linux Intel that steuerbote uses, with their lines unchanged and in their order.

fixtures/ERiC-44.3.6.0-Linux-x86_64.version.txt is an excerpt of the Versionsinformationen of the package ERiC
44.3.6.0 for Linux x86_64 as ELSTER published them at releases.versions_url("44.3.6.0") on 23 November 2026 (225
libraries, Last-Modified 13 September 2026, SHA-256 of the whole file
45f0bb38536b46989f29c87ce836151cb33da1b2930af922a0b3e05b6391bdf3): the base libraries and the plugins steuerbote
uses, with their lines unchanged, padding and tabs included, and in their order.
"""

import hashlib
import io
import json
import shutil
import tempfile
import urllib.error
import urllib.request
import urllib.response
import zipfile
from collections.abc import Mapping
from datetime import UTC, date, datetime
from email.message import Message
from pathlib import Path
from unittest import TestCase, mock

from steuerbote import hooks
from steuerbote.eric import releases, runtime
from steuerbote.eric.releases import (
	BILANZ_TAXONOMIES,
	FIRST_ANNUAL_YEAR,
	MAX_LIST_BYTES,
	MAX_VERSIONS_BYTES,
	MINIMUM_LIST_URL,
	FetchedList,
	Minimum,
	MinimumList,
	MinimumListError,
	VersionsError,
	annual_checks,
	checks,
	complete_versions,
	due,
	fetch_list,
	fetch_versions,
	format_version,
	minimum_check,
	next_year_check,
	notices,
	parse_list,
	parse_version,
	parse_versions,
	read_versions,
	shortfalls,
	unread,
	versions_url,
)
from steuerbote.eric.runtime import MANIFEST, Check, Installation, install_from_archive, installations, verify

FIXTURE = Path(__file__).parent / "fixtures" / "eric_mindestversionsliste.yaml"
PUBLISHED = FIXTURE.read_text(encoding="utf-8")
VERSIONS_FIXTURE = Path(__file__).parent / "fixtures" / "ERiC-44.3.6.0-Linux-x86_64.version.txt"
PUBLISHED_VERSIONS = VERSIONS_FIXTURE.read_text(encoding="utf-8")
VERSIONS_44 = "https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Linux-x86_64.version.txt"
# The files of the excerpt below Linux-x86_64/lib, which the archive of a test installs.
PACKAGE_44 = tuple(
	line.split("\t")[0].strip().removeprefix("Linux-x86_64/lib/") for line in PUBLISHED_VERSIONS.splitlines()
)
# The product versions of the excerpt by file name.
LISTED_44 = {
	"libcommonData.so": "44, 3, 4, 0",
	"libcheckUStVA_2016.so": "44, 3, 2, 0",
	"libcheckZMDO.so": "44, 3, 2, 0",
	"libcheckUStVA_2025.so": "44, 3, 2, 0",
	"libcheckUStVA_2026.so": "44, 3, 2, 0",
	"libericapi.so": "44, 3, 4, 0",
	"libotto.so": "44, 3, 6, 0",
	"libericxerces.so": "26, 8, 11, 0",
	"libeSigner.so": "65, 0, 1, 5",
}
# What the probe could read with EricVersion of ERiC 44.3.6.0, invented after the first run with the package on
# 23 November 2026: every library by name, but a product version only for some of them.
PROBED_44 = dict.fromkeys(LISTED_44, "") | {
	"libericapi.so": "44, 3, 4, 0",
	"libericxerces.so": "26, 8, 11, 0",
	"libcommonData.so": "44, 3, 4, 0",
}
VERSIONS_JOB = "steuerbote.steuerbote.doctype.eric_settings.eric_settings.check_versions"
# The product versions EricVersion could report for ERiC 44.3.6.0, invented after the pattern of the handbook.
CURRENT = {
	"libericapi.so": "44, 3, 6, 0",
	"libericxerces.so": "26, 2, 3, 0",
	"libeSigner.so": "65.0.1.5",
	"libotto.so": "44, 3, 6, 0",
	"libcommonData.so": "44, 3, 6, 0",
	"libcheckUStVA_2025.so": "44, 3, 6, 0",
	"libcheckUStVA_2026.so": "44, 3, 6, 0",
	"libcheckZMDO.so": "44, 3, 6, 0",
}
# Next to libericapi.so and libcommonData.so, which every installation needs.
OPTIONAL = (
	"libericxerces.so",
	"libeSigner.so",
	"libotto.so",
	"libcheckUStVA_2025.so",
	"libcheckUStVA_2026.so",
	"libcheckZMDO.so",
)


def listed(*entries: str, version: str = "2.27.4.1", system: str = "Linux Intel", extra: str = "") -> str:
	"""A Mindestversionsliste of the published form whose section of the system holds the entries."""
	return (
		f"version: {version}\nbetriebssystemListe:\n  - betriebssystem: {system}\n    bibliothekListe:\n"
		+ "".join(entries)
		+ extra
	)


def library(name: str, version: str, mandatory: str | None = None) -> str:
	text = f"      - name: {name}\n        version: {version}\n"
	return text + (f"        verpflichtend: {mandatory}\n" if mandatory is not None else "")


def versions_of(versions: Mapping[str, str]) -> str:
	"""Versionsinformationen of the published form for the files below lib: path, product version and file version,
	separated by tabs and padded with spaces."""
	return "".join(
		f"Linux-x86_64/lib/{path}\t{version:<20}\t2026, 44, 3, 6      \n"
		for path, version in versions.items()
	)


class VersionTest(TestCase):
	def test_reads_the_versions_of_the_list_and_of_eric_version(self):
		for text, version in (
			("43,2,6,0", (43, 2, 6, 0)),
			("44, 3, 6, 0", (44, 3, 6, 0)),
			("54.0.0.1", (54, 0, 0, 1)),
			(" 25,9,11,0 ", (25, 9, 11, 0)),
		):
			with self.subTest(text=text):
				self.assertEqual(parse_version(text), version)

	def test_a_version_has_four_numbers(self):
		for text in ("43,2,6", "43,2,6,0,1", "43;2;6;0", "", "v43.2.6.0", "43.2.6.x"):
			with self.subTest(text=text), self.assertRaises(ValueError):
				parse_version(text)

	def test_writes_a_version_with_dots(self):
		self.assertEqual(format_version((43, 2, 6, 0)), "43.2.6.0")

	def test_compares_number_by_number(self):
		self.assertLess(parse_version("43,2,4,0"), parse_version("43,2,6,0"))
		self.assertLess(parse_version("43,2,10,0"), parse_version("43,10,2,0"))
		self.assertLess(parse_version("43,9,9,9"), parse_version("44,0,0,0"))


class ParseListTest(TestCase):
	def test_reads_the_libraries_of_linux_intel_from_the_published_list(self):
		minimums = parse_list(PUBLISHED)
		self.assertEqual(minimums.version, "2.26.4.1")
		self.assertEqual(
			minimums.libraries,
			(
				Minimum("libericapi.so", (43, 2, 6, 0), mandatory=True),
				Minimum("libericxerces.so", (25, 9, 11, 0)),
				Minimum("libeSigner.so", (63, 0, 0, 1)),
				Minimum("libotto.so", (43, 2, 6, 0)),
				Minimum("libcheckUStVA_2016.so", (43, 2, 4, 0)),
				Minimum("libcheckUStVA_2025.so", (43, 2, 4, 0)),
				Minimum("libcheckUStVA_2026.so", (43, 2, 6, 0)),
				Minimum("libcheckZMDO.so", (43, 2, 4, 0)),
				Minimum("libcommonData.so", (43, 2, 6, 0)),
				Minimum("libcheckUStVA_2015.so", (43, 2, 6, 0)),
			),
		)
		self.assertEqual(
			minimums.datenartversionen,
			(
				Minimum("ElsterFSE_PersG_202401", (43, 4, 4, 0)),
				Minimum("ElsterFSE_KapG_202401", (43, 4, 4, 0)),
			),
		)
		self.assertEqual(minimums.eric, Minimum("libericapi.so", (43, 2, 6, 0), mandatory=True))

	def test_the_published_list_is_valid_yaml_of_the_shape_read(self):
		"""The fixture holds the lines of the published list as they were, so it keeps the indentation of the list:
		two spaces per level, a dash before each entry."""
		lines = PUBLISHED.splitlines()
		self.assertEqual(
			lines[:4],
			[
				"version: 2.26.4.1",
				"betriebssystemListe:",
				"  - betriebssystem: AIX",
				"    bibliothekListe:",
			],
		)
		self.assertIn("  - betriebssystem: Linux Intel", lines)
		self.assertIn("      - name: libericapi.linux-so", lines)

	def test_takes_only_the_section_of_linux_intel(self):
		names = {minimum.name for minimum in parse_list(PUBLISHED).libraries}
		self.assertFalse(
			names & {"libericapi.aix-so", "libericapi.dylib", "ericapi.dll", "libericapi.linuxpower-so"}
		)
		self.assertEqual(
			parse_list(
				listed(library("libericapi.aix-so", "43,2,6,0", "true"), system="AIX")
				+ "  - betriebssystem: Linux Intel\n    bibliothekListe:\n"
				+ library("libericapi.linux-so", "44,1,0,0", "true")
			).libraries,
			(Minimum("libericapi.so", (44, 1, 0, 0), mandatory=True),),
		)

	def test_refuses_a_list_without_linux_intel(self):
		with self.assertRaises(MinimumListError) as raised:
			parse_list(listed(library("libericapi.dylib", "43,2,6,0", "true"), system="macOS"))
		self.assertEqual(
			str(raised.exception),
			"Die Mindestversionsliste 2.27.4.1 nennt kein Betriebssystem „Linux Intel“.",
		)

	def test_a_library_is_mandatory_only_where_the_list_says_true(self):
		minimums = parse_list(
			listed(
				library("libericapi.linux-so", "43,2,6,0", "true"),
				library("libotto.linux-so", "43,2,6,0", "false"),
				library("libericxerces.linux-so", "25,9,11,0"),
			)
		)
		self.assertEqual([minimum.mandatory for minimum in minimums.libraries], [True, False, False])
		with self.assertRaises(MinimumListError) as raised:
			parse_list(listed(library("libericapi.linux-so", "43,2,6,0", "ja")))
		self.assertIn("verpflichtend", str(raised.exception))

	def test_a_name_without_the_suffix_of_linux_stays_as_it_is(self):
		self.assertEqual(
			parse_list(listed(library("libnew.so", "45,1,0,0"))).libraries,
			(Minimum("libnew.so", (45, 1, 0, 0)),),
		)

	def test_a_list_without_datenartversionen(self):
		minimums = parse_list(listed(library("libericapi.linux-so", "43,2,6,0", "true")))
		self.assertEqual(minimums.datenartversionen, ())

	def test_without_libericapi_the_list_names_no_minimum_of_eric(self):
		self.assertIsNone(parse_list(listed(library("libotto.linux-so", "43,2,6,0"))).eric)

	def test_refuses_a_list_missing_what_it_needs(self):
		for text, fragment in (
			("betriebssystemListe:\n  - betriebssystem: Linux Intel\n", "version"),
			("version: 2.26.4.1\n", "betriebssystemListe"),
			("version: 2.26.4.1\nbetriebssystemListe: Linux Intel\n", "betriebssystemListe"),
			("version: 2.26.4.1\nbetriebssystemListe:\n  - betriebssystem: Linux Intel\n", "bibliothekListe"),
			(listed("      - version: 43,2,6,0\n"), "name"),
			(listed("      - name: libotto.linux-so\n"), "version"),
			(listed(library("libotto.linux-so", "43.2.6")), "43.2.6"),
			(
				"version:\n  - 2\nbetriebssystemListe:\n  - betriebssystem: Linux Intel\n"
				"    bibliothekListe:\n" + library("libotto.linux-so", "43,2,6,0"),
				"version",
			),
			(listed("      - libotto.linux-so\n"), "name"),
			(
				listed(library("libotto.linux-so", "43,2,6,0"), extra="    datenartversionListe: keine\n"),
				"datenartversionListe",
			),
			("", "version"),
		):
			with self.subTest(text=text), self.assertRaises(MinimumListError) as raised:
				parse_list(text)
			self.assertIn(fragment, str(raised.exception))

	def test_reads_comments_blank_lines_quotes_and_keys_it_does_not_know(self):
		minimums = parse_list(
			"---\n"
			"# Mindestversionen\n"
			"version: '2.27.4.1'\n"
			"stand: 2027-04-26\n"
			"\n"
			"betriebssystemListe:\n"
			'- betriebssystem: "Linux Intel"\n'
			"  hinweis: neu\n"
			"  details:\n"
			"    stand: 2027-04-26\n"
			"    quelle: ELSTER\n"
			"  bibliothekListe:\n"
			"    - name: libericapi.linux-so  # die API\n"
			"      version: 44,1,2,0\n"
			"      verpflichtend: true\n"
			"      datum: 2027-04-26\n"
			"  pluginListe:\n"
			"    - name: x\n"
			"      werte:\n"
			"        - 1\n"
			"        - 2\n"
			"  leer:\n"
		)
		self.assertEqual(minimums.version, "2.27.4.1")
		self.assertEqual(minimums.libraries, (Minimum("libericapi.so", (44, 1, 2, 0), mandatory=True),))

	def test_refuses_yaml_beyond_the_shape_of_the_list(self):
		for text, fragment in (
			("version: 2.26.4.1\n\tbetriebssystemListe:\n", "Zeile 2"),
			("version: 2.26.4.1\nbetriebssystemListe: [a, b]\n", "Zeile 2"),
			("version: 2.26.4.1\nbetriebssystemListe: {a: b}\n", "Zeile 2"),
			("version: &erste 2.26.4.1\n", "Zeile 1"),
			("version: *erste\n", "Zeile 1"),
			("version: !!str 2.26.4.1\n", "Zeile 1"),
			("version: |\n  2.26.4.1\n", "Zeile 1"),
			("version: >\n  2.26.4.1\n", "Zeile 1"),
			("version: 2.26.4.1\nversion: 2.26.4.2\n", "zweimal"),
			("version: 2.26.4.1\n  name: x\n", "Zeile 2"),
			("version: 2.26.4.1\njust text\n", "Zeile 2"),
			("  - betriebssystem: Linux Intel\n", "Zeile 1"),
			('version: "2.26.4.1\n', "Zeile 1"),
			('version: "2.26\\4.1"\n', "Zeile 1"),
			("version: 2.26.4.1\n...\n", "Zeile 2"),
		):
			with self.subTest(text=text), self.assertRaises(MinimumListError) as raised:
				parse_list(text)
			self.assertIn(fragment, str(raised.exception))

	def test_a_single_quote_inside_single_quotes_is_doubled(self):
		minimums = parse_list(listed(library("libericapi.linux-so", "43,2,6,0", "true"), version="'2.26''4'"))
		self.assertEqual(minimums.version, "2.26'4")

	def test_crosses_the_settings_as_json_and_back(self):
		minimums = parse_list(PUBLISHED)
		stored = minimums.to_json()
		self.assertEqual(MinimumList.from_json(stored), minimums)
		self.assertEqual(json.loads(stored)["libraries"][0], ["libericapi.so", "43.2.6.0", True])

	def test_refuses_stored_json_of_another_shape(self):
		for text in (
			"",
			"[]",
			'{"version": "2.26.4.1"}',
			'{"version": 2, "libraries": [], "datenartversionen": []}',
			'{"version": "2.26.4.1", "libraries": [["libotto.so", "43.2.6.0"]], "datenartversionen": []}',
			'{"version": "2.26.4.1", "libraries": [["libotto.so", "43.2.6", false]], "datenartversionen": []}',
			'{"version": "2.26.4.1", "libraries": [["libotto.so", "43.2.6.0", 1]], "datenartversionen": []}',
			'{"version": "2.26.4.1", "libraries": [[7, "43.2.6.0", false]], "datenartversionen": []}',
			'{"version": "2.26.4.1", "libraries": [], "datenartversionen": [7]}',
		):
			with self.subTest(text=text), self.assertRaises(MinimumListError):
				MinimumList.from_json(text)


class FakeAnswer:
	"""What urllib's opener returns for an answer with status 200."""

	def __init__(self, body: bytes, last_modified: str | None = None) -> None:
		self.stream = io.BytesIO(body)
		self.headers = Message()
		if last_modified is not None:
			self.headers["Last-Modified"] = last_modified
		self.closed = False

	def read(self, size: int = -1) -> bytes:
		return self.stream.read(size)

	def __enter__(self) -> FakeAnswer:
		return self

	def __exit__(self, *exception) -> None:
		self.closed = True


class FakeOpener:
	"""Hands out one answer or raises one error, and keeps what it was asked."""

	def __init__(self, answer: FakeAnswer | None = None, error: Exception | None = None) -> None:
		self.answer = answer
		self.error = error
		self.calls: list[tuple[urllib.request.Request, float]] = []

	def open(self, request: urllib.request.Request, timeout: float) -> FakeAnswer:
		self.calls.append((request, timeout))
		if self.error is not None:
			raise self.error
		return self.answer


class FakeServer(urllib.request.BaseHandler):
	"""Answers in front of the handlers of urllib: the first request with a redirect to ``location``, every later one
	with a list of its own, which a fetch that follows the redirect would return."""

	handler_order = 100

	def __init__(self, status: int, location: str) -> None:
		self.status = status
		self.location = location
		self.asked: list[str] = []

	def https_open(self, request: urllib.request.Request) -> urllib.response.addinfourl:
		return self._answer(request)

	def http_open(self, request: urllib.request.Request) -> urllib.response.addinfourl:
		return self._answer(request)

	def _answer(self, request: urllib.request.Request) -> urllib.response.addinfourl:
		self.asked.append(request.full_url)
		headers = Message()
		if len(self.asked) == 1:
			headers["Location"] = self.location
			answer = urllib.response.addinfourl(io.BytesIO(b"moved"), headers, request.full_url, self.status)
		else:
			forged = listed(library("libericapi.linux-so", "1,0,0,0", "true")).encode()
			answer = urllib.response.addinfourl(io.BytesIO(forged), headers, request.full_url, 200)
		answer.msg = "Found"
		return answer


class FetchTest(TestCase):
	def test_gets_the_published_list_without_credentials_and_with_a_short_timeout(self):
		opener = FakeOpener(FakeAnswer(PUBLISHED.encode()))
		fetch_list(opener)
		((request, timeout),) = opener.calls
		self.assertEqual(
			(request.full_url, request.get_method(), request.data),
			("https://www.elster.de/elsterweb/attachments/eric/eric_mindestversionsliste.yaml", "GET", None),
		)
		self.assertEqual(request.full_url, MINIMUM_LIST_URL)
		self.assertEqual(
			[name for name, _ in request.header_items() if name.lower() in ("authorization", "cookie")], []
		)
		self.assertEqual(timeout, 10)

	def test_returns_the_text_and_when_the_server_says_it_changed(self):
		answer = FakeAnswer(PUBLISHED.encode(), last_modified="Fri, 28 Aug 2026 11:25:09 GMT")
		self.assertEqual(
			fetch_list(FakeOpener(answer)),
			FetchedList(PUBLISHED, datetime(2026, 8, 28, 11, 25, 9, tzinfo=UTC)),
		)
		self.assertTrue(answer.closed)

	def test_a_change_in_another_zone_is_kept_in_utc(self):
		answer = FakeAnswer(b"version: 1\n", last_modified="Fri, 28 Aug 2026 13:25:09 +0200")
		self.assertEqual(
			fetch_list(FakeOpener(answer)).last_modified, datetime(2026, 8, 28, 11, 25, 9, tzinfo=UTC)
		)

	def test_a_change_without_a_zone_is_taken_as_utc(self):
		answer = FakeAnswer(b"version: 1\n", last_modified="Fri, 28 Aug 2026 11:25:09 -0000")
		self.assertEqual(
			fetch_list(FakeOpener(answer)).last_modified, datetime(2026, 8, 28, 11, 25, 9, tzinfo=UTC)
		)

	def test_without_a_readable_time_of_change_it_stays_open(self):
		for value in (None, "", "gestern"):
			with self.subTest(value=value):
				answer = FakeAnswer(b"version: 1\n", last_modified=value)
				self.assertIsNone(fetch_list(FakeOpener(answer)).last_modified)

	def test_refuses_a_list_longer_than_the_limit(self):
		with self.assertRaises(MinimumListError) as raised:
			fetch_list(FakeOpener(FakeAnswer(b"x" * (MAX_LIST_BYTES + 1))))
		self.assertIn("1 MiB", str(raised.exception))
		self.assertEqual(len(fetch_list(FakeOpener(FakeAnswer(b"#" * MAX_LIST_BYTES))).text), MAX_LIST_BYTES)

	def test_leaves_errors_to_the_caller(self):
		for error in (
			urllib.error.URLError("Name or service not known"),
			TimeoutError("timed out"),
			urllib.error.HTTPError(MINIMUM_LIST_URL, 404, "Not Found", Message(), io.BytesIO(b"")),
		):
			with self.subTest(error=error), self.assertRaises(OSError):
				fetch_list(FakeOpener(error=error))
		with self.assertRaises(UnicodeDecodeError):
			fetch_list(FakeOpener(FakeAnswer(b"version: \xff\n")))

	def test_follows_no_redirect(self):
		"""The list comes from the address ELSTER publishes: a redirect, to another host, to plain HTTP or back to the
		same address, ends the fetch."""
		for status, location in (
			(301, "https://elster.example.org/eric_mindestversionsliste.yaml"),
			(302, "http://www.elster.de/elsterweb/attachments/eric/eric_mindestversionsliste.yaml"),
			(303, MINIMUM_LIST_URL),
			(307, "https://elster.example.org/eric_mindestversionsliste.yaml"),
			(308, "https://elster.example.org/eric_mindestversionsliste.yaml"),
		):
			opener = releases.make_opener()
			server = FakeServer(status, location)
			opener.add_handler(server)
			with self.subTest(status=status):
				with self.assertRaises(urllib.error.HTTPError) as raised:
					fetch_list(opener)
				self.assertEqual(raised.exception.code, status)
				self.assertEqual(server.asked, [MINIMUM_LIST_URL])

	def test_without_an_opener_it_takes_one_that_follows_no_redirect(self):
		opener = FakeOpener(FakeAnswer(b"version: 1\n"))
		with mock.patch.object(releases, "make_opener", return_value=opener) as made:
			fetch_list()
		made.assert_called_once_with()
		self.assertEqual(len(opener.calls), 1)


class ParseVersionsTest(TestCase):
	"""The Versionsinformationen of a package: per file its path, product version and file version, as the handbook
	shows them for ERiC-37.1.3.0-Windows-x86_64.jar (HB Kap. 4.3 with footnote 21)."""

	def test_reads_the_product_version_of_each_library_of_the_published_list(self):
		self.assertEqual(
			parse_versions(PUBLISHED_VERSIONS),
			{
				"plugins/libcommonData.so": "44, 3, 4, 0",
				"plugins/libcheckUStVA_2016.so": "44, 3, 2, 0",
				"plugins/libcheckZMDO.so": "44, 3, 2, 0",
				"plugins/libcheckUStVA_2025.so": "44, 3, 2, 0",
				"plugins/libcheckUStVA_2026.so": "44, 3, 2, 0",
				"libericapi.so": "44, 3, 4, 0",
				"libotto.so": "44, 3, 6, 0",
				"libericxerces.so": "26, 8, 11, 0",
				"libeSigner.so": "65, 0, 1, 5",
			},
		)

	def test_the_published_list_pads_its_columns_with_spaces(self):
		"""The fixture keeps the lines as ELSTER published them, so the reading is tested on their padding."""
		lines = PUBLISHED_VERSIONS.splitlines()
		self.assertIn("Linux-x86_64/lib/libotto.so   \t44, 3, 6, 0         \t2026, 44, 3, 6      ", lines)
		self.assertIn("Linux-x86_64/lib/libeSigner.so\t65, 0, 1, 5         \t65, 0, 1, 5         ", lines)
		self.assertEqual(sorted(parse_versions(PUBLISHED_VERSIONS)), sorted(PACKAGE_44))

	def test_reads_line_ends_of_windows_and_empty_lines(self):
		self.assertEqual(
			parse_versions("Linux-x86_64/lib/libericapi.so\t44, 3, 4, 0\t2026, 44, 3, 4\r\n\r\n"),
			{"libericapi.so": "44, 3, 4, 0"},
		)

	def test_leaves_out_what_lies_outside_the_libraries_of_linux(self):
		self.assertEqual(
			parse_versions(
				"Linux-x86_64/bin/ericSystemCheck\tneu\n"
				"Windows-x86_64/dll/ericapi.dll\t44, 3, 4, 0\t2026.44.3.4\n"
				"Linux-x86_64/lib/libericapi.so\t44, 3, 4, 0\t2026, 44, 3, 4\n"
			),
			{"libericapi.so": "44, 3, 4, 0"},
		)

	def test_refuses_text_of_another_form(self):
		for text, problem in (
			("", "nennen keine Bibliothek unter Linux-x86_64/lib/"),
			("Linux-x86_64/bin/ericSystemCheck\t44, 3, 6, 0\t2026, 44, 3, 6\n", "nennen keine Bibliothek"),
			(
				"Linux-x86_64/lib/libericapi.so 44, 3, 4, 0 2026, 44, 3, 4\n",
				"Zeile 1: keine drei durch Tabulatoren getrennten Spalten",
			),
			(
				"Linux-x86_64/lib/libericapi.so\t44, 3, 4, 0\n",
				"Zeile 1: keine drei durch Tabulatoren getrennten Spalten",
			),
			(
				"Linux-x86_64/lib/libericapi.so\t44, 3, 4, 0\t2026, 44, 3, 4\n"
				"Linux-x86_64/lib/libotto.so\t44, 3, 6\t2026, 44, 3, 6\n",
				"Zeile 2: die Produktversion „44, 3, 6“ hat keine vier Zahlen",
			),
			(
				"Linux-x86_64/lib/libericapi.so\t44, 3, 4, 0\t2026, 44, 3, 4\n" * 2,
				"Zeile 2: Linux-x86_64/lib/libericapi.so steht zweimal",
			),
			(
				"Linux-x86_64/lib/../libericapi.so\t44, 3, 4, 0\t2026, 44, 3, 4\n",
				"Zeile 1: unzulässiger Pfad Linux-x86_64/lib/../libericapi.so",
			),
			(
				"Linux-x86_64/lib/plugins//libcommonData.so\t44, 3, 4, 0\t2026, 44, 3, 4\n",
				"Zeile 1: unzulässiger Pfad",
			),
			(
				"Linux-x86_64/lib/plugins\\libcommonData.so\t44, 3, 4, 0\t2026, 44, 3, 4\n",
				"Zeile 1: unzulässiger Pfad",
			),
		):
			with self.subTest(text=text), self.assertRaises(VersionsError) as raised:
				parse_versions(text)
			self.assertIn(problem, str(raised.exception))
			self.assertTrue(str(raised.exception).startswith("Die Versionsinformationen "))

	def test_a_problem_reads_as_a_sentence_about_the_versionsinformationen(self):
		self.assertEqual(
			str(VersionsError("nennen keine Bibliothek unter Linux-x86_64/lib/")),
			"Die Versionsinformationen nennen keine Bibliothek unter Linux-x86_64/lib/.",
		)
		self.assertEqual(
			str(VersionsError("sind größer als 1 MiB", f"von {VERSIONS_44}")),
			f"Die Versionsinformationen von {VERSIONS_44} sind größer als 1 MiB.",
		)


class FetchVersionsTest(TestCase):
	"""ELSTER publishes the Versionsinformationen of every package without login next to its download."""

	def test_the_versionsinformationen_lie_next_to_the_package_of_their_version(self):
		self.assertEqual(versions_url("44.3.6.0"), VERSIONS_44)
		self.assertEqual(
			versions_url("45.1.5.0"),
			"https://download.elster.de/download/eric/eric_45/ERiC-45.1.5.0-Linux-x86_64.version.txt",
		)

	def test_gets_them_without_credentials_and_with_a_short_timeout(self):
		answer = FakeAnswer(PUBLISHED_VERSIONS.encode())
		opener = FakeOpener(answer)
		self.assertEqual(fetch_versions("44.3.6.0", opener), PUBLISHED_VERSIONS)
		((request, timeout),) = opener.calls
		self.assertEqual((request.full_url, request.get_method(), request.data), (VERSIONS_44, "GET", None))
		self.assertEqual(
			[name for name, _ in request.header_items() if name.lower() in ("authorization", "cookie")], []
		)
		self.assertEqual(timeout, 10)
		self.assertTrue(answer.closed)

	def test_refuses_versionsinformationen_longer_than_the_limit(self):
		with self.assertRaises(VersionsError) as raised:
			fetch_versions("44.3.6.0", FakeOpener(FakeAnswer(b"x" * (MAX_VERSIONS_BYTES + 1))))
		self.assertEqual(str(raised.exception), "Die Versionsinformationen sind größer als 1 MiB.")
		self.assertEqual(
			len(fetch_versions("44.3.6.0", FakeOpener(FakeAnswer(b"#" * MAX_VERSIONS_BYTES)))),
			MAX_VERSIONS_BYTES,
		)

	def test_leaves_errors_to_the_caller(self):
		for error in (
			urllib.error.URLError("Name or service not known"),
			TimeoutError("timed out"),
			urllib.error.HTTPError(VERSIONS_44, 404, "Not Found", Message(), io.BytesIO(b"")),
		):
			with self.subTest(error=error), self.assertRaises(OSError):
				fetch_versions("44.3.6.0", FakeOpener(error=error))
		with self.assertRaises(UnicodeDecodeError):
			fetch_versions("44.3.6.0", FakeOpener(FakeAnswer(b"Linux-x86_64/lib/\xff\n")))

	def test_follows_no_redirect(self):
		for status in (301, 302, 303, 307, 308):
			opener = releases.make_opener()
			server = FakeServer(status, "https://elster.example.org/ERiC-44.3.6.0-Linux-x86_64.version.txt")
			opener.add_handler(server)
			with self.subTest(status=status):
				with self.assertRaises(urllib.error.HTTPError) as raised:
					fetch_versions("44.3.6.0", opener)
				self.assertEqual(raised.exception.code, status)
				self.assertEqual(server.asked, [VERSIONS_44])

	def test_without_an_opener_it_takes_one_that_follows_no_redirect(self):
		opener = FakeOpener(FakeAnswer(PUBLISHED_VERSIONS.encode()))
		with mock.patch.object(releases, "make_opener", return_value=opener) as made:
			fetch_versions("44.3.6.0")
		made.assert_called_once_with()
		self.assertEqual(len(opener.calls), 1)


class InstalledTestCase(TestCase):
	"""Runtimes installed from invented archives, each with the product versions a probe reports for it."""

	def setUp(self):
		self.directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-releases-"))
		self.addCleanup(shutil.rmtree, self.directory)
		self.root = self.directory / "eric"
		# ERiC installs on Linux x86_64 with glibc only; the invented archives install whatever platform runs the tests.
		site = mock.patch.object(runtime, "_platform", return_value=("linux", "x86_64", "glibc 2.41"))
		site.start()
		self.addCleanup(site.stop)

	def install(
		self,
		version: str = "44.3.6.0",
		libraries: tuple[str, ...] = OPTIONAL,
		versions: Mapping[str, str] | None = CURRENT,
	) -> None:
		lib = f"ERiC-{version}/Linux-x86_64/lib"
		archive = self.directory / f"ERiC-{version}-Linux-x86_64.jar"
		with zipfile.ZipFile(archive, "w") as jar:
			jar.writestr(f"{lib}/libericapi.so", b"ericapi")
			jar.writestr(f"{lib}/plugins2/libcommonData.so", b"commonData")
			for name in libraries:
				folder = "plugins2/" if name.startswith("libcheck") else ""
				jar.writestr(f"{lib}/{folder}{name}", name.encode())
		checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
		probe = None if versions is None else (lambda info: dict(versions))
		install_from_archive(archive, checksum, self.root, probe=probe)

	def package(self, versions: Mapping[str, str] = PROBED_44) -> None:
		"""Install the files of the excerpt of the Versionsinformationen of ERiC 44.3.6.0, with the product versions the
		probe reads."""
		lib = "ERiC-44.3.6.0/Linux-x86_64/lib"
		archive = self.directory / "ERiC-44.3.6.0-Linux-x86_64.jar"
		with zipfile.ZipFile(archive, "w") as jar:
			for name in PACKAGE_44:
				jar.writestr(f"{lib}/{name}", name.encode())
		checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
		install_from_archive(archive, checksum, self.root, probe=lambda info: dict(versions))

	def listing(self, changes: Mapping[str, str]) -> bytes:
		"""The excerpt of the Versionsinformationen of ERiC 44.3.6.0 with other product versions by file name."""
		return versions_of(
			{
				name: changes.get(name.rsplit("/", 1)[-1], LISTED_44[name.rsplit("/", 1)[-1]])
				for name in PACKAGE_44
			}
		).encode()

	def installed(self) -> tuple[Installation, ...]:
		return installations(self.root)


class ShortfallTest(InstalledTestCase):
	def test_a_runtime_that_reaches_every_minimum(self):
		self.install()
		(installation,) = self.installed()
		self.assertEqual(shortfalls(installation, parse_list(PUBLISHED)), ())
		self.assertEqual(
			minimum_check(self.installed(), parse_list(PUBLISHED)),
			Check(
				"minimum",
				True,
				"ERiC 44.3.6.0 erreicht die Mindestversionen der Mindestversionsliste 2.26.4.1 "
				"(libericapi.so ab 43.2.6.0).",
			),
		)

	def test_names_each_library_below_its_minimum(self):
		self.install(
			"43.1.3.0",
			versions=CURRENT
			| {
				"libericapi.so": "43, 1, 2, 0",
				"libeSigner.so": "62.0.0.0",
				"libcheckUStVA_2026.so": "43, 1, 3, 0",
			},
		)
		check = minimum_check(self.installed(), parse_list(PUBLISHED))
		self.assertEqual(
			check,
			Check(
				"minimum",
				False,
				"Abgleich mit der Mindestversionsliste 2.26.4.1: ERiC 43.1.3.0: libericapi.so 43.1.2.0 statt mindestens "
				"43.2.6.0, libeSigner.so 62.0.0.0 statt mindestens 63.0.0.1, libcheckUStVA_2026.so 43.1.3.0 statt "
				"mindestens 43.2.6.0. Mit einer Bibliothek unter ihrer Mindestversion ist kein Datenversand möglich "
				"(ERiC-Entwicklerhandbuch, Kap. 5.4.2).",
				notice="minimum 2.26.4.1 43.1.3.0",
			),
		)

	def test_a_mandatory_library_the_runtime_lacks(self):
		self.install(libraries=("libcheckUStVA_2026.so",))
		minimums = parse_list(
			listed(
				library("libericapi.linux-so", "43,2,6,0", "true"),
				library("libotto.linux-so", "43,2,6,0", "true"),
			)
		)
		(installation,) = self.installed()
		self.assertEqual(shortfalls(installation, minimums), ("libotto.so fehlt",))

	def test_what_the_list_names_and_the_runtime_lacks_is_no_shortfall_unless_mandatory(self):
		self.install(libraries=("libcheckUStVA_2026.so",))
		(installation,) = self.installed()
		self.assertEqual(shortfalls(installation, parse_list(PUBLISHED)), ())

	def test_what_the_list_does_not_name_is_not_compared(self):
		self.install(
			"45.1.5.0",
			libraries=(*OPTIONAL, "libcheckUStVA_2027.so"),
			versions=CURRENT | {"libcheckUStVA_2027.so": "1, 0, 0, 0"},
		)
		(installation,) = self.installed()
		self.assertEqual(shortfalls(installation, parse_list(PUBLISHED)), ())

	def test_a_runtime_without_any_version_read(self):
		"""Neither the probe nor the Versionsinformationen of the package named a version, so nothing can be compared;
		the next weekly check reads the Versionsinformationen, a new installation is not needed."""
		self.install(versions=None)
		(installation,) = self.installed()
		self.assertEqual(
			shortfalls(installation, parse_list(PUBLISHED)),
			(
				"die Versionen seiner Bibliotheken sind unbekannt, weil weder EricVersion bei der Einrichtung noch die "
				"Versionsinformationen des Pakets sie genannt haben; die wöchentliche Prüfung liest diese von "
				"download.elster.de oder aus der Datei, die steuerbote_eric_versions nennt",
			),
		)
		self.assertEqual(unread(installation, parse_list(PUBLISHED)), ())
		self.assertEqual(
			minimum_check(self.installed(), parse_list(PUBLISHED)).notice, "minimum 2.26.4.1 44.3.6.0"
		)

	def test_a_library_whose_version_was_not_read_is_a_hint_and_no_shortfall(self):
		self.install(versions={"libericapi.so": "44, 3, 6, 0", "libotto.so": "unbekannt"})
		(installation,) = self.installed()
		minimums = parse_list(PUBLISHED)
		self.assertEqual(shortfalls(installation, minimums), ())
		self.assertEqual(
			unread(installation, minimums),
			(
				"libericxerces.so",
				"libeSigner.so",
				"libotto.so",
				"libcheckUStVA_2025.so",
				"libcheckUStVA_2026.so",
				"libcheckZMDO.so",
				"libcommonData.so",
			),
		)
		check = minimum_check(self.installed(), minimums)
		self.assertEqual((check.ok, check.notice), (True, ""))
		self.assertIn(
			"Ohne gelesene Version und deshalb nicht verglichen: ERiC 44.3.6.0: libericxerces.so, libeSigner.so, "
			"libotto.so, libcheckUStVA_2025.so, libcheckUStVA_2026.so und 2 weitere.",
			check.detail,
		)

	def test_a_library_below_its_minimum_stays_a_shortfall_beside_the_hint(self):
		self.install(versions={"libericapi.so": "43, 1, 2, 0"})
		check = minimum_check(self.installed(), parse_list(PUBLISHED))
		self.assertEqual((check.ok, check.notice), (False, "minimum 2.26.4.1 44.3.6.0"))
		self.assertTrue(
			check.detail.startswith(
				"Abgleich mit der Mindestversionsliste 2.26.4.1: ERiC 44.3.6.0: libericapi.so 43.1.2.0 statt "
				"mindestens 43.2.6.0. Mit einer Bibliothek unter ihrer Mindestversion ist kein Datenversand möglich "
				"(ERiC-Entwicklerhandbuch, Kap. 5.4.2). Ohne gelesene Version und deshalb nicht verglichen: ERiC "
				"44.3.6.0: libericxerces.so,"
			),
			check.detail,
		)

	def test_names_at_most_five_shortfalls_of_a_runtime(self):
		self.install(versions=dict.fromkeys(CURRENT, "1, 0, 0, 0"))
		(installation,) = self.installed()
		found = shortfalls(installation, parse_list(PUBLISHED))
		self.assertEqual(len(found), 8)
		self.assertEqual(found[0], "libericapi.so 1.0.0.0 statt mindestens 43.2.6.0")
		self.assertIn(
			"ERiC 44.3.6.0: libericapi.so 1.0.0.0 statt mindestens 43.2.6.0, libericxerces.so 1.0.0.0 statt "
			"mindestens 25.9.11.0, libeSigner.so 1.0.0.0 statt mindestens 63.0.0.1, libotto.so 1.0.0.0 statt "
			"mindestens 43.2.6.0, libcheckUStVA_2025.so 1.0.0.0 statt mindestens 43.2.4.0 und 3 weitere.",
			minimum_check(self.installed(), parse_list(PUBLISHED)).detail,
		)

	def test_compares_every_installed_runtime(self):
		self.install()
		self.install("43.1.3.0", versions=CURRENT | {"libericapi.so": "43, 1, 2, 0"})
		check = minimum_check(self.installed(), parse_list(PUBLISHED))
		self.assertFalse(check.ok)
		self.assertIn("ERiC 43.1.3.0: libericapi.so 43.1.2.0 statt mindestens 43.2.6.0.", check.detail)
		self.assertNotIn("44.3.6.0", check.detail)
		self.assertEqual(check.notice, "minimum 2.26.4.1 43.1.3.0")

	def test_runtimes_that_all_reach_the_minimums(self):
		self.install()
		self.install("45.1.5.0")
		self.assertEqual(
			minimum_check(self.installed(), parse_list(PUBLISHED)).detail,
			"ERiC 45.1.5.0 und 44.3.6.0 erreichen die Mindestversionen der Mindestversionsliste 2.26.4.1 "
			"(libericapi.so ab 43.2.6.0).",
		)
		self.install("44.2.10.0")
		self.assertIn(
			"ERiC 45.1.5.0, 44.3.6.0 und 44.2.10.0 erreichen",
			minimum_check(self.installed(), parse_list(PUBLISHED)).detail,
		)

	def test_a_list_that_names_no_minimum_of_libericapi(self):
		self.install()
		self.assertEqual(
			minimum_check(
				self.installed(), parse_list(listed(library("libotto.linux-so", "43,2,6,0")))
			).detail,
			"ERiC 44.3.6.0 erreicht die Mindestversionen der Mindestversionsliste 2.27.4.1.",
		)

	def test_a_datenartversion_of_steuerbote_is_compared_with_its_plugin(self):
		"""HB Kap. 5.4.2: the Mindestversion is set for the ERiC library of each datenartVersion, its plugin."""
		self.install()
		minimums = parse_list(
			listed(
				library("libericapi.linux-so", "43,2,6,0", "true"),
				extra=(
					"    datenartversionListe:\n"
					"      - name: UStVA_2026\n        version: 44,4,0,0\n"
					"      - name: UStVA_2025\n        version: 44,3,6,0\n"
					"      - name: ZMDO\n        version: 45,1,0,0\n"
					"      - name: UStVA_2027\n        version: 45,1,0,0\n"
					"      - name: ElsterFSE_PersG_202401\n        version: 99,0,0,0\n"
				),
			)
		)
		(installation,) = self.installed()
		self.assertEqual(
			shortfalls(installation, minimums),
			(
				"libcheckUStVA_2026.so (UStVA_2026) 44.3.6.0 statt mindestens 44.4.0.0",
				"libcheckZMDO.so (ZMDO) 44.3.6.0 statt mindestens 45.1.0.0",
			),
		)

	def test_without_a_list_or_without_a_runtime(self):
		self.assertEqual(
			minimum_check((), None),
			Check(
				"minimum",
				False,
				"Die Mindestversionsliste von ELSTER ist noch nicht geladen; die wöchentliche Prüfung der "
				"ERiC-Versionen lädt sie.",
			),
		)
		self.assertEqual(
			minimum_check((), parse_list(PUBLISHED)),
			Check(
				"minimum",
				False,
				"Ohne ERiC-Laufzeit gibt es nichts mit der Mindestversionsliste 2.26.4.1 zu vergleichen.",
			),
		)


class PackageVersionsTest(InstalledTestCase):
	"""The Versionsinformationen of its package complete what the probe read of an installation with EricVersion: with
	ERiC 44.3.6.0, EricVersion named every library but gave the product version of a few, so most of them had none to
	compare with the Mindestversionsliste (HB Kap. 4.3 with footnote 21)."""

	def published(self) -> FakeOpener:
		return FakeOpener(FakeAnswer(PUBLISHED_VERSIONS.encode()))

	def test_before_they_are_read_the_libraries_without_a_version_are_a_hint(self):
		self.package()
		(installation,) = self.installed()
		minimums = parse_list(PUBLISHED)
		self.assertEqual(shortfalls(installation, minimums), ())
		self.assertEqual(
			unread(installation, minimums),
			(
				"libeSigner.so",
				"libotto.so",
				"libcheckUStVA_2016.so",
				"libcheckUStVA_2025.so",
				"libcheckUStVA_2026.so",
				"libcheckZMDO.so",
			),
		)
		self.assertEqual(
			minimum_check(self.installed(), minimums),
			Check(
				"minimum",
				True,
				"ERiC 44.3.6.0 erreicht die Mindestversionen der Mindestversionsliste 2.26.4.1 (libericapi.so ab "
				"43.2.6.0), soweit ihre Versionen gelesen sind. Ohne gelesene Version und deshalb nicht verglichen: "
				"ERiC 44.3.6.0: libeSigner.so, libotto.so, libcheckUStVA_2016.so, libcheckUStVA_2025.so, "
				"libcheckUStVA_2026.so und 1 weitere. Ihre Versionen nennen die Versionsinformationen des Pakets, die "
				"die wöchentliche Prüfung von download.elster.de liest oder aus der Datei, die "
				"steuerbote_eric_versions nennt.",
			),
		)
		self.assertEqual(notices(self.installed(), minimums, date(2026, 6, 1)), ())

	def test_their_product_versions_complete_those_of_eric_version(self):
		self.package()
		opener = self.published()
		self.assertEqual(complete_versions(self.installed(), opener=opener), ())
		self.assertEqual([request.full_url for request, _timeout in opener.calls], [VERSIONS_44])
		(installation,) = self.installed()
		self.assertEqual(
			(dict(installation.listed_versions), installation.listed_versions_source),
			(LISTED_44, VERSIONS_44),
		)
		self.assertEqual(dict(installation.library_versions), PROBED_44)
		minimums = parse_list(PUBLISHED)
		self.assertEqual((shortfalls(installation, minimums), unread(installation, minimums)), ((), ()))
		self.assertEqual(
			minimum_check(self.installed(), minimums).detail,
			"ERiC 44.3.6.0 erreicht die Mindestversionen der Mindestversionsliste 2.26.4.1 (libericapi.so ab "
			"43.2.6.0).",
		)
		self.assertEqual(verify(installation), ())

	def test_they_are_read_once(self):
		self.package()
		complete_versions(self.installed(), opener=self.published())
		again = FakeOpener(error=AssertionError("read again"))
		self.assertEqual(complete_versions(self.installed(), opener=again), ())
		self.assertEqual(again.calls, [])

	def test_the_manifest_keeps_everything_else(self):
		self.package()
		manifest = self.root / "44.3.6.0" / MANIFEST
		before = json.loads(manifest.read_text(encoding="utf-8"))
		mode = manifest.stat().st_mode
		read_versions(self.installed()[0], opener=self.published())
		self.assertEqual(
			json.loads(manifest.read_text(encoding="utf-8")),
			before | {"listed_versions": LISTED_44, "listed_versions_source": VERSIONS_44},
		)
		self.assertEqual(manifest.stat().st_mode, mode)
		self.assertEqual(sorted(path.name for path in manifest.parent.iterdir()), ["lib", MANIFEST])

	def test_reading_them_returns_the_installation_as_its_manifest_now_describes_it(self):
		self.package()
		completed = read_versions(self.installed()[0], opener=self.published())
		self.assertEqual(completed, self.installed()[0])
		self.assertEqual(dict(completed.listed_versions), LISTED_44)

	def test_a_copy_the_operator_names_takes_the_place_of_the_download(self):
		"""For a site without access to download.elster.de."""
		self.package()
		copy = self.directory / "ERiC-44.3.6.0-Linux-x86_64.version.txt"
		copy.write_bytes(VERSIONS_FIXTURE.read_bytes())
		opener = FakeOpener(error=urllib.error.URLError("Network is unreachable"))
		self.assertEqual(complete_versions(self.installed(), copy, opener), ())
		self.assertEqual(opener.calls, [])
		(installation,) = self.installed()
		self.assertEqual(
			(dict(installation.listed_versions), installation.listed_versions_source), (LISTED_44, str(copy))
		)

	def test_a_copy_serves_only_the_version_its_name_names(self):
		self.package()
		copy = self.directory / "ERiC-45.1.5.0-Linux-x86_64.version.txt"
		copy.write_text("Linux-x86_64/lib/libericapi.so\t45, 1, 3, 0\t2026, 45, 1, 3\n", encoding="utf-8")
		self.assertEqual(complete_versions(self.installed(), copy, self.published()), ())
		(installation,) = self.installed()
		self.assertEqual(installation.listed_versions_source, VERSIONS_44)

	def test_a_copy_bears_the_name_elster_gives_the_versionsinformationen(self):
		self.package()
		copy = self.directory / "versionen.txt"
		copy.write_bytes(VERSIONS_FIXTURE.read_bytes())
		self.assertEqual(
			complete_versions(self.installed(), copy, self.published()),
			(
				f"Die Datei {copy} trägt nicht den Namen von Versionsinformationen, "
				"ERiC-<Version>-Linux-x86_64.version.txt; Steuerbote nimmt sie nicht.",
			),
		)
		(installation,) = self.installed()
		self.assertEqual(installation.listed_versions_source, VERSIONS_44)

	def test_what_cannot_be_read_is_named_and_leaves_the_manifest_as_it_was(self):
		self.package()
		manifest = self.root / "44.3.6.0" / MANIFEST
		before = manifest.read_bytes()
		absent = self.directory / "ERiC-44.3.6.0-Linux-x86_64.version.txt"
		large = self.directory / "large" / "ERiC-44.3.6.0-Linux-x86_64.version.txt"
		large.parent.mkdir()
		large.write_bytes(b"#" * (MAX_VERSIONS_BYTES + 1))
		without_zmdo = "".join(
			line for line in PUBLISHED_VERSIONS.splitlines(keepends=True) if "ZMDO" not in line
		)
		downloaded = f"ERiC 44.3.6.0: Die Versionsinformationen von {VERSIONS_44}"
		for copy, answer, problem in (
			(
				None,
				urllib.error.URLError("Name or service not known"),
				f"{downloaded} ließen sich nicht laden: <urlopen error Name or service not known>.",
			),
			(
				None,
				urllib.error.HTTPError(VERSIONS_44, 404, "Not Found", Message(), io.BytesIO(b"")),
				f"{downloaded} ließen sich nicht laden: HTTP Error 404: Not Found.",
			),
			(None, TimeoutError("timed out"), f"{downloaded} ließen sich nicht laden: timed out."),
			(
				None,
				FakeAnswer(b"\xff"),
				f"{downloaded} sind kein UTF-8: 'utf-8' codec can't decode byte 0xff in position 0: invalid start "
				"byte.",
			),
			(
				None,
				FakeAnswer(b"#" * (MAX_VERSIONS_BYTES + 1)),
				f"{downloaded} sind größer als 1 MiB.",
			),
			(
				None,
				FakeAnswer(b"Linux-x86_64/lib/libericapi.so\t44, 3, 4\t2026, 44, 3, 4\n"),
				f"{downloaded} haben nicht die erwartete Form: Zeile 1: die Produktversion „44, 3, 4“ hat keine vier "
				"Zahlen.",
			),
			(
				None,
				FakeAnswer(without_zmdo.encode()),
				f"{downloaded} nennen nicht alle Bibliotheken der Laufzeit, es fehlen plugins/libcheckZMDO.so; sie "
				"gehören zu einem anderen Paket.",
			),
			(
				absent,
				None,
				f"ERiC 44.3.6.0: Die Versionsinformationen aus {absent} ließen sich nicht lesen: [Errno 2] No such file "
				f"or directory: '{absent}'.",
			),
			(large, None, f"ERiC 44.3.6.0: Die Versionsinformationen aus {large} sind größer als 1 MiB."),
		):
			opener = FakeOpener(error=answer) if isinstance(answer, Exception) else FakeOpener(answer)
			with self.subTest(problem=problem):
				self.assertEqual(complete_versions(self.installed(), copy, opener), (problem,))
				self.assertEqual(manifest.read_bytes(), before)
				(installation,) = self.installed()
				self.assertEqual(
					(dict(installation.listed_versions), installation.listed_versions_source), ({}, "")
				)

	def test_a_manifest_that_cannot_be_written_stays_as_it_was(self):
		self.package()
		manifest = self.root / "44.3.6.0" / MANIFEST
		before = manifest.read_bytes()
		with mock.patch.object(runtime.os, "replace", side_effect=OSError("No space left on device")):
			found = complete_versions(self.installed(), opener=self.published())
		self.assertEqual(
			found,
			(
				f"ERiC 44.3.6.0: Die Versionsinformationen von {VERSIONS_44} ließen sich nicht im Manifest festhalten: "
				"No space left on device.",
			),
		)
		self.assertEqual(manifest.read_bytes(), before)
		self.assertEqual(sorted(path.name for path in manifest.parent.iterdir()), ["lib", MANIFEST])

	def test_where_both_name_a_version_they_agree(self):
		"""A library whose versions disagree is a shortfall, for then the Versionsinformationen do not describe the
		installed package."""
		self.package(PROBED_44 | {"libotto.so": "44, 3, 7, 0"})
		complete_versions(self.installed(), opener=self.published())
		(installation,) = self.installed()
		self.assertEqual(
			shortfalls(installation, parse_list(PUBLISHED)),
			("libotto.so 44.3.7.0 laut EricVersion, 44.3.6.0 laut den Versionsinformationen des Pakets",),
		)
		check = minimum_check(self.installed(), parse_list(PUBLISHED))
		self.assertEqual((check.ok, check.notice), (False, "minimum 2.26.4.1 44.3.6.0"))
		self.assertIn("ERiC 44.3.6.0: libotto.so 44.3.7.0 laut EricVersion, 44.3.6.0 laut den", check.detail)

	def test_where_they_disagree_the_lower_version_counts(self):
		self.package()
		read_versions(
			self.installed()[0], opener=FakeOpener(FakeAnswer(self.listing({"libericapi.so": "43, 1, 0, 0"})))
		)
		(installation,) = self.installed()
		self.assertEqual(
			shortfalls(installation, parse_list(PUBLISHED)),
			(
				"libericapi.so 43.1.0.0 statt mindestens 43.2.6.0",
				"libericapi.so 44.3.4.0 laut EricVersion, 43.1.0.0 laut den Versionsinformationen des Pakets",
			),
		)

	def test_a_version_of_another_form_counts_as_none(self):
		self.package(PROBED_44 | {"libotto.so": "unbekannt"})
		complete_versions(self.installed(), opener=self.published())
		(installation,) = self.installed()
		self.assertEqual(shortfalls(installation, parse_list(PUBLISHED)), ())


class NextYearTest(InstalledTestCase):
	def test_before_the_main_release_a_missing_year_is_no_failure(self):
		self.install()
		self.assertEqual(
			next_year_check(self.installed(), date(2026, 11, 14)),
			Check(
				"plugin_next",
				True,
				"Das Jahr 2027 bringt erst das Hauptrelease von ERiC, das für Mitte November 2026 geplant ist "
				"(ERiC-Entwicklerhandbuch, Kap. 2.3).",
			),
		)
		self.assertTrue(next_year_check((), date(2026, 1, 2)).ok)

	def test_from_mid_november_the_coming_year_needs_its_plugin(self):
		self.install()
		for today in (date(2026, 11, 15), date(2026, 12, 31)):
			with self.subTest(today=today):
				self.assertEqual(
					next_year_check(self.installed(), today),
					Check(
						"plugin_next",
						False,
						"Für das Jahr 2027 fehlt ERiC mit dem Plugin libcheckUStVA_2027.so.",
						notice="next-year 2027",
					),
				)

	def test_a_beta_with_the_coming_year(self):
		self.install()
		self.install("45.1.5.0", libraries=(*OPTIONAL, "libcheckUStVA_2027.so"))
		beta = "Das Jahr 2027 kennt nur die Beta ERiC 45.1.5.0: Prüfen und Testsenden, kein Senden."
		self.assertEqual(
			next_year_check(self.installed(), date(2026, 10, 20)), Check("plugin_next", True, beta)
		)
		self.assertEqual(
			next_year_check(self.installed(), date(2026, 11, 23)),
			Check("plugin_next", False, beta, notice="next-year 2027"),
		)

	def test_a_released_runtime_with_the_coming_year(self):
		self.install("45.2.1.0", libraries=(*OPTIONAL, "libcheckUStVA_2027.so"))
		self.assertEqual(
			next_year_check(self.installed(), date(2026, 12, 1)),
			Check("plugin_next", True, "ERiC 45.2.1.0 prüft und sendet das Jahr 2027."),
		)


class NoticesTest(InstalledTestCase):
	def test_without_a_runtime_nobody_hears_of_anything(self):
		self.assertEqual(notices((), parse_list(PUBLISHED), date(2027, 1, 4)), ())

	def test_the_failing_checks_of_years_and_minimums_each_with_its_notice(self):
		self.install("44.3.6.0", versions=CURRENT | {"libericapi.so": "43, 1, 2, 0"})
		found = notices(self.installed(), parse_list(PUBLISHED), date(2026, 11, 23))
		self.assertEqual([check.notice for check in found], ["minimum 2.26.4.1 44.3.6.0", "next-year 2027"])
		found = notices(self.installed(), parse_list(PUBLISHED), date(2027, 1, 4))
		self.assertEqual([check.notice for check in found], ["year 2027", "minimum 2.26.4.1 44.3.6.0"])
		self.assertEqual(
			found[0].detail, "Für das Jahr 2027 fehlt ERiC mit dem Plugin libcheckUStVA_2027.so."
		)

	def test_a_runtime_that_serves_the_year_and_reaches_the_minimums_brings_no_notice(self):
		self.install()
		self.assertEqual(notices(self.installed(), parse_list(PUBLISHED), date(2026, 6, 1)), ())

	def test_a_list_not_loaded_yet_is_no_notice(self):
		self.install()
		self.assertEqual(notices(self.installed(), None, date(2026, 6, 1)), ())

	def test_each_notice_once(self):
		failing = (
			Check("minimum", False, "unter der Liste", notice="minimum 2.26.4.1 44.3.6.0"),
			Check("plugin_next", False, "2027 fehlt", notice="next-year 2027"),
		)
		self.assertEqual(due(failing, []), failing)
		self.assertEqual(due(failing, ["next-year 2027", "year 2026"]), failing[:1])
		self.assertEqual(due(failing, ("minimum 2.26.4.1 44.3.6.0", "next-year 2027")), ())


# The plugins of the annual filings of 2026 in ERiC 44.3.6.0: the Umsatzsteuererklärung and the taxonomy 6.9 of the
# E-Bilanz, not yet the Körperschaftsteuererklärung and the Gewerbesteuererklärung (ERiC-Entwicklerhandbuch,
# Tabelle 2-12; version list of the package).
ANNUAL_2026 = ("libcheckUSt_2026.so", "libcheckBilanz_6_9.so")


class AnnualChecksTest(InstalledTestCase):
	"""The plugins of the annual filings of the year before, which are filed from 1 January: the Erklärungen of the VZ
	and the E-Bilanz of the fiscal year in its taxonomy, from the first year steuerbote files."""

	def test_the_annual_filings_begin_with_the_year_2026(self):
		"""docs/roadmap.md, „Ab 2026“; 6.9 for a fiscal year beginning after 31 December 2025 (BMF letter of 10 June
		2025, IV C 6 - S 2133-b/00064/002/006), 6.10 for one beginning after 31 December 2026 (BMF letter of 8 June
		2026, IV C 6 - S 2133-b/00067/002/023)."""
		self.assertEqual((FIRST_ANNUAL_YEAR, dict(BILANZ_TAXONOMIES)), (2026, {2026: "6.9", 2027: "6.10"}))

	def test_before_the_first_filing_year_there_is_nothing_to_check(self):
		self.install()
		for today in (date(2026, 1, 1), date(2026, 11, 23), date(2026, 12, 31)):
			with self.subTest(today=today):
				self.assertEqual(annual_checks(self.installed(), today), ())

	def test_from_1_january_each_plugin_of_the_year_before(self):
		self.install(libraries=(*OPTIONAL, *ANNUAL_2026))
		self.assertEqual(
			annual_checks(self.installed(), date(2027, 1, 1)),
			(
				Check("ust", True, "ERiC 44.3.6.0 prüft und sendet die Umsatzsteuererklärung 2026."),
				Check(
					"kst",
					False,
					"Für die Körperschaftsteuererklärung 2026 fehlt ERiC mit dem Plugin libcheckKSt_2026.so.",
					notice="annual KSt_30_2026",
				),
				Check(
					"gewst",
					False,
					"Für die Gewerbesteuererklärung 2026 fehlt ERiC mit dem Plugin libcheckGewSt_2026.so.",
					notice="annual GewSt_2026",
				),
				Check(
					"bilanz",
					True,
					"ERiC 44.3.6.0 prüft und sendet die E-Bilanz des Wirtschaftsjahres 2026 (Taxonomie 6.9).",
				),
			),
		)

	def test_a_beta_with_the_plugins_serves_checks_and_test_sends_only(self):
		self.install(libraries=(*OPTIONAL, *ANNUAL_2026))
		self.install("45.1.5.0", libraries=(*OPTIONAL, "libcheckKSt_2026.so", "libcheckGewSt_2026.so"))
		found = {check.name: check for check in annual_checks(self.installed(), date(2027, 2, 1))}
		self.assertEqual(
			found["kst"],
			Check(
				"kst",
				False,
				"Die Körperschaftsteuererklärung 2026 kennt nur die Beta ERiC 45.1.5.0: Prüfen und Testsenden, kein "
				"Senden.",
				notice="annual KSt_30_2026",
			),
		)
		self.assertEqual(
			found["ust"].detail, "ERiC 44.3.6.0 prüft und sendet die Umsatzsteuererklärung 2026."
		)

	def test_a_fiscal_year_whose_taxonomy_steuerbote_does_not_know_yet(self):
		self.install(libraries=(*OPTIONAL, *ANNUAL_2026))
		found = {check.name: check for check in annual_checks(self.installed(), date(2029, 1, 3))}
		self.assertEqual(
			found["bilanz"],
			Check(
				"bilanz",
				False,
				"Für das Wirtschaftsjahr 2028 kennt Steuerbote noch keine Taxonomie der E-Bilanz.",
			),
		)
		self.assertEqual(found["ust"].notice, "annual USt_2028")

	def test_the_e_bilanz_of_the_fiscal_year_2027_takes_the_plugin_of_6_10(self):
		self.install(libraries=(*OPTIONAL, *ANNUAL_2026))
		found = {check.name: check for check in annual_checks(self.installed(), date(2028, 1, 3))}
		self.assertEqual(
			found["bilanz"],
			Check(
				"bilanz",
				False,
				"Für die E-Bilanz des Wirtschaftsjahres 2027 (Taxonomie 6.10) fehlt ERiC mit dem Plugin "
				"libcheckBilanz_6_10.so.",
				notice="annual Bilanz_6.10",
			),
		)
		self.install("45.1.5.0", libraries=(*OPTIONAL, "libcheckBilanz_6_10.so"))
		found = {check.name: check for check in annual_checks(self.installed(), date(2028, 1, 3))}
		self.assertEqual(
			found["bilanz"].detail,
			"Die E-Bilanz des Wirtschaftsjahres 2027 (Taxonomie 6.10) kennt nur die Beta ERiC 45.1.5.0: Prüfen und "
			"Testsenden, kein Senden.",
		)

	def test_laufzeitumgebung_pruefen_lists_them_after_the_list_and_the_coming_year(self):
		self.install(libraries=(*OPTIONAL, *ANNUAL_2026))
		self.assertEqual(
			[check.name for check in checks(self.installed(), parse_list(PUBLISHED), date(2027, 1, 4))],
			["minimum", "plugin_next", "ust", "kst", "gewst", "bilanz"],
		)
		self.assertEqual(
			[check.name for check in checks(self.installed(), parse_list(PUBLISHED), date(2026, 11, 23))],
			["minimum", "plugin_next"],
		)


class AnnualNoticesTest(InstalledTestCase):
	def test_only_a_site_with_annual_filings_hears_of_a_missing_plugin_once_from_1_january(self):
		self.install(libraries=(*OPTIONAL, *ANNUAL_2026))
		installed, minimums = self.installed(), parse_list(PUBLISHED)
		self.assertEqual(
			[check.notice for check in notices(installed, minimums, date(2027, 1, 4))], ["year 2027"]
		)
		self.assertEqual(
			[check.notice for check in notices(installed, minimums, date(2027, 1, 4), annual=True)],
			["year 2027", "annual KSt_30_2026", "annual GewSt_2026"],
		)
		self.assertEqual(
			[check.notice for check in notices(installed, minimums, date(2026, 12, 7), annual=True)],
			["next-year 2027"],
		)

	def test_without_a_runtime_nobody_hears_of_the_annual_plugins_either(self):
		self.assertEqual(notices((), parse_list(PUBLISHED), date(2027, 1, 4), annual=True), ())


class ScheduleTest(TestCase):
	def test_the_versions_are_checked_every_week(self):
		self.assertEqual(hooks.scheduler_events["weekly"], [VERSIONS_JOB])
		self.assertEqual(hooks.scheduler_events["daily"], ["steuerbote.steuerbote.deadlines.send_reminders"])
