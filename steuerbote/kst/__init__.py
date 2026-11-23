"""Körperschaftsteuer of a GmbH or UG: the year data, the categories of the Income Tax Mapping and the computation.

This package is pure Python. It never imports Frappe, so it can be tested without a bench.

- years.py: the Veranlagungszeiträume with their rates and limits, the provisional forms and the files of the year
  check.
- categories.py: the categories of the Income Tax Mapping and the trading classes, the Mapping of a company, and
  classify(), which sums the ledger lines per category with the postings behind each amount.
- holdings.py: § 8b KStG per holding (Holding, HoldingResult, exemption) and p8b(), the lines 156 to 201 of Anlage
  GK.
- losses.py: what carries over from year to year, the Verlustabzug of § 10d EStG (loss_deduction, Anlage Verluste),
  the Termingeschäfte of § 15 Absatz 4 Satz 3 EStG (derivatives, Anlage GK lines 51 and 52) and the Zuwendungen of
  § 9 Absatz 1 Nummer 2 KStG (donations, Anlage Z); minimum_taxation() is the rule of § 10d Absatz 2.
"""
