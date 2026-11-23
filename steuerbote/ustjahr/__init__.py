"""Umsatzsteuererklärung (form USt 2 A): the year table, the catalogue of the form, the split of the Kennzahlen of
the Voranmeldung, the computation, the Vorauszahlungssoll, the reconciliation with the filed Voranmeldungen and
the rules of ERiC that Steuerbote checks itself.

This package is pure Python. It never imports Frappe, so it can be tested without a bench. The Frappe side of the
annual return calls it in this order, each module documenting its part:

1. years.year_of() gives the year of the form with its BMF letter and the Datenart version and plugin of ERiC;
   years.filing_deadline() the deadline of § 149 Absatz 2 to 4 AO, moved by § 108 Absatz 3 AO.
2. form.catalogue_for() gives the fields of the form with their lines, Kennzahlen, sums, pairs and rate lines, and
   the rules of the Jahresdokumentation.
3. split.split() gives each account of the VAT Return Mapping its line of the annual return: the annual field of
   its rule (Choice), the default of its role, or the default line of its Kennzahl; AnnualRule adds an account
   only the annual return reads.
4. calculation.calculate() computes the fields from the LedgerLine of the year (steuerbote/ustva/calculation.py),
   with lines by hand (ManualLine); calculation.entries() gives the amounts as the return files them.
5. soll.vorauszahlungssoll() gives line 125 from the filed Voranmeldungen (Filed) and the Sondervorauszahlung,
   soll.abschlusszahlung() Kz 820 and soll.payment_due() the day it is due.
6. reconciliation.reconcile() sets the return against the filed Voranmeldungen and the runs of the Voranmeldung
   on today's ledger, period by period and Kennzahl by Kennzahl; reconciliation.journal_entries() hints at
   Journal Entries on tax accounts.
7. rules.check() runs the checks of Steuerbote and the rules of ERiC it checks itself on the amounts of
   entries() and the details of the company.

Every module keeps its messages as English templates with their values apart and lists them in MESSAGES for the
translations; what the checks report is a form.Finding with a code, a severity and the fields it names.
"""
