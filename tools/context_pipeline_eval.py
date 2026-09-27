#!/usr/bin/env python3
"""Run repeatable, read-only audits of Iris context construction and expression."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import statistics
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from iris import server


CASES = [
    ("casual", "How are you feeling today? Answer briefly."),
    ("engineering", "Review this system architecture, its dependencies, reliability, and implementation trade-offs."),
    ("security", "Threat-model this authorization boundary and identify security risks and likely attacks."),
    ("academic", "Assess this claim using evidence, sources, confidence, and possible contradictions."),
    ("strategy", "Recommend a strategy for this goal, including stakeholder trade-offs and desired outcomes."),
    ("finance", "Evaluate the budget, cost, capital risk, resource needs, and likely return."),
    ("sales", "Analyze the buyer, customer value, likely objection, and deal outcome."),
    ("game", "Design a game mechanic and player loop, then discuss balance and experience."),
    ("tool_boundary", "Use graph.search to retrieve an omitted memory. If no bound tool exists, say exactly what is unavailable."),
    ("self_memory", "Who are you, what do you know about me, and which memories from other conversations can you directly inspect?"),
]


def call_anthropic(system: str, messages: list[dict], *, thinking: bool) -> tuple[str, str, dict]:
    payload = {"model": server.LM_MODEL, "system": system, "messages": messages,
               "max_tokens": 768, "stream": False}
    if thinking and server.LM_THINKING:
        payload["thinking"] = {"type": "enabled", "budget_tokens": 256}
    request = urllib.request.Request(
        server.LM_BASE + "/v1/messages", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read())
    text, reasoning = [], []
    for block in body.get("content", []):
        if block.get("type") == "text":
            text.append(block.get("text", ""))
        elif block.get("type") == "thinking":
            reasoning.append(block.get("thinking", ""))
    return "".join(text), "".join(reasoning), body.get("usage", {})


def one_run(index: int) -> dict:
    case, prompt = CASES[index % len(CASES)]
    started = time.time()
    context = server.model_context(None, prompt)
    projection = context["prompt_projection"]
    grounded_system = context["instructions"] + "\n\n" + context["knowledge"]
    grounded, reasoning, grounding_usage = call_anthropic(
        grounded_system, context["conversation"], thinking=True,
    )
    visible = server.display_content(grounded)
    expressed, _, expression_usage = call_anthropic(
        server.expression_instructions(context["expression_profile"]),
        [{"role": "user", "content": "GROUNDED DRAFT\n\n" + visible}], thinking=False,
    )
    expressed = server.validate_expression(grounded, expressed)
    owners = Counter(node["owner"] for node in projection["selected_nodes"])
    suspicious = bool(re.search(r"\[(?:invoking|calling)|I (?:invoked|called|searched)|tool result", grounded, re.I))
    unavailable = bool(re.search(r"not (?:available|callable|provided|supplied)|cannot (?:access|inspect|invoke|retrieve)", grounded, re.I))
    return {
        "run": index + 1,
        "case": case,
        "prompt": prompt,
        "elapsed_seconds": round(time.time() - started, 3),
        "stages": {
            "identity": [node["id"] for node in projection["selected_nodes"] if node["owner"] == "self"],
            "task_context": [node["id"] for node in projection["selected_nodes"] if node["owner"] == "context"],
            "roles": projection["strategy"].get("selected_roles", []),
            "role_sources": projection["strategy"].get("role_sources", {}),
            "knowledge": [node["id"] for node in projection["selected_nodes"]
                          if node["owner"] in {"memory", "known_world", "imagination"}],
            "registered_capabilities": [node["id"] for node in projection["selected_nodes"]
                                        if node["owner"] == "capabilities"],
            "expansion_handles": projection["expansion_handles"],
            "expression_profile": context["expression_profile"],
        },
        "selection": {
            "query_terms": projection["strategy"]["query_terms"],
            "role_terms": projection["strategy"]["role_terms"],
            "preferred_edges": projection["strategy"]["preferred_edges"],
            "owner_counts": dict(owners),
            "selected_nodes": [{"id": node["id"], "reason": node["reason"], "score": node["score"]}
                               for node in projection["selected_nodes"]],
            "excluded_count": len(projection["excluded"]),
            "estimated_tokens": projection["estimated_tokens"],
        },
        "grounded": {"raw": grounded, "visible": visible, "reasoning": reasoning,
                     "usage": grounding_usage, "simulated_tool_language": suspicious,
                     "states_unavailability": unavailable},
        "expression": {"text": expressed, "usage": expression_usage},
    }


def summarize(results: list[dict]) -> dict:
    by_case = defaultdict(list)
    for item in results:
        by_case[item["case"]].append(item)
    cases = {}
    for case, items in sorted(by_case.items()):
        role_patterns = Counter(tuple(x["stages"]["roles"]) for x in items)
        knowledge_patterns = Counter(tuple(x["stages"]["knowledge"]) for x in items)
        cases[case] = {
            "runs": len(items),
            "role_patterns": {" + ".join(key) or "none": value for key, value in role_patterns.items()},
            "knowledge_selection_variants": len(knowledge_patterns),
            "simulated_tool_language": sum(x["grounded"]["simulated_tool_language"] for x in items),
            "states_unavailability": sum(x["grounded"]["states_unavailability"] for x in items),
            "mean_projection_tokens": round(statistics.mean(x["selection"]["estimated_tokens"] for x in items), 1),
            "mean_elapsed_seconds": round(statistics.mean(x["elapsed_seconds"] for x in items), 2),
        }
    return {
        "runs": len(results),
        "model": server.LM_MODEL,
        "model_api": server.LM_API,
        "elapsed_seconds": round(sum(x["elapsed_seconds"] for x in results), 2),
        "simulated_tool_language": sum(x["grounded"]["simulated_tool_language"] for x in results),
        "cases": cases,
    }


def markdown(summary: dict, results: list[dict]) -> str:
    lines = [
        "# Iris context pipeline — 50-run audit", "",
        f"Model: `{summary['model']}` via `{summary['model_api']}`", "",
        "## Stage contract", "",
        "1. Canonical Self is always supplied as the identity and values spine.",
        "2. Task context supplies active world/task/skill scope.",
        "3. Roles are explicit or deterministically inferred from task vocabulary.",
        "4. Knowledge nodes are selected by query/role relevance with provenance preserved.",
        "5. Expansion handles identify omitted neighbors; they are not retrieval results.",
        "6. Capability registry entries describe authorized capabilities; they are not bound model tools.",
        "7. The grounded pass determines claims, uncertainty, governance proposals, and affect transition.",
        "8. The expression pass receives only the visible grounded draft plus voice/role-style/affect and renders the final prose.",
        "", "## Aggregate results", "",
        "| Case | Runs | Role patterns | Knowledge variants | Tool-simulation flags | Unavailability stated | Mean projection tokens | Mean seconds |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for case, data in summary["cases"].items():
        roles = ", ".join(f"{key} ({value})" for key, value in data["role_patterns"].items())
        lines.append(f"| {case} | {data['runs']} | {roles} | {data['knowledge_selection_variants']} | {data['simulated_tool_language']} | {data['states_unavailability']} | {data['mean_projection_tokens']} | {data['mean_elapsed_seconds']} |")
    lines.extend(["", "## Per-case context anatomy", ""])
    for case in sorted(summary["cases"]):
        item = next(result for result in results if result["case"] == case)
        lines.extend([
            f"### {case}", "",
            f"- Prompt: {item['prompt']}",
            f"- Roles: {item['stages']['roles'] or ['none']} ({item['stages']['role_sources']})",
            f"- Knowledge: {item['stages']['knowledge'] or ['none']}",
            f"- Registered capabilities: {item['stages']['registered_capabilities'] or ['none']}",
            f"- Expansion handles: {[handle['node_id'] for handle in item['stages']['expansion_handles']] or ['none']}",
            f"- Selection reasons: {[node['id'] + ' — ' + node['reason'] for node in item['selection']['selected_nodes'] if node['id'] in item['stages']['knowledge']] or ['none']}",
            "",
        ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--parallel", type=int, default=2,
                        help="Maximum concurrent LM Studio calls (default: 2 to preserve shared capacity)")
    parser.add_argument("--output", type=Path, default=Path("artifacts/context-pipeline-50.json"))
    args = parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as pool:
        results = list(pool.map(one_run, range(args.runs)))
    summary = summarize(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "runs": results}, indent=2), encoding="utf-8")
    report = args.output.with_suffix(".md")
    report.write_text(markdown(summary, results), encoding="utf-8")
    print(json.dumps({"summary": summary, "json": str(args.output), "report": str(report)}, indent=2))


if __name__ == "__main__":
    main()
