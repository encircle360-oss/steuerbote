"""The connections of an Annual Accounts: the E-Bilanzen of its company and year, which name it as the Jahresabschluss
Berechnen compares their Handelsbilanz with."""

from frappe import _


def get_data() -> dict:
	return {
		"fieldname": "annual_accounts",
		"transactions": [{"label": _("Electronic Balance Sheet"), "items": ["Electronic Balance Sheet"]}],
	}
