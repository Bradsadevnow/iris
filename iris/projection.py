"""Turn-scoped, Self-centered knowledge projection.

This module is deliberately read-only.  It federates records owned by Self,
Memory, Context, Capabilities, and the two world graphs, then chooses a bounded
subset for one model turn.  Selection never changes canonical state.
"""
from __future__ import annotations

import math
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .graph import visible_world
from .identity_packs import load_pack


WORD = re.compile(r"[a-z0-9][a-z0-9_-]+", re.IGNORECASE)
SELF_ID = "self:halcyon"
STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been", "before",
    "being", "between", "briefly", "but", "can", "could", "did", "does", "doing",
    "each", "for", "from", "had", "has", "have", "her", "here", "hers", "him",
    "his", "how", "into", "its", "just", "likely", "may", "more", "most", "other",
    "our", "out", "please", "should", "some", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "today", "too",
    "use", "using", "very", "was", "were", "what", "when", "where", "which", "who",
    "why", "will", "with", "would", "you", "your",
}

ROLE_STRATEGIES: dict[str, dict[str, list[str]]] = {
    "security": {"terms": ["security", "risk", "threat", "attack", "permission", "auth", "boundary", "failure", "blast", "deny"],
                 "edges": ["contradicted_by", "depends_on", "implemented_by", "motivated_by"]},
    "engineer": {"terms": ["engineer", "system", "architecture", "implementation", "dependency", "reliability", "test", "failure"],
                 "edges": ["depends_on", "implemented_by", "related_to", "motivated_by"]},
    "academic": {"terms": ["evidence", "source", "research", "theory", "confidence", "contradiction"],
                 "edges": ["supported_by", "contradicted_by", "derived_from", "related_to"]},
    "strategist": {"terms": ["strategy", "goal", "tradeoff", "stakeholder", "outcome", "decision"],
                   "edges": ["depends_on", "motivated_by", "related_to"]},
    "financer": {"terms": ["cost", "finance", "budget", "risk", "return", "capital", "resource"],
                 "edges": ["depends_on", "supported_by", "related_to"]},
    "sales": {"terms": ["customer", "sale", "buyer", "deal", "value", "objection", "outcome"],
              "edges": ["related_to", "motivated_by", "supported_by"]},
    "game-developer": {"terms": ["game", "player", "mechanic", "loop", "world", "experience", "balance"],
                       "edges": ["involves", "depends_on", "related_to"]},
}

PROFILE_TENSIONS: dict[frozenset[str], dict[str, str]] = {
    frozenset({"security", "sales"}): {
        "between": "Security favors restrictive boundaries while Sales favors low-friction progress.",
        "requirement": "Preserve authorization boundaries while minimizing friction for legitimate users.",
    },
    frozenset({"academic", "sales"}): {
        "between": "Academic qualification can compete with Sales brevity and momentum.",
        "requirement": "Keep the recommendation concise without overstating evidence or confidence.",
    },
    frozenset({"financer", "game-developer"}): {
        "between": "Financial efficiency can compete with experimentation needed to validate player value.",
        "requirement": "Bound experimentation by cost while preserving a meaningful playtest signal.",
    },
}


def _tokens(value: str) -> set[str]:
    return {token for m in WORD.finditer(value or "")
            if len(token := m.group(0).lower()) > 2 and token not in STOP_WORDS}


def estimate_tokens(value: str) -> int:
    return max(1, math.ceil(len(value) / 4))


@dataclass(frozen=True)
class ProjectionNode:
    id: str
    owner: str
    kind: str
    label: str
    content: str
    status: str = "canonical"
    confidence: float | None = None
    visibility: str = "standard"
    scope: str = "global"
    source_ids: list[str] = field(default_factory=list)
    created_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectionEdge:
    source: str
    relation: str
    target: str
    owner: str


