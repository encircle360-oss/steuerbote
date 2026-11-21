import io
import urllib.error
import urllib.request
import urllib.response
from email.message import Message
from unittest import TestCase

from steuerbote.vatid.transport import MAX_RESPONSE_BYTES, Request, Response, UrllibFetch

URL = "https://api.evatr.vies.bzst.de/app/v1/abfrage"
BODY = b'{"anfragendeUstid":"DE123456789","angefragteUstid":"ATU12345678"}'
# What a server elsewhere would answer in place of the BZSt, invented.
FORGED = b'{"id":"0a1b2c3d4e5f6071","anfrageZeitpunkt":"2026-11-20T15:00:00+01:00","status":"evatr-0000"}'


class FakeAnswer:
	"""What urllib's opener returns for a response with a status of 2xx."""

	def __init__(self, status: int, body: bytes) -> None:
		self.status = status
		self.stream = io.BytesIO(body)
		self.closed = False

	def read(self, size: int = -1) -> bytes:
		return self.stream.read(size)

	def __enter__(self) -> FakeAnswer:
		return self

	def __exit__(self, *exception) -> None:
		self.closed = True


class FakeOpener:
	"""An opener that hands out one answer or raises one error, and keeps what it was asked."""

	def __init__(self, answer: FakeAnswer | None = None, error: Exception | None = None) -> None:
		self.answer = answer
		self.error = error
		self.calls: list[tuple[urllib.request.Request, float]] = []

	def open(self, request: urllib.request.Request, timeout: float) -> FakeAnswer:
		self.calls.append((request, timeout))
		if self.error is not None:
			raise self.error
		return self.answer


def http_error(code: int, body: bytes) -> urllib.error.HTTPError:
	return urllib.error.HTTPError(URL, code, "Bad Request", Message(), io.BytesIO(body))


class FakeServer(urllib.request.BaseHandler):
	"""Answers in front of the handlers of urllib: the first request with a redirect to ``location``, every later
	one with an answer of its own, which a fetch that follows the redirect would return. Keeps the addresses asked."""

	handler_order = 100

	def __init__(self, status: int, location: str) -> None:
		self.status = status
		self.location = location
		self.asked: list[str] = []

	def https_open(self, request: urllib.request.Request) -> urllib.response.addinfourl:
		return self._answer(request)

	def http_open(self, request: urllib.request.Request) -> urllib.response.addinfourl:
		return self._answer(request)

	def _answer(self, request: urllib.request.Request) -> urllib.response.addinfourl:
		self.asked.append(request.full_url)
		headers = Message()
		if len(self.asked) == 1:
			headers["Location"] = self.location
			answer = urllib.response.addinfourl(io.BytesIO(b"moved"), headers, request.full_url, self.status)
		else:
			answer = urllib.response.addinfourl(io.BytesIO(FORGED), headers, request.full_url, 200)
		answer.msg = "Found"
		return answer


class RequestTest(TestCase):
	def test_headers_are_read_only(self):
		request = Request(URL, {"Content-Type": "application/json"}, BODY)
		with self.assertRaises(TypeError):
			request.headers["Accept"] = "text/html"


class UrllibFetchTest(TestCase):
	def test_posts_the_body_with_the_headers_and_the_timeout(self):
		opener = FakeOpener(FakeAnswer(200, b"{}"))
		UrllibFetch(timeout_seconds=12.5, opener=opener)(
			Request(URL, {"Content-Type": "application/json"}, BODY)
		)
		((request, timeout),) = opener.calls
		self.assertEqual((request.full_url, request.get_method(), request.data), (URL, "POST", BODY))
		self.assertEqual(request.get_header("Content-type"), "application/json")
		self.assertEqual(timeout, 12.5)

	def test_returns_status_and_body_of_the_answer(self):
		answer = FakeAnswer(200, b'{"status":"evatr-0000"}')
		response = UrllibFetch(opener=FakeOpener(answer))(Request(URL, {}, BODY))
		self.assertEqual(response, Response(200, b'{"status":"evatr-0000"}'))
		self.assertTrue(answer.closed)

	def test_returns_an_error_status_with_its_body_instead_of_raising(self):
		body = (
			b'{"id":"0a1b2c3d4e5f6071","anfrageZeitpunkt":"2026-11-20T15:00:00+01:00","status":"evatr-0004"}'
		)
		response = UrllibFetch(opener=FakeOpener(error=http_error(400, body)))(Request(URL, {}, BODY))
		self.assertEqual(response, Response(400, body))

	def test_reads_no_more_than_the_limit(self):
		long_body = b"x" * (MAX_RESPONSE_BYTES + 10)
		fetch = UrllibFetch(opener=FakeOpener(FakeAnswer(200, long_body)))
		self.assertEqual(len(fetch(Request(URL, {}, BODY)).body), MAX_RESPONSE_BYTES)
		fetch = UrllibFetch(opener=FakeOpener(error=http_error(503, long_body)))
		self.assertEqual(len(fetch(Request(URL, {}, BODY)).body), MAX_RESPONSE_BYTES)

	def test_raises_os_error_when_no_answer_came(self):
		for error in (urllib.error.URLError("Name or service not known"), TimeoutError("timed out")):
			fetch = UrllibFetch(opener=FakeOpener(error=error))
			with self.subTest(error=error), self.assertRaises(OSError):
				fetch(Request(URL, {}, BODY))

	def test_fetches_https_only(self):
		opener = FakeOpener(FakeAnswer(200, b"{}"))
		for url in (
			"http://api.evatr.vies.bzst.de/app/v1/abfrage",
			"file:///etc/passwd",
			"ftp://example.org/",
		):
			with self.subTest(url=url), self.assertRaises(ValueError):
				UrllibFetch(opener=opener)(Request(url, {}, BODY))
		self.assertEqual(opener.calls, [])

	def test_follows_no_redirect(self):
		"""The answer is the proof of the query, so it comes from the address asked: a redirect, to another host, to
		plain HTTP or back to the same address, is returned as the answer it is."""
		for status, location in (
			(302, "http://api.evatr.vies.bzst.de/app/v1/abfrage"),
			(301, "https://evatr.example.org/app/v1/abfrage"),
			(303, URL),
			(307, "https://evatr.example.org/app/v1/abfrage"),
			(308, "https://evatr.example.org/app/v1/abfrage"),
		):
			fetch = UrllibFetch()
			server = FakeServer(status, location)
			fetch.opener.add_handler(server)
			with self.subTest(status=status):
				self.assertEqual(fetch(Request(URL, {}, BODY)), Response(status, b"moved"))
				self.assertEqual(server.asked, [URL])

	def test_waits_a_minute_by_default(self):
		self.assertEqual(UrllibFetch().timeout_seconds, 60)

	def test_each_fetch_keeps_cookies_in_a_jar_of_its_own(self):
		first, second = UrllibFetch(), UrllibFetch()
		self.assertIsNot(first.opener, second.opener)
		jars = [
			handler.cookiejar
			for fetch in (first, second)
			for handler in fetch.opener.handlers
			if isinstance(handler, urllib.request.HTTPCookieProcessor)
		]
		self.assertEqual(len(jars), 2)
		self.assertIsNot(jars[0], jars[1])
