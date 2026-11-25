"""What an ERiC run did and what came back.

ERiC answers each call of EricBearbeiteVorgang with a return code, a return buffer with the errors or
hints of the Plausibilitätsprüfung and, when sending, the answer of the ELSTER server
(ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 6.2). A TransmissionResult keeps what steuerbote needs from
that: the outcome, the Transferticket, the messages for the user and the PDF. The simulation returns
the same type, marked as simulated. Results cross the process boundary of the worker as JSON.
"""

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

TESTMERKER = "700000004"
"""Testmerker of a test case that the ELSTER server deletes on receipt (Entwicklerhandbuch, Tabelle 6-7)."""

ERROR = "error"
HINT = "hint"
SCHEMA_NOT_CHECKED = "SIM-001"
"""The hint of the simulation that it checked the structure of the Nutzdaten alone, without the schema of the
ERiC documentation."""
SEVERITIES = frozenset({ERROR, HINT})

EXIT_OK = 0
"""The worker process wrote its answer to standard output, whatever the outcome."""
EXIT_FAILURE = 1
"""The worker process met an unexpected error; standard error names its type."""
EXIT_INVALID_REQUEST = 2
"""The worker process did not understand the request and loaded nothing."""


class Operation(Enum):
	VALIDATE = "validate"
	"""EricBearbeiteVorgang without sending: Plausibilitätsprüfung, hints and a preview PDF."""
	TEST_SEND = "test_send"
	"""Validate and send with the Testmerker; the ELSTER server accepts the case and deletes it."""
	SEND = "send"
	"""Validate and send for real."""

	@property
	def sends(self) -> bool:
		return self is not Operation.VALIDATE


class Outcome(Enum):
	VALID = "valid"
	"""Checked without errors, possibly with hints. Nothing was sent."""
	INVALID = "invalid"
	"""The Plausibilitätsprüfung found errors. Nothing was sent."""
	ACCEPTED = "accepted"
	"""The ELSTER server accepted the data and confirmed the Transferticket."""
	REJECTED = "rejected"
	"""The ELSTER server answered with an error in the TransferHeader or a NutzdatenHeader."""
	FAILED = "failed"
	"""Nothing was sent: the run ended before the transfer, in steuerbote or with a code of ERiC that occurs
	only before it, such as configuration, input, certificate, PIN or no connection."""
	UNKNOWN = "unknown"
	"""A send may or may not have reached ELSTER: any other code of ERiC, or a worker lost after it started.
	Never send again before the data are checked in Mein ELSTER."""

	@property
	def ok(self) -> bool:
		return self in (Outcome.VALID, Outcome.ACCEPTED)


SERVER_OUTCOMES = frozenset({Outcome.ACCEPTED, Outcome.REJECTED, Outcome.UNKNOWN})


@dataclass(frozen=True, slots=True)
class Message:
	code: str
	"""ERiC return code, Fehler- or Hinweiscode of a rule, server code, or SIM-… for the simulation."""
	text: str
	"""German text for the user."""
	severity: str
	"""ERROR or HINT."""
	field: str | None = None
	"""Kennzahl or XML path, when known."""

	def __post_init__(self):
		if self.severity not in SEVERITIES:
			raise ValueError(f"unknown severity {self.severity!r}, expected one of {sorted(SEVERITIES)}")


UNKNOWN_MESSAGE = Message(
	"SB-UNKNOWN",
	"Ob die Daten bei ELSTER angekommen sind, ist unbekannt. Nicht erneut senden, bevor geklärt ist, "
	"ob die Anmeldung eingegangen ist.",
	ERROR,
)
"""Goes with every result whose outcome is UNKNOWN."""


@dataclass(frozen=True, slots=True)
class TransmissionResult:
	operation: Operation
	ok: bool
	simulated: bool
	eric_version: str
	"""Version of the ERiC runtime, such as 44.3.6.0, or "simulation"."""
	transferticket: str | None
	"""Transferticket from the server answer; None for a validation and when the server sent none."""
	testmerker: str | None
	"""TESTMERKER for a test send, None otherwise."""
	messages: tuple[Message, ...] = ()
	protocol_pdf: bytes | None = None
	"""ERiC's Übertragungsprotokoll or preview, or the simulation's placeholder."""
	server_response_xml: str | None = None
	outcome: Outcome | None = None
	"""Derived from ok and the operation when not given."""

	def __post_init__(self):
		object.__setattr__(self, "messages", tuple(self.messages))
		if self.outcome is None:
			sent = Outcome.ACCEPTED if self.operation.sends else Outcome.VALID
			object.__setattr__(self, "outcome", sent if self.ok else Outcome.FAILED)
		if self.outcome.ok != self.ok:
			raise ValueError(f"ok={self.ok} contradicts the outcome {self.outcome.value}")
		if not self.operation.sends and (self.outcome in SERVER_OUTCOMES or self.transferticket is not None):
			raise ValueError("a validation never reaches the ELSTER server")
		if self.testmerker != (TESTMERKER if self.operation is Operation.TEST_SEND else None):
			raise ValueError(f"the Testmerker {TESTMERKER} belongs to a test send and only to it")

	def to_dict(self) -> dict[str, object]:
		"""The result as JSON values; the PDF in base64."""
		pdf = self.protocol_pdf
		return {
			"operation": self.operation.value,
			"ok": self.ok,
			"outcome": self.outcome.value,
			"simulated": self.simulated,
			"eric_version": self.eric_version,
			"transferticket": self.transferticket,
			"testmerker": self.testmerker,
			"messages": [
				{"code": m.code, "text": m.text, "severity": m.severity, "field": m.field}
				for m in self.messages
			],
			"protocol_pdf": None if pdf is None else base64.b64encode(pdf).decode(),
			"server_response_xml": self.server_response_xml,
		}

	@classmethod
	def from_dict(cls, data: object) -> TransmissionResult:
		"""Read a result written by to_dict, refusing anything of another shape."""
		if not isinstance(data, Mapping):
			raise ValueError("a result is a JSON object")
		messages = _value(data, "messages", list)
		pdf = _optional(data, "protocol_pdf", str)
		try:
			return cls(
				operation=Operation(_value(data, "operation", str)),
				ok=_value(data, "ok", bool),
				simulated=_value(data, "simulated", bool),
				eric_version=_value(data, "eric_version", str),
				transferticket=_optional(data, "transferticket", str),
				testmerker=_optional(data, "testmerker", str),
				messages=tuple(_message(message) for message in messages),
				protocol_pdf=None if pdf is None else base64.b64decode(pdf, validate=True),
				server_response_xml=_optional(data, "server_response_xml", str),
				outcome=Outcome(_value(data, "outcome", str)),
			)
		except binascii.Error as error:
			raise ValueError(f"protocol_pdf is not base64: {error}") from error


def _value[T](data: Mapping, key: str, kind: type[T]) -> T:
	value = data.get(key)
	if not isinstance(value, kind):
		raise ValueError(f"{key} must be {kind.__name__}, not {type(value).__name__}")
	return value


def _optional[T](data: Mapping, key: str, kind: type[T]) -> T | None:
	return None if data.get(key) is None else _value(data, key, kind)


def _message(data: object) -> Message:
	if not isinstance(data, Mapping):
		raise ValueError("a message is a JSON object")
	return Message(
		code=_value(data, "code", str),
		text=_value(data, "text", str),
		severity=_value(data, "severity", str),
		field=_optional(data, "field", str),
	)
