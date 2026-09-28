"""FastAPI server for the Halcyon chat and governance UI."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import re
import threading
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import AsyncIterator

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .kernel import Boundary, Gate, NOMINATION
from .graph import normalize_world, visible_world
from .identity_packs import list_packs, load_pack
from .imagination_doctrine import validate_blueprint
from .imagination_composer import compose_blueprint
from .imagination_registry import ImaginationPackRegistry, LensNotFound, PackNotFound
from .loop import SYSTEM, render_vocabulary
from .projection import ProjectionService
from .store import BlueprintConflict, ConversationBusy, StateConflict, Store
from .tools import TOOLS, build_invariants


ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.environ.get("IRIS_STATE", ROOT / "state"))
BOUNDARY_PATH = Path(os.environ.get("IRIS_BOUNDARY", ROOT / "boundary/imagine_and_chat.yaml"))
DB_PATH = Path(os.environ.get("IRIS_DB", STATE_DIR / "iris.db"))
IDENTITY_PACKS_DIR = ROOT / "seeds" / "identity_packs"
IMAGINATION_PACKS_DIR = ROOT / "seeds" / "imagination_packs"
LM_BASE = os.environ.get("IRIS_LM_BASE", "http://localhost:1234").rstrip("/")
LM_MODEL = os.environ.get("IRIS_LM_MODEL", "google/gemma-4-e4b")
LM_API = os.environ.get("IRIS_LM_API", "anthropic").lower()
LM_API_KEY = os.environ.get("IRIS_LM_API_KEY", "")
LM_THINKING = os.environ.get("IRIS_LM_THINKING", "1") not in {"0", "false", "False"}
CONTEXT_LIMIT = int(os.environ.get("IRIS_CONTEXT_LIMIT", "32768"))
AFFECT_LINE = re.compile(r"^AFFECT\s+(?P<values>.+)$")
AFFECT_DIMENSIONS = ("joy", "sadness", "fear", "anger", "trust", "disgust", "surprise", "anticipation")

SPEC = yaml.safe_load(BOUNDARY_PATH.read_text(encoding="utf-8"))
BOUNDARY = Boundary(SPEC)
BOUNDARY_HASH = "sha256:" + hashlib.sha256(BOUNDARY_PATH.read_bytes()).hexdigest()
STORE = Store(DB_PATH, STATE_DIR)
IMAGINATION_PACKS = ImaginationPackRegistry(IMAGINATION_PACKS_DIR, ROOT)


class TurnRequest(BaseModel):
    content: str


class CharacterTrait(BaseModel):
    id: str = Field(min_length=1, max_length=300)
    label: str = Field(min_length=1, max_length=300)
    group: str = Field(min_length=1, max_length=100)
    locked: bool = False


class CharacterSnapshotRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    blueprint_id: str = Field(min_length=1, max_length=300)
    revision: int = Field(ge=1)
    pack_id: str = Field(min_length=1, max_length=300)
    pack_version: int = Field(ge=1)
    traits: list[CharacterTrait] = Field(min_length=1, max_length=200)


class TokenRequest(BaseModel):
    conversation_id: str | None = None
    draft: str = ""

class ProjectionPreviewRequest(BaseModel):
    message: str
    include_known_world: bool = True
    include_imagination_world: bool = True
    token_budget: int = Field(default=8000, ge=500, le=24000)
    max_nodes: int = Field(default=80, ge=1, le=200)
    max_depth: int = Field(default=2, ge=0, le=2)

class ActiveContextRequest(BaseModel):
    world: str | None = "world:halcyon"
    task: str | None = None
    skills: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)

class MemoryEntryRequest(BaseModel):
    scope: str
    channel: str
    content: str
    origin: str = "experience"
    source_event_id: str | None = None
    derived_from: list[str] = Field(default_factory=list)

class AffectTransitionRequest(BaseModel):
    source_event_id: str
    deltas: dict[str, float]

class SelfClaimRequest(BaseModel):
    kind: str
    subject: str
    predicate: str
    value: str

class ToolExecuteRequest(BaseModel):
    tool_id: str
    arguments: dict = Field(default_factory=dict)

class McpCapabilityRequest(BaseModel):
    tool_id: str
    server: str
    description: str
    schema_definition: dict = Field(default_factory=dict)
    effect_class: str = "observe"

class ImaginationRunRequest(BaseModel):
    seed: str = "Grow your world. Add something true to itself and connected to what is already there."
    max_steps: int = Field(default=5, ge=1, le=20)
    auto_start: bool = True

class ImaginationBatchRequest(BaseModel):
    turns: int = Field(default=5, ge=1, le=20)

class ImaginationChatRequest(BaseModel):
    content: str

class BlueprintCreateRequest(BaseModel):
    title: str
    artifact_type: str
    pack: str = "villain"
    lens_id: str | None = None
    initiating_pressure_id: str | None = None
    ingredients: list[dict] = Field(default_factory=list)
    tensions: list[dict] = Field(default_factory=list)
    rejected_suggestions: list[dict] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    draft_entities: list[dict] = Field(default_factory=list)
    draft_edges: list[dict] = Field(default_factory=list)

class BlueprintUpdateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    patch: dict
    actor: str = "user"
    reason: str = "updated"

class BlueprintComposeRequest(BaseModel):
    expected_revision: int = Field(ge=1)

class BlueprintAdmitRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    candidate_hash: str

class PressureExploreRequest(BaseModel):
    title: str
    artifact_type: str
    pack: str = "villain"
    lens_id: str | None = None


class StreamHub:
    def __init__(self):
        self.events: dict[str, list[dict]] = defaultdict(list)
        self.conditions: dict[str, asyncio.Condition] = defaultdict(asyncio.Condition)
        self.terminal: set[str] = set()
        self.cancelled: set[str] = set()
        self.cancel_events: dict[str, threading.Event] = {}

    async def emit(self, turn_id: str, event: str, data: dict) -> None:
        items = self.events[turn_id]
        envelope = {"sequence": len(items) + 1, "timestamp": time.time(), "turn_id": turn_id, **data}
        items.append({"event": event, "data": envelope})
        if event in {"assistant.completed", "turn.failed", "turn.cancelled",
                     "imagination.run.completed", "imagination.run.cancelled", "imagination.run.failed",
                     "imagination.run.paused"}:
            self.terminal.add(turn_id)
        async with self.conditions[turn_id]:
            self.conditions[turn_id].notify_all()

    async def stream(self, turn_id: str, after: int = 0) -> AsyncIterator[str]:
        cursor = after
        while True:
            items = self.events.get(turn_id, [])
            while cursor < len(items):
                item = items[cursor]
                cursor += 1
                yield f"id: {cursor}\nevent: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
            if turn_id in self.terminal:
                break
            try:
                async with self.conditions[turn_id]:
                    await asyncio.wait_for(self.conditions[turn_id].wait(), timeout=15)
            except asyncio.TimeoutError:
                yield f"event: stream.heartbeat\ndata: {json.dumps({'turn_id': turn_id, 'timestamp': time.time()})}\n\n"


HUB = StreamHub()
IMAGINATION_TASKS: dict[str, asyncio.Task] = {}
app = FastAPI(title="Halcyon", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
)


def render_world(world: dict) -> str:
    world = visible_world(world)
    parts = ["# NODES"] + [f"- {node['label']} ({node['type']})" for node in sorted(world["nodes"].values(), key=lambda item: item["label"])]
    parts += ["", "# EDGES"] + [f"- {world['nodes'][edge['source']]['label']} | {edge['relation']} | {world['nodes'][edge['target']]['label']}" for edge in world["edges"]]
    parts += ["", "# CONSTRAINTS"] + [f"- {world['nodes'][rule['target']]['label']} | {rule['rule']} | {rule['value']}" for rule in world["constraints"]]
    return "\n".join(parts)


def render_state(state: dict) -> tuple[str, str, str]:
    """Self text, the known/seeded entity world, and the separate imagined world.

    state["world"] is the factual entity graph (seeded biography, real people/places)
    that Memory projects. state["imagination_world"] is the fictional graph the
    imagination verbs (create/relate/constrain/occur/name) actually write to. These are
    two different canonical stores so imagined-world content never lands in, or reads
    from, the factual one. See README "Important graph distinction".
    """
    self_mem = state["self"].get("memory", {})
    self_text = "(nothing remembered yet)" if not self_mem else "\n".join(
        f"- {k}: {v}" for k, v in sorted(self_mem.items()))
    return self_text, render_world(state["world"]), render_world(state["imagination_world"])

def system_projection() -> dict:
    sequence, state = STORE.state()
    claims = STORE.self_claims()
    entries = STORE.memory_entries()
    affect = STORE.effective_affect()
    context = STORE.active_context()
    capabilities = STORE.capabilities()
    world = visible_world(state["world"])
    channel_counts = {channel: sum(1 for item in entries if item["channel"] == channel)
                      for channel in ("experience", "cognitive_semantic", "emotional_semantic")}
    versions = STORE.versions()
    stance = ProjectionService(STORE, IDENTITY_PACKS_DIR).compile_stance(context.get("roles", []))
    return {
        "projection": True,
        "self": {"claims": claims, "claim_count": len(claims), "version": versions.get("self", 0)},
        "memory": {"channels": channel_counts, "reachable_entries": len(entries),
                   "world_nodes": len(world["nodes"]), "world_edges": len(world["edges"]),
                   "version": versions.get("memory", sequence)},
        "affect": {**affect, "version": versions.get("affect", 0)},
        "context": {**context, "version": versions.get("context", 0)},
        "stance": stance,
        "capabilities": {"items": capabilities, "available": sum(1 for item in capabilities if item["available"]),
                         "version": versions.get("capabilities", 0)},
        "governance": {"boundaries": {"world_self": BOUNDARY_HASH, "affect": "affect-vector-v1",
                                         "self": "self-claims-v1", "capabilities": "capability-v1"},
                       "version": versions.get("governance", 0)},
        "versions": versions,
    }


def model_context(conversation_id: str | None, draft: str,
                  memory_channels: list[str] | None = None,
                  include_world_mutation: bool = True,
                  include_known_world: bool = True,
                  include_imagination_world: bool = True) -> dict:
    sequence, state = STORE.state()
    self_text, known_world_text, imagination_world_text = render_state(state)
    instructions = SYSTEM.format(vocab=render_vocabulary(BOUNDARY)) + """

