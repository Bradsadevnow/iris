"""Identity packs: swappable Self manifests plus their capability declarations.

An identity pack is a JSON file shaped like seeds/halcyon_identity.json, extended
with a `capabilities` list:

    {"id": "engineer", "name": "The Engineer", "version": 1,
     "claims": [{"id", "kind", "subject", "predicate", "value", "source"?}, ...],
     "capabilities": [{"id", "effect_class", "description", "schema"?, "scope"?,
                        "limits"?, "source"?, "boundary_version"?}, ...]}

`claims` follow the exact shape Store.self_claims() reads. `kind` must be one of
the values Store.add_self_claim() already accepts (identity, value, preference,
commitment, relationship, goal, self_understanding) so packs render identically
to hand-added claims everywhere the system projects Self.

Installing a pack is the identity equivalent of profile_seed.import_seed: one
atomic transaction, no partial state. mode="switch" (default) retires every
other currently-active claim first, so the loaded pack becomes the whole active
Self — packs are personas you put on, not traits you accumulate. mode="layer"
skips that retirement, for a caller that deliberately wants to blend claims from
more than one pack (or keep the existing Self and add a pack's claims onto it).

Capabilities are always additive/upserted by id regardless of mode: adding
The Engineer's tools does not remove Halcyon's own; loading a second pack does
not remove the first pack's tools either. Capabilities carry no side effects of
their own here — none are wired to an executor, so they declare effect_class
"observe" and exist as an inspectable catalog of what the persona knows how to
do, the same way Halcyon's three builtin capabilities do today.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

REQUIRED_CLAIM_KINDS = {
    "identity", "value", "preference", "commitment",
    "relationship", "goal", "self_understanding",
}


def load_pack(path: str | Path) -> dict:
    pack = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("id", "name", "version", "claims"):
        if key not in pack:
            raise ValueError(f"identity pack {path} is missing required key {key!r}")
    for claim in pack["claims"]:
        if claim.get("kind") not in REQUIRED_CLAIM_KINDS:
            raise ValueError(f"identity pack {pack['id']} has a claim with invalid kind {claim.get('kind')!r}")
    return pack


def list_packs(directory: str | Path) -> list[dict]:
    """Summaries (id/name/tagline/version) of every *.json pack under directory, for a picker UI."""
    out = []
    for path in sorted(Path(directory).glob("*.json")):
        try:
            pack = load_pack(path)
        except (ValueError, json.JSONDecodeError):
            continue
        out.append({"id": pack["id"], "name": pack["name"], "version": pack["version"],
                    "tagline": pack.get("tagline", ""), "path": str(path)})
    return out


def install_identity_pack(store, path: str | Path, mode: str = "switch") -> dict:
    """Install a pack's Self claims and capabilities into store. Returns a small
    summary receipt, mirroring profile_seed.import_seed's return shape."""
    if mode not in ("switch", "layer"):
        raise ValueError("mode must be 'switch' or 'layer'")
    pack = load_pack(path)
    now = time.time()
    version = int(pack["version"])
    with store.transaction(immediate=True) as db:
        if mode == "switch":
            db.execute("UPDATE self_claims SET status='superseded' WHERE status='active'")
        for claim in pack["claims"]:
            db.execute(
                "INSERT OR REPLACE INTO self_claims VALUES (?,?,?,?,?,'active',?,?,?)",
                (claim["id"], claim["kind"], claim["subject"], claim["predicate"], claim["value"],
                 claim.get("source", f"identity-pack:{pack['id']}"), now, version),
            )
        for cap in pack.get("capabilities", []):
            db.execute(
                "INSERT OR REPLACE INTO capabilities VALUES (?,?,?,?,?,?,?,1,?,?)",
                (cap["id"], cap.get("source", f"identity-pack:{pack['id']}"), cap["effect_class"],
                 cap["description"], json.dumps(cap.get("schema", {})),
                 json.dumps(cap.get("scope", {})), json.dumps(cap.get("limits", {})),
                 cap.get("boundary_version", "capability-v1"), now),
            )
        db.execute("UPDATE domain_versions SET version=version+1,updated_at=? WHERE domain='self'", (now,))
        if pack.get("capabilities"):
            db.execute("UPDATE domain_versions SET version=version+1,updated_at=? WHERE domain='capabilities'", (now,))
    return {"installed": pack["id"], "name": pack["name"], "mode": mode,
            "claims": len(pack["claims"]), "capabilities": len(pack.get("capabilities", []))}
