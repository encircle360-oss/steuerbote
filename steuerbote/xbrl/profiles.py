"""The two reports Steuerbote writes on the HGB-Taxonomie: the E-Bilanz and the Offenlegung of the Jahresabschluss.

Both take the facts of steuerbote/xbrl/facts.py, which their modules build from the same Bilanzzuordnung, and the
writer of steuerbote/xbrl/writer.py. A profile names the views of steuerbote/xbrl/taxonomy.py a report may reference
and the checks of steuerbote/xbrl/checks.py its content passes:

- FISCAL, the E-Bilanz (§ 5b EStG), in the view of de-gaap-ci-2025-04-01-shell-fiscal.xsd, „GAAP steuerlicher
  Einzelabschluss“, with the GCD: of the entry points of the GAAP module „ist immer genau eines zusammen mit dem
  Einstiegsschema für die GCD ... zu referenzieren“ (Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025,
  A.5, B.3). It serves every size; the fiscal entry point of the MicroBilG is not one Steuerbote writes. Its content
  is what the GCD announces, with the Mussfelder valid for the legal form, NIL where the books cannot fill them, the
  Kontensalden, the Betriebsvermögensvergleich, the Anlagenspiegel and, for a Handelsbilanz, the Überleitung; a
  Steuerbilanz has no previous year. The checks: the components (B.9.2), the Mussfelder (B.14.2), the positions
  admissible for the Finanzverwaltung (B.4.2, B.11, B.14.3.1.15, B.14.4.1, B.14.6), the previous year (B.8.3), the
  calculation linkbase (B.14.11), the Oberpositionen (B.14.10), the Summenmussfelder (B.14.14) and the contexts
  (B.14.7).
- DISCLOSURE, the Offenlegung (§§ 325, 326 HGB) of a small company or a Kleinstkapitalgesellschaft: the views of
  „de-gaap-ci-2025-04-01 ... Einzelabschluss“ and, for a Kleinstkapitalgesellschaft, „de-gaap-ci-2025-04-01-microbilg
  ... Einzelabschluss MicroBilG“, each with de-gcd-2025-04-01 („Arbeitshilfe für die Einreichung von
  Jahresabschlüssen/Finanzberichten im XBRL-Format“ of the Unternehmensregister, Stand September 2025). Its content is
  what the company publishes and no more: the positions of the levels its class shows (§ 266 Abs. 1 Satz 3 und 4 HGB),
  which the caller names, as steuerbote/hgb/schemes.py gives them, since the register shows every position reported;
  no Kontensalden, which would publish the balance of each account; each Posten for both closing dates (§ 265 Abs. 2
  HGB). The checks: the positions admissible in a Handelsbilanz, „handelsrechtlich“ not permitted (A.9.2), what the
  class publishes, both closing dates, the calculation linkbase, the Oberpositionen, which the register shows with each
  position, and the contexts. The Mussfelder and the components are those of the „Taxonomie Steuer“ (B.14.2), and
  which data of the GCD the register needs is unverified, so the Offenlegung asks for neither.

check() writes the instance to check its contexts, so a report the writer refuses raises its WriterError. A report or
taxonomy of another profile raises a ProfileError. This module is pure Python and never imports Frappe.
"""

from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass, field

from steuerbote.xbrl import checks, writer
from steuerbote.xbrl.checks import Facets, Finding
from steuerbote.xbrl.facts import Entity, Fact, Periods, Report
from steuerbote.xbrl.taxonomy import NOT_PERMITTED_COMMERCIAL, Taxonomy, View


class ProfileError(ValueError):
	"""The report or the taxonomy is not one of the profile."""


type _Checks = Callable[[Report, Taxonomy, Collection[str] | None], tuple[Finding, ...]]


@dataclass(frozen=True, slots=True)
class Profile:
	"""A kind of report: the views it references and the checks its content passes."""

	name: str
	label: str
	views: tuple[View, ...]
	_checks: _Checks = field(repr=False, compare=False)

	def view(self, *, kleinst: bool = False) -> View:
		"""The view of a report, the last one for a Kleinstkapitalgesellschaft."""
		return self.views[-1] if kleinst else self.views[0]

	def report(
		self,
		taxonomy: Taxonomy,
		entity: Entity,
		periods: Periods,
		facts: Iterable[Fact],
		*,
		monetary_decimals: int = 2,
	) -> Report:
		"""The report of the facts, referencing the entry points of the view of the taxonomy."""
		self._require_view(taxonomy)
		return Report(entity, periods, writer.entry_points(taxonomy), tuple(facts), monetary_decimals)

	def check(
		self, report: Report, taxonomy: Taxonomy, *, published: Collection[str] | None = None
	) -> tuple[Finding, ...]:
		"""The findings of the checks of the profile in their order; ``published`` names, for the Offenlegung only, the
		concepts the class of the company shows."""
		self._require_view(taxonomy)
		if report.schema_refs != writer.entry_points(taxonomy):
			raise ProfileError(f"the report references the entry points of another view than {taxonomy.view}")
		return self._checks(report, taxonomy, published)

	def _require_view(self, taxonomy: Taxonomy) -> None:
		if taxonomy.view not in self.views:
			raise ProfileError(
				f"the {self.label} takes the view {' or '.join(self.views)}, not {taxonomy.view}"
			)


def _fiscal(report: Report, taxonomy: Taxonomy, published: Collection[str] | None) -> tuple[Finding, ...]:
	if published is not None:
		raise ProfileError(
			"the E-Bilanz is filed, not published: only the Offenlegung names what it publishes"
		)
	facets = Facets.of(report)
	return (
		*checks.components(report, taxonomy, facets),
		*checks.mussfelder(report, taxonomy, facets),
		*checks.admissibility(report, taxonomy, facets),
		*checks.prior_year(report, taxonomy, facets),
		*checks.calculation(report, taxonomy),
		*checks.oberpositionen(report, taxonomy),
		*checks.summenmussfelder(report, taxonomy),
		*checks.contexts(writer.instance(report, taxonomy)),
	)


def _disclosure(report: Report, taxonomy: Taxonomy, published: Collection[str] | None) -> tuple[Finding, ...]:
	if published is None:
		raise ProfileError("the Offenlegung names the concepts its class shows")
	return (
		*checks.admissibility(report, taxonomy, Facets.of(report), purposes=(NOT_PERMITTED_COMMERCIAL,)),
		*checks.published(report, taxonomy, published),
		*checks.closing_dates(report, taxonomy),
		*checks.calculation(report, taxonomy),
		*checks.oberpositionen(report, taxonomy),
		*checks.contexts(writer.instance(report, taxonomy)),
	)


FISCAL = Profile("fiscal", "E-Bilanz", (View.FISCAL,), _fiscal)
DISCLOSURE = Profile("disclosure", "Offenlegung", (View.COMMERCIAL, View.COMMERCIAL_MICROBILG), _disclosure)
PROFILES = (FISCAL, DISCLOSURE)