# GROUNDED RESPONSE PIPELINE
This pass determines substance, not presentation. Keep canonical Self, task roles, supplied
knowledge, retrieval handles, and capabilities distinct. A registered capability description is
not a tool result and MUST NOT be narrated as an invocation. Expansion handles prove only that
adjacent material was omitted. Use only facts literally supplied in this turn or returned by an
actual tool-result message. State when requested material is unavailable.

# AFFECT TRANSITION
The CURRENT AFFECT vector below is canonical input, not prose or personality.
React naturally from it. At the end of every completed response, propose exactly one complete
next vector on its own line using this literal form:
AFFECT joy:50.0; sadness:50.0; fear:50.0; anger:50.0; trust:50.0; disgust:50.0; surprise:50.0; anticipation:50.0
Include every dimension exactly once. Values must remain between 1 and 100 and no dimension
may move more than 10 points from the supplied current vector. This line is hidden from chat
and has no authority until the deterministic Affect boundary admits the complete vector.
Do not create cognitive or emotional semantic memories during ordinary chat; those meanings
are formed later by reflection/dreaming.
"""
    if include_world_mutation:
        instructions += """

# THE WORLD YOU ARE IMAGINING
The graph under THE WORLD YOU ARE IMAGINING (if present below) is fictional — entities, places,
relations, and events you and the user are building together. It is a separate canonical store
from WHAT YOU KNOW; nothing here is a fact about the real world, and nothing you know about the
real world belongs in it. You may read, discuss, question, interpret, or develop it in any
conversation, not only inside a dedicated Imagination session.

If one concrete change to the imagined world clearly belongs, you MAY include exactly one literal
NOMINATE line using the declared vocabulary. If no change belongs, do not nominate anything. Any
nomination remains a proposal until the ordinary deterministic gate admits and atomically commits
it. Do not expose the NOMINATE line in your visible prose and do not claim a proposed world change
committed before the gate decides.
"""
    eligible_memory = STORE.memory_entries(memory_channels)
    affect = STORE.effective_affect()
    active = STORE.active_context()
    system = system_projection()
    projection = ProjectionService(STORE, IDENTITY_PACKS_DIR).build(
        draft, include_known_world=include_known_world,
        include_imagination_world=include_imagination_world,
        memory_channels=memory_channels,
        token_budget=max(1000, min(12000, CONTEXT_LIMIT // 2)),
    )
    affect_text = "\n".join(f"- {key}: {value}" for key, value in affect["values"].items())
    knowledge = (projection["rendered_context"]
                 + "\n\n# GOVERNED CONTROL STATE\n"
                 + "The current Affect vector is required for the hidden transition protocol; it is not knowledge or persona.\n"
                 + affect_text)
    selected_roles = projection["strategy"].get("selected_roles", [])
    compiled_stance = projection["strategy"].get("compiled_stance", {})
    expression = expression_profile(compiled_stance, affect)
    prior = STORE.context_messages(conversation_id) if conversation_id else []
    conversation = prior + [{"role": "user", "content": draft}]
    supplied_memory_ids = {node["id"] for node in projection["selected_nodes"] if node["owner"] == "memory"}
    supplied_memory = [item for item in eligible_memory if item["id"] in supplied_memory_ids]
    omitted_memory = [item["id"] for item in eligible_memory if item["id"] not in supplied_memory_ids]
    selected_by_owner = {
        owner: [node["id"] for node in projection["selected_nodes"] if node["owner"] == owner]
        for owner in ("self", "context", "role", "memory", "known_world", "imagination", "capabilities")
    }
    kernel_ids = {"self:halcyon", "self:identity:name", "self:identity:pronouns",
                  "self:identity:form", "self:identity:origin", "self:relationship:brad"}
    context_manifest = {
        "identity_kernel": [node_id for node_id in selected_by_owner["self"] if node_id in kernel_ids],
        "activated_self_claims": [node_id for node_id in selected_by_owner["self"] if node_id not in kernel_ids],
        "task_context": active,
        "roles": [{"id": role_id, "source": projection["strategy"].get("role_sources", {}).get(role_id, "explicit")}
                  for role_id in selected_roles],
        "compiled_stance": compiled_stance,
        "conversation": {"messages_supplied": len(conversation), "prior_messages": len(prior)},
        "memory": {"eligible": [item["id"] for item in eligible_memory],
                   "supplied": [item["id"] for item in supplied_memory],
                   "omitted": omitted_memory, "tool_retrieved": []},
        "knowledge": {"known_world": selected_by_owner["known_world"],
                      "imagination": selected_by_owner["imagination"]},
        "tools": {"registered": [item["id"] for item in system["capabilities"]["items"] if item["available"]],
                  "bound": []},
        "affect_snapshot": {"values": affect["values"], "baselines": affect["baselines"],
                            "directions": affect["directions"]},
        "expansion_handles": projection["expansion_handles"],
        "budgets": projection["request"]["limits"],
        "versions": projection["domain_versions"],
    }
    return {"state_sequence": sequence, "state": state, "instructions": instructions,
            "knowledge": knowledge, "retrieved_memory": supplied_memory,
            "eligible_memory": eligible_memory, "supplied_memory": supplied_memory,
            "affect": affect,
            "active_context": active, "system_projection": system,
            "prompt_projection": projection,
            "expression_profile": expression, "context_manifest": context_manifest,
            "conversation": conversation, "model_id": LM_MODEL,
            "context_limit": CONTEXT_LIMIT}


def expression_profile(compiled_stance: dict, affect: dict) -> dict:
    """Build the final rendering profile, deliberately outside knowledge selection."""
    voice = next((claim["value"] for claim in STORE.self_claims()
                  if claim["id"] == "self:preference:voice"), "plain, direct language")
    expression = compiled_stance.get("expression", [])
    role_voices = [item["value"] for item in expression]
    return {"voice": voice, "role_voices": role_voices,
            "role_voice_sources": expression, "stance_profiles": compiled_stance.get("profiles", []),
            "stance_tensions": compiled_stance.get("tensions", []), "affect": affect["values"]}


def expression_instructions(profile: dict) -> str:
    role_voice = "\n".join(f"- {value}" for value in profile.get("role_voices", [])) or "- none"
    affect = "; ".join(f"{key}:{value}" for key, value in profile.get("affect", {}).items())
    trajectory = profile.get("affect_trajectory", {})
    direction = "; ".join(f"{key}:{value:+.2f}" for key, value in trajectory.get("delta", {}).items())
    return f"""You are the final expression layer for Halcyon.

