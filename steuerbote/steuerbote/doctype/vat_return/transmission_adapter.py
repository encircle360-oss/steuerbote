"""The seam between the Frappe layer and the ERiC packages of Steuerbote.

The VAT Return and the ERiC Settings reach the library layer (steuerbote.eric: service, result, runtime,
secrets) and the XML builder (steuerbote.elster: ustva_xml, envelope) only through these functions. Each
imports its module when it is called, so the Frappe layer loads and its tests run without those packages;
a missing package surfaces as TransmissionUnavailable, which the transmission records as a failure.
"""

import dataclasses
import importlib
from pathlib import Path
from types import ModuleType
from typing import Any

import frappe
from frappe.utils import get_bench_path

# The address the operator copied from the ELSTER developer area; Steuerbote never builds one itself.
DOWNLOAD_PREFIX = "https://"


class TransmissionUnavailable(Exception):
	"""A module the ELSTER transmission needs is not installed."""

	def __init__(self, module: str) -> None:
		super().__init__(module)
		self.module = module


def _module(name: str) -> ModuleType:
	try:
		return importlib.import_module(name)
	except ModuleNotFoundError as error:
		if error.name and name.startswith(error.name):
			raise TransmissionUnavailable(name) from error
		raise


def build_nutzdaten(vat_return: Any, hersteller_id: str) -> str:
	"""The Nutzdaten of the return, the element Anmeldungssteuern, as UTF-8 XML for ERiC."""
	return _module("steuerbote.elster.ustva_xml").to_nutzdaten(vat_return, hersteller_id=hersteller_id)


def run(
	operation: str,
	nutzdaten_xml: str,
	header: dict[str, str | None],
	runtime: Any,
	certificate_secret: bytes | None,
	certificate_password: str | None,
) -> Any:
	"""One run of steuerbote.eric.service: through the ERiC worker with a runtime, else the simulation.

	``header`` holds the fields of steuerbote.elster.envelope.EnvelopeHeader. Returns a
	steuerbote.eric.result.TransmissionResult.
	"""
	result = _module("steuerbote.eric.result")
	service = _module("steuerbote.eric.service")
	envelope = _module("steuerbote.elster.envelope")
	return service.run(
		result.Operation(operation),
		nutzdaten_xml,
		envelope.EnvelopeHeader(**header),
		runtime,
		certificate_secret,
		certificate_password,
	)


def detect_runtime(hersteller_id: str) -> Any:
	"""The installed ERiC runtime (steuerbote.eric.runtime.RuntimeInfo) with the Hersteller-ID, or None."""
	runtime = _module("steuerbote.eric.runtime").detect(runtime_root())
	return dataclasses.replace(runtime, hersteller_id=hersteller_id) if runtime else None


def install_from_archive(archive: str, sha256: str) -> Any:
	"""Unpack the ERiC archive the operator downloaded; returns the RuntimeInfo of the new runtime."""
	source = archive if archive.startswith(DOWNLOAD_PREFIX) else Path(archive)
	return _module("steuerbote.eric.runtime").install_from_archive(source, sha256, runtime_root())


def stash(certificate_secret: bytes, certificate_password: str) -> str:
	"""Keep certificate and password encrypted for a short time; returns the token for take()."""
	return _module("steuerbote.eric.secrets").stash(certificate_secret, certificate_password)


def take(token: str) -> tuple[bytes, str]:
	"""Certificate and password behind ``token``, once: the token is gone afterwards."""
	return _module("steuerbote.eric.secrets").take(token)


def runtime_root() -> Path:
	"""Where ERiC runtimes live: outside every site, so they are neither served nor backed up.

	``steuerbote_eric_root`` in common_site_config.json overrides the directory ``sites/eric`` of the bench.
	"""
	configured = frappe.conf.get("steuerbote_eric_root")
	return Path(configured) if configured else Path(get_bench_path(), "sites", "eric")
