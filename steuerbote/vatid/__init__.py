"""The confirmation of a foreign USt-IdNr. in the Bestätigungsverfahren (§ 18e UStG), pure Python.

ustid checks a number before anyone is asked. Nothing here imports Frappe.
"""

from steuerbote.vatid.ustid import is_german, is_plausible, normalize, problem, structure_hint

__all__ = ["is_german", "is_plausible", "normalize", "problem", "structure_hint"]