Rewrite the supplied GROUNDED DRAFT into Halcyon's visible voice. Expression happens after
reasoning and retrieval. Preserve every factual claim, uncertainty, recommendation, refusal,
and availability boundary. Do not add facts, imply a tool was called, strengthen confidence,
or introduce new conclusions. Do not mention this pipeline. Return visible prose only: never
emit NOMINATE or AFFECT lines.

HALCYON VOICE
- {profile.get('voice', 'plain, direct language')}

ROLE-SPECIFIC PRESENTATION (style only)
{role_voice}

CURRENT AFFECTIVE COLOR
{affect}

UNCOMMITTED AFFECTIVE TRAJECTORY (tone only; never describe it as committed state)
{direction or 'none'}
"""


def validate_expression(grounded: str, expressed: str) -> str:
    """Reject expression output that crosses the control-plane boundary."""
    fidelity = expression_fidelity(display_content(grounded), expressed)
    if not fidelity["passed"]:
        return display_content(grounded)
    return fidelity["value"]


def expression_fidelity(grounded_visible: str, expressed: str) -> dict:
    """Conservative structural checks until grounded output is a typed envelope."""
    value = display_content(expressed).strip()
    checks: dict[str, bool] = {
        "nonempty": bool(value),
        "no_control_lines": "NOMINATE what=" not in expressed and not any(
            AFFECT_LINE.match(line.strip()) for line in expressed.splitlines()
        ),
    }
    grounded_numbers = set(re.findall(r"(?<![\w])[-+]?\d+(?:\.\d+)?%?", grounded_visible))
    expressed_numbers = set(re.findall(r"(?<![\w])[-+]?\d+(?:\.\d+)?%?", value))
    checks["numbers_preserved"] = grounded_numbers <= expressed_numbers
    grounded_ids = set(re.findall(r"`([^`]+)`", grounded_visible))
    expressed_ids = set(re.findall(r"`([^`]+)`", value))
    checks["quoted_identifiers_preserved"] = grounded_ids <= expressed_ids
    boundary_terms = ("unavailable", "not available", "cannot", "not callable", "not supplied",
                      "unknown", "uncertain", "proposed", "uncommitted", "denied", "failed")
    required_boundaries = {term for term in boundary_terms if term in grounded_visible.lower()}
    checks["availability_preserved"] = all(term in value.lower() for term in required_boundaries)
    checks["bounded_expansion"] = len(value) <= max(len(grounded_visible) * 3, len(grounded_visible) + 400)
    return {"passed": all(checks.values()), "checks": checks, "value": value,
            "grounded_numbers": sorted(grounded_numbers),
            "grounded_identifiers": sorted(grounded_ids),
            "required_boundaries": sorted(required_boundaries)}


def imagination_context(conversation_id: str, intention: str, step: int,
                        rejection: str | None = None) -> dict:
    task = f"""<imagination_task>
MODE: AUTONOMOUS IMAGINATION

INTENTION
{intention}

STEP
{step}

Develop exactly one meaningful part of the world. It must connect naturally to canonical world state.
</imagination_task>"""
    if rejection:
        task += f"""

<previous_rejection>
The prior attempt committed nothing.

REASON
{rejection}

Correct the rejected field. Do not repeat the invalid value.
</previous_rejection>"""
    context = model_context(conversation_id, task, memory_channels=["emotional_semantic"],
                            include_world_mutation=False, include_known_world=False)
    values = context["affect"]["values"]
    ranges = "\n".join(
        f"{name}: current={value:.2f} allowed=[{max(1.0, value - 10.0):.2f}, {min(100.0, value + 10.0):.2f}]"
        for name, value in values.items()
    )
    template = "; ".join(f"{name}:{value:.2f}" for name, value in values.items())
    context["instructions"] += f"""

--- IMAGINATION OUTPUT CONTRACT ---

<affect_boundary>
The current vector and admitted range for this transaction are:

{ranges}

Every proposed value MUST fall inside its displayed inclusive range.
</affect_boundary>

<required_output>
Return these three sections in this exact order, separated by blank lines:

1. Plain-language reflection explaining the single addition.

2. Exactly one literal NOMINATE line using the declared vocabulary. No Markdown fence.
The N in NOMINATE must be the first character on the line and the final argument value must be
the last character. Do not add bullets, backticks, bold markers, labels, or commentary to that line.

3. Exactly one complete Affect line containing all eight dimensions:
AFFECT {template}

The template contains the current valid values. Change only dimensions that genuinely respond to this step.
</required_output>

--- END IMAGINATION OUTPUT CONTRACT ---"""
    return context


def world_dialogue_context(conversation_id: str, content: str) -> dict:
    context = model_context(conversation_id, content, memory_channels=["emotional_semantic"],
                            include_known_world=False)
    context["instructions"] += """

--- WORLD DIALOGUE MODE ---

<world_dialogue>
The user is talking with you inside the Imagination workspace about the world you are imagining
together. Use the supplied THE WORLD YOU ARE IMAGINING graph as present reality; treat it as the
primary subject of this turn.

Retrieved scoped memory above has been narrowed to your emotional state only, and the WHAT YOU
KNOW factual entity graph has been withheld, so real-world facts do not get mistaken for, or mixed
into, the fictional world. Keep the world-graph NOMINATE allowance and the Affect line required by
the Affect boundary. Do not expose either machine-readable line in your prose and do not claim that
a proposed world change committed before the gate decides.
</world_dialogue>

