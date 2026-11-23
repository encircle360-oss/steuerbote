"""The E-Bilanz of a GmbH or UG (§ 5b EStG) on the HGB-Taxonomie, from the balances of its books to the instance.

This package is pure Python with lxml. It never imports Frappe, so it can be tested without a bench. The Frappe side
of the E-Bilanz gives it plain values and takes its results, each module documenting its part:

1. positions.structure() gives what a GmbH or UG reports for its Case: the components, each position of Bilanz, GuV
   and Betriebsvermögensvergleich admissible for the legal form, the GKV and the fiscal year with its mark, the
   Mussfelder it sends, NIL where the books cannot fill them, those it must not send, and the rows and columns of
   the Anlagenspiegel.
2. instance.build() takes that structure, the master data of the GCD, gcd.MasterData, and the Sources the books
   give, and makes every part in turn:
   - calculation.calculate() gives each position its amount from the balances, AccountBalance, and the corrections
     and lines by hand, Adjustment: in the direction of the position, summed along the calculation linkbase, with
     the Jahresüberschuss of the Bilanz from the GuV;
   - ueberleitung.ueberleitung() turns a Handelsbilanz into the Steuerbilanz ERiC checks, with the
     Überleitungsrechnung of its differences, Transfer, and the steuerlicher Ausgleichsposten;
   - calculation.betriebsvermoegensvergleich() compares the Betriebsvermögen of that Steuerbilanz, with the changes
     of the equity the books do not say, EquityChanges;
   - anlagenspiegel.anlagenspiegel() builds the Anlagenspiegel (brutto) from the rows of the assets, Row, a column
     the Asset module does not book entered by hand with its reason;
   - kontennachweis.kontennachweis() gives the Kontensalden, or the reason a case of taxonomy 6.9 sends none;
   - gcd.facts() writes the Global Common Data, gcd.check() says what the master data lack;
   and gives an instance.EBilanz with its parts, the report of the profile FISCAL of steuerbote/xbrl/profiles.py,
   every finding, the instance and the findings for the table „Befunde“.
3. steuerbote/elster/ebilanz_xml.py writes its Nutzdaten for ERiC, steuerbote/eric/simulation/bilanz.py checks them
   in the simulation.

defaults.py holds the defaults of the Bilanzzuordnung for SKR03 and SKR04. Every finding is a positions.Finding with
a code, a German sentence, its source and what it is about; an error holds the E-Bilanz back from „Bereit“.
"""
