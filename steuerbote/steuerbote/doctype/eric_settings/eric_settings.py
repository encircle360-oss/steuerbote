"""ERiC-Einstellungen: what this installation needs to transmit through ERiC.

The Hersteller-ID belongs to the installation, not to a company, and so does the ERiC runtime. While either
is missing the settings simulate: Prüfen and Testsenden run against the simulation of steuerbote.eric and
nothing reaches the Finanzamt. Steuerbote ships no part of ERiC and downloads nothing: the operator puts the
archive for Linux x86_64 from the ELSTER developer area on the server, and the installation job unpacks it
through steuerbote.eric.runtime after checking its SHA-256. Before ERiC runs, the operator confirms the
Datenschutzhinweise of the tax administration (ERiC licence, § 5 Abs. 1 and 2); the settings keep who
confirmed them and when. The simulation needs no confirmation. Where the server reaches ELSTER through a proxy,
the settings name it, with its password in a Password field, and every run of ERiC goes through it; the
simulation reaches no server.
"""

import os
import re
from pathlib import Path

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime
from frappe.utils.background_jobs import is_job_enqueued

import steuerbote
from steuerbote.elster import ustva_xml
from steuerbote.eric import proxy
from steuerbote.eric.runtime import RuntimeInstallError
from steuerbote.steuerbote.doctype.vat_return import transmission_adapter
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import xml_errors

SETTINGS = "ERiC Settings"
# NutzdatenHeader of the ELSTER Basisschema: ProduktName has 1 to 50 characters.
PRODUKT_NAME_LENGTH = 50
# ERiC licence, § 12: "Der Produkt- oder Herstellername darf jedoch nicht den Bestandteil "ELSTER" enthalten."
TRADEMARK = "elster"
# TransferHeader of the ELSTER Basisschema: DatenLieferant is free text of at most 256 characters.
DATENLIEFERANT_LENGTH = 256
SHA256 = re.compile(r"[0-9a-f]{64}")

INSTALLATION_JOB = "steuerbote.steuerbote.doctype.eric_settings.eric_settings.run_installation"
INSTALLATION_JOB_ID = "steuerbote:eric:installation"
INSTALLATION_EVENT = "steuerbote_eric_installation"
# Unpacking and checking an archive of about 500 MB takes minutes.
INSTALLATION_TIMEOUT = 1800


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
		privacy_notice_confirmed: DF.Check
		privacy_notice_confirmed_by: DF.Link | None
		privacy_notice_confirmed_on: DF.Datetime | None
		produkt_name: DF.Data
		produkt_version: DF.Data | None
		proxy_password: DF.Password | None
		proxy_url: DF.Data | None
		proxy_user: DF.Data | None
		simulation: DF.Check
	# end: auto-generated types

	def validate(self) -> None:
		self.produkt_version = steuerbote.__version__
		self.hersteller_id = (self.hersteller_id or "").strip()
		self.produkt_name = (self.produkt_name or "").strip()
		self.datenlieferant = "; ".join(
			line.strip() for line in (self.datenlieferant or "").splitlines() if line.strip()
		)
		self.archive_path = (self.archive_path or "").strip()
		self.archive_sha256 = (self.archive_sha256 or "").strip().lower()
		if self.hersteller_id:
			# The rule of Kz 09 in the Nutzdaten, which carries the same Hersteller-ID as header and runtime.
			with xml_errors(_("ERiC Settings")):
				ustva_xml.require_hersteller_id(self.hersteller_id)
		self.check_produkt_name()
		self.check_archive()
		if len(self.datenlieferant) > DATENLIEFERANT_LENGTH:
			frappe.throw(_("The Datenlieferant has at most {0} characters.").format(DATENLIEFERANT_LENGTH))
		self.check_proxy()
		self.record_privacy_notice()
		self.simulation = int(not self.runs_eric())

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

	def check_archive(self) -> None:
		if self.archive_path and not os.path.isabs(self.archive_path):
			frappe.throw(_("Enter the ERiC archive as an absolute path on the server."))
		if self.archive_sha256 and not SHA256.fullmatch(self.archive_sha256):
			frappe.throw(_("The SHA-256 of the archive has 64 hexadecimal digits."))

	@frappe.whitelist(methods=["POST"])
	def install_runtime(self) -> None:
		"""Laufzeitumgebung installieren: unpack the ERiC archive of the saved settings in a background job."""
		frappe.only_for("System Manager", message=True)
		self.reload()
		if not (self.archive_path and self.archive_sha256):
			frappe.throw(_("Enter the ERiC archive and its SHA-256 and save the settings before installing."))
		if is_job_enqueued(INSTALLATION_JOB_ID):
			frappe.throw(_("An installation of ERiC is running already."))
		frappe.enqueue(
			INSTALLATION_JOB,
			queue="long",
			timeout=INSTALLATION_TIMEOUT,
			job_id=INSTALLATION_JOB_ID,
			deduplicate=True,
			enqueue_after_commit=True,
			archive_path=self.archive_path,
			sha256=self.archive_sha256,
		)


def run_installation(archive_path: str, sha256: str) -> None:
	"""Background job of ERiCSettings.install_runtime: unpack the archive and record the runtime.

	The user who started the installation gets a realtime notice either way.
	"""
	runtime = None
	error = None
	try:
		runtime = transmission_adapter.install_from_archive(archive_path, sha256)
	except RuntimeInstallError as refused:
		error = str(refused)
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