--- END WORLD DIALOGUE MODE ---"""
    return context


def estimate_tokens(text: str) -> int:
    # Explicitly an estimate. Most common tokenizers average roughly four chars/token.
    return max(1, (len(text) + 3) // 4) if text else 0


def usage_for_context(context: dict, output: str = "", reasoning: str = "") -> dict:
    instructions = estimate_tokens(context["instructions"])
    knowledge = estimate_tokens(context["knowledge"])
    conversation = estimate_tokens(json.dumps(context["conversation"], ensure_ascii=False))
    output_tokens = estimate_tokens(output)
    reasoning_tokens = estimate_tokens(reasoning)
    return {"instructions": instructions, "knowledge": knowledge, "conversation": conversation,
            "input_tokens": instructions + knowledge + conversation,
            "reasoning_tokens": reasoning_tokens or None, "output_tokens": output_tokens,
            "total_tokens": instructions + knowledge + conversation + output_tokens + reasoning_tokens,
            "context_limit": CONTEXT_LIMIT, "source": "estimate"}


def proposal_from(raw: str, receipt: dict) -> dict | None:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    matches = [(line, NOMINATION.match(line)) for line in lines if NOMINATION.match(line)]
    if not matches:
        nomination_like = next((line for line in lines if line.startswith("NOMINATE")), None)
        if nomination_like:
            return {"raw_line": nomination_like, "parse_status": "malformed"}
        return None
    if len(matches) > 1:
        return {"raw_line": "\n".join(line for line, _ in matches), "parse_status": "multiple"}
    line, match = matches[0]
    claim = receipt.get("claim")
    return {"raw_line": line, "what_path": match.group("what"), "verb": match.group("verb"),
            "raw_args": match.group("args"), "normalized_args": claim.get("args") if claim else None,
            "parse_status": "valid"}


def display_content(raw: str) -> str:
    visible = "\n".join(
        line for line in raw.splitlines()
        if "NOMINATE what=" not in line and not AFFECT_LINE.match(line.strip())
    ).strip()
    visible = re.sub(r"<\|[^>]+\|>", "", visible)
    return re.sub(
        r"^\s*final\s+plain-language reflection explaining the single addition\.?\s*",
        "", visible, flags=re.IGNORECASE,
    ).strip()

def affect_proposal(raw: str) -> dict[str, float] | None:
    matches = [AFFECT_LINE.match(line.strip()) for line in raw.splitlines() if AFFECT_LINE.match(line.strip())]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError("exactly one Affect vector may be proposed")
    pairs: dict[str, float] = {}
    for part in matches[0].group("values").split(";"):
        if ":" not in part:
            raise ValueError("malformed Affect vector")
        key, raw_value = (value.strip() for value in part.split(":", 1))
        if key in pairs:
            raise ValueError(f"duplicate Affect dimension {key}")
        value = float(raw_value)
        if not (value == value and abs(value) != float("inf")):
            raise ValueError("Affect values must be finite")
        pairs[key] = value
    if set(pairs) != set(AFFECT_DIMENSIONS):
        raise ValueError("Affect vector must contain exactly the configured dimensions")
    return pairs


def parse_openai_stream(response, callback, cancelled: threading.Event) -> tuple[str, str, dict]:
    answer, reasoning = [], []
    provider_usage: dict = {}
    for binary in response:
        if cancelled.is_set():
            break
        line = binary.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            continue
        value = line[5:].strip()
        if value == "[DONE]":
            break
        try:
            packet = json.loads(value)
        except json.JSONDecodeError:
            continue
        if packet.get("usage"):
            provider_usage = packet["usage"]
            callback("assistant.usage", {"usage": provider_usage, "source": "provider"})
        choices = packet.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        thought = delta.get("reasoning_content") or delta.get("reasoning") or ""
        content = delta.get("content") or ""
        if thought:
            reasoning.append(thought)
            callback("assistant.reasoning.delta", {"delta": thought, "reasoning_kind": "analysis"})
        if content:
            answer.append(content)
            callback("assistant.delta", {"delta": content})
    return "".join(answer), "".join(reasoning), provider_usage


def parse_anthropic_stream(response, callback, cancelled: threading.Event) -> tuple[str, str, dict]:
    answer, reasoning = [], []
    provider_usage: dict = {}
    event_name = ""
    for binary in response:
        if cancelled.is_set():
            break
        line = binary.decode("utf-8", errors="replace").strip()
        if line.startswith("event:"):
            event_name = line[6:].strip()
            continue
        if not line.startswith("data:"):
            continue
        try:
            packet = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        event_type = packet.get("type") or event_name
        if event_type == "message_start":
            usage = (packet.get("message") or {}).get("usage") or {}
            if usage:
                provider_usage.update(usage)
                callback("assistant.usage", {"usage": provider_usage, "source": "provider"})
        elif event_type == "content_block_start":
            block = packet.get("content_block") or {}
            if block.get("type") == "thinking" and block.get("thinking"):
                value = block["thinking"]
                reasoning.append(value)
                callback("assistant.reasoning.delta", {"delta": value, "reasoning_kind": "analysis"})
            elif block.get("type") == "text" and block.get("text"):
                value = block["text"]
                answer.append(value)
                callback("assistant.delta", {"delta": value})
        elif event_type == "content_block_delta":
            delta = packet.get("delta") or {}
            if delta.get("type") == "thinking_delta":
                value = delta.get("thinking", "")
                reasoning.append(value)
                callback("assistant.reasoning.delta", {"delta": value, "reasoning_kind": "analysis"})
            elif delta.get("type") == "text_delta":
                value = delta.get("text", "")
                answer.append(value)
                callback("assistant.delta", {"delta": value})
        elif event_type == "message_delta":
            usage = packet.get("usage") or {}
            if usage:
                provider_usage.update(usage)
                callback("assistant.usage", {"usage": provider_usage, "source": "provider"})
    return "".join(answer), "".join(reasoning), provider_usage


async def run_turn(turn: dict, context: dict, imagination_run_id: str | None = None,
                   imagination_kind: str = "autonomous") -> tuple[bool, str | None]:
    turn_id = turn["id"]
    loop = asyncio.get_running_loop()
    cancel = threading.Event()
    HUB.cancel_events[turn_id] = cancel
    await HUB.emit(turn_id, "turn.created", {"turn": turn})
    await HUB.emit(turn_id, "assistant.started", {"model_id": LM_MODEL})
    if imagination_run_id:
        await HUB.emit(imagination_run_id, f"imagination.{imagination_kind}.started", {"turn": turn})

    def callback(event: str, data: dict) -> None:
        asyncio.run_coroutine_threadsafe(HUB.emit(turn_id, event, data), loop)
        if imagination_run_id:
            asyncio.run_coroutine_threadsafe(HUB.emit(imagination_run_id, f"imagination.{event}", {**data, "turn_id": turn_id}), loop)

    def request_model(system: str, messages: list[dict], event_callback,
                      *, use_thinking: bool = True):
        if LM_API == "anthropic":
            payload = {"model": LM_MODEL, "system": system, "messages": messages,
                       "max_tokens": 2048, "stream": True}
            if LM_THINKING and use_thinking:
                payload["thinking"] = {"type": "enabled", "budget_tokens": 1024}
            headers = {"Content-Type": "application/json", "anthropic-version": "2023-06-01"}
            if LM_API_KEY:
                headers["x-api-key"] = LM_API_KEY
            endpoint = "/v1/messages"
            parser = parse_anthropic_stream
        elif LM_API == "openai":
            payload = {"model": LM_MODEL,
                       "messages": [{"role": "system", "content": system}] + messages,
                       "temperature": 0.7, "max_tokens": 2048, "stream": True,
                       "stream_options": {"include_usage": True}}
            headers = {"Content-Type": "application/json"}
            if LM_API_KEY:
                headers["Authorization"] = f"Bearer {LM_API_KEY}"
            endpoint = "/v1/chat/completions"
            parser = parse_openai_stream
        else:
            raise ValueError(f"unsupported IRIS_LM_API {LM_API!r}")
        body = json.dumps(payload).encode()
        req = urllib.request.Request(LM_BASE + endpoint, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=300) as response:
            return parser(response, event_callback, cancel)

    try:
        grounded_system = context["instructions"] + "\n\n" + context["knowledge"]

        def grounding_callback(event: str, data: dict) -> None:
            # The grounded draft is authoritative but not yet user-facing.
            if event != "assistant.delta":
                callback(event, data)

        raw, reasoning, grounding_usage = await asyncio.to_thread(
            request_model, grounded_system, context["conversation"], grounding_callback,
        )
        if turn_id in HUB.cancelled:
            cancel.set()
            result = STORE.fail_turn(turn_id, "generation_cancelled", cancelled=True)
            await HUB.emit(turn_id, "turn.cancelled", {"turn": result})
            if imagination_run_id:
                await HUB.emit(imagination_run_id, "imagination.step.cancelled", {"turn": result})
            HUB.cancel_events.pop(turn_id, None)
            return False, "generation cancelled"
        grounded_visible = display_content(raw)
        next_affect = affect_proposal(raw)
        if next_affect is None:
            raise ValueError("completed response did not propose the required Affect vector")
        affect_preview = STORE.preview_affect(next_affect)
        expression_profile_used = copy.deepcopy(context["expression_profile"])
        expression_profile_used["affect_trajectory"] = affect_preview
        expressed = grounded_visible
        expression_usage: dict = {}
        fidelity = expression_fidelity(grounded_visible, grounded_visible)
        expression_fallback = False
        if grounded_visible:
            try:
                expression_prompt = expression_instructions(expression_profile_used)

                def expression_callback(event: str, data: dict) -> None:
                    # Validate the complete rendering before anything reaches chat.
                    if event == "assistant.usage":
                        callback(event, data)

                candidate, _, expression_usage = await asyncio.to_thread(
                    request_model, expression_prompt,
                    [{"role": "user", "content": "GROUNDED DRAFT\n\n" + grounded_visible}],
                    expression_callback, use_thinking=False,
                )
                fidelity = expression_fidelity(grounded_visible, candidate)
                expressed = validate_expression(raw, candidate)
                expression_fallback = not fidelity["passed"]
                callback("assistant.delta", {"delta": expressed})
            except Exception:
                # Expression is presentation only; its failure cannot invalidate
                # an otherwise governed response.
                callback("assistant.delta", {"delta": grounded_visible})
                expressed = grounded_visible
                expression_fallback = True
                fidelity = {"passed": False, "checks": {"expression_request": False},
                            "value": grounded_visible}
        if turn_id in HUB.cancelled:
            cancel.set()
            result = STORE.fail_turn(turn_id, "generation_cancelled", cancelled=True)
            await HUB.emit(turn_id, "turn.cancelled", {"turn": result})
            if imagination_run_id:
                await HUB.emit(imagination_run_id, "imagination.step.cancelled", {"turn": result})
            HUB.cancel_events.pop(turn_id, None)
            return False, "generation cancelled"
        STORE.mark_finalizing(turn_id)
        await HUB.emit(turn_id, "assistant.finalizing", {})
        # Finalization and gate execution operate on the authoritative state version.
        for attempt in range(2):
            if turn_id in HUB.cancelled:
                result = STORE.fail_turn(turn_id, "generation_cancelled", cancelled=True)
                await HUB.emit(turn_id, "turn.cancelled", {"turn": result})
                HUB.cancel_events.pop(turn_id, None)
                return False, "generation cancelled"
            sequence, state = STORE.state()
            gate = Gate(BOUNDARY, copy.deepcopy(state), TOOLS, build_invariants(SPEC))
            receipt = gate.adjudicate(raw)
            proposal = proposal_from(raw, receipt)
            usage = usage_for_context(context, raw, reasoning)
            provider_usage = dict(grounding_usage)
            for key, value in expression_usage.items():
                if isinstance(value, (int, float)):
                    provider_usage[key] = provider_usage.get(key, 0) + value
            if provider_usage:
                input_count = provider_usage.get("input_tokens", provider_usage.get("prompt_tokens", usage["input_tokens"]))
                output_count = provider_usage.get("output_tokens", provider_usage.get("completion_tokens", usage["output_tokens"]))
                usage.update({
                    "input_tokens": input_count,
                    "output_tokens": output_count,
                    "total_tokens": provider_usage.get("total_tokens", input_count + output_count),
                    "source": "provider",
                })
            try:
                result = STORE.finalize(turn_id, raw, expressed, reasoning or None,
                                        "analysis" if reasoning else None, receipt, gate.state,
                                        sequence, BOUNDARY_HASH, proposal, usage, next_affect,
                                        {"profile": expression_profile_used,
                                         "grounded_visible": grounded_visible,
                                         "fidelity": fidelity,
                                         "fallback": expression_fallback})
                await HUB.emit(turn_id, "assistant.completed", result)
                if imagination_run_id:
                    await HUB.emit(imagination_run_id, "imagination.assistant.completed", result)
                HUB.cancel_events.pop(turn_id, None)
                return True, None
            except StateConflict:
                if attempt == 1:
                    raise
    except Exception as exc:
        code = "model_unavailable" if isinstance(exc, (OSError, TimeoutError)) else "adjudication_failed"
        result = STORE.fail_turn(turn_id, code)
        await HUB.emit(turn_id, "turn.failed", {"turn": result, "error_code": code})
        if imagination_run_id:
            await HUB.emit(imagination_run_id, "imagination.step.failed", {"turn": result, "error_code": code, "detail": str(exc)})
        HUB.cancel_events.pop(turn_id, None)
        return False, str(exc)


def graph_patch_for_turn(turn_id: str) -> dict | None:
    turn = STORE.turn(turn_id)
    receipt = turn.get("receipt") if turn else None
    if not receipt or receipt.get("outcome") != "committed":
        return None
    claim = json.loads(receipt["claim_json"]) if receipt.get("claim_json") else None
    result = json.loads(receipt["result_json"]) if receipt.get("result_json") else None
    if not claim or not claim["what"].startswith("world/"):
        return None
    return {"verb": claim["verb"], "what": claim["what"], "arguments": claim["args"],
            "result": result, "state_sequence": STORE.state()[0]}


async def run_imagination(run_id: str) -> None:
    try:
        retry_feedback: str | None = None
        failures = 0
        while True:
            run = STORE.imagination_run(run_id)
            if not run or run["status"] != "running" or run["completed_steps"] >= run["max_steps"]:
                break
            step = run["completed_steps"] + 1
            context = imagination_context(run["conversation_id"], run["seed"], step, retry_feedback)
            prompt = context["conversation"][-1]["content"]
            turn = STORE.begin_turn(run["conversation_id"], prompt, context)
            STORE.link_imagination_turn(run_id, turn["id"], "autonomous", step)
            STORE.imagination_step_started(run_id, turn["id"])
            succeeded, failure = await run_turn(turn, context, run_id)
            finished_turn = STORE.turn(turn["id"])
            patch = graph_patch_for_turn(turn["id"]) if succeeded else None
            if not succeeded or not finished_turn or finished_turn["status"] != "complete" or patch is None:
                failures += 1
                if failures < 2 and STORE.imagination_run(run_id)["status"] == "running":
                    receipt = finished_turn.get("receipt") if finished_turn else None
                    retry_feedback = failure or (receipt or {}).get("rationale") or "no world mutation committed"
                    await HUB.emit(run_id, "imagination.step.retrying", {"turn_id": turn["id"], "reason": retry_feedback})
                    continue
                updated = STORE.imagination_step_finished(run_id, True)
                await HUB.emit(run_id, "imagination.step.completed", {"step": updated["completed_steps"], "turn_id": turn["id"], "status": updated["status"], "graph_patch": None})
                break
            failures, retry_feedback = 0, None
            updated = STORE.imagination_step_finished(run_id, False)
            await HUB.emit(run_id, "imagination.step.completed", {
                "step": updated["completed_steps"], "turn_id": turn["id"],
                "status": updated["status"], "graph_patch": patch,
            })
            if updated["status"] != "running":
                break
        final = STORE.imagination_run(run_id)
        if final:
            terminal = ("imagination.run.completed" if final["status"] == "complete" else
                        "imagination.run.cancelled" if final["status"] == "cancelled" else
                        "imagination.run.failed" if final["status"] == "failed" else
                        "imagination.run.paused")
            await HUB.emit(run_id, terminal, {"run": {k: v for k, v in final.items() if k != "conversation"}})
    except Exception as exc:
        STORE.set_imagination_status(run_id, "failed")
        await HUB.emit(run_id, "imagination.run.failed", {"error_code": type(exc).__name__})
    finally:
        IMAGINATION_TASKS.pop(run_id, None)


def start_imagination_task(run_id: str) -> None:
    task = IMAGINATION_TASKS.get(run_id)
    if not task or task.done():
        IMAGINATION_TASKS[run_id] = asyncio.create_task(run_imagination(run_id))


@app.get("/api/imagination/runs")
def imagination_runs():
    return STORE.imagination_runs()


@app.post("/api/imagination/runs", status_code=202)
async def create_imagination_run(body: ImaginationRunRequest):
    seed = body.seed.strip()
    if not seed:
        raise HTTPException(422, "Imagination needs an intention")
    run = STORE.create_imagination_run(seed, body.max_steps, body.auto_start)
    if body.auto_start:
        start_imagination_task(run["id"])
    return {**{k: v for k, v in run.items() if k != "conversation"},
            "stream_url": f"/api/imagination/runs/{run['id']}/stream"}


@app.get("/api/imagination/runs/{run_id}")
def imagination_run(run_id: str):
    run = STORE.imagination_run(run_id)
    if not run:
        raise HTTPException(404, "Imagination run not found")
    return run


@app.get("/api/imagination/runs/{run_id}/stream")
async def imagination_stream(run_id: str, request: Request):
    if not STORE.imagination_run(run_id):
        raise HTTPException(404, "Imagination run not found")
    try:
        after = int(request.headers.get("last-event-id", "0"))
    except ValueError:
        after = 0
    return StreamingResponse(HUB.stream(run_id, after), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/imagination/runs/{run_id}/pause")
def pause_imagination(run_id: str):
    run = STORE.set_imagination_status(run_id, "paused")
    if not run:
        raise HTTPException(404, "Imagination run not found")
    return run


@app.post("/api/imagination/runs/{run_id}/resume", status_code=202)
async def resume_imagination(run_id: str):
    run = STORE.imagination_run(run_id)
    if not run:
        raise HTTPException(404, "Imagination run not found")
    if run["completed_steps"] >= run["max_steps"]:
        raise HTTPException(409, "Imagination run is already complete")
    STORE.set_imagination_status(run_id, "running")
    HUB.terminal.discard(run_id)
    start_imagination_task(run_id)
    return STORE.imagination_run(run_id)


@app.post("/api/imagination/runs/{run_id}/start", status_code=202)
async def start_imagination_batch(run_id: str, body: ImaginationBatchRequest):
    run = STORE.imagination_run(run_id)
    if not run:
        raise HTTPException(404, "Imagination run not found")
    if run["status"] == "running":
        raise HTTPException(409, "Imagination is already running")
    if run["conversation"].get("active_turn"):
        raise HTTPException(409, "Halcyon is still responding")
    updated = STORE.start_imagination_batch(run_id, body.turns)
    HUB.terminal.discard(run_id)
    start_imagination_task(run_id)
    return updated


@app.post("/api/imagination/runs/{run_id}/messages", status_code=202)
async def imagination_chat(run_id: str, body: ImaginationChatRequest):
    run = STORE.imagination_run(run_id)
    if not run:
        raise HTTPException(404, "Imagination run not found")
    if run["status"] == "running":
        raise HTTPException(409, "Pause imagination before talking with Halcyon")
    content = body.content.strip()
    if not content:
        raise HTTPException(422, "Message is empty")
    context = world_dialogue_context(run["conversation_id"], content)
    try:
        turn = STORE.begin_turn(run["conversation_id"], content, context)
    except ConversationBusy as exc:
        raise HTTPException(409, detail={"code": "conversation_busy", "turn_id": exc.turn_id}) from exc
    STORE.link_imagination_turn(run_id, turn["id"], "chat")
    HUB.terminal.discard(run_id)
    asyncio.create_task(run_turn(turn, context, run_id, "chat"))
    return {"turn_id": turn["id"], "run_id": run_id,
            "stream_url": f"/api/imagination/runs/{run_id}/stream"}


@app.post("/api/imagination/runs/{run_id}/stop")
def stop_imagination(run_id: str):
    run = STORE.set_imagination_status(run_id, "cancelled")
    if not run:
        raise HTTPException(404, "Imagination run not found")
    return run


@app.get("/api/health")
def health():
    sequence, _ = STORE.state()
    return {"status": "ok", "model": LM_MODEL, "model_api": LM_API, "state_sequence": sequence}


@app.get("/api/conversations")
def conversations():
    return STORE.conversations()


@app.get("/api/conversations/{conversation_id}")
def conversation(conversation_id: str):
    data = STORE.conversation(conversation_id)
    if not data:
        raise HTTPException(404, "Conversation not found")
    return data


@app.post("/api/conversations/{conversation_id}/character-snapshots", status_code=201)
def append_character_snapshot(conversation_id: str, body: CharacterSnapshotRequest):
    actual_id = None if conversation_id == "new" else conversation_id
    payload = body.model_dump()
    raw = "IRIS_CHARACTER_SNAPSHOT_V1\n" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    groups: dict[str, list[str]] = {}
    for trait in body.traits:
        label = f"{trait.label} (locked)" if trait.locked else trait.label
        groups.setdefault(trait.group, []).append(label)
    display = "Character draft · " + body.title + "\n" + "\n".join(
        f"{group}: {', '.join(labels)}" for group, labels in groups.items()
    )
    try:
        return STORE.append_context_message(actual_id, raw, display, f"Character: {body.title}")
    except ConversationBusy as exc:
        raise HTTPException(409, detail={"code": "conversation_busy", "turn_id": exc.turn_id}) from exc


@app.post("/api/conversations/{conversation_id}/turns", status_code=202)
async def create_turn(conversation_id: str, body: TurnRequest):
    content = body.content.strip()
    if not content:
        raise HTTPException(422, "Message is empty")
    actual_id = None if conversation_id == "new" else conversation_id
    context = model_context(actual_id, content)
    usage = usage_for_context(context)
    if usage["input_tokens"] > CONTEXT_LIMIT:
        raise HTTPException(413, "Message exceeds the configured context limit")
    try:
        turn = STORE.begin_turn(actual_id, content, context)
    except ConversationBusy as exc:
        raise HTTPException(409, detail={"code": "conversation_busy", "turn_id": exc.turn_id}) from exc
    asyncio.create_task(run_turn(turn, context))
    return {"turn_id": turn["id"], "conversation_id": turn["conversation_id"],
            "status": "generating", "stream_url": f"/api/turns/{turn['id']}/stream"}


@app.get("/api/turns/{turn_id}/stream")
async def stream_turn(turn_id: str, request: Request):
    if not STORE.turn(turn_id):
        raise HTTPException(404, "Turn not found")
    last = request.headers.get("last-event-id", "0")
    try:
        after = int(last)
    except ValueError:
        after = 0
    return StreamingResponse(HUB.stream(turn_id, after), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/turns/{turn_id}")
def get_turn(turn_id: str):
    data = STORE.turn(turn_id)
    if not data:
        raise HTTPException(404, "Turn not found")
    return data


@app.post("/api/turns/{turn_id}/cancel")
async def cancel_turn(turn_id: str):
    data = STORE.turn(turn_id)
    if not data:
        raise HTTPException(404, "Turn not found")
    if data["status"] in {"complete", "failed", "cancelled", "interrupted"}:
        return data
    HUB.cancelled.add(turn_id)
    cancel_event = HUB.cancel_events.get(turn_id)
    if cancel_event:
        cancel_event.set()
    return {"turn_id": turn_id, "status": "cancelling"}


@app.post("/api/tokens/count")
def count_tokens(body: TokenRequest):
    context = model_context(body.conversation_id, body.draft)
    usage = usage_for_context(context)
    draft_tokens = estimate_tokens(body.draft)
    conversation_without_draft = max(0, usage["conversation"] - draft_tokens)
    return {"instructions": usage["instructions"], "knowledge": usage["knowledge"],
            "conversation": conversation_without_draft, "draft": draft_tokens,
            "total": usage["input_tokens"], "context_limit": CONTEXT_LIMIT,
            "source": "estimate", "exact": False}


@app.get("/api/turns/{turn_id}/context")
def turn_context(turn_id: str):
    data = STORE.turn_context(turn_id)
    if not data:
        raise HTTPException(404, "Turn context not found")
    return data


@app.get("/api/governance/{kind}")
def governance(kind: str):
    mapping = {"proposals": "proposals", "gate-decisions": "gate_decisions", "receipts": "receipts"}
    if kind not in mapping:
        raise HTTPException(404, "Governance view not found")
    return STORE.governance(mapping[kind])


@app.get("/api/boundary/attestation")
def attestation():
    return {**BOUNDARY.attestation(), "hash": BOUNDARY_HASH}


@app.get("/api/world")
def canonical_world():
    """The known/seeded entity graph (real people, places, organizations) Memory projects."""
    sequence, state = STORE.state()
    return {"sequence": sequence, **visible_world(state["world"])}

@app.get("/api/imagination/world")
def imagination_world():
    """The separate, fictional world graph Imagination's NOMINATE verbs actually write to."""
    sequence, state = STORE.state()
    return {"sequence": sequence, **visible_world(state["imagination_world"])}

