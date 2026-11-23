"""The structure of an Erklärung that the simulation checks: the Umsatzsteuererklärung (E50), the
Körperschaftsteuererklärung (E30) and the Gewerbesteuererklärung (E20).

Sources are the Jahresdokumentationen of the ERiC documentation 44.3.6.0, cited as JD: Jahresdokumentation_E50_2026.ods,
Jahresdokumentation_E30_2025.ods and Jahresdokumentation_E20_2025.ods, and Datenarten/ElsterErklaerung/
Formale_Plausipruefungen.ods, cited as FP. The simulation checks:

- the root of the Datenart in the namespace and the version of its year (sheet „Allg. Information“: „Für Nutzdaten muss
  der Namensraum '...' angegeben werden“ and „Als Name des Nutzdaten-Wurzelelements wird der Datenartname '...'
  verwendet“), SIM-003;
- the two Pflichtvordrucke of „Allg. Information“, the main form of the Erklärung (USt2A, KSt1, GewSt1A) and the
  Vorsatz, SIM-004;
- the fields of the Vorsatz that the rules of the sheet „Vorsatz - Regeln“ require (VORSATZ), SIM-004, the
  Steuernummer that OrdNrArt S requires (10433), SIM-004, the Unterfallart of the Datenart (sheet „Vorsatz - Felder“),
  SIM-010, and that the Zeitraum is the year of the Datenart (109000005), SIM-007;
- that the recipient of the NutzdatenHeader is the Finanzamt of the Steuernummer, the first four of its digits (FP
  10010), SIM-010.

The rules of the Vordrucke of a year are the modules', which add them to the Checks of their Datenart (ust, kst,
gewst).
"""

from functools import partial
from typing import NamedTuple
from xml.etree import ElementTree

from steuerbote.eric.datenart import Datenart
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import ERROR, Message
from steuerbote.eric.simulation import Checks, Rule, Structure, child_text

STEUERNUMMER = "S"


class Required(NamedTuple):
	"""A field of the Vorsatz that a rule requires, by its path below the Vorsatz, with its Fehlercode and text."""

	path: str
	code: str
	text: str

	@property
	def name(self) -> str:
		return self.path.rpartition("/")[2]


VORSATZ = (
	Required("Unterfallart", "10425", "Die Unterfallart muss im Feld Unterfallart angegeben werden"),
	Required("Vorgang", "10427", "Der Vorgang muss im Feld Vorgang angegeben werden"),
	Required("Zeitraum", "109000004", "Der Zeitraum muss im Feld Zeitraum angegeben werden"),
	Required("AbsName", "10100", "Der Absendername muss im Feld AbsName angegeben werden"),
	Required("AbsStr", "10110", "Die Straße des Absenders muss im Feld AbsStr angegeben werden"),
	Required("AbsOrt", "10130", "Der Ort des Absenders muss im Feld AbsOrt angegeben werden"),
	Required("Copyright", "10435", "Das Copyright muss im Feld Copyright angegeben werden"),
	Required("OrdNrArt", "10423", "Die Art der Ordnungsnummer muss im Feld OrdNrArt angegeben werden"),
	Required(
		"Rueckuebermittlung/Bescheid",
		"10438",
		"Im Feld Bescheid ist anzugeben, ob die Bereitstellung der Bescheiddaten zur elektronischen Abholung gewünscht "
		"wird",
	),
)
"""The fields of the Vorsatz that its rules require, with the Fehlercode and the text of the rule (JD, sheet „Vorsatz
- Regeln“)."""
STEUERNUMMER_RULE = Required(
	"StNr",
	"10433",
	"Es wurde im Feld OrdNrArt angegeben, dass die Steuererklärung mit einer vorhandenen Steuernummer abgegeben wird. "
	"Diese Steuernummer ist im Feld StNr zu erklären",
)


def checks(title: str, main_form: str, rules: tuple[Rule, ...] = ()) -> Checks:
	"""The Checks of an Erklärung: its structure with the main form, the rule of the recipient and ``rules``."""
	return Checks(
		structure=partial(_structure, main_form),
		filing=partial(_filing, title),
		structure_only=_structure_only,
		rules=(recipient, *rules),
	)


def recipient(root: ElementTree.Element, kind: Datenart, header: EnvelopeHeader) -> Message | None:
	"""FP 10010: with OrdNrArt S the Bundesfinanzamtsnummer of the NutzdatenHeader is the first four digits of the
	Steuernummer."""
	steuernummer = child_text(root, "Vorsatz/StNr", kind)
	if child_text(root, "Vorsatz/OrdNrArt", kind) != STEUERNUMMER or header.empfaenger == steuernummer[:4]:
		return None
	return Message(
		"SIM-010",
		f"Die Bundesfinanzamtsnummer {header.empfaenger} im NutzdatenHeader ist nicht die der Steuernummer im Vorsatz, "
		f"{steuernummer[:4]} (formale Prüfung 10010).",
		ERROR,
		"Empfaenger",
	)


def _structure(main_form: str, root: ElementTree.Element, kind: Datenart) -> Structure:
	if root.tag != f"{{{kind.namespace}}}{kind.root}" or root.get("version") != kind.root_version:
		begins = f"Die Nutzdaten beginnen nicht mit {kind.root} in der Version {kind.root_version}"
		return None, Message("SIM-003", f"{begins} im Namensraum {kind.namespace}.", ERROR, kind.root)
	for form in (main_form, "Vorsatz"):
		if root.find(f"{{{kind.namespace}}}{form}") is None:
			text = f"Der Vordruck {form} ist ein Pflichtvordruck (Jahresdokumentation, Allg. Information)."
			return None, Message("SIM-004", text, ERROR, form)
	for field in VORSATZ:
		if not child_text(root, f"Vorsatz/{field.path}", kind):
			return None, _missing(field)
	if child_text(root, "Vorsatz/OrdNrArt", kind) == STEUERNUMMER and not child_text(
		root, "Vorsatz/StNr", kind
	):
		return None, _missing(STEUERNUMMER_RULE)
	unterfallart = child_text(root, "Vorsatz/Unterfallart", kind)
	if unterfallart != kind.unterfallart:
		text = (
			f"Die Unterfallart {unterfallart} ist nicht die der Datenart {kind.name}, {kind.unterfallart} "
			"(Jahresdokumentation, Vorsatz - Felder)."
		)
		return None, Message("SIM-010", text, ERROR, "Unterfallart")
	zeitraum = child_text(root, "Vorsatz/Zeitraum", kind)
	if zeitraum != str(kind.year):
		text = f"Der Zeitraum {zeitraum} ist nicht das Jahr der Datenart, {kind.year} (Regel 109000005)."
		return None, Message("SIM-007", text, ERROR, "Zeitraum")
	return root, None


def _missing(field: Required) -> Message:
	return Message("SIM-004", f"{field.text} (Regel {field.code}).", ERROR, field.name)


def _filing(title: str, root: ElementTree.Element, kind: Datenart) -> list[str]:
	return [f"Erklärung: {title} {child_text(root, 'Vorsatz/Zeitraum', kind)}"]


def _structure_only(kind: Datenart, reason: str) -> str:
	return f"Die Simulation prüft nur Aufbau, Pflichtvordrucke und Vorsatz, nicht das XSD des Jahres {kind.year}: {reason}"
