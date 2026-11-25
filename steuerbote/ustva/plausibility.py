"""Plausibility of a Voranmeldung: the comparison with earlier periods, and hints from the invoices.

Every Kennzahl comes from the ledger (see calculation.py). This module adds what helps a person check the
Kennzahlen before filing and changes none of them: the Vorperiodenvergleich, which sets each Kennzahl
against the previous period of the same rhythm and against the same period a year earlier, and hints where
the invoices behind the ledger look wrong, where invoices and ledger part ways, or where an account watched
at the hint level has a balance. A hint or a warning never holds a return. An error does (holds): a turnover in Kz 41,
42 or 21 whose customer has no valid USt-IdNr., which costs the exemption (steuerbote.vatid.exemption), and an override
whose ledger amount changed since it was made. Steuerbote cannot tax an invoice anew; the return waits for the invoice
to be corrected or for remarks that say why it is filed nonetheless, as the Zusammenfassende Meldung holds the same
voucher (decision of the maintainer, docs/zm.md [Q16]).

The rules behind the hints on single invoices:

- Kz 41 holds innergemeinschaftliche Lieferungen „an Abnehmer mit Umsatzsteuer-Identifikationsnummer“
  (form USt 1 A 2026, line 19): the goods go „in das übrige Gemeinschaftsgebiet“ and the customer „hat
  gegenüber dem Unternehmer eine ihm von einem anderen Mitgliedstaat erteilte gültige
  Umsatzsteuer-Identifikationsnummer verwendet“ (§ 6a Absatz 1 Satz 1 Nummer 1 and 4 UStG).
- Kz 21 holds the sonstige Leistungen of § 18b Satz 1 Nummer 2 UStG, „für die der in einem anderen
  Mitgliedstaat ansässige Leistungsempfänger die Steuer dort schuldet“; the Zusammenfassende Meldung
  names for them „die Umsatzsteuer-Identifikationsnummer jedes Leistungsempfängers, die ihm in einem
  anderen Mitgliedstaat erteilt worden ist“ (§ 18a Absatz 7 Satz 1 Nummer 3 Buchstabe a UStG).
- Kz 81 and 86 hold taxable turnover at 19 % and 7 %, and the form derives their tax from the base (lines
  13 and 14), so an invoice on their accounts charges that rate. This holds whichever way the return takes the tax of
  these lines (StatutoryTax in calculation.py): the hint checks the invoice, not the return.

The hints on single invoices check a VAT id only for being there; the party's country is that of the address
on the invoice. Whether the BZSt confirmed the USt-IdNr. of a customer behind Kz 41, 42 or 21, how long ago, and
whether it found it valid, vat_id_hints() says from the latest confirmation of each number (§ 18e UStG). The Gemeinschaftsgebiet follows § 1 Absatz 2a UStG: the member states of the European
Union, with Monaco as part of France („Das Fürstentum Monaco gilt als Gebiet der Französischen
Republik“).
"""

from collections.abc import Callable, Iterable, Sequence
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Protocol

from steuerbote.ustva.calculation import AccountBalance, DerivedBase, require_cents
from steuerbote.ustva.kennzahlen import Kennzahl
from steuerbote.ustva.mapping import AccountRule, Mapping, is_account_number
from steuerbote.ustva.period import Period, day_label
from steuerbote.ustva.residence import Finding, Problem, Residence, Source
from steuerbote.ustva.rounding import CENT, EURO, HUNDRED, ZERO, tax_from_base, to_cents
from steuerbote.vatid.exemption import consequence
from steuerbote.vatid.result import Outcome, valid_through
from steuerbote.vatid.ustid import is_plausible, normalize, problem


class Severity(Enum):
	HINT = "Hinweis"
	WARNING = "Warnung"
	ERROR = "Fehler"


class Code(StrEnum):
	EU_WITHOUT_VAT_ID = "EU-OHNE-USTID"
	EU_ADDRESS = "EU-VORLAGE-ADRESSE"
	ZERO_TAX = "NULLSATZ-OHNE-GRUND"
	TAX_DEVIATION = "STEUER-ABWEICHUNG"
	INPUT_TAX_DEVIATION = "VORSTEUER-ABWEICHUNG"
	INVOICES_AND_LEDGER = "ABGLEICH-RECHNUNGEN"
	WATCHED_ACCOUNT = "KONTO-BEOBACHTET"
	PREVIOUS_PERIOD = "ABWEICHUNG-VORPERIODE"
	NO_CATALOGUE = "KEIN-KATALOG"
	MAPPING_UNFIT = "ZUORDNUNG-JAHRGANG"
	VAT_ID_UNCONFIRMED = "USTIDNR-UNGEPRUEFT"
	VAT_ID_STALE = "USTIDNR-VERALTET"
	VAT_ID_INVALID = "USTIDNR-UNGUELTIG"
	TAX_TEMPLATE_WITHOUT_PLACE = "STEUERVORLAGE-OHNE-KENNZAHL"
	REGISTER_DEVIATION = "REGISTER-ABWEICHUNG"
	BASE_FROM_TAX = "GRUNDLAGE-AUS-STEUER"
	BEFORE_START = "VOR-START"
	RESIDENCE_OPEN = "SITZ-OFFEN"
	RESIDENCE_CONFLICT = "SITZ-WIDERSPRUCH"
	EU_SERVICE_OUTSIDE = "KZ46-OHNE-EU-SITZ"
	ACQUISITION_OUTSIDE_EU = "ERWERB-AUS-DRITTLAND"
	OVERRIDE_STALE = "KORREKTUR-UEBERHOLT"
	PERIOD_NOT_ENDED = "ZEITRAUM-NICHT-ABGELAUFEN"
	ZM_WITHOUT_RHYTHM = "ZM-OHNE-RHYTHMUS"
	CORRECTION_UNCHANGED = "BERICHTIGUNG-OHNE-AENDERUNG"


