"""The setup of a company as a list of steps: what Steuerbote einrichten runs, in which order, and what each step did.

A step is plain data: a key, an English label that the desk translates, its order among the steps, the keys of the
steps whose documents it needs, and the dotted path of the function that runs it. The steps for the
Umsatzsteuer-Voranmeldung live in steuerbote/steuerbote/setup.py; any other module or app adds its own steps through
the hook steuerbote_setup_steps of its hooks.py, one dict per step with the fields of Step (Step.from_hook). plan()
checks the steps and puts them in the order they run: a step after every step it needs and otherwise by order and
key, so the same steps always run in the same order.

A step reports one Outcome and notes on what it did: it created its document, skipped it because the document was
there, could not decide what only the user can settle, failed, or did not run because a step it needs has no
document. A note marked open names something the user still has to do. A step makes only what is missing, so a
second run creates nothing; what it must not do on its own, such as relabelling a field of ERPNext, it offers as an
Action, which the page shows as a button.

Messages are English templates with positional placeholders, which the Frappe layer translates before formatting
them, as in SetupError. This module is pure Python and never imports Frappe.
"""

import re
from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from enum import Enum

NOT_A_STEP = "A setup step is a dict with key, label, order, run and needs, not {0}."
MISSING_FIELDS = "The setup step {0} lacks {1}."
UNKNOWN_FIELDS = "The setup step {0} has fields Steuerbote does not know: {1}."
NOT_A_KEY = (
	"{0} is not the key of a setup step: lowercase letters, digits and underscores, starting with a letter."
)
NO_LABEL = "The setup step {0} has no label."
NOT_AN_ORDER = "The order of the setup step {0} is {1}, not a whole number."
NOT_A_FUNCTION = "The setup step {0} runs {1}, which is not the dotted path of a function."
NEEDS_ITSELF = "The setup step {0} needs itself."
DUPLICATE_STEP = "The setup step {0} is defined twice."
UNKNOWN_NEED = "The setup step {0} needs {1}, which is no setup step."
CYCLE = "The setup steps {0} need each other in a circle."
NOT_AN_ACTION = "The action {0} of a setup step calls {1}, which is not the dotted path of a function."
MESSAGES = (
	NOT_A_STEP,
	MISSING_FIELDS,
	UNKNOWN_FIELDS,
	NOT_A_KEY,
	NO_LABEL,
	NOT_AN_ORDER,
	NOT_A_FUNCTION,
	NEEDS_ITSELF,
	DUPLICATE_STEP,
	UNKNOWN_NEED,
	CYCLE,
	NOT_AN_ACTION,
)

KEY = re.compile(r"[a-z][a-z0-9_]*")
DOTTED_PATH = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+")
REQUIRED_FIELDS = ("key", "label", "order", "run")
FIELDS = (*REQUIRED_FIELDS, "needs")


