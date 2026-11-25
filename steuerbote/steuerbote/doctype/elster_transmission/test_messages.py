"""The summary of the messages of an ELSTER Transmission, without a bench."""

import json
from pathlib import Path
from unittest import TestCase

from steuerbote.eric.result import ERROR, HINT
from steuerbote.steuerbote.doctype.elster_transmission import messages

MESSAGE_DOCTYPE = (
	Path(__file__).resolve().parents[1] / "elster_transmission_message" / "elster_transmission_message.json"
)


class SummaryTest(TestCase):
	def test_counts_the_errors_and_hints_and_keeps_the_first_three_of_each(self):
		rows = [
			{"severity": "hint", "code": "610001003", "text": "Hinweise während der Plausibilitätsprüfung."},
			{"severity": "error", "code": "11085153", "text": "Das Jahr des Wechsels ..."},
			*(
				{"severity": "hint", "code": f"1108515{index}", "text": f"Hinweis {index}"}
				for index in range(4)
			),
		]
		summary = messages.summary(rows)
		self.assertEqual((summary["errors"], summary["hints"]), (1, 5))
		self.assertEqual(summary["first_errors"], [{"code": "11085153", "text": "Das Jahr des Wechsels ..."}])
		self.assertEqual(
			[message["code"] for message in summary["first_hints"]], ["610001003", "11085150", "11085151"]
		)

	def test_a_message_of_steuerbote_may_come_without_a_code(self):
		summary = messages.summary([{"severity": "error", "code": None, "text": "Der Lauf brach ab."}])
		self.assertEqual(summary["first_errors"], [{"code": "", "text": "Der Lauf brach ab."}])

	def test_without_messages_there_is_nothing_to_show(self):
		self.assertEqual(
			messages.summary([]), {"errors": 0, "hints": 0, "first_errors": [], "first_hints": []}
		)

	def test_the_kinds_are_those_of_the_messages_of_a_transmission(self):
		fields = json.loads(MESSAGE_DOCTYPE.read_text(encoding="utf-8"))["fields"]
		(severity,) = (field for field in fields if field["fieldname"] == "severity")
		self.assertEqual(severity["options"].split("\n"), [ERROR, HINT])


class ReadableTest(TestCase):
	"""ERiC names a field by its path in the Nutzdaten; the form names it as the Vordruck does."""

	def test_a_kennzahl_of_the_voranmeldung(self):
		text, field = messages.readable(
			"Es wurde Vorsteuer in Feld '$/Elster[1]/DatenTeil[1]/Nutzdatenblock[1]/Nutzdaten[1]/Anmeldungssteuern[1]"
			"/Steuerfall[1]/Umsatzsteuervoranmeldung[1]/Kz61[1]$' eingetragen.",
			"/Anmeldungssteuern[1]/Steuerfall[1]/Umsatzsteuervoranmeldung[1]/Kz61[1]",
			"UStVA",
			2026,
		)
		self.assertEqual((text, field), ("Es wurde Vorsteuer in Feld 'Kz 61' eingetragen.", "Kz 61"))

	def test_a_field_of_an_erklaerung_by_its_line(self):
		for datenart, path, expected in (
			("USt", "/E50[1]/USt2A[1]/Allg[1]/Dauer_Unt_Eig[1]/E3001401[1]", "Zeile 19 (E3001401)"),
			("KSt", "/KSt1[1]/AE[1]/Einzel[1]/E8122101[1]", "KSt1 Zeile 22c (E8122101)"),
			("GewSt", "/GewSt1A[1]/Hinz[1]/P_8_Nr_1_Wj1[1]/E4003703[1]", "GewSt1A Zeile 56 (E4003703)"),
		):
			with self.subTest(datenart=datenart):
				self.assertEqual(
					messages.readable(f"Feld '${path}$' fehlt.", path, datenart, 2026),
					(f"Feld '{expected}' fehlt.", expected),
				)

	def test_keeps_what_it_does_not_know(self):
		for datenart, year, path in (
			("Bilanz", None, "/Kontext[1]/gaap:bs.ass[1]"),
			("KSt", 2026, "/KSt1[1]/E9999999[1]"),
			("USt", 2026, "/E50[1]/USt2A[1]/E9999999[1]"),
			("KSt", 2020, "/KSt1[1]/AE[1]/Einzel[1]/E8122101[1]"),
			("ZMDO", None, "/Header[1]/ndh:DatenLieferant[1]"),
		):
			with self.subTest(path=path):
				name = path.rpartition("/")[2].partition("[")[0]
				self.assertEqual(
					messages.readable(f"Feld '${path}$'.", path, datenart, year), (f"Feld '{name}'.", name)
				)
		self.assertEqual(messages.readable("Ohne Feld.", None, "UStVA", 2026), ("Ohne Feld.", None))
		self.assertEqual(
			messages.readable("Mussfeld.", "gcd:genInfo.company.id.name", "Bilanz", None),
			("Mussfeld.", "gcd:genInfo.company.id.name"),
		)
