"""Plausibility of a Voranmeldung: the comparison with earlier periods, and hints from the invoices.

Every Kennzahl comes from the ledger (see calculation.py). This module adds what helps a person check the
Kennzahlen before filing and changes none of them: the Vorperiodenvergleich, which sets each Kennzahl
against the previous period of the same rhythm and against the same period a year earlier, and hints where
the invoices behind the ledger look wrong or where invoices and ledger part ways. A hint never holds a
return; whether a return is ready stays with the Verprobung and the watched accounts.

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
  13 and 14), so an invoice on their accounts charges that rate.

A VAT id is only checked for being there, not for being valid; the party's country is that of the address
on the invoice. The Gemeinschaftsgebiet follows § 1 Absatz 2a UStG: the member states of the European
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

from steuerbote.ustva.calculation import require_cents
from steuerbote.ustva.kennzahlen import Kennzahl
from steuerbote.ustva.mapping import AccountRule, Mapping, is_account_number
from steuerbote.ustva.period import Period
from steuerbote.ustva.rounding import CENT, EURO, HUNDRED, ZERO, tax_from_base, to_cents


class Severity(Enum):
	HINT = "Hinweis"
	WARNING = "Warnung"


class Code(StrEnum):
	EU_WITHOUT_VAT_ID = "EU-OHNE-USTID"
	EU_ADDRESS = "EU-VORLAGE-ADRESSE"
	ZERO_TAX = "NULLSATZ-OHNE-GRUND"
	TAX_DEVIATION = "STEUER-ABWEICHUNG"
	INVOICES_AND_LEDGER = "ABGLEICH-RECHNUNGEN"
	PREVIOUS_PERIOD = "ABWEICHUNG-VORPERIODE"
	NO_CATALOGUE = "KEIN-KATALOG"
	MAPPING_UNFIT = "ZUORDNUNG-JAHRGANG"


# A wrong invoice is a warning; a difference that may well be explained, such as a journal entry on a
# revenue account or a quieter month, is a hint.
SEVERITIES: MappingProxyType[Code, Severity] = MappingProxyType(
	{
		Code.EU_WITHOUT_VAT_ID: Severity.WARNING,
		Code.EU_ADDRESS: Severity.WARNING,
		Code.ZERO_TAX: Severity.WARNING,
		Code.TAX_DEVIATION: Severity.WARNING,
		Code.INVOICES_AND_LEDGER: Severity.HINT,
		Code.PREVIOUS_PERIOD: Severity.HINT,
		Code.NO_CATALOGUE: Severity.HINT,
		Code.MAPPING_UNFIT: Severity.HINT,
	}
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
		text = f"{booked}, aber der Kunde {line.party} hat keine USt-IdNr."
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
	lines: Iterable[InvoiceLine], ledger: ReadOnlyMapping[str, Decimal], mapping: Mapping, figures: Figures
) -> list[Hint]:
	"""Invoices against the ledger: per base an invoice books, the net of the invoices and the ledger amount.

	``ledger`` holds the exact amounts the ledger gives each Kennzahl, before rounding. A difference of
	more than a euro gets a hint, in the order of the form: a journal entry on a revenue account or an
	invoice on an account of another Kennzahl explains one as well as a missing invoice.
	"""
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


@dataclass(frozen=True, slots=True)
class EarlierPeriod:
	"""A period to compare with and its reported amounts by Kennzahl.

	``values`` is None when Steuerbote cannot compute the period; ``missing`` then says why: no catalogue
	of Kennzahlen for its year (NO_CATALOGUE), or a mapping that does not fit the form of that year
	(MAPPING_UNFIT).
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
) -> tuple[Hint, ...]:
	"""Every hint of a return: the warnings first, then the hints; each kind in the order it is found.

	The invoices come first, then their reconciliation with the ledger, then the comparison.
	"""
	found = [
		*invoice_hints(lines, mapping, figures),
		*reconciliation_hints(lines, ledger, mapping, figures),
		*comparison_hints(comparison, figures),
	]
	return tuple(sorted(found, key=lambda hint: hint.severity is not Severity.WARNING))