# A turnover that loses its exemption without a valid USt-IdNr. of the customer and an override that hides a change of
# the ledger are errors; a wrong invoice is a warning; a difference that may well be explained, such as a journal entry
# on a revenue account or a quieter month, is a hint.
SEVERITIES: MappingProxyType[Code, Severity] = MappingProxyType(
	{
		Code.EU_WITHOUT_VAT_ID: Severity.ERROR,
		Code.EU_ADDRESS: Severity.WARNING,
		Code.ZERO_TAX: Severity.WARNING,
		Code.TAX_DEVIATION: Severity.WARNING,
		Code.INPUT_TAX_DEVIATION: Severity.WARNING,
		Code.INVOICES_AND_LEDGER: Severity.HINT,
		Code.WATCHED_ACCOUNT: Severity.HINT,
		Code.PREVIOUS_PERIOD: Severity.HINT,
		Code.NO_CATALOGUE: Severity.HINT,
		Code.MAPPING_UNFIT: Severity.HINT,
		Code.BEFORE_START: Severity.HINT,
		Code.VAT_ID_UNCONFIRMED: Severity.HINT,
		Code.VAT_ID_STALE: Severity.HINT,
		Code.VAT_ID_INVALID: Severity.ERROR,
		Code.TAX_TEMPLATE_WITHOUT_PLACE: Severity.HINT,
		Code.REGISTER_DEVIATION: Severity.HINT,
		Code.BASE_FROM_TAX: Severity.HINT,
		Code.RESIDENCE_OPEN: Severity.HINT,
		Code.RESIDENCE_CONFLICT: Severity.HINT,
		Code.EU_SERVICE_OUTSIDE: Severity.WARNING,
		Code.ACQUISITION_OUTSIDE_EU: Severity.WARNING,
		Code.OVERRIDE_STALE: Severity.ERROR,
		Code.PERIOD_NOT_ENDED: Severity.WARNING,
		Code.ZM_WITHOUT_RHYTHM: Severity.WARNING,
		Code.CORRECTION_UNCHANGED: Severity.HINT,
	}
)
# The order of the hints of a return: errors, then warnings, then hints.
SEVERITY_ORDER: MappingProxyType[Severity, int] = MappingProxyType(
	{Severity.ERROR: 0, Severity.WARNING: 1, Severity.HINT: 2}
)
NO_VAT_ID_ADVICE = "Berichtige die Rechnung, oder begründe in den Anmerkungen, warum die Voranmeldung trotzdem so abgegeben wird."
INVALID_ADVICE = (
	"Belegt eine frühere Bestätigung die Gültigkeit am Tag des Umsatzes, begründe das in den Anmerkungen; sonst "
	"berichtige die Rechnung."
)
MALFORMED_ADVICE = (
	"Berichtige die USt-IdNr. in der Rechnung, oder begründe in den Anmerkungen, warum die Voranmeldung trotzdem so "
	"abgegeben wird."
)

EU_KENNZAHLEN = ("41", "21")
STATUTORY_RATE_KENNZAHLEN = ("81", "86")
# The bases an invoice books: sales on income accounts, § 13b services on expense accounts.
SALES_KENNZAHLEN = ("81", "86", "41", "21", "45")
PURCHASE_KENNZAHLEN = ("46", "84")
# Books may round the tax of each item, so a line of several items may differ from its rate by a cent.
TAX_TOLERANCE_PER_LINE = CENT
# Invoice amounts are exact; the hint is about turnover the invoices do not explain, not about cents.
RECONCILIATION_TOLERANCE = EURO
GERMANY = "DE"


@dataclass(frozen=True, slots=True)
class MemberState:
	"""A member state: ISO 3166-1 code, its name as ERPNext names the Country, and its German name."""

	code: str
	country: str
	german: str


# The 27 member states of the European Union in 2026, in the protocol order of the EU: Art. 52 Absatz 1 EUV,
# without the United Kingdom, to which the treaties no longer apply since 1 February 2020 (Art. 50 Absatz 3
# EUV and the withdrawal agreement, ABl. L 29 of 31 January 2020).
EU_MEMBER_STATES: tuple[MemberState, ...] = (
	MemberState("BE", "Belgium", "Belgien"),
	MemberState("BG", "Bulgaria", "Bulgarien"),
	MemberState("CZ", "Czech Republic", "Tschechien"),
	MemberState("DK", "Denmark", "Dänemark"),
	MemberState("DE", "Germany", "Deutschland"),
	MemberState("EE", "Estonia", "Estland"),
	MemberState("IE", "Ireland", "Irland"),
	MemberState("GR", "Greece", "Griechenland"),
	MemberState("ES", "Spain", "Spanien"),
	MemberState("FR", "France", "Frankreich"),
	MemberState("HR", "Croatia", "Kroatien"),
	MemberState("IT", "Italy", "Italien"),
	MemberState("CY", "Cyprus", "Zypern"),
	MemberState("LV", "Latvia", "Lettland"),
	MemberState("LT", "Lithuania", "Litauen"),
	MemberState("LU", "Luxembourg", "Luxemburg"),
	MemberState("HU", "Hungary", "Ungarn"),
	MemberState("MT", "Malta", "Malta"),
	MemberState("NL", "Netherlands", "Niederlande"),
	MemberState("AT", "Austria", "Österreich"),
	MemberState("PL", "Poland", "Polen"),
	MemberState("PT", "Portugal", "Portugal"),
	MemberState("RO", "Romania", "Rumänien"),
	MemberState("SI", "Slovenia", "Slowenien"),
	MemberState("SK", "Slovakia", "Slowakei"),
	MemberState("FI", "Finland", "Finnland"),
	MemberState("SE", "Sweden", "Schweden"),
)
# Territory that § 1 Absatz 2a Satz 2 UStG counts as that of a member state: code, name in ERPNext, state.
COUNTED_AS_MEMBER_STATE: tuple[tuple[str, str, str], ...] = (("MC", "Monaco", "FR"),)


