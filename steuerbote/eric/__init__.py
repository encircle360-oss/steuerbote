"""ERiC: the library of the tax administration that checks and sends ELSTER data.

Steuerbote never ships ERiC. An operator installs a runtime from the archive of the ELSTER developer
area (runtime), and each call runs once in a short-lived worker process (worker, through the ctypes
binding in api). Without a runtime the simulation answers instead (fake). service.run chooses between
them. All modules but secrets are pure Python and never import Frappe; secrets hands certificate and PIN
over to the background job.

The package does not import the worker, so python -m steuerbote.eric.worker runs it only once.
"""

from steuerbote.eric.fake import Simulation
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import (
	ERROR,
	HINT,
	TESTMERKER,
	UNKNOWN_MESSAGE,
	Message,
	Operation,
	Outcome,
	TransmissionResult,
)
from steuerbote.eric.runtime import (
	Check,
	Installation,
	RuntimeInfo,
	RuntimeInstallError,
	detect,
	install_from_archive,
	installations,
	status,
	verify,
)
from steuerbote.eric.service import PrivacyNoticeNotConfirmed, WorkerError, library_versions, run

__all__ = [
	"ERROR",
	"HINT",
	"TESTMERKER",
	"UNKNOWN_MESSAGE",
	"Check",
	"EnvelopeHeader",
	"Installation",
	"Message",
	"Operation",
	"Outcome",
	"PrivacyNoticeNotConfirmed",
	"RuntimeInfo",
	"RuntimeInstallError",
	"Simulation",
	"TransmissionResult",
	"WorkerError",
	"detect",
	"install_from_archive",
	"installations",
	"library_versions",
	"run",
	"status",
	"verify",
]
