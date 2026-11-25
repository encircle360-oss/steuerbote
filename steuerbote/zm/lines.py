"""The lines of a Zusammenfassende Meldung, from the vouchers behind Kz 41, 42 and 21.

A ZM reports, per Erwerber or Leistungsempfänger, „die Summe der Bemessungsgrundlagen“ of the
innergemeinschaftliche Warenlieferungen (Art L), of the Lieferungen im Sinne des § 25b Absatz 2 (Art D) and of
the sonstige Leistungen (Art S), each under the USt-IdNr. it was made under (§ 18a Absatz 7 Satz 1 UStG). The
Voranmeldung reports the same turnover in Kz 41 (line 19), Kz 42 (line 33) and Kz 21 (line 35) of the form
USt 1 A 2026. The Anleitung zur ZM (USt ZM 1/2021, IV.8 and IV.11) wants them „summiert für die jeweilige
Umsatzart [...] in je einer Zeile“, at most three lines per Erwerber.

The lines come from the ledger, voucher by voucher, as the Kennzahlen do: § 18a Absatz 7 Satz 2 UStG applies
§ 17 UStG to the ZM, so a Skonto, a discount or a receivable written off as uncollectable changes the line of the
Meldezeitraum „in dem die Änderung eingetreten ist“ (BZSt, „Berichtigung einer ZM“, Rabatte; Anleitung zur ZM,
IV.10). Invoices alone miss these. The caller gives each voucher's exact amount in Kz 41, 42 or 21 with its
party, the party's USt-IdNr. and, for Art D, the country where the goods arrive.

The ZM takes whole euros (ZMDO: betrag, GeldBetragOhneCent). How to round is written nowhere; Steuerbote drops
the cents towards zero, as for the Bemessungsgrundlagen of the Voranmeldung (rounding.to_full_euros), and a line
of zero euros is not reported: „Sog. „Nullmeldungen“ sind nicht abzugeben“ (Anleitung zur ZM, III.1).

A line holds the ZM back from „Bereit“ when a voucher names no customer or no USt-IdNr. of it, when the
USt-IdNr. is not one the ZM takes (steuerbote.zm.ustid), when the confirmation of § 18e UStG found it invalid or
has not confirmed it (the outcome is an input), or when the USt-IdNr. of a Dreiecksgeschäft was not issued in
the country where the goods arrive (§ 18a Absatz 7 Satz 1 Nummer 4 Buchstabe a UStG). An override with a
Begründung lifts the block of its line and replaces its amount. A line without a USt-IdNr. the ZM takes cannot
be reported, so its override can only drop it, with 0. An override without vouchers is a line of its own, such
as a Verbringen (§ 6a Absatz 2 UStG), which the ZM reports under the company's own USt-IdNr. in the other member
state (§ 18a Absatz 7 Satz 1 Nummer 2 UStG). It reports an amount only under a USt-IdNr., and a hint names it
with its Begründung, which explains why no voucher of the ledger stands behind it.

An override is made against the exact ledger amount of its line, its basis. When the ledger books another amount
later, such as a late invoice of the same customer, the override would hide the change from the ZM and from its
Berichtigung, which reports „die vollständige korrekte Summe“ (§ 18a Absatz 10 UStG; Anleitung zur ZM, IV.12.2):
the line then holds the ZM back until the override is confirmed or removed, and nothing lifts that block. A release
of the USt-IdNr. (``accepted``) is not an override: with a Begründung, such as a confirmation of the day of the
supply kept outside Steuerbote, it lifts only the block of an unconfirmed or invalid number, and the line reports its
ledger amount.

A Berichtigung reports only the lines that change what the BZSt holds (steuerbote.zm.correction). A line it repeats
unchanged, whose only block is the confirmation of its number, was filed so already and holds the Berichtigung back no
more (Statement.holding).
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from enum import Enum, StrEnum
from types import MappingProxyType

from steuerbote.ustva.calculation import require_cents
from steuerbote.ustva.period import day_label
from steuerbote.ustva.plausibility import Figures
from steuerbote.ustva.rounding import EURO, ZERO, require_decimal, to_full_euros
from steuerbote.vatid.exemption import consequence
from steuerbote.zm.errors import ZmError
from steuerbote.zm.findings import Code, Finding, voucher_no
from steuerbote.zm.ustid import Refusal, country_prefix, normalize, refusal

NOT_WHOLE_EUROS = "A line of the Zusammenfassende Meldung takes whole euros, not {0}."
NO_REASON = "An override of a line of the Zusammenfassende Meldung needs a Begründung."
NOT_A_VAT_ID = "{0} is not a USt-IdNr. that the Zusammenfassende Meldung takes for Art {1}."
OVERRIDDEN_TWICE = "The line {0} {1} of the Zusammenfassende Meldung is overridden twice."
OWN_LINE_WITHOUT_VAT_ID = (
	"A line of the Zusammenfassende Meldung entered by hand needs the USt-IdNr. it reports, for a Verbringen "
	"the company's own USt-IdNr. in the member state of arrival."
)


class Art(StrEnum):
	L = "L"
	D = "D"
	S = "S"


KENNZAHL_ART: MappingProxyType[str, Art] = MappingProxyType({"41": Art.L, "42": Art.D, "21": Art.S})
ART_KENNZAHL: MappingProxyType[Art, str] = MappingProxyType(
	{art: number for number, art in KENNZAHL_ART.items()}
)
# The order of the Kennzahlen on the form USt 1 A: lines 19, 33 and 35.
ART_ORDER = (Art.L, Art.D, Art.S)


class Validity(Enum):
	"""The outcome of the confirmation of a USt-IdNr. (§ 18e UStG)."""

	CONFIRMED = "confirmed"
	INVALID = "invalid"
	UNCONFIRMED = "unconfirmed"


@dataclass(frozen=True, slots=True)
class VoucherAmount:
	"""What one voucher adds to Kz 41, 42 or 21, in cents, and the customer it names.

	``voucher`` is the key "<voucher type>:<voucher name>" of steuerbote.ledger, ``vat_id`` the USt-IdNr. as
	ERPNext holds it and ``destination`` the country where the goods of a Dreiecksgeschäft arrive, as an ISO code
	or as ERPNext names the Country.
	"""

	voucher: str
	kennzahl: str
	amount: Decimal
	party: str | None = None
	vat_id: str | None = None
	destination: str | None = None

	def __post_init__(self) -> None:
		if not (isinstance(self.voucher, str) and self.voucher):
			raise ValueError(f"voucher must be a document name, not {self.voucher!r}")
		if self.kennzahl not in KENNZAHL_ART:
			raise ValueError(f"Kennzahl {self.kennzahl!r} has no Art of the ZM")
		require_cents(self.amount)

	@property
	def art(self) -> Art:
		return KENNZAHL_ART[self.kennzahl]


@dataclass(frozen=True, slots=True)
class Override:
	"""An amount that a line reports instead of the computed one, and why; ``basis`` is the exact ledger amount of the
	line the override was made against, None for an override that build() meets for the first time. ``basis_unknown``
	marks an override from before Steuerbote kept the basis, whose basis is the ledger amount of the day of the update
	and not the one it was made against; it holds its line until it is confirmed."""

	amount: Decimal
	reason: str
	basis: Decimal | None = None
	basis_unknown: bool = False

	def __post_init__(self) -> None:
		require_whole_euros(self.amount)
		if not (isinstance(self.reason, str) and self.reason.strip()):
			raise ZmError(NO_REASON)
		if self.basis is not None:
			require_cents(self.basis)


@dataclass(frozen=True, slots=True)
class ConfirmationAge:
	"""How old the latest confirmation of a number may be at ``until``, the last day of the months of the ZM, in
	days, as the VAT Return Settings allow it for the Voranmeldung."""

	until: date
	days: int

	def __post_init__(self) -> None:
		if isinstance(self.days, bool) or not isinstance(self.days, int) or self.days < 0:
			raise ValueError(f"the age of a confirmation is a number of days from 0 on, not {self.days!r}")


@dataclass(frozen=True, slots=True)
class Meldezeile:
	"""A line as the ZM reports it: USt-IdNr., Art and the sum in whole euros."""

	vat_id: str
	art: Art
	amount: Decimal

	def __post_init__(self) -> None:
		object.__setattr__(self, "art", Art(self.art))
		if not _reportable(self.vat_id, self.art):
			raise ZmError(NOT_A_VAT_ID, self.vat_id, self.art.value)
		require_whole_euros(self.amount)

	@property
	def key(self) -> tuple[str, Art]:
		return (self.vat_id, self.art)


@dataclass(frozen=True, slots=True)
class Line:
	"""The vouchers of one USt-IdNr. and Art, and what holds the line back.

	``vat_id`` is the USt-IdNr. as the ZM writes it or, if the ZM cannot take it, as the vouchers give it; it is
	empty for the vouchers without one.
	"""

	vat_id: str
	art: Art
	vouchers: tuple[VoucherAmount, ...] = ()
	override: Override | None = None
	findings: tuple[Finding, ...] = ()
	acceptance: str = ""

	@property
	def key(self) -> tuple[str, Art]:
		return (self.vat_id, self.art)

	@property
	def amount(self) -> Decimal:
		"""The exact sum of the vouchers."""
		return sum((item.amount for item in self.vouchers), ZERO)

	@property
	def valid(self) -> bool:
		"""The ZM can report the line under its USt-IdNr."""
		return _reportable(self.vat_id, self.art)

	@property
	def manual(self) -> bool:
		"""The line is entered by hand: no voucher stands behind it, only the override and its Begründung."""
		return not self.vouchers and self.override is not None

	@property
	def computed(self) -> Decimal:
		return to_full_euros(self.amount)

	@property
	def reported(self) -> Decimal:
		return self.override.amount if self.override else self.computed

	@property
	def blocked(self) -> bool:
		return any(self._holds(finding) for finding in self.findings)

	def _holds(self, finding: Finding) -> bool:
		if not finding.blocking:
			return False
		if finding.code is Code.OVERRIDE_STALE:
			return True
		if self.acceptance and finding.code in RELEASABLE:
			return False
		return not (self.override is not None and (self.valid or self.override.amount == ZERO))

	@property
	def holding_findings(self) -> tuple[Finding, ...]:
		"""The findings that hold the line, without those an override or a release lifted."""
		return tuple(finding for finding in self.findings if self._holds(finding))

	def unchanged(self, held: ReadOnlyMapping[tuple[str, Art], Decimal]) -> bool:
		"""The line reports what the BZSt holds for it, and only the confirmation of its number holds it."""
		return (
			self.meldezeile is not None
			and held.get(self.key) == self.reported
			and all(finding.code in RELEASABLE for finding in self.findings if self._holds(finding))
		)

	@property
	def meldezeile(self) -> Meldezeile | None:
		"""The line as the ZM reports it, or None if it reports nothing."""
		if not (self.valid and self.reported):
			return None
		return Meldezeile(self.vat_id, self.art, self.reported)


@dataclass(frozen=True, slots=True)
class Statement:
	"""The lines of a ZM, ordered by USt-IdNr. and then as the form orders their Kennzahlen."""

	lines: tuple[Line, ...]

	@property
	def ready(self) -> bool:
		return not any(line.blocked for line in self.lines)

	def holding(self, held: ReadOnlyMapping[tuple[str, Art], Decimal] | None) -> tuple[Line, ...]:
		"""The lines that hold the ZM back; for a Berichtigung, with what the BZSt holds (``held``), not those it
		repeats unchanged with only the confirmation of their number open."""
		return tuple(
			line for line in self.lines if line.blocked and not (held is not None and line.unchanged(held))
		)

	def ready_against(self, held: ReadOnlyMapping[tuple[str, Art], Decimal] | None) -> bool:
		return not self.holding(held)

	@property
	def findings(self) -> tuple[Finding, ...]:
		return tuple(finding for line in self.lines for finding in line.findings)

	@property
	def meldezeilen(self) -> tuple[Meldezeile, ...]:
		return tuple(meldezeile for line in self.lines if (meldezeile := line.meldezeile) is not None)


def build(
	amounts: Iterable[VoucherAmount],
	figures: Figures,
	validity: ReadOnlyMapping[str, Validity] | None = None,
	overrides: ReadOnlyMapping[tuple[str, Art], Override] | None = None,
	asked: ReadOnlyMapping[str, date] | None = None,
	accepted: ReadOnlyMapping[tuple[str, Art], str] | None = None,
	confirmation_age: ConfirmationAge | None = None,
) -> Statement:
	"""The lines of the voucher amounts of a Meldezeitraum.

	``validity`` holds the outcome of the confirmation by USt-IdNr. as the ZM writes it; a USt-IdNr. without an
	outcome passes. ``overrides`` are keyed by USt-IdNr. and Art as the lines show them. ``asked`` holds the day
	the confirmation of each USt-IdNr. was asked, which the findings on it name: a confirmation holds for the
	moment of its query („Bestätigungen für zurückliegende Zeitpunkte oder Zeiträume sind nicht möglich.“, BZSt,
	„Fragen und Antworten“ zur USt-IdNr.). ``accepted`` holds the Begründung of each released number by line, and
	``confirmation_age`` how old a confirmation may be before a hint names it; without it no confirmation ages.
	"""
	vouchers: dict[tuple[str, Art], list[VoucherAmount]] = {}
	for item in amounts:
		vouchers.setdefault((line_vat_id(item.vat_id, item.art), item.art), []).append(item)
	overridden: dict[tuple[str, Art], Override] = {}
	for (vat_id, art), override in (overrides or {}).items():
		key = (line_vat_id(vat_id, Art(art)), Art(art))
		if key in overridden:
			raise ZmError(OVERRIDDEN_TWICE, *key)
		overridden[key] = override
	releases = {
		(line_vat_id(vat_id, Art(art)), Art(art)): reason.strip()
		for (vat_id, art), reason in (accepted or {}).items()
		if (reason or "").strip()
	}
	context = _Context(validity or {}, asked or {}, figures, confirmation_age)
	lines = (
		_line(key, tuple(vouchers.get(key, ())), overridden.get(key), releases.get(key, ""), context)
		for key in sorted(vouchers.keys() | overridden.keys(), key=line_order)
	)
	return Statement(tuple(lines))


def line_vat_id(vat_id: str | None, art: Art) -> str:
	"""The USt-IdNr. under which a line of ``art`` reports ``vat_id``: as the ZM writes it, else as given."""
	return normalize(vat_id, services=art is Art.S) or (vat_id or "").strip()


def line_order(key: tuple[str, Art]) -> tuple[str, int]:
	"""Sort lines by USt-IdNr. and then as the form orders their Kennzahlen."""
	return key[0], ART_ORDER.index(key[1])


@dataclass(frozen=True, slots=True)
class _Context:
	"""What build() knows about the numbers of every line, and how it writes amounts."""

	validity: ReadOnlyMapping[str, Validity]
	asked: ReadOnlyMapping[str, date]
	figures: Figures
	confirmation_age: ConfirmationAge | None


# The findings on the confirmation of a number, which a release of the number lifts (decision of the maintainer).
RELEASABLE = frozenset({Code.INVALID_VAT_ID, Code.UNCONFIRMED_VAT_ID})
NO_VAT_ID_ADVICE = "Berichtigen Sie die Rechnung, oder nehmen Sie die Zeile mit der Korrektur 0 und einer Begründung aus der ZM."
MALFORMED_ADVICE = (
	"Berichtigen Sie die USt-IdNr. in der Rechnung, oder nehmen Sie die Zeile mit der Korrektur 0 und einer Begründung "
	"aus der ZM."
)
INVALID_ADVICE = (
	"Belegt eine frühere Bestätigung die Gültigkeit am Tag des Umsatzes, geben Sie die USt-IdNr. mit Begründung frei; "
	"sonst berichtigen Sie die Rechnung."
)
# The Sorgfalt of § 6a Absatz 4 UStG asks for the confirmation at the time of the supply (UStAE 6a.8 Abs. 6 Satz 1).
UNCONFIRMED_ADVICE = (
	"Die Bestätigung soll spätestens zum Umsatz vorliegen (UStAE 6a.8 Abs. 6): „USt-IdNrn. prüfen“ fragt beim "
	"BZSt an; liegt eine Bestätigung anders vor, geben Sie die USt-IdNr. mit Begründung frei."
)


def _line(
	key: tuple[str, Art],
	vouchers: tuple[VoucherAmount, ...],
	override: Override | None,
	release: str,
	context: _Context,
) -> Line:
	vat_id, art = key
	if not (vouchers or vat_id) and override is not None and override.amount:
		raise ZmError(OWN_LINE_WITHOUT_VAT_ID)
	figures = context.figures
	party = next((name for item in vouchers if (name := (item.party or "").strip())), "")
	findings: list[Finding] = []
	problem = refusal(vat_id, services=art is Art.S)
	day = context.asked.get(vat_id)
	validity = context.validity.get(vat_id)
	if vat_id and problem is not None:
		text = f"{_MALFORMED[problem].format(vat_id)} {consequence(ART_KENNZAHL[art])} {MALFORMED_ADVICE}"
		findings.append(Finding(Code.MALFORMED_VAT_ID, text, party=party))
	elif vat_id and validity is Validity.INVALID:
		query = f"Bestätigungsabfrage vom {day_label(day)}" if day else "Bestätigungsabfrage"
		text = f"Die USt-IdNr. {vat_id} ist laut {query} ungültig. {consequence(ART_KENNZAHL[art])} {INVALID_ADVICE}"
		findings.append(Finding(Code.INVALID_VAT_ID, text, party=party))
	elif vat_id and validity is Validity.UNCONFIRMED:
		unanswered = f"; die Bestätigungsabfrage vom {day_label(day)} ergab kein Ergebnis" if day else ""
		text = f"Die USt-IdNr. {vat_id} ist nicht bestätigt{unanswered}. {UNCONFIRMED_ADVICE}"
		findings.append(Finding(Code.UNCONFIRMED_VAT_ID, text, party=party))
	elif vat_id and validity is Validity.CONFIRMED and day and context.confirmation_age is not None:
		findings.extend(_aged(vat_id, day, context.confirmation_age, party))
	for item in vouchers:
		findings.extend(_voucher_findings(item, vat_id, problem is None, figures))
	if not vouchers and override is not None and vat_id:
		text = (
			f"Die Zeile {vat_id} ({art.value}) ist von Hand eingetragen und steht ohne Beleg im Hauptbuch mit "
			f"{figures.money(override.amount)} in der ZM; Begründung: {override.reason.strip()}"
		)
		findings.append(Finding(Code.OWN_LINE, _sentence(text)))
	amount = sum((item.amount for item in vouchers), ZERO)
	if override is not None:
		if override.basis_unknown:
			findings.append(
				Finding(Code.OVERRIDE_STALE, _unconfirmed(key, override, amount, figures), party=party)
			)
		elif override.basis is None:
			override = replace(override, basis=amount)
		elif override.basis != amount:
			findings.append(Finding(Code.OVERRIDE_STALE, _stale(key, override, amount, figures), party=party))
	acceptance = release if any(finding.code in RELEASABLE for finding in findings) else ""
	if acceptance:
		text = f"Die USt-IdNr. {vat_id} ist für die Zeile {art.value} freigegeben; Begründung: {acceptance}"
		findings.append(Finding(Code.VAT_ID_ACCEPTED, _sentence(text), party=party))
	return Line(vat_id, art, vouchers, override, tuple(findings), acceptance)


def _aged(vat_id: str, day: date, age: ConfirmationAge, party: str) -> list[Finding]:
	days = (age.until - day).days
	if days <= age.days:
		return []
	text = (
		f"Die USt-IdNr. {vat_id} ist zuletzt am {day_label(day)} bestätigt worden, {days} Tage vor dem Ende der "
		f"Monate der Meldung; die Einstellungen lassen höchstens {age.days} Tage zu. „USt-IdNrn. prüfen“ fragt erneut."
	)
	return [Finding(Code.CONFIRMATION_STALE, text, party=party)]


def _line_label(key: tuple[str, Art]) -> str:
	vat_id, art = key
	return f"{vat_id} ({art.value})" if vat_id else f"ohne USt-IdNr. ({art.value})"


def _unconfirmed(key: tuple[str, Art], override: Override, amount: Decimal, figures: Figures) -> str:
	return (
		f"Die Korrektur der Zeile {_line_label(key)} auf {figures.money(override.amount)} stammt aus einer Version von "
		"Steuerbote, die nicht festhielt, bei welchem Betrag im Hauptbuch sie eingetragen wurde; das Hauptbuch bucht "
		f"jetzt {figures.money(amount)}. Die Zeile hält die Meldung an, bis die Korrektur bestätigt ist: Prüfen Sie "
		"sie gegen das Hauptbuch und ändern Sie Betrag oder Begründung, oder löschen Sie die Korrektur, dann meldet "
		"die Zeile das Hauptbuch."
	)


def _stale(key: tuple[str, Art], override: Override, amount: Decimal, figures: Figures) -> str:
	line = _line_label(key)
	return (
		f"Die Korrektur der Zeile {line} auf {figures.money(override.amount)} wurde bei "
		f"{figures.money(override.basis)} im Hauptbuch eingetragen; das Hauptbuch bucht jetzt {figures.money(amount)}. "
		"Die Zeile hält die Meldung an, bis die Korrektur bestätigt ist: Passen Sie Betrag oder Begründung an, oder "
		"löschen Sie die Korrektur, dann meldet die Zeile das Hauptbuch."
	)


def _sentence(text: str) -> str:
	"""A sentence ends with one full stop, also after a name such as „Muster B.V.“."""
	return text if text.endswith((".", "!", "?")) else f"{text}."


# Why a USt-IdNr. is no line of the ZM, after steuerbote.zm.ustid.
_MALFORMED: MappingProxyType[Refusal, str] = MappingProxyType(
	{
		Refusal.FORMAT: "„{0}“ ist keine USt-IdNr. im Format der ZM: Länderkennzeichen und Buchstaben, Ziffern, + "
		"oder *, zusammen 7 bis 14 Zeichen.",
		Refusal.DOMESTIC: "„{0}“ ist eine deutsche USt-IdNr.; die ZM nennt nur USt-IdNrn. anderer Mitgliedstaaten.",
		Refusal.UNITED_KINGDOM: "„{0}“ ist eine britische USt-IdNr.; das Länderkennzeichen GB gilt nur für "
		"Meldezeiträume bis 2020.",
		Refusal.UNKNOWN_COUNTRY: "„{0}“ beginnt mit keinem Länderkennzeichen eines anderen Mitgliedstaats.",
		Refusal.NORTHERN_IRELAND_SERVICES: "„{0}“ ist eine nordirische USt-IdNr.; sie gilt in der ZM nur für "
		"Lieferungen, nicht für sonstige Leistungen.",
	}
)


def _voucher_findings(item: VoucherAmount, vat_id: str, valid: bool, figures: Figures) -> list[Finding]:
	number = voucher_no(item.voucher)
	booked = f"Beleg {number} geht mit {figures.money(item.amount)} in Kz {item.kennzahl} ein"
	party = (item.party or "").strip()
	if not party:
		return [Finding(Code.NO_PARTY, f"{booked}, nennt aber keinen Kunden.", item.voucher)]
	if not vat_id:
		text = (
			f"{_sentence(f'{booked}, nennt aber keine USt-IdNr. des Kunden {party}')} "
			f"{consequence(item.kennzahl)} {NO_VAT_ID_ADVICE}"
		)
		return [Finding(Code.NO_VAT_ID, text, item.voucher, party)]
	if item.art is not Art.D or not valid or country_prefix(item.destination) == vat_id[:2]:
		return []
	if not (item.destination or "").strip():
		text = f"Beleg {number} nennt nicht, in welchem Land die Lieferung an den letzten Abnehmer {vat_id} endet."
	else:
		text = (
			f"Beleg {number}: Die Lieferung endet in {item.destination.strip()}, die USt-IdNr. {vat_id} des "
			"letzten Abnehmers ist nicht in diesem Land erteilt."
		)
	return [Finding(Code.DESTINATION, text, item.voucher, party)]


def _reportable(vat_id: str, art: Art) -> bool:
	"""The ZM can report a line of ``art`` under ``vat_id`` as it stands."""
	return isinstance(vat_id, str) and normalize(vat_id, services=art is Art.S) == vat_id


def require_whole_euros(amount: Decimal) -> None:
	require_decimal(amount)
	if not amount.is_finite() or amount != amount.quantize(EURO):
		raise ZmError(NOT_WHOLE_EUROS, amount)
