"""ERiC-Einstellungen: what this installation needs to transmit through ERiC.

The Hersteller-ID belongs to the installation, not to a company, and so does the ERiC runtime. While either
is missing the settings simulate: Prüfen and Testsenden run against the simulation of steuerbote.eric and
nothing reaches the Finanzamt. Steuerbote ships no part of ERiC and never downloads it: the operator puts the
archive for Linux x86_64 from the ELSTER developer area on the server and names it with its SHA-256 in
common_site_config.json of the bench, which the settings show and never change, and the installation job unpacks
it through steuerbote.eric.runtime after checking its SHA-256. Before ERiC runs, the operator confirms the
Datenschutzhinweise of the tax administration (ERiC licence, § 5 Abs. 1 and 2); the settings keep who
confirmed them and when. The simulation needs no confirmation. Where the server reaches ELSTER through a proxy,
the settings name it, with its password in a Password field, and every run of ERiC goes through it; the
simulation reaches no server. "Laufzeitumgebung prüfen" shows the checks of steuerbote.eric.runtime.status: the
platform, the runtimes installed with their libraries, the plugins of the current year and of the Zusammenfassende
Meldung, and the Hersteller-ID; then those of steuerbote.eric.releases: the Mindestversionsliste of ELSTER and the
plugin of the coming year.

Every week check_versions loads the Mindestversionsliste, keeps it in the settings and tells the System Managers
once of each failing check of steuerbote.eric.releases.notices, as the ERiC licence asks the Softwarehersteller to
check regularly for new versions (§ 5 Abs. 4) and to use at least the Mindestversion (§ 5 Abs. 6); a site that keeps
Annual Filing Settings hears also of the plugins of the annual filings of the year before. Before it compares, it
reads the Versionsinformationen of each installed runtime whose manifest lacks them, as the installation does for
its runtime: from the copy common_site_config.json names as steuerbote_eric_versions, else from download.elster.de.
The settings keep whether the check failed apart from how its notice went out: by e-mail and as a notification, as a
notification only where no outgoing e-mail account is set up, to nobody without a System Manager besides
Administrator, or not at all, to be sent with the next check. Only that job writes its fields; a save of the form
keeps them. The version of the app follows each migration and shows whenever the form loads.

The settings keep the copyright notice of the manufacturer of the software, which the Vorsatz of every Erklärung
carries (steuerbote/elster/vorsatz.py), at most 50 characters and without a default. A run of ERiC with an Erklärung
needs it (vorsatz_copyright).

The HGB-Taxonomie of the E-Bilanz and the Offenlegung comes the way ERiC does: Steuerbote ships none, since its files
carry no licence that allows passing them on (steuerbote/xbrl/versions.py). The operator puts the package of each
version from esteuer.de on the server and names it in common_site_config.json, steuerbote_taxonomy_6_9 with its
SHA-256 as steuerbote_taxonomy_6_9_sha256, which must be the checksum versions.py records for the package esteuer.de
publishes. "Taxonomie einrichten" installs each named version in a background job through steuerbote.xbrl.taxonomy,
outside every site, in sites/taxonomy of the bench or where steuerbote_taxonomy_root names; "Laufzeitumgebung prüfen"
reports whether each version is installed and unchanged. taxonomy_view() gives the E-Bilanz and the Offenlegung the
parsed view of an installed version.
"""

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import frappe
from frappe import _
from frappe.database.utils import commit_after_response
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.model.document import Document
from frappe.utils import (
	cint,
	convert_utc_to_system_timezone,
	escape_html,
	format_datetime,
	get_bench_path,
	get_url_to_form,
	getdate,
	now_datetime,
	strip_html,
)
from frappe.utils.background_jobs import is_job_enqueued
from frappe.utils.user import get_system_managers