@app.get("/api/imagination/packs")
def imagination_packs():
    return IMAGINATION_PACKS.list_packs()

@app.get("/api/imagination/packs/{pack}")
def imagination_pack(pack: str):
    try:
        return IMAGINATION_PACKS.pack(pack)
    except PackNotFound as exc:
        raise HTTPException(404, "Imagination pack not found") from exc

@app.get("/api/imagination/doctrine")
def imagination_doctrine(pack: str = "villain", lens: str | None = None,
                          q: str = "", selected: str = "", limit: int = 120,
                          token_budget: int = 4000):
    selected_ids = [item.strip() for item in selected.split(",") if item.strip()]
    try:
        return IMAGINATION_PACKS.project(
            pack, lens=lens, query=q, selected=selected_ids,
            limit=max(1, min(limit, 500)), token_budget=max(250, min(token_budget, 16000)),
        )
    except PackNotFound as exc:
        raise HTTPException(404, "Imagination pack not found") from exc
    except LensNotFound as exc:
        raise HTTPException(404, "Imagination lens not found") from exc
    except KeyError as exc:
        raise HTTPException(404, "Doctrine primitive not found") from exc

@app.get("/api/imagination/doctrine/nodes/{node_id:path}")
def imagination_doctrine_node(node_id: str, pack: str = "villain"):
    try:
        return IMAGINATION_PACKS.node(pack, node_id)
    except PackNotFound as exc:
        raise HTTPException(404, "Imagination pack not found") from exc
    except KeyError as exc:
        raise HTTPException(404, "Doctrine primitive not found") from exc

