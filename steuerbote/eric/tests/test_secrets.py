"""Runs with bench run-tests only: the store needs the Redis cache and the encryption key of a site, and
the tracebacks are the ones Frappe writes into the Error Log."""

import base64
import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.eric import secrets, service
from steuerbote.eric.result import Operation
from steuerbote.eric.runtime import RuntimeInfo
from steuerbote.eric.secrets import SecretsExpired, SecretsMismatch, discard, hand_over, stash, take
from steuerbote.eric.tests import stub
from steuerbote.eric.tests.test_service import HEADER, nutzdaten
from steuerbote.eric.tests.tracebacks import interrupted_after

CERTIFICATE = b"\x30\x82\x01\x00fake\x00pkcs12\x00container"
PIN = "Test-PIN-4711"
SECRETS = (PIN, base64.b64encode(CERTIFICATE).decode(), "pkcs12")
USER = "steuerbote-geheim@example.com"
OTHER_USER = "steuerbote-fremd@example.com"
RETURN = ("VAT Return", "UStVA-2026-00001")
OTHER_RETURN = ("VAT Return", "UStVA-2026-00002")
TRANSMISSION = "ELSTER-2026-00001"


class Interrupted(BaseException):
	"""An exception that no handler of steuerbote catches."""


class SecretsTest(IntegrationTestCase):
	def key(self, token: str) -> bytes:
		return frappe.cache.make_key(secrets.KEY.format(token=token))

	def handed_over_key(self, transmission: str) -> bytes:
		return frappe.cache.make_key(secrets.HANDED_OVER.format(transmission=transmission))

	def stashed(self, user: str = USER, document: tuple[str, str] = RETURN) -> str:
		token = stash(CERTIFICATE, PIN, user=user, document=document)
		self.addCleanup(frappe.cache.delete, self.key(token))
		return token

	def handed_over(self, transmission: str = TRANSMISSION) -> None:
		hand_over(self.stashed(), transmission, user=USER, document=RETURN)
		self.addCleanup(frappe.cache.delete, self.handed_over_key(transmission))

	def test_hands_certificate_and_pin_over_once(self):
		token = self.stashed()
		hand_over(token, TRANSMISSION, user=USER, document=RETURN)
		with self.assertRaises(SecretsExpired):
			hand_over(token, "ELSTER-2026-00002", user=USER, document=RETURN)
		self.assertEqual(take(TRANSMISSION, user=USER, document=RETURN), (CERTIFICATE, PIN))
		with self.assertRaises(SecretsExpired):
			take(TRANSMISSION, user=USER, document=RETURN)

	def test_a_token_starts_a_transmission_only_for_its_user_and_document(self):
		"""The token is a capability: whoever holds it could send another document with the certificate, so the
		stash names the user who entered it and the document it was entered for, and the token is used up by the
		first attempt."""
		for user, document in ((OTHER_USER, RETURN), (USER, OTHER_RETURN), (OTHER_USER, OTHER_RETURN)):
			token = self.stashed()
			with self.subTest(user=user, document=document):
				with self.assertRaises(SecretsMismatch):
					hand_over(token, TRANSMISSION, user=user, document=document)
				with self.assertRaises(SecretsExpired):
					hand_over(token, TRANSMISSION, user=USER, document=RETURN)
				self.assertIsNone(frappe.cache.get(self.handed_over_key(TRANSMISSION)))

	def test_the_job_takes_the_certificate_only_for_the_user_and_document_of_its_transmission(self):
		for user, document in ((OTHER_USER, RETURN), (USER, OTHER_RETURN)):
			self.handed_over()
			with self.subTest(user=user, document=document):
				with self.assertRaises(SecretsMismatch):
					take(TRANSMISSION, user=user, document=document)
				with self.assertRaises(SecretsExpired):
					take(TRANSMISSION, user=USER, document=RETURN)

	def test_keeps_them_encrypted_for_15_minutes_at_most(self):
		token = self.stashed()
		stored = frappe.cache.get(self.key(token))
		for plain in (
			PIN.encode(),
			base64.b64encode(CERTIFICATE),
			b"pkcs12",
			USER.encode(),
			RETURN[1].encode(),
		):
			self.assertNotIn(plain, stored)
		self.assertTrue(0 < frappe.cache.ttl(self.key(token)) <= 15 * 60)
		frappe.cache.expire(self.key(token), 60)
		hand_over(token, TRANSMISSION, user=USER, document=RETURN)
		self.addCleanup(frappe.cache.delete, self.handed_over_key(TRANSMISSION))
		self.assertEqual(frappe.cache.get(self.handed_over_key(TRANSMISSION)), stored)
		self.assertTrue(0 < frappe.cache.ttl(self.handed_over_key(TRANSMISSION)) <= 60)

	def test_keys_belong_to_the_site(self):
		token = self.stashed()
		self.assertTrue(self.key(token).startswith(f"{frappe.local.conf.db_name}|".encode()))
		self.assertTrue(
			self.handed_over_key(TRANSMISSION).startswith(f"{frappe.local.conf.db_name}|".encode())
		)

	def test_each_stash_gets_a_token_of_its_own(self):
		first, second = self.stashed(), self.stashed()
		self.assertNotEqual(first, second)
		self.assertRegex(first, r"^[A-Za-z0-9_-]{43}$")

	def test_refuses_unknown_and_malformed_tokens(self):
		for token in ("x" * 43, "", "../../etc/passwd", "a b", None, TRANSMISSION):
			with self.subTest(token=token), self.assertRaises(SecretsExpired):
				hand_over(token, TRANSMISSION, user=USER, document=RETURN)

	def test_refuses_a_store_it_cannot_read(self):
		token = self.stashed()
		with (
			patch("frappe.utils.password.decrypt", return_value='{"certificate": "", "password": ""}'),
			self.assertRaises(SecretsExpired),
		):
			hand_over(token, TRANSMISSION, user=USER, document=RETURN)
		self.handed_over()
		with (
			patch("frappe.utils.password.decrypt", return_value="kein JSON"),
			self.assertRaises(SecretsExpired),
		):
			take(TRANSMISSION, user=USER, document=RETURN)

	def test_a_transmission_closed_without_its_job_drops_its_certificate(self):
		self.handed_over()
		discard(TRANSMISSION)
		discard(TRANSMISSION)
		with self.assertRaises(SecretsExpired):
			take(TRANSMISSION, user=USER, document=RETURN)


