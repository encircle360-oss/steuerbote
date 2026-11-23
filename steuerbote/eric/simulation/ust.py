"""The simulation of the Umsatzsteuererklärung, Datenart USt (Jahresdokumentation_E50_<Jahr>.ods): the structure of
an Erklärung with the main form USt2A, and the rules of the year in RULES."""

from steuerbote.eric.simulation import Rule, erklaerung

TITLE = "Umsatzsteuererklärung"
MAIN_FORM = "USt2A"
RULES: tuple[Rule, ...] = ()
"""The rules of the sheet „USt2A - Regeln“ that the simulation checks beyond the structure."""

CHECKS = erklaerung.checks(TITLE, MAIN_FORM, RULES)
