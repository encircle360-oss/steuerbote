app_name = "steuerbote"
app_title = "Steuerbote"
app_publisher = "encircle360 GmbH"
app_description = "ELSTER tax filings for ERPNext: Umsatzsteuer-Voranmeldung first, year-end filings later"
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
# the proof of the confirmations of USt-IdNrn. record what went to the tax authorities.
company_data_to_be_ignored = [
	"VAT ID Confirmation",
	"Recapitulative Statement",
	"VAT Return Extension",
	"VAT Return",
	"ELSTER Transmission",
]

# The files of an ELSTER Transmission and the answer kept with a VAT ID Confirmation stay as they were stored.
doc_events = {
	"File": {
		"before_validate": "steuerbote.steuerbote.record_files.keep_unchanged",
		"on_trash": "steuerbote.steuerbote.record_files.keep_while_recorded",
		"before_rename": "steuerbote.steuerbote.record_files.keep_name",
	}
}

# Every day the recipients in the VAT Return Settings of each company hear of its deadlines not filed.
scheduler_events = {"daily": ["steuerbote.steuerbote.deadlines.send_reminders"]}
