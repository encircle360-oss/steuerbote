"""What a GmbH or UG publishes of its Jahresabschluss, by when, after which Feststellung, and what being late costs.

What is published. The Geschäftsführer transmit „den festgestellten Jahresabschluss, den Lagebericht, den
Bestätigungsvermerk oder den Vermerk über dessen Versagung“ to the operator of the Unternehmensregister (§ 325
Abs. 1 HGB). The Geschäftsführer of a small company „nur die Bilanz und den Anhang zu übermitteln haben“, and „Der
Anhang braucht die die Gewinn- und Verlustrechnung betreffenden Angaben nicht zu enthalten“ (§ 326 Abs. 1 HGB).
Those of a Kleinst „nur die Bilanz zu übermitteln haben und dabei die Einstellung in das Unternehmensregister durch
dauerhafte Hinterlegung verlangen können“ if they notify the operator „dass sie zwei der drei in § 267a Absatz 1
genannten Merkmale für die nach § 267 Absatz 4 maßgeblichen Abschlussstichtage nicht überschreiten“ (§ 326 Abs. 2
HGB). A deposited balance sheet is open „nur auf Antrag durch Übermittlung einer
Kopie“ (§ 9 Abs. 6 Satz 3 HGB). Steuerbote deposits a Kleinst unless told otherwise, the default of the
Offenlegung research. Kleinst and klein draw up no Lagebericht (§ 264 Abs. 1 Satz 4 HGB) and are not audited
(§ 316 Abs. 1 Satz 1 HGB). Steuerbote prepares the disclosure of Kleinst and klein; for mittelgroß, which § 327 HGB
spares part of it, and groß it names the parts only.

The Annual Accounts read the class of the fiscal year from steuerbote.hgb.size, the form of the balance sheet from
steuerbote.hgb.schemes and the Angaben from steuerbote.hgb.notes. Text of §§ 9, 264, 316, 325, 326, 327 HGB as read
on gesetze-im-internet.de on 23 November 2026.
"""

from dataclasses import dataclass
from enum import Enum

from steuerbote.hgb.size import SizeClass


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
