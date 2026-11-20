"""The error of the ZM core."""


class ZmError(ValueError):
	"""A rule of the Zusammenfassende Meldung is broken.

	``template`` is an English sentence with positional placeholders and ``values`` fill them, so that the Frappe
	layer can translate the template before formatting it.
	"""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values
