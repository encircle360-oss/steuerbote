"""The calls of the Frappe layer into the ERiC runtime, with the paths and the user of the site filled in.

The documents that go to ELSTER and the ERiC Settings reach the worker and the runtime directory of steuerbote.eric
only through these functions, so that their tests can replace what needs a real ERiC and run the rest for real:
the XML of steuerbote.elster, the header, the simulation and the store of certificate and password.

The runtimes serve every site of the bench, and installing one loads the library of its archive as the user of
the bench. So the archive, its SHA-256 and the directory of the runtimes come from common_site_config.json, which
only the operator of the server writes, and never from a site: neither from its site_config.json nor from the
ERiC Settings, which a System Manager edits.
"""

import os
import re
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint, escape_html, get_bench_path, getdate

from steuerbote.eric import runtime, service
from steuerbote.eric.datenart import Datenart
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.proxy import Proxy, parse
from steuerbote.eric.result import Operation, TransmissionResult
from steuerbote.eric.runtime import RuntimeInfo

ERIC_SETTINGS = "ERiC Settings"
ARCHIVE = "steuerbote_eric_archive"
ARCHIVE_SHA256 = "steuerbote_eric_archive_sha256"
RUNTIME_ROOT = "steuerbote_eric_root"
SHA256 = re.compile(r"[0-9a-f]{64}")


def run(
	operation: Operation,
	nutzdaten_xml: str,
	header: EnvelopeHeader,
	runtime_info: RuntimeInfo | None,
	certificate_secret: bytes | None,
	certificate_password: str | None,
) -> TransmissionResult:
	"""One run of ERiC in its worker process with a runtime, through the proxy of the ERiC Settings if they name
	one, or of the simulation without a runtime, which reaches no server."""
	return service.run(
		operation,
		nutzdaten_xml,
		header,
		runtime_info,
		certificate_secret,
		certificate_password,
		proxy=None if runtime_info is None else settings_proxy(),
	)


def settings_proxy() -> Proxy | None:
	"""The proxy of the ERiC Settings, with its password from the encrypted store of the site, or None."""
	settings = frappe.get_single(ERIC_SETTINGS)
	if not settings.proxy_url:
		return None
	proxy_password = settings.get_password("proxy_password", raise_exception=False)
	return parse(settings.proxy_url, settings.proxy_user, proxy_password)


def detect_runtime(
	datenart: Datenart, operation: Operation, hersteller_id: str, log_dir: Path
) -> RuntimeInfo | None:
	"""The newest released runtime with the plugin of the Datenart, such as the UStVA of a year; for Prüfen and
	Testsenden a beta when no released runtime has that plugin, or None.

	A beta sends no real case (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 2.3), so Senden never gets one;
	steuerbote.eric.runtime.detect prefers a released runtime whenever a beta is allowed. The runtime carries
	whether the ERiC Settings record the confirmation of the Datenschutzhinweise, without which
	steuerbote.eric.service runs no ERiC.
	"""
	return runtime.detect(
		runtime_root(),
		datenart=datenart,
		allow_beta=operation is not Operation.SEND,
		log_dir=log_dir,
		hersteller_id=hersteller_id,
		confirmed_privacy_notice=bool(cint(frappe.get_single(ERIC_SETTINGS).privacy_notice_confirmed)),
	)


def steuernummer_valid(number: str) -> bool | None:
	"""Whether ERiC takes the 13-digit Steuernummer of ELSTER, by EricPruefeSteuernummer of the newest installed runtime
	(ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 6.3.3); None without a runtime, without the confirmed Datenschutzhinweise
	or when the check gives no answer. ERiC writes its eric.log beside those of the transmissions of the site."""
	try:
		runtime_info = _steuernummer_runtime()
	except runtime.RuntimeIntegrityError:
		return None
	return service.steuernummer_valid(runtime_info, number)


def _steuernummer_runtime() -> RuntimeInfo | None:
	from steuerbote.steuerbote.doctype.eric_settings.eric_settings import eric_log_root

	return runtime.detect(
		runtime_root(),
		allow_beta=True,
		log_dir=eric_log_root() / "steuernummer",
		confirmed_privacy_notice=bool(cint(frappe.get_single(ERIC_SETTINGS).privacy_notice_confirmed)),
	)


