import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from iris import server
from iris.server import ActiveContextRequest
from iris.store import Store


class RoleOverlayTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.store = Store(root / "iris.db", root)

    def tearDown(self):
        self.temp.cleanup()

    def test_unknown_role_is_rejected_before_it_reaches_the_store(self):
        with patch.object(server, "STORE", self.store):
            with self.assertRaises(HTTPException) as exc:
                server.update_active_context(ActiveContextRequest(roles=["not-a-real-role"]))
        self.assertEqual(exc.exception.status_code, 422)
        self.assertEqual(self.store.active_context()["roles"], [])

    def test_valid_role_round_trips_through_active_context(self):
        with patch.object(server, "STORE", self.store):
            result = server.update_active_context(ActiveContextRequest(roles=["engineer", "academic"]))
        self.assertEqual(result["roles"], ["academic", "engineer"])
        self.assertEqual(self.store.active_context()["roles"], ["academic", "engineer"])

    def test_active_role_overlays_the_prompt_without_touching_self_claims(self):
        self.store.set_active_context("world:halcyon", None, [], ["engineer"])
        with patch.object(server, "STORE", self.store):
            context = server.model_context(None, "hello")
            projection = server.system_projection()
        self.assertIn("## ACTIVE REASONING ROLE", context["knowledge"])
        self.assertIn("The Engineer", context["knowledge"])
        self.assertIn("Known methods:", context["knowledge"])
        # Halcyon's own canonical identity is never diluted by an equipped role.
        self.assertEqual({c["subject"] for c in projection["self"]["claims"]}, {"Halcyon"})
        self.assertEqual({c["subject"] for c in self.store.self_claims()}, {"Halcyon"})

    def test_no_active_roles_means_no_overlay_section(self):
        with patch.object(server, "STORE", self.store):
            context = server.model_context(None, "hello")
        self.assertNotIn("## ACTIVE REASONING ROLE", context["knowledge"])

    def test_role_overlay_survives_a_store_restart(self):
        self.store.set_active_context("world:halcyon", None, [], ["strategist"])
        restarted = Store(Path(self.temp.name) / "iris.db", Path(self.temp.name))
        self.assertEqual(restarted.active_context()["roles"], ["strategist"])
        self.assertEqual({c["subject"] for c in restarted.self_claims()}, {"Halcyon"})


if __name__ == "__main__":
    unittest.main()
