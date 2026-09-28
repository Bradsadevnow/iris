"""Compile rich pack sources into the shared fictional-possibility graph.

This module is deliberately read-only. It creates an in-memory projection of an
inert seed; it does not register capabilities or mutate a Workbench or World.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

from .imagination_pack import validate_manifest


EDGE_TYPES = {
    "compatible_with", "suggests", "requires", "intensifies",
    "soft_conflict_with", "expresses_as", "resolves_through",
    "creates_demand_for", "tagged_with",
}

DOMAIN_HINTS = {
    "families": ["character", "villain"], "modifiers": ["character", "villain", "moral"],
    "signifiers": ["expression", "atmosphere", "location"], "dialogue_grammars": ["voice", "character"],
    "payoffs": ["payoff", "story"], "skins": ["expression", "world"],
    "petty_atrocities": ["moral", "character"], "exposures": ["institution", "character"],
    "competencies": ["competency", "character", "labor"], "institutions": ["institution", "credential"],
    "macguffins": ["artifact", "custody", "stakes", "containment", "betrayal"],
    "lairs": ["location", "architecture", "defense", "vulnerability"],
    "roles": ["character", "sidekick", "relationship"], "loyalty_modes": ["relationship", "sidekick"],
    "task_domains": ["labor", "sidekick"], "competence_profiles": ["competency", "sidekick"],
    "fold_profiles": ["betrayal", "sidekick"], "plot_goals": ["goal", "scheme"],
    "plot_shapes": ["plot_shape", "scheme"], "betrayals": ["betrayal", "story"],
    "reversals": ["reversal", "story"], "tension_payoff_beats": ["tension", "payoff"],
    "strategic_agendas": ["scheme", "goal"], "structural_complications": ["scheme", "tension"],
    "contractor_classes": ["labor", "organization"], "slots": ["workbench", "recipe"],
}

def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _is_primitive(value: Any) -> bool:
    return not isinstance(value, dict) or not value or any(not isinstance(item, dict) for item in value.values())


def _walk(group: str, value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[str, tuple[str, ...], Any]]:
    if not isinstance(value, dict):
        yield group, path, value
        return
    for key, item in value.items():
        next_path = (*path, str(key))
        if _is_primitive(item):
            yield group, next_path, item
        else:
            yield from _walk(group, item, next_path)


def _domains(group: str, path: tuple[str, ...], payload: dict) -> list[str]:
    hints = DOMAIN_HINTS.get(path[-2] if len(path) > 1 else group, DOMAIN_HINTS.get(group, []))
    extra = payload.get("domains", []) if isinstance(payload, dict) else []
    return list(dict.fromkeys([*hints, *extra, "fiction"]))


def _payload(value: Any) -> dict:
    return value if isinstance(value, dict) else {"value": value}


def _policy_literals(path: Path) -> Iterable[tuple[str, Any]]:
    """Read authored declarative tables from policy code without importing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    allowed = {
        "CATEGORY_COMMONS_TARGETED", "SANCTION_PROFILE_BY_SEVERITY",
        "MORAL_TEXTURE_MODIFIER_PRESSURE", "MORAL_TEXTURE_FAMILY_PRESSURE", "weights",
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for target in targets:
            if isinstance(target, ast.Name) and target.id in allowed:
                try:
                    yield target.id, ast.literal_eval(value)
                except (ValueError, TypeError):
                    pass


def compile_doctrine(path: str | Path, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Compile every allowlisted doctrine item without flattening its payload."""
    validation = validate_manifest(path, repo_root)
    manifest_path = Path(path).resolve()
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    classification_groups = validation["classification"]["groups"]
    classification_overrides = validation["classification"].get("overrides", {})
    classification_collapses = validation["classification"].get("collapses", [])
    deferred_groups = {
        group: bucket
        for bucket, spec in validation["classification"].get("deferred", {}).items()
        for group in spec.get("groups", [])
    }
    root = Path(repo_root).resolve() if repo_root else manifest_path.parents[3]
    source_root = (root / manifest["source"]["root"]).resolve()
    primitives: dict[str, dict] = {}
    lookup: dict[tuple[str, str], str] = {}
    pending_tags: list[tuple[str, str]] = []

    for entry in manifest["doctrine"]:
        document = yaml.safe_load((source_root / entry["file"]).read_text(encoding="utf-8"))
        roots = entry.get("root_keys") or [entry["root_key"]]
        for group in roots:
            for _, item_path, raw in _walk(group, document[group]):
                if not item_path:
                    continue
                key = item_path[-1]
                kind = item_path[-2] if len(item_path) > 1 else group
                payload = _payload(raw)
                primitive_id = f"primitive:{_slug(group)}:{':'.join(_slug(item) for item in item_path)}"
                label = payload.get("label") or payload.get("name") or payload.get("institution_name") or key.replace("_", " ").title()
                classification = classification_groups.get(kind)
                override = classification_overrides.get(kind, {}).get(key)
                if classification is not None and override is not None:
                    classification = {**classification, **override}
                if classification is None:
                    deferred = deferred_groups.get(kind)
                    classification = {
                        "subject": deferred or "unclassified", "role": "deferred_record",
                        "constellations": [], "clusters": [], "granularity": "compound",
                        "selectable": False, "treatment": "preserve_losslessly" if deferred else "review",
                    }
                lanes = classification.get("constellations", [])
                primitives[primitive_id] = {
                    "id": primitive_id, "kind": kind, "lane": lanes[0] if lanes else None,
                    "lanes": lanes,
                    "domains": _domains(group, item_path, payload),
                    "label": label, "content": payload,
                    "classification": {
                        "subject": classification.get("subject", "unclassified"),
                        "role": classification.get("role", "unclassified"),
                        "clusters": classification.get("clusters", []),
                        "granularity": classification.get("granularity", "unknown"),
                        "selectable": bool(classification.get("selectable", False)),
                        "treatment": classification.get("treatment", "defer"),
                    },
                    "source": {"pack": manifest["id"], "version": manifest["version"],
                               "file": entry["file"], "root": group, "path": list(item_path),
                               "sha256": entry["sha256"]},
                }
                # A classification overlay may intentionally promote a rich
                # compound field into its own selectable atomic cards. This is
                # opt-in so authored records remain lossless by default.
                for field, rule in classification.get("fields", {}).items():
                    if not rule.get("selectable"):
                        continue
                    values = payload.get(field, [])
                    if not isinstance(values, list):
                        values = [values] if values not in (None, "") else []
                    for field_value in values:
                        if not isinstance(field_value, (str, int, float, bool)):
                            continue
                        derived_lane = rule.get("constellation") or (lanes[0] if lanes else None)
                        derived_id = f"{primitive_id}:{_slug(field)}:{_slug(str(field_value))}"
                        primitives[derived_id] = {
                            "id": derived_id, "kind": field, "lane": derived_lane,
                            "lanes": [derived_lane] if derived_lane else [],
                            "domains": list(dict.fromkeys([*_domains(group, item_path, payload), rule.get("cluster", field)])),
                            "label": str(field_value).strip().capitalize(),
                            "content": {"value": field_value, "from": label},
                            "classification": {
                                "subject": classification.get("subject", "character"),
                                "role": "trait", "clusters": [rule.get("cluster", field)],
                                "granularity": "atomic", "selectable": True,
                                "treatment": rule.get("treatment", "split"),
                            },
                            "source": {"pack": manifest["id"], "version": manifest["version"],
                                       "file": entry["file"], "root": group,
                                       "path": [*item_path, field, str(field_value)],
                                       "parent": primitive_id, "sha256": entry["sha256"]},
                        }
                lookup[(group, key)] = primitive_id
                for tag in payload.get("tags", []) if isinstance(payload.get("tags", []), list) else []:
                    pending_tags.append((primitive_id, str(tag)))

    # Collapse overly granular authored cards into a selectable canonical card
    # while preserving every source primitive as a non-selectable variant.
    for collapse in classification_collapses:
        member_ids = set(collapse.get("members", []))
        parent_ids = set(collapse.get("member_parents", []))
        member_ids.update(
            item["id"] for item in primitives.values()
            if item.get("source", {}).get("parent") in parent_ids
        )
        missing = member_ids - primitives.keys()
        if missing:
            raise ValueError(f"unknown collapse members for {collapse['id']}: {sorted(missing)}")
        members = [primitives[item] for item in sorted(member_ids)]
        for member in members:
            member["classification"] = {
                **member["classification"], "selectable": False,
                "collapsed_into": f"primitive:collapse:{collapse['id']}",
            }
        bundle_id = f"primitive:collapse:{collapse['id']}"
        lane = collapse["constellation"]
        primitives[bundle_id] = {
            "id": bundle_id, "kind": "trait_profile", "lane": lane, "lanes": [lane],
            "domains": list(dict.fromkeys([*(collapse.get("domains", [])), lane, "character", "fiction"])),
            "label": collapse["label"],
            "content": {
                "summary": collapse.get("summary", ""),
                "variants": [member["label"] for member in members],
                "variant_details": [member["content"] for member in members],
            },
            "classification": {
                "subject": "character", "role": collapse.get("role", "trait_bundle"),
                "clusters": [collapse["cluster"]], "granularity": "compound",
                "selectable": True, "treatment": "collapse_variants",
            },
            "source": {"pack": manifest["id"], "version": manifest["version"],
                       "classification": "collapse", "members": sorted(member_ids)},
        }

    for resource in validation["resources"]:
        if resource["category"] != "policies" or not resource["path"].endswith(".py"):
            continue
        for table, value in _policy_literals(Path(resource["path"])):
            entries = value.items() if isinstance(value, dict) else [("value", value)]
            for key, raw in entries:
                primitive_id = f"policy:{_slug(resource['id'])}:{_slug(table)}:{_slug(str(key))}"
                primitives[primitive_id] = {
                    "id": primitive_id, "kind": "selection_policy",
                    "lane": None, "lanes": [],
                    "classification": {"subject": "generator", "role": "generator_instruction",
                                       "clusters": [], "granularity": "compound",
                                       "selectable": False, "treatment": "preserve"},
                    "domains": ["recipe", "workbench", "fiction"],
                    "label": str(key).replace("_", " ").title(), "content": _payload(raw),
                    "source": {"pack": manifest["id"], "version": manifest["version"],
                               "file": str(Path(resource["path"]).relative_to(source_root)),
                               "table": table, "sha256": resource["sha256"]},
                }

    edges: dict[str, dict] = {}

    def add_edge(source: str, relation: str, target: str, evidence: str) -> None:
        if relation not in EDGE_TYPES:
            raise ValueError(f"unsupported doctrine relation: {relation}")
        edge_id = f"edge:{_slug(source)}:{relation}:{_slug(target)}"
        edges[edge_id] = {"id": edge_id, "source": source, "relation": relation,
                          "target": target, "evidence": evidence}

    for primitive in list(primitives.values()):
        content, source = primitive["content"], primitive["source"]
        references = (
            ("signifier_tags", "signifiers", "compatible_with"),
            ("dialogue_tags", "dialogue_grammars", "compatible_with"),
            ("payoff_tags", "payoffs", "resolves_through"),
            ("compatible_families", "families", "compatible_with"),
            ("family_tags", "families", "suggests"),
        )
        for field, target_group, relation in references:
            values = content.get(field, [])
            for value in values if isinstance(values, list) else []:
                target = lookup.get((target_group, str(value)))
                if target:
                    add_edge(primitive["id"], relation, target,
                             f"{source['file']}:{'.'.join(source['path'])}.{field}")

    for source_id, tag in pending_tags:
        tag_id = f"primitive:tag:{_slug(tag)}"
        if tag_id not in primitives:
            primitives[tag_id] = {"id": tag_id, "kind": "tag", "lane": None, "lanes": [],
                                  "classification": {"subject": "reference", "role": "connector",
                                                     "clusters": [], "granularity": "atomic",
                                                     "selectable": False, "treatment": "connect"},
                                  "domains": ["fiction"],
                                  "label": tag.replace("_", " ").title(), "content": {"tag": tag},
                                  "source": {"pack": manifest["id"], "version": manifest["version"],
                                             "derived": "shared-tag-index"}}
        add_edge(source_id, "tagged_with", tag_id, "authored tag")

    graph = {
        "schema": "iris.imagination-doctrine/v1", "pack": validation,
        "primitives": sorted(primitives.values(), key=lambda item: item["id"]),
        "edges": sorted(edges.values(), key=lambda item: item["id"]),
        "lenses": manifest.get("lenses", []),
    }
    validate_doctrine_graph(graph)
    return graph


def validate_doctrine_graph(graph: dict[str, Any]) -> None:
    primitive_ids = [item["id"] for item in graph.get("primitives", [])]
    if len(primitive_ids) != len(set(primitive_ids)):
        raise ValueError("duplicate doctrine primitive id")
    known = set(primitive_ids)
    for edge in graph.get("edges", []):
        if edge.get("relation") not in EDGE_TYPES:
            raise ValueError(f"unsupported doctrine relation: {edge.get('relation')}")
        if edge.get("source") not in known or edge.get("target") not in known:
            raise ValueError(f"dangling doctrine edge: {edge.get('id')}")


def validate_blueprint(blueprint: dict[str, Any]) -> None:
    if not str(blueprint.get("id", "")).startswith("blueprint:"):
        raise ValueError("blueprint id must begin with blueprint:")
    if blueprint.get("status") not in {"draft", "candidate", "admitted", "rejected"}:
        raise ValueError("invalid blueprint status")
    allowed_origins = {"user_selected", "halcyon_suggested", "derived", "world_pressure"}
    seen: set[str] = set()
    for ingredient in blueprint.get("ingredients", []):
        if ingredient.get("origin") not in allowed_origins:
            raise ValueError("invalid ingredient origin")
        primitive = str(ingredient.get("primitive", ""))
        if not (primitive.startswith("primitive:") or primitive.startswith("policy:")):
            raise ValueError("ingredient must reference a doctrine primitive")
        if primitive in seen:
            raise ValueError("duplicate blueprint ingredient")
        seen.add(primitive)
        if "locked" in ingredient and not isinstance(ingredient["locked"], bool):
            raise ValueError("ingredient lock must be boolean")
    for tension in blueprint.get("tensions", []):
        if len(tension.get("between", [])) != 2:
            raise ValueError("tension must reference exactly two primitives")
        if tension.get("resolution", "retain") not in {"retain", "resolve", "reject"}:
            raise ValueError("invalid tension resolution")
    draft_ids = {item.get("id") for item in blueprint.get("draft_entities", [])}
    if any(not str(item).startswith("draft:") for item in draft_ids) or len(draft_ids) != len(blueprint.get("draft_entities", [])):
        raise ValueError("draft entity ids must be unique and begin with draft:")
    for edge in blueprint.get("draft_edges", []):
        if edge.get("source") not in draft_ids or edge.get("target") not in draft_ids:
            raise ValueError("draft edge must connect draft entities")


def validate_world_pressure(pressure: dict[str, Any]) -> None:
    if not str(pressure.get("id", "")).startswith("pressure:"):
        raise ValueError("pressure id must begin with pressure:")
    if pressure.get("status") not in {"open", "exploring", "resolved", "retained"}:
        raise ValueError("invalid world pressure status")
    if not pressure.get("subject") or not pressure.get("kind"):
        raise ValueError("world pressure requires subject and kind")
