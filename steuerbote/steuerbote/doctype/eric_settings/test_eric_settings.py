import csv
import hashlib
import json
import re
import shutil
import tempfile
import urllib.error
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

import frappe
from frappe.desk.form.meta import get_meta as get_form_meta
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.tests import IntegrationTestCase
from frappe.utils import convert_utc_to_system_timezone, get_bench_path, get_datetime

import steuerbote
from steuerbote.eric import releases, runtime, service
from steuerbote.eric.datenart import ZMDO
from steuerbote.eric.proxy import Proxy
from steuerbote.eric.releases import FetchedList, MinimumList
from steuerbote.eric.result import Operation
from steuerbote.eric.runtime import RuntimeInfo, RuntimeInstallError
from steuerbote.steuerbote.doctype.elster_transmission import transmission
from steuerbote.steuerbote.doctype.eric_settings import eric_settings
from steuerbote.steuerbote.doctype.eric_settings.eric_settings import (
	check_versions,
	eric_log_root,
	run_installation,
	run_taxonomy_installation,
	vorsatz_copyright,
)
from steuerbote.steuerbote.doctype.vat_return import transmission_adapter
from steuerbote.tests.helpers import make_company
from steuerbote.xbrl import taxonomy
from steuerbote.xbrl.taxonomy import View
from steuerbote.xbrl.tests import mini
from steuerbote.xbrl.versions import TAXONOMIES

# The users of the tests are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]

SETTINGS = "ERiC Settings"
ANNUAL_FILING_SETTINGS = "Annual Filing Settings"
# The company whose Annual Filing Settings make a site keep annual filings.
ANNUAL_FILINGS_COMPANY = "Steuerbote Test ERiC Jahresmeldungen GmbH"
INSTALLATION_JOB = "steuerbote.steuerbote.doctype.eric_settings.eric_settings.run_installation"
ARCHIVE = "/srv/eric/ERiC-44.3.6.0-Linux-x86_64.jar"
CHECKSUM = "ab" * 32
# What a System Manager could upload as a File and enter as the archive.
UPLOADED = "/home/frappe/frappe-bench/sites/test_site/private/files/ERiC-44.3.6.0-Linux-x86_64.jar"
UPLOADED_CHECKSUM = "cd" * 32
BENCH = {"steuerbote_eric_archive": ARCHIVE, "steuerbote_eric_archive_sha256": CHECKSUM}
LIB_DIR = "/srv/eric/44.3.6.0/lib"
RUNTIME = RuntimeInfo("44.3.6.0", Path(LIB_DIR), Path(LIB_DIR), Path("/srv/eric/log"), "")
ACCOUNTS_MANAGER = "steuerbote-eric-einstellungen@example.com"
SYSTEM_MANAGER = "steuerbote-eric-versionen@example.com"
# An excerpt of the Mindestversionsliste as ELSTER published it on 23 November 2026, list version 2.26.4.1.
MINIMUM_LIST = (
	Path(releases.__file__).parent / "tests" / "fixtures" / "eric_mindestversionsliste.yaml"
).read_text(encoding="utf-8")
LIST_CHANGED = datetime(2026, 8, 28, 11, 25, 9, tzinfo=UTC)
PUBLISHED = FetchedList(MINIMUM_LIST, LIST_CHANGED)
# Product versions EricVersion could report, invented: a runtime that reaches the list 2.26.4.1 and one below it.
CURRENT = {
	"libericapi.so": "44, 3, 6, 0",
	"libcommonData.so": "44, 3, 6, 0",
	"libcheckUStVA_2026.so": "44, 3, 6, 0",
}
OUTDATED = CURRENT | {"libericapi.so": "43, 1, 2, 0"}
VERSION_CHECK_FIELDS = (
	"minimum_list_version",
	"minimum_list_modified",
	"minimum_eric_version",
	"minimum_versions",
	"versions_checked_on",
	"versions_check_failed",
	"version_notices",
	"version_notice_status",
	"version_notified_on",
)
# Where the Versionsinformationen of the package ERiC 44.3.6.0 for Linux x86_64 lie (ERiC-Entwicklerhandbuch, Kap. 4.3,
# footnote 21; download server of ELSTER as of 23 November 2026).
VERSIONS_44 = "https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Linux-x86_64.version.txt"
# The files of the runtime the tests of the versions install, below lib.
RUNTIME_FILES = {
	"libericapi.so": "libericapi.so",
	"libcommonData.so": "plugins2/libcommonData.so",
	"libcheckUStVA_2026.so": "plugins2/libcheckUStVA_2026.so",
}
# The password of the proxy, invented.
PROXY_GEHEIM = "Proxy-Geheim-2026"
# A copyright notice of the manufacturer of the software, invented.
COPYRIGHT = "(c) 2026 Beispiel Software GmbH, München"


def versionsinformationen(versions: dict[str, str]) -> str:
	"""The Versionsinformationen of the runtime of the tests in the published form: per file its path, product version
	and file version, separated by tabs."""
	return "".join(
		f"Linux-x86_64/lib/{RUNTIME_FILES[name]}\t{version}\t2026, 44, 3, 6\n"
		for name, version in versions.items()
	)


def make_user(email: str, role: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Steuerbote",
				"send_welcome_email": 0,
				"roles": [{"role": role}],
			}
		).insert(ignore_permissions=True)
	return email


