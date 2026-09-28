"""Deterministic composition of noncanonical Workbench artifact candidates."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .imagination_registry import ImaginationPackRegistry


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "artifact"


def _description(node: dict) -> str:
    content = node["content"]
    for key in ("dramatic_function", "detail", "summary", "real_function", "structural_mechanic",
                "texture", "resolution", "speech_pattern", "room_logic", "framing", "value"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "A selected creative primitive."


def _dependencies(nodes: list[dict]) -> list[dict]:
    dependencies: dict[str, dict] = {}
    for node in nodes:
        content = node["content"]
        signals = (
            ("containment_needs", "containment_location", "requires somewhere capable of containing it",
             ["assign_existing_location", "create_location", "assign_institution", "retain_unresolved"]),
            ("custody_state", "custodian", "requires a current or contested custodian",
             ["assign_existing_character", "create_character", "assign_institution", "retain_unresolved"]),
            ("desired_by", "claimant", "creates demand for someone who desires it",
             ["assign_existing_entity", "create_character", "create_faction", "retain_unresolved"]),
            ("betrayal_magnet", "betrayal_pressure", "creates pressure on an existing relationship",
             ["connect_existing_relationship", "create_sidekick", "create_faction", "retain_unresolved"]),
            ("target", "target", "requires a target",
             ["assign_existing_entity", "create_entity", "retain_unresolved"]),
            ("hospitality_cover", "public_mask", "requires a public-facing explanation",
             ["assign_existing_institution", "create_organization", "define_cover_story", "retain_unresolved"]),
        )
        for field, kind, reason, resolutions in signals:
            value = content.get(field)
            if value not in (None, "", [], {}):
                dependencies.setdefault(kind, {"kind": kind, "reason": reason,
                                               "source_primitive": node["id"], "source_field": field,
                                               "hint": value, "possible_resolutions": resolutions})
    return sorted(dependencies.values(), key=lambda item: item["kind"])


def _lore(title: str, artifact_type: str, nodes: list[dict], blueprint: dict,
          doctrine_edges: list[dict]) -> str:
    lines = [f"# {title}", "", f"*Noncanonical {artifact_type} candidate.*", "", "## Creative foundation", ""]
    for node in nodes:
        lines.append(f"- **{node['label']}** — {_description(node)}")
    tensions = blueprint.get("tensions", [])
    if tensions:
        labels = {node["id"]: node["label"] for node in nodes}
        lines.extend(["", "## Productive tensions", ""])
        for tension in tensions:
            left, right = tension["between"]
            reason = tension.get("reason") or "retained for creative pressure"
            lines.append(f"- **{labels.get(left, left)}** ↔ **{labels.get(right, right)}** — {reason}")
    if doctrine_edges:
        labels = {node["id"]: node["label"] for node in nodes}
        lines.extend(["", "## Internal logic", ""])
        for edge in doctrine_edges:
            lines.append(f"- {labels.get(edge['source'], edge['source'])} *{edge['relation'].replace('_', ' ')}* {labels.get(edge['target'], edge['target'])}")
    if blueprint.get("open_questions"):
        lines.extend(["", "## Open questions", ""])
        lines.extend(f"- {question}" for question in blueprint["open_questions"])
    return "\n".join(lines).rstrip() + "\n"


def compose_blueprint(registry: ImaginationPackRegistry, blueprint: dict) -> dict[str, Any]:
    """Compile a blueprint into a stable candidate without touching World state."""
    pack = blueprint["pack_id"].removeprefix("imagination-pack:")
    graph = registry.graph(pack)
    if graph["pack"]["version"] != blueprint["pack_version"]:
        raise ValueError("blueprint doctrine version is no longer available")
    by_id = {item["id"]: item for item in graph["primitives"]}
    ingredient_ids = [item["primitive"] for item in blueprint.get("ingredients", [])]
    if not ingredient_ids:
        raise ValueError("blueprint needs at least one ingredient before composition")
    nodes = [by_id[item] for item in ingredient_ids]
    selected = set(ingredient_ids)
    doctrine_edges = [edge for edge in graph["edges"]
                      if edge["source"] in selected and edge["target"] in selected]
    title = blueprint["title"]
    primary_id = f"draft:{_slug(title)}"
    explicit_entities = blueprint.get("draft_entities", [])
    primary = next((item for item in explicit_entities if item.get("id") == primary_id), None) or {
        "id": primary_id, "type": blueprint["artifact_type"], "label": title, "properties": {},
    }
    primary = {**primary, "properties": {**primary.get("properties", {}),
        "doctrine_ingredients": ingredient_ids, "pack_id": blueprint["pack_id"],
        "pack_version": blueprint["pack_version"], "blueprint_id": blueprint["id"]}}
    entities = [primary, *(item for item in explicit_entities if item.get("id") != primary_id)]
    genealogy = {
        "user_selected": [item["primitive"] for item in blueprint.get("ingredients", []) if item["origin"] == "user_selected"],
        "halcyon_suggested": [item["primitive"] for item in blueprint.get("ingredients", []) if item["origin"] == "halcyon_suggested"],
        "derived": [item["primitive"] for item in blueprint.get("ingredients", []) if item["origin"] == "derived"],
        "world_pressure": [item["primitive"] for item in blueprint.get("ingredients", []) if item["origin"] == "world_pressure"],
        "locked": [item["primitive"] for item in blueprint.get("ingredients", []) if item.get("locked")],
        "rejected_suggestions": blueprint.get("rejected_suggestions", []),
        "retained_tensions": [item for item in blueprint.get("tensions", []) if item.get("resolution", "retain") == "retain"],
        "doctrine_relationships": doctrine_edges,
        "world_dependencies": _dependencies(nodes),
    }
    for dependency in genealogy["world_dependencies"]:
        dependency["subject_draft_id"] = primary_id
    lore = {primary_id: _lore(title, blueprint["artifact_type"], nodes, blueprint, doctrine_edges)}
    body = {"schema": "iris.imagination-candidate/v1", "blueprint_id": blueprint["id"],
            "blueprint_revision": blueprint["revision"], "pack_id": blueprint["pack_id"],
            "pack_version": blueprint["pack_version"], "artifact_type": blueprint["artifact_type"],
            "entities": entities, "edges": blueprint.get("draft_edges", []), "lore": lore,
            "genealogy": genealogy}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    candidate = {**body, "id": f"candidate:{digest[:16]}", "content_hash": f"sha256:{digest}"}
    validate_candidate(candidate)
    return candidate


def validate_candidate(candidate: dict[str, Any]) -> None:
    if candidate.get("schema") != "iris.imagination-candidate/v1":
        raise ValueError("invalid candidate schema")
    entity_ids = [item.get("id") for item in candidate.get("entities", [])]
    if not entity_ids or len(entity_ids) != len(set(entity_ids)):
        raise ValueError("candidate entities must have unique ids")
    if any(not str(item).startswith("draft:") for item in entity_ids):
        raise ValueError("candidate entities must remain in the draft namespace")
    known = set(entity_ids)
    for edge in candidate.get("edges", []):
        if edge.get("source") not in known or edge.get("target") not in known:
            raise ValueError("candidate edge must connect candidate entities")
    if set(candidate.get("lore", {})) - known:
        raise ValueError("candidate lore must belong to a candidate entity")
