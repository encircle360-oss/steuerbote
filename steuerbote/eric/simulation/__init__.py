"""The checks of the simulation by Datenart, which steuerbote.eric.fake runs.

Each Datenart has its Checks: the structure of its Nutzdaten, the rules the simulation checks beyond it, the lines
its placeholder protocol shows and whether the simulation checks the Nutzdaten against the schema of the Datenart.
The UStVA and ZMDO have theirs in steuerbote.eric.fake. The Erklärungen and the E-Bilanz have a module each, ust,
kst, gewst and bilanz, with the structure of their Datenart (erklaerung for the three Erklärungen) and the rules of
their Jahresdokumentation, which the modules of the annual filings add.

This package is pure Python and never imports Frappe.
"""

from collections.abc import Callable
from typing import NamedTuple
from xml.etree import ElementTree

from steuerbote.eric.datenart import Datenart
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import Message

type Structure = tuple[ElementTree.Element | None, Message | None]
"""What the protocol reads of the Nutzdaten, or the error of their structure."""
type Rule = Callable[[ElementTree.Element, Datenart, EnvelopeHeader], Message | None]
"""A rule on Nutzdaten of a sound structure, with the header of their delivery: its error, or None."""
type Hints = Callable[[ElementTree.Element, Datenart], tuple[Message, ...]]
"""The rules of kind Hinweis that what the protocol reads of the Nutzdaten sets off, as their hints."""


def no_hints(found: ElementTree.Element, kind: Datenart) -> tuple[Message, ...]:
	"""The hints of a Datenart whose Hinweise the simulation leaves to ERiC: none."""
	return ()


class Checks(NamedTuple):
	"""How the simulation checks the Nutzdaten of a Datenart and what its protocol says of them.

	``structure`` takes the parsed Nutzdaten and returns what the protocol reads, or the error of their structure;
	``filing`` gives the lines of the protocol from it; ``structure_only`` says why the schema was not checked;
	``rules`` run once the structure holds; ``schema`` says whether the Nutzdaten are checked against the schema of
	the Datenart, as ERiC checks them; ``hints`` gives the Hinweise of Nutzdaten without errors, which hold nothing
	back.
	"""

	structure: Callable[[ElementTree.Element, Datenart], Structure]
	filing: Callable[[ElementTree.Element, Datenart], list[str]]
	structure_only: Callable[[Datenart, str], str]
	rules: tuple[Rule, ...] = ()
	schema: bool = True
	hints: Hints = no_hints


def child_text(element: ElementTree.Element, path: str, kind: Datenart) -> str:
	"""The text of the element at the path below ``element`` in the namespace of the Datenart, stripped; empty without
	one."""
	found = element.find("/".join(f"{{{kind.namespace}}}{part}" for part in path.split("/")))
	return "" if found is None or found.text is None else found.text.strip()
