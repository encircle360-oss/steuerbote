"""The Gewerbesteuererklärung as ELSTER XML: the Nutzdaten E20 of a VZ, which ERiC takes for the Datenart
GewSt_<Jahr>.

Sources are the ERiC documentation 44.3.6.0 (https://download.elster.de/download/eric/eric_44/): the schema
E20-2025.xsd and Jahresdokumentation_E20_2025.ods, cited as JD.

The Nutzdaten are the element E20 in the namespace and the version of the Datenart of the VZ
(steuerbote.eric.datenart.gewst), and in it the Vordrucke of steuerbote.gewst.form in the order of the xs:sequence
of E20: GewSt1A once, then one Anlage BEG per holding, up to 99 („max. lfd. Nr. Vordruck“ of the JD), and the
Vorsatz with the Unterfallart 20 as the last element. The E20 has no Indexfeld. steuerbote.elster.kst_xml.build
writes them, with the same checks as for the E30; SCHEMAS holds the contexts of the E20 that repeat, with their
maxOccurs in E20-2025.xsd, and the year of the schema the tests check the Nutzdaten against: 2026 is written as E20
version 2026 in the namespace of 2026 and tested against E20-2025.xsd after a rewrite of namespace and version in
the test.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable
from types import MappingProxyType

from lxml import etree

from steuerbote.elster.kst_xml import Schema, build
from steuerbote.elster.ustva_xml import serialized
from steuerbote.elster.vorsatz import Vorsatz
from steuerbote.gewst.form import catalogue_for
from steuerbote.kst.form import Vordruck
from steuerbote.ustva.years import UnknownYearError

SCHEMAS: MappingProxyType[int, Schema] = MappingProxyType(
	{
		2026: Schema(
			2026,
			{
				"GewSt1A/St_Gest": 10,
				"GewSt1A/Hinz/P_8_Nr_8/Einz": 99,
				"GewSt1A/Kuerz/Gew_PersG/Einz": 99,
				"GewSt1A/Kuerz/Zuw/Stb_Zweck/Einz": 99,
				"GewSt1A/Kuerz/Zuw/Stift/Spenden/Einz": 99,
				"GewSt1A/Kuerzung_AStG/Einz": 99,
				"GewSt1A/Weit_Ang/Gew_Ertr_OG/Einz": 99,
			},
			2025,
		)
	}
)


def schema_for(year: int) -> Schema:
	try:
		return SCHEMAS[year]
	except KeyError:
		known = ", ".join(str(known_year) for known_year in SCHEMAS)
		raise UnknownYearError(f"no schema E20 for {year}; known years: {known}") from None


def nutzdaten(year: int, vordrucke: Iterable[Vordruck], vorsatz: Vorsatz) -> etree._Element:
	"""The element E20 of the VZ with the Vordrucke and the Vorsatz."""
	return build(catalogue_for(year), schema_for(year), vordrucke, vorsatz)


def to_nutzdaten(year: int, vordrucke: Iterable[Vordruck], vorsatz: Vorsatz) -> str:
	"""The Nutzdaten E20 as text, without a declaration, as the DatenTeil of steuerbote.eric.header takes them."""
	return serialized(nutzdaten(year, vordrucke, vorsatz))