class ProjectionService:
    """Build a deterministic prompt projection from an Iris Store snapshot."""

    def __init__(self, store, identity_packs_dir: str | Path):
        self.store = store
        self.identity_packs_dir = Path(identity_packs_dir)

    def build(self, message: str, *, include_known_world: bool = True,
              include_imagination_world: bool = True,
              memory_channels: list[str] | None = None,
              token_budget: int = 8000, max_nodes: int = 80,
              max_depth: int = 2) -> dict[str, Any]:
        sequence, state = self.store.state()
        active = self.store.active_context()
        versions = self.store.versions()
        selected_roles, role_sources = self._select_roles(message, active.get("roles", []))
        compiled_stance = self.compile_stance(selected_roles, role_sources)
        nodes, edges = self._federate(
            state, active, memory_channels, include_known_world,
            include_imagination_world, selected_roles, role_sources,
        )
        query_terms = _tokens(message)
        roles = selected_roles
        role_terms = {term for role in roles for term in ROLE_STRATEGIES.get(role, {}).get("terms", [])}
        preferred_edges = []
        for role in roles:
            for relation in ROLE_STRATEGIES.get(role, {}).get("edges", []):
                if relation not in preferred_edges:
                    preferred_edges.append(relation)

        distances = self._distances(edges, SELF_ID, max_depth)
        ranked = []
        for node in nodes.values():
            mandatory = (node.owner in {"self", "context"} or node.kind == "role"
                         or (include_imagination_world and not include_known_world and node.owner == "imagination"))
            score, reasons = self._score(node, query_terms, role_terms, active, distances, mandatory)
            text_terms = _tokens(f"{node.label} {node.content}")
            matched_terms = sorted(query_terms & text_terms)
            label_terms = _tokens(node.label)
            label_term_match = bool(label_terms & query_terms)
            label_match = bool(label_terms and label_terms <= query_terms)
            relevant = bool(matched_terms or label_match)
            if node.owner in {"known_world", "imagination"}:
                relevant = label_term_match or len(matched_terms) >= 2
            if node.owner == "capabilities":
                relevant = False
                reasons.append("registry entry is not a bound tool")
            elif node.owner == "imagination" and include_known_world and not matched_terms and not label_match:
                relevant = False
            if matched_terms:
                reasons.append("matched terms: " + ", ".join(matched_terms))
            if label_match:
                reasons.append("exact label match")
            ranked.append((mandatory, relevant, score, node, reasons))
        ranked.sort(key=lambda item: (not item[0], not item[1], -item[2], item[3].id))

        selected, excluded, used = [], [], 0
        for mandatory, relevant, score, node, reasons in ranked:
            rendered = self._render_node(node)
            cost = estimate_tokens(rendered)
            if relevant and "query match" not in reasons and "role affinity" not in reasons:
                reasons.append("relevant lexical signal")
            if (mandatory or relevant) and len(selected) < max_nodes and (mandatory or used + cost <= token_budget):
                selected.append({**asdict(node), "score": round(score, 4),
                                 "reason": "; ".join(reasons), "estimated_tokens": cost})
                used += cost
            else:
                reason = ("not relevant to this turn" if not mandatory and not relevant else
                          "node limit" if len(selected) >= max_nodes else "token budget")
                excluded.append({"node_id": node.id, "reason": reason})

        selected_ids = {item["id"] for item in selected}
        selected_edges = [asdict(edge) for edge in edges if edge.source in selected_ids and edge.target in selected_ids]
        handles = self._expansion_handles(edges, selected_ids, nodes)
        projection_id = f"projection_{uuid.uuid4().hex[:16]}"
        result = {
            "id": projection_id,
            "subject_id": SELF_ID,
            "state_sequence": sequence,
            "domain_versions": versions,
            "request": {"message": message, "active_context": active,
                        "limits": {"prompt_tokens": token_budget, "max_nodes": max_nodes, "max_depth": max_depth}},
            "strategy": {"explicit_roles": active.get("roles", []), "selected_roles": roles,
                         "role_sources": role_sources, "query_terms": sorted(query_terms),
                         "role_terms": sorted(role_terms), "preferred_edges": preferred_edges,
                         "compiled_stance": compiled_stance},
            "selected_nodes": selected,
            "selected_edges": selected_edges,
            "expansion_handles": handles,
            "excluded": excluded,
            "estimated_tokens": used,
            "created_at": time.time(),
        }
        result["rendered_context"] = self.render(result)
        return result

    def authorized_graph(self, *, include_known_world: bool = True,
                         include_imagination_world: bool = True,
                         memory_channels: list[str] | None = None) -> dict[str, Any]:
        """Return the complete currently authorized read model for graph tools.

        This is not prompt selection: callers must still enforce their own result
        limits. Protected records are absent because the underlying Store and
        visible_world adapters expose only standard visibility here.
        """
        _, state = self.store.state()
        active = self.store.active_context()
        nodes, edges = self._federate(
            state, active, memory_channels, include_known_world,
            include_imagination_world, active.get("roles", []),
            {role: "explicit" for role in active.get("roles", [])},
        )
        return {
            "nodes": {node_id: asdict(node) for node_id, node in nodes.items()},
            "edges": [asdict(edge) for edge in edges],
        }

    def _federate(self, state: dict, active: dict, memory_channels: list[str] | None,
                  include_known_world: bool, include_imagination_world: bool,
                  selected_roles: list[str], role_sources: dict[str, str]):
        nodes: dict[str, ProjectionNode] = {
            SELF_ID: ProjectionNode(SELF_ID, "self", "subject", "Halcyon", "The canonical subject of this projection.")
        }
        edges: list[ProjectionEdge] = []

        for claim in self.store.self_claims():
            nodes[claim["id"]] = ProjectionNode(
                claim["id"], "self", "self_claim", claim["kind"],
                f"{claim['subject']} {claim['predicate']} {claim['value']}",
                source_ids=[claim["source"]], created_at=claim["created_at"], metadata={"claim_kind": claim["kind"]},
            )
            edges.append(ProjectionEdge(SELF_ID, "self_has_claim", claim["id"], "self"))

        for item in self.store.memory_entries(memory_channels):
            status = "remembered" if item["channel"] == "experience" else "inferred"
            nodes[item["id"]] = ProjectionNode(
                item["id"], "memory", item["channel"], item["channel"].replace("_", " "), item["content"],
                status=status, scope=item["scope"], source_ids=[x for x in [item.get("source_event_id")] if x],
                created_at=item["created_at"], metadata={"origin": item["origin"], "derived_from": item["derived_from"]},
            )
            edges.append(ProjectionEdge(SELF_ID, "self_remembers", item["id"], "memory"))
            for source_id in item["derived_from"]:
                if source_id in nodes:
                    edges.append(ProjectionEdge(item["id"], "derived_from", source_id, "memory"))

        self._add_context(nodes, edges, active)
        self._add_roles(nodes, edges, selected_roles, role_sources)
        self._add_capabilities(nodes, edges)
        if include_known_world:
            self._add_world(nodes, edges, visible_world(state["world"]), "known_world", "self_knows_about", "canonical")
        if include_imagination_world:
            self._add_world(nodes, edges, visible_world(state["imagination_world"]), "imagination", "imagines", "fictional")
        return nodes, edges

    @staticmethod
    def _select_roles(message: str, explicit_roles: list[str]) -> tuple[list[str], dict[str, str]]:
        """Choose task stances without treating them as identity."""
        chosen = [role for role in explicit_roles if role in ROLE_STRATEGIES]
        sources = {role: "explicit" for role in chosen}
        terms = _tokens(message)
        candidates = []
        for role, strategy in ROLE_STRATEGIES.items():
            if role in sources:
                continue
            hits = terms & set(strategy["terms"])
            if hits:
                candidates.append((len(hits), role))
        if candidates:
            _, role = sorted(candidates, key=lambda item: (-item[0], item[1]))[0]
            chosen.append(role)
            sources[role] = "inferred"
        return chosen, sources

    def compile_stance(self, roles: list[str], sources: dict[str, str] | None = None) -> dict[str, Any]:
        """Compile profile packs into bounded, attributable task guidance."""
        sources = sources or {role: "explicit" for role in roles}
        profiles = []
        contributions: dict[str, dict[str, set[str]]] = {
            "attention": {}, "principles": {}, "methods": {},
            "expression": {}, "preferred_edges": {},
        }

        def contribute(kind: str, value: str, role_id: str):
            normalized = value.strip()
            if normalized:
                contributions[kind].setdefault(normalized, set()).add(role_id)

        for role_id in roles:
            path = self.identity_packs_dir / f"{role_id}.json"
            if not path.exists():
                continue
            pack = load_pack(path)
            strategy = ROLE_STRATEGIES.get(role_id, {})
            principles = [claim["value"] for claim in pack["claims"]
                          if claim["kind"] in {"value", "commitment", "goal", "self_understanding"}]
            expression = [claim["value"] for claim in pack["claims"]
                          if claim["kind"] == "preference" and claim["predicate"] == "expresses itself with"]
            methods = [{"id": item["id"], "description": item["description"]}
                       for item in pack.get("capabilities", [])]
            attention = strategy.get("terms", [])
            edges = strategy.get("edges", [])
            profiles.append({"id": role_id, "name": pack["name"], "source": sources.get(role_id, "explicit"),
                             "attention": attention, "principles": principles, "methods": methods,
                             "expression": expression, "preferred_edges": edges})
            for item in attention: contribute("attention", item, role_id)
            for item in principles: contribute("principles", item, role_id)
            for item in methods: contribute("methods", item["id"], role_id)
            for item in expression: contribute("expression", item, role_id)
            for item in edges: contribute("preferred_edges", item, role_id)

        tensions = []
        role_set = set(roles)
        for pair, detail in PROFILE_TENSIONS.items():
            if pair <= role_set:
                tensions.append({"profiles": sorted(pair), **detail})
        merged = {
            kind: [{"value": value, "contributed_by": sorted(contributors)}
                   for value, contributors in sorted(items.items())]
            for kind, items in contributions.items()
        }
        return {"profiles": profiles, **merged, "tensions": tensions,
                "precedence": ["governance", "canonical_self", "user_instruction",
                               "explicit_profiles", "inferred_profile", "expression"]}

    @staticmethod
    def _add_context(nodes, edges, active):
        values = []
        if active.get("world"):
            values.append((active["world"], "world"))
        if active.get("task"):
            values.append((active["task"], "task"))
        values.extend((value, "skill") for value in active.get("skills", []))
        for value, kind in values:
            node_id = f"context:{kind}:{value}"
            nodes[node_id] = ProjectionNode(node_id, "context", kind, value, f"Active {kind}: {value}")
            edges.append(ProjectionEdge(SELF_ID, "self_is_working_on" if kind == "task" else "scoped_to", node_id, "context"))

    def _add_roles(self, nodes, edges, roles, sources):
        for role_id in roles:
            path = self.identity_packs_dir / f"{role_id}.json"
            if not path.exists():
                continue
            pack = load_pack(path)
            node_id = f"role:{role_id}"
            reasoning_kinds = {"self_understanding", "value", "commitment", "goal"}
            claims = [f"[{c['kind']}] {c['predicate']} {c['value']}" for c in pack["claims"]
                      if c["kind"] in reasoning_kinds]
            methods = [cap["id"] for cap in pack.get("capabilities", [])]
            source = sources.get(role_id, "explicit")
            content = f"Task stance ({source}): {pack['name']} — {pack.get('tagline', '')}\n" + "\n".join(claims)
            if methods:
                content += "\nKnown methods: " + ", ".join(methods)
            nodes[node_id] = ProjectionNode(node_id, "role", "role", pack["name"], content,
                                             metadata={"role_id": role_id, "source": source, "methods": methods})
            edges.append(ProjectionEdge(SELF_ID, "self_is_filling_role", node_id, "role"))

    def _add_capabilities(self, nodes, edges):
        for capability in self.store.capabilities():
            node_id = f"capability:{capability['id']}"
            availability = "registered" if capability["available"] else "unavailable"
            nodes[node_id] = ProjectionNode(node_id, "capabilities", "capability", capability["id"],
                                             f"{capability['description']} ({capability['effect_class']}, {availability})",
                                             source_ids=[capability["source"]], metadata={"available": capability["available"]})
            edges.append(ProjectionEdge(SELF_ID, "self_can_use", node_id, "capabilities"))

    @staticmethod
    def _add_world(nodes, edges, world, owner, root_relation, status):
        for item in world["nodes"].values():
            node_id = f"{owner}:{item['id']}"
            props = "; ".join(f"{k}={v}" for k, v in sorted(item.get("properties", {}).items()))
            nodes[node_id] = ProjectionNode(node_id, owner, "entity", item["label"],
                                             f"{item['label']} ({item['type']})" + (f": {props}" if props else ""),
                                             status=status, visibility=item.get("visibility", "standard"),
                                             source_ids=item.get("sources", []))
            edges.append(ProjectionEdge(SELF_ID, root_relation, node_id, owner))
        for edge in world["edges"]:
            source, target = f"{owner}:{edge['source']}", f"{owner}:{edge['target']}"
            if source in nodes and target in nodes:
                edges.append(ProjectionEdge(source, edge["relation"], target, owner))

    @staticmethod
    def _distances(edges, root, max_depth):
        adjacent: dict[str, set[str]] = {}
        for edge in edges:
            adjacent.setdefault(edge.source, set()).add(edge.target)
            adjacent.setdefault(edge.target, set()).add(edge.source)
        distances, frontier = {root: 0}, [root]
        while frontier:
            current = frontier.pop(0)
            if distances[current] >= max_depth:
                continue
            for target in sorted(adjacent.get(current, set())):
                if target not in distances:
                    distances[target] = distances[current] + 1
                    frontier.append(target)
        return distances

    @staticmethod
    def _score(node, query_terms, role_terms, active, distances, mandatory):
        text_terms = _tokens(f"{node.label} {node.content}")
        query = len(query_terms & text_terms) / max(1, len(query_terms))
        role = len(role_terms & text_terms) / max(1, min(5, len(role_terms)))
        scope = 1.0 if node.scope == "global" or node.scope in set(active.get("skills", []) + [active.get("world"), active.get("task")]) else 0.0
        distance = distances.get(node.id)
        graph = 0.0 if distance is None else 1.0 / (1 + distance)
        provenance = 1.0 if node.status == "canonical" else 0.8 if node.status == "remembered" else 0.6
        score = query * .35 + scope * .20 + role * .15 + graph * .15 + provenance * .10
        if node.created_at:
            score += max(0.0, 1.0 - (time.time() - node.created_at) / (365 * 86400)) * .05
        if mandatory:
            score += 2.0
        reasons = []
        if mandatory: reasons.append("mandatory Self/context")
        if query: reasons.append("query match")
        if role: reasons.append("role affinity")
        if scope: reasons.append("active scope")
        if graph: reasons.append(f"graph distance {distance}")
        reasons.append(f"{node.status} provenance")
        return score, reasons

    @staticmethod
    def _render_node(node):
        return f"- [{node.id}] owner={node.owner} status={node.status} scope={node.scope}: {node.content}"

    @staticmethod
    def _expansion_handles(edges, selected_ids, nodes):
        grouped: dict[str, dict[str, Any]] = {}
        for edge in edges:
            if edge.source in selected_ids and edge.target not in selected_ids and edge.target in nodes:
                item = grouped.setdefault(edge.source, {"node_id": edge.source, "available_edges": set(), "unexpanded_count": 0})
                item["available_edges"].add(edge.relation)
                item["unexpanded_count"] += 1
        return [{**item, "available_edges": sorted(item["available_edges"])} for item in sorted(grouped.values(), key=lambda x: x["node_id"])]

    def render(self, projection):
        lines = [
            "# SELF-CENTERED KNOWLEDGE PROJECTION",
            "This is an authorized partial projection centered on canonical Self. Omission does not mean nonexistence.",
            "Preserve each item's owner and epistemic status. Fictional, remembered, inferred, and canonical material are not interchangeable.",
            "",
        ]
        groups = ["self", "context", "role", "memory", "known_world", "imagination", "capabilities"]
        headings = {
            "self": "CANONICAL SELF",
            "context": "TASK CONTEXT",
            "role": "ACTIVE REASONING ROLE",
            "memory": "SUPPLIED MEMORY",
            "known_world": "SUPPLIED KNOWN-WORLD KNOWLEDGE",
            "imagination": "SUPPLIED FICTIONAL KNOWLEDGE",
            "capabilities": "REGISTERED CAPABILITIES",
        }
        for owner in groups:
            items = [item for item in projection["selected_nodes"] if item["owner"] == owner]
            if owner == "self":
                items = [item for item in items if item["id"] != "self:preference:voice"]
            if not items:
                continue
            lines.append(f"## {headings[owner]}")
            if owner == "role":
                lines.append("These task-specific stances shape attention and method; they do not rename or replace Halcyon. Explicit profiles compose as peers. Any inferred profile is turn-scoped support and cannot override an explicit profile.")
            if owner == "capabilities":
                lines.append("Registry entries are not callable tools. A capability is callable only when a bound tool definition and tool result are present.")
            lines.extend(f"- [{item['id']}] status={item['status']} scope={item['scope']}: {item['content']}" for item in items)
            if owner == "role":
                stance = projection["strategy"].get("compiled_stance", {})
                attention = stance.get("attention", [])
                methods = stance.get("methods", [])
                if attention:
                    lines.append("Combined attention: " + "; ".join(
                        f"{item['value']} [{'+'.join(item['contributed_by'])}]" for item in attention
                    ))
                if methods:
                    lines.append("Known methods (reasoning procedures, not bound tools): " + "; ".join(
                        f"{item['value']} [{'+'.join(item['contributed_by'])}]" for item in methods
                    ))
                for tension in stance.get("tensions", []):
                    lines.append(f"Productive tension ({' + '.join(tension['profiles'])}): {tension['between']} Requirement: {tension['requirement']}")
            lines.append("")
        if projection["expansion_handles"]:
            lines.append("## EXPANSION HANDLES")
            lines.append("These identify omitted adjacent knowledge; they do not grant additional authority.")
            for handle in projection["expansion_handles"]:
                lines.append(f"- {handle['node_id']}: {handle['unexpanded_count']} omitted via {', '.join(handle['available_edges'])}")
        return "\n".join(lines).strip()
