import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from iris import server
from iris.server import ToolExecuteRequest
from iris.store import Store


class SystemIdentityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.store = Store(root / "iris.db", root)

    def tearDown(self):
        self.temp.cleanup()

    def test_self_is_versioned_and_projection_is_not_a_state_owner(self):
        before = self.store.versions()["self"]
        prior_count = len(self.store.self_claims())
        claim = self.store.add_self_claim("value", "Halcyon", "values", "legibility")
        self.assertEqual(claim["self_version"], before + 1)
        with patch.object(server, "STORE", self.store):
            projection = server.system_projection()
        self.assertTrue(projection["projection"])
        self.assertEqual(projection["self"]["claim_count"], prior_count + 1)
        self.assertNotIn("system", projection["versions"])

    def test_halcyon_identity_manifest_is_canonical_and_idempotent(self):
        claims = self.store.self_claims()
        name = next(item for item in claims if item["id"] == "self:identity:name")
        self.assertEqual((name["subject"], name["value"]), ("Halcyon", "Halcyon"))
        self.assertTrue(any(item["value"] == "she/her" for item in claims))
        count = len(claims)
        self.store._init()
        self.assertEqual(len(self.store.self_claims()), count)

    def test_builtin_observation_is_receipted_and_not_remembered(self):
        with patch.object(server, "STORE", self.store):
            result = server.execute_tool(ToolExecuteRequest(tool_id="affect.inspect", arguments={}))
        self.assertFalse(result["remembered"])
        receipt = self.store.tool_receipts()[0]
        self.assertEqual(receipt["decision"], "ACCEPT")
        self.assertEqual(receipt["execution_status"], "succeeded")
        self.assertEqual(self.store.memory_entries(), [])

    def test_unknown_and_disconnected_mcp_tools_are_denied_with_receipts(self):
        with patch.object(server, "STORE", self.store):
            with self.assertRaises(HTTPException):
                server.execute_tool(ToolExecuteRequest(tool_id="unknown.tool", arguments={}))
            self.store.register_mcp_capability("search", "demo", "Remote search", {}, "observe")
            with self.assertRaises(HTTPException):
                server.execute_tool(ToolExecuteRequest(tool_id="mcp.demo.search", arguments={}))
        receipts = self.store.tool_receipts()
        self.assertEqual([item["decision"] for item in receipts], ["DENY", "DENY"])

    def test_imagination_runs_are_durable_and_separate_from_chat_list(self):
        run = self.store.create_imagination_run("Grow one connected place", 3)
        self.assertEqual(run["status"], "running")
        self.assertEqual(run["completed_steps"], 0)
        self.assertEqual(self.store.conversations(), [])
        paused = self.store.set_imagination_status(run["id"], "paused")
        self.assertEqual(paused["status"], "paused")
        resumed = self.store.set_imagination_status(run["id"], "running")
        self.assertEqual(resumed["status"], "running")

    def test_imagination_session_tracks_chat_and_restartable_batches(self):
        run = self.store.create_imagination_run("Grow one connected place", 1, running=False)
        self.assertEqual(run["status"], "paused")
        context = server.model_context(run["conversation_id"], "What belongs here?")
        turn = self.store.begin_turn(run["conversation_id"], "What belongs here?", context)
        self.store.link_imagination_turn(run["id"], turn["id"], "chat")
        detail = self.store.imagination_run(run["id"])
        self.assertEqual(detail["turn_kinds"][turn["id"]], {"kind": "chat", "step": None})
        self.store.fail_turn(turn["id"], "test_complete")
        started = self.store.start_imagination_batch(run["id"], 7)
        self.assertEqual(started["status"], "running")
        self.assertEqual(started["max_steps"], 7)

    def test_world_dialogue_has_an_explicit_separated_mode_contract(self):
        run = self.store.create_imagination_run("Grow one connected place", 1, running=False)
        with patch.object(server, "STORE", self.store):
            context = server.world_dialogue_context(run["conversation_id"], "What should we build?")
        instructions = context["instructions"]
        self.assertIn("--- WORLD DIALOGUE MODE ---", instructions)
        self.assertIn("<world_dialogue>", instructions)
        self.assertIn("--- END WORLD DIALOGUE MODE ---", instructions)
        self.assertEqual(context["conversation"][-1]["content"], "What should we build?")

    def test_machine_lines_stay_out_of_visible_chat_even_when_marked_up(self):
        raw = "A place belongs here.\n**NOMINATE what=world/node/Harbor verb=create args=type:city; name:Harbor**\nAFFECT joy:50"
        self.assertEqual(server.display_content(raw), "A place belongs here.")
        noisy = "<|channel|>final <|constrain|>plain-language reflection explaining the single addition. A harbor belongs here."
        self.assertEqual(server.display_content(noisy), "A harbor belongs here.")

    def test_imagination_prompt_separates_task_affect_and_output_contract(self):
        with patch.object(server, "STORE", self.store):
            run = self.store.create_imagination_run("Grow one connected place", 1)
            context = server.imagination_context(run["conversation_id"], run["seed"], 1, "invalid affect transition for disgust")
        instructions = context["instructions"]
        self.assertIn("<imagination_task>\nMODE: AUTONOMOUS IMAGINATION", context["conversation"][-1]["content"])
        self.assertIn("--- IMAGINATION OUTPUT CONTRACT ---", instructions)
        self.assertIn("<affect_boundary>", instructions)
        self.assertIn("disgust: current=50.00 allowed=[40.00, 60.00]", instructions)
        self.assertLess(instructions.index("<affect_boundary>"), instructions.index("<required_output>"))


if __name__ == "__main__":
    unittest.main()
