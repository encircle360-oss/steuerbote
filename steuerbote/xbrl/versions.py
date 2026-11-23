"""The versions of the HGB-Taxonomie Steuerbote writes, and the fiscal years each of them serves.

The E-Bilanz is transmitted „nach amtlich vorgeschriebenem Datensatz“ (§ 5b Abs. 1 EStG), and the BMF publishes a
version of the taxonomy each year as that Datensatz: „Hiermit wird das aktualisierte Datenschema der Taxonomien
(Version 6.9) als amtlich vorgeschriebener Datensatz nach § 5b EStG veröffentlicht.“ (BMF letter of 10 June 2025, GZ
IV C 6 - S 2133-b/00064/002/006, BStBl I S. 1450). A version is a set of data, which TAXONOMIES keeps per version:

- the letter that publishes it, with the fiscal years it is for: „Die Taxonomien sind grundsätzlich für die Bilanzen
  der Wirtschaftsjahre zu verwenden, die nach dem 31. Dezember 2025 beginnen (Wirtschaftsjahr 2026 oder 2026/2027).
  ... Es wird nicht beanstandet, wenn diese auch für das Wirtschaftsjahr 2025 oder 2025/2026 verwendet werden.“;
- the last fiscal years it may serve: „Taxonomie letztmalig zu verwenden für Wirtschaftsjahre, die vor dem 31.12.
  xxxx enden“, 2027 for 6.9, and the day ERiC sends real cases with it, 26.05.2026 („Übersicht über die Verwendung
  der Taxonomie-Versionen für die Übermittlung der E-Bilanz an die Finanzverwaltung“, Stand 03.06.2026, on
  www.esteuer.de);
- the package esteuer.de publishes, with its SHA-256, which the operator downloads and names in
  common_site_config.json of the bench (steuerbote_taxonomy_6_9 and steuerbote_taxonomy_6_9_sha256), since the
  files say only „(c) XBRL Deutschland e.V. - see http://www.xbrl.de“ and no licence allows passing them on;
- the modules, named after the date of the taxonomy: the GCD module for the master data and the GAAP module of the
  Kerntaxonomie, „Kerntaxonomie (de-gaap-ci) für branchenunabhängige Anwendungen“ (Technischer Leitfaden zur
  HGB-Taxonomie 6.9, Stand 10.06.2025, A.2), with their entry points (A.5). For the E-Bilanz „ist immer genau eines
  zusammen mit dem Einstiegsschema für die GCD, „de-gcd-2025-04-01-shell.xsd", zu referenzieren“, the fiscal one
  de-gaap-ci-2025-04-01-shell-fiscal.xsd (B.3). The Unternehmensregister takes the commercial ones,
  de-gaap-ci-2025-04-01 (Einzelabschluss) and de-gaap-ci-2025-04-01-microbilg (Einzelabschluss MicroBilG), each with
  de-gcd-2025-04-01, and has offered 6.9 since 15.10.2025 („Arbeitshilfe für die Einreichung von
  Jahresabschlüssen/Finanzberichten im XBRL-Format“, Stand September 2025; notice „Neue XBRL-Taxonomie für
  Jahresabschlüsse“ on www.publikations-plattform.de);
- the Datenart of ERiC, Bilanz_6.9 with the plugin checkBilanz_6_9 (steuerbote/eric/datenart.py).

Documents reference the taxonomy by absolute URLs under http://www.xbrl.de/taxonomies/ (Leitfaden A.6), which the
server of XBRL Deutschland does not serve; a validator reads the operator's copy for them.

An Eröffnungsbilanz takes „eine der Taxonomieversionen ..., mit der auch die Schlussbilanz des ersten
Wirtschaftsjahres übermittelt werden kann“ (Übersicht über die Verwendung der Taxonomie-Versionen), so its version
is the one of the first fiscal year: for_fiscal_year() of that year.

Taxonomy 6.10 (BMF letter of 8 June 2026) comes as a second entry once ERiC 46 sends real cases with it in May 2027;
until then 6.9 is the only version of WJ 2026 that can be filed. Every table keyed by the version holds exactly the
versions of TAXONOMIES (steuerbote/xbrl/tests/test_versions.py).
"""

from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from steuerbote.eric.datenart import Datenart, bilanz
from steuerbote.ustva.years import MONTHS

BASE_URL = "http://www.xbrl.de/taxonomies/"
"""The prefix of the absolute URLs of the documents of the taxonomy (Technischer Leitfaden 6.9, A.6)."""
CONFIG_PREFIX = "steuerbote_taxonomy_"


class UnknownTaxonomyError(ValueError):
	"""Steuerbote knows no version of the taxonomy for the case."""


