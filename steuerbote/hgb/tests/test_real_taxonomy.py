"""The Offenlegung against the HGB-Taxonomie 6.9 of esteuer.de (steuerbote/xbrl/tests/real.py), in both of its views:
the mini taxonomy of the Offenlegung is an extract of them, every place an Angabe takes stands in them, and the
invented companies pass the checks of the profile DISCLOSURE and are written as against the mini taxonomy."""

from unittest import TestCase

from steuerbote.hgb import instance
from steuerbote.hgb.instance import SIGNATURE, SLOTS
from steuerbote.hgb.tests import companies
from steuerbote.hgb.tests import taxonomy as mini
from steuerbote.hgb.tests.companies import GOLDEN, canonical, golden
from steuerbote.xbrl.taxonomy import BALANCE_SHEET, Concept, View
from steuerbote.xbrl.tests import real

VIEWS = (View.COMMERCIAL, View.COMMERCIAL_MICROBILG)


def shape(concept: Concept) -> tuple:
	"""What the mini taxonomy keeps of a concept, without the particles of a tuple."""
	content = concept.content
	return (
		concept.namespace,
		concept.kind,
		concept.substitution_group,
		concept.item_type,
		concept.period_type,
		concept.balance,
		concept.abstract,
		concept.nillable,
		None if content is None else (content.group, content.min_occurs, content.max_occurs),
	)


class ExtractTest(TestCase):
	"""Each concept and arc of steuerbote/hgb/tests/taxonomy.py as the package has it."""

	def test_each_concept_as_in_the_views(self):
		for view in VIEWS:
			loaded = real.view(view)
			for name, concept in mini.CONCEPTS.items():
				with self.subTest(view=view, concept=name):
					self.assertIn(name, loaded.concepts)
					self.assertEqual(shape(concept), shape(loaded.concepts[name]))

	def test_the_particles_of_each_tuple_in_their_order(self):
		for view in VIEWS:
			loaded = real.view(view)
			for name, concept in mini.CONCEPTS.items():
				if concept.content is None:
					continue
				with self.subTest(view=view, concept=name):
					particles = list(loaded.concepts[name].content.particles)
					for particle in concept.content.particles:
						self.assertIn(particle, particles)
					positions = [particles.index(particle) for particle in concept.content.particles]
					self.assertEqual(positions, sorted(positions))

	def test_each_arc_as_in_the_views(self):
		for view in VIEWS:
			loaded = real.view(view)
			for role, arcs in mini.PRESENTATION.items():
				with self.subTest(view=view, role=role):
					found = {(arc.parent, arc.child, arc.order) for arc in loaded.presentation[role].arcs}
					self.assertLessEqual({(arc.parent, arc.child, arc.order) for arc in arcs}, found)
			with self.subTest(view=view, role="calculation"):
				found = {
					(arc.parent, arc.child, arc.weight) for arc in loaded.calculation[BALANCE_SHEET].arcs
				}
				self.assertLessEqual(
					{(arc.parent, arc.child, arc.weight) for arc in mini.CALCULATION_ARCS}, found
				)

	def test_the_positions_above_each_concept_and_the_sums_among_them(self):
		"""What the checks of the profile walk: every parent a concept of the extract has in the four presentation
		networks, and every arc of the calculation of the Bilanz between two of its concepts."""
		for view in VIEWS:
			loaded = real.view(view)
			for role, arcs in mini.PRESENTATION.items():
				network = loaded.presentation[role]
				above = {
					(arc.parent, arc.child, arc.order)
					for name in mini.CONCEPTS
					for arc in network.parents(name)
				}
				with self.subTest(view=view, role=role):
					self.assertEqual(above, {(arc.parent, arc.child, arc.order) for arc in arcs})
			calculation = {
				(arc.parent, arc.child, arc.weight)
				for arc in loaded.calculation[BALANCE_SHEET].arcs
				if arc.parent in mini.CONCEPTS and arc.child in mini.CONCEPTS
			}
			with self.subTest(view=view, role="calculation"):
				self.assertEqual(
					calculation, {(arc.parent, arc.child, arc.weight) for arc in mini.CALCULATION_ARCS}
				)


class PlacesTest(TestCase):
	"""The places of the Angaben, named as in the taxonomy 6.10 where its names did not change: each of them stands in
	both views of 6.9, so a name the loader does not find fails here."""

	def test_each_place_of_an_angabe_and_of_the_signatures(self):
		names = {
			f"de-gaap-ci:{concept}"
			for slots in SLOTS.values()
			for slot in slots
			for concept in (slot.text, slot.amount)
			if concept
		}
		names |= {
			f"de-gaap-ci:{SIGNATURE}.{part}"
			for part in (
				"place",
				"date",
				"type",
				"type.name",
				"person",
				"person.name",
				"person.otherattributes",
			)
		}
		names |= {
			f"de-gaap-ci:{concept}"
			for concept in (instance.CONTINGENCIES, instance.OTHER_BELOW, instance.NENNBETRAG, SIGNATURE)
		}
		for view in VIEWS:
			loaded = real.view(view)
			with self.subTest(view=view):
				self.assertEqual(sorted(name for name in names if not loaded.presented(name)), [])

	def test_every_concept_a_class_publishes(self):
		for name, offenlegung in companies.instances().items():
			loaded = real.view(offenlegung.view)
			with self.subTest(name=name):
				self.assertEqual(
					[concept for concept in offenlegung.published if not loaded.presented(concept)], []
				)


class InstancesTest(TestCase):
	def test_the_invented_companies_pass_every_check(self):
		for name, offenlegung in companies.instances().items():
			with self.subTest(name=name):
				self.assertEqual(instance.check(offenlegung, real.view(offenlegung.view)), ())

	def test_written_as_against_the_mini_taxonomy(self):
		for name in GOLDEN:
			offenlegung = companies.instances()[name]
			with self.subTest(name=name):
				self.assertEqual(
					canonical(instance.write(offenlegung, real.view(offenlegung.view))),
					canonical(golden(name)),
				)

	def test_every_instance_as_against_the_mini_taxonomy(self):
		for name, offenlegung in companies.instances().items():
			with self.subTest(name=name):
				self.assertEqual(
					instance.write(offenlegung, real.view(offenlegung.view)),
					instance.write(offenlegung, mini.view(offenlegung.view)),
				)