class TestERiCSettings(IntegrationTestCase):
	def configured(self, **values):
		"""common_site_config.json of the bench with these values."""
		return patch.object(transmission_adapter, "common_site_config", return_value=frappe._dict(values))

	def settings(self, **values):
		settings = frappe.get_single(SETTINGS)
		settings.update(
			{
				"archive_path": "",
				"archive_sha256": "",
				"hersteller_id": "",
				"produkt_name": "steuerbote",
				"datenlieferant": "",
				"installed_version": "",
				"lib_dir": "",
				"log_dir": "",
				"privacy_notice_confirmed": 0,
				"proxy_url": "",
				"proxy_user": "",
				"proxy_password": "",
				**values,
			}
		)
		settings.save()
		return frappe.get_single(SETTINGS)

	def test_a_proxy_is_one_eric_takes(self):
		settings = self.settings(
			proxy_url=" http://proxy.example.com:3128 ",
			proxy_user=" steuerbote ",
			proxy_password=PROXY_GEHEIM,
		)
		self.assertEqual(
			(settings.proxy_url, settings.proxy_user), ("http://proxy.example.com:3128", "steuerbote")
		)
		self.assertEqual(settings.get_password("proxy_password"), PROXY_GEHEIM)
		for values, message in (
			({"proxy_url": "proxy.example.com:3128"}, "is no proxy URL"),
			({"proxy_url": "http://proxy.example.com"}, "needs the port of the proxy"),
			({"proxy_url": "http://steuerbote:geheim@proxy.example.com:3128"}, "in their own fields"),
			(
				{"proxy_url": "http://proxy.example.com:3128", "proxy_user": "steuerbote"},
				"a user only with a password",
			),
			(
				{
					"proxy_url": "socks5://proxy.example.com:1080",
					"proxy_user": "steuerbote",
					"proxy_password": PROXY_GEHEIM,
				},
				"a SOCKS proxy only without user and password",
			),
		):
			with self.subTest(values=values), self.assertRaisesRegex(frappe.ValidationError, message):
				self.settings(**values)

	def test_without_a_proxy_url_neither_user_nor_password_stays(self):
		settings = self.settings(proxy_user="steuerbote", proxy_password=PROXY_GEHEIM)
		self.assertEqual((settings.proxy_url or None, settings.proxy_user or None), (None, None))
		self.assertIsNone(settings.get_password("proxy_password", raise_exception=False))
		self.assertIsNone(transmission_adapter.settings_proxy())

	def test_eric_goes_through_the_proxy_of_the_settings_and_the_simulation_reaches_no_server(self):
		self.settings(
			proxy_url="http://proxy.example.com:3128", proxy_user="steuerbote", proxy_password=PROXY_GEHEIM
		)
		runtime = RuntimeInfo("44.3.6.0", Path(LIB_DIR), Path(LIB_DIR), Path("/srv/eric/logs"), "12345", True)
		with patch.object(service, "run") as run:
			transmission_adapter.run(Operation.VALIDATE, "<Anmeldungssteuern/>", None, runtime, None, None)
			transmission_adapter.run(Operation.VALIDATE, "<Anmeldungssteuern/>", None, None, None, None)
		self.assertEqual(
			[call.kwargs["proxy"] for call in run.call_args_list],
			[Proxy("proxy.example.com", 3128, "steuerbote", PROXY_GEHEIM), None],
		)

	def test_starts_as_a_simulation_and_names_the_version_of_the_app(self):
		settings = self.settings()
		self.assertEqual(
			(settings.simulation, settings.produkt_name, settings.produkt_version),
			(1, "steuerbote", steuerbote.__version__),
		)

	def outdated_produkt_version(self) -> None:
		"""ERiC Settings last saved under an older version of the app."""
		self.settings()
		frappe.db.set_single_value(SETTINGS, "produkt_version", "0.4.0", update_modified=False)

	def test_every_migration_brings_the_version_of_the_app_into_the_settings(self):
		"""bench migrate runs after every update of the app, the hook after_migrate with it."""
		self.outdated_produkt_version()
		self.assertIn(
			"steuerbote.steuerbote.doctype.eric_settings.eric_settings.refresh_produkt_version",
			frappe.get_hooks("after_migrate", app_name="steuerbote"),
		)
		eric_settings.refresh_produkt_version()
		self.assertEqual(
			frappe.db.get_single_value(SETTINGS, "produkt_version", cache=False), steuerbote.__version__
		)

	def test_the_form_shows_the_version_of_the_app_and_keeps_it(self):
		self.outdated_produkt_version()
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(settings.produkt_version, "0.4.0")
		settings.run_method("onload")
		self.assertEqual(settings.produkt_version, steuerbote.__version__)
		self.assertEqual(
			frappe.db.get_single_value(SETTINGS, "produkt_version", cache=False), steuerbote.__version__
		)

	def test_the_header_of_a_delivery_names_the_version_of_the_app_and_never_the_stored_one(self):
		self.outdated_produkt_version()
		document = frappe._dict(company="Steuerbote Test GmbH", datenart=lambda: ZMDO)
		header = transmission.envelope_header(document, frappe.get_single(SETTINGS), Operation.VALIDATE, True)
		self.assertEqual(header.produkt_version, steuerbote.__version__)

	def test_leaves_the_simulation_only_with_a_runtime_and_a_hersteller_id(self):
		self.assertEqual(self.settings(hersteller_id="12345").simulation, 1)
		self.assertEqual(self.settings(installed_version="44.3.6.0", lib_dir=LIB_DIR).simulation, 1)
		self.assertEqual(
			self.settings(hersteller_id="12345", installed_version="44.3.6.0", lib_dir=LIB_DIR).simulation, 0
		)

	def test_the_simulation_flag_follows_the_settings_and_cannot_be_entered(self):
		self.assertEqual(self.settings(simulation=0).simulation, 1)
		self.assertEqual(
			self.settings(
				simulation=1, hersteller_id="12345", installed_version="44.3.6.0", lib_dir=LIB_DIR
			).simulation,
			0,
		)

	def test_the_confirmation_of_the_datenschutzhinweise_records_who_and_when(self):
		unconfirmed = self.settings()
		self.assertEqual(
			(unconfirmed.privacy_notice_confirmed_by, unconfirmed.privacy_notice_confirmed_on), (None, None)
		)
		confirmed = self.settings(privacy_notice_confirmed=1)
		self.assertEqual(confirmed.privacy_notice_confirmed_by, "Administrator")
		self.assertTrue(confirmed.privacy_notice_confirmed_on)
		again = self.settings(
			privacy_notice_confirmed=1,
			privacy_notice_confirmed_by=make_user(ACCOUNTS_MANAGER, "Accounts Manager"),
			privacy_notice_confirmed_on="2026-01-01 00:00:00",
		)
		self.assertEqual(
			(again.privacy_notice_confirmed_by, str(again.privacy_notice_confirmed_on)),
			("Administrator", str(confirmed.privacy_notice_confirmed_on)),
		)
		withdrawn = self.settings(privacy_notice_confirmed=0)
		self.assertEqual(
			(withdrawn.privacy_notice_confirmed_by, withdrawn.privacy_notice_confirmed_on), (None, None)
		)

	def test_the_simulation_does_not_depend_on_the_datenschutzhinweise(self):
		runtime = {"hersteller_id": "12345", "installed_version": "44.3.6.0", "lib_dir": LIB_DIR}
		self.assertEqual(self.settings(**runtime).simulation, 0)
		self.assertEqual(self.settings(**runtime, privacy_notice_confirmed=1).simulation, 0)
		self.assertEqual(self.settings(privacy_notice_confirmed=1).simulation, 1)

	def test_a_hersteller_id_has_five_digits(self):
		for value in ("1234", "123456", "12a45", "12 345"):
			with self.subTest(value=value), self.assertRaisesRegex(frappe.ValidationError, "five digits"):
				self.settings(hersteller_id=value)
		self.assertEqual(self.settings(hersteller_id=" 01234 ").hersteller_id, "01234")

	def test_refuses_the_hersteller_id_that_only_illustrates_the_documentation(self):
		with self.assertRaisesRegex(frappe.ValidationError, "74931"):
			self.settings(hersteller_id="74931")

	def test_the_product_name_is_short_and_without_elster(self):
		for name in ("ELSTER-Bote", "Mein Elster Werkzeug", "x" * 51):
			with self.subTest(name=name), self.assertRaises(frappe.ValidationError):
				self.settings(produkt_name=name)
		self.assertEqual(self.settings(produkt_name="Steuerbote Firma").produkt_name, "Steuerbote Firma")

	def test_the_datenlieferant_has_at_most_256_characters(self):
		self.assertEqual(len(self.settings(datenlieferant="a" * 256).datenlieferant), 256)
		with self.assertRaisesRegex(frappe.ValidationError, "256"):
			self.settings(datenlieferant="a" * 257)

	def test_the_copyright_notice_has_at_most_50_characters_elster_takes(self):
		"""The Vorsatz of every Erklärung carries it: „Copyrightvermerk des Herstellers der Steuersoftware“, at most 50
		characters (Jahresdokumentation E50 2026, sheet „Vorsatz - Felder“)."""
		self.assertEqual(self.settings(copyright=f"  {COPYRIGHT} ").copyright, COPYRIGHT)
		self.assertEqual(len(self.settings(copyright="x" * 50).copyright), 50)
		self.assertFalse(self.settings(copyright=" ").copyright)
		for value, message in (("x" * 51, "50"), ("© 2026 Beispiel Software GmbH", "U\\+00A9")):
			with self.subTest(value=value), self.assertRaisesRegex(frappe.ValidationError, message):
				self.settings(copyright=value)

	def test_the_copyright_notice_has_no_default(self):
		self.assertIsNone(frappe.get_meta(SETTINGS).get_field("copyright").default)

	def test_an_erklaerung_runs_through_eric_only_with_the_copyright_notice(self):
		"""Rules 10435 and 6 of the Vorsatz; the simulation takes the product name in its place."""
		runtime = {"hersteller_id": "12345", "installed_version": "44.3.6.0", "lib_dir": LIB_DIR}
		self.settings(**runtime, copyright=COPYRIGHT)
		self.assertEqual(vorsatz_copyright(), COPYRIGHT)
		self.settings(**runtime, copyright="")
		with self.assertRaisesRegex(frappe.ValidationError, "Copyright"):
			vorsatz_copyright()
		self.settings(copyright="", produkt_name="Steuerbote Firma")
		self.assertEqual(vorsatz_copyright(), "Steuerbote Firma")
		self.settings(copyright=COPYRIGHT)
		self.assertEqual(vorsatz_copyright(), COPYRIGHT)

	def test_the_archive_comes_from_the_bench_and_never_from_the_settings(self):
		"""The probe of an installation loads the library of the archive as the user of the bench, and the runtime
		serves every site of the bench: only its operator names the archive, in common_site_config.json."""
		uploaded = {"archive_path": UPLOADED, "archive_sha256": UPLOADED_CHECKSUM}
		site = {"steuerbote_eric_archive": UPLOADED, "steuerbote_eric_archive_sha256": UPLOADED_CHECKSUM}
		with self.configured(), patch.dict(frappe.local.conf, site):
			settings = self.settings(**uploaded)
			self.assertEqual((settings.archive_path or "", settings.archive_sha256 or ""), ("", ""))
			with (
				patch("frappe.enqueue") as enqueue,
				self.assertRaisesRegex(frappe.ValidationError, "common_site_config.json"),
			):
				settings.install_runtime()
			enqueue.assert_not_called()
		with (
			self.configured(**BENCH),
			patch.object(runtime, "install_from_archive", return_value=RUNTIME) as install,
			patch("frappe.publish_realtime"),
		):
			settings = self.settings(**uploaded)
			self.assertEqual((settings.archive_path, settings.archive_sha256), (ARCHIVE, CHECKSUM))
			with patch("frappe.enqueue") as enqueue:
				settings.install_runtime()
			enqueue.assert_called_once()
			run_installation()
		self.assertEqual(install.call_args.args[:2], (Path(ARCHIVE), CHECKSUM))

	def test_the_form_shows_the_archive_of_the_bench(self):
		settings = self.settings()
		with self.configured(
			steuerbote_eric_archive=f" {ARCHIVE} ", steuerbote_eric_archive_sha256="AB" * 32
		):
			settings.run_method("onload")
		self.assertEqual((settings.archive_path, settings.archive_sha256), (ARCHIVE, CHECKSUM))
		definition = frappe.get_meta(SETTINGS)
		for fieldname in ("archive_path", "archive_sha256"):
			with self.subTest(fieldname=fieldname):
				self.assertEqual(definition.get_field(fieldname).read_only, 1)

	def test_the_checksum_is_a_sha256_in_hex(self):
		with self.configured(
			steuerbote_eric_archive=ARCHIVE, steuerbote_eric_archive_sha256=f" {'AB' * 32} "
		):
			self.assertEqual(transmission_adapter.configured_archive(), (Path(ARCHIVE), CHECKSUM))
		for value in ("ab" * 31, "xy" * 32, 4711):
			with (
				self.subTest(value=value),
				self.configured(steuerbote_eric_archive=ARCHIVE, steuerbote_eric_archive_sha256=value),
				self.assertRaisesRegex(frappe.ValidationError, "64 hexadecimal digits"),
			):
				transmission_adapter.configured_archive()

	def test_the_archive_is_an_absolute_path_on_the_server(self):
		for value in (
			"ERiC-44.3.6.0-Linux-x86_64.jar",
			"eric/ERiC-44.3.6.0-Linux-x86_64.jar",
			"https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Linux-x86_64.jar",
		):
			with (
				self.subTest(value=value),
				self.configured(steuerbote_eric_archive=value, steuerbote_eric_archive_sha256=CHECKSUM),
				self.assertRaisesRegex(frappe.ValidationError, "absolute path on the server"),
			):
				transmission_adapter.configured_archive()

	def test_installing_needs_the_archive_and_its_checksum(self):
		settings = self.settings()
		for values in (
			{"steuerbote_eric_archive": ARCHIVE},
			{"steuerbote_eric_archive_sha256": CHECKSUM},
			{},
		):
			with self.subTest(values=values), self.configured(**values), patch("frappe.enqueue") as enqueue:
				with self.assertRaisesRegex(frappe.ValidationError, "bench set-config -g"):
					settings.install_runtime()
				enqueue.assert_not_called()

	def test_installing_runs_in_a_background_job_that_reads_the_archive_of_the_bench(self):
		settings = self.settings()
		with self.configured(**BENCH), patch("frappe.enqueue") as enqueue:
			settings.install_runtime()
		(call,) = enqueue.call_args_list
		self.assertEqual(call.args, (INSTALLATION_JOB,))
		self.assertEqual(
			call.kwargs,
			{
				"queue": "long",
				"timeout": 1800,
				"job_id": "steuerbote:eric:installation",
				"deduplicate": True,
				"enqueue_after_commit": True,
			},
		)

	def test_only_a_system_manager_installs(self):
		settings = self.settings()
		with (
			self.configured(**BENCH),
			self.set_user(make_user(ACCOUNTS_MANAGER, "Accounts Manager")),
			patch("frappe.enqueue") as enqueue,
			self.assertRaises(frappe.PermissionError),
		):
			settings.install_runtime()
		enqueue.assert_not_called()

	def test_the_runtimes_live_where_the_bench_says(self):
		with self.configured():
			self.assertEqual(transmission_adapter.runtime_root(), Path(get_bench_path(), "sites", "eric"))
		with self.configured(steuerbote_eric_root="/srv/eric"):
			self.assertEqual(transmission_adapter.runtime_root(), Path("/srv/eric"))
		with self.configured(), patch.dict(frappe.local.conf, {"steuerbote_eric_root": "/srv/elsewhere"}):
			self.assertEqual(transmission_adapter.runtime_root(), Path(get_bench_path(), "sites", "eric"))

	def test_the_installation_job_records_the_runtime(self):
		self.settings(hersteller_id="12345")
		runtime_info = RuntimeInfo(
			"44.3.6.0", Path(LIB_DIR), Path(LIB_DIR, "plugins"), Path("/srv/eric/logs"), "12345"
		)
		with (
			self.configured(**BENCH),
			patch.object(runtime, "install_from_archive", return_value=runtime_info) as install,
			patch("frappe.publish_realtime") as publish,
		):
			run_installation()
		self.assertEqual(
			install.call_args.args, (Path(ARCHIVE), CHECKSUM, transmission_adapter.runtime_root())
		)
		self.assertEqual(install.call_args.kwargs["installed_by"], "Administrator")
		self.assertIs(install.call_args.kwargs["probe"], service.library_versions)
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(settings.installed_version, settings.lib_dir, settings.log_dir, settings.simulation),
			("44.3.6.0", LIB_DIR, str(eric_log_root()), 0),
		)
		self.assertTrue(eric_log_root().is_absolute())
		self.assertTrue(settings.last_check)
		self.assertEqual(
			publish.call_args.args,
			("steuerbote_eric_installation", {"ok": True, "version": "44.3.6.0", "error": None}),
		)
		self.assertEqual(publish.call_args.kwargs["user"], frappe.session.user)

	def test_the_installation_reads_the_versionsinformationen_of_its_runtime(self):
		"""EricVersion gives the product version of the libraries ERiC loaded; the Versionsinformationen of the package
		give that of every library, and the manifest keeps both."""
		self.settings()
		directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-installation-"))
		self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
		archive = directory / "ERiC-44.3.6.0-Linux-x86_64.jar"
		with zipfile.ZipFile(archive, "w") as jar:
			for name in RUNTIME_FILES.values():
				jar.writestr(f"ERiC-44.3.6.0/Linux-x86_64/lib/{name}", name.encode())
		checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
		root = directory / "eric"

		probed = {"libericapi.so": "44, 3, 6, 0", "libcommonData.so": ""}

		def install() -> RuntimeInfo:
			return runtime.install_from_archive(archive, checksum, root, probe=lambda info: dict(probed))

		listed = dict.fromkeys(RUNTIME_FILES, "44, 3, 6, 0")
		with (
			self.configured(),
			patch.object(transmission_adapter, "install_configured_archive", side_effect=install),
			patch.object(transmission_adapter, "runtime_root", return_value=root),
			patch.object(releases, "fetch_versions", return_value=versionsinformationen(listed)) as fetch,
			patch("frappe.publish_realtime") as publish,
		):
			run_installation()
		fetch.assert_called_once_with("44.3.6.0", opener=None)
		(installation,) = runtime.installations(root)
		self.assertEqual(
			(dict(installation.listed_versions), dict(installation.library_versions)),
			(listed, probed),
		)
		self.assertEqual(publish.call_args.args[1]["ok"], True)

	def test_an_installation_whose_versionsinformationen_cannot_be_read_still_succeeds(self):
		"""The weekly check reads them later; meanwhile the Error Log says why they are missing."""
		self.settings()
		root = Path(tempfile.mkdtemp(prefix="steuerbote-eric-installation-")) / "eric"
		self.addCleanup(shutil.rmtree, root.parent, ignore_errors=True)
		archive = root.parent / "ERiC-44.3.6.0-Linux-x86_64.jar"
		with zipfile.ZipFile(archive, "w") as jar:
			for name in RUNTIME_FILES.values():
				jar.writestr(f"ERiC-44.3.6.0/Linux-x86_64/lib/{name}", name.encode())
		checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
		logged = frappe.db.count("Error Log")
		with (
			self.configured(),
			patch.object(
				transmission_adapter,
				"install_configured_archive",
				side_effect=lambda: runtime.install_from_archive(archive, checksum, root),
			),
			patch.object(transmission_adapter, "runtime_root", return_value=root),
			patch.object(releases, "fetch_versions", side_effect=TimeoutError("timed out")),
			patch("frappe.publish_realtime") as publish,
		):
			run_installation()
		self.assertEqual(
			publish.call_args.args,
			("steuerbote_eric_installation", {"ok": True, "version": "44.3.6.0", "error": None}),
		)
		self.assertEqual(frappe.get_single(SETTINGS).installed_version, "44.3.6.0")
		self.assertEqual(frappe.db.count("Error Log"), logged + 1)

	def test_a_failed_installation_keeps_the_settings_and_says_why(self):
		self.settings()
		with (
			self.configured(**BENCH),
			patch.object(
				runtime,
				"install_from_archive",
				side_effect=RuntimeInstallError(
					f"Die SHA-256-Summe des Archivs ist {'cd' * 32}, erwartet war {CHECKSUM}."
				),
			),
			patch("frappe.publish_realtime") as publish,
		):
			run_installation()
		settings = frappe.get_single(SETTINGS)
		self.assertEqual((settings.installed_version or "", settings.simulation), ("", 1))
		self.assertTrue(settings.last_check)
		event, message = publish.call_args.args
		self.assertEqual(
			(event, message["ok"], message["version"]), ("steuerbote_eric_installation", False, None)
		)
		self.assertIn("erwartet war", message["error"])

	def test_an_installation_on_another_platform_says_where_eric_runs(self):
		"""ERiC for Linux runs on Intel 64 and AMD64 only (ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 2-1): the job refuses
		the site before it reads the archive, and whoever started it reads why in their own language."""
		self.settings()
		logged = frappe.db.count("Error Log")
		with (
			self.configured(**BENCH),
			patch.object(runtime, "_platform", return_value=("linux", "aarch64", "glibc 2.41")),
			patch("frappe.publish_realtime") as publish,
		):
			run_installation()
		settings = frappe.get_single(SETTINGS)
		self.assertEqual((settings.installed_version or "", settings.simulation), ("", 1))
		self.assertEqual(
			publish.call_args.args,
			(
				"steuerbote_eric_installation",
				{
					"ok": False,
					"version": None,
					"error": "ERiC runs on Linux x86_64 only; this site runs on linux aarch64.",
				},
			),
		)
		self.assertEqual(frappe.db.count("Error Log"), logged)
		self.assertEqual(
			frappe._(runtime.UNSUPPORTED_SITE, lang="de").format("linux", "aarch64"),
			"ERiC läuft nur auf Linux x86_64; diese Site läuft auf linux aarch64.",
		)

	def test_an_unexpected_failure_of_the_installation_is_logged(self):
		self.settings()
		logged = frappe.db.count("Error Log")
		with (
			self.configured(**BENCH),
			patch.object(runtime, "install_from_archive", side_effect=OSError("Datenträger voll")),
			patch("frappe.publish_realtime") as publish,
		):
			run_installation()
		self.assertEqual(frappe.db.count("Error Log"), logged + 1)
		self.assertIn("Datenträger voll", publish.call_args.args[1]["error"])

	def test_an_installation_without_the_archive_of_the_bench_says_how_to_name_it(self):
		self.settings()
		with self.configured(), patch("frappe.publish_realtime") as publish:
			run_installation()
		event, message = publish.call_args.args
		self.assertEqual((event, message["ok"]), ("steuerbote_eric_installation", False))
		self.assertIn("common_site_config.json", message["error"])

	def runtime_root(self, *plugins: str) -> Path:
		"""A runtime of ERiC 44.3.6.0 installed from an archive of invented files, with the plugins named."""
		directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-status-"))
		self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
		archive = directory / "ERiC-44.3.6.0-Linux-x86_64.jar"
		lib = "ERiC-44.3.6.0/Linux-x86_64/lib"
		with zipfile.ZipFile(archive, "w") as jar:
			for name in (
				"libericapi.so",
				"plugins2/libcommonData.so",
				*(f"plugins2/lib{plugin}.so" for plugin in plugins),
			):
				jar.writestr(f"{lib}/{name}", name.encode())
		checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
		runtime.install_from_archive(archive, checksum, directory / "eric")
		return directory / "eric"

	def test_the_status_of_the_runtime_names_the_plugin_of_the_zusammenfassende_meldung(self):
		"""steuerbote.eric.runtime.status: the plugin checkZMDO serves the ZM of every year."""
		settings = self.settings(hersteller_id="12345")
		for plugins, ok, detail in (
			(("checkZMDO",), True, "ERiC 44.3.6.0 prüft und sendet die Zusammenfassende Meldung (ZMDO)."),
			((), False, "Für die Zusammenfassende Meldung (ZMDO) fehlt ERiC mit dem Plugin libcheckZMDO.so."),
		):
			with (
				self.subTest(plugins=plugins),
				patch.object(transmission_adapter, "runtime_root", return_value=self.runtime_root(*plugins)),
			):
				checks = {check["name"]: check for check in settings.check_runtime()}
				self.assertEqual((checks["zmdo"]["ok"], checks["zmdo"]["detail"]), (ok, detail))
				self.assertEqual(
					(checks["runtime"]["ok"], checks["hersteller_id"]["detail"]),
					(True, "Hersteller-ID 12345."),
				)
				self.assertIn("plugin", checks)

	def test_only_a_system_manager_checks_the_runtime(self):
		settings = self.settings()
		with (
			self.set_user(make_user(ACCOUNTS_MANAGER, "Accounts Manager")),
			self.assertRaises(frappe.PermissionError),
		):
			settings.check_runtime()

	def test_the_form_shows_the_status_of_the_runtime(self):
		script = get_form_meta(SETTINGS, cached=False).get("__js")
		self.assertIn('frm.call("check_runtime")', script)

	def test_every_text_of_the_settings_reads_in_german(self):
		"""Labels, descriptions and options of the fields and the texts of controller and form, in
		translations/de.csv, apart from the German terms every language shows as they are."""
		folder = Path(__file__).parent
		literal = re.compile(r'\b_{1,2}\(\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
		texts = set()
		for name in ("eric_settings.py", "eric_settings.js"):
			texts.update(literal.findall((folder / name).read_text(encoding="utf-8")))
		definition = json.loads((folder / "eric_settings.json").read_text(encoding="utf-8"))
		for field in definition["fields"]:
			texts.update(field[key] for key in ("label", "description") if field.get(key))
			if field["fieldtype"] == "Select":
				texts.update(option for option in field["options"].split("\n") if option)
		with Path(frappe.get_app_path("steuerbote", "translations", "de.csv")).open(
			encoding="utf-8", newline=""
		) as file:
			german = dict(csv.reader(file))
		self.assertEqual(
			sorted(texts - german.keys() - {"Datenschutzhinweise", "Hersteller-ID", "Proxy"}), []
		)


class TestERiCVersions(IntegrationTestCase):
	"""The weekly check of the ERiC versions: the Mindestversionsliste of ELSTER, kept in the ERiC Settings, compared
	with the installed runtimes, and a notice to the System Managers once for each finding."""

	def setUp(self):
		frappe.db.savepoint("eric_versions_test")
		self.addCleanup(frappe.db.rollback, save_point="eric_versions_test")
		self.manager = make_user(SYSTEM_MANAGER, "System Manager")
		# Whether a site keeps annual filings depends on the Annual Filing Settings of other tests; these tests say it.
		annual = patch.object(eric_settings, "has_annual_filings", return_value=False)
		annual.start()
		self.addCleanup(annual.stop)

	def runtime_root(self, versions: dict[str, str] | None) -> Path:
		"""A runtime of ERiC 44.3.6.0 with the plugin of 2026 whose probe read the product versions, or an empty root
		for None."""
		directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-versions-"))
		self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
		if versions is None:
			return directory / "eric"
		archive = directory / "ERiC-44.3.6.0-Linux-x86_64.jar"
		lib = "ERiC-44.3.6.0/Linux-x86_64/lib"
		with zipfile.ZipFile(archive, "w") as jar:
			for name in ("libericapi.so", "plugins2/libcommonData.so", "plugins2/libcheckUStVA_2026.so"):
				jar.writestr(f"{lib}/{name}", name.encode())
		checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
		runtime.install_from_archive(archive, checksum, directory / "eric", probe=lambda info: dict(versions))
		return directory / "eric"

	def check_versions(
		self,
		root: Path,
		fetched=PUBLISHED,
		error=None,
		day="2026-11-23 04:00:00",
		mail_error=None,
		versions=None,
		versions_error=None,
		email_account=True,
	):
		"""One run of the weekly job on the day, with the list the fetch returns or the error it raises; returns the
		e-mails it would send.

		Without versions, the Versionsinformationen of a runtime without them list the product versions its probe read,
		as for a package whose EricVersion named them all; the mock of their fetch stays in fetched_versions."""
		listed = versions if versions is not None else self.probed(root)
		with (
			self.freeze_time(day),
			patch.object(releases, "fetch_list", return_value=fetched, side_effect=error),
			patch.object(
				releases, "fetch_versions", return_value=listed, side_effect=versions_error
			) as fetch,
			patch.object(transmission_adapter, "runtime_root", return_value=root),
			patch.object(eric_settings, "has_outgoing_email_account", return_value=email_account),
			patch.object(frappe, "sendmail", side_effect=mail_error) as sendmail,
		):
			check_versions()
		self.fetched_versions = fetch
		return sendmail

	def probed(self, root: Path) -> str:
		"""Versionsinformationen with the product versions the probe read of the runtime under root."""
		installed = runtime.installations(root)
		return versionsinformationen(dict(installed[0].library_versions)) if installed else ""

	def checked(self, root: Path, day: str = "2026-11-23 10:00:00") -> dict[str, dict]:
		"""What Laufzeitumgebung prüfen shows on the day, by check."""
		settings = frappe.get_single(SETTINGS)
		with self.freeze_time(day), patch.object(transmission_adapter, "runtime_root", return_value=root):
			return {check["name"]: check for check in settings.check_runtime()}

	def notifications(self) -> list[frappe._dict]:
		return frappe.get_all(
			"Notification Log",
			filters={"for_user": self.manager, "document_type": SETTINGS},
			fields=["subject", "email_content"],
			order_by="creation",
		)

	def error_logs(self) -> set[str]:
		"""The Error Logs of the ERiC Settings. Frappe keeps them in a table outside the transaction, so they stay when
		a test rolls back."""
		return set(
			frappe.get_all(
				"Error Log", filters={"reference_doctype": SETTINGS, "reference_name": SETTINGS}, pluck="name"
			)
		)

	def test_the_weekly_check_keeps_the_list_and_tells_the_system_managers_once_of_each_finding(self):
		root = self.runtime_root(OUTDATED)
		sendmail = self.check_versions(root)
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(settings.minimum_list_version, settings.minimum_eric_version, settings.versions_check_failed),
			("2.26.4.1", "43.2.6.0", 0),
		)
		self.assertEqual(get_datetime(settings.versions_checked_on), get_datetime("2026-11-23 04:00:00"))
		self.assertEqual(
			get_datetime(settings.minimum_list_modified),
			convert_utc_to_system_timezone(LIST_CHANGED).replace(tzinfo=None),
		)
		self.assertEqual(MinimumList.from_json(settings.minimum_versions), releases.parse_list(MINIMUM_LIST))
		self.assertEqual(
			settings.version_notices.splitlines(), ["minimum 2.26.4.1 44.3.6.0", "next-year 2027"]
		)
		(notification,) = self.notifications()
		self.assertEqual(notification.subject, "Steuerbote: ERiC-Laufzeitumgebung prüfen")
		self.assertIn("Die wöchentliche Prüfung der ERiC-Versionen meldet:", notification.email_content)
		self.assertIn(
			"Abgleich mit der Mindestversionsliste 2.26.4.1: ERiC 44.3.6.0: libericapi.so 43.1.2.0 statt mindestens 43.2.6.0.",
			notification.email_content,
		)
		self.assertIn(
			"Für das Jahr 2027 fehlt ERiC mit dem Plugin libcheckUStVA_2027.so.", notification.email_content
		)
		mail = sendmail.call_args.kwargs
		sendmail.assert_called_once()
		self.assertIn(SYSTEM_MANAGER, mail["recipients"])
		self.assertNotIn("Administrator", mail["recipients"])
		self.assertEqual(mail["subject"], "Steuerbote: ERiC-Laufzeitumgebung prüfen")
		self.assertIn(
			"Abgleich mit der Mindestversionsliste 2.26.4.1: ERiC 44.3.6.0: libericapi.so 43.1.2.0 statt mindestens 43.2.6.0.",
			mail["message"],
		)
		self.assertIn("/desk/eric-settings", mail["message"])
		self.assertEqual((mail["reference_doctype"], mail["reference_name"]), (SETTINGS, SETTINGS))

		self.check_versions(root, day="2026-11-30 04:00:00").assert_not_called()
		self.assertEqual(len(self.notifications()), 1)

		newer = FetchedList(MINIMUM_LIST.replace("version: 2.26.4.1", "version: 2.27.4.1", 1), LIST_CHANGED)
		self.check_versions(root, fetched=newer, day="2026-12-07 04:00:00").assert_called_once()
		latest = self.notifications()[-1].email_content
		self.assertIn("Abgleich mit der Mindestversionsliste 2.27.4.1", latest)
		self.assertNotIn("2027", latest)

	def test_a_new_year_without_its_plugin_is_told_once_more(self):
		root = self.runtime_root(CURRENT)
		self.check_versions(root).assert_called_once()
		self.check_versions(root, day="2027-01-04 04:00:00").assert_called_once()
		self.assertIn(
			"Für das Jahr 2027 fehlt ERiC mit dem Plugin libcheckUStVA_2027.so.",
			self.notifications()[-1].email_content,
		)
		self.assertEqual(frappe.get_single(SETTINGS).version_notices, "year 2027")

	def test_a_site_with_annual_filings_hears_from_1_january_of_the_plugins_of_the_year_before(self):
		root = self.runtime_root(CURRENT)
		with patch.object(eric_settings, "has_annual_filings", return_value=True):
			self.check_versions(root, day="2027-01-04 04:00:00").assert_called_once()
		self.assertEqual(
			frappe.get_single(SETTINGS).version_notices.splitlines(),
			[
				"year 2027",
				"annual USt_2026",
				"annual KSt_30_2026",
				"annual GewSt_2026",
				"annual Bilanz_6.9",
			],
		)
		self.assertIn(
			"Für die Körperschaftsteuererklärung 2026 fehlt ERiC mit dem Plugin libcheckKSt_2026.so.",
			self.notifications()[-1].email_content,
		)

	def test_laufzeitumgebung_pruefen_lists_from_1_january_the_plugins_of_the_annual_filings(self):
		settings = frappe.get_single(SETTINGS)
		root = self.runtime_root(CURRENT)
		with (
			self.freeze_time("2027-01-04 10:00:00"),
			patch.object(transmission_adapter, "runtime_root", return_value=root),
		):
			checks = {check["name"]: check for check in settings.check_runtime()}
		self.assertEqual(
			list(checks)[-5:],
			["ust", "kst", "gewst", "bilanz", "taxonomy_6_9"],
		)
		self.assertEqual(
			checks["ust"]["detail"],
			"Für die Umsatzsteuererklärung 2026 fehlt ERiC mit dem Plugin libcheckUSt_2026.so.",
		)

	def test_a_runtime_that_serves_the_year_and_reaches_the_list_brings_no_notice(self):
		self.check_versions(self.runtime_root(CURRENT), day="2026-06-01 04:00:00").assert_not_called()
		self.assertEqual(self.notifications(), [])
		self.assertEqual(frappe.get_single(SETTINGS).version_notices or "", "")

	def test_a_site_without_a_runtime_loads_the_list_and_tells_nobody(self):
		self.check_versions(self.runtime_root(None), day="2027-01-04 04:00:00").assert_not_called()
		self.assertEqual(self.notifications(), [])
		self.assertEqual(frappe.get_single(SETTINGS).minimum_list_version, "2.26.4.1")

	def test_a_failed_fetch_lands_in_the_error_log_once_and_never_raises(self):
		root = self.runtime_root(CURRENT)
		self.check_versions(root)
		logged = self.error_logs()
		sendmail = self.check_versions(
			root, error=urllib.error.URLError("Name or service not known"), day="2026-11-30 04:00:00"
		)
		(log,) = self.error_logs() - logged
		self.assertIn("Name or service not known", frappe.db.get_value("Error Log", log, "error"))
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(
				settings.versions_check_failed,
				get_datetime(settings.versions_checked_on),
				settings.minimum_list_version,
			),
			(1, get_datetime("2026-11-30 04:00:00"), "2.26.4.1"),
		)
		sendmail.assert_not_called()
		self.check_versions(root, day="2026-12-07 04:00:00")
		self.assertEqual(frappe.get_single(SETTINGS).versions_check_failed, 0)

	def test_a_list_of_another_form_counts_as_a_failed_fetch(self):
		root = self.runtime_root(CURRENT)
		logged = self.error_logs()
		self.check_versions(root, fetched=FetchedList("version: 2.26.4.1\n", None))
		self.assertEqual(len(self.error_logs() - logged), 1)
		settings = frappe.get_single(SETTINGS)
		self.assertEqual((settings.versions_check_failed, settings.minimum_list_version or ""), (1, ""))

	def test_without_a_list_the_check_still_tells_of_the_years(self):
		root = self.runtime_root(CURRENT)
		self.check_versions(root, error=TimeoutError("timed out")).assert_called_once()
		(notification,) = self.notifications()
		self.assertIn("Für das Jahr 2027 fehlt ERiC", notification.email_content)
		self.assertNotIn("Mindestversionsliste", notification.email_content)

	def test_a_notice_that_cannot_be_sent_is_sent_with_the_next_check(self):
		"""The check itself succeeded, so only the notice says that it failed."""
		root = self.runtime_root(OUTDATED)
		logged = self.error_logs()
		self.check_versions(root, mail_error=frappe.OutgoingEmailError("SMTP nicht erreichbar"))
		self.assertEqual(len(self.error_logs() - logged), 1)
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(settings.versions_check_failed, settings.version_notice_status, settings.version_notices or ""),
			(0, "Not Delivered", ""),
		)
		self.assertEqual(get_datetime(settings.version_notified_on), get_datetime("2026-11-23 04:00:00"))
		self.assertEqual(self.notifications(), [])
		self.check_versions(root, day="2026-11-30 04:00:00").assert_called_once()
		self.assertEqual(len(self.notifications()), 1)
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(settings.version_notice_status, get_datetime(settings.version_notified_on)),
			("E-Mail and Notification", get_datetime("2026-11-30 04:00:00")),
		)

	def test_without_an_outgoing_email_account_the_notice_is_a_notification_and_one_hint(self):
		"""A site without an outgoing e-mail account still checks; its System Managers find the notice among their
		notifications, and the Error Log says once, without a traceback, why no e-mail went out."""
		root = self.runtime_root(OUTDATED)
		logged = self.error_logs()
		self.check_versions(root, email_account=False).assert_not_called()
		(notification,) = self.notifications()
		self.assertIn("libericapi.so 43.1.2.0 statt mindestens 43.2.6.0", notification.email_content)
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(
				settings.versions_check_failed,
				settings.version_notice_status,
				settings.version_notices.splitlines(),
			),
			(0, "Notification Only", ["minimum 2.26.4.1 44.3.6.0", "next-year 2027"]),
		)
		self.assertEqual(get_datetime(settings.version_notified_on), get_datetime("2026-11-23 04:00:00"))
		(hint,) = self.error_logs() - logged
		self.assertEqual(
			frappe.db.get_value("Error Log", hint, "error"),
			"No outgoing e-mail account is set up, so the System Managers got the notice of the ERiC versions as a "
			"notification only, without an e-mail.",
		)
		self.check_versions(root, day="2026-11-30 04:00:00", email_account=False).assert_not_called()
		self.assertEqual(self.error_logs() - logged, {hint})

	def test_the_notice_asks_frappe_for_the_outgoing_email_account_as_sendmail_does(self):
		with patch.object(EmailAccount, "find_outgoing", return_value=None) as find:
			self.assertFalse(eric_settings.has_outgoing_email_account())
		find.assert_called_once_with(match_by_doctype=SETTINGS)
		with patch.object(EmailAccount, "find_outgoing", return_value=frappe._dict(name="Steuerbote")):
			self.assertTrue(eric_settings.has_outgoing_email_account())

	def test_without_a_system_manager_besides_administrator_the_form_says_that_nobody_heard(self):
		with patch.object(eric_settings, "system_manager_addresses", return_value=[]):
			self.check_versions(self.runtime_root(OUTDATED)).assert_not_called()
		self.assertEqual(self.notifications(), [])
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(settings.versions_check_failed, settings.version_notice_status), (0, "No Recipients")
		)

	def test_the_check_and_its_notice_are_recorded_apart(self):
		"""The notice of new findings keeps its state while they last, and goes once nothing fails."""
		outdated = self.runtime_root(OUTDATED)
		self.check_versions(outdated, day="2026-06-01 04:00:00")
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(
				settings.versions_check_failed,
				settings.version_notice_status,
				get_datetime(settings.version_notified_on),
			),
			(0, "E-Mail and Notification", get_datetime("2026-06-01 04:00:00")),
		)
		self.check_versions(outdated, day="2026-06-08 04:00:00").assert_not_called()
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(
				get_datetime(settings.versions_checked_on),
				settings.version_notice_status,
				get_datetime(settings.version_notified_on),
			),
			(
				get_datetime("2026-06-08 04:00:00"),
				"E-Mail and Notification",
				get_datetime("2026-06-01 04:00:00"),
			),
		)
		self.check_versions(self.runtime_root(CURRENT), day="2026-06-15 04:00:00").assert_not_called()
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(
				settings.version_notices or "",
				settings.version_notice_status or "",
				settings.version_notified_on,
			),
			("", "", None),
		)

	def test_a_failed_notice_is_no_longer_shown_once_its_findings_are_gone_while_older_ones_last(self):
		"""What was told before stays told; the notice that failed has nothing left to deliver."""
		root = self.runtime_root(CURRENT)
		self.check_versions(root, day="2026-11-23 04:00:00").assert_called_once()
		self.assertEqual(frappe.get_single(SETTINGS).version_notices, "next-year 2027")
		newer = FetchedList(MINIMUM_LIST.replace("version: 2.26.4.1", "version: 2.27.4.1", 1), LIST_CHANGED)
		self.check_versions(
			self.runtime_root(OUTDATED),
			fetched=newer,
			day="2026-11-30 04:00:00",
			mail_error=RuntimeError("kaputt"),
		)
		self.assertEqual(frappe.get_single(SETTINGS).version_notice_status, "Not Delivered")
		self.check_versions(root, fetched=newer, day="2026-12-07 04:00:00").assert_not_called()
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(settings.version_notices, settings.version_notice_status or ""), ("next-year 2027", "")
		)

	def test_libraries_without_a_read_version_are_a_hint_of_laufzeitumgebung_pruefen(self):
		"""EricVersion of ERiC 44.3.6.0 gave the product version of a few libraries only. Until the
		Versionsinformationen of the package are read, the others are not compared, and the check does not fail."""
		root = self.runtime_root(
			{"libericapi.so": "44, 3, 6, 0", "libcommonData.so": "", "libcheckUStVA_2026.so": ""}
		)
		logged = self.error_logs()
		self.check_versions(
			root, versions_error=urllib.error.URLError("Name or service not known"), day="2026-06-01 04:00:00"
		).assert_not_called()
		(log,) = self.error_logs() - logged
		self.assertEqual(
			frappe.db.get_value("Error Log", log, "error"),
			f"ERiC 44.3.6.0: Die Versionsinformationen von {VERSIONS_44} ließen sich nicht laden: <urlopen error Name "
			"or service not known>.",
		)
		settings = frappe.get_single(SETTINGS)
		self.assertEqual((settings.versions_check_failed, settings.version_notices or ""), (0, ""))
		minimum = self.checked(root, "2026-06-01 10:00:00")["minimum"]
		self.assertTrue(minimum["ok"])
		self.assertIn(
			"Ohne gelesene Version und deshalb nicht verglichen: ERiC 44.3.6.0: libcheckUStVA_2026.so, "
			"libcommonData.so.",
			minimum["detail"],
		)

		read = versionsinformationen(dict.fromkeys(RUNTIME_FILES, "44, 3, 6, 0"))
		self.check_versions(root, versions=read, day="2026-06-08 04:00:00")
		self.fetched_versions.assert_called_once_with("44.3.6.0", opener=None)
		(installation,) = runtime.installations(root)
		self.assertEqual(installation.listed_versions_source, VERSIONS_44)
		self.assertEqual(
			self.checked(root, "2026-06-08 10:00:00")["minimum"]["detail"],
			"ERiC 44.3.6.0 erreicht die Mindestversionen der Mindestversionsliste 2.26.4.1 (libericapi.so ab "
			"43.2.6.0).",
		)
		self.check_versions(root, day="2026-06-15 04:00:00")
		self.fetched_versions.assert_not_called()

	def test_a_site_without_access_to_the_download_server_takes_the_copy_the_operator_names(self):
		root = self.runtime_root(CURRENT)
		copy = root.parent / "ERiC-44.3.6.0-Linux-x86_64.version.txt"
		copy.write_text(versionsinformationen(CURRENT), encoding="utf-8")
		with patch.object(
			transmission_adapter,
			"common_site_config",
			return_value=frappe._dict(steuerbote_eric_versions=f" {copy} "),
		):
			self.check_versions(root, versions_error=urllib.error.URLError("Network is unreachable"))
		self.fetched_versions.assert_not_called()
		(installation,) = runtime.installations(root)
		self.assertEqual(
			(dict(installation.listed_versions), installation.listed_versions_source), (CURRENT, str(copy))
		)

	def test_the_copy_is_an_absolute_path_on_the_server(self):
		root = self.runtime_root(CURRENT)
		logged = self.error_logs()
		with patch.object(
			transmission_adapter,
			"common_site_config",
			return_value=frappe._dict(steuerbote_eric_versions="ERiC-44.3.6.0-Linux-x86_64.version.txt"),
		):
			self.check_versions(root)
		(log,) = self.error_logs() - logged
		self.assertEqual(
			frappe.db.get_value("Error Log", log, "error"),
			"steuerbote_eric_versions in common_site_config.json is no absolute path on the server.",
		)
		self.fetched_versions.assert_called_once_with("44.3.6.0", opener=None)
		(installation,) = runtime.installations(root)
		self.assertEqual(installation.listed_versions_source, VERSIONS_44)

	def test_an_unexpected_failure_of_reading_the_versionsinformationen_never_stops_the_check(self):
		root = self.runtime_root(OUTDATED)
		logged = self.error_logs()
		with patch.object(releases, "complete_versions", side_effect=RuntimeError("unerwartet")):
			self.check_versions(root).assert_called_once()
		(log,) = self.error_logs() - logged
		self.assertIn("RuntimeError: unerwartet", frappe.db.get_value("Error Log", log, "error"))
		self.assertEqual(frappe.get_single(SETTINGS).minimum_list_version, "2.26.4.1")

	def test_the_status_of_the_runtime_compares_the_list_and_the_coming_year(self):
		settings = frappe.get_single(SETTINGS)
		root = self.runtime_root(OUTDATED)
		with (
			self.freeze_time("2026-11-23 10:00:00"),
			patch.object(transmission_adapter, "runtime_root", return_value=root),
		):
			checks = {check["name"]: check for check in settings.check_runtime()}
		self.assertEqual(
			(checks["minimum"]["ok"], checks["minimum"]["detail"]),
			(
				False,
				"Die Mindestversionsliste von ELSTER ist noch nicht geladen; die wöchentliche Prüfung der "
				"ERiC-Versionen lädt sie.",
			),
		)
		self.check_versions(root)
		with (
			self.freeze_time("2026-11-23 10:00:00"),
			patch.object(transmission_adapter, "runtime_root", return_value=root),
		):
			checks = {check["name"]: check for check in settings.check_runtime()}
		self.assertEqual(
			list(checks),
			[
				"platform",
				"runtime",
				"libraries",
				"plugin",
				"zmdo",
				"hersteller_id",
				"minimum",
				"plugin_next",
				"taxonomy_6_9",
			],
		)
		self.assertFalse(checks["minimum"]["ok"])
		self.assertIn("libericapi.so 43.1.2.0 statt mindestens 43.2.6.0", checks["minimum"]["detail"])
		self.assertEqual(
			checks["plugin_next"],
			{
				"name": "plugin_next",
				"ok": False,
				"detail": "Für das Jahr 2027 fehlt ERiC mit dem Plugin libcheckUStVA_2027.so.",
			},
		)

	def test_a_save_keeps_what_the_weekly_check_wrote(self):
		self.check_versions(self.runtime_root(OUTDATED))
		written = {
			fieldname: frappe.get_single(SETTINGS).get(fieldname) for fieldname in VERSION_CHECK_FIELDS
		}
		settings = frappe.get_single(SETTINGS)
		settings.update(
			{
				"minimum_list_version": "9.9.9.9",
				"minimum_list_modified": "2020-01-01 00:00:00",
				"minimum_eric_version": "1.0.0.0",
				"minimum_versions": "{}",
				"versions_checked_on": "2020-01-01 00:00:00",
				"versions_check_failed": 1,
				"version_notices": "",
				"version_notice_status": "Not Delivered",
				"version_notified_on": "2020-01-01 00:00:00",
			}
		)
		settings.save()
		self.assertEqual(
			{fieldname: frappe.get_single(SETTINGS).get(fieldname) for fieldname in VERSION_CHECK_FIELDS},
			written,
		)
		definition = frappe.get_meta(SETTINGS)
		for fieldname in VERSION_CHECK_FIELDS:
			with self.subTest(fieldname=fieldname):
				self.assertEqual(definition.get_field(fieldname).read_only, 1)

	def test_the_form_says_when_the_check_failed(self):
		script = get_form_meta(SETTINGS, cached=False).get("__js")
		self.assertIn("versions_check_failed", script)

	def test_the_form_says_how_the_notice_went_apart_from_the_check(self):
		script = get_form_meta(SETTINGS, cached=False).get("__js")
		self.assertIn("version_notice_status", script)
		self.assertIn("version_notified_on", script)
		self.assertEqual(
			frappe.get_meta(SETTINGS).get_field("version_notice_status").options.split("\n"),
			["", "E-Mail and Notification", "Notification Only", "No Recipients", "Not Delivered"],
		)


