"""The connections of a VAT Return: its ELSTER Transmissions."""

from steuerbote.steuerbote.doctype.elster_transmission.transmission import dashboard


def get_data() -> dict:
	return dashboard("VAT Return")
