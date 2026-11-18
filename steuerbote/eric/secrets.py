"""One-shot hand-over of certificate and PIN from the request to the background job that sends.

The arguments of a background job stay in Redis for days and show in the list of RQ Jobs, so certificate
and PIN never become job arguments. The request stashes them encrypted with the site's encryption key
(frappe.utils.password.encrypt, Fernet) in the Redis cache under a random token, for 15 minutes at most;
the job gets only the token and takes them with GETDEL, so they can be read once. Nothing is written to
the database, a file or a log.

This is the only module of steuerbote.eric that uses Frappe; it imports Frappe inside its functions.
"""

import base64
import json
import re
from secrets import token_urlsafe

TTL_SECONDS = 15 * 60
KEY = "steuerbote:eric:secret:{token}"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")


class SecretsExpired(Exception):
	"""The token is unknown, expired or already used."""


def stash(certificate: bytes, password: str) -> str:
	"""Keep certificate and password for one background job; the token is all the job may receive."""
	import frappe
	from frappe.utils.password import encrypt

	token = token_urlsafe(32)
	payload = json.dumps({"certificate": base64.b64encode(certificate).decode(), "password": password})
	frappe.cache.set(_key(token), encrypt(payload), ex=TTL_SECONDS)
	return token


def take(token: str) -> tuple[bytes, str]:
	"""Certificate and password kept under the token; SecretsExpired the second time and after 15 minutes."""
	import frappe
	from frappe.utils.password import decrypt

	if not isinstance(token, str) or not _TOKEN.fullmatch(token):
		raise SecretsExpired("not a token of steuerbote.eric.secrets")
	stored = frappe.cache.getdel(_key(token))
	if stored is None:
		raise SecretsExpired("certificate and password are gone: expired or already taken")
	data = json.loads(decrypt(stored.decode()))
	return base64.b64decode(data["certificate"]), data["password"]


def _key(token: str) -> bytes:
	import frappe

	return frappe.cache.make_key(KEY.format(token=token))
