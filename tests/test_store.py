from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from iris.store import Store


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


if __name__ == "__main__":
    unittest.main()
