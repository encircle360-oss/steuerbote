"""The cores of Körperschaftsteuer and Gewerbesteuer are pure Python: no module of them imports Frappe."""

import ast
from pathlib import Path
from unittest import TestCase

PACKAGES = tuple(Path(__file__).resolve().parents[2] / name for name in ("kst", "gewst"))


def imports(path: Path) -> set[str]:
	tree = ast.parse(path.read_text(encoding="utf-8"))
	found: set[str] = set()
	for node in ast.walk(tree):
		if isinstance(node, ast.Import):
			found.update(alias.name for alias in node.names)
		elif isinstance(node, ast.ImportFrom) and node.module:
			found.add(node.module)
	return found


class PureTest(TestCase):
	def test_no_module_of_the_cores_imports_frappe(self):
		modules = [path for package in PACKAGES for path in sorted(package.glob("*.py"))]
		self.assertGreater(len(modules), 9)
		for path in modules:
			with self.subTest(module=path.name):
				self.assertEqual(
					{name for name in imports(path) if name.split(".")[0] in ("frappe", "erpnext")}, set()
				)
