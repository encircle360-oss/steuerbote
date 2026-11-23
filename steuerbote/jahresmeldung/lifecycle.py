"""The life of an annual document: its statuses, the moves between them, when it is filed and how often a key is.

Two lifecycles generalise that of the Umsatzsteuer-Voranmeldung and the Zusammenfassende Meldung (docs/architektur.md,
„Lebenslauf einer Meldung“):

- FILING, the Erklärungen and the E-Bilanz, which go to the Finanzamt: Entwurf, Berechnet or Bereit, Abgegeben, and
  Ersetzt once a Berichtigung of the same key is filed. Submitting files the document, so it follows a filing, an
  accepted Senden or the note of a filing elsewhere, and Buchen alone is refused. Nothing filed is cancelled: the
  Finanzamt keeps what it received, and a change goes to it as a Berichtigung (steuerbote.jahresmeldung.corrections).
- ACCOUNTS, the Jahresabschluss: Entwurf, Berechnet, Festgestellt, Übermittelt, Eingestellt, and Ersetzt. Submitting
  is the Feststellung, by which „die Gesellschafter [...] über die Feststellung des Jahresabschlusses [...] zu
  beschließen“ have (§ 42a Abs. 2 Satz 1 GmbHG); the Übermittlung to the Unternehmensregister and its Einstellung
  come after it. A Jahresabschluss that changes is cancelled and amended, since „Wird der Jahresabschluss [...]
  geändert, so ist auch die Änderung nach Absatz 1 Satz 1 offenzulegen“ (§ 325 Abs. 1b Satz 1 HGB), and the
  amendment replaces it.

Only Steuerbote sets the status, by the moves of Event: Berechnen (CALCULATE) makes a document Bereit when its
findings and the checks of its module allow it (steuerbote.jahresmeldung.findings.ready), else Berechnet; the
Jahresabschluss has no Bereit and stays Berechnet. A save that changes what Berechnen checked, a correction or a line
by hand, leaves it Berechnet (CHANGE) until Berechnen checks it again; another key discards the calculation
(DISCARD). A calculated document is filed (FILE) when it is ready, or when its remarks say why it is filed
nonetheless, as a Voranmeldung is („Bereit oder Anmerkungen“, fit_for_filing).

A key, the company and the year with what else a module adds to it, such as the Bilanzart of the E-Bilanz, holds one
draft at a time and is filed once: every further filing of it is a Berichtigung of a filed document of the key. A
document counts as filed once it is submitted, or once it was sent through Steuerbote with an outcome that is accepted
or unknown, cancelled or not, since the Finanzamt has it or may have it (docs/architektur.md, „Lebenslauf einer
Meldung“).

STANDARD_FIELDS describes the fields every annual document carries (contract of stage 3, 2.5), which the Frappe layer
reads and writes; field_problems compares the definition of a DocType with them.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any

DRAFT_DOCSTATUS = 0
SUBMITTED = 1
CANCELLED = 2


class Status(StrEnum):
	DRAFT = "Entwurf"
	CALCULATED = "Berechnet"
	READY = "Bereit"
	FILED = "Abgegeben"
	REPLACED = "Ersetzt"
	ADOPTED = "Festgestellt"
	TRANSMITTED = "Übermittelt"
	PUBLISHED = "Eingestellt"


class Event(Enum):
	CALCULATE = "calculate"
	"""Berechnen read the sources and checked the document."""
	CHANGE = "change"
	"""A save changed what Berechnen checked: a correction or a line by hand."""
	DISCARD = "discard"
	"""Another key: the calculation is gone."""
	FILE = "file"
	"""Submitting: the filing of an Erklärung or the E-Bilanz, the Feststellung of the Jahresabschluss."""
	TRANSMIT = "transmit"
	"""The Jahresabschluss went to the Unternehmensregister."""
	PUBLISH = "publish"
	"""The Unternehmensregister has eingestellt the Jahresabschluss."""
	REPLACE = "replace"
	"""A later filing of the key replaces the document."""


class Problem(Enum):
	NO_MOVE = "no_move"
	NOT_CALCULATED = "not_calculated"
	NOT_READY = "not_ready"
	DRAFT_EXISTS = "draft_exists"
	FILED_EXISTS = "filed_exists"
	NOT_A_FILING = "not_a_filing"


class LifecycleError(ValueError):
	"""A move or a filing the lifecycle refuses; ``subject`` names what it refused, a status or a document."""

	def __init__(self, problem: Problem, subject: object = "") -> None:
		self.problem = problem
		self.subject = "" if subject is None else str(subject)
		super().__init__(f"{problem.value}: {self.subject}" if self.subject else problem.value)


@dataclass(frozen=True, slots=True)
class Lifecycle:
	"""The statuses of a kind of annual document and how it is filed.

	``ready`` is the status of a calculated document that is ready, None where the lifecycle has none; ``filed`` the
	status submitting gives, and ``later`` the statuses that follow it. ``submitted_by_hand`` says whether a user
	submits the document with Buchen, or only a filing does; ``cancellable`` whether a submitted document is cancelled
	and amended.
	"""

	name: str
	statuses: tuple[Status, ...]
	ready: Status | None
	filed: Status
	later: tuple[Status, ...] = ()
	submitted_by_hand: bool = False
	cancellable: bool = False

	@property
	def options(self) -> str:
		"""The options of the field status."""
		return "\n".join(self.statuses)

	@property
	def calculated(self) -> tuple[Status, ...]:
		"""The statuses of a document Berechnen calculated and nothing filed yet."""
		return (Status.CALCULATED,) if self.ready is None else (Status.CALCULATED, self.ready)

	@property
	def filings(self) -> tuple[Status, ...]:
		"""The statuses of a filed document that no later filing replaced."""
		return (self.filed, *self.later)

	def move(self, status: object, event: Event, *, ready: bool = False) -> Status:
		"""The status after ``event``, from ``status`` as the document stores it."""
		current = self._status(status)
		unfiled = (Status.DRAFT, *self.calculated)
		if event is Event.CALCULATE and current in unfiled:
			return self.ready if ready and self.ready else Status.CALCULATED
		if event is Event.CHANGE and current in unfiled:
			return Status.DRAFT if current is Status.DRAFT else Status.CALCULATED
		if event is Event.DISCARD and current in unfiled:
			return Status.DRAFT
		if event is Event.FILE and current is Status.DRAFT:
			raise LifecycleError(Problem.NOT_CALCULATED, current)
		if event is Event.FILE and current in self.calculated:
			return self.filed
		transmitted, published = (*self.later, None, None)[:2]
		if event is Event.TRANSMIT and transmitted and current is self.filed:
			return transmitted
		if event is Event.PUBLISH and published and current is transmitted:
			return published
		if event is Event.REPLACE and current in self.filings:
			return Status.REPLACED
		raise LifecycleError(Problem.NO_MOVE, current)

	def _status(self, status: object) -> Status:
		try:
			current = Status(status)
		except ValueError:
			raise LifecycleError(Problem.NO_MOVE, status) from None
		if current not in self.statuses:
			raise LifecycleError(Problem.NO_MOVE, current)
		return current


FILING = Lifecycle(
	"filing",
	(Status.DRAFT, Status.CALCULATED, Status.READY, Status.FILED, Status.REPLACED),
	ready=Status.READY,
	filed=Status.FILED,
)
"""The Umsatzsteuererklärung, the Körperschaft- and the Gewerbesteuererklärung and the E-Bilanz."""

ACCOUNTS = Lifecycle(
	"accounts",
	(Status.DRAFT, Status.CALCULATED, Status.ADOPTED, Status.TRANSMITTED, Status.PUBLISHED, Status.REPLACED),
	ready=None,
	filed=Status.ADOPTED,
	later=(Status.TRANSMITTED, Status.PUBLISHED),
	submitted_by_hand=True,
	cancellable=True,
)
"""The Jahresabschluss."""


def fit_for_filing(lifecycle: Lifecycle, status: object, ready: bool, remarks: str | None) -> None:
	"""Refuse to file a document that is not calculated, or not ready without remarks that say why."""
	if status not in lifecycle.calculated:
		raise LifecycleError(Problem.NOT_CALCULATED, status)
	if not ready and not (remarks or "").strip():
		raise LifecycleError(Problem.NOT_READY)


@dataclass(frozen=True, slots=True)
class Other:
	"""Another document of the same key: its name, its docstatus, whether it is a Berichtigung and whether it was sent
	through Steuerbote with an outcome that is accepted or unknown."""

	name: str
	docstatus: int
	is_correction: bool = False
	sent: bool = False


def refuse_second_draft(others: Iterable[Other]) -> None:
	"""A key holds one draft at a time."""
	draft = next((other for other in others if other.docstatus == DRAFT_DOCSTATUS), None)
	if draft is not None:
		raise LifecycleError(Problem.DRAFT_EXISTS, draft.name)


def refuse_second_filing(is_correction: bool, others: Iterable[Other]) -> None:
	"""A key is filed once: after a document of it is submitted, or sent through Steuerbote, every other document of
	it is a Berichtigung."""
	if is_correction:
		return
	filed = next((other for other in others if other.docstatus == SUBMITTED or other.sent), None)
	if filed is not None:
		raise LifecycleError(Problem.FILED_EXISTS, filed.name)


def check_correction(is_correction: bool, corrects: Other | None) -> None:
	"""A Berichtigung corrects a filed document of its key."""
	if is_correction and (corrects is None or corrects.docstatus != SUBMITTED):
		raise LifecycleError(Problem.NOT_A_FILING, corrects.name if corrects else "")


FILED_VIA = ("eric", "mein_elster", "other_way", "upload")
"""How a document was filed: through ERiC, in Mein ELSTER, another way, or uploaded to the Unternehmensregister."""


@dataclass(frozen=True, slots=True)
class StandardField:
	"""A field every annual document carries, as its DocType defines it."""

	fieldname: str
	fieldtype: str
	label: str
	options: str | None = None
	read_only: bool = True
	reqd: bool = False


def standard_fields(lifecycle: Lifecycle, doctype: str, *, transmits: bool) -> tuple[StandardField, ...]:
	"""The fields of an annual document of the DocType, in their order; one that ``transmits`` to ELSTER through ERiC
	also has the lock of its transmissions."""
	lock = (StandardField("transmission_in_progress", "Check", "Transmission Running"),) if transmits else ()
	return (
		StandardField("company", "Link", "Company", "Company", read_only=False, reqd=True),
		StandardField("year", "Int", "Year", read_only=False, reqd=True),
		StandardField("fiscal_year", "Link", "Fiscal Year", "Fiscal Year"),
		StandardField("from_date", "Date", "From Date"),
		StandardField("to_date", "Date", "To Date"),
		StandardField("status", "Select", "Status", lifecycle.options),
		StandardField("ready", "Check", "Ready to File"),
		StandardField("remarks", "Small Text", "Remarks", read_only=False),
		StandardField("deadline", "Date", "Due Date"),
		StandardField("is_correction", "Check", "Correction"),
		StandardField("corrects", "Link", "Corrects", doctype),
		*lock,
		StandardField("filed_via", "Select", "Filed Via", "\n" + "\n".join(FILED_VIA)),
		StandardField("filed_on", "Date", "Filed On"),
		StandardField("transferticket", "Data", "Transferticket"),
		StandardField("filed_by", "Link", "Noted By", "User"),
		StandardField("filing_note", "Small Text", "How and When Filed"),
		StandardField("findings", "Table", "Findings", "Annual Filing Finding"),
	)


def field_problems(definition: Mapping[str, Any], lifecycle: Lifecycle, *, transmits: bool) -> list[str]:
	"""What the definition of a DocType, as its JSON file holds it, lacks of the standard fields or defines otherwise."""
	defined = {field["fieldname"]: field for field in definition.get("fields", ())}
	problems = []
	for expected in standard_fields(lifecycle, definition["name"], transmits=transmits):
		field = defined.get(expected.fieldname)
		if field is None:
			problems.append(f"{expected.fieldname}: missing")
			continue
		for key, value in (
			("fieldtype", expected.fieldtype),
			("label", expected.label),
			("options", expected.options or None),
			("read_only", int(expected.read_only)),
			("reqd", int(expected.reqd)),
		):
			actual = field.get(key) or (0 if key in ("read_only", "reqd") else None)
			if actual != value:
				problems.append(f"{expected.fieldname}: {key} {actual!r}, not {value!r}")
	return problems
