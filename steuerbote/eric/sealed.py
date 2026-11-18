"""Bytes that hold certificate or PIN and never show them.

In developer mode Frappe writes the local variables of every frame of a traceback into the Error Log, and
hides a value only when the name of its variable, or a key of a dictionary, contains password, secret,
token or key. A value passes through frames whose names steuerbote does not choose: the request for the
worker is the variable input of subprocess.Popen.communicate while the worker runs, and the plain text of
the store is the variable txt of frappe.utils.password.encrypt. As Sealed, such a value shows as a
placeholder in every frame, under any name.
"""


class Sealed(bytes):
	"""Bytes whose str and repr are a placeholder."""

	__slots__ = ()

	def __repr__(self) -> str:
		return "<sealed>"

	__str__ = __repr__
