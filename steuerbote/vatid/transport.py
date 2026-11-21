"""The HTTP transport of a confirmation, passed in so that tests use fakes and the Frappe layer chooses
proxies and timeouts.

A Fetch sends one Request as a POST and returns the Response whatever its HTTP status: the BZSt answers a
refused or failed query with its status in the body of a 4xx or 5xx response, and VIES sends its faults
with HTTP 500. A Fetch raises OSError, and only OSError, when no response came at all. urllib's URLError,
TimeoutError, ssl.SSLError and the exceptions of requests all are OSError, so a transport that lets its
errors pass keeps to this, as long as it does not raise for an error status.

A Clock tells the time of the requests, with a time zone.
"""

import http.cookiejar
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

MAX_RESPONSE_BYTES = 1 << 20
"""Far more than any answer of the BZSt or VIES; a longer body is cut off and then unreadable."""
SERVER_ERROR = 500
"""The lowest HTTP status of a server error."""


@dataclass(frozen=True, slots=True)
class Request:
	url: str
	headers: Mapping[str, str]
	body: bytes

	def __post_init__(self):
		object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


@dataclass(frozen=True, slots=True)
class Response:
	status: int
	"""The HTTP status."""
	body: bytes


type Fetch = Callable[[Request], Response]
type Clock = Callable[[], datetime]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
	"""Answers a redirect with itself: urllib would follow it, also to another host or to plain HTTP, and the record
	of the query would keep an answer that did not come from the service asked."""

	def redirect_request(self, req, fp, code, msg, headers, newurl):
		raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


def _opener() -> urllib.request.OpenerDirector:
	return urllib.request.build_opener(
		urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), _NoRedirect()
	)


@dataclass(frozen=True, slots=True)
class UrllibFetch:
	"""A Fetch over urllib, HTTPS only and without following redirects, with the certificate store of the system and
	the proxies of the environment.

	Each instance keeps the cookies the services set in a jar of its own. Whether the BZSt ties a qualified
	query to the simple query before it is not documented; its status evatr-0008 speaks of a session. One
	instance per confirmation lets both queries share such a session and no more.
	"""

	timeout_seconds: float = 60.0
	"""For the connection and for each wait for data; the BZSt warns of long answer times."""
	opener: urllib.request.OpenerDirector = field(default_factory=_opener)

	def __call__(self, request: Request) -> Response:
		if not request.url.startswith("https://"):
			raise ValueError(f"only HTTPS is fetched, not {request.url!r}")
		http_request = urllib.request.Request(  # noqa: S310 - the scheme is https, checked above
			request.url, data=request.body, headers=dict(request.headers), method="POST"
		)
		try:
			with self.opener.open(http_request, timeout=self.timeout_seconds) as answer:
				return Response(answer.status, answer.read(MAX_RESPONSE_BYTES))
		except urllib.error.HTTPError as error:
			with error:
				return Response(error.code, error.read(MAX_RESPONSE_BYTES))
