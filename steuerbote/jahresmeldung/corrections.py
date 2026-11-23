"""How each annual filing is corrected: the Berichtigung by Datenart.

A key is filed once (steuerbote.jahresmeldung.lifecycle); every further filing of it is a Berichtigung, a new and
complete document that corrects a filed one, marked as its Datenart asks:

| Datenart | Berichtigung | Source |
|---|---|---|
| USt (E50) | Kz 110 „Berichtigte Steuererklärung“, E3000601 in line 3, a yes field: „Bitte die Zeile 3 nur angeben, wenn Sie eine bereits übermittelte Erklärung berichtigen wollen.“ A second return of the year is filed only with it | JD E50 2026, sheets „USt2A - Felder“ and „USt2A - Regeln“, rule 30002 |
| KSt (E30), GewSt (E20) | No field marks a Berichtigung, so it is a new full declaration. The qualified free text of § 150 Abs. 7 AO, „Angaben, die nach seiner Auffassung Anlass für eine Bearbeitung durch Amtsträger sind“, may explain it: KSt 1 line 13 (E8001305, the key 1 to 4, and E8001304, the text) and GewSt 1 A line 21 (E4003204, E4003205), each pair filed together or not at all (rules 8900735 and 40128). Whether ELSTER expects the text with a Berichtigung is unverified | § 150 Abs. 7 Satz 1 AO; JD E30 2025, „KSt1 - Felder“, „KSt1 - Regeln“; JD E20 2025, „GewSt1A - Felder“, „GewSt1A - Regeln“ |
| Bilanz | The Status des Berichts of the GCD, genInfo.report.id.revisionStatus: erstmalig for the first filing; „berichtigt“, „geändert“ or „berichtigt und geändert“ for a correction, „sonstige Korrektur“ for one outside Bilanz and GuV, and „identischer Abschluss mit differenzierteren Informationen“ for a filing that only adds information. „Korrektur durch Finanzverwaltung“ is not for a filing | FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d; de-gcd-2025-04-01.xsd, -label-de.xml and -reference-fiscal.xml of taxonomy 6.9 |
| Offenlegung | „Wird der Jahresabschluss [...] geändert, so ist auch die Änderung [...] offenzulegen.“ Before the Einstellung an order is changed or supplemented, which raises the fees by half, or cancelled, which halves them and costs nothing on the calendar day of the order; afterwards it is neither withdrawn nor deleted, and an error of one's own is corrected by an order of its own | § 325 Abs. 1b Satz 1 HGB; JVKostG, Anlage 1, Vorbemerkung 1.4.2 Abs. 2 Satz 2 and Abs. 3; Allgemeine Nutzungsbedingungen für das Unternehmensregister, § 13 Abs. 3 and § 14 Buchst. c |

The Vorauszahlungssoll of a berichtigte Umsatzsteuererklärung is the Kz 816 of the return it corrects
(steuerbote.ustjahr.soll).

The ERiC documentation is 44.3.6.0 (https://download.elster.de/download/eric/eric_44/), cited as JD for its
Jahresdokumentationen; the FAQ is that of esteuer.de (https://www.esteuer.de/, download/taxonomie/
FAQ_Version_2026-01.pdf); the Nutzungsbedingungen are https://www.publikations-plattform.de/order/D088.pdf.

This module is pure Python and never imports Frappe.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, StrEnum
from types import MappingProxyType


class Problem(Enum):
	UNKNOWN_DATENART = "unknown_datenart"
	UNKNOWN_STATUS = "unknown_status"
	FIRST_WITH_STATUS = "first_with_status"
	CORRECTION_WITHOUT_STATUS = "correction_without_status"
	NOT_FOR_FILING = "not_for_filing"


class CorrectionError(ValueError):
	"""A Berichtigung its Datenart does not take; ``value`` names what it refused."""

	def __init__(self, problem: Problem, value: object = None) -> None:
		self.problem = problem
		self.value = "" if value is None else str(value)
		super().__init__(f"{problem.value}: {self.value}" if self.value else problem.value)


class Method(Enum):
	MARKED = "marked"
	"""A field of the Erklärung marks the Berichtigung."""
	FULL_DECLARATION = "full_declaration"
	"""A new full declaration, which no field marks."""
	REVISION_STATUS = "revision_status"
	"""The Status des Berichts of the GCD of the E-Bilanz."""
	DISCLOSED_AGAIN = "disclosed_again"
	"""The change of the Jahresabschluss is disclosed again."""


@dataclass(frozen=True, slots=True)
class Berichtigung:
	"""How a Datenart, or the Offenlegung, is corrected: by which fields, in which line of the form, whether the way is
	verified, and its source."""

	datenart: str
	method: Method
	fields: tuple[str, ...] = ()
	line: int | None = None
	verified: bool = True
	source: str = ""


REVISION_STATUS = "genInfo.report.id.revisionStatus"
"""The Status des Berichts in the GCD of the E-Bilanz."""

UST = Berichtigung(
	"USt",
	Method.MARKED,
	("E3000601",),
	3,
	source="Jahresdokumentation_E50_2026.ods, USt2A - Felder E3000601 and USt2A - Regeln 30002",
)
KST = Berichtigung(
	"KSt",
	Method.FULL_DECLARATION,
	("E8001305", "E8001304"),
	13,
	verified=False,
	source="§ 150 Abs. 7 Satz 1 AO; Jahresdokumentation_E30_2025.ods, KSt1 - Felder and KSt1 - Regeln 8900735",
)
GEWST = Berichtigung(
	"GewSt",
	Method.FULL_DECLARATION,
	("E4003204", "E4003205"),
	21,
	verified=False,
	source="§ 150 Abs. 7 Satz 1 AO; Jahresdokumentation_E20_2025.ods, GewSt1A - Felder and GewSt1A - Regeln 40128",
)
BILANZ = Berichtigung(
	"Bilanz",
	Method.REVISION_STATUS,
	(REVISION_STATUS,),
	source="FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d; de-gcd-2025-04-01 of taxonomy 6.9",
)
OFFENLEGUNG = Berichtigung(
	"Offenlegung",
	Method.DISCLOSED_AGAIN,
	source=(
		"§ 325 Abs. 1b Satz 1 HGB; JVKostG, Anlage 1, Vorbemerkung 1.4.2; Allgemeine Nutzungsbedingungen für das "
		"Unternehmensregister, §§ 13 and 14"
	),
)

BERICHTIGUNGEN: MappingProxyType[str, Berichtigung] = MappingProxyType(
	{rule.datenart: rule for rule in (UST, KST, GEWST, BILANZ, OFFENLEGUNG)}
)
"""The Berichtigung by the name of the Datenart (steuerbote.eric.datenart), and of the Offenlegung."""

MARKED_YES = "1"
"""The value of a yes field, Formatkennzeichen J: „JaFeld mit Wert für Ja 1“ (JD, „Allg. Information“)."""


def berichtigung_of(datenart: str) -> Berichtigung:
	try:
		return BERICHTIGUNGEN[datenart]
	except KeyError:
		raise CorrectionError(Problem.UNKNOWN_DATENART, datenart) from None


def marker(rule: Berichtigung, *, is_correction: bool) -> str | None:
	"""The value of the field that marks a Berichtigung, for a Datenart that has one: Kz 110 of the USt 2 A."""
	return MARKED_YES if rule.method is Method.MARKED and is_correction else None


class RevisionStatus(StrEnum):
	"""The values of the Status des Berichts a filing of the E-Bilanz takes, as the GCD of taxonomy 6.9 names them."""

	FIRST = "E"
	CORRECTED = "B"
	CHANGED = "G"
	CORRECTED_AND_CHANGED = "BG"
	OTHER_CORRECTION = "sK"
	MORE_DETAIL = "I"


LABELS: MappingProxyType[RevisionStatus, str] = MappingProxyType(
	{
		RevisionStatus.FIRST: "erstmalig",
		RevisionStatus.CORRECTED: "berichtigt",
		RevisionStatus.CHANGED: "geändert",
		RevisionStatus.CORRECTED_AND_CHANGED: "berichtigt und geändert",
		RevisionStatus.OTHER_CORRECTION: "sonstige Korrektur",
		RevisionStatus.MORE_DETAIL: "identischer Abschluss mit differenzierteren Informationen",
	}
)
"""The labels of de-gcd-2025-04-01-label-de.xml."""

BY_THE_TAX_ADMINISTRATION = "K"
"""„Korrektur durch Finanzverwaltung“, notPermittedFor „Einreichung an Finanzverwaltung“."""


def revision_status(is_correction: bool, chosen: object) -> RevisionStatus:
	"""The Status des Berichts of a filing of the E-Bilanz: erstmalig for the first filing of its key, and for a
	further one the status chosen, which says how it corrects."""
	value = str(chosen or "")
	if value == BY_THE_TAX_ADMINISTRATION:
		raise CorrectionError(Problem.NOT_FOR_FILING, value)
	if not is_correction:
		if value and value != RevisionStatus.FIRST:
			raise CorrectionError(Problem.FIRST_WITH_STATUS, value)
		return RevisionStatus.FIRST
	if not value or value == RevisionStatus.FIRST:
		raise CorrectionError(Problem.CORRECTION_WITHOUT_STATUS, value)
	try:
		return RevisionStatus(value)
	except ValueError:
		raise CorrectionError(Problem.UNKNOWN_STATUS, value) from None


def revision_status_concept(status: RevisionStatus) -> str:
	"""The concept of the GCD that states the status, such as genInfo.report.id.revisionStatus.revisionStatus.B."""
	return f"{REVISION_STATUS}.revisionStatus.{status.value}"


class RegisterChange(Enum):
	CHANGE = "change"
	"""Before the Einstellung, documents „ergänzt oder geändert übermittelt“ (Vorbemerkung 1.4.2 Abs. 2 Satz 2)."""
	CANCEL = "cancel"
	"""Before the Einstellung, the request not to einstellen the documents (Vorbemerkung 1.4.2 Abs. 3)."""
	BERICHTIGUNG = "berichtigung"
	"""After the Einstellung: „Eine Korrektur kann bei selbstverursachten Fehlern nur eigenständig durch Übermittlung
	eines separaten Berichtigungsauftrags erfolgen“, since orders „können nach erfolgter Einstellung [...] grundsätzlich
	weder widerrufen noch auf andere Weise ganz oder teilweise rückgängig gemacht werden“ (Nutzungsbedingungen, § 13
	Abs. 3)."""


def register_changes(*, eingestellt: bool) -> tuple[RegisterChange, ...]:
	"""How an order to the Unternehmensregister changes, before and after its Einstellung."""
	return (RegisterChange.BERICHTIGUNG,) if eingestellt else (RegisterChange.CHANGE, RegisterChange.CANCEL)


def fee_factor(change: RegisterChange, *, same_day: bool = False) -> Decimal:
	"""The factor of the fees of the Einstellung: „in diesen Fällen erhöhen sich die Gebühren dieses Abschnitts um 50
	Prozent“ for a change, „ermäßigen sich die Gebühren nach diesem Abschnitt um 50 Prozent“ for a cancellation, and
	„Die Gebühren entstehen nicht, wenn [...] die Nichteinstellung an demselben Kalendertag verlangt wird, an dem die
	Übermittlung der Unterlagen erfolgt ist“ (JVKostG, Anlage 1, Vorbemerkung 1.4.2); a Berichtigungsauftrag is an
	order of its own, with the fees of one."""
	if change is RegisterChange.CHANGE:
		return Decimal("1.5")
	if change is RegisterChange.CANCEL:
		return Decimal("0") if same_day else Decimal("0.5")
	return Decimal("1")
