"""Gewerbesteuer of a GmbH or UG: the year data and the computation from the result of the Körperschaftsteuer.

This package is pure Python. It never imports Frappe, so it can be tested without a bench.

- years.py: the Erhebungszeiträume with the Messzahl, the Hinzurechnungen, Kürzungen and Fehlbeträge, the minimum
  Hebesatz, the provisional forms and the files of the year check.
- chain.py: compute(KstResult, GewstInputs, figures) -> GewstResult, the lines of GewSt 1 A (STEPS) and the Anlagen
  BEG (BegLine) from the result of steuerbote.kst.chain.
"""
