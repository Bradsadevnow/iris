import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from iris import server
from iris.graph import empty_world
from iris.projection import ProjectionService
from iris.server import ToolExecuteRequest
from iris.store import Store


class PromptProjectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.store = Store(root / "iris.db", root)
        self.service = ProjectionService(
            self.store, Path(__file__).resolve().parents[1] / "seeds" / "identity_packs"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_projection_is_self_centered_and_owner_preserving(self):
        memory = self.store.add_memory_entry(
            scope="global", channel="cognitive_semantic",
            content="Atomic persistence protects canonical memory boundaries.",
        )
        projection = self.service.build("How do memory boundaries work?")
        nodes = {item["id"]: item for item in projection["selected_nodes"]}
        self.assertIn("self:halcyon", nodes)
        self.assertEqual(nodes["self:halcyon"]["owner"], "self")
        self.assertEqual(nodes[memory["id"]]["owner"], "memory")
        self.assertTrue(any(edge["source"] == "self:halcyon" and edge["target"] == memory["id"]
                            for edge in projection["selected_edges"]))

    def test_role_changes_attention_without_changing_self(self):
        before = self.store.self_claims()
        self.store.set_active_context("world:halcyon", "task:review", [], ["security"])
        projection = self.service.build("Review authorization boundaries")
        role = next(item for item in projection["selected_nodes"] if item["id"] == "role:security")
        self.assertIn("role affinity", role["reason"])
        self.assertIn("contradicted_by", projection["strategy"]["preferred_edges"])
        self.assertEqual(self.store.self_claims(), before)

    def test_role_is_inferred_as_a_task_stance_not_an_identity(self):
        projection = self.service.build("Review this system architecture and its dependencies")
        self.assertEqual(projection["strategy"]["selected_roles"], ["engineer"])
        self.assertEqual(projection["strategy"]["role_sources"], {"engineer": "inferred"})
        role = next(item for item in projection["selected_nodes"] if item["id"] == "role:engineer")
        self.assertEqual(role["owner"], "role")
        self.assertNotIn("expresses itself with", role["content"])
        self.assertNotIn("is named", role["content"])

    def test_render_separates_self_roles_knowledge_and_unbound_capabilities(self):
        projection = self.service.build("Review this system architecture")
        rendered = projection["rendered_context"]
        self.assertIn("## CANONICAL SELF", rendered)
        self.assertIn("## ACTIVE REASONING ROLE", rendered)
        self.assertNotIn("## REGISTERED CAPABILITIES", rendered)
        self.assertNotIn("Halcyon expresses herself with", rendered)

    def test_known_and_imagined_worlds_remain_distinct(self):
        with self.store.transaction(immediate=True) as db:
            known = empty_world()
            imagined = empty_world()
            known["nodes"]["entity:harbor"] = {"id": "entity:harbor", "label": "Real Harbor", "type": "place", "visibility": "standard", "properties": {}, "sources": []}
            imagined["nodes"]["entity:harbor"] = {"id": "entity:harbor", "label": "Glass Harbor", "type": "place", "visibility": "standard", "properties": {}, "sources": []}
            db.execute("UPDATE canonical_state SET world_json=?,imagination_world_json=? WHERE singleton=1",
                       (__import__("json").dumps(known), __import__("json").dumps(imagined)))
        projection = self.service.build("harbor")
        nodes = {item["id"]: item for item in projection["selected_nodes"]}
        self.assertEqual(nodes["known_world:entity:harbor"]["status"], "canonical")
        self.assertEqual(nodes["imagination:entity:harbor"]["status"], "fictional")
        isolated = self.service.build("harbor", include_known_world=False)
        self.assertFalse(any(item["owner"] == "known_world" for item in isolated["selected_nodes"]))

    def test_budget_preserves_mandatory_self_and_context(self):
        for index in range(20):
            self.store.add_memory_entry(scope="global", channel="experience", content=(f"memory {index} " + "detail " * 80))
        projection = self.service.build("unrelated", token_budget=500, max_nodes=12)
        ids = {item["id"] for item in projection["selected_nodes"]}
        self.assertIn("self:halcyon", ids)
        self.assertTrue(any(item["owner"] == "self" for item in projection["selected_nodes"]))
        self.assertTrue(projection["excluded"])

    def test_turn_persists_projection_receipt(self):
        with patch.object(server, "STORE", self.store):
            context = server.model_context(None, "Explain the system architecture")
        turn = self.store.begin_turn(None, "Explain the system architecture", context)
        receipt = self.store.prompt_projection(context["prompt_projection"]["id"])
        self.assertEqual(receipt["turn_id"], turn["id"])
        self.assertEqual(receipt["subject_id"], "self:halcyon")
        captured = self.store.turn_context(turn["id"])
        self.assertEqual(captured["prompt_projection"]["id"], receipt["id"])
        self.assertEqual(captured["context_manifest"]["memory"]["supplied"], [])

    def test_stop_words_do_not_admit_unrelated_knowledge(self):
        with self.store.transaction(immediate=True) as db:
            known = empty_world()
            known["nodes"]["principle:governance"] = {
                "id": "principle:governance", "label": "Governance effects", "type": "principle",
                "visibility": "standard", "properties": {"formulation": "effects are bounded"}, "sources": [],
            }
            db.execute("UPDATE canonical_state SET world_json=? WHERE singleton=1",
                       (__import__("json").dumps(known),))
        projection = self.service.build("How are you feeling today? Answer briefly.")
        self.assertFalse(any(item["owner"] == "known_world" for item in projection["selected_nodes"]))

    def test_generic_node_type_does_not_admit_an_unrelated_entity(self):
        with self.store.transaction(immediate=True) as db:
            known = empty_world()
            known["nodes"]["resource:mathbricc"] = {
                "id": "resource:mathbricc", "label": "Mathbricc", "type": "resource",
                "visibility": "standard", "properties": {}, "sources": [],
            }
            db.execute("UPDATE canonical_state SET world_json=? WHERE singleton=1",
                       (__import__("json").dumps(known),))
        projection = self.service.build("Assess the financial return and resource allocation")
        self.assertNotIn("known_world:resource:mathbricc",
                         {item["id"] for item in projection["selected_nodes"]})

    def test_capabilities_do_not_compete_with_knowledge_and_fiction_requires_match(self):
        with self.store.transaction(immediate=True) as db:
            imagined = empty_world()
            imagined["nodes"]["entity:river"] = {
                "id": "entity:river", "label": "Whispering River", "type": "place",
                "visibility": "standard", "properties": {}, "sources": [],
            }
            db.execute("UPDATE canonical_state SET imagination_world_json=? WHERE singleton=1",
                       (__import__("json").dumps(imagined),))
        ordinary = self.service.build("Inspect the financial return and system cost")
        self.assertFalse(any(item["owner"] in {"capabilities", "imagination"}
                             for item in ordinary["selected_nodes"]))
        fictional = self.service.build("Tell me about the Whispering River")
        self.assertIn("imagination:entity:river", {item["id"] for item in fictional["selected_nodes"]})

    def test_graph_search_is_read_only_and_receipted(self):
        memory = self.store.add_memory_entry(scope="global", channel="cognitive_semantic", content="Authorization uses default deny boundaries.")
        with patch.object(server, "STORE", self.store):
            result = server.execute_tool(ToolExecuteRequest(
                tool_id="graph.search", arguments={"query": "authorization boundaries", "domains": ["memory"], "limit": 5}
            ))
            neighbors = server.execute_tool(ToolExecuteRequest(
                tool_id="graph.neighbors", arguments={"node_id": memory["id"], "depth": 1, "limit": 5}
            ))
        self.assertTrue(result["observation"])
        self.assertEqual(neighbors["observation"][0]["node"]["id"], "self:halcyon")
        self.assertFalse(result["remembered"])
        self.assertEqual(self.store.tool_receipts()[0]["decision"], "ACCEPT")


if __name__ == "__main__":
    unittest.main()
