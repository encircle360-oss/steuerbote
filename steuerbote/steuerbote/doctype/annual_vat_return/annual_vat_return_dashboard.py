"""The connections of an Annual VAT Return: its ELSTER Transmissions."""

from steuerbote.steuerbote.doctype.elster_transmission.transmission import dashboard


def get_data() -> dict:
	return dashboard("Annual VAT Return")
