"""The pure core the annual filings of stage 3 share, without Frappe.

The Umsatzsteuererklärung, the E-Bilanz, the Körperschaft- and the Gewerbesteuererklärung and the Jahresabschluss
live the same way: lifecycle.py holds their statuses and the moves between them, overrides.py their corrections and
lines by hand, findings.py what holds a document back from „Bereit“, and corrections.py how each Datenart corrects a
filing. Their Frappe layer is steuerbote/steuerbote/annual_filing.py.

documentation.py reads the Jahresdokumentationen of the ERiC documentation as data, and yearcheck.py compares the data
of every Datenart with them: ``python -m steuerbote.jahresmeldung.yearcheck``, what a Jahreswechsel has to change.
"""
