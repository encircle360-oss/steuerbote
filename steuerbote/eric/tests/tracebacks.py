"""Tracebacks with the local variables of their frames, as Frappe writes them into the Error Log.

In developer mode frappe.utils.get_traceback(with_context=True) prints every local variable of every
frame and hides a value only when the name of its variable, or a key of a plain dictionary, contains one
of the words of SENSITIVE. frame_variables renders a traceback by the same rules without Frappe, and
without shortening long values, so that a test can check that no secret appears in it.
"""

import re
import signal
from collections.abc import Iterator
from contextlib import contextmanager

SENSITIVE = re.compile("password|passwd|pwd|secret|token|key|authorization|cookie", re.IGNORECASE)
PLACEHOLDER = "********"


def frame_variables(error: BaseException) -> str:
	"""Each frame of the traceback of error with its local variables, hidden as Frappe hides them."""
	lines = []
	traceback = error.__traceback__
	while traceback is not None:
		frame = traceback.tb_frame
		lines.append(f"{frame.f_code.co_filename} in {frame.f_code.co_name}")
		for name, value in frame.f_locals.items():
			lines.append(f"    {name} = {PLACEHOLDER if _sensitive(name) else _top_level(value)}")
		traceback = traceback.tb_next
	return "\n".join(lines)


@contextmanager
def interrupted_after(seconds: float, error: BaseException) -> Iterator[None]:
	"""Raise error from a signal handler after seconds, as a background job is ended when it runs too long."""

	def interrupt(_signal: int, _frame: object) -> None:
		raise error

	previous = signal.signal(signal.SIGALRM, interrupt)
	signal.setitimer(signal.ITIMER_REAL, seconds)
	try:
		yield
	finally:
		signal.setitimer(signal.ITIMER_REAL, 0)
		signal.signal(signal.SIGALRM, previous)


def _sensitive(name: object) -> bool:
	return isinstance(name, str) and (SENSITIVE.search(name) is not None or name.lower() == "sid")


def _top_level(value: object) -> str:
	if type(value) is dict:
		value = {key: PLACEHOLDER if _sensitive(key) else item for key, item in value.items()}
	return _text(value, depth=1)


def _text(value: object, depth: int) -> str:
	if isinstance(value, str):
		return value
	if isinstance(value, dict):
		return (
			"{" + ", ".join(f"{_text(key, depth)}: {_text(item, depth)}" for key, item in value.items()) + "}"
		)
	if isinstance(value, list | tuple | set | frozenset):
		return "[" + ", ".join(_text(item, depth) for item in value) + "]"
	text = str(value)
	kind = type(value)
	attributes = getattr(value, "__dict__", None)
	if depth > 0 and kind.__str__ is object.__str__ and kind.__repr__ is object.__repr__ and attributes:
		shown = ", ".join(f"{name}={_text(item, depth - 1)}" for name, item in attributes.items())
		text += f"({shown})"
	return text