def _member_states_by_key() -> MappingProxyType[str, MemberState]:
	by_key = {key.casefold(): state for state in EU_MEMBER_STATES for key in (state.code, state.country)}
	for code, country, state_code in COUNTED_AS_MEMBER_STATE:
		by_key[code.casefold()] = by_key[country.casefold()] = by_key[state_code.casefold()]
	return MappingProxyType(by_key)


_MEMBER_STATES = _member_states_by_key()


def member_state(country: str | None) -> MemberState | None:
	"""The member state of a country given by its ISO code or its name in ERPNext; None outside the EU."""
	return _MEMBER_STATES.get((country or "").strip().casefold())


@dataclass(frozen=True, slots=True)
class InvoiceLine:
	"""What one submitted invoice books on one account, and the party it is made out to.

	Amounts are in company currency and in cents: ``net_amount`` the net of the invoice's items on the
	account, ``tax_amount`` the tax the invoice charges on these items, both negative on a return.
	``party_country`` is the country of the invoice's address, as ERPNext names it or as an ISO code, and
	None without an address; ``party_tax_id`` is the party's VAT id.
	"""

	voucher_type: str
	voucher_no: str
	posting_date: date
	party: str
	party_country: str | None
	party_tax_id: str | None
	account_number: str
	net_amount: Decimal
	tax_amount: Decimal
	is_return: bool = False

	def __post_init__(self) -> None:
		if not is_account_number(self.account_number):
			raise ValueError(f"{self.account_number!r} is not an account number")
		require_cents(self.net_amount)
		require_cents(self.tax_amount)

	@property
	def document(self) -> str:
		return f"{'Gutschrift' if self.is_return else 'Rechnung'} {self.voucher_no}"


@dataclass(frozen=True, slots=True)
class Hint:
	"""One sentence in German for the person who files the return, and the voucher and party it is about."""

	code: Code
	text: str
	voucher_type: str = ""
	voucher_no: str = ""
	party: str = ""

	@property
	def severity(self) -> Severity:
		return SEVERITIES[self.code]


class Figures(Protocol):
	"""Writes the figures of a hint the way the site shows numbers, amounts in the company's currency."""

	def money(self, amount: Decimal) -> str: ...

	def percent(self, value: Decimal) -> str: ...


def sales_accounts(mapping: Mapping) -> tuple[str, ...]:
	"""The accounts whose sales invoices the hints read."""
	return tuple(rule.account_number for rule in mapping.rules if rule.kennzahl in SALES_KENNZAHLEN)


def purchase_accounts(mapping: Mapping) -> tuple[str, ...]:
	"""The accounts whose purchase invoices the hints read: the services of § 13b UStG."""
	return tuple(rule.account_number for rule in mapping.rules if rule.kennzahl in PURCHASE_KENNZAHLEN)


def invoice_hints(lines: Iterable[InvoiceLine], mapping: Mapping, figures: Figures) -> list[Hint]:
	"""Hints on single invoices, in the order of their lines.

	An invoice in Kz 21 or 41 gets one hint per Kennzahl, with its net amount there, when its customer has
	no VAT id or its address lies in Germany, outside the EU or nowhere. A line on an account of Kz 81 or 86
	gets a hint when it charges no tax, or tax that differs from the rate of its Kennzahl by more than a cent.
	"""
	rules = _rules(mapping)
	lines = [line for line in lines if line.account_number in rules]
	eu_totals: dict[tuple[str, str, str], Decimal] = {}
	for line in lines:
		kennzahl = rules[line.account_number].kennzahl
		if kennzahl in EU_KENNZAHLEN:
			key = (line.voucher_type, line.voucher_no, kennzahl)
			eu_totals[key] = eu_totals.get(key, ZERO) + line.net_amount
	found: list[Hint] = []
	for line in lines:
		rule = rules[line.account_number]
		if rule.kennzahl in EU_KENNZAHLEN:
			total = eu_totals.pop((line.voucher_type, line.voucher_no, rule.kennzahl), None)
			if total is not None:
				found.extend(_eu_hints(line, rule.kennzahl, total, figures))
		elif rule.kennzahl in STATUTORY_RATE_KENNZAHLEN:
			hint = _tax_hint(line, rule.kennzahl, mapping.rate_for(rule), figures)
			if hint is not None:
				found.append(hint)
	return found


def _rules(mapping: Mapping) -> dict[str, AccountRule]:
	return {rule.account_number: rule for rule in mapping.rules}


