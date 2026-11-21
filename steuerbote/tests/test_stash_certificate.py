"""stash_certificate, the one request that carries certificate and password to the server: nothing of either escapes
it, not into the Recorder, the Error Log or the answer of a failure, and what it keeps serves only the user who
entered it, for the document they entered it for, through the transmission the job is given."""

import base64
from unittest.mock import patch

import frappe
import frappe.recorder
from frappe.recorder import RECORDER_REQUEST_HASH
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request

from steuerbote.eric import secrets
from steuerbote.steuerbote.doctype.elster_transmission.transmission import (
	MAX_CERTIFICATE_BYTES,
	STASH_LIMIT,
	stash_certificate,
)
from steuerbote.tests.helpers import make_company, make_mapping, make_settings, make_user
from steuerbote.tests.transmitting import CERTIFICATE, JOB, PIN, FakeEric, Transmitting

STASH = "steuerbote.steuerbote.doctype.elster_transmission.transmission.stash_certificate"
ENCODED = base64.b64encode(CERTIFICATE).decode()
SECRETS = (PIN, ENCODED)
NO_BASE64 = "kein base64!"
COMPANY = "Steuerbote Test Zertifikat GmbH"
DATENLIEFERANT_ADDRESS = {
	"filer_name": COMPANY,
	"street": "Hauptstraße 1",
	"postal_code": "80331",
	"city": "München",
}
ENTERED_BY = "steuerbote-zertifikat@example.com"
SOMEONE_ELSE = "steuerbote-zertifikat-fremd@example.com"