def _validate_blueprint_doctrine(pack: str, blueprint: dict) -> dict:
    try:
        pack_detail = IMAGINATION_PACKS.pack(pack)
        if blueprint.get("lens_id"):
            IMAGINATION_PACKS.project(pack, lens=blueprint["lens_id"], limit=1, token_budget=250)
        references = [item.get("primitive") for item in blueprint.get("ingredients", [])]
        references.extend(node for tension in blueprint.get("tensions", []) for node in tension.get("between", []))
        references.extend(item.get("primitive") for item in blueprint.get("rejected_suggestions", []))
        for node_id in {item for item in references if item}:
            IMAGINATION_PACKS.node(pack, node_id)
    except PackNotFound as exc:
        raise HTTPException(404, "Imagination pack not found") from exc
    except LensNotFound as exc:
        raise HTTPException(404, "Imagination lens not found") from exc
    except KeyError as exc:
        raise HTTPException(422, f"Unknown doctrine primitive: {exc.args[0]}") from exc
    try:
        validate_blueprint(blueprint)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return pack_detail

@app.get("/api/imagination/blueprints")
def imagination_blueprints(status: str | None = None):
    if status and status not in {"draft", "candidate", "admitted", "rejected"}:
        raise HTTPException(422, "Invalid blueprint status")
    return STORE.blueprints(status)