def _eu_hints(line: InvoiceLine, kennzahl: str, net: Decimal, figures: Figures) -> list[Hint]:
	booked = f"{line.document} über {figures.money(net)} geht in Kz {kennzahl} ein"
	customer = f"des Kunden {line.party}"
	found: list[Hint] = []
	if not (line.party_tax_id or "").strip():
		text = (
			f"{_sentence(f'{booked}, aber der Kunde {line.party} hat keine USt-IdNr')} "
			f"{consequence(kennzahl)} {NO_VAT_ID_ADVICE}"
		)
		found.append(_about(line, Code.EU_WITHOUT_VAT_ID, text))
	state = member_state(line.party_country)
	if not (line.party_country or "").strip():
		address = f"die Rechnung nennt keine Anschrift {customer}"
	elif state is None:
		address = f"die Anschrift {customer} liegt außerhalb der EU ({line.party_country})"
	elif state.code == GERMANY:
		address = f"die Anschrift {customer} liegt in {state.german}"
	else:
		return found
	found.append(_about(line, Code.EU_ADDRESS, _sentence(f"{booked}, aber {address}")))
	return found


def _tax_hint(line: InvoiceLine, kennzahl: str, rate: Decimal, figures: Figures) -> Hint | None:
	issuer = f"{line.document} an {line.party}"
	net = f"{figures.money(line.net_amount)} auf Konto {line.account_number} (Kz {kennzahl})"
	if not line.tax_amount:
		if not line.net_amount:
			return None
		return _about(line, Code.ZERO_TAX, f"{issuer} bucht {net} ohne Umsatzsteuer.")
	if abs(line.tax_amount - line.net_amount * rate / HUNDRED) <= TAX_TOLERANCE_PER_LINE:
		return None
	charged = figures.money(line.tax_amount)
	expected = figures.money(tax_from_base(line.net_amount, rate))
	text = f"{issuer} berechnet für {net} {charged} Umsatzsteuer, {rate} % wären {expected}."
	return _about(line, Code.TAX_DEVIATION, text)


def _about(line: InvoiceLine, code: Code, text: str) -> Hint:
	return Hint(code, text, line.voucher_type, line.voucher_no, line.party)


def _sentence(text: str) -> str:
	"""A sentence ends with one full stop, also after a name such as „Muster B.V.“."""
	return text if text.endswith(".") else f"{text}."


def reconciliation_hints(
	lines: Iterable[InvoiceLine],
	ledger: ReadOnlyMapping[str, Decimal],
	mapping: Mapping,
	figures: Figures,
	derived: Iterable[DerivedBase] = (),
) -> list[Hint]:
	"""Invoices against the ledger: per base an invoice books, the net of the invoices and the ledger amount.

	``ledger`` holds the exact amounts the ledger gives each Kennzahl, before rounding. A difference of
	more than a euro gets a hint, in the order of the form: a journal entry on a revenue account or an
	invoice on an account of another Kennzahl explains one as well as a missing invoice. The invoices count the
	accounts of a Kennzahl's rules, so the ``derived`` bases, which sit on none of them, leave the ledger amount.
	"""
	ledger = dict(ledger)
	for base in derived:
		ledger[base.kennzahl] = ledger.get(base.kennzahl, ZERO) - base.base
	rules = _rules(mapping)
	invoiced = dict.fromkeys((*SALES_KENNZAHLEN, *PURCHASE_KENNZAHLEN), ZERO)
	for line in lines:
		rule = rules.get(line.account_number)
		if rule is not None and rule.kennzahl in invoiced:
			invoiced[rule.kennzahl] += line.net_amount
	found: list[Hint] = []
	for kennzahl in (number for number in mapping.catalogue if number in invoiced):
		booked = ledger.get(kennzahl, ZERO)
		if abs(invoiced[kennzahl] - booked) > RECONCILIATION_TOLERANCE:
			amounts = f"netto {figures.money(invoiced[kennzahl])}, das Hauptbuch {figures.money(booked)}"
			text = f"Kz {kennzahl}: Die Rechnungen des Zeitraums ergeben {amounts}."
			found.append(Hint(Code.INVOICES_AND_LEDGER, text))
	return found


def watched_account_hints(
	balances: Iterable[AccountBalance], names: ReadOnlyMapping[str, str], figures: Figures
) -> list[Hint]:
	"""A hint per account watched at the hint level that has a balance, in the order of ``balances``.

	``names`` holds the names of the accounts by number, as far as the caller knows them. The hint names
	the account, its debits, its credits and the balance, which goes into no Kennzahl.
	"""
	found: list[Hint] = []
	for balance in balances:
		if not balance.balance:
			continue
		name = names.get(balance.account_number)
		account = f"Konto {balance.account_number} {name}" if name else f"Konto {balance.account_number}"
		side = "Soll" if balance.balance > ZERO else "Haben"
		totals = f"Soll {figures.money(balance.debit)}, Haben {figures.money(balance.credit)}"
		text = (
			f"{account} hat einen Saldo von {figures.money(abs(balance.balance))} im {side} ({totals}), "
			"geht aber in keine Kennzahl ein."
		)
		found.append(Hint(Code.WATCHED_ACCOUNT, text))
	return found


