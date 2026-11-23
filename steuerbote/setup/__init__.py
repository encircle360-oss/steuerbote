"""Steuerbote einrichten: the steps that set up a company, the chart it books in and its first Voranmeldungszeitraum.

steps.py holds the setup steps as plain data and puts them in the order they run, chart.py tells SKR03 from SKR04,
and rhythm.py proposes the Voranmeldungszeitraum of § 18 Absatz 2 UStG. steuerbote/steuerbote/setup.py runs the steps
on a site. This package is pure Python and never imports Frappe.
"""
