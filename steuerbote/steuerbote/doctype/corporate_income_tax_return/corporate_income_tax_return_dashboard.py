"""The connections of a Corporate Income Tax Return: its ELSTER Transmissions."""

from steuerbote.steuerbote.doctype.elster_transmission.transmission import dashboard


def get_data() -> dict:
	return dashboard("Corporate Income Tax Return")
