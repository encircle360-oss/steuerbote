"""What the browser tests find on the site: the invented records that seed.py makes, and the workspace Steuern.

The module imports neither Frappe nor Playwright, so that both sides read it: the seed runs inside the bench,
the tests run outside of it against the site.
"""

# The workspace Steuern (steuerbote/steuerbote/workspace/steuern) and its shortcuts, as the German desk shows them.
WORKSPACE_ROUTE = "/desk/steuerbote/steuern"
SHORTCUTS = (
	"Offene Fristen",
	"Neue Voranmeldung",
	"Voranmeldungen",
	"Kennzahlen (Bericht)",
	"Dauerfristanträge",
	"Neue ZM",
	"Zusammenf. Meldungen",
	"USt-IdNr.-Prüfungen",
	"Einrichten",
	"Einstellungen",
	"Kontenzuordnung",
)
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

# The Transferticket of the accepted Senden, invented in the form of TransferTicketSType of the ELSTER Basisschema.
TRANSFERTICKET = "e2026e2etransferticketerfunden01"
# What the form of such a draft says above its fields after ELSTER accepted its Senden.
ACCEPTED_NOTE = f"Mit Transferticket {TRANSFERTICKET} übermittelt: nur noch Buchen oder berichtigen; Anmerkungen bleiben änderbar."
