"""The Jahresabschluss of a GmbH or UG for the Offenlegung or Hinterlegung (§§ 264 to 289 and 325 to 329 HGB).

This package is pure Python. It never imports Frappe, so it can be tested without a bench:

- size.py: the size classes of §§ 267, 267a HGB, measured on two consecutive Abschlussstichtage;
- schemes.py: the balance sheet of § 266 HGB and the income statement of § 275 HGB, each position with its concept
  of the HGB taxonomy;
- statement.py: the balance sheet and the income statement of a size class from the balances of the books;
- notes.py: what Kleinst states under the balance sheet and what klein states in the Anhang;
- disclosure.py: what is published, by when, after which Feststellung, and what a late filing costs.
"""
