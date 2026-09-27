import tempfile
import unittest
from pathlib import Path

from iris.store import Store


class BraidStateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.store = Store(root / "iris.db", root)

    def tearDown(self):
        self.temp.cleanup()

    def test_channels_remain_distinct_and_scope_controls_retrieval(self):
        experience = self.store.add_memory_entry(scope="task:one", channel="experience", content="The gate denied a claim.")
        meaning = self.store.add_memory_entry(scope="skill:ai_systems", channel="cognitive_semantic", content="Speech is not proof of effect.", derived_from=[experience["id"]])
        emotional = self.store.add_memory_entry(scope="task:one", channel="emotional_semantic", content="The denial felt clarifying.", derived_from=[experience["id"]])
        self.store.set_active_context("world:iris", "task:one", ["skill:ai_systems"])
        retrieved = self.store.memory_entries()
        self.assertEqual({item["channel"] for item in retrieved}, {"experience", "cognitive_semantic", "emotional_semantic"})
        self.assertEqual(next(item for item in retrieved if item["id"] == emotional["id"])["derived_from"], [experience["id"]])
        self.store.set_active_context("world:iris", "task:two", [])
        self.assertEqual(self.store.memory_entries(), [])
        self.assertEqual(meaning["scope"], "skill:ai_systems")

    def test_affect_is_bounded_idempotent_and_separate_from_emotional_memory(self):
        transition = self.store.apply_affect("event-1", {"trust": 3.0, "surprise": 2.0})
        self.assertEqual(transition["after"]["trust"], 53.0)
        with self.assertRaises(ValueError):
            self.store.apply_affect("event-1", {"trust": 1.0})
        with self.assertRaises(ValueError):
            self.store.apply_affect("event-2", {"trust": 11.0})
        self.assertEqual(self.store.memory_entries(), [])

    def test_affect_preview_validates_without_committing(self):
        proposed = {name: 50.0 for name in ("joy", "sadness", "fear", "anger", "trust", "disgust", "surprise", "anticipation")}
        proposed["trust"] = 55.0
        preview = self.store.preview_affect(proposed)
        self.assertFalse(preview["committed"])
        self.assertEqual(preview["delta"]["trust"], 5.0)
        self.assertEqual(self.store.effective_affect()["history"], [])
        proposed["trust"] = 80.0
        with self.assertRaises(ValueError):
            self.store.preview_affect(proposed)


if __name__ == "__main__":
    unittest.main()