import steuerbote
from steuerbote.elster import ustva_xml, vorsatz
from steuerbote.eric import proxy, releases, runtime
from steuerbote.eric.releases import MinimumList, MinimumListError
from steuerbote.eric.runtime import Check, RuntimeInstallError, UnsupportedPlatform
from steuerbote.steuerbote.doctype.vat_return import transmission_adapter
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import xml_errors
from steuerbote.xbrl import taxonomy
from steuerbote.xbrl.taxonomy import Taxonomy, TaxonomyError, View
from steuerbote.xbrl.versions import TAXONOMIES

SETTINGS = "ERiC Settings"
ANNUAL_FILING_SETTINGS = "Annual Filing Settings"
DEFAULT_PRODUKT_NAME = "steuerbote"
# NutzdatenHeader of the ELSTER Basisschema: ProduktName has 1 to 50 characters.
PRODUKT_NAME_LENGTH = 50
# ERiC licence, § 12: "Der Produkt- oder Herstellername darf jedoch nicht den Bestandteil "ELSTER" enthalten."
TRADEMARK = "elster"
# TransferHeader of the ELSTER Basisschema: DatenLieferant is free text of at most 256 characters.
DATENLIEFERANT_LENGTH = 256

INSTALLATION_JOB = "steuerbote.steuerbote.doctype.eric_settings.eric_settings.run_installation"
INSTALLATION_JOB_ID = "steuerbote:eric:installation"
INSTALLATION_EVENT = "steuerbote_eric_installation"
# Unpacking and checking an archive of about 500 MB takes minutes.
INSTALLATION_TIMEOUT = 1800

TAXONOMY_ROOT = "steuerbote_taxonomy_root"
TAXONOMY_JOB = "steuerbote.steuerbote.doctype.eric_settings.eric_settings.run_taxonomy_installation"
TAXONOMY_JOB_ID = "steuerbote:taxonomy:installation"
TAXONOMY_EVENT = "steuerbote_taxonomy_installation"
# Unpacking the 279 files of a package and parsing its three views takes about a minute on a small server.
TAXONOMY_TIMEOUT = 900
SHA256 = transmission_adapter.SHA256

VERSIONS_SAVEPOINT = "steuerbote_eric_versions"
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
# The copy of the Versionsinformationen of a package in common_site_config.json, for a server without access to
# download.elster.de.
VERSIONS_COPY = "steuerbote_eric_versions"
NOTICE_SENT = "E-Mail and Notification"
NOTICE_NOTIFICATION_ONLY = "Notification Only"
NOTICE_NO_RECIPIENTS = "No Recipients"
NOTICE_NOT_DELIVERED = "Not Delivered"
# The details of the checks are German, written for the operator (steuerbote.eric), so the notice around them is.
NOTICE_LANGUAGE = "de"


class ERiCSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		archive_path: DF.Data | None
		archive_sha256: DF.Data | None
		copyright: DF.Data | None
		datenlieferant: DF.SmallText | None
		hersteller_id: DF.Data | None
		installed_taxonomies: DF.SmallText | None
		installed_version: DF.Data | None
		last_check: DF.Datetime | None
		lib_dir: DF.Data | None
		log_dir: DF.Data | None
		minimum_eric_version: DF.Data | None
		minimum_list_modified: DF.Datetime | None
		minimum_list_version: DF.Data | None
		minimum_versions: DF.LongText | None
		privacy_notice_confirmed: DF.Check
		privacy_notice_confirmed_by: DF.Link | None
		privacy_notice_confirmed_on: DF.Datetime | None
		produkt_name: DF.Data
		produkt_version: DF.Data | None
		proxy_password: DF.Password | None
		proxy_url: DF.Data | None
		proxy_user: DF.Data | None
		simulation: DF.Check
		taxonomy_archives: DF.SmallText | None
		version_notice_status: DF.Literal[
			"", "E-Mail and Notification", "Notification Only", "No Recipients", "Not Delivered"
		]
		version_notices: DF.SmallText | None
		version_notified_on: DF.Datetime | None
		versions_check_failed: DF.Check
		versions_checked_on: DF.Datetime | None
	# end: auto-generated types

	def onload(self) -> None:
		self.show_configured_archive()
		self.show_taxonomies()
		self.show_app_version()

	def show_app_version(self) -> None:
		"""The version of the app the site runs, also where the settings were saved under an older one; the stored
		field follows once the form has its answer."""
		if self.produkt_version == steuerbote.__version__:
			return
		self.produkt_version = steuerbote.__version__
		if not frappe.flags.read_only:
			commit_after_response(refresh_produkt_version)

	def validate(self) -> None:
		self.produkt_version = steuerbote.__version__
		self.hersteller_id = (self.hersteller_id or "").strip()
		self.produkt_name = (self.produkt_name or "").strip()
		self.datenlieferant = "; ".join(
			line.strip() for line in (self.datenlieferant or "").splitlines() if line.strip()
		)
		self.show_configured_archive()
		self.show_taxonomies()
		if self.hersteller_id:
			# The rule of Kz 09 in the Nutzdaten, which carries the same Hersteller-ID as header and runtime.
			with xml_errors(_("ERiC Settings")):
				ustva_xml.require_hersteller_id(self.hersteller_id)
		self.check_produkt_name()
		if len(self.datenlieferant) > DATENLIEFERANT_LENGTH:
			frappe.throw(_("The Datenlieferant has at most {0} characters.").format(DATENLIEFERANT_LENGTH))
		self.check_copyright()
		self.check_proxy()
		self.record_privacy_notice()
		self.keep_version_check()
		self.simulation = int(not self.runs_eric())

	def keep_version_check(self) -> None:
		"""What the weekly check of the versions wrote, whatever the form sent: only check_versions writes it."""
		before = self.get_doc_before_save()
		for fieldname in VERSION_CHECK_FIELDS:
			self.set(fieldname, before.get(fieldname) if before else None)

	def check_copyright(self) -> None:
		"""The copyright notice as the Vorsatz writes it: in the character set of ELSTER, at most 50 characters."""
		if not (self.copyright or "").strip():
			self.copyright = None
			return
		with xml_errors(_("ERiC Settings")):
			self.copyright = vorsatz.copyright_text(self.copyright)

	def check_proxy(self) -> None:
		"""A proxy ERiC can use (steuerbote.eric.proxy); without its URL, user and password go as well."""
		self.proxy_url = (self.proxy_url or "").strip()
		self.proxy_user = (self.proxy_user or "").strip() or None
		if not self.proxy_url:
			self.proxy_user = None
			self.proxy_password = None
			return
		try:
			proxy.parse(self.proxy_url, self.proxy_user, self.proxy_password)
		except proxy.ProxyError as error:
			frappe.throw(_(error.template).format(*error.values), title=_("ERiC Settings"))

	def record_privacy_notice(self) -> None:
		"""Who confirmed the Datenschutzhinweise and when: the user who first ticks the box, kept until the box
		is cleared."""
		if not cint(self.privacy_notice_confirmed):
			self.privacy_notice_confirmed_by = None
			self.privacy_notice_confirmed_on = None
			return
		before = self.get_doc_before_save()
		if before and cint(before.privacy_notice_confirmed) and before.privacy_notice_confirmed_by:
			self.privacy_notice_confirmed_by = before.privacy_notice_confirmed_by
			self.privacy_notice_confirmed_on = before.privacy_notice_confirmed_on
			return
		self.privacy_notice_confirmed_by = frappe.session.user
		self.privacy_notice_confirmed_on = now_datetime()

	def runs_eric(self) -> bool:
		"""Whether the transmissions go to ERiC: a runtime is installed and a Hersteller-ID entered."""
		return bool(self.installed_version and self.lib_dir and self.hersteller_id)

	def check_produkt_name(self) -> None:
		if len(self.produkt_name) > PRODUKT_NAME_LENGTH:
			frappe.throw(_("The product name has at most {0} characters.").format(PRODUKT_NAME_LENGTH))
		if TRADEMARK in self.produkt_name.casefold():
			frappe.throw(_("The product name must not contain the word ELSTER."))

	def show_configured_archive(self) -> None:
		"""The archive and its SHA-256 as common_site_config.json names them, whatever the form sent."""
		archive_path, sha256 = transmission_adapter.shown_archive()
		self.archive_path = archive_path or None
		self.archive_sha256 = sha256 or None

	def show_taxonomies(self) -> None:
		"""The package of each version as common_site_config.json names it and the versions installed on the server,
		whatever the form sent."""
		lines = []
		for version, (archive, sha256) in named_taxonomies().items():
			if archive or sha256:
				lines.append(f"{version}: {archive} (SHA-256 {sha256})")
			else:
				lines.append(_("{0}: not named in common_site_config.json").format(version))
		self.taxonomy_archives = "\n".join(lines) or None
		self.installed_taxonomies = (
			"\n".join(
				_("{0} from {1}, installed on {2} by {3}").format(
					installation.version,
					installation.archive,
					format_datetime(
						convert_utc_to_system_timezone(
							datetime.fromisoformat(installation.installed_at)
						).replace(tzinfo=None)
					),
					installation.installed_by,
				)
				for installation in taxonomy.installations(taxonomy_root())
			)
			or None
		)

	@frappe.whitelist(methods=["POST"])
	def install_runtime(self) -> None:
		"""Laufzeitumgebung installieren: unpack the ERiC archive that common_site_config.json names in a background
		job, which reads the archive there itself."""
		frappe.only_for("System Manager", message=True)
		transmission_adapter.configured_archive()
		if is_job_enqueued(INSTALLATION_JOB_ID):
			frappe.throw(_("An installation of ERiC is running already."))
		frappe.enqueue(
			INSTALLATION_JOB,
			queue="long",
			timeout=INSTALLATION_TIMEOUT,
			job_id=INSTALLATION_JOB_ID,
			deduplicate=True,
			enqueue_after_commit=True,
		)

	@frappe.whitelist(methods=["POST"])
	def install_taxonomy(self) -> None:
		"""Taxonomie einrichten: install each version of the HGB-Taxonomie whose package common_site_config.json names,
		in a background job, which reads the packages there itself."""
		frappe.only_for("System Manager", message=True)
		configured_taxonomies()
		if is_job_enqueued(TAXONOMY_JOB_ID):
			frappe.throw(_("An installation of the taxonomy is running already."))
		frappe.enqueue(
			TAXONOMY_JOB,
			queue="long",
			timeout=TAXONOMY_TIMEOUT,
			job_id=TAXONOMY_JOB_ID,
			deduplicate=True,
			enqueue_after_commit=True,
		)

	@frappe.whitelist(methods=["POST"])
	def check_runtime(self) -> list[dict]:
		"""Laufzeitumgebung prüfen: the checks of the status page for the runtimes installed, among them whether one
		holds the plugin of the current year and the plugin checkZMDO of the Zusammenfassende Meldung, then whether
		they reach the Mindestversionsliste the weekly check loaded and hold the plugin of the coming year."""
		frappe.only_for("System Manager", message=True)
		self.reload()
		installed = runtime.installations(transmission_adapter.runtime_root())
		checks = (
			*transmission_adapter.runtime_status(self.hersteller_id or ""),
			*releases.checks(installed, stored_minimum_list(self.minimum_versions), getdate()),
			*taxonomy_status(),
		)
		return [{"name": check.name, "ok": check.ok, "detail": check.detail} for check in checks]


