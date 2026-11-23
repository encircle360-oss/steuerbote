from unittest import TestCase

from steuerbote.mappings.diff import Change, Comparison, Difference, Origin, apply, compare

RULE_81 = {"place": "rule", "kennzahl": "81", "side": "credit", "tax_rate": None}
RULE_86 = {"place": "rule", "kennzahl": "86", "side": "credit", "tax_rate": None}
RULE_46 = {"place": "rule", "kennzahl": "46", "side": "debit", "tax_rate": "19"}
WATCHED = {"place": "watched", "level": "blocking"}
HINT = {"place": "watched", "level": "hint"}
CHECK = {"base_accounts": "8400", "tax_accounts": "1776", "side": "credit"}
CHECK_WIDER = {"base_accounts": "8400, 8401", "tax_accounts": "1776", "side": "credit"}


def account(number: str) -> tuple[str, str]:
	return ("account", number)


def check(label: str) -> tuple[str, str]:
	return ("check", label)


class CompareTest(TestCase):
	def test_items_that_read_the_same_are_unchanged(self):
		items = {account("8400"): RULE_81, check("Umsatzsteuer 19 %"): CHECK}
		self.assertEqual(compare(items, dict(items), dict(items)), Comparison((), tuple(items)))

	def test_an_item_only_the_proposal_has_is_added(self):
		(difference,) = compare({}, {account("1548"): WATCHED}, {}).differences
		self.assertEqual(
			difference,
			Difference(account("1548"), Change.ADDED, Origin.DEFAULTS, None, WATCHED, ("place", "level")),
		)

	def test_an_item_only_the_mapping_has_is_removed(self):
		(difference,) = compare({account("1548"): WATCHED}, {}, {account("1548"): WATCHED}).differences
		self.assertEqual(
			(
				difference.change,
				difference.origin,
				difference.current,
				difference.proposed,
				difference.fields,
			),
			(Change.REMOVED, Origin.DEFAULTS, WATCHED, None, ("place", "level")),
		)

	def test_a_changed_item_names_the_fields_that_differ(self):
		(difference,) = compare({account("8400"): RULE_81}, {account("8400"): RULE_86}, {}).differences
		self.assertEqual((difference.change, difference.fields), (Change.CHANGED, ("kennzahl",)))

	def test_a_change_of_place_names_every_field_of_both_places(self):
		(difference,) = compare({account("1567"): WATCHED}, {account("1567"): RULE_46}, None).differences
		self.assertEqual(difference.fields, ("place", "kennzahl", "side", "tax_rate", "level"))

	def test_an_empty_field_of_an_added_item_differs_from_nothing(self):
		(difference,) = compare({}, {account("8400"): RULE_81}, None).differences
		self.assertEqual(difference.fields, ("place", "kennzahl", "side"))

	def test_the_differences_follow_the_mapping_and_then_the_proposal(self):
		current = {account("8400"): RULE_81, account("8300"): RULE_86, account("1548"): WATCHED}
		proposed = {account("1600"): WATCHED, account("8400"): RULE_86, account("8300"): RULE_86}
		comparison = compare(current, proposed, None)
		self.assertEqual(
			[difference.key for difference in comparison.differences],
			[account("8400"), account("1548"), account("1600")],
		)
		self.assertEqual(comparison.unchanged, (account("8300"),))


class OriginTest(TestCase):
	"""The base is what the mapping took over from the defaults."""

	def test_a_difference_the_user_left_as_the_defaults_gave_it_comes_from_the_defaults(self):
		base = {account("8400"): RULE_81, account("1548"): WATCHED}
		current = dict(base)
		proposed = {account("8400"): RULE_86, account("1600"): WATCHED}
		differences = compare(current, proposed, base).differences
		self.assertEqual(
			[(difference.key, difference.change, difference.origin) for difference in differences],
			[
				(account("8400"), Change.CHANGED, Origin.DEFAULTS),
				(account("1548"), Change.REMOVED, Origin.DEFAULTS),
				(account("1600"), Change.ADDED, Origin.DEFAULTS),
			],
		)
		self.assertTrue(all(difference.proposes for difference in differences))

	def test_a_difference_the_user_made_is_the_users_own(self):
		base = {account("8400"): RULE_81, account("1548"): WATCHED, check("Umsatzsteuer 19 %"): CHECK}
		current = {account("8400"): RULE_86, account("1548"): HINT, account("3123"): RULE_46}
		proposed = {account("8400"): RULE_81, account("1548"): WATCHED, check("Umsatzsteuer 19 %"): CHECK}
		differences = compare(current, proposed, base).differences
		self.assertEqual(
			[(difference.key, difference.change, difference.origin) for difference in differences],
			[
				(account("8400"), Change.CHANGED, Origin.OWN),
				(account("1548"), Change.CHANGED, Origin.OWN),
				(account("3123"), Change.REMOVED, Origin.OWN),
				(check("Umsatzsteuer 19 %"), Change.ADDED, Origin.OWN),
			],
		)
		self.assertFalse(any(difference.proposes for difference in differences))

	def test_a_change_of_both_the_user_and_the_defaults_is_the_users_own(self):
		base = {check("Umsatzsteuer 19 %"): CHECK}
		current = {check("Umsatzsteuer 19 %"): {**CHECK, "side": "debit"}}
		proposed = {check("Umsatzsteuer 19 %"): CHECK_WIDER}
		(difference,) = compare(current, proposed, base).differences
		self.assertEqual((difference.origin, difference.fields), (Origin.OWN, ("base_accounts", "side")))

	def test_the_same_change_of_the_user_and_the_defaults_is_no_difference(self):
		comparison = compare(
			{account("8400"): RULE_86}, {account("8400"): RULE_86}, {account("8400"): RULE_81}
		)
		self.assertEqual(comparison, Comparison((), (account("8400"),)))

	def test_without_a_base_the_origin_is_unknown(self):
		(difference,) = compare({account("8400"): RULE_81}, {account("8400"): RULE_86}, None).differences
		self.assertEqual((difference.origin, difference.proposes), (Origin.UNKNOWN, False))


class ApplyTest(TestCase):
	def setUp(self):
		self.current = {account("8400"): RULE_81, account("1548"): HINT, account("3123"): RULE_46}
		self.proposed = {
			account("1600"): WATCHED,
			account("8400"): RULE_86,
			account("1548"): WATCHED,
			check("Umsatzsteuer 19 %"): CHECK,
		}

	def test_takes_over_the_chosen_differences_and_keeps_everything_else(self):
		result = apply(self.current, self.proposed, {account("8400"), account("3123"), account("1600")})
		self.assertEqual(
			list(result.items()),
			[(account("8400"), RULE_86), (account("1548"), HINT), (account("1600"), WATCHED)],
		)

	def test_added_items_come_last_in_the_order_of_the_proposal(self):
		result = apply(self.current, self.proposed, {check("Umsatzsteuer 19 %"), account("1600")})
		self.assertEqual(
			list(result),
			[account("8400"), account("1548"), account("3123"), account("1600"), check("Umsatzsteuer 19 %")],
		)

	def test_nothing_chosen_keeps_the_mapping(self):
		self.assertEqual(apply(self.current, self.proposed, ()), self.current)

	def test_everything_chosen_gives_the_proposal(self):
		every = {*self.current, *self.proposed}
		self.assertEqual(dict(apply(self.current, self.proposed, every)), dict(self.proposed))
		self.assertEqual(
			list(apply({}, self.proposed, every)),
			list(self.proposed),
			"an empty mapping takes the order of the file",
		)
