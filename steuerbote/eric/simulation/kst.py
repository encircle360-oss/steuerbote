"""The simulation of the Körperschaftsteuererklärung, Datenart KSt (Jahresdokumentation_E30_<Jahr>.ods): the
structure of an Erklärung with the main form KSt1, and the rules of the year in RULES."""

from steuerbote.eric.simulation import Rule, erklaerung

TITLE = "Körperschaftsteuererklärung"
MAIN_FORM = "KSt1"
RULES: tuple[Rule, ...] = ()
"""The rules of the sheets „<Vordruck> - Regeln“ that the simulation checks beyond the structure."""

CHECKS = erklaerung.checks(TITLE, MAIN_FORM, RULES)