class TestStashCertificate(Transmitting, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STZT")
		make_settings(COMPANY, [(2026, "monthly", 1)], **DATENLIEFERANT_ADDRESS)
		make_mapping(COMPANY)
		for user in (ENTERED_BY, SOMEONE_ELSE):
			make_user(user, "Accounts Manager")
		cls.returns = {}
		for period in (1, 2):
			doc = frappe.get_doc(
				{
					"doctype": "VAT Return",
					"company": COMPANY,
					"year": 2026,
					"rhythm": "monthly",
					"period_index": period,
				}
			).insert(ignore_permissions=True)
			doc.calculate()
			cls.returns[period] = doc.name

	def setUp(self):
		super().setUp()
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		self.addCleanup(setattr, frappe.local, "form_dict", frappe.local.form_dict)
		# Within a request every stash counts against the limit of its user, so no test leaves a count behind.
		self.addCleanup(frappe.cache.delete_keys, "rl:")

	def document(self, period: int = 1):
		return frappe.get_doc("VAT Return", self.returns[period])

	def form(self, period: int = 1, **values) -> dict:
		return {
			"document_type": "VAT Return",
			"document": self.returns[period],
			"password_protected_certificate": ENCODED,
			"certificate_password": PIN,
			**values,
		}

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

	def throttled(self) -> None:
		"""Frappe's rate limiter counts only within a request."""
		set_request(method="POST", path=f"/api/method/{STASH}")

	def assertShowsNoSecret(self, text: str) -> None:
		for secret in SECRETS:
			self.assertNotIn(secret, text)

	def test_a_failing_stash_answers_neutrally_and_neither_records_nor_logs_a_secret(self):
		"""The Recorder keeps the form of each request it records, Sentry receives the raw form with an error it
		reports, and Frappe's dialog of a server error copies the arguments of the request: a failure of the store
		is a ValidationError, which neither reports, and neither a record nor a log holds certificate or password."""
		form = self.requested(**self.form())
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
		form = self.requested(**self.form())
		self.recorded()
		self.assertTrue(stash_certificate(**form))
		frappe.recorder.dump()
		self.assertEqual(frappe.cache.hgetall(RECORDER_REQUEST_HASH), {})

	def test_a_refusal_names_neither_certificate_nor_password(self):
		for form in (
			self.form(password_protected_certificate=NO_BASE64),
			self.form(certificate_password=f"{PIN}ä"),
			self.form(document_type="Company"),
			{"password_protected_certificate": ENCODED, "certificate_password": PIN},
			{},
		):
			with self.subTest(fields=sorted(form)), self.assertRaises(frappe.ValidationError) as raised:
				stash_certificate(**self.requested(**form))
			self.assertShowsNoSecret(str(raised.exception) + frappe.as_json(frappe.local.message_log))

	def test_a_certificate_serves_only_the_user_and_the_document_it_was_entered_for(self):
		"""Whoever got hold of a token could otherwise send another return with the certificate."""
		self.use_runtime()
		attempts = (
			(SOMEONE_ELSE, 1, "another document or by another user"),
			(ENTERED_BY, 2, "another document or by another user"),
		)
		for user, period, message in attempts:
			with self.set_user(ENTERED_BY):
				token = stash_certificate(**self.form())
			# The request that is refused rolls back what it wrote.
			frappe.db.savepoint("refused")
			with (
				self.subTest(user=user, period=period),
				self.set_user(user),
				patch("frappe.enqueue") as enqueue,
				self.assertRaisesRegex(frappe.ValidationError, message),
			):
				self.document(period).transmit("test_send", token)
			frappe.db.rollback(save_point="refused")
			enqueue.assert_not_called()
		with self.set_user(ENTERED_BY):
			token = stash_certificate(**self.form())
			name, enqueue = self.transmit(self.document(), "test_send", token)
			fake = FakeEric()
			self.run_job(enqueue, fake)
		((run,),) = (fake.runs,)
		self.assertEqual((run["certificate"], run["password"]), (CERTIFICATE, PIN))
		self.assertEqual(frappe.db.get_value("ELSTER Transmission", name, "status"), "Erfolgreich")

	def test_the_job_is_given_nothing_that_unlocks_the_certificate(self):
		"""The arguments of a job stay in Redis and show in the list of RQ Jobs: they name the transmission, whose
		job alone takes the certificate, and never the token."""
		self.use_runtime()
		token = stash_certificate(**self.form())
		name, enqueue = self.transmit(self.document(), "test_send", token)
		(call,) = enqueue.call_args_list
		self.assertEqual(call.args, (JOB,))
		self.assertEqual(
			call.kwargs,
			{
				"name": self.returns[1],
				"operation": "test_send",
				"transmission": name,
				"queue": "long",
				"timeout": 300,
				"job_id": f"steuerbote:elster:{name}",
				"enqueue_after_commit": True,
			},
		)
		self.assertNotIn(token, repr(call))
		with self.assertRaises(secrets.SecretsExpired):
			secrets.hand_over(token, name, user=frappe.session.user, document=("VAT Return", self.returns[1]))
		self.run_job(enqueue, FakeEric())
		with self.assertRaises(secrets.SecretsExpired):
			secrets.take(name, user=frappe.session.user, document=("VAT Return", self.returns[1]))

	def test_each_user_stashes_a_certificate_at_most_ten_times_a_quarter_of_an_hour(self):
		"""Stashes are kept in the Redis cache, which drops what it cannot hold: unthrottled, one user could push out
		the certificate of a transmission another has started."""
		self.throttled()
		with self.set_user(ENTERED_BY):
			for _ in range(STASH_LIMIT):
				stash_certificate(**self.form())
			with self.assertRaises(frappe.RateLimitExceededError):
				stash_certificate(**self.form())
		with self.set_user(SOMEONE_ELSE):
			self.assertTrue(stash_certificate(**self.form()))

	def test_a_certificate_file_has_at_most_32_kib(self):
		self.assertEqual(MAX_CERTIFICATE_BYTES, 32 * 1024)
		largest = base64.b64encode(b"\x30" * MAX_CERTIFICATE_BYTES).decode()
		self.assertTrue(stash_certificate(**self.form(password_protected_certificate=largest)))
		for too_large in (
			base64.b64encode(b"\x30" * (MAX_CERTIFICATE_BYTES + 1)).decode(),
			"A" * (64 << 20),
		):
			with (
				self.subTest(length=len(too_large)),
				self.assertRaisesRegex(frappe.ValidationError, "at most 32 KiB"),
			):
				stash_certificate(**self.form(password_protected_certificate=too_large))