@app.post("/api/imagination/blueprints", status_code=201)
def create_imagination_blueprint(body: BlueprintCreateRequest):
    content = {"ingredients": body.ingredients, "tensions": body.tensions,
               "rejected_suggestions": body.rejected_suggestions,
               "open_questions": body.open_questions, "draft_entities": body.draft_entities,
               "draft_edges": body.draft_edges, "id": "blueprint:pending", "status": "draft",
               "lens_id": body.lens_id}
    pack = _validate_blueprint_doctrine(body.pack, content)
    return STORE.create_blueprint(
        body.title.strip() or "Untitled blueprint", body.artifact_type.strip() or "artifact",
        pack["id"], pack["version"], body.lens_id, body.initiating_pressure_id,
        {key: value for key, value in content.items() if key not in {"id", "status", "lens_id"}},
    )

@app.get("/api/imagination/blueprints/{blueprint_id}")
def imagination_blueprint(blueprint_id: str):
    item = STORE.blueprint(blueprint_id)
    if not item:
        raise HTTPException(404, "Blueprint not found")
    return item

@app.patch("/api/imagination/blueprints/{blueprint_id}")
def update_imagination_blueprint(blueprint_id: str, body: BlueprintUpdateRequest):
    current = STORE.blueprint(blueprint_id)
    if not current:
        raise HTTPException(404, "Blueprint not found")
    if body.actor not in {"user", "halcyon", "system"}:
        raise HTTPException(422, "Invalid blueprint actor")
    status = body.patch.get("status", current["status"])
    if status not in {"draft", "candidate", "rejected"}:
        raise HTTPException(422, "Blueprint admission is not available yet")
    candidate = {**current, **body.patch, "status": status}
    pack_slug = current["pack_id"].removeprefix("imagination-pack:")
    _validate_blueprint_doctrine(pack_slug, candidate)
    try:
        return STORE.update_blueprint(blueprint_id, body.expected_revision, body.patch,
                                      actor=body.actor, reason=body.reason)
    except BlueprintConflict as exc:
        raise HTTPException(409, {"error": "blueprint_revision_conflict",
                                  "current_revision": exc.revision}) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.post("/api/imagination/blueprints/{blueprint_id}/compose")
def compose_imagination_blueprint(blueprint_id: str, body: BlueprintComposeRequest):
    current = STORE.blueprint(blueprint_id)
    if not current:
        raise HTTPException(404, "Blueprint not found")
    if current["status"] == "rejected":
        raise HTTPException(422, "Rejected blueprint cannot be composed")
    try:
        candidate = compose_blueprint(IMAGINATION_PACKS, current)
        return STORE.update_blueprint(
            blueprint_id, body.expected_revision,
            {"status": "candidate", "candidate": candidate,
             "draft_entities": candidate["entities"], "draft_edges": candidate["edges"]},
            actor="system", reason="composed deterministic artifact candidate",
        )
    except BlueprintConflict as exc:
        raise HTTPException(409, {"error": "blueprint_revision_conflict",
                                  "current_revision": exc.revision}) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc

@app.post("/api/imagination/blueprints/{blueprint_id}/admit", status_code=201)
def admit_imagination_blueprint(blueprint_id: str, body: BlueprintAdmitRequest):
    current = STORE.blueprint(blueprint_id)
    if current and current.get("artifact_type") == "trait_bundle":
        raise HTTPException(422, "Trait bundles are reusable ingredients, not World entities")
    try:
        return STORE.admit_blueprint(blueprint_id, body.expected_revision, body.candidate_hash)
    except KeyError as exc:
        raise HTTPException(404, "Blueprint not found") from exc
    except BlueprintConflict as exc:
        raise HTTPException(409, {"error": "blueprint_revision_conflict",
                                  "current_revision": exc.revision}) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get("/api/imagination/admissions/{admission_id}")
def imagination_admission(admission_id: str):
    item = STORE.imagination_admission(admission_id)
    if not item:
        raise HTTPException(404, "Imagination admission not found")
    return item

@app.get("/api/imagination/pressures")
def imagination_pressures(status: str | None = None):
    if status and status not in {"open", "exploring", "resolved", "retained"}:
        raise HTTPException(422, "Invalid world-pressure status")
    return STORE.world_pressures(status)

@app.get("/api/imagination/pressures/{pressure_id}")
def imagination_pressure(pressure_id: str):
    item = STORE.world_pressure(pressure_id)
    if not item:
        raise HTTPException(404, "World pressure not found")
    return item

@app.post("/api/imagination/pressures/{pressure_id}/explore", status_code=201)
def explore_imagination_pressure(pressure_id: str, body: PressureExploreRequest):
    try:
        pack = IMAGINATION_PACKS.pack(body.pack)
        if body.lens_id:
            IMAGINATION_PACKS.project(body.pack, lens=body.lens_id, limit=1, token_budget=250)
        return STORE.explore_world_pressure(
            pressure_id, body.title.strip() or "Untitled pressure",
            body.artifact_type.strip() or "artifact", pack["id"], pack["version"], body.lens_id,
        )
    except PackNotFound as exc:
        raise HTTPException(404, "Imagination pack not found") from exc
    except LensNotFound as exc:
        raise HTTPException(404, "Imagination lens not found") from exc
    except KeyError as exc:
        raise HTTPException(404, "World pressure not found") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get("/api/system/projection")
def get_system_projection():
    return system_projection()

@app.get("/api/self/claims")
def get_self_claims():
    return {"version": STORE.versions().get("self", 0), "claims": STORE.self_claims()}

