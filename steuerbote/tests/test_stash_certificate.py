"""stash_certificate, the one request that carries certificate and password to the server: nothing of either escapes
it, not into the Recorder, the Error Log or the answer of a failure."""

import base64
from unittest.mock import patch

import frappe
import frappe.recorder
from frappe.recorder import RECORDER_REQUEST_HASH
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request

from steuerbote.steuerbote.doctype.elster_transmission.transmission import stash_certificate
from steuerbote.tests.transmitting import CERTIFICATE, PIN

STASH = "steuerbote.steuerbote.doctype.elster_transmission.transmission.stash_certificate"
ENCODED = base64.b64encode(CERTIFICATE).decode()
SECRETS = (PIN, ENCODED)


class TestStashCertificate(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		self.addCleanup(setattr, frappe.local, "form_dict", frappe.local.form_dict)

	def requested(self, **form) -> dict:
		"""A POST of the desk to stash_certificate, its form in frappe.form_dict as Frappe takes it in."""
		set_request(method="POST", path=f"/api/method/{STASH}")
		frappe.local.form_dict = frappe._dict(form)
		return form

	def recorded(self) -> None:
		"""The Recorder of the Administrator recording the request, as Frappe's before_request hook starts it once
		the Recorder runs; stopping it would end the transaction of the test, so it is only deleted."""
		frappe.recorder.delete()
		self.addCleanup(frappe.recorder.delete)
		frappe.recorder.record(force=True)
		self.assertIs(frappe.local._recorder.form_dict, frappe.local.form_dict)

	def assertShowsNoSecret(self, text: str) -> None:
		for secret in SECRETS:
			self.assertNotIn(secret, text)

	def test_a_failing_stash_answers_neutrally_and_neither_records_nor_logs_a_secret(self):
		"""The Recorder keeps the form of each request it records, Sentry receives the raw form with an error it
		reports, and Frappe's dialog of a server error copies the arguments of the request: a failure of the store
		is a ValidationError, which neither reports, and neither a record nor a log holds certificate or password."""
		form = self.requested(password_protected_certificate=ENCODED, certificate_password=PIN)
		self.recorded()
		with (
			patch.object(frappe.cache, "set", side_effect=ConnectionError(f"Redis ist fort: {PIN}")),
			self.assertRaises(frappe.ValidationError) as raised,
		):
			stash_certificate(**form)
		error = raised.exception
		self.assertIn("could not be kept", str(error))
		self.assertEqual((error.__cause__, error.__context__), (None, None))
		self.assertShowsNoSecret(str(error) + frappe.as_json(frappe.local.message_log))
		self.assertFalse(hasattr(frappe.local, "_recorder"))
		frappe.recorder.dump()
		self.assertShowsNoSecret(repr(frappe.cache.hgetall(RECORDER_REQUEST_HASH)))
		with patch.dict(frappe.local.conf, {"developer_mode": 1}):
			try:
				raise error
			except frappe.ValidationError:
				logged = frappe.log_error(title=str(error))
		entry = frappe.get_doc("Error Log", logged.name)
		self.assertIn("Traceback with variables", entry.error)
		self.assertShowsNoSecret(frappe.as_json(entry.as_dict()))

	def test_a_stash_is_never_recorded(self):
		form = self.requested(password_protected_certificate=ENCODED, certificate_password=PIN)
		self.recorded()
		self.assertTrue(stash_certificate(**form))
		frappe.recorder.dump()
		self.assertEqual(frappe.cache.hgetall(RECORDER_REQUEST_HASH), {})

	def test_a_refusal_names_neither_certificate_nor_password(self):
		for form in (
			{"password_protected_certificate": "kein base64!", "certificate_password": PIN},
			{"password_protected_certificate": ENCODED, "certificate_password": f"{PIN}ä"},
			{"certificate_password": PIN},
			{},
		):
			with self.subTest(fields=sorted(form)), self.assertRaises(frappe.ValidationError) as raised:
				stash_certificate(**self.requested(**form))
			self.assertShowsNoSecret(str(raised.exception) + frappe.as_json(frappe.local.message_log))