class SetupError(ValueError):
	"""A setup step is not defined as Steuerbote reads it; ``template`` and ``values`` make the message."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


class Outcome(Enum):
	"""What a step did."""

	CREATED = "created"
	SKIPPED = "skipped"
	UNDECIDED = "undecided"
	FAILED = "failed"
	BLOCKED = "blocked"


# The outcomes after which the document of a step exists, so that a step that needs it can run.
WITH_DOCUMENT = frozenset({Outcome.CREATED, Outcome.SKIPPED})


@dataclass(frozen=True, slots=True)
class Note:
	"""What a step tells about its work, as an English template and its values; ``open`` is left to the user."""

	template: str
	values: tuple[object, ...] = ()
	open: bool = False

	def __post_init__(self) -> None:
		object.__setattr__(self, "values", tuple(self.values))


@dataclass(frozen=True, slots=True)
class Action:
	"""What a step offers the user to do: an English label that the desk translates and the dotted path of a
	whitelisted function, which the page calls with the company and then runs the setup again."""

	label: str
	method: str

	def __post_init__(self) -> None:
		label_ok = isinstance(self.label, str) and bool(self.label.strip())
		if not label_ok or not isinstance(self.method, str) or not DOTTED_PATH.fullmatch(self.method):
			raise SetupError(NOT_AN_ACTION, self.label, self.method)


@dataclass(frozen=True, slots=True)
class StepResult:
	"""The outcome of a step, its notes, the document it made or found, as (DocType, name), and what it offers the
	user to do."""

	outcome: Outcome
	notes: tuple[Note, ...] = ()
	document: tuple[str, str] | None = None
	action: Action | None = None

	def __post_init__(self) -> None:
		object.__setattr__(self, "outcome", Outcome(self.outcome))
		object.__setattr__(self, "notes", tuple(self.notes))


@dataclass(frozen=True, slots=True)
class Step:
	"""A step of the setup: ``run`` is the dotted path of a function that takes the context of the run and returns
	a StepResult; ``needs`` are the keys of the steps whose documents it works with."""

	key: str
	label: str
	order: int
	run: str
	needs: tuple[str, ...] = ()

	def __post_init__(self) -> None:
		_require_key(self.key)
		if not isinstance(self.label, str) or not self.label.strip():
			raise SetupError(NO_LABEL, self.key)
		if isinstance(self.order, bool) or not isinstance(self.order, int):
			raise SetupError(NOT_AN_ORDER, self.key, self.order)
		if not isinstance(self.run, str) or not DOTTED_PATH.fullmatch(self.run):
			raise SetupError(NOT_A_FUNCTION, self.key, self.run)
		if isinstance(self.needs, str):
			raise SetupError(NOT_A_KEY, self.needs)
		needs = tuple(dict.fromkeys(self.needs))
		for need in needs:
			_require_key(need)
		if self.key in needs:
			raise SetupError(NEEDS_ITSELF, self.key)
		object.__setattr__(self, "needs", needs)

	@classmethod
	def from_hook(cls, entry: object) -> Step:
		"""The step an entry of the hook steuerbote_setup_steps defines: a dict with key, label, order and run, and
		optionally needs, a list of keys."""
		if not isinstance(entry, ReadOnlyMapping):
			raise SetupError(NOT_A_STEP, entry)
		name = entry.get("key", entry)
		if missing := [field for field in REQUIRED_FIELDS if field not in entry]:
			raise SetupError(MISSING_FIELDS, name, ", ".join(missing))
		if unknown := sorted(str(field) for field in entry if field not in FIELDS):
			raise SetupError(UNKNOWN_FIELDS, name, ", ".join(unknown))
		needs = entry.get("needs") or ()
		if isinstance(needs, str):
			raise SetupError(NOT_A_KEY, needs)
		return cls(
			key=entry["key"], label=entry["label"], order=entry["order"], run=entry["run"], needs=tuple(needs)
		)


def plan(steps: Iterable[Step]) -> tuple[Step, ...]:
	"""The steps in the order they run: each after the steps it needs, otherwise by order and then key."""
	by_key: dict[str, Step] = {}
	for step in steps:
		if step.key in by_key:
			raise SetupError(DUPLICATE_STEP, step.key)
		by_key[step.key] = step
	for step in by_key.values():
		for need in step.needs:
			if need not in by_key:
				raise SetupError(UNKNOWN_NEED, step.key, need)
	waiting = sorted(by_key.values(), key=lambda step: (step.order, step.key))
	planned: list[Step] = []
	done: set[str] = set()
	while waiting:
		ready = next((step for step in waiting if done.issuperset(step.needs)), None)
		if ready is None:
			raise SetupError(CYCLE, ", ".join(step.key for step in waiting))
		planned.append(ready)
		done.add(ready.key)
		waiting.remove(ready)
	return tuple(planned)


def missing_needs(step: Step, results: ReadOnlyMapping[str, StepResult]) -> tuple[str, ...]:
	"""The steps the step needs whose documents are missing: they failed, did not run or could not decide."""
	return tuple(
		need for need in step.needs if need not in results or results[need].outcome not in WITH_DOCUMENT
	)


def changed(results: Iterable[StepResult]) -> bool:
	"""Whether a run made anything; a run that only found what was there changed nothing."""
	return any(result.outcome is Outcome.CREATED for result in results)


def _require_key(value: object) -> None:
	if not isinstance(value, str) or not KEY.fullmatch(value):
		raise SetupError(NOT_A_KEY, value)
