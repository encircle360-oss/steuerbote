from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

import steuerbote
from steuerbote.eric.runtime import RuntimeInfo, RuntimeInstallError
from steuerbote.steuerbote.doctype.eric_settings.eric_settings import eric_log_root, run_installation
from steuerbote.steuerbote.doctype.vat_return import transmission_adapter

# The users of the tests are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]

SETTINGS = "ERiC Settings"
INSTALLATION_JOB = "steuerbote.steuerbote.doctype.eric_settings.eric_settings.run_installation"
ARCHIVE = "/srv/eric/ERiC-44.3.6.0-Linux-x86_64.jar"
CHECKSUM = "ab" * 32
LIB_DIR = "/srv/eric/44.3.6.0/lib"
ACCOUNTS_MANAGER = "steuerbote-eric-einstellungen@example.com"


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
				**values,
			}
		)
		settings.save()
		return frappe.get_single(SETTINGS)

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

	def test_the_checksum_is_a_sha256_in_hex(self):
		self.assertEqual(self.settings(archive_sha256=f" {'AB' * 32} ").archive_sha256, CHECKSUM)
		for value in ("ab" * 31, "xy" * 32):
			with self.subTest(value=value), self.assertRaisesRegex(frappe.ValidationError, "SHA-256"):
				self.settings(archive_sha256=value)

	def test_the_archive_is_an_absolute_path_on_the_server(self):
		self.assertEqual(self.settings(archive_path=f" {ARCHIVE} ").archive_path, ARCHIVE)
		for value in (
			"ERiC-44.3.6.0-Linux-x86_64.jar",
			"eric/ERiC-44.3.6.0-Linux-x86_64.jar",
			"https://download.elster.de/download/eric/eric_44/ERiC-44.3.6.0-Linux-x86_64.jar",
		):
			with (
				self.subTest(value=value),
				self.assertRaisesRegex(frappe.ValidationError, "absolute path on the server"),
			):
				self.settings(archive_path=value)

	def test_installing_needs_the_archive_and_its_checksum(self):
		for values in ({"archive_path": ARCHIVE}, {"archive_sha256": CHECKSUM}):
			settings = self.settings(**values)
			with self.subTest(values=values), patch("frappe.enqueue") as enqueue:
				with self.assertRaises(frappe.ValidationError):
					settings.install_runtime()
				enqueue.assert_not_called()

	def test_installing_runs_in_a_background_job_that_gets_the_archive_and_its_checksum(self):
		settings = self.settings(archive_path=ARCHIVE, archive_sha256=CHECKSUM)
		with patch("frappe.enqueue") as enqueue:
			settings.install_runtime()
		(call,) = enqueue.call_args_list
		self.assertEqual(call.args, (INSTALLATION_JOB,))
		self.assertEqual(
			call.kwargs,
			{
				"archive_path": ARCHIVE,
				"sha256": CHECKSUM,
				"queue": "long",
				"timeout": 1800,
				"job_id": "steuerbote:eric:installation",
				"deduplicate": True,
				"enqueue_after_commit": True,
			},
		)

	def test_only_a_system_manager_installs(self):
		settings = self.settings(archive_path=ARCHIVE, archive_sha256=CHECKSUM)
		with (
			self.set_user(make_user(ACCOUNTS_MANAGER, "Accounts Manager")),
			patch("frappe.enqueue") as enqueue,
			self.assertRaises(frappe.PermissionError),
		):
			settings.install_runtime()
		enqueue.assert_not_called()

	def test_the_installation_job_records_the_runtime(self):
		self.settings(hersteller_id="12345")
		runtime = RuntimeInfo(
			"44.3.6.0", Path(LIB_DIR), Path(LIB_DIR, "plugins"), Path("/srv/eric/logs"), "12345"
		)
		with (
			patch.object(transmission_adapter, "install_from_archive", return_value=runtime) as install,
			patch("frappe.publish_realtime") as publish,
		):
			run_installation(archive_path=ARCHIVE, sha256=CHECKSUM)
		install.assert_called_once_with(ARCHIVE, CHECKSUM)
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
			patch.object(
				transmission_adapter,
				"install_from_archive",
				side_effect=RuntimeInstallError(
					f"Die SHA-256-Summe des Archivs ist {'cd' * 32}, erwartet war {CHECKSUM}."
				),
			),
			patch("frappe.publish_realtime") as publish,
		):
			run_installation(archive_path=ARCHIVE, sha256=CHECKSUM)
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
			patch.object(
				transmission_adapter, "install_from_archive", side_effect=OSError("Datenträger voll")
			),
			patch("frappe.publish_realtime") as publish,
		):
			run_installation(archive_path=ARCHIVE, sha256=CHECKSUM)
		self.assertEqual(frappe.db.count("Error Log"), logged + 1)
		self.assertIn("Datenträger voll", publish.call_args.args[1]["error"])
