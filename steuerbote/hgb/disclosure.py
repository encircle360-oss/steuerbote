"""What a GmbH or UG publishes of its Jahresabschluss, by when, after which Feststellung, and what being late costs.

What is published. The Geschäftsführer transmit „den festgestellten Jahresabschluss, den Lagebericht, den
Bestätigungsvermerk oder den Vermerk über dessen Versagung“ to the operator of the Unternehmensregister (§ 325
Abs. 1 HGB). The Geschäftsführer of a small company „nur die Bilanz und den Anhang zu übermitteln haben“, and „Der
Anhang braucht die die Gewinn- und Verlustrechnung betreffenden Angaben nicht zu enthalten“ (§ 326 Abs. 1 HGB).
Those of a Kleinst „nur die Bilanz zu übermitteln haben und dabei die Einstellung in das Unternehmensregister durch
dauerhafte Hinterlegung verlangen können“ if they notify the operator „dass sie zwei der drei in § 267a Absatz 1
genannten Merkmale für die nach § 267 Absatz 4 maßgeblichen Abschlussstichtage nicht überschreiten“ (§ 326 Abs. 2
HGB). A deposited balance sheet is open „nur auf Antrag durch Übermittlung einer Kopie“ (§ 9 Abs. 6 Satz 3 HGB).
Steuerbote deposits a Kleinst unless told otherwise, since that publishes the least. Kleinst and klein draw up no
Lagebericht (§ 264 Abs. 1 Satz 4 HGB) and are not audited (§ 316 Abs. 1 Satz 1 HGB). Steuerbote prepares the
disclosure of Kleinst and klein; for mittelgroß, which § 327 HGB spares part of it, and groß it names the parts
only.

The Ergebnisverwendung. The Anhang states „der Vorschlag für die Verwendung des Ergebnisses oder der Beschluss über
seine Verwendung“ (§ 285 Nr. 34 HGB), which small companies need not state (§ 288 Abs. 1 Nr. 1 HGB); a Kleinst has no
Anhang (§ 264 Abs. 1 Satz 5 HGB) and transmits the balance sheet only (§ 326 Abs. 2 Satz 1 HGB). „Ist im
Jahresabschluss nur der Vorschlag für die Ergebnisverwendung enthalten, ist der Beschluss über die
Ergebnisverwendung nach seinem Vorliegen nach Absatz 1 Satz 1 offenzulegen.“ (§ 325 Abs. 1b Satz 2 HGB), naming the
Jahresabschluss it belongs to (§ 328 Abs. 3 HGB). In the balance sheet the appropriation shows through the
Bilanzgewinn (steuerbote.hgb.statement).

By when. „Der Jahresabschluß und der Lagebericht sind von den gesetzlichen Vertretern in den ersten drei Monaten des
Geschäftsjahrs für das vergangene Geschäftsjahr aufzustellen“; a small company „dürfen den Jahresabschluß auch
später aufstellen, wenn dies einem ordnungsgemäßen Geschäftsgang entspricht, jedoch innerhalb der ersten sechs
Monate des Geschäftsjahres“ (§ 264 Abs. 1 Satz 3 und 4 HGB). The shareholders decide on the Feststellung and the
Ergebnisverwendung „spätestens bis zum Ablauf der ersten acht Monate oder, wenn es sich um eine kleine
Gesellschaft handelt (§ 267 Abs. 1 des Handelsgesetzbuchs), bis zum Ablauf der ersten elf Monate des
Geschäftsjahrs“ (§ 42a Abs. 2 Satz 1 GmbHG); a Kleinst is a small company (§ 267a Abs. 1 HGB). Without a known
class the shorter periods apply. The documents go to the register „spätestens ein Jahr nach dem
Abschlussstichtag des Geschäftsjahrs“ (§ 325 Abs. 1a Satz 1 HGB), and „Für die Wahrung der Fristen [...] ist der
Zeitpunkt der Übermittlung der Unterlagen maßgebend“ (§ 325 Abs. 4 Satz 2 HGB); only the festgestellter
Jahresabschluss counts (§ 325 Abs. 1 Satz 1 Nr. 1 HGB). The months of the next fiscal year end with the day before
the day of the same number (§ 187 Abs. 2, § 188 Abs. 2 BGB), the year after the closing date on the day of the same
number or the last day of its month (§ 187 Abs. 1, § 188 Abs. 2 und 3 BGB). Whether § 193 BGB moves a day on a
weekend is unverified, so Steuerbote keeps the day and says so (``on_weekend``) for an early reminder.

After which Feststellung. Only „den festgestellten Jahresabschluss“ is disclosed (§ 325 Abs. 1 Satz 1 Nr. 1 HGB),
and „Das Datum der Feststellung oder der Billigung [...] ist anzugeben“ (§ 328 Abs. 1a Satz 1 HGB). „Der
Jahresabschluß ist vom Kaufmann unter Angabe des Datums zu unterzeichnen.“ (§ 245 Satz 1 HGB) For a GmbH that is
every Geschäftsführer: „Der Jahresabschluss ist von sämtlichen Geschäftsführern einer GmbH zu unterzeichnen. Daher
reicht eine alleinige Unterzeichnung, auch bei Einzelvertretungsbefugnis, nicht aus.“ (Bundesamt für Justiz, FAQ
zu Inhalts- und Formverstößen, read on 23 November 2026) The disclosed version names each of them with the date,
such as „gez. Max Mustermann“; a sole shareholder and Geschäftsführer may sign on the day of the Feststellung and
states that date twice (same source). adoption_problems() and transmission_problems() check this.

Nullbilanz. „Soweit tatsächlich keine zu bilanzierenden Aktiv- oder Passivposten im Geschäftsjahr entstanden sind,
muss zumindest das Stammkapital in Höhe des am Bilanzstichtag geltenden Handelsregistereintrags vorhanden sein.“
(Bundesamt für Justiz, FAQ zu Inhalts- und Formverstößen) The Stammkapital stands in the balance sheet as
Gezeichnetes Kapital (§ 42 Abs. 1 GmbHG) „mit dem Nennbetrag“ (§ 272 Abs. 1 Satz 1 HGB); capital_problems()
compares the two.

What being late costs. The Bundesamt für Justiz threatens the Geschäftsführer and the company with an Ordnungsgeld
„innerhalb einer Frist von sechs Wochen vom Zugang der Androhung an ihrer gesetzlichen Verpflichtung nachzukommen“
(§ 335 Abs. 3 Satz 1 HGB); „Das Ordnungsgeld beträgt mindestens zweitausendfünfhundert und höchstens
fünfundzwanzigtausend Euro.“ (§ 335 Abs. 1 Satz 4 HGB) Filed after the six weeks, it is lowered „auf einen Betrag von
500 Euro, wenn die Beteiligten von dem Recht einer Kleinstkapitalgesellschaft nach § 326 Absatz 2 Gebrauch gemacht
haben“, to 1 000 Euro for a small company and to 2 500 Euro otherwise (§ 335 Abs. 4 Satz 2 Nr. 1 to 3 HGB); Nr. 4
lowers it further for a short delay, at the discretion of the Bundesamt. A procedure costs 100,00 Euro (Nr. 1210 of
the Kostenverzeichnis of the JVKostG), and against several persons „entstehen die Gebühren für jede Person
gesondert“ (Vorbemerkung 1.2.1). The register charges 18,50 Euro for the Einstellung of a Kleinst and 25,00 Euro
for klein (Nr. 1420 and 1421 KV JVKostG), 3,00 Euro a year for a company with the reliefs of § 326 HGB
(Nr. 1410), half more for documents changed before the Einstellung and half less for a withdrawal
(Vorbemerkung 1.4.2 Abs. 2 und 3), read on gesetze-im-internet.de on 23 November 2026.

The Annual Accounts read the class of the fiscal year from steuerbote.hgb.size, the form of the balance sheet
from steuerbote.hgb.schemes and the Angaben from steuerbote.hgb.notes. Text of §§ 9, 245, 264, 285, 288, 316,
325, 326, 327, 328 HGB, § 42a GmbHG and §§ 187, 188, 193 BGB as read on gesetze-im-internet.de on
23 November 2026.
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum, StrEnum
from types import MappingProxyType

from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import Finding, Severity


class DisclosureError(ValueError):
	"""The class cannot disclose so."""


class Mode(Enum):
	OFFENLEGUNG = "Offenlegung"
	HINTERLEGUNG = "Hinterlegung"


class Part(Enum):
	BILANZ = "Bilanz"
	GUV = "Gewinn- und Verlustrechnung"
	ANHANG = "Anhang"
	LAGEBERICHT = "Lagebericht"
	BESTAETIGUNGSVERMERK = "Bestätigungsvermerk oder Vermerk über dessen Versagung"


@dataclass(frozen=True, slots=True)
class Publication:
	"""What one class transmits in one mode: the parts, whether the Angaben stand under the balance sheet, whether
	the Anhang leaves out what concerns the income statement, whether anyone may read it, whether the Mitteilung of
	§ 326 Abs. 2 Satz 2 HGB goes with it and whether Steuerbote prepares it."""

	size_class: SizeClass
	mode: Mode
	parts: tuple[Part, ...]
	below_balance_sheet: bool
	notes_without_income_statement: bool
	public: bool
	notice: bool
	prepared: bool
	reference: str


_EVERYTHING = (Part.BILANZ, Part.GUV, Part.ANHANG, Part.LAGEBERICHT, Part.BESTAETIGUNGSVERMERK)


def modes(size_class: SizeClass) -> tuple[Mode, ...]:
	"""The ways ``size_class`` may disclose, the default first."""
	if size_class is SizeClass.KLEINST:
		return (Mode.HINTERLEGUNG, Mode.OFFENLEGUNG)
	return (Mode.OFFENLEGUNG,)


def default_mode(size_class: SizeClass) -> Mode:
	return modes(size_class)[0]


def publication(size_class: SizeClass, mode: Mode | None = None) -> Publication:
	"""What ``size_class`` transmits to the Unternehmensregister in ``mode``, its default without one."""
	mode = default_mode(size_class) if mode is None else mode
	if mode not in modes(size_class):
		raise DisclosureError(f"a {size_class.value} cannot choose the {mode.value} (§ 326 Abs. 2 HGB)")
	match size_class:
		case SizeClass.KLEINST:
			deposited = mode is Mode.HINTERLEGUNG
			return Publication(
				size_class,
				mode,
				(Part.BILANZ,),
				below_balance_sheet=True,
				notes_without_income_statement=False,
				public=not deposited,
				notice=deposited,
				prepared=True,
				reference="§ 326 Abs. 2, § 9 Abs. 6 Satz 3 HGB" if deposited else "§ 326 Abs. 2 HGB",
			)
		case SizeClass.KLEIN:
			return Publication(
				size_class,
				mode,
				(Part.BILANZ, Part.ANHANG),
				below_balance_sheet=False,
				notes_without_income_statement=True,
				public=True,
				notice=False,
				prepared=True,
				reference="§ 326 Abs. 1 HGB",
			)
		case _:
			return Publication(
				size_class,
				mode,
				_EVERYTHING,
				below_balance_sheet=False,
				notes_without_income_statement=False,
				public=True,
				notice=False,
				prepared=False,
				reference="§ 325 Abs. 1, § 327 HGB"
				if size_class is SizeClass.MITTELGROSS
				else "§ 325 Abs. 1 HGB",
			)


class DeadlineKind(Enum):
	AUFSTELLUNG = "Aufstellung"
	FESTSTELLUNG = "Feststellung"
	OFFENLEGUNG = "Offenlegung"


_SATURDAY = 5


@dataclass(frozen=True, slots=True)
class Deadline:
	"""A day by which a step is due; ``assumed_class`` when the class was unknown and the shorter period applies."""

	kind: DeadlineKind
	due: date
	reference: str
	assumed_class: bool = False

	@property
	def on_weekend(self) -> bool:
		"""A Saturday or Sunday, which § 193 BGB may move to the Monday; that is unverified."""
		return self.due.weekday() >= _SATURDAY


def preparation_deadline(fiscal_year_end: date, size_class: SizeClass | None) -> Deadline:
	"""The last day of the Aufstellung: three months into the next fiscal year, six for a small company where that
	suits an ordnungsgemäßer Geschäftsgang."""
	months = 6 if size_class is not None and size_class.is_small else 3
	return Deadline(
		DeadlineKind.AUFSTELLUNG,
		_end_of_months(fiscal_year_end, months),
		"§ 264 Abs. 1 Satz 3 und 4 HGB",
		size_class is None,
	)


def adoption_deadline(fiscal_year_end: date, size_class: SizeClass | None) -> Deadline:
	"""The last day for the Feststellung and the Ergebnisverwendung: eight months into the next fiscal year, eleven
	for a small company."""
	months = 11 if size_class is not None and size_class.is_small else 8
	return Deadline(
		DeadlineKind.FESTSTELLUNG,
		_end_of_months(fiscal_year_end, months),
		"§ 42a Abs. 2 Satz 1 GmbHG",
		size_class is None,
	)


def disclosure_deadline(fiscal_year_end: date) -> Deadline:
	"""The last day of the transmission to the Unternehmensregister: one year after the Abschlussstichtag."""
	try:
		due = fiscal_year_end.replace(year=fiscal_year_end.year + 1)
	except ValueError:
		due = date(fiscal_year_end.year + 1, 2, 28)
	return Deadline(DeadlineKind.OFFENLEGUNG, due, "§ 325 Abs. 1a Satz 1 HGB")


def deadline_kept(fiscal_year_end: date, transmitted_on: date, adopted_on: date | None) -> bool:
	"""Whether a transmission on ``transmitted_on`` keeps the deadline: on or before its last day, and not before
	the Feststellung on ``adopted_on``."""
	if adopted_on is None or transmitted_on < adopted_on:
		return False
	return transmitted_on <= disclosure_deadline(fiscal_year_end).due


def _end_of_months(fiscal_year_end: date, months: int) -> date:
	"""The last day of the first ``months`` months of the fiscal year after the one ending on ``fiscal_year_end``:
	the day before the day of the same number as its first day, or the last day of a month without that day."""
	start = fiscal_year_end + timedelta(days=1)
	if start.day == 1:
		return _add_months(start, months) - timedelta(days=1)
	last_month = _add_months(start.replace(day=1), months)
	days = calendar.monthrange(last_month.year, last_month.month)[1]
	return last_month.replace(day=min(start.day - 1, days))


def _add_months(first: date, months: int) -> date:
	"""The first day of the month ``months`` after the month of ``first``, itself a first day."""
	index = first.month - 1 + months
	return date(first.year + index // 12, index % 12 + 1, 1)


class DisclosureCode(StrEnum):
	NOT_ADOPTED = "JA-NICHT-FESTGESTELLT"
	ADOPTED_EARLY = "JA-FESTSTELLUNG-DATUM"
	UNSIGNED = "JA-UNTERSCHRIFT-FEHLT"
	UNDATED = "JA-UNTERSCHRIFT-OHNE-DATUM"
	SIGNED_EARLY = "JA-UNTERSCHRIFT-DATUM"
	BEFORE_ADOPTION = "JA-VOR-FESTSTELLUNG"
	NO_SIGNATURE = "JA-OHNE-UNTERSCHRIFT"
	CAPITAL = "JA-STAMMKAPITAL"


_ADOPTION_REFERENCE = "§ 325 Abs. 1 Satz 1 Nr. 1, § 328 Abs. 1a Satz 1 HGB"
_SIGNATURE_REFERENCE = "§ 245 Satz 1 HGB; Bundesamt für Justiz, FAQ zu Inhalts- und Formverstößen"


@dataclass(frozen=True, slots=True)
class Director:
	"""A Geschäftsführer of the company and the days of the office, as the Annual Filing Settings record them."""

	name: str
	start: date | None = None
	end: date | None = None

	def in_office(self, day: date) -> bool:
		return (self.start is None or self.start <= day) and (self.end is None or day <= self.end)


@dataclass(frozen=True, slots=True)
class Signature:
	"""A signature of the Jahresabschluss: who, in which function, where and on which day."""

	name: str
	function: str
	place: str
	signed_on: date | None


def adoption_problems(
	fiscal_year_end: date,
	adopted_on: date | None,
	directors: tuple[Director, ...],
	signatures: tuple[Signature, ...],
) -> tuple[Finding, ...]:
	"""What keeps the Jahresabschluss from the register: no Feststellung or one dated within the fiscal year, and a
	Geschäftsführer in office on the day of the Feststellung without a dated signature after the fiscal year."""
	findings: list[Finding] = []
	if adopted_on is None:
		findings.append(
			_finding(
				DisclosureCode.NOT_ADOPTED, "Der Jahresabschluss ist nicht festgestellt.", _ADOPTION_REFERENCE
			)
		)
	elif adopted_on <= fiscal_year_end:
		findings.append(
			_finding(
				DisclosureCode.ADOPTED_EARLY,
				"Der Jahresabschluss kann nicht vor dem Ende seines Geschäftsjahres festgestellt sein.",
				"§ 42a Abs. 2 Satz 1 GmbHG",
			)
		)
	by_name = {_normal(signature.name): signature for signature in signatures}
	for director in directors:
		if not director.in_office(adopted_on or fiscal_year_end):
			continue
		signature = by_name.get(_normal(director.name))
		if signature is None:
			findings.append(
				_finding(
					DisclosureCode.UNSIGNED,
					f"{director.name} hat den Jahresabschluss nicht unterzeichnet; jeder Geschäftsführer unterzeichnet.",
					_SIGNATURE_REFERENCE,
					director.name,
				)
			)
		elif signature.signed_on is None:
			findings.append(
				_finding(
					DisclosureCode.UNDATED,
					f"Der Unterschrift von {director.name} fehlt das Datum.",
					_SIGNATURE_REFERENCE,
					director.name,
				)
			)
		elif signature.signed_on <= fiscal_year_end:
			findings.append(
				_finding(
					DisclosureCode.SIGNED_EARLY,
					f"{director.name} kann den Jahresabschluss nicht vor dem Ende seines Geschäftsjahres "
					"unterzeichnet haben.",
					_SIGNATURE_REFERENCE,
					director.name,
				)
			)
	return tuple(findings)


def transmission_problems(
	adopted_on: date | None, transmitted_on: date, signatures: tuple[Signature, ...]
) -> tuple[Finding, ...]:
	"""What keeps a transmission from counting: one before the Feststellung, and one without a dated signature."""
	findings: list[Finding] = []
	if adopted_on is None or transmitted_on < adopted_on:
		findings.append(
			_finding(
				DisclosureCode.BEFORE_ADOPTION,
				"Übermittelt wird erst der festgestellte Jahresabschluss; eine Übermittlung davor wahrt die Frist "
				"nicht.",
				"§ 325 Abs. 1 Satz 1 Nr. 1, Abs. 4 Satz 2 HGB",
			)
		)
	if not any(signature.signed_on is not None for signature in signatures):
		findings.append(
			_finding(
				DisclosureCode.NO_SIGNATURE,
				"Der übermittelte Jahresabschluss braucht die Unterschriften mit Datum.",
				_SIGNATURE_REFERENCE,
			)
		)
	return tuple(findings)


def _normal(name: str) -> str:
	return " ".join(name.split()).casefold()


def _finding(code: DisclosureCode, text: str, reference: str, concept: str = "") -> Finding:
	return Finding(code, Severity.ERROR, text, reference, concept)


@dataclass(frozen=True, slots=True)
class Ordnungsgeld:
	minimum: Decimal
	maximum: Decimal
	weeks: int
	reference: str
	procedure_fee: Decimal
	procedure_fee_reference: str


ORDNUNGSGELD = Ordnungsgeld(
	Decimal("2500"),
	Decimal("25000"),
	6,
	"§ 335 Abs. 1 Satz 4, Abs. 3 Satz 1 HGB",
	Decimal("100.00"),
	"Nr. 1210 KV JVKostG",
)


@dataclass(frozen=True, slots=True)
class Reduction:
	amount: Decimal
	reference: str


def reduced_ordnungsgeld(size_class: SizeClass, mode: Mode) -> Reduction:
	"""What the Ordnungsgeld is lowered to when the company files after the six weeks (§ 335 Abs. 4 Satz 2 Nr. 1 to
	3 HGB); a Kleinst that published counts as the small company it is."""
	if size_class is SizeClass.KLEINST and mode is Mode.HINTERLEGUNG:
		return Reduction(Decimal("500"), "§ 335 Abs. 4 Satz 2 Nr. 1 HGB")
	if size_class.is_small:
		return Reduction(Decimal("1000"), "§ 335 Abs. 4 Satz 2 Nr. 2 HGB")
	return Reduction(Decimal("2500"), "§ 335 Abs. 4 Satz 2 Nr. 3 HGB")


@dataclass(frozen=True, slots=True)
class Fees:
	filing: Decimal
	filing_reference: str
	yearly: Decimal
	yearly_reference: str


_YEARLY_WITH_RELIEFS = (Decimal("3.00"), "Nr. 1410 KV JVKostG")
_FILING_FEES = MappingProxyType(
	{
		SizeClass.KLEINST: Fees(Decimal("18.50"), "Nr. 1420 KV JVKostG", *_YEARLY_WITH_RELIEFS),
		SizeClass.KLEIN: Fees(Decimal("25.00"), "Nr. 1421 KV JVKostG", *_YEARLY_WITH_RELIEFS),
	}
)


def filing_fees(size_class: SizeClass) -> Fees:
	"""What the register charges a class Steuerbote prepares for the Einstellung and every year."""
	try:
		return _FILING_FEES[size_class]
	except KeyError:
		raise DisclosureError(
			f"Steuerbote names the fees of Kleinst and klein only, not of a {size_class.value}"
		) from None


@dataclass(frozen=True, slots=True)
class FeeChanges:
	"""The factor on the fee for documents changed before the Einstellung and for a withdrawal before it; a
	withdrawal on the day of the transmission costs nothing."""

	changed: Decimal
	withdrawn: Decimal
	reference: str


FEE_CHANGES = FeeChanges(Decimal("1.5"), Decimal("0.5"), "Vorbemerkung 1.4.2 Abs. 2 und 3 KV JVKostG")


@dataclass(frozen=True, slots=True)
class ResultUse:
	"""Whether a class discloses its Ergebnisverwendung, and whether a Beschluss follows a Vorschlag disclosed with
	the Jahresabschluss."""

	disclosed: bool
	follows: bool
	reference: str


def ergebnisverwendung(size_class: SizeClass) -> ResultUse:
	match size_class:
		case SizeClass.KLEINST:
			return ResultUse(False, False, "§ 264 Abs. 1 Satz 5, § 326 Abs. 2 Satz 1 HGB")
		case SizeClass.KLEIN:
			return ResultUse(False, False, "§ 288 Abs. 1 Nr. 1, § 285 Nr. 34 HGB")
		case _:
			return ResultUse(True, True, "§ 285 Nr. 34, § 325 Abs. 1b Satz 2, § 328 Abs. 3 HGB")


def capital_problems(subscribed_capital: Decimal, registered_capital: Decimal) -> tuple[Finding, ...]:
	"""An error when the Gezeichnetes Kapital of the balance sheet is not the Stammkapital of the Handelsregister
	at the Abschlussstichtag, such as the sum of the shares the Annual Filing Settings hold."""
	if subscribed_capital == registered_capital:
		return ()
	return (
		Finding(
			DisclosureCode.CAPITAL,
			Severity.ERROR,
			"Das Gezeichnete Kapital der Bilanz ist nicht das Stammkapital des Handelsregisters am Abschlussstichtag.",
			"§ 42 Abs. 1 GmbHG, § 272 Abs. 1 Satz 1 HGB; Bundesamt für Justiz, FAQ zu Inhalts- und Formverstößen",
			amount=subscribed_capital - registered_capital,
		),
	)