@app.post("/api/self/claims", status_code=201)
def create_self_claim(body: SelfClaimRequest):
    try:
        return STORE.add_self_claim(body.kind, body.subject, body.predicate, body.value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get("/api/capabilities")
def get_capabilities():
    return {"version": STORE.versions().get("capabilities", 0), "items": STORE.capabilities()}

@app.get("/api/system/roles")
def get_available_roles():
    return list_packs(IDENTITY_PACKS_DIR)

@app.get("/api/system/roles/{role_id}")
def get_role_detail(role_id: str):
    path = IDENTITY_PACKS_DIR / f"{role_id}.json"
    if not path.exists():
        raise HTTPException(404, "Role pack not found")
    return load_pack(path)

@app.post("/api/capabilities/mcp", status_code=201)
def register_mcp(body: McpCapabilityRequest):
    try:
        return STORE.register_mcp_capability(body.tool_id, body.server, body.description,
                                             body.schema_definition, body.effect_class)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get("/api/tools/receipts")
def get_tool_receipts():
    return STORE.tool_receipts()

@app.post("/api/tools/execute")
def execute_tool(body: ToolExecuteRequest):
    capability = STORE.capability(body.tool_id)
    context = STORE.active_context()
    checks = []
    if capability is None:
        checks.append(["registration", "DENY", "tool is not registered locally"])
        receipt = STORE.record_tool_receipt(tool_id=body.tool_id, source="unknown", effect_class="unknown",
                                            raw_args=body.arguments, normalized_args=None, context=context,
                                            decision="DENY", checks=checks, execution_status="not_attempted")
        raise HTTPException(403, detail={"message": "Tool denied", "receipt_id": receipt["id"]})
    checks.append(["registration", "PASS", "tool is registered locally"])
    if not capability["available"]:
        checks.append(["availability", "DENY", "executor is not connected"])
        receipt = STORE.record_tool_receipt(tool_id=body.tool_id, source=capability["source"],
                                            effect_class=capability["effect_class"], raw_args=body.arguments,
                                            normalized_args=None, context=context, decision="DENY", checks=checks,
                                            execution_status="not_attempted")
        raise HTTPException(403, detail={"message": "Tool unavailable", "receipt_id": receipt["id"]})
    checks.append(["availability", "PASS", "executor is available"])
    if capability["effect_class"] != "observe":
        checks.append(["effect", "DENY", "V1 permits observe effects only"])
        receipt = STORE.record_tool_receipt(tool_id=body.tool_id, source=capability["source"], effect_class=capability["effect_class"],
                                            raw_args=body.arguments, normalized_args=None, context=context,
                                            decision="DENY", checks=checks, execution_status="not_attempted")
        raise HTTPException(403, detail={"message": "Effect denied", "receipt_id": receipt["id"]})
    checks.append(["effect", "PASS", "observe effect permitted"])
    required = {key for key, rule in capability["schema"].items() if rule.get("required")}
    if not required.issubset(body.arguments) or any(key not in capability["schema"] for key in body.arguments):
        checks.append(["arguments", "DENY", "arguments do not match the local schema"])
        receipt = STORE.record_tool_receipt(tool_id=body.tool_id, source=capability["source"], effect_class="observe",
                                            raw_args=body.arguments, normalized_args=None, context=context,
                                            decision="DENY", checks=checks, execution_status="not_attempted")
        raise HTTPException(422, detail={"message": "Arguments denied", "receipt_id": receipt["id"]})
    checks.append(["arguments", "PASS", "arguments match the local schema"])
    if body.tool_id == "system.inspect":
        result = system_projection()
    elif body.tool_id == "affect.inspect":
        result = STORE.effective_affect()
    elif body.tool_id == "memory.search":
        query = str(body.arguments["query"]).lower()
        result = [item for item in STORE.memory_entries() if query in item["content"].lower()][:20]
    elif body.tool_id in {"graph.inspect", "graph.neighbors", "graph.search"}:
        graph = ProjectionService(STORE, IDENTITY_PACKS_DIR).authorized_graph()
        nodes = graph["nodes"]
        if body.tool_id == "graph.inspect":
            result = nodes.get(str(body.arguments["node_id"]))
            if result is None:
                raise HTTPException(404, "Authorized graph node not found")
        elif body.tool_id == "graph.search":
            terms = {term.lower() for term in re.findall(r"[a-z0-9_-]+", str(body.arguments["query"]), re.I) if len(term) > 2}
            domains = set(body.arguments.get("domains") or [])
            limit = min(25, max(1, int(body.arguments.get("limit", 10))))
            matches = []
            for node in nodes.values():
                if domains and node["owner"] not in domains:
                    continue
                haystack = f"{node['label']} {node['content']}".lower()
                score = sum(1 for term in terms if term in haystack)
                if score:
                    matches.append((score, node))
            result = [node for _, node in sorted(matches, key=lambda item: (-item[0], item[1]["id"]))[:limit]]
        else:
            node_id = str(body.arguments["node_id"])
            allowed_edges = set(body.arguments.get("edges") or [])
            limit = min(25, max(1, int(body.arguments.get("limit", 12))))
            depth = min(2, max(1, int(body.arguments.get("depth", 1))))
            matches, seen, frontier = [], {node_id}, [(node_id, 0)]
            while frontier and len(matches) < limit:
                current, current_depth = frontier.pop(0)
                if current_depth >= depth:
                    continue
                for edge in graph["edges"]:
                    if allowed_edges and edge["relation"] not in allowed_edges:
                        continue
                    target = edge["target"] if edge["source"] == current else edge["source"] if edge["target"] == current else None
                    if not target or target in seen or target not in nodes:
                        continue
                    seen.add(target)
                    matches.append({"depth": current_depth + 1, "edge": edge, "node": nodes[target]})
                    frontier.append((target, current_depth + 1))
                    if len(matches) >= limit:
                        break
            result = matches
    else:
        result = None
    checks.append(["execute", "OK", "built-in executor returned an observation"])
    receipt = STORE.record_tool_receipt(tool_id=body.tool_id, source=capability["source"], effect_class="observe",
                                        raw_args=body.arguments, normalized_args=body.arguments, context=context,
                                        decision="ACCEPT", checks=checks, execution_status="succeeded", result=result)
    return {"observation": result, "receipt_id": receipt["id"], "remembered": False}


@app.post("/api/projections/preview")
def preview_projection(body: ProjectionPreviewRequest):
    return ProjectionService(STORE, IDENTITY_PACKS_DIR).build(
        body.message, include_known_world=body.include_known_world,
        include_imagination_world=body.include_imagination_world,
        token_budget=body.token_budget, max_nodes=body.max_nodes,
        max_depth=body.max_depth,
    )


@app.get("/api/projections/{projection_id}")
def get_prompt_projection(projection_id: str):
    projection = STORE.prompt_projection(projection_id)
    if projection is None:
        raise HTTPException(404, "Prompt projection not found")
    return projection


@app.get("/api/projections")
def get_prompt_projections(conversation_id: str | None = None, limit: int = 50):
    return STORE.prompt_projections(conversation_id, limit)


@app.get("/api/memory/self")
def self_memory():
    sequence, state = STORE.state()
    return {"sequence": sequence, **state["self"]}

@app.get("/api/context/active")
def active_context():
    return STORE.active_context()

@app.put("/api/context/active")
def update_active_context(body: ActiveContextRequest):
    known = {pack["id"] for pack in list_packs(IDENTITY_PACKS_DIR)}
    unknown = [role for role in body.roles if role not in known]
    if unknown:
        raise HTTPException(422, f"unknown role id(s): {', '.join(unknown)}")
    return STORE.set_active_context(body.world, body.task, body.skills, body.roles)

@app.get("/api/memory/entries")
def memory_entries(channel: str | None = None):
    channels = None if not channel or channel == "all" else [channel]
    return {"context": STORE.active_context(), "entries": STORE.memory_entries(channels)}

@app.post("/api/memory/entries", status_code=201)
def create_memory_entry(body: MemoryEntryRequest):
    try:
        return STORE.add_memory_entry(scope=body.scope, channel=body.channel, content=body.content,
                                      origin=body.origin, source_event_id=body.source_event_id,
                                      derived_from=body.derived_from)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get("/api/memory/timeline")
def memory_timeline():
    entries = STORE.memory_entries()
    events = [{"id": item["id"], "kind": item["channel"], "content": item["content"],
               "scope": item["scope"], "created_at": item["created_at"]} for item in entries]
    for item in STORE.effective_affect()["history"]:
        events.append({"id": item["id"], "kind": "affect", "content": "Affect changed",
                       "scope": "global", "created_at": item["created_at"], "delta": item["delta"]})
    return sorted(events, key=lambda item: item["created_at"], reverse=True)

@app.get("/api/affect")
def affect():
    return STORE.effective_affect()

@app.post("/api/affect/transitions", status_code=201)
def affect_transition(body: AffectTransitionRequest):
    try:
        return STORE.apply_affect(body.source_event_id, body.deltas)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _node_detail(world: dict, node_name: str, sequence: int, not_found: str,
                 include_lore: bool = False) -> dict:
    node = world["nodes"].get(node_name)
    if node is None:
        raise HTTPException(404, not_found)
    def decorate(edge):
        return {**edge, "source_label": world["nodes"][edge["source"]]["label"],
                "target_label": world["nodes"][edge["target"]]["label"]}
    incoming = [decorate(edge) for edge in world["edges"] if edge["target"] == node_name]
    outgoing = [decorate(edge) for edge in world["edges"] if edge["source"] == node_name]
    constraints = [rule for rule in world["constraints"] if rule["target"] == node_name]
    aliases = [world["nodes"][edge["target"]]["label"] for edge in outgoing if edge["relation"] == "known as"]
    provenance = STORE.node_provenance(node["label"])
    admission = STORE.imagination_admission(node.get("properties", {}).get("admission_id", ""))
    origin = None
    if provenance:
        turn = STORE.turn(provenance["turn_id"])
        message = (turn or {}).get("assistant_message") or {}
        receipt = (turn or {}).get("receipt") or {}
        origin = {
            "turn_id": provenance["turn_id"], "conversation_id": provenance.get("conversation_id"),
            "ordinal": provenance.get("ordinal"), "state_sequence": provenance["state_sequence_after"],
            "reflection": message.get("display_content", ""),
            "mutation": {"verb": provenance["verb"], "what": provenance["what_path"],
                         "arguments": json.loads(provenance["args_json"]),
                         "result": json.loads(provenance["result_json"]) if provenance.get("result_json") else None},
            "receipt": {"id": provenance.get("receipt_id"), "decision": receipt.get("decision"),
                        "outcome": receipt.get("outcome")},
            "created_at": provenance["created_at"],
        }
    detail = {"id": node_name, "name": node["label"], "type": node["type"], "properties": node.get("properties", {}),
            "sources": node.get("sources", []),
            "source_details": [world.get("sources", {}).get(source, {"title": source}) for source in node.get("sources", [])],
            "aliases": aliases,
            "incoming": incoming, "outgoing": outgoing, "constraints": constraints,
            "sequence": sequence, "provenance": provenance, "origin": origin,
            "admission": admission}
    if include_lore:
        detail["lore"] = STORE.imagination_lore(node_name)
    return detail


@app.get("/api/memory/nodes/{node_name:path}")
def memory_node(node_name: str):
    sequence, state = STORE.state()
    world = visible_world(state["world"])
    return _node_detail(world, node_name, sequence, "Memory node not found")


@app.get("/api/imagination/nodes/{node_name:path}")
def imagination_node(node_name: str):
    sequence, state = STORE.state()
    world = visible_world(state["imagination_world"])
    return _node_detail(world, node_name, sequence, "World entity not found", include_lore=True)