def derived_base_hints(derived: Iterable[DerivedBase], figures: Figures) -> list[Hint]:
	"""A hint per base taken from the tax, because the lines of its voucher did not tell it, in the order given.

	The ledger keys a voucher as "<voucher type>:<voucher name>" (steuerbote.ledger), and the hint names both.
	"""
	found: list[Hint] = []
	for base in derived:
		if not base.from_tax:
			continue
		books = "Der Beleg bucht" if base.voucher is not None else "Die Buchungen ohne Beleg buchen"
		booked = (
			"aber nichts auf ein Grundlagenkonto"
			if base.voucher is not None
			else "aber nichts auf Grundlagenkonten"
		)
		lines = (
			"seine übrigen Buchungszeilen ergeben"
			if base.voucher is not None
			else "ihre übrigen Buchungszeilen ergeben"
		)
		text = (
			f"Kz {base.kennzahl}: {books} {figures.money(base.tax)} Steuer auf „{base.label}“, {booked}, und {lines} "
			"die Bemessungsgrundlage nicht eindeutig. Steuerbote hat sie aus der Steuer zurückgerechnet "
			f"({figures.money(base.tax)} zu {figures.percent(base.rate)}) und meldet {figures.money(base.base)}; "
			"bitte prüfen Sie sie am Beleg."
		)
		voucher_type, _, voucher_no = (base.voucher or "").partition(":")
		found.append(Hint(Code.BASE_FROM_TAX, text, voucher_type, voucher_no))
	return found


# The decisions of residence.place() and the checks of calculate() on sections C and D as the hints say them.
RESIDENCE_CODES: MappingProxyType[Problem, Code] = MappingProxyType(
	{
		Problem.NO_SUPPLIER: Code.RESIDENCE_OPEN,
		Problem.SUPPLIERS_DISAGREE: Code.RESIDENCE_OPEN,
		Problem.NO_COUNTRY: Code.RESIDENCE_OPEN,
		Problem.ADDRESS_ELSEWHERE: Code.RESIDENCE_CONFLICT,
		Problem.VAT_ID_PREFIX: Code.RESIDENCE_CONFLICT,
		Problem.TEMPLATE_OTHER_FROM_MEMBER_STATE: Code.RESIDENCE_CONFLICT,
		Problem.STATED_EU_SERVICE_OUTSIDE: Code.EU_SERVICE_OUTSIDE,
		Problem.EU_SERVICE_ACCOUNT_OUTSIDE: Code.EU_SERVICE_OUTSIDE,
		Problem.ACQUISITION_OUTSIDE_EU: Code.ACQUISITION_OUTSIDE_EU,
	}
)
RESIDENCES: MappingProxyType[str, str] = MappingProxyType(
	{
		Residence.DOMESTIC: "im Inland",
		Residence.OTHER_MEMBER_STATE: "im übrigen Gemeinschaftsgebiet",
		Residence.THIRD_COUNTRY: "im Drittlandsgebiet",
	}
)
STATED_BY: MappingProxyType[str, str] = MappingProxyType(
	{
		Source.VOUCHER: "Der Beleg ist",
		Source.SUPPLIER: "Der Lieferant ist",
		Source.TAX_TEMPLATE: "Die Steuervorlage des Belegs ist",
	}
)
CLASSIFY = (
	"Ordne den Beleg oder den Lieferanten in der Kontenzuordnung unter „Einordnung nach § 13b UStG“ ein"
)


def residence_hints(findings: Iterable[Finding]) -> list[Hint]:
	"""A hint per finding of calculate() on the suppliers of sections C and D, in the order given.

	The ledger keys a voucher as "<voucher type>:<voucher name>" (steuerbote.ledger), and the hint names both.
	"""
	found: list[Hint] = []
	for finding in findings:
		voucher_type, _, voucher_no = (finding.voucher or "").partition(":")
		code = RESIDENCE_CODES[finding.problem]
		found.append(
			Hint(code, _sentence(_residence_text(finding)), voucher_type, voucher_no, finding.supplier)
		)
	return found


