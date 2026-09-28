"""Read-only discovery and bounded projection of Imagination doctrine packs."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .imagination_doctrine import compile_doctrine
from .imagination_pack import validate_manifest


class PackNotFound(KeyError):
    pass


class LensNotFound(KeyError):
    pass


def _terms(value: str) -> set[str]:
    return {item for item in re.findall(r"[a-z0-9]+", value.lower()) if len(item) > 1}


class ImaginationPackRegistry:
    def __init__(self, root: str | Path, repo_root: str | Path | None = None):
        self.root = Path(root)
        self.repo_root = Path(repo_root).resolve() if repo_root else self.root.resolve().parents[1]
        self._cache: dict[str, tuple[tuple[tuple[str, int, int], ...], dict]] = {}

    def _manifests(self) -> list[Path]:
        return sorted(self.root.glob("*/manifest.yaml")) if self.root.exists() else []

    def _resolve(self, pack: str) -> Path:
        for path in self._manifests():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if pack in {data.get("id"), path.parent.name}:
                return path
        raise PackNotFound(pack)

    def list_packs(self) -> list[dict[str, Any]]:
        items = []
        for path in self._manifests():
            report = validate_manifest(path, self.repo_root)
            items.append({"id": report["id"], "slug": path.parent.name, "name": report["name"],
                          "version": report["version"], "status": report["status"],
                          "source_count": report["source_count"], "resource_count": report["resource_count"],
                          "lens_count": report["lens_count"], "lenses": report["lenses"]})
        return items

    def graph(self, pack: str) -> dict[str, Any]:
        path = self._resolve(pack)
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        source_root = self.repo_root / manifest["source"]["root"]
        dependencies = [path]
        if manifest.get("classification", {}).get("file"):
            dependencies.append(path.parent / manifest["classification"]["file"])
        dependencies.extend(source_root / item["file"] for item in manifest.get("doctrine", []))
        dependencies.extend(source_root / item["file"]
                            for entries in manifest.get("resources", {}).values() for item in entries)
        stamp = tuple((str(item), item.stat().st_mtime_ns, item.stat().st_size)
                      for item in sorted(set(dependencies)))
        cached = self._cache.get(str(path))
        if cached and cached[0] == stamp:
            return cached[1]
        graph = compile_doctrine(path, self.repo_root)
        self._cache[str(path)] = (stamp, graph)
        return graph

    def pack(self, pack: str) -> dict[str, Any]:
        graph = self.graph(pack)
        return {**{key: graph["pack"][key] for key in (
            "id", "version", "name", "status", "source_count", "resource_count", "lens_count", "lenses"
        )}, "primitive_count": len(graph["primitives"]), "edge_count": len(graph["edges"])}

    def node(self, pack: str, node_id: str) -> dict[str, Any]:
        graph = self.graph(pack)
        node = next((item for item in graph["primitives"] if item["id"] == node_id), None)
        if not node:
            raise KeyError(node_id)
        edges = [item for item in graph["edges"] if node_id in {item["source"], item["target"]}]
        known = {item["id"]: item for item in graph["primitives"]}
        return {**node, "relationships": [{**edge,
                 "source_label": known[edge["source"]]["label"],
                 "target_label": known[edge["target"]]["label"]} for edge in edges]}

    def project(self, pack: str, lens: str | None = None, query: str = "",
                selected: list[str] | None = None, limit: int = 120,
                token_budget: int = 4000) -> dict[str, Any]:
        graph = self.graph(pack)
        nodes = {item["id"]: item for item in graph["primitives"]}
        selected = list(dict.fromkeys(selected or []))
        unknown = [item for item in selected if item not in nodes]
        if unknown:
            raise KeyError(unknown[0])
        lens_spec = None
        if lens:
            lens_spec = next((item for item in graph["lenses"]
                              if lens == item["id"] or lens in item.get("legacy_ids", [])), None)
            if not lens_spec:
                raise LensNotFound(lens)
        lens_domains = set(lens_spec.get("domains", [])) if lens_spec else set()
        lens_lanes = set(lens_spec.get("lanes", [])) if lens_spec else set()
        query_terms = _terms(query)
        scored: list[tuple[int, str, str]] = []
        for node_id, node in nodes.items():
            reasons = []
            score = 0
            if node_id in selected:
                reasons.append("selected"); score += 1000
            elif lens_spec and not node.get("classification", {}).get("selectable", False):
                continue
            if lens_lanes and lens_lanes.intersection(node.get("lanes", [])):
                reasons.append("lens"); score += 20
            elif lens_lanes and node_id not in selected:
                continue
            elif lens_domains and lens_domains.intersection(node["domains"]):
                reasons.append("lens"); score += 20
            elif lens_domains and node_id not in selected:
                continue
            if query_terms:
                label_terms = _terms(node["label"])
                body_terms = _terms(json.dumps(node["content"], ensure_ascii=False, sort_keys=True))
                matches = len(query_terms & label_terms) * 5 + len(query_terms & body_terms)
                if not matches and node_id not in selected:
                    continue
                if matches:
                    reasons.append("query"); score += matches
            scored.append((score, node_id, "+".join(reasons) or "pack"))

        # A selected primitive brings its immediate authored neighborhood even
        # when those neighbors sit outside the active lens.
        neighbor_reasons: dict[str, str] = {}
        for edge in graph["edges"]:
            if edge["source"] in selected and edge["target"] in nodes:
                neighbor_reasons.setdefault(edge["target"], f"neighbor:{edge['relation']}")
            if edge["target"] in selected and edge["source"] in nodes:
                neighbor_reasons.setdefault(edge["source"], f"neighbor:{edge['relation']}")
        existing = {item[1] for item in scored}
        scored.extend((500, node_id, reason) for node_id, reason in neighbor_reasons.items() if node_id not in existing)
        scored.sort(key=lambda item: (-item[0], nodes[item[1]]["label"].lower(), item[1]))
        match_count = len(scored)

        included = []
        estimated = 0
        for _, node_id, reason in scored:
            node = nodes[node_id]
            cost = max(1, len(json.dumps(node, ensure_ascii=False)) // 4)
            if included and (len(included) >= max(1, min(limit, 500)) or estimated + cost > token_budget):
                continue
            included.append({**node, "inclusion_reason": reason, "estimated_tokens": cost})
            estimated += cost
        included_ids = {item["id"] for item in included}
        edges = [item for item in graph["edges"]
                 if item["source"] in included_ids and item["target"] in included_ids]
        rendered = self._render_context(included, edges, lens_spec)
        return {"pack": graph["pack"]["id"], "pack_version": graph["pack"]["version"],
                "lens": lens_spec, "query": query, "selected": selected,
                "nodes": included, "edges": edges, "estimated_tokens": estimated,
                "match_count": match_count,
                "excluded_count": len(nodes) - len(included), "rendered_context": rendered}

    @staticmethod
    def _render_context(nodes: list[dict], edges: list[dict], lens: dict | None) -> str:
        lines = ["# IMAGINATION DOCTRINE PROJECTION"]
        if lens:
            lines.append(f"Lens: {lens['label']} ({lens['id']})")
        lines.append("These are reusable possibilities, not canonical world facts.")
        for node in nodes:
            lines.append(f"\n## {node['label']} [{node['id']}]")
            lines.append(f"kind={node['kind']} domains={','.join(node['domains'])} selected_by={node['inclusion_reason']}")
            lines.append(json.dumps(node["content"], ensure_ascii=False, sort_keys=True))
        if edges:
            lines.append("\n## Visible relationships")
            lines.extend(f"- {edge['source']} --{edge['relation']}--> {edge['target']}" for edge in edges)
        return "\n".join(lines)
