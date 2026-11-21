import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.desk.form.meta import get_meta as get_form_meta
from frappe.tests import IntegrationTestCase
from frappe.utils import get_bench_path

import steuerbote
from steuerbote.eric import runtime, service
from steuerbote.eric.proxy import Proxy
from steuerbote.eric.result import Operation
from steuerbote.eric.runtime import RuntimeInfo, RuntimeInstallError
from steuerbote.steuerbote.doctype.eric_settings.eric_settings import eric_log_root, run_installation
from steuerbote.steuerbote.doctype.vat_return import transmission_adapter

# The users of the tests are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]

SETTINGS = "ERiC Settings"
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
# The password of the proxy, invented.
PROXY_GEHEIM = "Proxy-Geheim-2026"


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