def _residence_text(finding: Finding) -> str:
	kz, other, supplier, facts = finding.kennzahl, finding.alternative, finding.supplier, finding.facts
	went = f"Steuerbote meldet die Bemessungsgrundlage in Kz {kz}"
	match finding.problem:
		case Problem.NO_SUPPLIER:
			return (
				f"Kz {kz}: Der Beleg bucht Steuer nach § 13b UStG ohne Grundlagenkonto und nennt keinen Lieferanten; "
				f"{went}, der Vorgabe der Verprobung. Ist es eine sonstige Leistung nach § 3a Abs. 2 UStG eines im "
				f"übrigen Gemeinschaftsgebiet ansässigen Unternehmers, gehört sie in Kz {other}: {CLASSIFY}"
			)
		case Problem.SUPPLIERS_DISAGREE:
			where = ", ".join(
				f"{name} {RESIDENCES[residence]}"
				for name, residence in zip(facts[::2], facts[1::2], strict=True)
			)
			return f"Kz {kz}: Die Lieferanten des Belegs sind an verschiedenen Orten ansässig ({where}); {went}. {CLASSIFY}"
		case Problem.NO_COUNTRY:
			prefix = (
				f"; seine USt-IdNr. beginnt mit {facts[0]}, das zeigt aber nur eine Registrierung"
				if facts
				else ""
			)
			return (
				f"Kz {kz}: Beim Lieferanten {supplier} ist weder ein Land noch eine Anschrift mit Land gepflegt{prefix}. "
				f"{went}. Pflege das Land des Lieferanten, oder {CLASSIFY[0].lower()}{CLASSIFY[1:]}"
			)
		case Problem.ADDRESS_ELSEWHERE:
			return (
				f"Kz {kz}: Beim Lieferanten {supplier} steht als Land {facts[0]}, seine Anschrift liegt aber in "
				f"{facts[1]}. Steuerbote folgt dem Land; bitte prüfen Sie, wo der Lieferant ansässig ist"
			)
		case Problem.VAT_ID_PREFIX:
			return (
				f"Kz {kz}: Der Lieferant {supplier} hat das Land {facts[0]}, seine USt-IdNr. beginnt aber mit "
				f"{facts[1]}. Steuerbote folgt dem Land, denn ansässig ist ein Unternehmer, wo er Sitz, "
				"Geschäftsleitung oder eine Betriebsstätte hat (§ 13b Abs. 7 UStG), nicht wo er registriert ist; "
				"bitte prüfen Sie den Sitz am Beleg"
			)
		case Problem.TEMPLATE_OTHER_FROM_MEMBER_STATE:
			return (
				f"Kz {kz}: Die Steuervorlage {facts[0]} ist als andere Leistung nach § 13b Abs. 2 UStG eingeordnet, der "
				f"Lieferant {supplier} ist aber im übrigen Gemeinschaftsgebiet ansässig. Ist es eine sonstige Leistung "
				f"nach § 3a Abs. 2 UStG, gehört sie in Kz {other}: {CLASSIFY}"
			)
		case Problem.STATED_EU_SERVICE_OUTSIDE:
			return (
				f"Kz {kz}: {STATED_BY[facts[0]]} als sonstige Leistung aus dem übrigen Gemeinschaftsgebiet eingeordnet, "
				f"der Lieferant {supplier} ist laut Stammdaten aber {RESIDENCES[facts[1]]} ansässig. Kz {kz} setzt einen "
				"im übrigen Gemeinschaftsgebiet ansässigen Unternehmer voraus (§ 13b Abs. 1 UStG); bitte prüfen Sie die "
				"Einordnung"
			)
		case Problem.EU_SERVICE_ACCOUNT_OUTSIDE:
			reason = (
				f"ist laut Stammdaten aber {RESIDENCES[facts[1]]} ansässig"
				if facts[0] in (Source.COUNTRY, Source.ADDRESS)
				else "ist aber als andere Leistung nach § 13b Abs. 2 UStG eingeordnet"
			)
			return (
				f"Kz {kz}: Der Beleg bucht auf ein Grundlagenkonto von Kz {kz}, der Lieferant {supplier} {reason}. "
				f"Kz {kz} nimmt nur sonstige Leistungen nach § 3a Abs. 2 UStG eines im übrigen Gemeinschaftsgebiet "
				f"ansässigen Unternehmers auf (§ 13b Abs. 1 UStG), alle anderen gehören in Kz {other}"
			)
	return (
		f"Der Beleg bucht Umsatzsteuer aus innergemeinschaftlichem Erwerb, der Lieferant {supplier} ist laut Stammdaten "
		f"aber im Drittlandsgebiet ansässig ({facts[0]}). Ein innergemeinschaftlicher Erwerb setzt voraus, dass der "
		"Gegenstand aus einem anderen Mitgliedstaat kommt (§ 1a Abs. 1 Nr. 1 UStG); kommt er aus dem Drittlandsgebiet, "
		"ist es eine Einfuhr. Bitte prüfe den Beleg"
	)


@dataclass(frozen=True, slots=True)
class EarlierPeriod:
	"""A period to compare with and its reported amounts by Kennzahl.

	``values`` is None when Steuerbote cannot compute the period; ``missing`` then says why: no catalogue
	of Kennzahlen for its year (NO_CATALOGUE), a mapping that does not fit the form of that year
	(MAPPING_UNFIT), or a period before the start of the books in Steuerbote, whose ledger holds only the opening
	balances (BEFORE_START, steuerbote/setup/start.py).
	"""

	period: Period
	values: ReadOnlyMapping[str, Decimal] | None
	missing: Code = Code.NO_CATALOGUE

	@property
	def known(self) -> bool:
		return self.values is not None

	def value(self, kennzahl: str) -> Decimal | None:
		return None if self.values is None else self.values.get(kennzahl, ZERO)


@dataclass(frozen=True, slots=True)
class ComparisonRow:
	"""A Kennzahl of the Vorperiodenvergleich; a value of a period Steuerbote cannot compute is None."""

	kennzahl: str
	label: str
	current: Decimal
	previous_period: Decimal | None
	previous_year: Decimal | None
	difference: Decimal | None
	difference_percent: Decimal | None
	flagged: bool


@dataclass(frozen=True, slots=True)
class Comparison:
	previous_period: EarlierPeriod
	previous_year: EarlierPeriod
	rows: tuple[ComparisonRow, ...]


def compare(
	current: ReadOnlyMapping[str, Decimal],
	previous_period: EarlierPeriod,
	previous_year: EarlierPeriod,
	catalogue: ReadOnlyMapping[str, Kennzahl],
	deviates: Callable[[Decimal, Decimal], bool],
) -> Comparison:
	"""The Vorperiodenvergleich: a row per Kennzahl of any of the three periods, in the order of the form.

	``current`` holds the amounts the return files. The difference and its share are those to the previous
	period; the share is in percent of the earlier amount, rounded to hundredths, and missing without an
	earlier amount. A row is flagged when ``deviates(current, previous)`` says its change to the previous
	period is auffällig. Kennzahlen that the form of the return's year does not know are left out.
	"""
	numbers = {*current, *(previous_period.values or ()), *(previous_year.values or ())}
	rows = tuple(
		_row(catalogue[number], current.get(number, ZERO), previous_period, previous_year, deviates)
		for number in catalogue
		if number in numbers
	)
	return Comparison(previous_period, previous_year, rows)


