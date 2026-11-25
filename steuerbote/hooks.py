from pathlib import Path

app_name = "steuerbote"
app_title = "Steuerbote"
app_publisher = "encircle360 GmbH"
app_description = "ELSTER tax filings for ERPNext: Umsatzsteuer-Voranmeldung, Dauerfristverlängerung, Zusammenfassende Meldung, Umsatzsteuer-, Körperschaftsteuer- and Gewerbesteuererklärung, E-Bilanz and Jahresabschluss with Offenlegung for the Unternehmensregister"
app_email = "oss@encircle360.com"
app_license = "AGPL-3.0-or-later"
app_home = "/desk/steuern"

required_apps = ["frappe/erpnext"]

# The apps screen and the app switcher of the desk list an app from this entry. Steuerbote also mounts its
# dock on the rail of ERPNext (dock/steuerbote), and where the desk has that rail, Frappe keeps a mounted app
# off the apps screen; the entry still offers Steuerbote as the default app of a user.
# There is no app_logo_url: Frappe takes the logo of the login page from those of all installed apps.
add_to_apps_screen = [
	{
		"name": app_name,
		"logo": "/assets/steuerbote/images/steuerbote-logo.svg",
		"title": app_title,
		"route": app_home,
		"has_permission": "steuerbote.permissions.has_app_permission",
	}
]

# The icon of the module on the rail and in the header of its sidebar.
app_include_icons = ["/assets/steuerbote/icons/module-icons.svg"]

# The custom field on the Journal Entry, and the print formats of the app as the defaults of their DocTypes:
# a standard DocType takes its default print format only from a Property Setter.
fixtures = [
	{"dt": "Custom Field", "filters": [["module", "=", "Steuerbote"]]},
	{"dt": "Property Setter", "filters": [["module", "=", "Steuerbote"]]},
]

# ERPNext's "Delete Company Transactions" (Transaction Deletion Record) deletes the documents of every DocType
# linked to the company with frappe.db.delete, past on_trash, unless the DocType is listed here: the filings and
# the proof of the confirmations of USt-IdNrn. record what went to the tax authorities, and the Annual Filing
# Settings hold what no ledger gives again, such as the day of the Feststellung of a Jahresabschluss and the
# Vorträge and Vorauszahlungen of the notices. The annual documents join once the app brings their DocType: the
# record links each name of the list to its DocType and refuses one without it.
_ANNUAL_DOCUMENTS = (
	"Annual VAT Return",
	"Electronic Balance Sheet",
	"Corporate Income Tax Return",
	"Trade Tax Return",
	"Annual Accounts",
)
_DOCTYPES = Path(__file__).resolve().parent / "steuerbote" / "doctype"
company_data_to_be_ignored = [
	"VAT ID Confirmation",
	"Recapitulative Statement",
	"VAT Return Extension",
	"VAT Return",
	"ELSTER Transmission",
	"VAT Return Prior Filing",
	"Annual Filing Settings",
	*(name for name in _ANNUAL_DOCUMENTS if (_DOCTYPES / name.lower().replace(" ", "_")).is_dir()),
]

# The files of an ELSTER Transmission and the answer kept with a VAT ID Confirmation stay as they were stored.
doc_events = {
	"File": {
		"before_validate": "steuerbote.steuerbote.record_files.keep_unchanged",
		"on_trash": "steuerbote.steuerbote.record_files.keep_while_recorded",
		"before_rename": "steuerbote.steuerbote.record_files.keep_name",
	}
}

# Every day the recipients in the VAT Return Settings of each company hear of its deadlines not filed. Every week
# Steuerbote loads the Mindestversionsliste of ERiC and tells the System Managers of what the installed runtimes
# lack, as the ERiC licence asks the Softwarehersteller to check regularly for new versions (§ 5 Abs. 4).
scheduler_events = {
	"daily": ["steuerbote.steuerbote.deadlines.send_reminders"],
	"weekly": ["steuerbote.steuerbote.doctype.eric_settings.eric_settings.check_versions"],
}

# bench migrate runs after every update of the app; the ERiC Settings then show the version it brings.
after_migrate = ["steuerbote.steuerbote.doctype.eric_settings.eric_settings.refresh_produkt_version"]

# The steps Steuerbote einrichten runs besides its own (steuerbote/steuerbote/setup.py): the Kontenzuordnung
# Ertragsteuern and the Bilanzzuordnung, each with the defaults of SKR03 or SKR04.
steuerbote_setup_steps = [
	{
		"key": "books_start",
		"label": "Start in Steuerbote",
		"order": 35,
		"needs": ["vat_return_settings", "vat_return_mapping"],
		"run": "steuerbote.steuerbote.setup.check_books_start",
	},
	{
		"key": "income_tax_mapping",
		"label": "Income Tax Mapping",
		"order": 40,
		"run": "steuerbote.steuerbote.doctype.income_tax_mapping.setup.run",
	},
	{
		"key": "balance_sheet_mapping",
		"label": "Balance Sheet Mapping",
		"order": 50,
		"run": "steuerbote.steuerbote.doctype.balance_sheet_mapping.setup.run",
	},
]
