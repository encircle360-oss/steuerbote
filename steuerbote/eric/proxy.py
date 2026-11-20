"""The proxy through which ERiC reaches the ELSTER servers.

ERiC takes a proxy as API settings of EricEinstellungSetzen (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 4.1.2.2,
Tabelle 4-2), set after EricInitialisiere and before the call that sends (Kap. 6.2.4, step 2), for the instance
of ERiC they are set on (Kap. 5.3.14):

- http.proxy_host: „IP-Adresse oder Hostname des Proxys. Das SOCKS4- und SOCKS5-Protokoll ohne
  Authentifizierung wird unterstützt. Der Protokollname ist dem Hostname voranzustellen, z. B.:
  socks4://mein.proxy.xy“
- http.proxy_port, 0 to 65535: „Proxy-Port muss angegeben werden, falls http.proxy_host gesetzt wurde,
  andernfalls schlägt der Versand mit dem Rückgabecode ERIC_TRANSFER_ERR_PROXYPORT_INVALID fehl.“
- http.proxy_username and http.proxy_password for the authentication at the proxy; http.proxy_auth keeps its
  default Any.

The operator names the proxy as a URL, http://host:port, socks4://host:port or socks5://host:port, and user and
password apart, so that the password is kept encrypted. This module is pure Python and never imports Frappe.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

SCHEMES = ("http", "socks4", "socks5")
SOCKS = ("socks4", "socks5")
MAX_PORT = 65535

NOT_A_PROXY_URL = "{0} is no proxy URL: ERiC takes http://, socks4:// or socks5:// with a host and a port."
NO_PORT = "The proxy URL needs the port of the proxy, such as http://proxy.example.com:3128."
CREDENTIALS_IN_URL = "Enter the user and the password of the proxy in their own fields, not in the URL."
INCOMPLETE_CREDENTIALS = "The proxy takes a user only with a password, and a password only with a user."
SOCKS_WITH_CREDENTIALS = "ERiC takes a SOCKS proxy only without user and password."
MESSAGES = (NOT_A_PROXY_URL, NO_PORT, CREDENTIALS_IN_URL, INCOMPLETE_CREDENTIALS, SOCKS_WITH_CREDENTIALS)


class ProxyError(ValueError):
	"""A proxy ERiC cannot use; ``template`` and ``values`` make the message, so that a caller can translate it."""

	def __init__(self, template: str, *values: object) -> None:
		super().__init__(template.format(*values))
		self.template = template
		self.values = values


@dataclass(frozen=True, slots=True)
class Proxy:
	"""The proxy as the settings of ERiC take it: the host, with its protocol for SOCKS, the port, and user and
	password together or neither. The password never shows in the representation."""

	host: str
	port: int
	username: str | None = None
	password: str | None = field(default=None, repr=False)

	def __post_init__(self) -> None:
		if not (isinstance(self.host, str) and self.host):
			raise ValueError("the host of a proxy is a text")
		if not (
			isinstance(self.port, int) and not isinstance(self.port, bool) and 0 <= self.port <= MAX_PORT
		):
			raise ValueError(f"the port of a proxy is a number from 0 to {MAX_PORT}")
		for name in ("username", "password"):
			if not isinstance(getattr(self, name), str | None):
				raise ValueError(f"the {name} of a proxy is a text")
		if (self.username is None) != (self.password is None):
			raise ValueError("a proxy takes a user and a password together")

	def settings(self) -> tuple[tuple[str, str], ...]:
		"""The API settings of ERiC for this proxy, as EricEinstellungSetzen takes them."""
		settings = (("http.proxy_host", self.host), ("http.proxy_port", str(self.port)))
		if self.username is None:
			return settings
		return (*settings, ("http.proxy_username", self.username), ("http.proxy_password", self.password))

	def to_dict(self) -> dict[str, str | int | None]:
		return {"host": self.host, "port": self.port, "username": self.username, "password": self.password}

	@classmethod
	def from_dict(cls, data: object) -> Proxy:
		if not isinstance(data, Mapping):
			raise ValueError("a proxy is a JSON object")
		return cls(data.get("host"), data.get("port"), data.get("username"), data.get("password"))


def parse(url: str, username: str | None = None, password: str | None = None) -> Proxy:
	"""The proxy of a URL and the user and password entered apart; ProxyError if ERiC cannot use it."""
	text = url.strip()
	# Before anything echoes the URL: a user and a password in it would show in the message.
	if "@" in text:
		raise ProxyError(CREDENTIALS_IN_URL)
	try:
		parts = urlsplit(text)
		port = parts.port
	except ValueError:
		raise ProxyError(NOT_A_PROXY_URL, text) from None
	scheme = parts.scheme
	if (
		scheme not in SCHEMES
		or not parts.hostname
		or parts.path not in ("", "/")
		or parts.query
		or parts.fragment
	):
		raise ProxyError(NOT_A_PROXY_URL, text)
	if port is None:
		raise ProxyError(NO_PORT)
	user = (username or "").strip() or None
	if (user is None) != (not password):
		raise ProxyError(INCOMPLETE_CREDENTIALS)
	if user is not None and scheme in SOCKS:
		raise ProxyError(SOCKS_WITH_CREDENTIALS)
	host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
	return Proxy(f"{scheme}://{host}" if scheme in SOCKS else host, port, user, password or None)
