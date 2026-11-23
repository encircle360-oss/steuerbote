"""The simulation of the E-Bilanz, Datenart Bilanz: the frame of ebilanz_000002.xsd around the XBRL instance, and the
rules of the taxonomy in RULES.

Sources are the ERiC documentation 44.3.6.0: Datenarten/ElsterBilanz/Bilanz/Schema/ebilanz_000002.xsd, whose EBilanz
holds the stichtag „im Format YYYYMMTT“ and then xbrli:xbrl and has the attribute version, an integer from 1 to 2;
the sheet „Header - Felder“ of Jahresdokumentation_Bilanz_Taxonomie_6_9.ods, whose stichtag is a „Datum JJJJMMTT mit
Zusatzprüfung“; and the ERiC-Entwicklerhandbuch, Tabelle 9-20: ERiC checks no schema of the Nutzdaten of the Datenart
Bilanz, „Nutzdatenschemavalidierung: Nein“, so the simulation does not either. The XBRL instance is the plugin's to
check; the rules the simulation checks of it, such as Aktiva equal to Passiva, come in RULES.
"""

from datetime import datetime
from xml.etree import ElementTree

from steuerbote.eric.datenart import Datenart
from steuerbote.eric.result import ERROR, Message
from steuerbote.eric.simulation import Checks, Rule, Structure

XBRL = "{http://www.xbrl.org/2003/instance}xbrl"
VERSIONS = range(1, 3)
"""The versions of the interface ebilanz_000002.xsd takes."""
STICHTAG_FORMAT = "%Y%m%d"
RULES: tuple[Rule, ...] = ()
"""The rules of the taxonomy that the simulation checks of the XBRL instance."""


def _structure(root: ElementTree.Element, kind: Datenart) -> Structure:
	version = root.get("version", "")
	if (
		root.tag != f"{{{kind.namespace}}}{kind.root}"
		or not version.isdigit()
		or int(version) not in VERSIONS
	):
		begins = f"Die Nutzdaten beginnen nicht mit {kind.root} in der Version {kind.root_version}"
		return None, Message("SIM-003", f"{begins} im Namensraum {kind.namespace}.", ERROR, kind.root)
	stichtag = root.find(f"{{{kind.namespace}}}stichtag")
	if stichtag is None:
		text = "Die E-Bilanz braucht den Stichtag vor der XBRL-Instanz (ebilanz_000002.xsd)."
		return None, Message("SIM-004", text, ERROR, "stichtag")
	if root.find(XBRL) is None:
		text = "Die E-Bilanz braucht die XBRL-Instanz xbrli:xbrl nach dem Stichtag (ebilanz_000002.xsd)."
		return None, Message("SIM-004", text, ERROR, "xbrl")
	if [child.tag for child in root] != [stichtag.tag, XBRL]:
		text = "Die E-Bilanz enthält genau den Stichtag und danach die XBRL-Instanz (ebilanz_000002.xsd)."
		return None, Message("SIM-003", text, ERROR, kind.root)
	if _stichtag(stichtag.text) is None:
		text = (
			f"Der Stichtag {(stichtag.text or '').strip()} ist kein Datum JJJJMMTT (Jahresdokumentation, Header - "
			"Felder)."
		)
		return None, Message("SIM-010", text, ERROR, "stichtag")
	return root, None


def _stichtag(text: str | None) -> datetime | None:
	value = (text or "").strip()
	if len(value) != len("JJJJMMTT") or not value.isdigit():
		return None
	try:
		return datetime.strptime(value, STICHTAG_FORMAT)
	except ValueError:
		return None


def _filing(root: ElementTree.Element, kind: Datenart) -> list[str]:
	stichtag = _stichtag(root.findtext(f"{{{kind.namespace}}}stichtag"))
	return [f"Stichtag: {stichtag:%d.%m.%Y}", f"Taxonomie: {kind.taxonomy}"]


def _structure_only(kind: Datenart, reason: str) -> str:
	return f"Die Simulation prüft nur den Rahmen der E-Bilanz, nicht ihre XBRL-Instanz: {reason}"


CHECKS = Checks(_structure, _filing, _structure_only, RULES, schema=False)
