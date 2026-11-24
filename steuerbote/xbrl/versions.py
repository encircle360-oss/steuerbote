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

Taxonomy 6.10 is published by the BMF letter of 8 June 2026 (GZ IV C 6 - S 2133-b/00067/002/023, DOK
COO.7005.100.4.14979781): „Die Taxonomien sind grundsätzlich für die Bilanzen der Wirtschaftsjahre zu verwenden, die
nach dem 31. Dezember 2026 beginnen (Wirtschaftsjahr 2027 oder 2027/2028). ... Es wird nicht beanstandet, wenn diese
auch für das Wirtschaftsjahr 2026 oder 2026/2027 verwendet werden. Die Übermittlungsmöglichkeiten mit diesen neuen
Taxonomien wird für Testfälle voraussichtlich ab November 2026 und für Echtfälle ab Mai 2027 gegeben sein.“ The letter is
to be printed in the BStBl I without a page yet, so its DOK stands for it. The Übersicht über die Verwendung der
Taxonomie-Versionen (Stand 03.06.2026) gives 6.10 the fiscal years ending before 31.12.2028, ERiC 45 for test cases and
ERiC 46 for real cases, and ERiC 45.1.5.0 has the plugin checkBilanz_6_10 „mit Testmerkerpflicht“ (ERiC-Releasenotes
45.1.5.0, Kap. 3.1.8). 6.9 stays the taxonomy of WJ 2026: until May 2027 it is the only one with which an E-Bilanz of
2026 can be filed. Every table keyed by the version holds exactly the versions of TAXONOMIES
(steuerbote/xbrl/tests/test_versions.py), and FIRST is the version a new Bilanzzuordnung names.
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
	"""Where the letter is printed, BStBl I S. … once the Bundessteuerblatt has it, else its DOK."""
	begins_after: date
	"""A fiscal year beginning after this day takes the version."""
	tolerated_begins_after: date
	"""A fiscal year beginning after this day may take the version, „nicht beanstandet“."""
	last_ends_before: date
	"""The version serves only fiscal years ending before this day."""
	real_cases_from: date
	"""From this day ERiC sends real cases of the version."""
	register_since: date | None
	"""From this day the Unternehmensregister takes the version, None while it has announced no day."""
	archive_url: str
	archive_sha256: str
	kontensalden_reason: bool = False
	"""Whether an E-Bilanz of the version may leave the Kontensalden out with the reason in
	genInfo.report.id.reportElement.reportElements.transmissionNotYetPossible, which only 6.9 allows: „Um Härtefälle zu
	vermeiden, wird es für die Übermittlung von E-Bilanzen mit der Taxonomie-Version 6.9 nicht beanstandet, wenn ... die
	Bilanz und GuV ohne Kontennachweise ... übermittelt werden.“ (BMF letter of 10 June 2025), and 6.10 deletes the
	position: „Die Übergangsregelung war ausschließlich auf die Taxonomie-Version 6.9 anwendbar“ (Änderungsnachweis zum
	Taxonomie-Update 2026, Taxonomie 6.10/6.9, 2.)."""

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
			kontensalden_reason=True,
		),
		"6.10": Version(
			version="6.10",
			released=date(2026, 4, 1),
			letter_date=date(2026, 6, 8),
			reference="IV C 6 - S 2133-b/00067/002/023",
			bstbl="DOK COO.7005.100.4.14979781",
			begins_after=date(2026, 12, 31),
			tolerated_begins_after=date(2025, 12, 31),
			last_ends_before=date(2028, 12, 31),
			# „für Echtfälle ab Mai 2027“ names no day, so the first of the month stands for it.
			real_cases_from=date(2027, 5, 1),
			register_since=None,
			archive_url=(
				"https://www.esteuer.de/download/taxonomie_20260615/germany-gaap-taxonomy-v6.10-2026-04-01-xbrl.zip"
			),
			archive_sha256="de00ceaad0e532d238dea24a48160ec335422a3a71c38dd03c7b2b34b32fff76",
		),
	}
)
LATEST = TAXONOMIES[max(TAXONOMIES, key=lambda version: tuple(int(part) for part in version.split(".")))]
FIRST = TAXONOMIES["6.9"]
"""The version of the fiscal year 2026, the first Steuerbote files (FIRST_ANNUAL_YEAR of steuerbote/eric/releases.py):
a new Bilanzzuordnung names its positions, and „Auf neue Taxonomie heben“ lifts it to a later version
(steuerbote/xbrl/changes.py)."""


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
