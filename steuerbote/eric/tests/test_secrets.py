"""Runs with bench run-tests only: the store needs the Redis cache and the encryption key of a site."""

import base64

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.eric import secrets
from steuerbote.eric.secrets import SecretsExpired, stash, take

CERTIFICATE = b"\x30\x82\x01\x00fake\x00pkcs12\x00container"
PIN = "Test-PIN-4711"


class SecretsTest(IntegrationTestCase):
	def key(self, token: str) -> bytes:
		return frappe.cache.make_key(secrets.KEY.format(token=token))

	def test_hands_certificate_and_pin_over_once(self):
		token = stash(CERTIFICATE, PIN)
		self.assertEqual(take(token), (CERTIFICATE, PIN))
		with self.assertRaises(SecretsExpired):
			take(token)

	def test_keeps_them_encrypted_for_15_minutes_at_most(self):
		token = stash(CERTIFICATE, PIN)
		self.addCleanup(frappe.cache.delete, self.key(token))
		stored = frappe.cache.get(self.key(token))
		for plain in (PIN.encode(), base64.b64encode(CERTIFICATE), b"pkcs12"):
			self.assertNotIn(plain, stored)
		self.assertTrue(0 < frappe.cache.ttl(self.key(token)) <= 15 * 60)

	def test_keys_belong_to_the_site(self):
		token = stash(CERTIFICATE, PIN)
		self.addCleanup(frappe.cache.delete, self.key(token))
		self.assertTrue(self.key(token).startswith(f"{frappe.local.conf.db_name}|".encode()))

	def test_each_stash_gets_a_token_of_its_own(self):
		first, second = stash(CERTIFICATE, PIN), stash(CERTIFICATE, PIN)
		self.addCleanup(frappe.cache.delete, self.key(first), self.key(second))
		self.assertNotEqual(first, second)
		self.assertRegex(first, r"^[A-Za-z0-9_-]{43}$")

	def test_refuses_unknown_and_malformed_tokens(self):
		for token in ("x" * 43, "", "../../etc/passwd", "a b", None):
			with self.subTest(token=token), self.assertRaises(SecretsExpired):
				take(token)
