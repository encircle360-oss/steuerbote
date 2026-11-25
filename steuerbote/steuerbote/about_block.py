"""The block Über Steuerbote for the desk, in the language of the user (the pure part is about.py)."""

import frappe
from frappe import _

from steuerbote.steuerbote import about


@frappe.whitelist()
def render() -> str:
	return about.render(_)
