"""What the browser tests find on the site: the invented records that seed.py makes, the workspace Steuern and the
sidebar Steuerbote.

The module imports neither Frappe nor Playwright, so that both sides read it: the seed runs inside the bench,
the tests run outside of it against the site.
"""

# The workspace Steuern (steuerbote/steuerbote/workspace/steuern), its sections and their shortcuts, as the German
# desk shows them.
WORKSPACE_ROUTE = "/desk/steuerbote/steuern"
WORKSPACE_SECTIONS = {
	"Fristen": ("Offene Fristen",),
	"Umsatzsteuer-Voranmeldung": (
		"Neue Voranmeldung",
		"Voranmeldungen",
		"Kennzahlen (Bericht)",
		"Dauerfristanträge",
	),
	"Zusammenfassende Meldung": ("Neue ZM", "Zusammenf. Meldungen", "USt-IdNr.-Prüfungen"),
	"Jahresmeldungen": (
		"Neue USt-Erklärung",
		"Neue E-Bilanz",
		"Neue KSt-Erklärung",
		"Neue GewSt-Erklärung",
		"USt-Erklärungen",
		"E-Bilanzen",
		"KSt-Erklärungen",
		"GewSt-Erklärungen",
		"Jahresabschlüsse",
		"Jahres-Einstellungen",
		"Bilanzzuordnung",
		"Zuord. Ertragsteuern",
	),
	"Einrichtung": ("Einrichten", "Einstellungen", "Kontenzuordnung"),
}
SHORTCUTS = tuple(label for labels in WORKSPACE_SECTIONS.values() for label in labels)
# The sidebar Steuerbote (steuerbote/steuerbote/sidebar/steuerbote) as the German desk shows it to the Administrator:
# its entries in their order, each group with the entries it holds.
SIDEBAR = {
	"Steuern": (),
	"Voranmeldungen": (),
	"Dauerfristanträge": (),
	"Zusammenf. Meldungen": (),
	"USt-IdNr.-Prüfungen": (),
	"Jahresmeldungen": (
		"USt-Erklärungen",
		"E-Bilanzen",
		"KSt-Erklärungen",
		"GewSt-Erklärungen",
		"Jahresabschlüsse",
		"Jahres-Einstellungen",
		"Bilanzzuordnung",
		"Zuord. Ertragsteuern",
	),
	"Übermittlung": ("ELSTER-Übermittlung", "ERiC-Einstellungen"),
	"Berichte": (
		"Offene Fristen",
		"UStVA Kennzahlen",
		"E-Bilanz Positionen",
		"KSt/GewSt-Nachweis",
		"Fristerinnerungen",
	),
	"Einrichtung": ("Einrichten", "Einstellungen", "Kontenzuordnung"),
}
# The shortcut to the page Steuerbote einrichten, which only a System Manager or an Accounts Manager opens.
SETUP_SHORTCUT = "Einrichten"

COMPANY = "Steuerbote E2E GmbH"
ABBR = "STE2E"
YEAR = 2026
# The month of the calculated VAT Return and Recapitulative Statement, with the invoices of the seed.
MONTH = 10
MONTH_LABEL = "Oktober 2026"
# The month before, filed in Mein ELSTER, so that the ELSTER Transmission list has a row.
FILED_MONTH = 9

# The examples of the OpenAPI document of the eVatR API, as in steuerbote/vatid/tests/fakes.py.
OWN_VAT_ID = "DE123456789"
EU_VAT_ID = "ATU12345678"

DOMESTIC_CUSTOMER = "Musterkunde GmbH (E2E)"
EU_CUSTOMER = "Alpen Beratung GmbH (E2E)"
EU_SUPPLIER = "Wiener Software GmbH (E2E)"

# A sale at 19 % (Kz 81), a sonstige Leistung to the EU customer (Kz 21, line S of the ZM) and a service of the EU
# supplier under § 13b UStG (Kz 46, 47 and 67), all in MONTH.
DOMESTIC_INVOICE = "SINV-STE2E-10-1"
EU_INVOICE = "SINV-STE2E-10-2"
REVERSE_CHARGE_INVOICE = "PINV-STE2E-10-1"
DOMESTIC_NET = 1000
DOMESTIC_TAX = 190
EU_NET = 2000
REVERSE_CHARGE_NET = 300
REVERSE_CHARGE_TAX = 57

