"""The connections of an Electronic Balance Sheet: its ELSTER Transmissions."""

from steuerbote.steuerbote.doctype.elster_transmission.transmission import dashboard


def get_data() -> dict:
	return dashboard("Electronic Balance Sheet")
