"""The verbs — the only code that touches canonical state, one function per verb.

Five imagination verbs (create / relate / constrain / occur / name) that grow the
world graph, living behind the gate instead of after a permissive prose extractor.
Plus `remember`, the sole writer of the SELF graph.

Each returns a small result dict describing what changed (or a noop). A repeat
is a noop, not an error — the gate still receipts it.
"""
from __future__ import annotations


# ── imagination: writes world/* ────────────────────────────────────────────

def _create(state, what, a):
    w = state["world"]
    if a["name"] in w["nodes"]:
        return {"noop": f"node {a['name']!r} already exists"}
    w["nodes"][a["name"]] = a["type"]
    return {"created": a["name"], "type": a["type"]}


def _relate(state, what, a):
    w = state["world"]
    e = [a["subject"], a["relation"], a["object"]]
    if e in w["edges"]:
        return {"noop": "edge already exists"}
    w["edges"].append(e)
    return {"related": e}


def _constrain(state, what, a):
    w = state["world"]
    c = [a["target"], a["rule"], a["value"]]
    if c in w["constraints"]:
        return {"noop": "constraint already exists"}
    w["constraints"].append(c)
    return {"constrained": c}


def _occur(state, what, a):
    # Events are nodes, never mutations. Nothing is retracted.
    w = state["world"]
    w["nodes"].setdefault(a["event"], "event")
    e = [a["event"], "involves", a["participant"]]
    if e in w["edges"]:
        return {"noop": "event link already exists"}
    w["edges"].append(e)
    return {"occurred": e}


def _name(state, what, a):
    w = state["world"]
    e = [a["target"], "known as", a["alias"]]
    if e in w["edges"]:
        return {"noop": "alias already exists"}
    w["edges"].append(e)
    return {"named": e}


# ── selfhood: writes self/* (the ONLY writer of the self graph) ────────────

def _remember(state, what, a):
    state["self"].setdefault("memory", {})[a["key"]] = a["value"]
    return {"remembered": a["key"], "value": a["value"]}


TOOLS = {
    "create": _create, "relate": _relate, "constrain": _constrain,
    "occur": _occur, "name": _name, "remember": _remember,
}


# ── invariants: pure checks over a candidate (trial) state ─────────────────
# Built from the declaration so the numbers live in the boundary file, not here.

def build_invariants(spec: dict) -> dict:
    limits = spec.get("limits", {})
    world_cap = limits.get("world_max_elements", 100_000)
    self_cap = limits.get("self_max_memories", 10_000)

    def world_within_budget(state):
        w = state["world"]
        n = len(w["nodes"]) + len(w["edges"]) + len(w["constraints"])
        if n > world_cap:
            return f"world would hold {n} elements, over the declared {world_cap}"
        return None

    def self_within_budget(state):
        n = len(state["self"].get("memory", {}))
        if n > self_cap:
            return f"self would hold {n} memories, over the declared {self_cap}"
        return None

    return {"world_within_budget": world_within_budget,
            "self_within_budget": self_within_budget}
