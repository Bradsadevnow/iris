from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from iris.store import Store
from iris.tools import TOOLS


def context() -> dict:
    return {
        "state_sequence": 0,
        "context_limit": 32768,
        "instructions": "system",
        "knowledge": "empty",
        "conversation": [{"role": "user", "content": "hello"}],
        "model_id": "test-model",
    }


def receipt() -> dict:
    return {
        "id": "receipt_1",
        "decision": "ACCEPT",
        "claim": {"what": "self/memory/greeting", "verb": "remember",
                  "args": {"key": "greeting", "value": "hello"}},
        "rationale": "I will remember.\nNOMINATE what=self/memory/greeting verb=remember args=key:greeting; value:hello",
        "decision_basis": [["schema", "PASS", "one nomination"],
                           ["execute", "OK", "effect applied"]],
        "result": {"remembered": "greeting", "value": "hello"},
    }


class StoreTransactionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.store = Store(root / "iris.db", root / "state")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_context_message_is_visible_and_supplied_without_generation(self) -> None:
        raw = 'IRIS_CHARACTER_SNAPSHOT_V1\n{"title":"Mara","traits":[{"id":"trait:patient"}]}'
        message = self.store.append_context_message(
            None, raw, "Character draft · Mara\nIdentity: Patient", "Character: Mara"
        )
        detail = self.store.conversation(message["conversation_id"])
        self.assertEqual(len(detail["messages"]), 1)
        self.assertEqual(detail["messages"][0]["turn_status"], "complete")
        self.assertIsNone(detail["active_turn"])
        self.assertEqual(
            self.store.context_messages(message["conversation_id"]),
            [{"role": "user", "content": raw}],
        )

    def test_commits_message_receipt_and_state_together(self) -> None:
        turn = self.store.begin_turn(None, "hello", context())
        state = self.store.state()[1]
        state["self"]["memory"]["greeting"] = "hello"
        result = self.store.finalize(
            turn["id"], receipt()["rationale"], "I will remember.", None, None,
            receipt(), state, 0, "sha256:test",
            {"raw_line": "NOMINATE ...", "what_path": "self/memory/greeting",
             "verb": "remember", "raw_args": "key:greeting; value:hello",
             "normalized_args": {"key": "greeting", "value": "hello"},
             "parse_status": "valid"},
            {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14,
             "reasoning_tokens": None, "source": "estimate"},
            expression_receipt={"profile": {"voice": "warm"},
                                "grounded_visible": "I will remember.",
                                "fidelity": {"passed": True}, "fallback": False},
        )
        sequence, committed = self.store.state()
        self.assertEqual(sequence, 1)
        self.assertEqual(committed["self"]["memory"]["greeting"], "hello")
        self.assertEqual(result["outcome"], "committed")
        loaded = self.store.turn(turn["id"])
        self.assertEqual(loaded["status"], "complete")
        self.assertIsNotNone(loaded["assistant_message"])
        self.assertIsNotNone(loaded["receipt"])
        captured = self.store.turn_context(turn["id"])
        self.assertTrue(captured["expression_receipt"]["fidelity"]["passed"])
        self.assertFalse(captured["expression_receipt"]["fallback"])
        provenance = self.store.node_provenance("missing")
        self.assertIsNone(provenance)

    def test_rolls_back_everything_when_receipt_insert_fails(self) -> None:
        turn = self.store.begin_turn(None, "hello", context())
        state = self.store.state()[1]
        state["self"]["memory"]["greeting"] = "hello"
        with self.store.connect() as db:
            db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON receipts BEGIN SELECT RAISE(ABORT, 'fault'); END")
        with self.assertRaises(Exception):
            self.store.finalize(
                turn["id"], receipt()["rationale"], "I will remember.", None, None,
                receipt(), state, 0, "sha256:test", None,
                {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14,
                 "reasoning_tokens": None, "source": "estimate"},
            )
        sequence, committed = self.store.state()
        self.assertEqual(sequence, 0)
        self.assertEqual(committed["self"]["memory"], {})
        loaded = self.store.turn(turn["id"])
        self.assertEqual(loaded["status"], "generating")
        self.assertIsNone(loaded["assistant_message"])
        self.assertIsNone(loaded["receipt"])

    def test_imagination_lore_is_created_and_revised_forward_only(self) -> None:
        first = self.store.begin_turn(None, "Create Eternia", context())
        state = self.store.state()[1]
        create_args = {"name": "Eternia", "type": "city"}
        create_result = TOOLS["create"](state, "world/entity", create_args)
        create_receipt = {
            "id": "receipt_create_eternia", "decision": "ACCEPT",
            "claim": {"what": "world/entity", "verb": "create", "args": create_args},
            "rationale": "Create the city.",
            "decision_basis": [["schema", "PASS", "valid mutation"]],
            "result": create_result,
        }
        self.store.finalize(
            first["id"], "Eternia rises beside the silver sea.",
            "Eternia rises beside the silver sea.", None, None,
            create_receipt, state, 0, "sha256:create", None,
            {"input_tokens": 8, "output_tokens": 7, "total_tokens": 15,
             "reasoning_tokens": None, "source": "estimate"},
        )

        lore = self.store.imagination_lore("entity:eternia")
        self.assertEqual(lore["version"], 1)
        self.assertEqual(lore["markdown"], "# Eternia\n\nEternia rises beside the silver sea.\n")
        self.assertEqual([item["operation"] for item in lore["revisions"]], ["create"])

        second_context = context()
        second_context["state_sequence"] = 1
        second = self.store.begin_turn(first["conversation_id"], "Add the river", second_context)
        state = self.store.state()[1]
        relate_args = {"subject": "Eternia", "relation": "has", "object": "Whispering River"}
        relate_result = TOOLS["relate"](state, "world/relation", relate_args)
        relate_receipt = {
            "id": "receipt_relate_river", "decision": "ACCEPT",
            "claim": {"what": "world/relation", "verb": "relate", "args": relate_args},
            "rationale": "Connect the river.",
            "decision_basis": [["schema", "PASS", "valid mutation"]],
            "result": relate_result,
        }
        self.store.finalize(
            second["id"], "The Whispering River carries old songs through Eternia.",
            "The Whispering River carries old songs through Eternia.", None, None,
            relate_receipt, state, 1, "sha256:relate", None,
            {"input_tokens": 8, "output_tokens": 9, "total_tokens": 17,
             "reasoning_tokens": None, "source": "estimate"},
        )

        lore = self.store.imagination_lore("entity:eternia")
        self.assertEqual(lore["version"], 2)
        self.assertIn("## Development 2", lore["markdown"])
        self.assertIn("The Whispering River carries old songs", lore["markdown"])
        self.assertEqual([item["operation"] for item in lore["revisions"]], ["append", "create"])
        river_lore = self.store.imagination_lore("entity:whispering-river")
        self.assertEqual(river_lore["version"], 1)

    def test_legacy_turn_lore_migrates_to_general_source_provenance(self) -> None:
        root = Path(self.temp.name) / "legacy"
        root.mkdir()
        path = root / "iris.db"
        db = sqlite3.connect(path)
        db.executescript("""
        CREATE TABLE imagination_lore (
          entity_id TEXT PRIMARY KEY, title TEXT NOT NULL, markdown TEXT NOT NULL,
          version INTEGER NOT NULL, created_turn_id TEXT NOT NULL,
          updated_turn_id TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE imagination_lore_revisions (
          id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, version INTEGER NOT NULL,
          operation TEXT NOT NULL, markdown TEXT NOT NULL, turn_id TEXT NOT NULL,
          created_at REAL NOT NULL, UNIQUE(entity_id, version), UNIQUE(entity_id, turn_id)
        );
        INSERT INTO imagination_lore VALUES
          ('entity:old','Old','# Old',1,'turn_old','turn_old',1.0,1.0);
        INSERT INTO imagination_lore_revisions VALUES
          ('rev_old','entity:old',1,'create','# Old','turn_old',1.0);
        """)
        db.close()
        migrated = Store(path, root / "state")
        lore = migrated.imagination_lore("entity:old")
        self.assertEqual(lore["created_source_kind"], "turn")
        self.assertEqual(lore["created_source_id"], "turn_old")
        self.assertEqual(lore["revisions"][0]["source_kind"], "turn")


if __name__ == "__main__":
    unittest.main()
