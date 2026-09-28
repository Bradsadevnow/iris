from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from iris import server
from iris.imagination_registry import ImaginationPackRegistry


ROOT = Path(__file__).resolve().parents[1]
PACKS = ROOT / "seeds" / "imagination_packs"


class ImaginationRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ImaginationPackRegistry(PACKS, ROOT)

    def test_discovers_rich_inert_pack(self) -> None:
        packs = self.registry.list_packs()
        self.assertEqual([item["slug"] for item in packs], ["villain"])
        detail = self.registry.pack("villain")
        self.assertEqual(detail["id"], "imagination-pack:villain")
        self.assertGreater(detail["primitive_count"], 600)
        self.assertGreater(detail["edge_count"], 700)

    def test_lens_projection_is_bounded_and_explains_selection(self) -> None:
        projection = self.registry.project("villain", lens="lens:role", query="compliance",
                                           limit=12, token_budget=1800)
        self.assertLessEqual(len(projection["nodes"]), 12)
        self.assertLessEqual(projection["estimated_tokens"], 1800)
        self.assertGreater(projection["excluded_count"], 0)
        self.assertTrue(all("role" in node["lanes"] for node in projection["nodes"]))
        self.assertTrue(all("query" in node["inclusion_reason"] for node in projection["nodes"]))
        self.assertIn("not canonical world facts", projection["rendered_context"])

    def test_character_cards_have_one_semantic_home(self) -> None:
        graph = self.registry.graph("villain")
        selectable = [item for item in graph["primitives"] if item["classification"]["selectable"]]
        self.assertTrue(all(len(item["lanes"]) == 1 for item in selectable))

        roles = self.registry.project("villain", lens="lens:role", limit=500, token_budget=16000)
        identity = self.registry.project("villain", lens="lens:identity", limit=500, token_budget=32000)
        purpose = self.registry.project("villain", lens="lens:purpose", limit=500, token_budget=32000)
        contribution = self.registry.project("villain", lens="lens:contribution", limit=500, token_budget=16000)
        flaws = self.registry.project("villain", lens="lens:flaws", limit=500, token_budget=32000)
        self.assertEqual({item["kind"] for item in roles["nodes"]}, {"exposures", "trait_profile"})
        self.assertEqual({item["kind"] for item in identity["nodes"]},
                         {"families", "modifiers", "trait_profile"})
        self.assertNotIn("Ceremonial Luxury", {item["label"] for item in identity["nodes"]})
        self.assertNotIn("Clean Horror", {item["label"] for item in identity["nodes"]})
        self.assertEqual({item["classification"]["clusters"][0] for item in identity["nodes"]},
                         {"archetype", "temperament", "voice"})
        self.assertIn("values", {item["classification"]["clusters"][0] for item in purpose["nodes"]})
        self.assertEqual({item["kind"] for item in contribution["nodes"]},
                         {"competencies", "trait_profile"})
        self.assertIn("Compliance Theater", {item["label"] for item in roles["nodes"]})
        self.assertNotIn("Deception Class", {item["label"] for item in roles["nodes"]})
        self.assertNotIn("Deception Class", {item["label"] for item in contribution["nodes"]})
        self.assertIn("actively making things worse", {item["label"] for item in flaws["nodes"]})
        self.assertNotIn("actively making things worse", {item["label"] for item in contribution["nodes"]})
        self.assertNotIn("microwaving fish at work", {item["label"] for item in flaws["nodes"]})
        security = next(item for item in roles["nodes"] if item["label"] == "Security And Logistics")
        self.assertIn("cleanup specialist", security["content"]["variants"])
        self.assertNotIn("dies before act two", {item["label"] for item in flaws["nodes"]})
        self.assertLess(len(selectable), 120)
        original_voice = next(item for item in graph["primitives"] if item["label"] == "Shareholder Calm")
        self.assertFalse(original_voice["classification"]["selectable"])
        self.assertEqual(original_voice["classification"]["collapsed_into"],
                         "primitive:collapse:voice-corporate-calm")

    def test_selected_node_brings_cross_lens_neighborhood(self) -> None:
        selected = "primitive:families:corporate-predator"
        projection = self.registry.project("villain", lens="lens:contribution", selected=[selected],
                                           limit=80, token_budget=10000)
        by_id = {item["id"]: item for item in projection["nodes"]}
        self.assertIn(selected, by_id)
        self.assertEqual(by_id[selected]["inclusion_reason"], "selected")
        self.assertTrue(any(item["inclusion_reason"].startswith("neighbor:")
                            for item in projection["nodes"]))

    def test_server_exposes_registry_without_mutating_world(self) -> None:
        with patch.object(server, "IMAGINATION_PACKS", self.registry):
            before = server.STORE.state()
            packs = server.imagination_packs()
            projection = server.imagination_doctrine(lens="lens:identity", q="calm", limit=10)
            after = server.STORE.state()
        self.assertEqual(packs[0]["id"], "imagination-pack:villain")
        self.assertLessEqual(len(projection["nodes"]), 10)
        self.assertEqual(before, after)

    def test_unknown_lens_returns_not_found(self) -> None:
        with patch.object(server, "IMAGINATION_PACKS", self.registry):
            with self.assertRaises(HTTPException) as raised:
                server.imagination_doctrine(lens="lens:nope")
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