class TracebackTest(IntegrationTestCase):
	"""What frappe.get_traceback(with_context=True) writes into the Error Log in developer mode."""

	def setUp(self):
		super().setUp()
		self.enterContext(patch.dict(frappe.local.conf, {"developer_mode": 1}))

	def traceback_of(self, call: Callable[[], object]) -> str:
		try:
			call()
		except Exception, Interrupted:
			return frappe.get_traceback(with_context=True)
		self.fail("the call raised nothing")

	def assertShowsNoSecret(self, traceback: str) -> None:
		self.assertIn("Traceback with variables", traceback)
		for secret in SECRETS:
			self.assertNotIn(secret, traceback)

	def test_stash_when_the_cache_fails(self):
		with patch.object(frappe.cache, "set", side_effect=ConnectionError("Redis ist fort")):
			traceback = self.traceback_of(lambda: stash(CERTIFICATE, PIN, user=USER, document=RETURN))
		self.assertShowsNoSecret(traceback)
		self.assertIn("payload_secret = ********", traceback)

	def test_stash_with_a_broken_encryption_key(self):
		with patch.dict(frappe.local.conf, {"encryption_key": "kein Fernet-Schlüssel"}):
			traceback = self.traceback_of(lambda: stash(CERTIFICATE, PIN, user=USER, document=RETURN))
		self.assertShowsNoSecret(traceback)
		self.assertIn("txt = <sealed>", traceback)

	def test_take_of_a_store_it_cannot_read(self):
		plain = json.dumps({"certificate": base64.b64encode(CERTIFICATE).decode(), "password": PIN})
		token = stash(CERTIFICATE, PIN, user=USER, document=RETURN)
		hand_over(token, TRANSMISSION, user=USER, document=RETURN)
		with patch("frappe.utils.password.decrypt", return_value=plain):
			traceback = self.traceback_of(lambda: take(TRANSMISSION, user=USER, document=RETURN))
		self.assertShowsNoSecret(traceback)
		self.assertIn("SecretsExpired", traceback)

	def test_a_run_of_eric_that_an_exception_interrupts(self):
		directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-traceback-"))
		self.addCleanup(shutil.rmtree, directory)
		lib_dir = stub.install(directory)
		runtime = RuntimeInfo("44.3.6.0", lib_dir, lib_dir, directory / "log", "12345", True)
		with interrupted_after(1, Interrupted()):
			traceback = self.traceback_of(
				lambda: service.run(
					Operation.SEND,
					nutzdaten("STUB-SLEEP"),
					HEADER,
					runtime,
					CERTIFICATE,
					PIN,
					timeout_seconds=60,
				)
			)
		self.assertShowsNoSecret(traceback)
		self.assertIn("input = <sealed>", traceback)
