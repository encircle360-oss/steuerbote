"""The connections of a Trade Tax Return: its ELSTER Transmissions."""

from steuerbote.steuerbote.doctype.elster_transmission.transmission import dashboard


def get_data() -> dict:
	return dashboard("Trade Tax Return")
