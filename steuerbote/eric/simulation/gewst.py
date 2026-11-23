"""The simulation of the Gewerbesteuererklärung, Datenart GewSt (Jahresdokumentation_E20_<Jahr>.ods): the structure
of an Erklärung with the main form GewSt1A, and the rules of the year in RULES."""

from steuerbote.eric.simulation import Rule, erklaerung

TITLE = "Gewerbesteuererklärung"
MAIN_FORM = "GewSt1A"
RULES: tuple[Rule, ...] = ()
"""The rules of the sheets „<Vordruck> - Regeln“ that the simulation checks beyond the structure."""

CHECKS = erklaerung.checks(TITLE, MAIN_FORM, RULES)