def run_installation() -> None:
	"""Background job of ERiCSettings.install_runtime: unpack the archive common_site_config.json names and record
	the runtime.

	The user who started the installation gets a realtime notice either way, a refusal of the platform in their
	language.
	"""
	runtime = None
	error = None
	try:
		runtime = transmission_adapter.install_configured_archive()
	except UnsupportedPlatform as refused:
		error = _(refused.template).format(*refused.values)
	except RuntimeInstallError as refused:
		error = str(refused)
	except frappe.ValidationError as refused:
		error = strip_html(str(refused))
	except Exception as failure:
		frappe.log_error(title=_("Installation of ERiC failed"))
		error = str(failure)
	if runtime is not None:
		complete_versions(runtime.version)
	settings = frappe.get_single(SETTINGS)
	if runtime is not None:
		settings.update(
			{
				"installed_version": runtime.version,
				"lib_dir": str(runtime.lib_dir),
				"log_dir": str(eric_log_root()),
			}
		)
	settings.last_check = now_datetime()
	settings.save(ignore_permissions=True)
	frappe.publish_realtime(
		INSTALLATION_EVENT,
		{"ok": runtime is not None, "version": runtime.version if runtime else None, "error": error},
		user=frappe.session.user,
		after_commit=True,
	)


def refresh_produkt_version() -> None:
	"""after_migrate (hooks.py): the version of the app in the settings, which a save writes, so that it is the one of
	the update without a save. The header of a delivery takes the version of the app itself."""
	if frappe.db.get_single_value(SETTINGS, "produkt_version", cache=False) != steuerbote.__version__:
		frappe.db.set_single_value(SETTINGS, "produkt_version", steuerbote.__version__, update_modified=False)


