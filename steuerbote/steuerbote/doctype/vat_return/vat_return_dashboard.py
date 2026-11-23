"""The connections of a VAT Return: its ELSTER Transmissions, besides the USt-IdNr.-Bestätigungen its DocType links."""

from steuerbote.steuerbote.doctype.elster_transmission.transmission import dashboard


def get_data() -> dict:
	return dashboard("VAT Return")
