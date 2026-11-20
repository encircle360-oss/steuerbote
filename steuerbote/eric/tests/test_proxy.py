from unittest import TestCase

from steuerbote.eric import proxy
from steuerbote.eric.proxy import Proxy, ProxyError, parse

# The password of the proxy, invented.
GEHEIM = "Proxy-Geheim-2026"


class ParseTest(TestCase):
	def test_an_http_proxy_gives_host_and_port(self):
		self.assertEqual(parse("http://proxy.example.com:3128"), Proxy("proxy.example.com", 3128))
		self.assertEqual(parse(" HTTP://Proxy.Example.com:3128/ "), Proxy("proxy.example.com", 3128))

	def test_socks_keeps_its_protocol_in_front_of_the_host(self):
		"""„Der Protokollname ist dem Hostname voranzustellen, z. B.: socks4://mein.proxy.xy“ (Tabelle 4-2)."""
		self.assertEqual(parse("socks4://proxy.example.com:1080").host, "socks4://proxy.example.com")
		self.assertEqual(parse("socks5://10.0.0.1:1080"), Proxy("socks5://10.0.0.1", 1080))

	def test_an_ip_address_of_version_6_keeps_its_brackets(self):
		self.assertEqual(parse("http://[2001:db8::1]:3128").host, "[2001:db8::1]")

	def test_the_port_is_required(self):
		"""Without the port, sending fails with ERIC_TRANSFER_ERR_PROXYPORT_INVALID (Tabelle 4-2)."""
		with self.assertRaises(ProxyError) as raised:
			parse("http://proxy.example.com")
		self.assertEqual(raised.exception.template, proxy.NO_PORT)

	def test_refuses_what_is_no_proxy_url_of_eric(self):
		for url in (
			"proxy.example.com:3128",
			"https://proxy.example.com:3128",
			"socks5h://proxy.example.com:1080",
			"http://proxy.example.com:3128/pfad",
			"http://proxy.example.com:3128?a=1",
			"http://proxy.example.com:3128#a",
			"http://:3128",
			"http://proxy.example.com:70000",
			"http://proxy.example.com:port",
		):
			with self.subTest(url=url), self.assertRaises(ProxyError) as raised:
				parse(url)
			self.assertEqual(
				(raised.exception.template, raised.exception.values), (proxy.NOT_A_PROXY_URL, (url.strip(),))
			)

	def test_user_and_password_go_apart_from_the_url(self):
		with self.assertRaises(ProxyError) as raised:
			parse(f"http://steuerbote:{GEHEIM}@proxy.example.com:3128")
		self.assertEqual(raised.exception.template, proxy.CREDENTIALS_IN_URL)
		self.assertNotIn(GEHEIM, str(raised.exception))

	def test_user_and_password_come_together(self):
		self.assertEqual(
			parse("http://proxy.example.com:3128", " steuerbote ", GEHEIM),
			Proxy("proxy.example.com", 3128, "steuerbote", GEHEIM),
		)
		for username, password in (("steuerbote", None), (None, GEHEIM), ("  ", GEHEIM)):
			with self.subTest(username=username), self.assertRaises(ProxyError) as raised:
				parse("http://proxy.example.com:3128", username, password)
			self.assertEqual(raised.exception.template, proxy.INCOMPLETE_CREDENTIALS)

	def test_socks_takes_no_authentication(self):
		"""„Das SOCKS4- und SOCKS5-Protokoll ohne Authentifizierung wird unterstützt.“ (Tabelle 4-2)"""
		with self.assertRaises(ProxyError) as raised:
			parse("socks5://proxy.example.com:1080", "steuerbote", GEHEIM)
		self.assertEqual(raised.exception.template, proxy.SOCKS_WITH_CREDENTIALS)

	def test_every_message_is_listed_for_its_translation(self):
		self.assertEqual(
			set(proxy.MESSAGES),
			{
				proxy.NOT_A_PROXY_URL,
				proxy.NO_PORT,
				proxy.CREDENTIALS_IN_URL,
				proxy.INCOMPLETE_CREDENTIALS,
				proxy.SOCKS_WITH_CREDENTIALS,
			},
		)


class SettingsTest(TestCase):
	def test_names_the_api_settings_of_eric_for_the_proxy(self):
		"""http.proxy_host, http.proxy_port, http.proxy_username and http.proxy_password (Tabelle 4-2)."""
		self.assertEqual(
			Proxy("proxy.example.com", 3128).settings(),
			(("http.proxy_host", "proxy.example.com"), ("http.proxy_port", "3128")),
		)
		self.assertEqual(
			Proxy("proxy.example.com", 3128, "steuerbote", GEHEIM).settings(),
			(
				("http.proxy_host", "proxy.example.com"),
				("http.proxy_port", "3128"),
				("http.proxy_username", "steuerbote"),
				("http.proxy_password", GEHEIM),
			),
		)

	def test_the_password_never_shows_in_its_representation(self):
		self.assertNotIn(GEHEIM, repr(Proxy("proxy.example.com", 3128, "steuerbote", GEHEIM)))


class DictionaryTest(TestCase):
	def test_crosses_the_process_boundary_as_json_values(self):
		for value in (
			Proxy("proxy.example.com", 3128),
			Proxy("socks5://10.0.0.1", 1080),
			Proxy("p", 0, "u", "p"),
		):
			with self.subTest(proxy=value):
				self.assertEqual(Proxy.from_dict(value.to_dict()), value)

	def test_refuses_anything_of_another_shape(self):
		valid = Proxy("proxy.example.com", 3128, "steuerbote", GEHEIM).to_dict()
		for case, data in {
			"no object": ["proxy.example.com", 3128],
			"host": valid | {"host": ""},
			"port type": valid | {"port": "3128"},
			"port flag": valid | {"port": True},
			"port range": valid | {"port": 65536},
			"username": valid | {"username": 7},
			"password": valid | {"password": 7},
			"user without password": valid | {"password": None},
		}.items():
			with self.subTest(case), self.assertRaises(ValueError) as raised:
				Proxy.from_dict(data)
			self.assertNotIn(GEHEIM, str(raised.exception))