def run_taxonomy_installation() -> None:
	"""Background job of ERiCSettings.install_taxonomy: install each version whose package common_site_config.json
	names. The user who started the installation gets a realtime notice either way."""
	versions: list[str] = []
	error = None
	try:
		for version, (archive, sha256) in configured_taxonomies().items():
			installation = taxonomy.install_from_archive(
				archive, sha256, taxonomy_root(), TAXONOMIES[version], installed_by=frappe.session.user
			)
			versions.append(installation.version)
	except TaxonomyError as refused:
		error = str(refused)
	except frappe.ValidationError as refused:
		error = strip_html(str(refused))
	except Exception as failure:
		frappe.log_error(title=_("Installation of the taxonomy failed"))
		error = str(failure)
	frappe.publish_realtime(
		TAXONOMY_EVENT,
		{"ok": error is None, "versions": versions, "error": error},
		user=frappe.session.user,
		after_commit=True,
	)


def named_taxonomies() -> dict[str, tuple[str, str]]:
	"""The package and the SHA-256 common_site_config.json names for each version, empty where it names none."""
	config = transmission_adapter.common_site_config()
	return {
		version.version: (
			str(config.get(version.config_key) or "").strip(),
			str(config.get(version.config_sha256_key) or "").strip().lower(),
		)
		for version in TAXONOMIES.values()
	}


def configured_taxonomies() -> dict[str, tuple[Path, str]]:
	"""The package and the SHA-256 of each version common_site_config.json names, checked: an absolute path on the
	server and the checksum of the package esteuer.de publishes. Naming none is an error."""
	configured = {}
	for version, (archive, sha256) in named_taxonomies().items():
		if not (archive or sha256):
			continue
		entry = TAXONOMIES[version]
		if not (archive and sha256):
			frappe.throw(no_taxonomy_message(version))
		if not os.path.isabs(archive):
			frappe.throw(
				_("{0} in common_site_config.json is no absolute path on the server.").format(
					entry.config_key
				)
			)
		if not SHA256.fullmatch(sha256):
			frappe.throw(
				_("{0} in common_site_config.json has 64 hexadecimal digits.").format(entry.config_sha256_key)
			)
		if sha256 != entry.archive_sha256:
			frappe.throw(
				_(
					"{0} in common_site_config.json is not the SHA-256 of the package of the HGB-Taxonomie {1} that esteuer.de publishes: {2}."
				).format(entry.config_sha256_key, version, entry.archive_sha256)
			)
		configured[version] = (Path(archive), sha256)
	if not configured:
		frappe.throw(no_taxonomy_message(max(TAXONOMIES, key=_version_key)))
	return configured


