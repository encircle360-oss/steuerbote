"""The Global Common Data of the E-Bilanz: the company and the report from the master data and the case, and NIL for
every other Mussfeld of the GCD of a GmbH or UG.

Sources are the Technischer Leitfaden zur HGB-Taxonomie 6.9, Stand 10.06.2025 („Leitfaden“), B.14.3.1, and the rules of
Jahresdokumentation_Bilanz_Taxonomie_6_9.ods of the ERiC documentation 44.3.6.0, sheet „Kontext - Regeln“, cited by
their Fehlercode; the GmbH example of that documentation, HandelsbilanzLandwirt_GmbH.xml, shows the same GCD.

Report (genInfo.report):

- Fertigstellungsstatus „endgültig“ [reportStatus.E], as „Ein Datensatz mit dem „Fertigstellungsstatus des Berichts“
  ... „vorläufig“ ... stellt weder eine fristwahrende Übersendung dar, noch erfüllt er eine Abgabeverpflichtung.“
  (B.14.3.1.1).
- Status des Berichts [revisionStatus]: „erstmalig“, or for a Berichtigung the status that says how it corrects
  (B.14.3.1.2; FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d; steuerbote/jahresmeldung/corrections.py).
- Berichtsbestandteile [reportElement]: the components of the case (steuerbote/ebilanz/positions.py) as empty strings,
  the other values that are Mussfelder as NIL: „Wenn eine Position für die Mehrfachauswahl in ihren Auswahlwerten
  Mussfelder enthält, dann müssen alle Werte der Mussfelder berichtet werden, die übrigen Werte sind optional.“ (A.10.1)
  The „Erläuterung, warum die Übermittlung der Kontennachweise noch nicht möglich ist“ carries the reason of a case
  without Kontensalden and is NIL in every other (B.12; rules 170405002 and 170405024).
- Bilanzart [statementType] Jahresabschluss or Eröffnungsbilanz (B.14.3.1.3). „Bilanz enthält Ausweis des
  Bilanzgewinns/Bilanzverlustes“ is false, since the Bilanz shows the Jahresüberschuss, and „Bei Bilanzart ...
  Eröffnungsbilanz ... ist nur die Ausprägung „nein“ zulässig“ (B.14.3.1.7; rules 170205047 and 170405038).
- Bilanzierungsstandard HAOE, HGBM or AO (B.13, B.14.3.1.12); Branchen „Kerntaxonomie“ [specialAccountingStandard.K],
  as the report references the GAAP module of the Kerntaxonomie (B.14.3.1.13, B.14.3.1.14); GuV-Format
  Gesamtkostenverfahren (B.14.3.1.15); Konsolidierungsumfang „nicht konsolidiert/Einzelabschluss“
  [consolidationRange.EA] (B.14.3.1.8, rule 170205046).
- Beginn and Ende des Wirtschaftsjahres and the Bilanzstichtag (B.14.3.1.4, B.14.3.1.6; rules 170205048, 170205070,
  170205071), and those of the previous fiscal year, NIL in the first (B.14.3.1.5, B.14.3.1.6). The version of the
  taxonomy serves the fiscal year: „Eine Eröffnungsbilanz ist mit einer der Taxonomieversionen zu übermitteln, mit der
  auch die Schlussbilanz des ersten Wirtschaftsjahres übermittelt werden kann. ... Es wird nicht beanstandet, wenn eine
  Eröffnungsbilanz mit der vorhergehenden Taxonomieversion übermittelt wird.“ (B.18; rules 170205007, 170205017 and
  170205018; steuerbote/xbrl/versions.py).

Company (genInfo.company):

- Name, Straße, Postleitzahl and Ort of the Firmensitz: „Werte müssen ungleich „leer“ sein. Die Angabe „Firmensitz,
  Hausnummer“ ... kann auch „leer“ übermittelt werden.“ (B.14.3.1.16; rules 170205049, 170205051, 170205052 and
  170205053). The country is Deutschland, where a GmbH has its Sitz (§ 4a GmbHG). The texts take the characters of
  ELSTER (steuerbote/elster/charset.py; ERiC E-Bilanz-Dokumentation für HGB-Taxonomie 6.9, Kap. 3.16).
- Rechtsform GMBH or UG of the kind „KSt“ (B.4.1, B.14.3.1.17): legal_status() of the Annual Filing Settings
  (steuerbote/steuerbote/doctype/annual_filing_settings/rules.py), whose rechtsform() gives the keys 350 and 370 of the
  KSt 1 and GewSt 1 A, which the GCD does not take.
- Unternehmenskennnummern [idNo]: „Mindestens die Ausprägung „13stellige Steuernummer“ ... muss angegeben sein.
  ... Wird eine Eröffnungsbilanz übermittelt ..., muss bei Fehlen eines Wertes bei „13stellige Steuernummer“ ein Wert
  bei „4stellige Bundesfinanzamtsnummer“ ... angegeben sein.“ (B.14.3.1.18; rules 170205025 and 170205026). The
  Bundesfinanzamtsnummer is the first four digits of the Steuernummer, the Finanzamt that receives the E-Bilanz
  (B.2.1; rules 170205001 and 170205002). Steuerbote checks the form of ELSTER, 13 digits with a 0 as the fifth, and
  leaves the Prüfziffer to ERiC (B.14.8). Which identifier the contexts of an Eröffnungsbilanz without a Steuernummer
  name is unverified: every example of the ERiC documentation names the Steuernummer in the scheme of
  steuerbote/xbrl/facts.py (B.14.7), so such an E-Bilanz waits for the Steuernummer.
- Zuordnung zur Einkunftsart „Einkünfte aus Gewerbebetrieb“ [incomeClassification.trade], which a GmbH must choose
  (B.14.3.1.9; rule 170405037), and the Geschäftstätigkeit where the settings give it.

- Gesellschafter [shareholder], a Mussfeld of the GCD of a GmbH (B.14.2.1), once for each shareholder of the Annual
  Filing Settings who holds shares on the Bilanzstichtag: the name, the Rechtsform des Gesellschafters [legalStatus]
  KOER for a corporation and PG for a partnership, and the Beteiligungsschlüssel [ShareDivideKey] as Zähler and Nenner
  in lowest terms, both digits only (de-gcd-2025-04-01.xsd). The Rechtsform of a natural person tells Privatvermögen
  (NPP) from Betriebsvermögen (NPB), which the settings do not record, so it stays NIL. Steuernummer, IdNr. and W-IdNr.
  of a shareholder are kept for the KSt 1 (§ 139b Abs. 2 AO for the IdNr.) and are NIL here; the Gesellschafterschlüssel
  [id] is for a partnership (B.14.3.1.19) and NIL as well. Without shareholders in the settings one Gesellschafter is
  NIL, as the GmbH example HandelsbilanzLandwirt_GmbH.xml reports it.

Every other Mussfeld of the GCD of the legal form (steuerbote.xbrl.checks.required(); B.14.2.1, B.14.2.3) is NIL, and
of a tuple with Mussfelder „Es ist vielmehr erforderlich, die Inhalte der Datenstruktur so zu berichten, dass die
darin enthaltenen Mussfelder mit NIL-Werten befüllt werden.“ (A.10.1): the Unternehmenskennnummern Steuerbote does not
keep, with the parts their sequence cannot do without. „Wenn eine Position mit Auswahlwerten als Mussfeld deklariert
ist, dann muss zumindest einer der enthaltenen Auswahlwerte berichtet werden oder das jeweilige Tupel ist mit dem Wert
NIL zu berichten.“ (A.10.1) ERiC takes only the first: its rule 170155092 looks for a fact of the Mussfeld in the
contexts of the current year, which a tuple has none of, so a choice NIL as a whole fails (validation with ERiC
44.3.6.0, Bilanz_6.9). A choice without a value reports one Auswahlwert NIL in the fiscal year instead, the one the
GmbH example names: „Unternehmen mit Gewinnermittlung für besondere Fälle“ [entityWithTaxablePurposeBusiness], which
a GmbH or UG with the ordinary determination of its profit is not, and „Inländische Betriebsstätte eines ausländischen
Unternehmens“ [domesticBranchOfForeignCompany], which a GmbH with its Sitz in Germany is not. NIL is no value: the
Ausprägungen of entityWithTaxablePurposeBusiness count only „werthaltig“ (B.20.1.2, B.20.1.3). A Mussfeld of another
legal form is not sent, not even NIL (FAQ zur E-Bilanz, Tz. 4 a). The facts follow the presentation of the GCD, which
also decides what is reported: „Es dürfen nur solche Positionen übermittelt werden, die in dem Presentation Network
erfasst sind“ (B.11).

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from fractions import Fraction

from steuerbote.ebilanz.kontennachweis import NOT_YET_POSSIBLE
from steuerbote.ebilanz.positions import Finding, Structure, leitfaden, rule
from steuerbote.elster.charset import CharsetError, describe, transliterate
from steuerbote.jahresmeldung.corrections import RevisionStatus, revision_status_concept
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import (
	ELSTER_STEUERNUMMER,
	Shareholder,
	ShareholderKind,
	shareholders_on,
)
from steuerbote.xbrl.facts import Entity, Fact, Item, Period, Tuple, choice, nil
from steuerbote.xbrl.taxonomy import GCD, Kind, Taxonomy
from steuerbote.xbrl.versions import UnknownTaxonomyError, version_of

PREFIX = "de-gcd:"
COUNTRY = "Deutschland"
SEQUENCE = "sequence"
ERIC_CHARACTERS = "ERiC E-Bilanz-Dokumentation für HGB-Taxonomie 6.9, Kap. 3.16"


def gcd(name: str) -> str:
	"""A name of the GCD module with its prefix."""
	return f"{PREFIX}{name}"


ID_NUMBERS = gcd("genInfo.company.id.idNo")
ST13 = gcd("genInfo.company.id.idNo.type.companyId.ST13")
BF4 = gcd("genInfo.company.id.idNo.type.companyId.BF4")
NAME = gcd("genInfo.company.id.name")
STREET = gcd("genInfo.company.id.location.street")
HOUSE_NUMBER = gcd("genInfo.company.id.location.houseNo")
POSTAL_CODE = gcd("genInfo.company.id.location.zipCode")
CITY = gcd("genInfo.company.id.location.city")
COUNTRY_NAME = gcd("genInfo.company.id.location.country")
BUSINESS = gcd("genInfo.company.id.business")
FISCAL_YEAR_BEGIN = gcd("genInfo.report.period.fiscalYearBegin")
PREVIOUS_FISCAL_YEAR_END = gcd("genInfo.report.period.fiscalPreviousYearEnd")
SHAREHOLDER = gcd("genInfo.company.id.shareholder")
SHAREHOLDER_NAME = gcd("genInfo.company.id.shareholder.name")
SHAREHOLDER_STATUS = "genInfo.company.id.shareholder.legalStatus"
SHAREHOLDER_LEGAL_STATUS = {
	ShareholderKind.CORPORATION: "legalStatus.KOER",
	ShareholderKind.PARTNERSHIP: "legalStatus.PG",
}
SHARE_DIVIDE_KEY = gcd("genInfo.company.id.shareholder.ShareDivideKey")
NIL_CHOICES = {
	gcd("genInfo.company.id.entityWithTaxablePurposeBusiness"): gcd(
		"genInfo.company.id.entityWithTaxablePurposeBusiness.merchantVesselsInInternationalTraffic"
	),
	gcd("genInfo.company.id.domesticBranchOfForeignCompany"): gcd(
		"genInfo.company.id.domesticBranchOfForeignCompany.other"
	),
	gcd(SHAREHOLDER_STATUS): gcd(f"{SHAREHOLDER_STATUS}.legalStatus.NPP"),
}
"""The Auswahlwert a choice without a value reports NIL, as the GmbH example of the ERiC documentation 44.3.6.0,
HandelsbilanzLandwirt_GmbH.xml, does; any other choice reports its first."""
CHOICE = "choice"


@dataclass(frozen=True, slots=True)
class Gesellschafter:
	"""A shareholder as the GCD reports it: the name, the kind of the Annual Filing Settings and the share in percent."""

	name: str
	kind: ShareholderKind
	percent: Decimal


def gesellschafter(shareholders: Iterable[Shareholder], day: date) -> tuple[Gesellschafter, ...]:
	"""The shareholders of the settings who hold shares on the day, the Bilanzstichtag."""
	return tuple(
		Gesellschafter(shareholder.name, shareholder.kind, shareholder.percent)
		for shareholder in shareholders_on(shareholders, day)
	)


@dataclass(frozen=True, slots=True)
class MasterData:
	"""What the GCD says of the company and the filing beyond the case, from the Annual Filing Settings.

	``steuernummer`` is the Steuernummer for the income taxes in the 13-digit form of ELSTER, None for an
	Eröffnungsbilanz before the Finanzamt gave one, which then names its ``bundesfinanzamtsnummer``.
	``house_number`` holds the Hausnummer with its suffix, such as 12a. ``previous_fiscal_year`` is the first and the
	last day of the previous fiscal year, None in the first; a Handelsbilanz that shows the previous year takes those
	of its case. ``generated`` is the day the E-Bilanz is written, its Erstellungsdatum.
	"""

	name: str
	street: str
	postal_code: str
	city: str
	steuernummer: str | None
	house_number: str = ""
	bundesfinanzamtsnummer: str | None = None
	business: str = ""
	revision_status: RevisionStatus = RevisionStatus.FIRST
	previous_fiscal_year: tuple[date, date] | None = None
	generated: date | None = None
	shareholders: tuple[Gesellschafter, ...] = field(default=())

	@property
	def finanzamt(self) -> str | None:
		"""The Bundesfinanzamtsnummer of the Finanzamt that receives the E-Bilanz (Leitfaden B.2.1)."""
		if self.steuernummer:
			return self.steuernummer[:4]
		return self.bundesfinanzamtsnummer or None


def entity(master: MasterData) -> Entity | None:
	"""The company as the contexts of the instance name it, None without a Steuernummer of ELSTER."""
	if master.steuernummer is None or not ELSTER_STEUERNUMMER.fullmatch(master.steuernummer):
		return None
	return Entity.steuernummer(master.steuernummer)


def facts(structure: Structure, master: MasterData, *, reason: str = "") -> tuple[Fact, ...]:
	"""The GCD of the E-Bilanz in the order of its presentation; ``reason`` says why a case without Kontensalden sends
	none (steuerbote.ebilanz.kontennachweis.Kontennachweis.reason)."""
	case = structure.case
	periods = case.periods
	previous = (
		(periods.prior_fiscal_year_begin, periods.prior_fiscal_year_end)
		if case.prior
		else master.previous_fiscal_year
	)
	given: list[Fact] = [
		_choice("genInfo.report.id.reportStatus", "reportStatus.E"),
		choice(gcd("genInfo.report.id.revisionStatus"), gcd(revision_status_concept(master.revision_status))),
		_choice(
			"genInfo.report.id.reportElement",
			*(f"reportElements.{component.code}" for component in structure.components),
		),
		_item(NOT_YET_POSSIBLE, None if case.kontennachweis else _text(reason)),
		_choice("genInfo.report.id.statementType", f"statementType.{case.statement_type.value}"),
		_item(gcd("genInfo.report.id.incomeStatementendswithBalProfit"), False),
		_choice(
			"genInfo.report.id.accountingStandard", f"accountingStandard.{case.accounting_standard.value}"
		),
		_choice("genInfo.report.id.specialAccountingStandard", "K"),
		_choice("genInfo.report.id.incomeStatementFormat", "incomeStatementFormat.GKV"),
		_choice("genInfo.report.id.consolidationRange", "consolidationRange.EA"),
		_item(FISCAL_YEAR_BEGIN, periods.fiscal_year_begin),
		_item(gcd("genInfo.report.period.fiscalYearEnd"), periods.fiscal_year_end),
		_item(gcd("genInfo.report.period.balSheetClosingDate"), periods.balance_sheet_date),
		_item(gcd("genInfo.report.period.fiscalPreviousYearBegin"), previous[0] if previous else None),
		_item(PREVIOUS_FISCAL_YEAR_END, previous[1] if previous else None),
		_item(
			gcd("genInfo.report.period.balSheetClosingDatePreviousYear"), previous[1] if previous else None
		),
		_item(NAME, _text(master.name)),
		_item(STREET, _text(master.street)),
		_item(HOUSE_NUMBER, _text(master.house_number)),
		_item(POSTAL_CODE, _text(master.postal_code)),
		_item(CITY, _text(master.city)),
		_item(COUNTRY_NAME, COUNTRY),
		_choice("genInfo.company.id.legalStatus", f"legalStatus.{case.legal_status}"),
		Tuple(ID_NUMBERS, (_item(ST13, master.steuernummer or None), _item(BF4, master.finanzamt))),
		_item(BUSINESS, _text(master.business)),
		_choice("genInfo.company.id.incomeClassification", "trade"),
	]
	given.extend(_shareholder(shareholder) for shareholder in master.shareholders)
	if master.generated is not None:
		given.append(_item(gcd("genInfo.doc.id.generationDate"), master.generated))
	by_concept: dict[str, list[Fact]] = {}
	for fact in given:
		by_concept.setdefault(fact.concept, []).append(fact)
	return tuple(_completed(structure, by_concept))


def check(structure: Structure, master: MasterData, *, reason: str = "") -> tuple[Finding, ...]:
	"""What the master data of the GCD lack or get wrong; every finding holds the E-Bilanz back."""
	taxonomy = structure.taxonomy
	case = structure.case
	findings = [
		Finding(
			code,
			f"„{label}“ fehlt in den Einstellungen der Jahresmeldungen.",
			f"{leitfaden(taxonomy, 'B.14.3.1.16')}; {rule(taxonomy, code)}",
			concept,
		)
		for code, concept, value, label in (
			("170205049", NAME, master.name, "Name des Unternehmens"),
			("170205053", STREET, master.street, "Firmensitz, Straße"),
			("170205052", POSTAL_CODE, master.postal_code, "Firmensitz, Postleitzahl"),
			("170205051", CITY, master.city, "Firmensitz, Ort"),
		)
		if not value.strip()
	]
	texts = [
		(NAME, master.name, "Name des Unternehmens"),
		(STREET, master.street, "Firmensitz, Straße"),
		(HOUSE_NUMBER, master.house_number, "Firmensitz, Hausnummer"),
		(POSTAL_CODE, master.postal_code, "Firmensitz, Postleitzahl"),
		(CITY, master.city, "Firmensitz, Ort"),
		(BUSINESS, master.business, "Geschäftstätigkeit"),
		*(
			(SHAREHOLDER_NAME, shareholder.name, "Name des Gesellschafters")
			for shareholder in master.shareholders
		),
	]
	if not case.kontennachweis:
		texts.append(
			(
				NOT_YET_POSSIBLE,
				reason,
				"Erläuterung, warum die Übermittlung der Kontennachweise noch nicht möglich ist",
			)
		)
	for concept, value, label in texts:
		try:
			transliterate(value)
		except CharsetError as error:
			findings.append(
				Finding(
					"EB-GCD-ZEICHEN",
					f"„{label}“ enthält Zeichen, die ELSTER nicht nimmt: "
					f"{', '.join(describe(character) for character in error.characters)}.",
					ERIC_CHARACTERS,
					concept,
				)
			)
	findings.extend(_numbers(structure, master))
	findings.extend(_previous_fiscal_year(structure, master))
	findings.extend(_version(structure))
	return tuple(findings)


def _numbers(structure: Structure, master: MasterData) -> Iterator[Finding]:
	taxonomy = structure.taxonomy
	source = leitfaden(taxonomy, "B.14.3.1.18")
	if master.steuernummer:
		if not ELSTER_STEUERNUMMER.fullmatch(master.steuernummer):
			yield Finding(
				"EB-STEUERNUMMER",
				f"Die Steuernummer {master.steuernummer} hat nicht die Form von ELSTER: 13 Ziffern, die fünfte eine 0.",
				leitfaden(taxonomy, "B.14.3.1.18, B.14.8"),
				ST13,
			)
		elif master.bundesfinanzamtsnummer and master.bundesfinanzamtsnummer != master.finanzamt:
			yield Finding(
				"EB-FINANZAMT",
				f"Die Bundesfinanzamtsnummer {master.bundesfinanzamtsnummer} ist nicht die der Steuernummer, "
				f"{master.finanzamt}.",
				f"{leitfaden(taxonomy, 'B.2.1')}; {rule(taxonomy, '170205002')}",
				BF4,
			)
		return
	if not structure.case.opening:
		yield Finding(
			"170205025",
			"Die Steuernummer fehlt; ohne sie geht nur eine Eröffnungsbilanz.",
			f"{source}; {rule(taxonomy, '170205025')}",
			ST13,
		)
		return
	finanzamt = master.bundesfinanzamtsnummer or ""
	if not (len(finanzamt) == 4 and finanzamt.isdigit()):
		yield Finding(
			"170205026",
			"Ohne Steuernummer nennt die Eröffnungsbilanz die vierstellige Bundesfinanzamtsnummer ihres Finanzamts.",
			f"{source}; {rule(taxonomy, '170205026')}",
			BF4,
		)
	yield Finding(
		"EB-KENNUNG",
		"Welche Kennung die Kontexte einer Eröffnungsbilanz ohne Steuernummer nennen, ist ungeprüft; die "
		"Eröffnungsbilanz wartet auf die Steuernummer vom Finanzamt.",
		f"{leitfaden(taxonomy, 'B.14.7')}; ERiC-Dokumentation 44.3.6.0, Beispiele der Taxonomie 6.9",
		ST13,
	)


def _previous_fiscal_year(structure: Structure, master: MasterData) -> Iterator[Finding]:
	"""The previous fiscal year of the master data before the fiscal year (Leitfaden B.14.3.1.6); that of a case is
	checked by steuerbote.xbrl.facts.Periods."""
	taxonomy = structure.taxonomy
	if structure.case.prior or master.previous_fiscal_year is None:
		return
	begin, end = master.previous_fiscal_year
	if end < begin:
		yield Finding(
			"170405009",
			f"Das vorhergehende Wirtschaftsjahr endet am {end:%d.%m.%Y}, vor seinem Beginn am {begin:%d.%m.%Y}.",
			f"{leitfaden(taxonomy, 'B.14.3.1.6')}; {rule(taxonomy, '170405009')}",
			PREVIOUS_FISCAL_YEAR_END,
		)
	elif end >= structure.case.periods.fiscal_year_begin:
		yield Finding(
			"170405006",
			f"Das vorhergehende Wirtschaftsjahr endet am {end:%d.%m.%Y}, nicht vor dem Beginn des Wirtschaftsjahres am "
			f"{structure.case.periods.fiscal_year_begin:%d.%m.%Y}.",
			f"{leitfaden(taxonomy, 'B.14.3.1.6')}; {rule(taxonomy, '170405006')}",
			PREVIOUS_FISCAL_YEAR_END,
		)


def _version(structure: Structure) -> Iterator[Finding]:
	"""The fiscal year within the years of the version (Leitfaden B.18): it begins after the day the letter names, and
	it ends before the last day the version serves, a year later for an Eröffnungsbilanz, which may take the
	previous version."""
	taxonomy = structure.taxonomy
	case = structure.case
	periods = case.periods
	try:
		version = version_of(taxonomy.version)
	except UnknownTaxonomyError:
		yield Finding(
			"EB-TAXONOMIE",
			f"Steuerbote kennt die HGB-Taxonomie {taxonomy.version} nicht.",
			"steuerbote/xbrl/versions.py",
			FISCAL_YEAR_BEGIN,
		)
		return
	source = f"{leitfaden(taxonomy, 'B.18')}; {version.letter}"
	if periods.fiscal_year_begin <= version.tolerated_begins_after:
		yield Finding(
			"170205007",
			f"Die HGB-Taxonomie {version.version} gilt für Wirtschaftsjahre, die nach dem "
			f"{version.tolerated_begins_after:%d.%m.%Y} beginnen, nicht für eines ab dem "
			f"{periods.fiscal_year_begin:%d.%m.%Y}.",
			f"{source}; {rule(taxonomy, '170205007')}",
			FISCAL_YEAR_BEGIN,
		)
	last = version.last_ends_before
	code = "170205018"
	if case.opening:
		last, code = last.replace(year=last.year + 1), "170205017"
	if periods.fiscal_year_end >= last:
		yield Finding(
			code,
			f"Die HGB-Taxonomie {version.version} gilt für Wirtschaftsjahre, die vor dem {last:%d.%m.%Y} enden, nicht "
			f"für eines bis zum {periods.fiscal_year_end:%d.%m.%Y}.",
			f"{source}; {rule(taxonomy, code)}",
			gcd("genInfo.report.period.fiscalYearEnd"),
		)


def _item(concept: str, value) -> Item:
	return Item(concept, Period.WIRTSCHAFTSJAHR, value)


def _choice(name: str, *values: str) -> Tuple:
	return choice(gcd(name), *(gcd(f"{name}.{value}") for value in values))


def _text(value: str) -> str | None:
	"""A text in the characters of ELSTER, None for an empty one; one with other characters stays as it is, for
	check() to name them."""
	text = value.strip()
	try:
		return transliterate(text) or None
	except CharsetError:
		return text


def _shareholder(shareholder: Gesellschafter) -> Tuple:
	share = Fraction(shareholder.percent) / 100
	status = SHAREHOLDER_LEGAL_STATUS.get(shareholder.kind)
	return Tuple(
		SHAREHOLDER,
		(
			_item(SHAREHOLDER_NAME, _text(shareholder.name)),
			*(
				_item(gcd(f"genInfo.company.id.shareholder.{part}"), None)
				for part in ("id", "taxnumber", "taxid", "WID")
			),
			_choice(SHAREHOLDER_STATUS, status)
			if status
			else Tuple(
				gcd(SHAREHOLDER_STATUS), (nil(NIL_CHOICES[gcd(SHAREHOLDER_STATUS)], Period.WIRTSCHAFTSJAHR),)
			),
			Tuple(
				SHARE_DIVIDE_KEY,
				(
					_item(f"{SHARE_DIVIDE_KEY}.numerator", str(share.numerator)),
					_item(f"{SHARE_DIVIDE_KEY}.denominator", str(share.denominator)),
				),
			),
		),
	)


def _completed(structure: Structure, given: Mapping[str, list[Fact]]) -> Iterator[Fact]:
	"""The given facts and NIL for every other Mussfeld, in the order of the presentation of the GCD."""
	taxonomy = structure.taxonomy
	required = frozenset(name for name in structure.required if name.startswith(PREFIX))
	for name, _ in taxonomy.presentation[GCD].walk():
		if taxonomy.tuples_of(name):
			continue
		if name in given:
			yield from (_with_parts(taxonomy, fact, required) for fact in given[name])
		elif name in required:
			yield _nil(taxonomy, name, required)


def _with_parts(taxonomy: Taxonomy, fact: Fact, required: frozenset[str]) -> Fact:
	"""A given fact, a tuple with NIL for the parts it lacks."""
	if isinstance(fact, Item):
		return fact
	present = {child.concept for child in fact.children}
	missing = [
		_nil(taxonomy, part, required)
		for part in _parts(taxonomy, fact.concept, required)
		if part not in present
	]
	return Tuple(fact.concept, (*fact.children, *missing))


def _nil(taxonomy: Taxonomy, name: str, required: frozenset[str]) -> Fact:
	"""A Mussfeld without a value: NIL, a tuple with its parts NIL or, for a choice, one Auswahlwert NIL."""
	concept = taxonomy.concepts[name]
	if concept.kind is not Kind.TUPLE:
		return nil(name, Period.WIRTSCHAFTSJAHR)
	if concept.content.group == CHOICE:
		return Tuple(name, (nil(NIL_CHOICES.get(name) or taxonomy.parts(name)[0], Period.WIRTSCHAFTSJAHR),))
	return Tuple(name, tuple(_nil(taxonomy, part, required) for part in _parts(taxonomy, name, required)))


def _parts(taxonomy: Taxonomy, name: str, required: frozenset[str]) -> list[str]:
	"""The parts a tuple holds: its Mussfelder, and for a sequence each part it cannot do without."""
	content = taxonomy.concepts[name].content
	needed = (
		{particle.concept for particle in content.particles if particle.min_occurs}
		if content.group == SEQUENCE
		else set()
	)
	return [part for part in taxonomy.parts(name) if part in required or part in needed]
