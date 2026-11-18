"""ERiC-Einstellungen: what this installation needs to transmit through ERiC.

The Hersteller-ID belongs to the installation, not to a company, and so does the ERiC runtime. While either
is missing the settings simulate: Prüfen and Testsenden run against the simulation of steuerbote.eric and
nothing reaches the Finanzamt. Steuerbote ships no part of ERiC. The operator downloads the archive for Linux
x86_64 from the ELSTER developer area, and the installation job unpacks it through steuerbote.eric.runtime.
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.utils.background_jobs import is_job_enqueued

import steuerbote
from steuerbote.steuerbote.doctype.vat_return import transmission_adapter

SETTINGS = "ERiC Settings"
# headerbasis_datentypen.xsd of the ERiC documentation: a Hersteller-ID has five digits.
HERSTELLER_ID = re.compile(r"[0-9]{5}")
# ERiC-Entwicklerhandbuch 44.3.6.0, p. 170: "Die aus vorherigen ERiC Releases bekannte Test-Hersteller-ID 74931
# dient in der Dokumentation nur noch zu Illustrationszwecken"; ERiC refuses it.
ILLUSTRATION_HERSTELLER_ID = "74931"
# NutzdatenHeader of the ELSTER Basisschema: ProduktName has 1 to 50 characters.
PRODUKT_NAME_LENGTH = 50
# ERiC licence, § 12: "Der Produkt- oder Herstellername darf jedoch nicht den Bestandteil "ELSTER" enthalten."
TRADEMARK = "elster"
# TransferHeader of the ELSTER Basisschema: DatenLieferant is free text of at most 256 characters.
DATENLIEFERANT_LENGTH = 256
SHA256 = re.compile(r"[0-9a-f]{64}")
# The operator copies the address from the ELSTER developer area; only the ELSTER download server is accepted.
DOWNLOAD_SERVER = "https://download.elster.de/"

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
		produkt_name: DF.Data
		produkt_version: DF.Data | None
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
		self.check_hersteller_id()
		self.check_produkt_name()
		self.check_archive()
		if len(self.datenlieferant) > DATENLIEFERANT_LENGTH:
			frappe.throw(_("The Datenlieferant has at most {0} characters.").format(DATENLIEFERANT_LENGTH))
		self.simulation = int(not self.runs_eric())

	def runs_eric(self) -> bool:
		"""Whether the transmissions go to ERiC: a runtime is installed and a Hersteller-ID entered."""
		return bool(self.installed_version and self.lib_dir and self.hersteller_id)

	def check_hersteller_id(self) -> None:
		if not self.hersteller_id:
			return
		if not HERSTELLER_ID.fullmatch(self.hersteller_id):
			frappe.throw(_("A Hersteller-ID has five digits."))
		if self.hersteller_id == ILLUSTRATION_HERSTELLER_ID:
			frappe.throw(
				_(
					"The Hersteller-ID {0} only illustrates the ERiC documentation. Enter the Hersteller-ID issued to you."
				).format(ILLUSTRATION_HERSTELLER_ID)
			)

	def check_produkt_name(self) -> None:
		if len(self.produkt_name) > PRODUKT_NAME_LENGTH:
			frappe.throw(_("The product name has at most {0} characters.").format(PRODUKT_NAME_LENGTH))
		if TRADEMARK in self.produkt_name.lower():
			frappe.throw(_("The product name must not contain the word ELSTER."))

	def check_archive(self) -> None:
		path = self.archive_path
		if path and not (path.startswith("/") or path.startswith(DOWNLOAD_SERVER)):
			frappe.throw(
				_(
					"Enter the ERiC archive as an absolute path on the server or as its address on {0}."
				).format(DOWNLOAD_SERVER)
			)
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
	except transmission_adapter.TransmissionUnavailable as missing:
		error = _("The ERiC library layer of Steuerbote is not installed: {0} is missing.").format(
			missing.module
		)
	except Exception as failure:
		frappe.log_error(title=_("Installation of ERiC failed"))
		error = str(failure)
	settings = frappe.get_single(SETTINGS)
	if runtime is not None:
		settings.update(
			{
				"installed_version": runtime.version,
				"lib_dir": str(runtime.lib_dir),
				"log_dir": str(runtime.log_dir),
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
