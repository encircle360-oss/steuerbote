"""The confirmation of a foreign USt-IdNr. in the Bestätigungsverfahren (§ 18e UStG), pure Python.

ustid checks a number before anyone is asked, bzst queries the eVatR REST API of the BZSt, vies queries
VIES of the European Commission, and service.confirm asks the BZSt first and VIES only when the BZSt
cannot answer. Each query becomes a Confirmation (result), which keeps the answer as the proof. The HTTP
transport and the clock are passed in (transport): the Frappe layer chooses proxies and timeouts, the tests
use fakes, and nothing here imports Frappe.
"""

from steuerbote.vatid.result import Confirmation, Details, Match, Outcome, Service
from steuerbote.vatid.service import confirm
from steuerbote.vatid.transport import Clock, Fetch, Request, Response, UrllibFetch
from steuerbote.vatid.ustid import is_german, is_plausible, normalize, problem, structure_hint

__all__ = [
	"Clock",
	"Confirmation",
	"Details",
	"Fetch",
	"Match",
	"Outcome",
	"Request",
	"Response",
	"Service",
	"UrllibFetch",
	"confirm",
	"is_german",
	"is_plausible",
	"normalize",
	"problem",
	"structure_hint",
]
