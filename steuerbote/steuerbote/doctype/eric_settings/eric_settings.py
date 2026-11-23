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
check regularly for new versions (§ 5 Abs. 4) and to use at least the Mindestversion (§ 5 Abs. 6). Only that job
writes its fields; a save of the form keeps them.
"""

from datetime import datetime
from pathlib import Path

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.utils import (
	cint,
	convert_utc_to_system_timezone,
	escape_html,
	get_url_to_form,
	getdate,
	now_datetime,
	strip_html,
)
from frappe.utils.background_jobs import is_job_enqueued
from frappe.utils.user import get_system_managers

import steuerbote
from steuerbote.elster import ustva_xml
from steuerbote.eric import proxy, releases, runtime
from steuerbote.eric.releases import MinimumList, MinimumListError
from steuerbote.eric.runtime import Check, RuntimeInstallError
from steuerbote.steuerbote.doctype.vat_return import transmission_adapter
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import xml_errors

SETTINGS = "ERiC Settings"
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

VERSIONS_SAVEPOINT = "steuerbote_eric_versions"
VERSION_CHECK_FIELDS = (
	"minimum_list_version",
	"minimum_list_modified",
	"minimum_eric_version",
	"minimum_versions",
	"versions_checked_on",
	"versions_check_failed",
	"version_notices",
)
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
		datenlieferant: DF.SmallText | None
		hersteller_id: DF.Data | None
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
		version_notices: DF.SmallText | None
		versions_check_failed: DF.Check
		versions_checked_on: DF.Datetime | None
	# end: auto-generated types

	def onload(self) -> None:
		self.show_configured_archive()

	def validate(self) -> None:
		self.produkt_version = steuerbote.__version__
		self.hersteller_id = (self.hersteller_id or "").strip()
		self.produkt_name = (self.produkt_name or "").strip()
		self.datenlieferant = "; ".join(
			line.strip() for line in (self.datenlieferant or "").splitlines() if line.strip()
		)
		self.show_configured_archive()
		if self.hersteller_id:
			# The rule of Kz 09 in the Nutzdaten, which carries the same Hersteller-ID as header and runtime.
			with xml_errors(_("ERiC Settings")):
				ustva_xml.require_hersteller_id(self.hersteller_id)
		self.check_produkt_name()
		if len(self.datenlieferant) > DATENLIEFERANT_LENGTH:
			frappe.throw(_("The Datenlieferant has at most {0} characters.").format(DATENLIEFERANT_LENGTH))
		self.check_proxy()
		self.record_privacy_notice()
		self.keep_version_check()
		self.simulation = int(not self.runs_eric())

	def keep_version_check(self) -> None:
		"""What the weekly check of the versions wrote, whatever the form sent: only check_versions writes it."""
		before = self.get_doc_before_save()
		for fieldname in VERSION_CHECK_FIELDS:
			self.set(fieldname, before.get(fieldname) if before else None)

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
		)
		return [{"name": check.name, "ok": check.ok, "detail": check.detail} for check in checks]


def run_installation() -> None:
	"""Background job of ERiCSettings.install_runtime: unpack the archive common_site_config.json names and record
	the runtime.

	The user who started the installation gets a realtime notice either way.
	"""
	runtime = None
	error = None
	try:
		runtime = transmission_adapter.install_configured_archive()
	except RuntimeInstallError as refused:
		error = str(refused)
	except frappe.ValidationError as refused:
		error = strip_html(str(refused))
	except Exception as failure:
		frappe.log_error(title=_("Installation of ERiC failed"))
		error = str(failure)
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


def eric_log_root() -> Path:
	"""Where the transmissions of this site let ERiC write eric.log, a directory per transmission."""
	return Path(frappe.get_site_path("logs", "eric")).resolve()


def check_versions() -> None:
	"""The weekly job (scheduler_events in hooks.py): load the Mindestversionsliste of ELSTER, keep it in the ERiC
	Settings and tell the System Managers once of each failing check of steuerbote.eric.releases.notices.

	It never raises. A list that cannot be loaded or read lands in the Error Log, the settings note the check as
	failed and keep the list loaded before, which the comparison then takes. A notice that cannot be sent lands in the
	Error Log as well and goes out with the next check.
	"""
	settings = frappe.get_single(SETTINGS)
	values: dict[str, object] = {"versions_checked_on": now_datetime(), "versions_check_failed": 0}
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
		values["version_notices"] = notify(minimum_list, settings.version_notices)
	except Exception:
		frappe.db.rollback(save_point=VERSIONS_SAVEPOINT)
		values["versions_check_failed"] = 1
		frappe.log_error(
			title=_("The notice of the ERiC versions failed"),
			reference_doctype=SETTINGS,
			reference_name=SETTINGS,
		)
	else:
		frappe.db.release_savepoint(VERSIONS_SAVEPOINT)
	frappe.db.set_single_value(SETTINGS, values, update_modified=False)


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


def notify(minimum_list: MinimumList | None, notified: str | None) -> str:
	"""Tell the System Managers of the failing checks of the installed runtimes not told before, and return the
	notices of all failing checks, one per line, as told."""
	installed = runtime.installations(transmission_adapter.runtime_root())
	failing = releases.notices(installed, minimum_list, getdate())
	new = releases.due(failing, (notified or "").splitlines())
	if new:
		send_notice(new)
	return "\n".join(check.notice for check in failing)


def send_notice(checks: tuple[Check, ...]) -> None:
	"""One e-mail and one notification in the desk for each System Manager, Administrator and Guest left out as
	Frappe does for its own notices. The e-mail goes first: its queue is part of the transaction, while the
	notification in the desk is queued for after the commit."""
	recipients = system_manager_addresses()
	if not recipients:
		return
	subject = _("Steuerbote: check the ERiC runtime", lang=NOTICE_LANGUAGE)
	message = notice_message(checks)
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
