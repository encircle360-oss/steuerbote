"""Where the supplier of a purchase is established, and whether its base takes the line of § 13b Absatz 1 UStG.

Section D of form USt 1 A 2026 takes the purchases whose tax the company owes as Leistungsempfänger (§ 13b Absatz 5
UStG) on three lines. Line 30 (Kz 46/47) holds the „sonstige Leistungen nach § 3a Absatz 2 UStG eines im übrigen
Gemeinschaftsgebiet ansässigen Unternehmers“, line 32 (Kz 84/85) „Werklieferungen und die nicht in Zeile 30
einzutragenden sonstigen Leistungen eines im Ausland ansässigen Unternehmers“ and the domestic cases of § 13b Absatz 2
Nummer 2 and 4 to 12 UStG, such as Bauleistungen and the cleaning of buildings (Anleitung USt 1 E 2026, „Zeilen 30 bis
32“). A voucher that books the tax of § 13b UStG on an ordinary expense account does not tell which line it belongs
to; its supplier does. place() decides from the facts the caller gives per voucher (Voucher):

1. a classification of the voucher itself, which a person stated (Source.VOUCHER);
2. a classification of its supplier, which a person stated (Source.SUPPLIER);
3. a classification of the tax template of the voucher, which a person stated for the template (Source.TAX_TEMPLATE);
4. the country of the supplier's master data (Source.COUNTRY), else the country of its address (Source.ADDRESS): a
   supplier established in another member state on the day of the voucher gives Classification.EU_SERVICE, one
   established in Germany or in the Drittlandsgebiet Classification.OTHER.

A stated classification always wins, because only a person can tell an EU supplier's supply that is no service of
§ 3a Absatz 2 UStG, such as a Werklieferung, a service connected with land (§ 3a Absatz 3 Nummer 1 UStG) or the
short-term hire of a means of transport (§ 3a Absatz 3 Nummer 2 UStG): those belong to § 13b Absatz 2 Nummer 1 UStG
and line 32. Without one and without a country the classification stays open (None), and the caller takes the
Kennzahl of its mapping. Every contradiction is a Finding, never a silent choice.

The VAT ID decides nothing. Its prefix only checks the country: a supplier established in the Drittlandsgebiet may
hold the VAT ID of a member state where it is registered, a number starting with EU is the identification of the
non-Union scheme of the One-Stop-Shop (Article 362 of Directive 2006/112/EC), which a business established outside
the Union holds, and XI is Northern Ireland, which counts as a member state for goods only. A prefix that names
another residence than the country gives Problem.VAT_ID_PREFIX.

„Ein im übrigen Gemeinschaftsgebiet ansässiger Unternehmer ist ein Unternehmer, der in den Gebieten der übrigen
Mitgliedstaaten der Europäischen Union, die nach dem Gemeinschaftsrecht als Inland dieser Mitgliedstaaten gelten,
einen Wohnsitz, seinen gewöhnlichen Aufenthalt, seinen Sitz, seine Geschäftsleitung oder eine Betriebsstätte hat“,
and „Maßgebend ist der Zeitpunkt, in dem die Leistung ausgeführt wird“ (§ 13b Absatz 7 Satz 2 and 4 UStG). The member
states of a day follow MEMBERSHIPS. Monaco counts as France (§ 1 Absatz 2a Satz 2 UStG). The territories of a member
state outside its VAT territory, such as the Canary Islands or Åland (Article 6 of Directive 2006/112/EC), share the
country code of the state; a supplier there needs a stated classification.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from types import MappingProxyType

from steuerbote.vatid.ustid import normalize

GERMANY = "DE"


class Residence(StrEnum):
	"""Where a supplier is established for § 13b UStG."""

	DOMESTIC = "domestic"
	OTHER_MEMBER_STATE = "other member state"
	THIRD_COUNTRY = "third country"


class Classification(StrEnum):
	"""The line of section D a person states for a supplier, a voucher or a tax template.

	EU_SERVICE: a sonstige Leistung of § 3a Absatz 2 UStG of a business established in another member state, § 13b
	Absatz 1 UStG, line 30. OTHER: every other supply of § 13b UStG on line 32.
	"""

	EU_SERVICE = "EU Service"
	OTHER = "Other Reverse Charge"


class Source(StrEnum):
	"""What decided the classification of a voucher."""

	VOUCHER = "voucher"
	SUPPLIER = "supplier"
	TAX_TEMPLATE = "tax template"
	COUNTRY = "country"
	ADDRESS = "address"
	NONE = "none"


STATED = frozenset({Source.VOUCHER, Source.SUPPLIER, Source.TAX_TEMPLATE})


@dataclass(frozen=True, slots=True)
class Membership:
	"""A member state for VAT: its code, its name as ERPNext names the Country, its first and its last day."""

	code: str
	country: str
	joined: date
	left: date | None = None

	def on(self, day: date) -> bool:
		return self.joined <= day and (self.left is None or day <= self.left)


FOUNDING = date(1958, 1, 1)
FIRST_ENLARGEMENT = date(1973, 1, 1)
ENLARGEMENT_2004 = date(2004, 5, 1)
ENLARGEMENT_2007 = date(2007, 1, 1)
# The member states of the European Union by their accession, and the United Kingdom, whose VAT law stayed that of the
# Union to the end of the transition period on 31 December 2020 (Articles 126 and 127 of the withdrawal agreement, ABl.
# L 29 of 31 January 2020); the Isle of Man counted as its territory (§ 1 Absatz 2a Satz 2 UStG). Accession years as
# the European Union lists them (https://european-union.europa.eu/principles-countries-history/eu-countries_en), the
# days those of the accession treaties.
MEMBERSHIPS: tuple[Membership, ...] = (
	Membership("BE", "Belgium", FOUNDING),
	Membership("BG", "Bulgaria", ENLARGEMENT_2007),
	Membership("CZ", "Czech Republic", ENLARGEMENT_2004),
	Membership("DK", "Denmark", FIRST_ENLARGEMENT),
	Membership("DE", "Germany", FOUNDING),
	Membership("EE", "Estonia", ENLARGEMENT_2004),
	Membership("IE", "Ireland", FIRST_ENLARGEMENT),
	Membership("GR", "Greece", date(1981, 1, 1)),
	Membership("ES", "Spain", date(1986, 1, 1)),
	Membership("FR", "France", FOUNDING),
	Membership("HR", "Croatia", date(2013, 7, 1)),
	Membership("IT", "Italy", FOUNDING),
	Membership("CY", "Cyprus", ENLARGEMENT_2004),
	Membership("LV", "Latvia", ENLARGEMENT_2004),
	Membership("LT", "Lithuania", ENLARGEMENT_2004),
	Membership("LU", "Luxembourg", FOUNDING),
	Membership("HU", "Hungary", ENLARGEMENT_2004),
	Membership("MT", "Malta", ENLARGEMENT_2004),
	Membership("NL", "Netherlands", FOUNDING),
	Membership("AT", "Austria", date(1995, 1, 1)),
	Membership("PL", "Poland", ENLARGEMENT_2004),
	Membership("PT", "Portugal", date(1986, 1, 1)),
	Membership("RO", "Romania", ENLARGEMENT_2007),
	Membership("SI", "Slovenia", ENLARGEMENT_2004),
	Membership("SK", "Slovakia", ENLARGEMENT_2004),
	Membership("FI", "Finland", date(1995, 1, 1)),
	Membership("SE", "Sweden", date(1995, 1, 1)),
	Membership("GB", "United Kingdom", FIRST_ENLARGEMENT, date(2020, 12, 31)),
)
# Territory that § 1 Absatz 2a Satz 2 UStG counts as that of a member state: code, name in ERPNext, the state's code.
COUNTED_AS: tuple[tuple[str, str, str], ...] = (("MC", "Monaco", "FR"), ("IM", "Isle of Man", "GB"))
# The prefixes of VAT IDs that are no ISO code of their state: Greece writes EL. XI is Northern Ireland, where the
# rules of the Union apply to goods only: „Für den Dienstleistungsverkehr mit Nordirland gelten die für das
# Drittlandsgebiet geltenden Vorschriften zur Umsatzsteuer.“ (BZSt, „Fragen und Antworten“ zur USt-IdNr.)
VAT_PREFIXES = MappingProxyType({"EL": "GR"})
THIRD_COUNTRY_PREFIXES = frozenset({"XI"})
# EU and nine digits identify a business established outside the Union in the non-Union scheme of the One-Stop-Shop
# (Article 362 of Directive 2006/112/EC); such a number says nothing about a member state.
NO_EVIDENCE_PREFIXES = frozenset({"EU"})


def _by_key() -> MappingProxyType[str, Membership]:
	found = {key.casefold(): state for state in MEMBERSHIPS for key in (state.code, state.country)}
	for code, country, state in COUNTED_AS:
		found[code.casefold()] = found[country.casefold()] = found[state.casefold()]
	return MappingProxyType(found)


_MEMBERSHIPS = _by_key()


def member_state(country: str | None, day: date) -> Membership | None:
	"""The member state a country given by its code or its name in ERPNext belongs to on ``day``; None outside."""
	state = _MEMBERSHIPS.get((country or "").strip().casefold())
	return state if state is not None and state.on(day) else None


def residence_in(country: str | None, day: date) -> Residence | None:
	"""Where a business with an establishment in ``country`` is established on ``day``; None without a country."""
	if not (country or "").strip():
		return None
	state = member_state(country, day)
	if state is None:
		return Residence.THIRD_COUNTRY
	return Residence.DOMESTIC if state.code == GERMANY else Residence.OTHER_MEMBER_STATE


def vat_id_prefix(vat_id: str | None) -> str:
	"""The first two letters of the VAT ID as normalize() reads it; empty without them."""
	number = normalize(vat_id) if isinstance(vat_id, str) else ""
	prefix = number[:2]
	return prefix if len(prefix) == 2 and prefix.isalpha() else ""


def residence_of_vat_id(vat_id: str | None, day: date) -> Residence | None:
	"""The residence a VAT ID points to on ``day``: that of a member state's prefix, the Drittlandsgebiet for XI and for
	a prefix of a former member state, None for EU and every other prefix, which names no state for sure."""
	prefix = vat_id_prefix(vat_id)
	if prefix in THIRD_COUNTRY_PREFIXES:
		return Residence.THIRD_COUNTRY
	code = VAT_PREFIXES.get(prefix, prefix)
	if prefix in NO_EVIDENCE_PREFIXES or not any(state.code == code for state in MEMBERSHIPS):
		return None
	return residence_in(code, day)


class Problem(StrEnum):
	"""Why a person should look at a voucher of section C or D."""

	NO_SUPPLIER = "no supplier"
	SUPPLIERS_DISAGREE = "suppliers disagree"
	NO_COUNTRY = "no country"
	ADDRESS_ELSEWHERE = "address elsewhere"
	VAT_ID_PREFIX = "vat id prefix"
	STATED_EU_SERVICE_OUTSIDE = "stated eu service outside"
	TEMPLATE_OTHER_FROM_MEMBER_STATE = "template other from member state"
	ACQUISITION_OUTSIDE_EU = "acquisition outside eu"
	EU_SERVICE_ACCOUNT_OUTSIDE = "eu service account outside"


@dataclass(frozen=True, slots=True)
class Supplier:
	"""A supplier as its master data tell it: name, country, the country of its address, VAT ID, and the
	classification a person stated for it."""

	name: str
	country: str | None = None
	address_country: str | None = None
	vat_id: str | None = None
	classification: Classification | None = None

	def __post_init__(self) -> None:
		if not (isinstance(self.name, str) and self.name.strip()):
			raise ValueError(f"a supplier needs a name, not {self.name!r}")
		if self.classification is not None:
			object.__setattr__(self, "classification", Classification(self.classification))


@dataclass(frozen=True, slots=True)
class Voucher:
	"""What the caller knows of one voucher: its day, the suppliers it books, the classification a person stated
	for it, and its tax template with the classification a person stated for that template."""

	day: date
	suppliers: tuple[Supplier, ...] = ()
	classification: Classification | None = None
	tax_template: str | None = None
	template_classification: Classification | None = None

	def __post_init__(self) -> None:
		if not isinstance(self.day, date):
			raise TypeError(f"day must be a date, not {type(self.day).__name__}")
		object.__setattr__(self, "suppliers", tuple(self.suppliers))
		for name in ("classification", "template_classification"):
			value = getattr(self, name)
			if value is not None:
				object.__setattr__(self, name, Classification(value))


@dataclass(frozen=True, slots=True)
class Finding:
	"""A voucher a person should look at: what is wrong, the supplier it is about and the facts that show it, such
	as countries or a prefix. ``kennzahl`` names the Kennzahl the base went to, when one did, and ``alternative``
	the Kennzahl a classification would send it to instead."""

	problem: Problem
	voucher: str | None
	supplier: str = ""
	facts: tuple[str, ...] = ()
	kennzahl: str = ""
	alternative: str = ""


@dataclass(frozen=True, slots=True)
class Placement:
	"""The decision for one voucher: its classification (None while open), the residence of its suppliers (None
	when unknown or not one), what decided the classification and what a person should look at."""

	classification: Classification | None
	residence: Residence | None
	source: Source
	findings: tuple[Finding, ...] = field(default=())


UNKNOWN = Placement(None, None, Source.NONE)


@dataclass(frozen=True, slots=True)
class _Established:
	residence: Residence | None
	source: Source
	findings: tuple[Finding, ...]


def _established(voucher: str | None, supplier: Supplier, day: date) -> _Established:
	by_country = residence_in(supplier.country, day)
	by_address = residence_in(supplier.address_country, day)
	by_vat_id = residence_of_vat_id(supplier.vat_id, day)
	findings: list[Finding] = []
	if by_country is not None:
		residence, source = by_country, Source.COUNTRY
		if by_address is not None and by_address is not by_country:
			facts = (supplier.country.strip(), supplier.address_country.strip())
			findings.append(Finding(Problem.ADDRESS_ELSEWHERE, voucher, supplier.name, facts))
	elif by_address is not None:
		residence, source = by_address, Source.ADDRESS
	else:
		facts = (vat_id_prefix(supplier.vat_id),) if by_vat_id is not None else ()
		return _Established(None, Source.NONE, (Finding(Problem.NO_COUNTRY, voucher, supplier.name, facts),))
	if by_vat_id is not None and by_vat_id is not residence:
		country = supplier.country if source is Source.COUNTRY else supplier.address_country
		facts = (country.strip(), vat_id_prefix(supplier.vat_id))
		findings.append(Finding(Problem.VAT_ID_PREFIX, voucher, supplier.name, facts))
	return _Established(residence, source, tuple(findings))


def place(voucher: str | None, facts: Voucher | None) -> Placement:
	"""The classification of a voucher of § 13b UStG and the residence of its suppliers, see the module.

	A voucher the caller knows nothing of stays open without a finding. Several suppliers decide together only when
	they agree; otherwise the classification stays open unless a person stated one for the voucher.
	"""
	if facts is None:
		return UNKNOWN
	established = [_established(voucher, supplier, facts.day) for supplier in facts.suppliers]
	residences = {each.residence for each in established}
	residence = residences.pop() if len(residences) == 1 else None
	stated, source = _stated(facts)
	findings: list[Finding] = []
	if stated is None:
		if residence is not None:
			stated = (
				Classification.EU_SERVICE
				if residence is Residence.OTHER_MEMBER_STATE
				else Classification.OTHER
			)
			source = (
				established[0].source if len({each.source for each in established}) == 1 else Source.COUNTRY
			)
			findings.extend(finding for each in established for finding in each.findings)
		else:
			findings.extend(_open(voucher, facts, established))
	elif stated is Classification.EU_SERVICE and residence not in (None, Residence.OTHER_MEMBER_STATE):
		findings.append(_stated_outside(voucher, facts, source, residence))
	elif (
		source is Source.TAX_TEMPLATE
		and stated is Classification.OTHER
		and residence is Residence.OTHER_MEMBER_STATE
	):
		findings.append(
			Finding(
				Problem.TEMPLATE_OTHER_FROM_MEMBER_STATE,
				voucher,
				_names(facts.suppliers),
				(facts.tax_template or "",),
			)
		)
	return Placement(stated, residence, source, tuple(findings))


def _stated(facts: Voucher) -> tuple[Classification | None, Source]:
	if facts.classification is not None:
		return facts.classification, Source.VOUCHER
	stated = {supplier.classification for supplier in facts.suppliers}
	if len(stated) == 1 and None not in stated:
		return stated.pop(), Source.SUPPLIER
	if facts.template_classification is not None:
		return facts.template_classification, Source.TAX_TEMPLATE
	return None, Source.NONE


def _open(voucher: str | None, facts: Voucher, established: list[_Established]) -> Iterable[Finding]:
	"""Why no classification was found: no supplier, suppliers established in different places, or suppliers
	without a country."""
	if not facts.suppliers:
		return (Finding(Problem.NO_SUPPLIER, voucher),)
	if all(each.residence is not None for each in established):
		where = tuple(
			fact
			for supplier, each in zip(facts.suppliers, established, strict=True)
			for fact in (supplier.name, str(each.residence))
		)
		return (Finding(Problem.SUPPLIERS_DISAGREE, voucher, _names(facts.suppliers), where),)
	return (finding for each in established if each.residence is None for finding in each.findings)


def _stated_outside(voucher: str | None, facts: Voucher, source: Source, residence: Residence) -> Finding:
	return Finding(
		Problem.STATED_EU_SERVICE_OUTSIDE, voucher, _names(facts.suppliers), (str(source), str(residence))
	)


def _names(suppliers: Iterable[Supplier]) -> str:
	return ", ".join(supplier.name for supplier in suppliers)
