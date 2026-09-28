from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from iris import server
from iris.imagination_registry import ImaginationPackRegistry
from iris.imagination_composer import compose_blueprint
from iris.server import (BlueprintAdmitRequest, BlueprintComposeRequest, BlueprintCreateRequest,
                         BlueprintUpdateRequest, PressureExploreRequest)
from iris.store import Store


ROOT = Path(__file__).resolve().parents[1]


class ImaginationBlueprintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        state = Path(self.temp.name)
        self.store = Store(state / "iris.db", state)
        self.registry = ImaginationPackRegistry(ROOT / "seeds" / "imagination_packs", ROOT)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create_blueprint(self) -> dict:
        body = BlueprintCreateRequest(
            title="The Black Ledger", artifact_type="artifact", lens_id="lens:artifact",
            ingredients=[{
                "primitive": "primitive:macguffins:ancient-apocalypse-engine",
                "origin": "user_selected", "locked": True,
            }],
            open_questions=["Who currently holds custody?"],
            draft_entities=[{"id": "draft:ledger", "type": "artifact", "label": "The Black Ledger"}],
        )
        with patch.object(server, "STORE", self.store), patch.object(server, "IMAGINATION_PACKS", self.registry):
            return server.create_imagination_blueprint(body)

    def test_blueprint_is_durable_versioned_and_noncanonical(self) -> None:
        before = self.store.state()
        created = self.create_blueprint()
        self.assertTrue(created["id"].startswith("blueprint:"))
        self.assertEqual((created["status"], created["revision"]), ("draft", 1))
        self.assertTrue(created["ingredients"][0]["locked"])
        self.assertEqual(self.store.state(), before)

        restarted = Store(self.store.path, self.store.state_dir)
        loaded = restarted.blueprint(created["id"])
        self.assertEqual(loaded["title"], "The Black Ledger")
        self.assertEqual(len(loaded["revisions"]), 1)

    def test_update_records_genealogy_and_checks_revision(self) -> None:
        created = self.create_blueprint()
        suggestion = {
            "primitive": "primitive:macguffins:forbidden-operating-manual",
            "origin": "halcyon_suggested", "accepted_by_user": True, "locked": False,
        }
        body = BlueprintUpdateRequest(
            expected_revision=1, actor="halcyon", reason="suggested a memory cost",
            patch={"title": "The Black Ledger, Revised",
                   "ingredients": [*created["ingredients"], suggestion], "status": "candidate"},
        )
        with patch.object(server, "STORE", self.store), patch.object(server, "IMAGINATION_PACKS", self.registry):
            updated = server.update_imagination_blueprint(created["id"], body)
            self.assertEqual((updated["revision"], updated["status"]), (2, "candidate"))
            self.assertEqual(updated["revisions"][0]["actor"], "halcyon")
            self.assertEqual(updated["revisions"][0]["snapshot"]["title"], "The Black Ledger, Revised")
            self.assertEqual(updated["revisions"][1]["snapshot"]["title"], "The Black Ledger")
            with self.assertRaises(HTTPException) as raised:
                server.update_imagination_blueprint(created["id"], body)
        self.assertEqual(raised.exception.status_code, 409)

    def test_unknown_primitive_and_admission_are_rejected(self) -> None:
        with patch.object(server, "STORE", self.store), patch.object(server, "IMAGINATION_PACKS", self.registry):
            with self.assertRaises(HTTPException) as unknown:
                server.create_imagination_blueprint(BlueprintCreateRequest(
                    title="Bad", artifact_type="artifact",
                    ingredients=[{"primitive": "primitive:nope", "origin": "user_selected"}],
                ))
        self.assertEqual(unknown.exception.status_code, 422)

        created = self.create_blueprint()
        with patch.object(server, "STORE", self.store), patch.object(server, "IMAGINATION_PACKS", self.registry):
            with self.assertRaises(HTTPException) as admission:
                server.update_imagination_blueprint(created["id"], BlueprintUpdateRequest(
                    expected_revision=1, patch={"status": "admitted"}, reason="too early",
                ))
        self.assertEqual(admission.exception.status_code, 422)
        self.assertEqual(self.store.state()[0], 0)

    def test_composition_creates_a_deterministic_noncanonical_candidate(self) -> None:
        with patch.object(server, "STORE", self.store), patch.object(server, "IMAGINATION_PACKS", self.registry):
            created = server.create_imagination_blueprint(BlueprintCreateRequest(
                title="The Black Ledger", artifact_type="artifact", lens_id="lens:artifact",
                ingredients=[
                    {"primitive": "primitive:families:corporate-predator",
                     "origin": "user_selected", "locked": True},
                    {"primitive": "primitive:signifiers:neutral-luxury",
                     "origin": "halcyon_suggested", "accepted_by_user": True},
                    {"primitive": "primitive:macguffins:forbidden-operating-manual",
                     "origin": "derived"},
                ],
                tensions=[{
                    "between": ["primitive:signifiers:neutral-luxury",
                                "primitive:macguffins:forbidden-operating-manual"],
                    "resolution": "retain", "reason": "the danger should look administratively calm",
                }],
            ))
            direct_a = compose_blueprint(self.registry, created)
            direct_b = compose_blueprint(self.registry, created)
            self.assertEqual(direct_a, direct_b)
            composed = server.compose_imagination_blueprint(
                created["id"], BlueprintComposeRequest(expected_revision=1))

        candidate = composed["candidate"]
        self.assertEqual((composed["status"], composed["revision"]), ("candidate", 2))
        self.assertTrue(candidate["id"].startswith("candidate:"))
        self.assertTrue(candidate["entities"][0]["id"].startswith("draft:"))
        self.assertIn("the soft black ledger", candidate["lore"]["draft:the-black-ledger"].lower())
        self.assertIn("primitive:families:corporate-predator", candidate["genealogy"]["user_selected"])
        self.assertIn("primitive:signifiers:neutral-luxury", candidate["genealogy"]["halcyon_suggested"])
        self.assertGreater(len(candidate["genealogy"]["doctrine_relationships"]), 0)
        self.assertTrue(any(item["kind"] == "custodian"
                            for item in candidate["genealogy"]["world_dependencies"]))
        self.assertEqual(self.store.state()[0], 0)

    def test_admission_atomically_commits_graph_lore_genealogy_and_blueprint(self) -> None:
        with patch.object(server, "STORE", self.store), patch.object(server, "IMAGINATION_PACKS", self.registry):
            created = server.create_imagination_blueprint(BlueprintCreateRequest(
                title="The Black Ledger", artifact_type="artifact", lens_id="lens:artifact",
                ingredients=[
                    {"primitive": "primitive:macguffins:forbidden-operating-manual",
                     "origin": "user_selected", "locked": True},
                ],
            ))
            composed = server.compose_imagination_blueprint(
                created["id"], BlueprintComposeRequest(expected_revision=1))
            candidate = composed["candidate"]
            admission = server.admit_imagination_blueprint(
                created["id"], BlueprintAdmitRequest(
                    expected_revision=2, candidate_hash=candidate["content_hash"]))

        sequence, state = self.store.state()
        self.assertEqual(sequence, 1)
        self.assertIn("entity:the-black-ledger", state["imagination_world"]["nodes"])
        self.assertEqual(admission["state_sequence_after"], 1)
        self.assertEqual(admission["entity_mapping"]["draft:the-black-ledger"], "entity:the-black-ledger")
        self.assertEqual(admission["receipt"]["genealogy"], candidate["genealogy"])
        pressures = self.store.world_pressures("open")
        self.assertGreaterEqual(len(pressures), 3)
        self.assertEqual({item["subject_entity_id"] for item in pressures}, {"entity:the-black-ledger"})
        self.assertIn("custodian", {item["kind"] for item in pressures})
        lore = self.store.imagination_lore("entity:the-black-ledger")
        self.assertEqual(lore["created_source_kind"], "admission")
        self.assertEqual(lore["created_source_id"], admission["id"])
        self.assertIn("The Soft Black Ledger", lore["markdown"])
        blueprint = self.store.blueprint(created["id"])
        self.assertEqual((blueprint["status"], blueprint["revision"]), ("admitted", 3))
        with patch.object(server, "STORE", self.store):
            detail = server.imagination_node("entity:the-black-ledger")
        self.assertEqual(detail["admission"]["id"], admission["id"])
        self.assertIsNone(detail["origin"])

        custody = next(item for item in pressures if item["kind"] == "custodian")
        with patch.object(server, "STORE", self.store), patch.object(server, "IMAGINATION_PACKS", self.registry):
            exploration = server.explore_imagination_pressure(
                custody["id"], PressureExploreRequest(
                    title="Who Keeps the Ledger?", artifact_type="character", lens_id="lens:character"))
        self.assertEqual(exploration["initiating_pressure_id"], custody["id"])
        self.assertIn("requires a current or contested custodian", exploration["open_questions"])
        pressure = self.store.world_pressure(custody["id"])
        self.assertEqual(pressure["status"], "exploring")
        self.assertEqual(pressure["exploration_blueprint_id"], exploration["id"])

    def test_failed_admission_rolls_back_everything(self) -> None:
        def candidate(title: str) -> dict:
            with patch.object(server, "STORE", self.store), patch.object(server, "IMAGINATION_PACKS", self.registry):
                created = server.create_imagination_blueprint(BlueprintCreateRequest(
                    title=title, artifact_type="artifact",
                    ingredients=[{"primitive": "primitive:macguffins:sovereign-access-key",
                                  "origin": "user_selected"}],
                ))
                return server.compose_imagination_blueprint(
                    created["id"], BlueprintComposeRequest(expected_revision=1))

        first = candidate("The Sovereign Key")
        with patch.object(server, "STORE", self.store):
            server.admit_imagination_blueprint(first["id"], BlueprintAdmitRequest(
                expected_revision=2, candidate_hash=first["candidate"]["content_hash"]))
        second = candidate("The Sovereign Key")
        before = self.store.state()
        with patch.object(server, "STORE", self.store):
            with self.assertRaises(HTTPException) as raised:
                server.admit_imagination_blueprint(second["id"], BlueprintAdmitRequest(
                    expected_revision=2, candidate_hash=second["candidate"]["content_hash"]))
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(self.store.state(), before)
        self.assertEqual(self.store.blueprint(second["id"])["status"], "candidate")

    def test_trait_bundle_cannot_be_admitted_as_a_world_entity(self) -> None:
        with patch.object(server, "STORE", self.store), patch.object(server, "IMAGINATION_PACKS", self.registry):
            created = server.create_imagination_blueprint(BlueprintCreateRequest(
                title="Calm Procedural Control", artifact_type="trait_bundle",
                lens_id="lens:origins",
                ingredients=[{"primitive": "primitive:exposures:compliance-theater",
                              "origin": "user_selected"}],
            ))
            composed = server.compose_imagination_blueprint(
                created["id"], BlueprintComposeRequest(expected_revision=1))
            with self.assertRaises(HTTPException) as raised:
                server.admit_imagination_blueprint(created["id"], BlueprintAdmitRequest(
                    expected_revision=2, candidate_hash=composed["candidate"]["content_hash"]))
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(self.store.state()[0], 0)


if __name__ == "__main__":
    unittest.main()
