from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.llm.plugin_tools import plugin_class_to_tool_spec, plugins_to_tool_specs  # noqa: E402


class DummyPluginA:
    name = "dummy_a"
    description = "dummy a description"

    def match(self, event_type="message") -> bool:  # pragma: no cover
        return False

    def handle(self):  # pragma: no cover
        pass


class DummyPluginB:
    name = "dummy_b"
    description = "dummy b description"

    def match(self, event_type="message") -> bool:  # pragma: no cover
        return False

    def handle(self):  # pragma: no cover
        pass


class TestPluginTools(unittest.TestCase):
    def test_plugin_class_to_tool_spec(self):
        spec = plugin_class_to_tool_spec(DummyPluginA)
        self.assertEqual(spec.name, "dummy_a")
        self.assertEqual(spec.description, "dummy a description")
        self.assertEqual(spec.parameters.get("type"), "object")
        self.assertEqual(spec.parameters.get("required"), [])
        self.assertTrue(spec.parameters.get("additionalProperties"))

    def test_plugins_to_tool_specs_dedupe(self):
        specs = plugins_to_tool_specs([DummyPluginA, DummyPluginA, DummyPluginB])
        self.assertEqual(len(specs), 2)
        self.assertEqual({s.name for s in specs}, {"dummy_a", "dummy_b"})


if __name__ == "__main__":
    unittest.main(verbosity=2)