def _row(
	kennzahl: Kennzahl,
	current: Decimal,
	previous_period: EarlierPeriod,
	previous_year: EarlierPeriod,
	deviates: Callable[[Decimal, Decimal], bool],
) -> ComparisonRow:
	earlier = previous_period.value(kennzahl.number)
	difference = None if earlier is None else current - earlier
	share = to_cents(difference * HUNDRED / abs(earlier)) if earlier else None
	return ComparisonRow(
		kennzahl=kennzahl.number,
		label=kennzahl.label,
		current=current,
		previous_period=earlier,
		previous_year=previous_year.value(kennzahl.number),
		difference=difference,
		difference_percent=share,
		flagged=earlier is not None and deviates(current, earlier),
	)


# Why a compared period stays empty, as the start of its hint.
MISSING: MappingProxyType[Code, str] = MappingProxyType(
	{
		Code.NO_CATALOGUE: "Kein Katalog für {0}",
		Code.MAPPING_UNFIT: "Die Kontenzuordnung passt nicht zum Vordruck {0}",
		Code.BEFORE_START: "Vor dem Start der Bücher in Steuerbote",
	}
)


def comparison_hints(comparison: Comparison, figures: Figures) -> list[Hint]:
	"""A hint per auffällige Kennzahl, then one per reason and year that leaves a compared period empty."""
	previous = comparison.previous_period.period
	found = [_deviation_hint(row, previous, figures) for row in comparison.rows if row.flagged]
	unknown = [
		earlier for earlier in (comparison.previous_period, comparison.previous_year) if not earlier.known
	]
	for missing, year in sorted({(earlier.missing, earlier.period.year) for earlier in unknown}):
		periods = " und ".join(
			earlier.period.label
			for earlier in unknown
			if (earlier.missing, earlier.period.year) == (missing, year)
		)
		found.append(
			Hint(missing, f"{MISSING[missing].format(year)}: Der Vergleich mit {periods} bleibt leer.")
		)
	return found


def _deviation_hint(row: ComparisonRow, previous: Period, figures: Figures) -> Hint:
	"""A flagged row has an amount of the previous period, and a share unless that amount is zero."""
	direction = "über" if row.difference > ZERO else "unter"
	share = "" if row.difference_percent is None else f" um {figures.percent(abs(row.difference_percent))}"
	earlier = f"der Vorperiode {previous.label} ({figures.money(row.previous_period)})"
	text = f"Kz {row.kennzahl} liegt mit {figures.money(row.current)}{share} {direction} {earlier}."
	return Hint(Code.PREVIOUS_PERIOD, text)


def hints(
	comparison: Comparison,
	lines: Sequence[InvoiceLine],
	ledger: ReadOnlyMapping[str, Decimal],
	mapping: Mapping,
	figures: Figures,
	watched: Iterable[AccountBalance] = (),
	names: ReadOnlyMapping[str, str] = MappingProxyType({}),
	derived: Iterable[DerivedBase] = (),
	findings: Iterable[Finding] = (),
) -> tuple[Hint, ...]:
	"""Every hint of a return: the errors first, then the warnings, then the hints; each kind in the order it is found.

	The invoices come first, then their reconciliation with the ledger, then the balances of the accounts
	watched at the hint level (``watched``, named after ``names``), then the bases taken from the tax of their
	voucher (``derived``, calculation.derive_bases), then the findings on the suppliers of sections C and D
	(``findings``, UstvaResult.findings), then the comparison.
	"""
	derived = tuple(derived)
	found = [
		*invoice_hints(lines, mapping, figures),
		*reconciliation_hints(lines, ledger, mapping, figures, derived),
		*watched_account_hints(watched, names, figures),
		*derived_base_hints(derived, figures),
		*residence_hints(findings),
		*comparison_hints(comparison, figures),
	]
	return tuple(sorted(found, key=_rank))


def _rank(hint: Hint) -> int:
	return SEVERITY_ORDER[hint.severity]


def holds(found: Iterable[Hint]) -> bool:
	"""Whether an error among the hints holds the return back from „Bereit“."""
	return any(hint.severity is Severity.ERROR for hint in found)


# The Kennzahlen whose turnover a customer takes under a USt-IdNr. another member state issued, in the order of the
# form USt 1 A 2026: Kz 41 (line 19), Kz 42 (line 33) and Kz 21 (line 35). The Zusammenfassende Meldung names the
# number behind each of them (§ 18a Absatz 7 Satz 1 Nummer 1, 4 and 3, each Buchstabe a, UStG).
VAT_ID_KENNZAHLEN = ("41", "42", "21")
VAT_ID_CODES: frozenset[Code] = frozenset({Code.VAT_ID_UNCONFIRMED, Code.VAT_ID_STALE, Code.VAT_ID_INVALID})
# No source names an age: the BZSt confirms for the moment of the query, and a confirmation later than the supply
# does not show the Sorgfalt of § 6a Absatz 4 UStG (UStAE 6a.8 Abs. 6 Satz 1). The default is about a
# Kalendervierteljahr, the Voranmeldungszeitraum of § 18 Absatz 2 Satz 1 UStG; the VAT Return Settings change it.
DEFAULT_CONFIRMATION_AGE = 90
CONFIRM_ACTION = "„USt-IdNrn. prüfen“"


class VatIdUse(Protocol):
	"""A voucher behind Kz 41, 42 or 21 as the hints on USt-IdNrn. read it, such as a VoucherAmount of
	steuerbote.zm.lines: the USt-IdNr. under which its customer takes the turnover, as ERPNext keeps it, the name of
	the customer and the Kennzahl."""

	@property
	def vat_id(self) -> str | None: ...

	@property
	def party(self) -> str | None: ...

	@property
	def kennzahl(self) -> str: ...


