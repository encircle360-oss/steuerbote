"""One-shot hand-over of certificate and PIN from the request to the background job that sends.

The arguments of a background job stay in Redis for days and show in the list of RQ Jobs, so neither certificate
and PIN nor anything that unlocks them becomes a job argument. stash() keeps them encrypted with the site's
encryption key (frappe.utils.password.encrypt, Fernet) in the Redis cache under a random token, for 15 minutes at
most, sealed together with the user who entered them and the document they were entered for. hand_over() takes them
under the token once, when a transmission of a document starts, and only for that user and document; it keeps them
for the rest of their 15 minutes under the name of the transmission, the one key the job of that transmission
knows. take() gives them to that job once, for the user and document of its transmission again. A token is thus
used up by the first transmission it is handed to, whoever holds it. Nothing is written to the database, a file or
a log.

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
HANDED_OVER = "steuerbote:eric:transmission:{transmission}"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")


class SecretsExpired(Exception):
	"""The token is unknown, expired or already used, or the transmission has no certificate."""


class SecretsMismatch(SecretsExpired):
	"""Certificate and password were entered by another user or for another document; they are gone now."""


def stash(certificate_secret: bytes, password: str, *, user: str, document: tuple[str, str]) -> str:
	"""Keep certificate and password for one transmission of the document by the user; the token is all the
	request that starts it gets."""
	import frappe
	from frappe.utils.password import encrypt

	token = token_urlsafe(32)
	payload_secret = Sealed(
		json.dumps(
			{
				"certificate_secret": base64.b64encode(certificate_secret).decode(),
				"password": password,
				"user": user,
				"document": list(document),
			}
		).encode()
	)
	# Not set_value: it would keep the value in the cache of the request as well, and pickle it. The key
	# carries the site prefix of make_key, which is what set_value would add.
	key, encrypted_secret = _key(KEY.format(token=token)), encrypt(payload_secret)
	frappe.cache.set(key, encrypted_secret, ex=TTL_SECONDS)  # nosemgrep: frappe-cache-breaks-multitenancy
	return token


def hand_over(token: str, transmission: str, *, user: str, document: tuple[str, str]) -> None:
	"""Move what the token keeps to the transmission, if the user starts it for the document they were entered
	for; SecretsMismatch otherwise, and SecretsExpired for a token that is unknown, expired or used. Either way the
	token is used up."""
	import frappe

	if not isinstance(token, str) or not _TOKEN.fullmatch(token):
		raise SecretsExpired("not a token of steuerbote.eric.secrets")
	key = _key(KEY.format(token=token))
	pipeline = frappe.cache.pipeline()
	pipeline.ttl(key)
	pipeline.getdel(key)
	seconds, stored_secret = pipeline.execute()
	if stored_secret is None:
		raise SecretsExpired("certificate and password are gone: expired or already taken")
	_unsealed(stored_secret, user, document)
	frappe.cache.set(  # nosemgrep: frappe-cache-breaks-multitenancy
		_key(HANDED_OVER.format(transmission=transmission)),
		stored_secret,
		ex=seconds if 0 < seconds <= TTL_SECONDS else TTL_SECONDS,
	)


def take(transmission: str, *, user: str, document: tuple[str, str]) -> tuple[bytes, str]:
	"""Certificate and password handed over to the transmission, once, for its user and document; SecretsExpired
	the second time and after their 15 minutes."""
	import frappe

	stored_secret = frappe.cache.getdel(_key(HANDED_OVER.format(transmission=transmission)))
	if stored_secret is None:
		raise SecretsExpired("certificate and password are gone: expired or already taken")
	return _unsealed(stored_secret, user, document)


def discard(transmission: str) -> None:
	"""Drop what was handed over to a transmission whose job will not run."""
	import frappe

	frappe.cache.delete(_key(HANDED_OVER.format(transmission=transmission)))


def _unsealed(stored_secret: bytes, user: str, document: tuple[str, str]) -> tuple[bytes, str]:
	from frappe.utils.password import decrypt

	decrypted_secret = decrypt(stored_secret.decode())
	try:
		payload_secret = json.loads(decrypted_secret)
		certificate_secret = base64.b64decode(payload_secret["certificate_secret"], validate=True)
		password = payload_secret["password"]
		entered = (payload_secret["user"], tuple(payload_secret["document"]))
	except ValueError, KeyError, TypeError:
		# from None keeps the frames of json and base64 out of the traceback: they hold the plain text.
		raise SecretsExpired("certificate and password are unreadable") from None
	if entered != (user, tuple(document)):
		raise SecretsMismatch("certificate and password were entered by another user or for another document")
	return certificate_secret, password


def _key(name: str) -> bytes:
	import frappe

	return frappe.cache.make_key(name)
