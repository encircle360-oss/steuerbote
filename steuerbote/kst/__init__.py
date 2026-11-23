"""Körperschaftsteuer of a GmbH or UG: the year data, the categories of the Income Tax Mapping and the computation.

This package is pure Python. It never imports Frappe, so it can be tested without a bench.

- years.py: the Veranlagungszeiträume with their rates and limits, the provisional forms and the files of the year
  check.
- categories.py: the categories of the Income Tax Mapping and the trading classes, the Mapping of a company, and
  classify(), which sums the ledger lines per category with the postings behind each amount.
"""
