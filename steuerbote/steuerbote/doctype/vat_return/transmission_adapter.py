"""The calls of the Frappe layer into the ERiC runtime, with the paths and the user of the site filled in.

The VAT Return and the ERiC Settings reach the worker and the runtime directory of steuerbote.eric only
through these functions, so that their tests can replace what needs a real ERiC and run the rest for real:
the XML of steuerbote.elster, the header, the simulation and the store of certificate and password.
"""

from pathlib import Path

import frappe
from frappe.utils import get_bench_path

from steuerbote.eric import runtime, service
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import Operation, TransmissionResult
from steuerbote.eric.runtime import RuntimeInfo


def run(
	operation: Operation,
	nutzdaten_xml: str,
	header: EnvelopeHeader,
	runtime_info: RuntimeInfo | None,
	certificate_secret: bytes | None,
	certificate_password: str | None,
) -> TransmissionResult:
	"""One run of ERiC in its worker process with a runtime, of the simulation without one."""
	return service.run(
		operation, nutzdaten_xml, header, runtime_info, certificate_secret, certificate_password
	)


def detect_runtime(year: int, operation: Operation, hersteller_id: str, log_dir: Path) -> RuntimeInfo | None:
	"""The newest installed runtime with the plugin of the year, or None.

	A beta sends no real case, so it serves Testsenden only (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 2.3).
	"""
	return runtime.detect(
		runtime_root(),
		year=year,
		allow_beta=operation is Operation.TEST_SEND,
		log_dir=log_dir,
		hersteller_id=hersteller_id,
	)


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