@dataclass(frozen=True, slots=True)
class LatestConfirmation:
	"""The latest confirmation of a USt-IdNr. in the Bestätigungsverfahren (§ 18e UStG): the day of its query, what
	the service found and, for a number it found not valid then, the validity the BZSt named (gueltigAb,
	gueltigBis)."""

	asked_on: date
	outcome: Outcome
	valid_from: date | None = None
	valid_until: date | None = None


def confirmable(uses: Iterable[VatIdUse]) -> list[str]:
	"""The USt-IdNrn. of the vouchers that the BZSt can confirm, written as a confirmation keeps them, each once and
	in order."""
	return sorted({normalize(use.vat_id) for use in _with_vat_ids(uses) if is_plausible(use.vat_id)})


def _with_vat_ids(uses: Iterable[VatIdUse]) -> list[VatIdUse]:
	return [use for use in uses if use.kennzahl in VAT_ID_KENNZAHLEN and (use.vat_id or "").strip()]


def vat_id_hints(
	uses: Iterable[VatIdUse],
	latest: ReadOnlyMapping[str, LatestConfirmation],
	period: Period,
	max_age: int,
) -> list[Hint]:
	"""A hint per USt-IdNr. behind Kz 41, 42 and 21 of the period whose confirmation is missing, out of date or found
	it invalid, in the order of the numbers; a number confirmed lately gets none.

	``latest`` holds the latest confirmation by the number as a confirmation keeps it. The BZSt confirms a number
	for the moment of the query („Bestätigungen für zurückliegende Zeitpunkte oder Zeiträume sind nicht möglich.“,
	BZSt, Fragen und Antworten zur USt-IdNr.), so a confirmation is out of date when it lies more than ``max_age``
	days before the end of the period; one after the end is current. A number the BZSt found not valid counts as
	confirmed when the answer shows it valid all through the period (valid_through). A number without any answer
	has no confirmation, and one the BZSt cannot confirm at all is invalid as it stands.
	"""
	if max_age < 0:
		raise ValueError(f"the age of a confirmation is a number of days from 0 on, not {max_age} days")
	written: dict[str, str] = {}
	parties: dict[str, str] = {}
	kennzahlen: dict[str, set[str]] = {}
	for use in _with_vat_ids(uses):
		number = normalize(use.vat_id)
		written.setdefault(number, use.vat_id.strip())
		kennzahlen.setdefault(number, set()).add(use.kennzahl)
		if not parties.get(number):
			parties[number] = (use.party or "").strip()
	found = []
	for number in sorted(written):
		finding = _finding(number, latest.get(number), period, max_age)
		if finding is not None:
			code, predicate = finding
			subject = _subject(number, written[number], parties[number], kennzahlen[number])
			if code is Code.VAT_ID_INVALID:
				first = next(kennzahl for kennzahl in VAT_ID_KENNZAHLEN if kennzahl in kennzahlen[number])
				advice = MALFORMED_ADVICE if problem(number) is not None else INVALID_ADVICE
				predicate = f"{predicate} {consequence(first)} {advice}"
			found.append(Hint(code, f"{subject} {predicate}", party=parties[number]))
	return found


def _subject(number: str, written: str, party: str, kennzahlen: set[str]) -> str:
	shown = number if is_plausible(written) else f"„{written}“"
	customer = f" des Kunden {party}" if party else ""
	numbers = [kennzahl for kennzahl in VAT_ID_KENNZAHLEN if kennzahl in kennzahlen]
	listed = numbers[0] if len(numbers) == 1 else f"{', '.join(numbers[:-1])} und {numbers[-1]}"
	return f"Die USt-IdNr. {shown}{customer} (Kz {listed})"


def _finding(
	number: str, confirmation: LatestConfirmation | None, period: Period, max_age: int
) -> tuple[Code, str] | None:
	"""The code and the rest of the sentence of the hint on a number, None for a number confirmed lately."""
	reason = problem(number)
	if reason is not None:
		return Code.VAT_ID_INVALID, f"lässt sich nicht bestätigen: {reason}"
	if confirmation is None:
		return (
			Code.VAT_ID_UNCONFIRMED,
			f"ist nicht bestätigt. {CONFIRM_ACTION} lässt sie beim BZSt bestätigen.",
		)
	day = day_label(confirmation.asked_on)
	if confirmation.outcome is Outcome.UNKNOWN:
		unanswered = f"ist nicht bestätigt: Die Bestätigungsabfrage vom {day} ergab kein Ergebnis."
		return Code.VAT_ID_UNCONFIRMED, f"{unanswered} {CONFIRM_ACTION} fragt erneut."
	if confirmation.outcome is Outcome.INVALID and not valid_through(
		confirmation.valid_from, confirmation.valid_until, period.start, period.end
	):
		return Code.VAT_ID_INVALID, f"ist laut Bestätigungsabfrage vom {day} ungültig."
	age = (period.end - confirmation.asked_on).days
	if age <= max_age:
		return None
	stale = (
		f"ist zuletzt am {day} bestätigt worden, {age} Tage vor dem Ende des Voranmeldungszeitraums {period.label}; "
		f"die Einstellungen lassen höchstens {max_age} Tage zu."
	)
	return Code.VAT_ID_STALE, f"{stale} {CONFIRM_ACTION} fragt erneut."


def merged(*groups: Iterable[Hint]) -> tuple[Hint, ...]:
	"""The hints of several sources as one list, as hints() orders its own: the errors first, then the warnings, then
	the hints, each kind in the order of the sources and within each source in its order."""
	return tuple(sorted((hint for group in groups for hint in group), key=_rank))
