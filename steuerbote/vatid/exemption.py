"""What a missing or invalid USt-IdNr. of the customer costs a turnover of Kz 41, 42 or 21.

The Umsatzsteuer-Voranmeldung and the Zusammenfassende Meldung name the same voucher when its customer has no valid
USt-IdNr., and both say the same sentence about it:

- Kz 41: the innergemeinschaftliche Lieferung is tax-exempt only if the customer „gegenüber dem Unternehmer eine ihm
  von einem anderen Mitgliedstaat erteilte gültige Umsatzsteuer-Identifikationsnummer verwendet“ (§ 6a Absatz 1
  Satz 1 Nummer 4 UStG), and not if the Unternehmer did not file the Zusammenfassende Meldung or filed it „im Hinblick
  auf die jeweilige Lieferung unrichtig oder unvollständig“ (§ 4 Nummer 1 Buchstabe b UStG).
- Kz 42: the ZM names the last Abnehmer of a Dreiecksgeschäft by his USt-IdNr. (§ 18a Absatz 7 Satz 1 Nummer 4 UStG).
- Kz 21: a USt-IdNr. the recipient uses shows the supplier that he is an Unternehmer (§ 3a Absatz 2 UStG, UStAE 3a.2
  Absatz 9), and the ZM names the recipient by it (§ 18a Absatz 7 Satz 1 Nummer 3 UStG).

Steuerbote cannot tax an invoice anew; the documents stop the user and say what to do.
"""

from types import MappingProxyType

KENNZAHLEN = ("41", "42", "21")

_CONSEQUENCES = MappingProxyType(
	{
		"41": "Ohne gültige USt-IdNr. des Abnehmers ist die innergemeinschaftliche Lieferung nicht steuerfrei "
		"(§ 6a Abs. 1 Satz 1 Nr. 4 UStG); ohne richtige Zeile in der ZM entfällt die Steuerfreiheit ebenso "
		"(§ 4 Nr. 1 Buchst. b UStG).",
		"42": "Ohne gültige USt-IdNr. des letzten Abnehmers kann die ZM die Lieferung im Dreiecksgeschäft nicht "
		"melden (§ 18a Abs. 7 Satz 1 Nr. 4 UStG).",
		"21": "Ohne gültige USt-IdNr. des Leistungsempfängers fehlt der Nachweis, dass er Unternehmer ist "
		"(§ 3a Abs. 2 UStG, UStAE 3a.2 Abs. 9), und die ZM kann die Leistung nicht melden "
		"(§ 18a Abs. 7 Satz 1 Nr. 3 UStG).",
	}
)


def consequence(kennzahl: str) -> str:
	"""The sentence on what a turnover of ``kennzahl`` loses without a valid USt-IdNr. of the customer."""
	try:
		return _CONSEQUENCES[kennzahl]
	except KeyError:
		raise ValueError(f"Kz {kennzahl} needs no USt-IdNr. of the customer") from None
