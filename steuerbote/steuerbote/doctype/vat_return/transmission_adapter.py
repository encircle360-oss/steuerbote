"""The calls of the Frappe layer into the ERiC runtime, with the paths and the user of the site filled in.

The documents that go to ELSTER and the ERiC Settings reach the worker and the runtime directory of steuerbote.eric
only through these functions, so that their tests can replace what needs a real ERiC and run the rest for real:
the XML of steuerbote.elster, the header, the simulation and the store of certificate and password.
"""

from pathlib import Path

import frappe
from frappe.utils import cint, get_bench_path, getdate

from steuerbote.eric import runtime, service
from steuerbote.eric.datenart import Datenart
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.proxy import Proxy, parse
from steuerbote.eric.result import Operation, TransmissionResult
from steuerbote.eric.runtime import RuntimeInfo

ERIC_SETTINGS = "ERiC Settings"


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


def runtime_status(hersteller_id: str) -> tuple[runtime.Check, ...]:
	"""The checks of the status page: platform, the runtimes installed, their libraries, the plugin of the current year
	and the one of the Zusammenfassende Meldung, and the Hersteller-ID."""
	return runtime.status(runtime_root(), year=getdate().year, hersteller_id=hersteller_id)


def install_from_archive(archive_path: str, sha256: str) -> RuntimeInfo:
	"""Unpack the ERiC archive on the server after checking its SHA-256; the worker loads the libraries
	once before the version is activated."""
	return runtime.install_from_archive(
		Path(archive_path),
		sha256,
		runtime_root(),
		installed_by=frappe.session.user,
		probe=service.library_versions,
	)


def runtime_root() -> Path:
	"""Where ERiC runtimes live: outside every site, so they are neither served nor backed up.

	``steuerbote_eric_root`` in common_site_config.json overrides the directory ``sites/eric`` of the bench.
	"""
	configured = frappe.conf.get("steuerbote_eric_root")
	return Path(configured) if configured else Path(get_bench_path(), "sites", "eric")
