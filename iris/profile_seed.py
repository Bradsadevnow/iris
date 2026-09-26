"""Versioned, idempotent profile-seed import."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import yaml

from .graph import edge_id, normalize_world


def load_seed(path: str | Path) -> dict:
    path = Path(path)
    seed = yaml.safe_load(path.read_text(encoding="utf-8"))
    seed["_hash"] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return seed


def merge_seed(world: dict, seed: dict) -> tuple[dict, dict]:
    world = normalize_world(world)
    world["sources"].update(seed.get("sources", {}))
    added_nodes = added_edges = updated_nodes = 0
    for raw in seed.get("nodes", []):
        node = {"visibility": "standard", "properties": {}, "sources": [], **raw}
        existing = world["nodes"].get(node["id"])
        if existing is None:
            world["nodes"][node["id"]] = node
            added_nodes += 1
        elif existing != node:
            world["nodes"][node["id"]] = {**existing, **node,
                "properties": {**existing.get("properties", {}), **node.get("properties", {})},
                "sources": sorted(set(existing.get("sources", [])) | set(node.get("sources", [])))}
            updated_nodes += 1
    existing_edges = {item["id"] for item in world["edges"]}
    for raw in seed.get("edges", []):
        item = {"assertion": "user_stated", "confidence": None, "visibility": "standard",
                "sources": [], "status": "active", "properties": {}, **raw}
        item.setdefault("id", edge_id(item["source"], item["relation"], item["target"]))
        if item["id"] not in existing_edges:
            world["edges"].append(item); existing_edges.add(item["id"]); added_edges += 1
    return world, {"seed_id": seed["id"], "seed_version": seed["version"], "seed_hash": seed["_hash"],
                   "added_nodes": added_nodes, "updated_nodes": updated_nodes, "added_edges": added_edges}


def import_seed(store, path: str | Path) -> dict:
    seed = load_seed(path)
    now = time.time()
    with store.transaction(immediate=True) as db:
        prior = db.execute("SELECT * FROM seed_imports WHERE seed_id=? AND seed_hash=?", (seed["id"], seed["_hash"])).fetchone()
        if prior:
            return {"noop": True, "seed_id": seed["id"], "seed_hash": seed["_hash"]}
        sequence, state = store.state(db)
        world, result = merge_seed(state["world"], seed)
        changed = result["added_nodes"] + result["updated_nodes"] + result["added_edges"] > 0
        next_sequence = sequence + 1 if changed else sequence
        if changed:
            db.execute("UPDATE canonical_state SET sequence=?, world_json=?, updated_at=? WHERE singleton=1",
                       (next_sequence, json.dumps(world), now))
        db.execute("INSERT INTO seed_imports VALUES (?,?,?,?,?,?)",
                   (seed["id"], seed["version"], seed["_hash"], str(path), next_sequence, now))
    if changed:
        store.write_projections(next_sequence, {"world": world, "self": state["self"]})
    return {**result, "noop": not changed, "state_sequence": next_sequence}
