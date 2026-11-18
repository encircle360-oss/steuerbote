"""ERiC: the library of the tax administration that checks and sends ELSTER data.

Steuerbote never ships ERiC. An operator installs a runtime from the archive of the ELSTER developer
area (runtime), and each call runs once in a short-lived worker process (worker, through the ctypes
binding in api). Without a runtime the simulation answers instead (fake). service.run chooses between
them. All modules but secrets are pure Python and never import Frappe.
"""

from steuerbote.eric.result import (
	ERROR,
	HINT,
	TESTMERKER,
	Message,
	Operation,
	Outcome,
	TransmissionResult,
)

__all__ = [
	"ERROR",
	"HINT",
	"TESTMERKER",
	"Message",
	"Operation",
	"Outcome",
	"TransmissionResult",
]