def no_taxonomy_message(version: str) -> str:
	entry = TAXONOMIES[version]
	return _(
		"Name the package of the HGB-Taxonomie {0} from esteuer.de and its SHA-256 as {1} and {2} in common_site_config.json of the bench, with bench set-config -g on the server."
	).format(version, entry.config_key, entry.config_sha256_key)


def taxonomy_root() -> Path:
	"""Where the taxonomies live: outside every site, so they are neither served nor backed up.

	``steuerbote_taxonomy_root`` in common_site_config.json overrides the directory ``sites/taxonomy`` of the bench.
	"""
	configured = transmission_adapter.common_site_config().get(TAXONOMY_ROOT)
	return Path(configured) if configured else Path(get_bench_path(), "sites", "taxonomy")


def taxonomy_status() -> tuple[Check, ...]:
	"""What „Laufzeitumgebung prüfen“ reports of each version: named, installed and unchanged."""
	return taxonomy.status(
		taxonomy_root(),
		{
			version: (Path(archive), sha256) if archive and sha256 else None
			for version, (archive, sha256) in named_taxonomies().items()
		},
	)


def taxonomy_view(version: str, view: View) -> Taxonomy:
	"""The parsed view of an installed version for the E-Bilanz and the Offenlegung, refused while the version is not
	installed or the file of the view differs from the manifest."""
	if version not in TAXONOMIES:
		frappe.throw(_("Steuerbote knows no HGB-Taxonomie {0}.").format(version))
	root = taxonomy_root()
	installation = taxonomy.installed(root, TAXONOMIES[version])
	if installation is None:
		frappe.throw(
			_("The HGB-Taxonomie {0} is not installed: Install Taxonomy in the ERiC Settings.").format(
				version
			)
		)
	try:
		return _parsed_view(str(root), version, installation.views.get(view.value, ""), view)
	except TaxonomyError as error:
		frappe.throw(str(error), title=_("HGB Taxonomy"))


@lru_cache(maxsize=6)
def _parsed_view(root: str, version: str, checksum: str, view: View) -> Taxonomy:
	"""A view read once per process and checksum of its file, which the key of the cache holds: each view of 6.9 is
	some 5 MB of JSON."""
	installation = taxonomy.installed(Path(root), TAXONOMIES[version])
	if installation is None:
		raise TaxonomyError(f"Die HGB-Taxonomie {version} ist nicht eingerichtet.")
	return installation.view(view)


def _version_key(version: str) -> tuple[int, ...]:
	return tuple(int(part) for part in version.split("."))


def vorsatz_copyright() -> str:
	"""The copyright notice of the Vorsatz of an Erklärung, which the rules 10435 and 6 require (Jahresdokumentation
	E50 2026, sheet „Vorsatz - Regeln“; Formale_Plausipruefungen.ods). A run of ERiC needs the one of the settings; the
	simulation takes the product name in its place, as it takes 00000 for a missing Hersteller-ID."""
	settings = frappe.get_single(SETTINGS)
	if settings.copyright:
		return settings.copyright
	if cint(settings.simulation):
		return settings.produkt_name or DEFAULT_PRODUKT_NAME
	frappe.throw(_("Enter the Copyright Notice in the ERiC Settings."), title=_("ERiC Settings"))


def has_annual_filings() -> bool:
	"""Whether the site keeps annual filings: it has Annual Filing Settings, which come with them."""
	return bool(frappe.db.table_exists(ANNUAL_FILING_SETTINGS) and frappe.db.count(ANNUAL_FILING_SETTINGS))


def eric_log_root() -> Path:
	"""Where the transmissions of this site let ERiC write eric.log, a directory per transmission."""
	return Path(frappe.get_site_path("logs", "eric")).resolve()


