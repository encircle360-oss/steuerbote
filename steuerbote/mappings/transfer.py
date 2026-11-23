"""The file a mapping travels in: Zuordnung exportieren writes it, Zuordnung importieren reads it back.

A file is JSON in UTF-8 with a header and a body:

	{
		"header": {
			"format": "steuerbote/vat-return-mapping",
			"format_version": 1,
			"app_version": "0.5.0",
			"company": "Muster GmbH",
			"chart": "SKR03",
			"defaults_version": "SKR03 2026.1",
			"exported_on": "2026-11-23",
			"sha256": "…"
		},
		"body": {"mapping": {…}, "defaults": {…}}
	}

``format`` names the kind of mapping and ``format_version`` the shape of its body; a reader takes only the kind it
asks for and versions up to FORMAT_VERSION. The body is what the mapping holds, in the plain data of its converter
(steuerbote/mapping_sync.py for the VAT Return Mapping). ``sha256`` is the SHA-256 of the canonical JSON of the body:
keys sorted, no blanks, UTF-8 as it is, so it does not depend on how the file is indented. It tells a file that was
damaged or changed by hand after the export; it is no signature, since anyone can compute it anew. Company, app
version, chart, defaults version and day inform the reader and the user; which chart a mapping may take is the
importer's decision.

read() checks the text in this order: JSON, header and body, the format and its version, the other fields of the
header, the checksum. A file that fails raises TransferError with an English template and its values, which the
Frappe layer translates. This module is pure Python and never imports Frappe.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any

FORMAT_VERSION = 1
HEADER_FIELDS = (
	"format",
	"format_version",
	"app_version",
	"company",
	"chart",
	"defaults_version",
	"exported_on",
	"sha256",
)

NOT_JSON = "The file is no JSON."
NOT_A_FILE = "The file is no mapping of Steuerbote: it needs a header and a body."
OTHER_FORMAT = "The file holds {0}, not {1}."
NEWER_FORMAT = "The file has the format version {0}; this Steuerbote reads up to {1}."
BAD_HEADER = "The header of the file lacks {0} or holds it in another form."
CHECKSUM_DIFFERS = (
	"The checksum of the file does not fit its content: it was damaged or changed after the export."
)
MESSAGES = (NOT_JSON, NOT_A_FILE, OTHER_FORMAT, NEWER_FORMAT, BAD_HEADER, CHECKSUM_DIFFERS)


class TransferError(ValueError):
	"""A file that cannot be imported; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


@dataclass(frozen=True, slots=True)
class Header:
	"""What the header of a file says; ``defaults_version`` is empty for a mapping that knew no defaults."""

	format: str
	format_version: int
	app_version: str
	company: str
	chart: str
	defaults_version: str
	exported_on: date
	sha256: str


@dataclass(frozen=True, slots=True)
class TransferFile:
	header: Header
	body: Any


def canonical_json(data: Any) -> str:
	"""JSON in one form for the same data, so that its text, and a digest of it, depend on nothing else."""
	return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def checksum(body: Any) -> str:
	"""The SHA-256 of the canonical JSON of the body, in hexadecimal digits."""
	return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def write(
	kind: str,
	body: Any,
	*,
	app_version: str,
	company: str,
	chart: str,
	defaults_version: str,
	exported_on: date,
) -> str:
	"""The text of the file: its header with the checksum of the body, then the body, indented for people to read."""
	header = {
		"format": kind,
		"format_version": FORMAT_VERSION,
		"app_version": app_version,
		"company": company,
		"chart": chart,
		"defaults_version": defaults_version,
		"exported_on": exported_on.isoformat(),
		"sha256": checksum(body),
	}
	return json.dumps({"header": header, "body": body}, indent=1, ensure_ascii=False) + "\n"


def read(text: str, kind: str) -> TransferFile:
	"""The header and body of the text of a file of the format ``kind``; raises TransferError for any other text."""
	try:
		data = json.loads(text)
	except ValueError:
		raise TransferError(NOT_JSON) from None
	if not isinstance(data, dict) or set(data) != {"header", "body"} or not isinstance(data["header"], dict):
		raise TransferError(NOT_A_FILE)
	header = data["header"]
	if not isinstance(header.get("format"), str):
		raise TransferError(BAD_HEADER, "format")
	if header["format"] != kind:
		raise TransferError(OTHER_FORMAT, header["format"], kind)
	version = header.get("format_version")
	if not _whole(version) or version < 1:
		raise TransferError(BAD_HEADER, "format_version")
	if version > FORMAT_VERSION:
		raise TransferError(NEWER_FORMAT, version, FORMAT_VERSION)
	for field in HEADER_FIELDS[2:]:
		if not isinstance(header.get(field), str):
			raise TransferError(BAD_HEADER, field)
	try:
		exported_on = date.fromisoformat(header["exported_on"])
	except ValueError:
		raise TransferError(BAD_HEADER, "exported_on") from None
	if header["sha256"] != checksum(data["body"]):
		raise TransferError(CHECKSUM_DIFFERS)
	values = {field: header[field] for field in HEADER_FIELDS}
	return TransferFile(Header(**{**values, "exported_on": exported_on}), data["body"])


def _whole(value: object) -> bool:
	"""True is an int to Python, but no version."""
	return isinstance(value, int) and not isinstance(value, bool)
