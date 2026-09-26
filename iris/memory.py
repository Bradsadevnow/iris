"""The persistent substrate — three graphs, walled.

  world     : what she imagines / knows about the world (nodes / edges /
              constraints). Grown by the imagination verbs.
  self      : who she is. Writable ONLY through the gated `remember` verb —
              never as a side effect of a conversation or of imagining.
  episodic  : an append-only log of what was said and done. Never mutated,
              never retracted — the identity's memory of its own life.

Persistence is plain JSON / JSONL under a state directory, so the whole
identity is a save-file: snapshot it, diff it, roll it back. The container's
job is only to give this directory a stable home; nothing about *who she is*
lives anywhere but here.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .graph import normalize_world


class Memory:
    def __init__(self, state_dir: str | Path):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.world_f = self.dir / "world.json"
        self.self_f = self.dir / "self.json"
        self.episodic_f = self.dir / "episodic.jsonl"
        self.receipts_f = self.dir / "receipts.jsonl"

        # state is ONE dict object; the gate holds this same reference and
        # mutates it in place on ACCEPT (clear + update from the trial copy).
        self.state: dict = {
            "world": self._load(self.world_f, {"nodes": {}, "edges": [], "constraints": []}),
            "self":  self._load(self.self_f,  {"name": "halcyon", "memory": {}}),
        }

    @staticmethod
    def _load(f: Path, default):
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default

    def commit(self) -> None:
        """Persist the canonical graphs. Called only after the gate admits a write."""
        self.world_f.write_text(json.dumps(self.state["world"], indent=1), encoding="utf-8")
        self.self_f.write_text(json.dumps(self.state["self"], indent=1), encoding="utf-8")

    def episode(self, kind: str, content: str) -> None:
        with self.episodic_f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), "kind": kind, "content": content}) + "\n")

    def receipt(self, r: dict) -> None:
        with self.receipts_f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(r) + "\n")

    def recent_episodes(self, n: int = 20) -> list[dict]:
        if not self.episodic_f.exists():
            return []
        lines = self.episodic_f.read_text(encoding="utf-8").splitlines()[-n:]
        return [json.loads(l) for l in lines if l.strip()]

    def render_world(self, limit: int = 120) -> str:
        w = normalize_world(self.state["world"])
        out = ["# NODES"]
        for node in sorted(w["nodes"].values(), key=lambda item: item["label"])[:limit]:
            if node.get("visibility", "standard") == "standard":
                out.append(f"- {node['label']} ({node['type']})")
        out.append("\n# EDGES")
        for e in w["edges"][:limit]:
            if e.get("visibility", "standard") == "standard":
                out.append(f"- {w['nodes'][e['source']]['label']} | {e['relation']} | {w['nodes'][e['target']]['label']}")
        out.append("\n# CONSTRAINTS")
        for c in w["constraints"][:limit]:
            if c.get("visibility", "standard") == "standard":
                out.append(f"- {w['nodes'][c['target']]['label']} | {c['rule']} | {c['value']}")
        return "\n".join(out)

    def render_self(self) -> str:
        m = self.state["self"].get("memory", {})
        if not m:
            return "(nothing remembered yet)"
        return "\n".join(f"- {k}: {v}" for k, v in sorted(m.items()))
