"""Validation for inert, versioned Imagination doctrine seeds."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


SCHEMA = "iris.imagination-pack/v1"
CLASSIFICATION_SCHEMA = "iris.imagination-classification/v1"


def _contained(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"doctrine path escapes source root: {candidate}")
    return resolved


def validate_manifest(path: str | Path, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Validate one pack without registering it or touching canonical state."""
    manifest_path = Path(path).resolve()
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ValueError(f"expected schema {SCHEMA}")
    if not isinstance(manifest.get("version"), int) or manifest["version"] < 1:
        raise ValueError("pack version must be a positive integer")
    if not str(manifest.get("id", "")).startswith("imagination-pack:"):
        raise ValueError("pack id must begin with imagination-pack:")
    if manifest.get("status") != "seed-only":
        raise ValueError("curated seeds must remain seed-only")

    root = Path(repo_root).resolve() if repo_root else manifest_path.parents[3]
    source_root = _contained(root, root / manifest["source"]["root"])
    classification_spec = manifest.get("classification")
    if not isinstance(classification_spec, dict):
        raise ValueError("pack must declare a classification overlay")
    classification_path = _contained(manifest_path.parent, manifest_path.parent / classification_spec.get("file", ""))
    if not classification_path.is_file():
        raise ValueError(f"missing classification overlay: {classification_path}")
    classification_digest = hashlib.sha256(classification_path.read_bytes()).hexdigest()
    if classification_digest != classification_spec.get("sha256"):
        raise ValueError("hash mismatch for classification overlay")
    classification = yaml.safe_load(classification_path.read_text(encoding="utf-8"))
    if not isinstance(classification, dict) or classification.get("schema") != CLASSIFICATION_SCHEMA:
        raise ValueError(f"expected classification schema {CLASSIFICATION_SCHEMA}")
    constellation_ids = {item.get("id") for item in classification.get("constellations", [])}
    if not constellation_ids or None in constellation_ids:
        raise ValueError("classification must declare constellations")
    for group, rule in classification.get("groups", {}).items():
        unknown = set(rule.get("constellations", [])) - constellation_ids
        if unknown:
            raise ValueError(f"unknown constellation for {group}: {sorted(unknown)}")
    for group, entries in classification.get("overrides", {}).items():
        if group not in classification.get("groups", {}):
            raise ValueError(f"classification override references unknown group: {group}")
        for item, rule in entries.items():
            unknown = set(rule.get("constellations", [])) - constellation_ids
            if unknown:
                raise ValueError(f"unknown constellation for {group}.{item}: {sorted(unknown)}")
    collapse_ids: set[str] = set()
    for collapse in classification.get("collapses", []):
        collapse_id = collapse.get("id")
        if not collapse_id or collapse_id in collapse_ids:
            raise ValueError(f"duplicate or missing classification collapse id: {collapse_id}")
        collapse_ids.add(collapse_id)
        if collapse.get("constellation") not in constellation_ids:
            raise ValueError(f"unknown constellation for collapse {collapse_id}")
    holdings = classification.get("deferred", {}).get("holdings", {})
    if not holdings.get("preserve_losslessly") or not {"macguffins", "lairs"}.issubset(holdings.get("groups", [])):
        raise ValueError("classification must preserve deferred Holdings")
    seen: set[str] = set()
    sources = []
    for entry in manifest.get("doctrine", []):
        source_id = entry.get("id")
        if not source_id or source_id in seen:
            raise ValueError(f"duplicate or missing doctrine id: {source_id}")
        seen.add(source_id)
        source_path = _contained(source_root, source_root / entry["file"])
        if not source_path.is_file():
            raise ValueError(f"missing doctrine source: {source_path}")
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if digest != entry.get("sha256"):
            raise ValueError(f"hash mismatch for doctrine source {source_id}")
        document = yaml.safe_load(source_path.read_text(encoding="utf-8"))
        required_keys = entry.get("root_keys") or [entry.get("root_key")]
        if not isinstance(document, dict) or any(not key or key not in document for key in required_keys):
            raise ValueError(f"missing declared root key in doctrine source {source_id}")
        item_count = sum(len(document[key]) for key in required_keys if isinstance(document[key], dict))
        sources.append({"id": source_id, "path": str(source_path), "sha256": digest,
                        "root_keys": required_keys, "item_count": item_count})

    if not sources:
        raise ValueError("pack must declare at least one doctrine source")
    resources = []
    for category, entries in manifest.get("resources", {}).items():
        for entry in entries:
            resource_path = _contained(source_root, source_root / entry["file"])
            if not resource_path.is_file():
                raise ValueError(f"missing {category} resource: {resource_path}")
            digest = hashlib.sha256(resource_path.read_bytes()).hexdigest()
            if digest != entry.get("sha256"):
                raise ValueError(f"hash mismatch for {category} resource {entry.get('id')}")
            resources.append({"id": entry["id"], "category": category,
                              "path": str(resource_path), "sha256": digest})
    lenses = manifest.get("lenses", [])
    lens_ids = [item.get("id") for item in lenses]
    if len(lens_ids) != len(set(lens_ids)) or any(not str(item).startswith("lens:") for item in lens_ids):
        raise ValueError("lens ids must be unique and begin with lens:")
    return {"id": manifest["id"], "version": manifest["version"], "name": manifest["name"],
            "status": manifest["status"], "source_count": len(sources),
            "item_count": sum(item["item_count"] for item in sources), "sources": sources,
            "resource_count": len(resources), "resources": resources, "lens_count": len(lenses),
            "lenses": lenses, "future_contract": manifest.get("future_contract", {}),
            "classification": {"path": str(classification_path), "sha256": classification_digest,
                               "schema": classification["schema"],
                               "constellations": classification["constellations"],
                               "groups": classification["groups"],
                               "overrides": classification.get("overrides", {}),
                               "collapses": classification.get("collapses", []),
                               "deferred": classification.get("deferred", {})}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an inert Imagination pack seed.")
    parser.add_argument("manifest")
    args = parser.parse_args()
    print(json.dumps(validate_manifest(args.manifest), indent=2))


if __name__ == "__main__":
    main()
