"""The E-Bilanz of a GmbH or UG (§ 5b EStG) on the HGB-Taxonomie, from the balances of its books to the instance.

This package is pure Python with lxml. It never imports Frappe, so it can be tested without a bench. The Frappe side
of the E-Bilanz calls it in this order, each module documenting its part:

1. positions.structure() gives what a GmbH reports for its case: the components, each position of Bilanz, GuV and
   Betriebsvermögensvergleich admissible for the legal form, the GKV and the fiscal year with its mark, the
   Mussfelder it sends, NIL where the books cannot fill them, those it must not send, and the rows and columns of
   the Anlagenspiegel.
2. calculation.calculate() takes the balances of the books as the Bilanzzuordnung maps them, AccountBalance, and the
   corrections and lines by hand, Adjustment, and gives each position its amount in the direction of the position,
   the sums along the calculation linkbase and the Jahresüberschuss of the Bilanz from the GuV;
   calculation.betriebsvermoegensvergleich() adds the Betriebsvermögensvergleich.
3. anlagenspiegel.anlagenspiegel() builds the Anlagenspiegel (brutto) from the rows of the assets, Row, with the
   columns nobody books by hand marked with their reason.
4. ueberleitung.ueberleitung() turns a Handelsbilanz into the Steuerbilanz ERiC checks, with the
   Überleitungsrechnung of its differences, Transfer, and the steuerlicher Ausgleichsposten.
5. kontennachweis.kontennachweis() gives the Kontensalden of each position.
6. gcd.facts() writes the Global Common Data from the master data of the settings, MasterData.
7. instance.build() puts it together as a report of the profile FISCAL of steuerbote/xbrl/profiles.py, checks it and
   gives the facts, the findings and the instance; steuerbote/elster/ebilanz_xml.py wraps the instance for ERiC.

defaults.py holds the defaults of the Bilanzzuordnung for SKR03 and SKR04. Every finding is a positions.Finding with
a code, a German sentence, its source and what it is about; an error holds the E-Bilanz back from „Bereit“.
"""
