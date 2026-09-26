from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from iris.graph import visible_world
from iris.profile_seed import import_seed
from iris.store import Store


SEED = Path(__file__).parent / "fixtures" / "example_profile.yaml"


class ProfileSeedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.store = Store(root / "iris.db", root / "state")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_import_is_atomic_idempotent_and_filters_protected(self) -> None:
        result = import_seed(self.store, SEED)
        self.assertEqual(result["added_nodes"], 4)
        self.assertEqual(result["added_edges"], 3)
        self.assertEqual(result["state_sequence"], 1)
        second = import_seed(self.store, SEED)
        self.assertTrue(second["noop"])
        sequence, state = self.store.state()
        self.assertEqual(sequence, 1)
        self.assertIn("context:private", state["world"]["nodes"])
        ordinary = visible_world(state["world"])
        self.assertNotIn("context:private", ordinary["nodes"])
        self.assertIn("person:example", ordinary["nodes"])
        conflicting = [edge for edge in ordinary["edges"] if edge.get("properties", {}).get("conflict_group") == "example-dates"]
        self.assertEqual(len(conflicting), 2)
        self.assertTrue(all(edge["status"] == "disputed" for edge in conflicting))


if __name__ == "__main__":
    unittest.main()