def check_versions() -> None:
	"""The weekly job (scheduler_events in hooks.py): read the Versionsinformationen of the runtimes without them,
	load the Mindestversionsliste of ELSTER, keep it in the ERiC Settings and tell the System Managers once of each
	failing check of steuerbote.eric.releases.notices.

	It never raises. A list that cannot be loaded or read lands in the Error Log, the settings note the check as
	failed and keep the list loaded before, which the comparison then takes. Versionsinformationen that cannot be read
	land in the Error Log, and their libraries stay without a version, a hint of the comparison. How the notice went
	out the settings note apart from the check: one that cannot be sent lands in the Error Log as well and goes out
	with the next check.
	"""
	settings = frappe.get_single(SETTINGS)
	values: dict[str, object] = {"versions_checked_on": now_datetime(), "versions_check_failed": 0}
	complete_versions()
	minimum_list = stored_minimum_list(settings.minimum_versions)
	try:
		fetched = releases.fetch_list()
		minimum_list = releases.parse_list(fetched.text)
	except Exception:
		values["versions_check_failed"] = 1
		frappe.log_error(
			title=_("The Mindestversionsliste of ERiC could not be loaded"),
			reference_doctype=SETTINGS,
			reference_name=SETTINGS,
		)
	else:
		values.update(list_values(minimum_list, fetched.last_modified))
	frappe.db.savepoint(VERSIONS_SAVEPOINT)
	try:
		values.update(notify(minimum_list, settings))
	except Exception:
		frappe.db.rollback(save_point=VERSIONS_SAVEPOINT)
		values.update(version_notice_status=NOTICE_NOT_DELIVERED, version_notified_on=now_datetime())
		frappe.log_error(
			title=_("The notice of the ERiC versions failed"),
			reference_doctype=SETTINGS,
			reference_name=SETTINGS,
		)
	else:
		frappe.db.release_savepoint(VERSIONS_SAVEPOINT)
	frappe.db.set_single_value(SETTINGS, values, update_modified=False)


def complete_versions(version: str | None = None) -> None:
	"""Read the Versionsinformationen of each installed runtime whose manifest lacks them, only of the version if one
	is given (steuerbote.eric.releases.complete_versions). What keeps them from being read lands in the Error Log as one
	entry; nothing raises."""
	try:
		copy, problems = versions_copy()
		installed = tuple(
			installation
			for installation in runtime.installations(transmission_adapter.runtime_root())
			if version is None or installation.version == version
		)
		problems += releases.complete_versions(installed, copy)
	except Exception:
		frappe.log_error(
			title=_("The Versionsinformationen of ERiC could not be read"),
			reference_doctype=SETTINGS,
			reference_name=SETTINGS,
		)
		return
	if problems:
		frappe.log_error(
			title=_("The Versionsinformationen of ERiC could not be read"),
			message="\n".join(problems),
			reference_doctype=SETTINGS,
			reference_name=SETTINGS,
		)


def versions_copy() -> tuple[Path | None, tuple[str, ...]]:
	"""The copy of the Versionsinformationen of a package that steuerbote_eric_versions in common_site_config.json
	names, as only the operator of the server names the archive, and why it is not taken."""
	configured = str(transmission_adapter.common_site_config().get(VERSIONS_COPY) or "").strip()
	if not configured:
		return None, ()
	if not os.path.isabs(configured):
		return None, (
			_("{0} in common_site_config.json is no absolute path on the server.").format(VERSIONS_COPY),
		)
	return Path(configured), ()


def stored_minimum_list(text: str | None) -> MinimumList | None:
	"""The Mindestversionsliste the weekly check kept, None before it loaded one."""
	if not text:
		return None
	try:
		return MinimumList.from_json(text)
	except MinimumListError:
		return None


