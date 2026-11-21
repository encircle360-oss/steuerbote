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
	"Einstellungen",
	"Kontenzuordnung",
)

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