# A user with the role Accounts User alone: the tests set its password through the Administrator.
ACCOUNTANT = "steuerbote-e2e-buchhaltung@example.com"
ACCOUNTANT_ROLE = "Accounts User"

# A second company, whose drafts went to ELSTER: ELSTER accepted the Senden of its VAT Return for MONTH and of its
# Dauerfristverlängerung while their submission failed, and the Senden of its Recapitulative Statement for MONTH
# has an unknown outcome. Each draft keeps all but its remarks.
SENT_COMPANY = "Steuerbote E2E Gesendet GmbH"
SENT_ABBR = "STE2G"
# A third company with SKR03 accounts and nothing else, which the browser test of Steuerbote einrichten sets up.
SETUP_COMPANY = "Steuerbote E2E Einrichtung GmbH"
SETUP_ABBR = "STE2S"
# Its rules, tax checks and watched accounts with the defaults of SKR03: 8400 and 1576, 8400 against 1776, and 1548.
SETUP_MAPPING = {"rules": 2, "checks": 1, "watched": 1}

# A fourth company with SKR03 accounts and the mapping of "Vorgaben laden", which the browser tests of Vorgaben
# aktualisieren and of the file of a mapping change and set back.
MAPPING_COMPANY = "Steuerbote E2E Zuordnung GmbH"
MAPPING_ABBR = "STE2Z"

# The Transferticket of the accepted Senden, invented in the form of TransferTicketSType of the ELSTER Basisschema.
TRANSFERTICKET = "e2026e2etransferticketerfunden01"
# What the form of such a draft says above its fields after ELSTER accepted its Senden.
ACCEPTED_NOTE = f"Mit Transferticket {TRANSFERTICKET} übermittelt: nur noch Buchen oder berichtigen; Anmerkungen bleiben änderbar."

# A fifth company with the Körperschaft- and the Gewerbesteuererklärung of YEAR: SKR03 accounts, Annual Filing Settings
# with its shareholder and its one Betriebsstätte, the Kontenzuordnung Ertragsteuern of "Vorgaben laden" and a ledger
# of the year. Both returns are calculated drafts, and nothing of the company goes to ELSTER.
INCOME_TAX_COMPANY = "Steuerbote E2E Ertragsteuern GmbH"
INCOME_TAX_ABBR = "STE2K"
# Until ELSTER publishes the forms of YEAR, both returns take those of the Jahresdokumentation of the year before.
DOCUMENTATION_YEAR = YEAR - 1

# A sixth company with Annual Filing Settings and its Jahresabschluss of YEAR, calculated: the balances are those of the
# invented Kleinstkapitalgesellschaft of steuerbote/hgb/tests/companies.py, since the test site has no HGB-Taxonomie to
# place books with. Its Feststellung, which comes after the fiscal year, is open.
ACCOUNTS_COMPANY = "Steuerbote E2E Jahresabschluss GmbH"
ACCOUNTS_ABBR = "STE2J"
ACCOUNTS_DIRECTOR = "Erika Beispiel"

# A seventh company with the E-Bilanz of YEAR: SKR04 accounts, Annual Filing Settings, a Balance Sheet Mapping and a
# ledger of the year, with a bank of 106,000 euros and a Jahresüberschuss of 38,000. The site of the browser tests has
# no HGB-Taxonomie, so the seed calculates the E-Bilanz with the mini taxonomy of the tests of steuerbote/ebilanz in its
# place; it stays Berechnet with the finding that the taxonomy is missing, and nothing of it goes to ELSTER.
EBILANZ_COMPANY = "Steuerbote E2E E-Bilanz GmbH"
EBILANZ_ABBR = "STE2B"
# What the print shows of the bank and of the Jahresüberschuss.
EBILANZ_BANK = "106.000,00"
EBILANZ_NET_INCOME = "38.000,00"