def list_values(minimum_list: MinimumList, last_modified: datetime | None) -> dict[str, object]:
	"""The fields of the settings that show the list: its version, when it changed and the Mindestversion of ERiC."""
	eric = minimum_list.eric
	return {
		"minimum_list_version": minimum_list.version,
		"minimum_list_modified": (
			convert_utc_to_system_timezone(last_modified).replace(tzinfo=None) if last_modified else None
		),
		"minimum_eric_version": releases.format_version(eric.version) if eric else None,
		"minimum_versions": minimum_list.to_json(),
	}


def notify(minimum_list: MinimumList | None, settings: Document) -> dict[str, object]:
	"""Tell the System Managers of the failing checks of the installed runtimes not told before. Returns the fields
	that record it: the notices of all failing checks, one per line, as told, and how the notice of new ones went out,
	which stays while they fail and goes once nothing is left to tell."""
	installed = runtime.installations(transmission_adapter.runtime_root())
	failing = releases.notices(installed, minimum_list, getdate(), annual=has_annual_filings())
	values: dict[str, object] = {"version_notices": "\n".join(check.notice for check in failing)}
	new = releases.due(failing, (settings.version_notices or "").splitlines())
	if new:
		values.update(version_notice_status=send_notice(new), version_notified_on=now_datetime())
	elif not failing or settings.version_notice_status == NOTICE_NOT_DELIVERED:
		values.update(version_notice_status="", version_notified_on=None)
	return values


def send_notice(checks: tuple[Check, ...]) -> str:
	"""One e-mail and one notification in the desk for each System Manager, Administrator and Guest left out as
	Frappe does for its own notices, and how the notice went out. The e-mail goes first: its queue is part of the
	transaction, while the notification in the desk is queued for after the commit. Without an outgoing e-mail account
	the notification goes alone, and the Error Log says so once, without a traceback."""
	recipients = system_manager_addresses()
	if not recipients:
		return NOTICE_NO_RECIPIENTS
	subject = _("Steuerbote: check the ERiC runtime", lang=NOTICE_LANGUAGE)
	message = notice_message(checks)
	by_email = has_outgoing_email_account()
	if by_email:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			reference_doctype=SETTINGS,
			reference_name=SETTINGS,
		)
	enqueue_create_notification(
		recipients,
		{
			"type": "Alert",
			"document_type": SETTINGS,
			"document_name": SETTINGS,
			"subject": subject,
			"email_content": message,
		},
	)
	if by_email:
		return NOTICE_SENT
	frappe.log_error(
		title=_("The notice of the ERiC versions went out as a notification only"),
		message=_(
			"No outgoing e-mail account is set up, so the System Managers got the notice of the ERiC versions as a notification only, without an e-mail."
		),
		reference_doctype=SETTINGS,
		reference_name=SETTINGS,
	)
	return NOTICE_NOTIFICATION_ONLY


def has_outgoing_email_account() -> bool:
	"""Whether Frappe has an outgoing e-mail account for the notice, looked up as frappe.sendmail looks it up."""
	return bool(EmailAccount.find_outgoing(match_by_doctype=SETTINGS))


def system_manager_addresses() -> list[str]:
	"""The e-mail addresses of the enabled System Managers."""
	names = get_system_managers(only_name=True)
	if not names:
		return []
	return frappe.get_all("User", filters={"name": ["in", names]}, pluck="email", order_by="name")


def notice_message(checks: tuple[Check, ...]) -> str:
	"""The body of the notice: the failing checks, then where all checks and the new versions of ERiC are."""
	language = NOTICE_LANGUAGE
	link = f'<a href="{escape_html(get_url_to_form(SETTINGS))}">{escape_html(_("ERiC Settings", lang=language))}</a>'
	intro = _("The weekly check of the ERiC versions found:", lang=language)
	outro = _(
		"Check Runtime in the {0} shows every check. New versions of ERiC are on the ERiC download page of the ELSTER developer area, after login.",
		lang=language,
	).format(link)
	items = "".join(f"<li>{escape_html(check.detail)}</li>" for check in checks)
	return f"<p>{escape_html(intro)}</p><ul>{items}</ul><p>{outro}</p>"