@dataclass(frozen=True, slots=True)
class Version:
	"""A version of the HGB-Taxonomie with the letter that publishes it and the fiscal years it serves."""

	version: str
	"""Such as 6.9."""
	released: date
	"""The date of the taxonomy, which its modules carry in their names."""
	letter_date: date
	reference: str
	"""The Geschäftszeichen (GZ) of the letter."""
	bstbl: str
	begins_after: date
	"""A fiscal year beginning after this day takes the version."""
	tolerated_begins_after: date
	"""A fiscal year beginning after this day may take the version, „nicht beanstandet“."""
	last_ends_before: date
	"""The version serves only fiscal years ending before this day."""
	real_cases_from: date
	"""From this day ERiC sends real cases of the version."""
	register_since: date
	"""From this day the Unternehmensregister takes the version."""
	archive_url: str
	archive_sha256: str

	@property
	def letter(self) -> str:
		"""The letter as the docstrings cite it."""
		day = self.letter_date
		return (
			f"BMF letter of {day.day} {MONTHS[day.month - 1]} {day.year} (GZ {self.reference}, {self.bstbl})"
		)

	@property
	def archive_name(self) -> str:
		return self.archive_url.rsplit("/", 1)[1]

	@property
	def gcd(self) -> str:
		"""The GCD module (Global Common Data), such as de-gcd-2025-04-01."""
		return f"de-gcd-{self.released.isoformat()}"

	@property
	def gaap(self) -> str:
		"""The GAAP module of the Kerntaxonomie, such as de-gaap-ci-2025-04-01."""
		return f"de-gaap-ci-{self.released.isoformat()}"

	@property
	def gcd_namespace(self) -> str:
		return f"{BASE_URL}{self.gcd}"

	@property
	def gaap_namespace(self) -> str:
		return f"{BASE_URL}{self.gaap}"

	@property
	def gcd_shell(self) -> str:
		"""The entry point of the GCD, by its path in the package."""
		return f"{self.gcd}/{self.gcd}-shell.xsd"

	@property
	def fiscal_shell(self) -> str:
		"""The entry point of the E-Bilanz, „GAAP steuerlicher Einzelabschluss“ (Leitfaden A.5, B.3)."""
		return f"{self.gaap}/{self.gaap}-shell-fiscal.xsd"

	@property
	def commercial_shell(self) -> str:
		"""The entry point of the Einzelabschluss of the commercial view, for the Offenlegung of a small company."""
		return f"{self.gaap}/{self.gaap}-shell.xsd"

	@property
	def microbilg_shell(self) -> str:
		"""The entry point of the Einzelabschluss MicroBilG, for the Offenlegung of a Kleinstkapitalgesellschaft."""
		return f"{self.gaap}/{self.gaap}-shell-microbilg.xsd"

	def url(self, path: str) -> str:
		"""The absolute URL a document references a file of the package by (Leitfaden A.6)."""
		return f"{BASE_URL}{path}"

	@property
	def datenart(self) -> Datenart:
		return bilanz(self.version)

	@property
	def config_key(self) -> str:
		"""The key of common_site_config.json that names the package on the server."""
		return CONFIG_PREFIX + self.version.replace(".", "_")

	@property
	def config_sha256_key(self) -> str:
		return f"{self.config_key}_sha256"

	def allows(self, begin: date, end: date) -> bool:
		"""Whether a fiscal year from begin to end may take the version."""
		return self.tolerated_begins_after < begin and end < self.last_ends_before

	def is_default_for(self, begin: date, end: date) -> bool:
		"""Whether a fiscal year from begin to end takes the version „grundsätzlich“."""
		return self.begins_after < begin and end < self.last_ends_before


TAXONOMIES: MappingProxyType[str, Version] = MappingProxyType(
	{
		"6.9": Version(
			version="6.9",
			released=date(2025, 4, 1),
			letter_date=date(2025, 6, 10),
			reference="IV C 6 - S 2133-b/00064/002/006",
			bstbl="BStBl I S. 1450",
			begins_after=date(2025, 12, 31),
			tolerated_begins_after=date(2024, 12, 31),
			last_ends_before=date(2027, 12, 31),
			real_cases_from=date(2026, 5, 26),
			register_since=date(2025, 10, 15),
			archive_url=(
				"https://www.esteuer.de/download/taxonomie_20250618/german-gaap-taxonomy-v6.9-2025-04-01-xbrl.zip"
			),
			archive_sha256="accd62202d73c036910fee118b30730f0392934afc9730617788e30a0480df87",
		),
	}
)
LATEST = TAXONOMIES[max(TAXONOMIES, key=lambda version: tuple(int(part) for part in version.split(".")))]


def version_of(version: str) -> Version:
	"""The entry of a version, such as 6.9."""
	try:
		return TAXONOMIES[version]
	except KeyError:
		known = ", ".join(TAXONOMIES)
		raise UnknownTaxonomyError(f"Steuerbote knows no HGB-Taxonomie {version}; known: {known}") from None


def allowed_for(begin: date, end: date) -> tuple[Version, ...]:
	"""The versions a fiscal year from begin to end may take, by the letters that publish them."""
	_require_fiscal_year(begin, end)
	return tuple(entry for entry in TAXONOMIES.values() if entry.allows(begin, end))


def for_fiscal_year(begin: date, end: date) -> Version:
	"""The version a fiscal year from begin to end takes „grundsätzlich“: the newest whose letter names it."""
	_require_fiscal_year(begin, end)
	defaults = [entry for entry in TAXONOMIES.values() if entry.is_default_for(begin, end)]
	if not defaults:
		raise UnknownTaxonomyError(
			f"Steuerbote knows no HGB-Taxonomie for the fiscal year {begin.isoformat()} to {end.isoformat()}; "
			f"known: {', '.join(TAXONOMIES)}"
		)
	return defaults[-1]


def _require_fiscal_year(begin: date, end: date) -> None:
	if end < begin:
		raise ValueError(
			f"a fiscal year ends after it begins, not on {end.isoformat()} before {begin.isoformat()}"
		)
