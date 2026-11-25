"""The tables of docs/ust-idnr-pruefung.md show the statuses, faults and member states of the code."""

from pathlib import Path
from unittest import TestCase

from steuerbote.vatid.bzst import STATUSES
from steuerbote.vatid.result import Outcome
from steuerbote.vatid.transport import UrllibFetch
from steuerbote.vatid.ustid import MEMBER_STATES
from steuerbote.vatid.vies import FAULTS

DOC = Path(__file__).resolve().parents[3] / "docs" / "ust-idnr-pruefung.md"
OUTCOMES = {Outcome.VALID: "gültig", Outcome.INVALID: "ungültig", Outcome.UNKNOWN: "unbekannt"}


def table(heading: str, header: list[str]) -> list[list[str]]:
	"""The rows of the table under the heading whose head is header."""
	text = DOC.read_text(encoding="utf-8")
	start = text.index(f"\n{heading}\n")
	following = text.find("\n#", start + 1)
	lines = text[start : following if following > 0 else len(text)].splitlines()
	tables: list[list[list[str]]] = []
	previous = ""
	for line in lines:
		if line.startswith("|"):
			if not previous.startswith("|"):
				tables.append([])
			tables[-1].append([cell.strip() for cell in line.strip().strip("|").split("|")])
		previous = line
	(found,) = [rows for rows in tables if rows[0] == header]
	return found[2:]


class StatusTableTest(TestCase):
	def test_shows_every_status_of_the_catalogue_in_its_order(self):
		rows = table("## Statusmeldungen des BZSt", ["Status", "HTTP", "Meldung", "Ergebnis", "VIES"])
		self.assertEqual([row[0] for row in rows], [f"`{code}`" for code in STATUSES])
		for row, status in zip(rows, STATUSES.values(), strict=True):
			with self.subTest(status=status.code):
				self.assertEqual(
					row[1:],
					[
						"\N{EN DASH}" if status.http is None else str(status.http),
						status.message,
						OUTCOMES[status.outcome],
						"ja" if status.unavailable else "nein",
					],
				)


class FaultTableTest(TestCase):
	def test_shows_every_fault_of_vies_with_its_outcome(self):
		rows = table("### Fehler von VIES", ["`faultstring`", "Bedeutung laut WSDL", "Ergebnis"])
		self.assertEqual([row[0] for row in rows], [f"`{code}`" for code in FAULTS])
		for row, fault in zip(rows, FAULTS.values(), strict=True):
			with self.subTest(fault=fault.code):
				self.assertEqual(row[2], OUTCOMES[fault.outcome])


class MemberStateTableTest(TestCase):
	def test_shows_every_member_state_with_the_structure_of_the_merkblatt(self):
		rows = table(
			"## Aufbau einer USt-IdNr.",
			["Kennzeichen", "Mitgliedstaat", "Stellen nach dem Kennzeichen laut BZSt"],
		)
		self.assertEqual(
			rows, [[state.code, state.name, state.structure] for state in MEMBER_STATES.values()]
		)


class TimeoutTest(TestCase):
	def test_the_wait_is_described_as_urllib_counts_it(self):
		"""urllib applies its timeout to the connection and to each wait for data, not to the whole answer; an answer
		that comes in parts may take longer, which the docs say instead of promising 60 seconds per answer."""
		text = DOC.read_text(encoding="utf-8")
		seconds = int(UrllibFetch().timeout_seconds)
		self.assertNotIn(f"bis zu {seconds} Sekunden auf jede Antwort", text)
		self.assertIn(
			f"{seconds} Sekunden auf den Aufbau der Verbindung und auf jedes Stück der Antwort", text
		)
