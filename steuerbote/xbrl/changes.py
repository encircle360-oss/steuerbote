"""What a version of the HGB-Taxonomie changes against the one before, and „Auf neue Taxonomie heben“: a
Bilanzzuordnung on the positions of one version lifted to those of a later one.

Changes. CHANGES holds for every version of steuerbote/xbrl/versions.py but the first what it changes against the one
before, named with the prefixes of the modules (de-gaap-ci, de-gcd):

- renamed: a concept the later version names otherwise. XBRL Deutschland ships with each package the versioning
  reports of XBRL Versioning 1.0 against the version before, such as versioning/de-gaap-ci-2026-04-01/
  de-gaap-ci-2026-04-01-shell-fiscal-with-2025-04-01-versioning.xml of the package 6.10, whose conceptRename keep the
  local name of every concept of the GAAP and the GCD module: only the namespace of the module moves, from
  2025-04-01 to 2026-04-01, which the names of the Bilanzzuordnung do not carry. 6.10 renames none.
- removed and added: the concepts the package of the version has no more and those it has new, by the views of the
  loader (steuerbote/xbrl/taxonomy.py), which name the same concepts in each view. 6.10 removes 43 and adds 39: „Positionen,
  deren Gültigkeitsdatum mehr als fünf Jahre in der Vergangenheit liegt (< 31.12.2021), wurden mit den zugehörigen
  Referenzen entfernt.“, „Die Position „Erläuterung, warum die Übermittlung der Kontennachweise noch nicht möglich
  ist“ ... wurde gelöscht.“, the Einzahlungsverpflichtungen of the partners moved and their Oberposition and
  Auffangposition deleted, the Zurechnungen nach § 4j EStG deleted; „Konto nicht vorhanden oder nicht übermittelbar“
  [detailedInformation.accountbalances.notPossible], the Grundsteuer, the Verzeichnisse nach § 5 Abs. 1 Satz 2 and
  § 5a Abs. 4 EStG and others new (Änderungsnachweis zum Taxonomie-Update 2026, Taxonomie 6.10/6.9, 1. to 3.).
- mussfelder: the Mussfelder and Summenmussfelder of a Kapitalgesellschaft that the later version has new: „Die neue
  Position „Grundsteuer“ [is.netIncome.otherTaxes.GrSt] ... erhält die Mussfeld-Auszeichnung sowie alle drei
  Rechtsformauszeichnungen.“ (Änderungsnachweis, 3.), the only one of 6.10.

steuerbote/xbrl/tests/test_changes.py compares the data of each version with both packages of esteuer.de.

Lift. lift() takes a Bilanzzuordnung (steuerbote/xbrl/mapping.py) through the changes of each version up to the target
and gives the Lifted mapping on the target version: a rule of a renamed position names the new one; a rule whose
position or position for the opposite balance the later version removed, or that the view of the target refuses as
check() does, becomes a Watched account at the level blocking, a row to decide, so that a balance on it holds the
E-Bilanz and the Jahresabschluss back until someone gives it a position; the new Mussfelder are listed, since the
books may hold accounts that belong on them, such as the Grundsteuer, which the GuV of 6.9 had in the sonstige Steuern.
The watched accounts and those outside the Bilanz and the GuV stay as they are. A mapping climbs only to a later
version: the positions of an earlier one may be those the later version removed.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from steuerbote.ustva.mapping import WatchLevel
from steuerbote.xbrl.mapping import Mapping, Part, Rule, Watched, rule_problems
from steuerbote.xbrl.taxonomy import GAAP_PREFIX, Taxonomy
from steuerbote.xbrl.versions import TAXONOMIES, version_of

ANDERUNGSNACHWEIS_6_10 = (
	"Änderungsnachweis zum Taxonomie-Update 2026 (Taxonomie 6.10/6.9), www.esteuer.de; the versioning reports "
	"versioning/de-gaap-ci-2026-04-01/de-gaap-ci-2026-04-01-shell-fiscal-with-2025-04-01-versioning.xml and "
	"versioning/de-gcd-2026-04-01/de-gcd-2026-04-01-shell-with-2025-04-01-versioning.xml of the package 6.10"
)


class LiftError(ValueError):
	"""The Bilanzzuordnung cannot be lifted so."""


@dataclass(frozen=True, slots=True)
class Changes:
	"""What a version of the taxonomy changes against the one before, by the names of the concepts with the prefixes
	of their modules."""

	source_version: str
	target_version: str
	renamed: ReadOnlyMapping[str, str]
	removed: frozenset[str]
	added: frozenset[str]
	mussfelder: tuple[str, ...]
	"""The new Mussfelder and Summenmussfelder of a Kapitalgesellschaft."""
	source: str
	"""Where the changes come from."""

	def __post_init__(self) -> None:
		object.__setattr__(self, "renamed", MappingProxyType(dict(self.renamed)))


CHANGES: MappingProxyType[str, Changes] = MappingProxyType(
	{
		"6.10": Changes(
			"6.9",
			"6.10",
			renamed={},
			removed=frozenset(
				{
					"de-gaap-ci:bs.ass.currAss.receiv.shareholders.silent",
					"de-gaap-ci:bs.ass.currAss.receiv.unpaidCapitalPartners",
					"de-gaap-ci:bs.ass.currAss.receiv.unpaidCapitalPartners.misc",
					"de-gaap-ci:bs.ass.fixAss.fin.loansToSharehold.gmbhSilent",
					"de-gaap-ci:bs.ass.fixAss.fin.otherFinAss.silent",
					"de-gaap-ci:bs.ass.fixAss.fin.particip.silent.atypical",
					"de-gaap-ci:bs.ass.fixAss.fin.particip.silent.misc",
					"de-gaap-ci:bs.ass.fixAss.fin.particip.silent.typical",
					"de-gaap-ci:bs.eqLiab.liab.shareholders.gmbhSilent",
					"de-gaap-ci:fpl.additions.costOfRightsEStG4j",
					"de-gaap-ci:mgmtRep.salariesSystem",
					"de-gaap-ci:nt.relationships.DCGK_713_423",
					"de-gaap-ci:nt.relationships.remunerationReport",
					"de-gaap-ci:nt.relationships.salariesActiveMembers.BoardsSpecification.personal",
					"de-gaap-ci:nt.relationships.salariesActiveMembers.BoardsSpecification.personal.details",
					"de-gaap-ci:nt.relationships.salariesActiveMembers.BoardsSpecification.personal.details.DCGK_545_3comment",
					"de-gaap-ci:nt.relationships.salariesActiveMembers.BoardsSpecification.personal.details.DCGK_545_3value",
					"de-gaap-ci:nt.relationships.salariesActiveMembers.BoardsSpecification.personal.details.fixum",
					"de-gaap-ci:nt.relationships.salariesActiveMembers.BoardsSpecification.personal.details.longTermBenefit",
					"de-gaap-ci:nt.relationships.salariesActiveMembers.BoardsSpecification.personal.details.profitbenfit",
					"de-gaap-ci:nt.relationships.salariesActiveMembers.BoardsSpecification.personal.name",
					"de-gaap-ci:nt.relationships.salariesActiveMembers.BoardsSpecification.personal.value",
					"de-gaap-ci:nt.relationships.salariesFormerMembers.BoardsSpecification.personal",
					"de-gaap-ci:nt.relationships.salariesFormerMembers.BoardsSpecification.personal.details",
					"de-gaap-ci:nt.relationships.salariesFormerMembers.BoardsSpecification.personal.name",
					"de-gaap-ci:nt.relationships.salariesFormerMembers.BoardsSpecification.personal.value",
					"de-gaap-ci:nt.segmBusiness.DRS3_42",
					"de-gaap-ci:nt.segmBusiness.DRS3_45",
					"de-gaap-ci:nt.segmBusiness.assets",
					"de-gaap-ci:nt.segmBusiness.geographical",
					"de-gaap-ci:nt.segmBusiness.geographical.Assets",
					"de-gaap-ci:nt.segmBusiness.geographical.Description",
					"de-gaap-ci:nt.segmBusiness.geographical.SalesValue",
					"de-gaap-ci:nt.segmBusiness.geographical.longTermInvest",
					"de-gaap-ci:nt.segmBusiness.longTermInvest",
					"de-gaap-ci:nt.segmBusiness.profit.profAssoc",
					"de-gaap-ci:nt.segmGeographical.Business.Assets",
					"de-gaap-ci:nt.segmGeographical.Business.longTermInvest",
					"de-gaap-ci:nt.segmGeographical.DRS3_42",
					"de-gaap-ci:nt.segmGeographical.DRS3_45",
					"de-gaap-ci:nt.segmGeographical.longTermInvest",
					"de-gaap-ci:nt.segmGeographical.profit.profAssoc",
					"de-gcd:genInfo.report.id.reportElement.reportElements.transmissionNotYetPossible",
				}
			),
			added=frozenset(
				{
					"de-gaap-ci:DeterminationOfTaxableIncomeSpec.merchantVessels.RegisterEStG5aAbs4",
					"de-gaap-ci:bs.ass.currAss.inventory.finishedAndMerch.emissionBEHG",
					"de-gaap-ci:bs.ass.currAss.inventory.finishedAndMerch.emissionTEHG",
					"de-gaap-ci:bs.ass.currAss.inventory.finishedAndMerch.emissionTHG",
					"de-gaap-ci:bs.ass.currAss.inventory.material.emissionBEHG",
					"de-gaap-ci:bs.ass.currAss.inventory.material.emissionTEHG",
					"de-gaap-ci:bs.ass.currAss.inventory.material.emissionTHG",
					"de-gaap-ci:bs.ass.currAss.receiv.dueCapOfCoop",
					"de-gaap-ci:bs.ass.currAss.receiv.unpaidCapitalLimitedLiablePartners",
					"de-gaap-ci:bs.ass.currAss.receiv.unpaidCapitalUnlimitedLiablePartners",
					"de-gaap-ci:bs.eqLiab.equity.diffEarningsLessParent",
					"de-gaap-ci:bs.eqLiab.equity.revenueRes.departingMembersGenG",
					"de-gaap-ci:bs.eqLiab.equity.revenueRes.totalGenG",
					"de-gaap-ci:bs.eqLiab.otherSpecRes.TEHGFreeOfCharge",
					"de-gaap-ci:bs.eqLiab.otherSpecRes.THGFreeOfCharge",
					"de-gaap-ci:cfsDRS21.cashEqu.cashChanges.cfFromInvestments.awGrant",
					"de-gaap-ci:cfsDRS21.cashEqu.cashChanges.cfFromInvestments.grantRepay",
					"de-gaap-ci:cfsDRS21.cashEqu.cashChanges.cfFromInvestments.investmGrantRec",
					"de-gaap-ci:detailedInformation.accountbalances.notPossible",
					"de-gaap-ci:dim_parentDRS22K.accGroupStatement.contributionsPaidToCapitalIncrease",
					"de-gaap-ci:dim_parentDRS22K.accGroupStatement.contributionsSilentPartner",
					"de-gaap-ci:dim_parentDRS22K.accGroupStatement.deficitNotCoveredByCapital",
					"de-gaap-ci:dim_parentDRS22K.accGroupStatement.profitParticipCapital",
					"de-gaap-ci:dim_parentDRS22K.accGroupStatement.reserves.capIncreaseContributionsInclPremium",
					"de-gaap-ci:dim_parentDRS22K.accGroupStatement.shares.ownShares.multipleVotingShares",
					"de-gaap-ci:dim_parentDRS22K.accGroupStatement.shares.subscribed.multipleVotingShares",
					"de-gaap-ci:dim_parentDRS22K.accGroupStatement.shares.unpaidContribution.multipleVotingShares",
					"de-gaap-ci:dim_parentDRS22P.accGroupStatement.contributionsSilentPartner",
					"de-gaap-ci:dim_parentDRS22P.accGroupStatement.deficitNotCoveredByCapital",
					"de-gaap-ci:dim_parentDRS22P.accGroupStatement.diffEarningsLessParent",
					"de-gaap-ci:dim_parentDRS22P.accGroupStatement.profitParticipCapital",
					"de-gaap-ci:incomeUse.gainLoss.additionRevenReserves.RevRes",
					"de-gaap-ci:incomeUse.gainLoss.creditRes",
					"de-gaap-ci:incomeUse.gainLoss.debitRes",
					"de-gaap-ci:incomeUse.gainLoss.diffEarningsLessParent",
					"de-gaap-ci:incomeUse.gainLoss.releaseRevenReserves.RevRes",
					"de-gaap-ci:is.netIncome.otherTaxes.GrSt",
					"de-gaap-ci:nt.RegisterEStG5Abs1S2",
					"de-gcd:genInfo.company.id.shareholder.idNotAssigned",
				}
			),
			mussfelder=("de-gaap-ci:is.netIncome.otherTaxes.GrSt",),
			source=ANDERUNGSNACHWEIS_6_10,
		),
	}
)
"""The changes of each version but the first against the one before, by the later version."""


@dataclass(frozen=True, slots=True)
class Decision:
	"""A rule the lift cannot carry over: the rule as it was, the position that keeps it out and why, in German."""

	rule: Rule
	position: str
	text: str


@dataclass(frozen=True, slots=True)
class Lifted:
	"""A Bilanzzuordnung on a later version: the mapping, the rules whose positions the lift renamed as (account, old
	position, new position), the rules left to decide, now watched at the level blocking, and the new Mussfelder."""

	mapping: Mapping
	renamed: tuple[tuple[str, str, str], ...]
	to_decide: tuple[Decision, ...]
	mussfelder: tuple[str, ...]


def between(source: str, target: str) -> tuple[Changes, ...]:
	"""The changes from one version to a later one, each version in its order; none from a version to itself."""
	version_of(source)
	version_of(target)
	order = list(TAXONOMIES)
	start, end = order.index(source), order.index(target)
	if end < start:
		raise LiftError(
			f"a Bilanzzuordnung climbs to a later version of the HGB-Taxonomie, not from {source} to {target}"
		)
	return tuple(CHANGES[version] for version in order[start + 1 : end + 1])


def lift(
	mapping: Mapping,
	target: str,
	*,
	taxonomy: Taxonomy | None = None,
	parts: ReadOnlyMapping[str, Part] | None = None,
	changes: Iterable[Changes] | None = None,
) -> Lifted:
	"""The mapping on the positions of the target version, through the changes of each version up to it, by default
	those of CHANGES; ``taxonomy`` is the fiscal view of the target, which refuses what check() refuses, with the part
	of each account in ``parts``."""
	steps = between(mapping.taxonomy_version, target) if changes is None else tuple(changes)
	if not steps:
		raise LiftError(f"the Bilanzzuordnung names the positions of the HGB-Taxonomie {target} already")
	reached = mapping.taxonomy_version
	for step in steps:
		if step.source_version != reached:
			raise LiftError(
				f"the changes lead from {step.source_version} to {step.target_version}, the mapping names {reached}"
			)
		reached = step.target_version
	if reached != target:
		raise LiftError(f"the changes lead to {reached}, not to {target}")
	rules: list[Rule] = []
	watched = list(mapping.watched)
	renamed: list[tuple[str, str, str]] = []
	to_decide: list[Decision] = []
	for rule in mapping.rules:
		decision, carried = _carried(rule, steps, taxonomy, (parts or {}).get(rule.account_number))
		if decision is not None:
			to_decide.append(decision)
			watched.append(Watched(rule.account_number, WatchLevel.BLOCKING))
			continue
		for old, new in ((rule.concept, carried.concept), (rule.opposite, carried.opposite)):
			if old is not None and old != new:
				renamed.append((rule.account_number, old, new))
		rules.append(carried)
	return Lifted(
		Mapping(mapping.chart, tuple(rules), tuple(watched), mapping.excluded, target),
		tuple(renamed),
		tuple(to_decide),
		tuple(_unqualified(name) for step in steps for name in step.mussfelder),
	)


def _carried(
	rule: Rule, steps: tuple[Changes, ...], taxonomy: Taxonomy | None, part: Part | None
) -> tuple[Decision | None, Rule]:
	"""The rule on the target version, or the decision why it cannot go there."""
	concept, opposite = rule.concept, rule.opposite
	for step in steps:
		concept, opposite = _renamed(concept, step), _renamed(opposite, step)
		for name in (concept, opposite):
			if name is not None and _qualified(name) in step.removed:
				text = f"Die HGB-Taxonomie {step.target_version} hat die Position {name} nicht mehr."
				return Decision(rule, name, text), rule
	carried = replace(rule, concept=concept, opposite=opposite)
	problems = rule_problems(carried, taxonomy, part) if taxonomy is not None else ()
	if problems:
		return Decision(rule, str(problems[0].values[1]), problems[0].text), rule
	return None, carried


def _renamed(name: str | None, step: Changes) -> str | None:
	if name is None:
		return None
	return _unqualified(step.renamed.get(_qualified(name), _qualified(name)))


def _qualified(name: str) -> str:
	return name if ":" in name else f"{GAAP_PREFIX}:{name}"


def _unqualified(name: str) -> str:
	return name.removeprefix(f"{GAAP_PREFIX}:")