def zero_steuernummer(entered: str) -> str:
	"""The message for a Steuernummer of nothing but zeros (steuerbote.elster.steuernummer)."""
	return _(
		"{0} is no Steuernummer: it is nothing but zeros. Enter the Steuernummer of the last notice of the Finanzamt."
	).format(escape_html(entered))


def require_valid_steuernummer(number: str, entered: str) -> None:
	"""Refuse a Steuernummer whose check digit ERiC refuses, when the settings are saved rather than at the first
	transmission; ``entered`` is the number as the user wrote it. A check that gives no answer lets the save pass
	and says why, since the first Prüfen of a return checks the number again."""
	valid = steuernummer_valid(number)
	if valid is False:
		frappe.throw(
			_(
				"ERiC refuses the Steuernummer {0}: its check digit or its Finanzamt is wrong. Compare it with the last notice of the Finanzamt."
			).format(escape_html(entered)),
			title=_("Invalid Steuernummer"),
		)
	if valid is None:
		frappe.msgprint(
			_(
				"ERiC has not checked the Steuernummer {0}: {1} The first Prüfen of a return checks it; until then, compare it with the last notice of the Finanzamt."
			).format(escape_html(entered), _unchecked_reason()),
			title=_("Steuernummer not checked"),
			indicator="orange",
		)


def _unchecked_reason() -> str:
	try:
		runtime_info = _steuernummer_runtime()
	except runtime.RuntimeIntegrityError:
		return _("The libraries of the installed ERiC differ from its manifest.")
	if runtime_info is None:
		return _("No ERiC runtime is installed.")
	if not runtime_info.confirmed_privacy_notice:
		return _("The ERiC Settings do not record the confirmation of the Datenschutzhinweise.")
	return _("ERiC gave no answer to the check.")


def runtime_status(hersteller_id: str) -> tuple[runtime.Check, ...]:
	"""The checks of the status page: platform, the runtimes installed, their libraries, the plugin of the current year
	and the one of the Zusammenfassende Meldung, and the Hersteller-ID."""
	return runtime.status(runtime_root(), year=getdate().year, hersteller_id=hersteller_id)


def install_configured_archive() -> RuntimeInfo:
	"""Unpack the ERiC archive the operator names after checking its SHA-256; the worker loads the libraries
	once before the version is activated."""
	archive_path, sha256 = configured_archive()
	return runtime.install_from_archive(
		archive_path,
		sha256,
		runtime_root(),
		installed_by=frappe.session.user,
		probe=service.library_versions,
	)


def configured_archive() -> tuple[Path, str]:
	"""The ERiC archive and its SHA-256 as ``steuerbote_eric_archive`` and ``steuerbote_eric_archive_sha256`` of
	common_site_config.json name them."""
	archive_path, sha256 = shown_archive()
	if not (archive_path and sha256):
		frappe.throw(
			_(
				"Name the ERiC archive and its SHA-256 as {0} and {1} in common_site_config.json of the bench, with bench set-config -g on the server."
			).format(ARCHIVE, ARCHIVE_SHA256)
		)
	if not os.path.isabs(archive_path):
		frappe.throw(_("{0} in common_site_config.json is no absolute path on the server.").format(ARCHIVE))
	if not SHA256.fullmatch(sha256):
		frappe.throw(_("{0} in common_site_config.json has 64 hexadecimal digits.").format(ARCHIVE_SHA256))
	return Path(archive_path), sha256


def shown_archive() -> tuple[str, str]:
	"""Archive and SHA-256 of common_site_config.json as the ERiC Settings show them, empty where none is named."""
	config = common_site_config()
	return (
		str(config.get(ARCHIVE) or "").strip(),
		str(config.get(ARCHIVE_SHA256) or "").strip().lower(),
	)


def runtime_root() -> Path:
	"""Where ERiC runtimes live: outside every site, so they are neither served nor backed up.

	``steuerbote_eric_root`` in common_site_config.json overrides the directory ``sites/eric`` of the bench.
	"""
	configured = common_site_config().get(RUNTIME_ROOT)
	return Path(configured) if configured else Path(get_bench_path(), "sites", "eric")


def common_site_config() -> dict:
	"""common_site_config.json of the bench, read anew: what its operator configures for every site."""
	return frappe.get_common_site_config()
