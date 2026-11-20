"""Who the desk offers Steuerbote to."""

import frappe

# The roles of the workspace "Steuern"; the DocTypes and the report of the app grant theirs to the same roles.
APP_ROLES = frozenset({"Accounts Manager", "Accounts User", "System Manager"})


def has_app_permission() -> bool:
	"""Whether the apps screen of the desk lists Steuerbote for the session user."""
	return not APP_ROLES.isdisjoint(frappe.get_roles())