class TestAnnualFilings(IntegrationTestCase):
	"""Whether the site keeps annual filings, which decides whether the weekly check of the versions tells of the
	plugins of the annual filings. TestERiCVersions says it in each of its tests; this class asks the site."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		make_company(ANNUAL_FILINGS_COMPANY, "STEJ")

	def setUp(self) -> None:
		super().setUp()
		frappe.db.savepoint("annual_filings_test")
		self.addCleanup(frappe.db.rollback, save_point="annual_filings_test")

	def test_only_a_site_with_annual_filing_settings_keeps_annual_filings(self):
		"""The Annual Filing Settings come with the annual filings: a site keeps them once a company has its settings,
		and none while their table is missing, as before the migration that brings it."""
		frappe.db.delete(ANNUAL_FILING_SETTINGS)
		self.assertFalse(eric_settings.has_annual_filings())
		frappe.get_doc(
			{"doctype": ANNUAL_FILING_SETTINGS, "company": ANNUAL_FILINGS_COMPANY, "legal_form": "GmbH"}
		).insert()
		self.assertTrue(eric_settings.has_annual_filings())
		with patch.object(frappe.db, "table_exists", return_value=False):
			self.assertFalse(eric_settings.has_annual_filings())


class TestTaxonomy(IntegrationTestCase):
	"""Taxonomie einrichten: the HGB-Taxonomie whose package the operator names in common_site_config.json, installed
	outside every site. The package of the mini taxonomy (steuerbote/xbrl/tests/mini.py) stands in for the one of
	esteuer.de, so its checksum takes the place of the published one."""

	def setUp(self):
		super().setUp()
		directory = Path(tempfile.mkdtemp(prefix="steuerbote-taxonomy-settings-"))
		self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
		self.archive, self.checksum = mini.archive(directory)
		self.root = directory / "taxonomy"
		published = patch.object(
			eric_settings,
			"TAXONOMIES",
			MappingProxyType({"6.9": replace(TAXONOMIES["6.9"], archive_sha256=self.checksum)}),
		)
		published.start()
		self.addCleanup(published.stop)

	def bench(self, **values):
		"""common_site_config.json with the package of the mini taxonomy and the directory of the taxonomies."""
		config = {
			"steuerbote_taxonomy_6_9": str(self.archive),
			"steuerbote_taxonomy_6_9_sha256": self.checksum,
			"steuerbote_taxonomy_root": str(self.root),
			**values,
		}
		return patch.object(transmission_adapter, "common_site_config", return_value=frappe._dict(config))

	def install(self):
		with self.bench(), patch("frappe.publish_realtime") as publish:
			run_taxonomy_installation()
		return publish

	def test_the_form_shows_the_packages_of_the_bench_and_the_installed_versions(self):
		settings = frappe.get_single(SETTINGS)
		with self.bench():
			settings.run_method("onload")
		self.assertEqual(settings.taxonomy_archives, f"6.9: {self.archive} (SHA-256 {self.checksum})")
		self.assertFalse(settings.installed_taxonomies)
		self.install()
		with self.bench():
			settings.run_method("onload")
		for part in ("6.9", self.archive.name, "Administrator"):
			with self.subTest(part=part):
				self.assertIn(part, settings.installed_taxonomies)
		with self.bench(steuerbote_taxonomy_6_9="", steuerbote_taxonomy_6_9_sha256=""):
			settings.run_method("onload")
		self.assertIn("common_site_config.json", settings.taxonomy_archives)

	def test_what_the_form_shows_comes_from_the_bench_and_the_server(self):
		definition = frappe.get_meta(SETTINGS)
		for fieldname in ("taxonomy_archives", "installed_taxonomies"):
			with self.subTest(fieldname=fieldname):
				self.assertEqual(definition.get_field(fieldname).read_only, 1)
		settings = frappe.get_single(SETTINGS)
		settings.update(
			{
				"hersteller_id": "",
				"produkt_name": "steuerbote",
				"proxy_url": "",
				"taxonomy_archives": "6.9: /home/frappe/hochgeladen.zip",
				"installed_taxonomies": "6.9",
			}
		)
		with self.bench():
			settings.save()
		settings = frappe.get_single(SETTINGS)
		self.assertEqual(
			(settings.taxonomy_archives, settings.installed_taxonomies or ""),
			(f"6.9: {self.archive} (SHA-256 {self.checksum})", ""),
		)

	def test_installing_needs_the_package_of_the_bench_and_its_checksum(self):
		settings = frappe.get_single(SETTINGS)
		for values in (
			{"steuerbote_taxonomy_6_9": ""},
			{"steuerbote_taxonomy_6_9_sha256": ""},
			{"steuerbote_taxonomy_6_9": "", "steuerbote_taxonomy_6_9_sha256": ""},
		):
			with (
				self.subTest(values=values),
				self.bench(**values),
				patch("frappe.enqueue") as enqueue,
				self.assertRaisesRegex(frappe.ValidationError, "bench set-config -g"),
			):
				settings.install_taxonomy()
			enqueue.assert_not_called()

	def test_the_package_is_the_one_esteuer_publishes(self):
		"""The checksum the operator names is checked against the archive, and it is the one of steuerbote/xbrl/versions.py
		for the package esteuer.de publishes: a changed package changes the Mussfelder and the calculations of every
		check."""
		settings = frappe.get_single(SETTINGS)
		for values, message in (
			({"steuerbote_taxonomy_6_9_sha256": "ab" * 32}, "esteuer.de"),
			({"steuerbote_taxonomy_6_9_sha256": "xyz"}, "64 hexadecimal digits"),
			(
				{"steuerbote_taxonomy_6_9": "german-gaap-taxonomy-v6.9-2025-04-01-xbrl.zip"},
				"absolute path on the server",
			),
		):
			with (
				self.subTest(values=values),
				self.bench(**values),
				patch("frappe.enqueue") as enqueue,
				self.assertRaisesRegex(frappe.ValidationError, message),
			):
				settings.install_taxonomy()
			enqueue.assert_not_called()
		with self.bench(steuerbote_taxonomy_6_9_sha256=f" {self.checksum.upper()} "):
			self.assertEqual(eric_settings.configured_taxonomies(), {"6.9": (self.archive, self.checksum)})

	def test_installing_runs_in_a_background_job(self):
		settings = frappe.get_single(SETTINGS)
		with self.bench(), patch("frappe.enqueue") as enqueue:
			settings.install_taxonomy()
		(call,) = enqueue.call_args_list
		self.assertEqual(
			call.args,
			("steuerbote.steuerbote.doctype.eric_settings.eric_settings.run_taxonomy_installation",),
		)
		self.assertEqual(
			call.kwargs,
			{
				"queue": "long",
				"timeout": 900,
				"job_id": "steuerbote:taxonomy:installation",
				"deduplicate": True,
				"enqueue_after_commit": True,
			},
		)

	def test_only_a_system_manager_installs_the_taxonomy(self):
		settings = frappe.get_single(SETTINGS)
		with (
			self.bench(),
			self.set_user(make_user(ACCOUNTS_MANAGER, "Accounts Manager")),
			patch("frappe.enqueue") as enqueue,
			self.assertRaises(frappe.PermissionError),
		):
			settings.install_taxonomy()
		enqueue.assert_not_called()

	def test_the_job_installs_each_named_version_outside_every_site(self):
		publish = self.install()
		self.assertEqual(
			publish.call_args.args,
			("steuerbote_taxonomy_installation", {"ok": True, "versions": ["6.9"], "error": None}),
		)
		self.assertEqual(publish.call_args.kwargs["user"], frappe.session.user)
		installation = taxonomy.installed(self.root, TAXONOMIES["6.9"])
		self.assertEqual(
			(installation.archive_sha256, installation.installed_by), (self.checksum, "Administrator")
		)
		with self.bench():
			view = eric_settings.taxonomy_view("6.9", View.FISCAL)
			self.assertIs(eric_settings.taxonomy_view("6.9", View.FISCAL), view)
		self.assertEqual((view.version, view.view), ("6.9", View.FISCAL))
		self.assertTrue(view.has("de-gaap-ci:bs.ass"))

	def test_a_failed_installation_says_why(self):
		with (
			self.bench(steuerbote_taxonomy_6_9=str(self.archive.with_name("fehlt.zip"))),
			patch("frappe.publish_realtime") as publish,
		):
			run_taxonomy_installation()
		event, message = publish.call_args.args
		self.assertEqual(
			(event, message["ok"], message["versions"]), ("steuerbote_taxonomy_installation", False, [])
		)
		self.assertIn("lässt sich nicht lesen", message["error"])
		self.assertIsNone(taxonomy.installed(self.root, TAXONOMIES["6.9"]))

	def test_an_installation_without_a_package_of_the_bench_says_how_to_name_it(self):
		with (
			self.bench(steuerbote_taxonomy_6_9="", steuerbote_taxonomy_6_9_sha256=""),
			patch("frappe.publish_realtime") as publish,
		):
			run_taxonomy_installation()
		self.assertIn("common_site_config.json", publish.call_args.args[1]["error"])

	def test_an_unexpected_failure_of_the_installation_is_logged(self):
		logged = frappe.db.count("Error Log")
		with (
			self.bench(),
			patch.object(taxonomy, "install_from_archive", side_effect=OSError("Datenträger voll")),
			patch("frappe.publish_realtime") as publish,
		):
			run_taxonomy_installation()
		self.assertEqual(frappe.db.count("Error Log"), logged + 1)
		self.assertIn("Datenträger voll", publish.call_args.args[1]["error"])

	def test_laufzeitumgebung_pruefen_reports_each_version(self):
		settings = frappe.get_single(SETTINGS)
		with self.bench():
			checks = {check["name"]: check for check in settings.check_runtime()}
		self.assertFalse(checks["taxonomy_6_9"]["ok"])
		self.assertIn("Taxonomie einrichten", checks["taxonomy_6_9"]["detail"])
		self.install()
		with self.bench():
			checks = {check["name"]: check for check in settings.check_runtime()}
		self.assertEqual(
			checks["taxonomy_6_9"],
			{
				"name": "taxonomy_6_9",
				"ok": True,
				"detail": "Die HGB-Taxonomie 6.9 ist eingerichtet und unverändert.",
			},
		)

	def test_the_taxonomies_live_where_the_bench_says(self):
		with patch.object(transmission_adapter, "common_site_config", return_value=frappe._dict()):
			self.assertEqual(eric_settings.taxonomy_root(), Path(get_bench_path(), "sites", "taxonomy"))
		with self.bench():
			self.assertEqual(eric_settings.taxonomy_root(), self.root)

	def test_a_view_is_read_only_from_an_installed_version(self):
		for version in ("6.9", "7.0"):
			with (
				self.subTest(version=version),
				self.bench(),
				self.assertRaisesRegex(frappe.ValidationError, version.replace(".", r"\.")),
			):
				eric_settings.taxonomy_view(version, View.FISCAL)

	def test_the_form_installs_the_taxonomy(self):
		script = get_form_meta(SETTINGS, cached=False).get("__js")
		self.assertIn('frm.call("install_taxonomy")', script)
		self.assertIn("steuerbote_taxonomy_installation", script)
