"""One-shot hand-over of certificate and PIN from the request to the background job that sends.

The arguments of a background job stay in Redis for days and show in the list of RQ Jobs, so certificate
and PIN never become job arguments. The request stashes them encrypted with the site's encryption key
(frappe.utils.password.encrypt, Fernet) in the Redis cache under a random token, for 15 minutes at most;
the job gets only the token and takes them with GETDEL, so they can be read once. Nothing is written to
the database, a file or a log.

In developer mode an Error Log shows the local variables of each frame. Every variable that holds
certificate, PIN or their plain text therefore has secret or password in its name, and the plain text
passes to encrypt as Sealed; see steuerbote.eric.sealed.

This is the only module of steuerbote.eric that uses Frappe; it imports Frappe inside its functions.
"""

import base64
import json
import re
from secrets import token_urlsafe

from steuerbote.eric.sealed import Sealed

TTL_SECONDS = 15 * 60
KEY = "steuerbote:eric:secret:{token}"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")


class SecretsExpired(Exception):
	"""The token is unknown, expired or already used."""


def stash(certificate_secret: bytes, password: str) -> str:
	"""Keep certificate and password for one background job; the token is all the job may receive."""
	import frappe
	from frappe.utils.password import encrypt

	token = token_urlsafe(32)
	payload_secret = Sealed(
		json.dumps(
			{"certificate_secret": base64.b64encode(certificate_secret).decode(), "password": password}
		).encode()
	)
	# Not set_value: it would keep the value in the cache of the request as well, and pickle it. The key
	# carries the site prefix of make_key, which is what set_value would add.
	key, encrypted_secret = _key(token), encrypt(payload_secret)
	frappe.cache.set(key, encrypted_secret, ex=TTL_SECONDS)  # nosemgrep: frappe-cache-breaks-multitenancy
	return token


def take(token: str) -> tuple[bytes, str]:
	"""Certificate and password kept under the token; SecretsExpired the second time and after 15 minutes."""
	import frappe
	from frappe.utils.password import decrypt

	if not isinstance(token, str) or not _TOKEN.fullmatch(token):
		raise SecretsExpired("not a token of steuerbote.eric.secrets")
	stored_secret = frappe.cache.getdel(_key(token))
	if stored_secret is None:
		raise SecretsExpired("certificate and password are gone: expired or already taken")
	decrypted_secret = decrypt(stored_secret.decode())
	try:
		payload_secret = json.loads(decrypted_secret)
		return (
			base64.b64decode(payload_secret["certificate_secret"], validate=True),
			payload_secret["password"],
		)
	except ValueError, KeyError, TypeError:
		# from None keeps the frames of json and base64 out of the traceback: they hold the plain text.
		raise SecretsExpired("certificate and password are unreadable") from None


def _key(token: str) -> bytes:
	import frappe

	return frappe.cache.make_key(KEY.format(token=token))
