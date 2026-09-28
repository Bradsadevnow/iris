# Halcyon / Iris

Halcyon is a persistent, inspectable agent system built around one rule:

> Language may propose effects. Only an owning boundary may authorize and commit them.

The model is intentionally nondeterministic. The state transition is not. Conversations,
reasoning artifacts, proposals, gate decisions, mutations, Affect transitions, and tool attempts
leave durable records that can be inspected independently of what the model says happened.

Iris is the current repository and runtime. Halcyon is the identity presented by that runtime.
This is an experimental system, not a production security boundary.

## What exists now

The repository contains a working FastAPI and React application with:

- Streaming, persistent chat against Anthropic-compatible or OpenAI-compatible model servers.
- Expandable endpoint-provided thinking and captured per-turn context.
- Projected token counts before sending and provider usage when available.
- SQLite/WAL transactions for turn finalization and admitted state changes.
- A deny-by-default nomination gate with proposals, decisions, receipts, and mutation records.
- Three scoped Memory channels: experience, cognitive meaning, and emotional meaning.
- An independently owned eight-dimensional Affect vector and transition history.
- Canonical Self claims and a composed, non-writable System Identity projection.
- Active World, Task, and Skill retrieval scopes.
- Built-in read-only capabilities plus a local authorization registry for MCP declarations.
- A Self-centered, owner-preserving knowledge projection that ranks and token-budgets relevant
  Self, Memory, role, world, and capability nodes for each turn.
- A separated response pipeline: canonical Self, task context, reasoning role, supplied knowledge,
  governed draft, then a final expression-only rendering pass.
- Per-turn context manifests distinguishing eligible, supplied, omitted, and tool-retrieved Memory,
  plus persisted expression inputs, fidelity results, and fallback receipts.
- Bounded read-only graph inspection, search, and neighbor traversal with tool receipts.
- An Imagination workspace with world-aware chat, streamed autonomous turns, a batch counter,
  pause/stop controls, and a live entity graph.
- Memory, Self, Capabilities, Tool receipts, Proposals, Gate decisions, Receipts, and Boundary UI.

## System shape

Halcyon is a projection of independently owned systems:

```text
Self + Memory + Affect + Context + Capabilities + Governance
                              |
                              v
                    System Identity projection
                              |
                              v
                         Language / UI
```

Language owns no canonical state. Each state owner is intended to be writable only through its
own boundary. The System Identity view composes current projections and their version vector; it
is not another state store.

### State owners

| Owner | Owns | Does not own |
|---|---|---|
| Self | Durable identity claims, values, commitments, preferences, relationships, goals | Current emotion, active task, external facts |
| Memory | Experiences, cognitive meanings, emotional meanings, scopes, sources, derivation | Current Affect |
| Affect | Current eight-value vector, baselines, movement limits, transition history | Semantic interpretation of emotion |
| Context | Active World, Task, and Skill scopes used for retrieval | The records inside those scopes |
| Capabilities | Tool declarations, schemas, effect classes, availability, limits | Permission inferred from remote descriptions |
| Governance | Proposals, decisions, receipts, mutations, boundary versions | Model-authored claims about execution |

The Affect dimensions are `joy`, `sadness`, `fear`, `anger`, `trust`, `disgust`, `surprise`,
and `anticipation`. Ordinary turns receive the current vector and may propose one complete next
vector. The Affect boundary checks completeness, finite values, the `1–100` range, and maximum
movement. It does not manufacture cognitive or emotional-semantic memories during the turn.

## Chat and atomic finalization

A normal server turn has four phases:

```text
begin transaction      grounded model pass      expression model pass      finalization transaction
-----------------      -------------------      ---------------------      ------------------------
message + context -->  claims + uncertainty --> visible voice only -----> gate + Affect checks
turn = generating      NOMINATE/AFFECT          no control authority       assistant + evidence
                       no canonical effects      cannot authorize effects   admitted state changes
                                                                            turn = complete
```

The server never holds a database transaction open while waiting for either model pass. The
grounded draft is authoritative for nominations, Affect, and gate adjudication but is not shown
directly. The expression pass receives only its visible prose plus the final voice/style profile;
it cannot authorize effects. Its validated output becomes `display_content`, while the grounded
draft remains `raw_content`. For admitted changes, the assistant message, receipts, mutations,
canonical state, and Affect transition commit atomically. A state version conflict retries
adjudication against the new authoritative state once.

One conversation may have only one active turn. Interrupted generations are never adjudicated.

The model proposes effects using one literal standalone line:

```text
NOMINATE what=<path> verb=<verb> args=<key:value; key:value>
```

The initial world vocabulary is `create`, `relate`, `constrain`, `occur`, and `name`.
The legacy `remember` verb writes the old `self/memory/*` collection. Canonical Self claims now
have their own state owner and API; these two concepts should not be treated as equivalent.

## Imagination workspace

Imagination is a persistent world session, not a disposable generation job.

- The left side contains a conversation with Halcyon about the current imagined world.
- A chat response may nominate one world change, but ordinary discussion does not require one.
- **Rip** runs the requested number of additional autonomous world-building turns.
- Chat turns and autonomous turns share one conversation, the canonical imagined-world graph, and
  the same gate and transaction machinery.
- An autonomous counter advances only after a world mutation commits. A malformed or denied
  attempt receives one governed retry before the run fails.
- Each committed step refreshes the right-hand graph and focuses the changed entity when possible.

Each imagined entity also has a first-class Markdown lore document. A newly admitted world
mutation creates lore for every entity it touches; later admitted mutations append a versioned
development entry in the same database transaction as the graph change. Lore is forward-only:
existing entities are not backfilled from old chat. Their original assistant reflection remains
visible as labeled provenance, but is not silently promoted into canonical lore. The entity
dossier opens on **Lore**, with separate **Graph** and **History** views.

### Important graph distinction

There are three canonical graphs/dicts in `canonical_state`, and they are never mixed:

1. **Imagined world graph** (`canonical_state.imagination_world_json`, `state["imagination_world"]`)
   — fictional entities, places, events, relations, aliases, and constraints created by
   Imagination's `create`/`relate`/`constrain`/`occur`/`name` verbs. Served at `/api/imagination/world`
   and `/api/imagination/nodes/{id}`, rendered by `ImaginationWorldGraph.tsx`. Starts empty.
2. **Known/seeded entity graph** (`canonical_state.world_json`, `state["world"]`) — real people,
   places, and organizations imported by `iris/profile_seed.py` (e.g. the user's own biography).
   Served at `/api/world` and `/api/memory/nodes/{id}`, and is what Memory's graph projects onto
   (augmented with scope/semantic-memory nodes via `braidProjection` in `MemoryView.tsx`).
3. **Memory graph** — experiences and cognitive/emotional meanings connected by scope, derivation,
   provenance, and retrieval relationships, projected over graph (2) above.

This used to be a single shared `world_json`, which meant seeded biography and Imagination's
fictional entities lived in the same store — Imagination would render (and could nominate changes
onto) the user's real biography. `iris/tools.py`'s imagination verbs now write to
`imagination_world_json` exclusively; `world_json` is only ever written by profile import. The
UI keeps the same separation: `ImaginationWorldGraph.tsx` and `MemoryView.tsx`'s `MemoryGraph` are
two distinct components using world-native vs. memory-native copy, sharing only the domain-neutral
`GraphCanvas.tsx` primitive (Sigma lifecycle, layout, camera, selection highlighting).

`model_context()` in `iris/server.py` presents both worlds to ordinary chat (so Halcyon can read
and nominate imagined-world changes in any conversation, not only inside the Imagination view,
labeled `WHAT YOU KNOW` vs `THE WORLD YOU ARE IMAGINING`), but Imagination-specific contexts
(`imagination_context`, `world_dialogue_context`) omit `WHAT YOU KNOW` and the `experience`/
`cognitive_semantic` Memory channels, so a fictional turn's prompt never mixes in unrelated real
facts. See **Current design questions** below for what is still open (multiple named worlds,
world history/replay, and whether an imagined-world session should ever write a summary back to
autobiographical Memory).

## Memory and retrieval

Memory records have a channel and scope:

- `experience`
- `cognitive_semantic`
- `emotional_semantic`

Global scope is always active. The current World, Task, and Skill scopes determine which records
are retrieved into model context. Captured turn context stores the exact retrieved Memory records,
Affect input, active scopes, composed System projection, instructions, knowledge projection, and
conversation supplied to the model.

The Memory UI provides Graph, Explorer, Timeline, and Affect lenses. Its graph is a projection for
inspection, not an additional canonical store.

## Dynamic knowledge projection

Before a model turn, `iris/projection.py` builds a read-only federated graph centered on Halcyon.
The graph connects canonical Self claims to currently reachable Memory, active context, task roles,
known-world and imagined-world entities, and registered capabilities without transferring
ownership of those records to Self.

Prompt construction now keeps these stages explicit:

1. **Canonical Self** — stable identity, values, commitments, relationships, and goals.
2. **Task context** — active World, Task, and Skill scopes.
3. **Active reasoning role** — explicit roles plus at most one deterministically inferred task
   stance. Users may manually compose multiple explicit profiles; they participate as peer lenses.
   The inferred profile is ephemeral support and cannot override explicit profiles. Profiles compile
   into attributable attention, principles, methods, traversal preferences, and expression guidance;
   they do not rename or replace Halcyon.
4. **Supplied knowledge** — selected Memory, known-world, or fictional nodes with owner and
   epistemic status preserved.
5. **Expansion handles** — receipts for omitted adjacent nodes, never retrieval results.
6. **Registered capabilities** — declarations only. They are not callable by the model unless a
   bound tool definition and subsequent tool result are present.
7. **Governed control state** — current Affect needed by the hidden transition protocol; it is not
   persona or knowledge.
8. **Grounded draft** — determines factual substance, uncertainty, proposals, and Affect output.
9. **Expression** — runs last and renders visible prose from the grounded draft using Halcyon's
   voice, role-specific presentation preference, and current affective color.

The expression profile is deliberately excluded from knowledge selection. Expression may change
tone, pacing, vocabulary, and layout, but is instructed not to add claims, simulate tool use,
strengthen confidence, or change availability boundaries. Control lines emitted by an expression
pass are rejected and the grounded visible prose is used instead.

Every started turn persists its projection receipt: selected nodes and edges, selection reasons,
exclusions, token estimates, active strategy, source versions, and rendered context. The built-in
`graph.inspect`, `graph.search`, and `graph.neighbors` can be called through the HTTP capability
boundary and leave ordinary tool receipts. They are not yet bound into the Anthropic/OpenAI model
request. Model-driven traversal during a response is therefore not implemented: the grounded model
currently sees registered capability descriptions and expansion handles, not callable tool schemas.

The current lexical selector is intentionally considered provisional. Audit prompts exposed
over-selection from stop words, single-token matches, broad role vocabulary, capability/knowledge
competition, fictional leakage, and a star-shaped Self graph that makes graph distance weak. The
remediation sequence and acceptance criteria live in
[`docs/CONTEXT_PIPELINE_ROADMAP.md`](docs/CONTEXT_PIPELINE_ROADMAP.md).

The ownership and transaction changes that make Self compression-only, Memory independent,
Affect bounded, and fictional canon Imagination-only are roadmapped in
[`docs/CHAT_STATE_BOUNDARIES_ROADMAP.md`](docs/CHAT_STATE_BOUNDARIES_ROADMAP.md).

## Self and capabilities

Halcyon's canonical identity is seeded from `seeds/halcyon_identity.json`. Self claims are
versioned and visible in the Self page and the right-side Self popout.

Built-in V1 observation capabilities are:

- `system.inspect`
- `memory.search`
- `affect.inspect`
- `graph.inspect`
- `graph.search`
- `graph.neighbors`

Every tool attempt passes through the capability boundary and leaves a tool receipt. Tool success
does not automatically become Memory. MCP capability declarations can be registered, but a remote
description never grants local authority, and disconnected MCP tools are denied.

## Storage

In server mode, SQLite/WAL is authoritative. The default database is `state/iris.db`.

Important durable records include:

- conversations, turns, messages, and captured contexts;
- proposals, gate decisions, receipts, and mutations;
- canonical known-world, imagined-world, and legacy self-memory JSON inside the canonical-state row;
- Memory channel entries and Affect history;
- canonical Self claims and domain versions;
- active retrieval context;
- capability declarations and tool receipts;
- persistent Imagination runs and chat/autonomous turn classifications.

`state/world.json` and `state/self.json` are compatibility projections written after canonical
state transactions. They are not authoritative in the server runtime.

### Legacy CLI warning

`python run.py` and `python run.py --imagine N` still use the earlier JSON-backed `Memory` runtime.
They do **not** use the same full SQLite server path described above. `--server` and
`--seed-profile` use `Store` and SQLite. Until the CLI is migrated or removed, do not run legacy
chat/imagination concurrently with the server against the same `state/` directory.

## Running the application

Requirements:

- Python 3.12 or compatible Python 3 release
- Node.js and npm
- A local or reachable Anthropic-compatible or OpenAI-compatible model endpoint

Create the Python environment and start the API:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py --server
```

Start the UI in another terminal:

```bash
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

The API defaults to `http://127.0.0.1:8000`. The Vite development server proxies `/api` there.

For normal local development, install the repository launcher once and use `hal` from any
terminal. It starts the backend and Vite UI together, restarts a prior Iris session if necessary,
streams both logs, and stops both process groups on Ctrl+C:

```bash
ln -sf "$(pwd)/bin/hal" "$HOME/.local/bin/hal"
hal
```

`hal restart` is equivalent to `hal`; `hal status` reports the tracked processes, and `hal stop`
shuts them down without touching the model server on port 1234.

### Model configuration

| Variable | Purpose | Default |
|---|---|---|
| `IRIS_LM_BASE` | Model server base URL | `http://localhost:1234` |
| `IRIS_LM_MODEL` | Provider model identifier | `google/gemma-4-e4b` |
| `IRIS_LM_API` | `anthropic` or `openai` wire format | `anthropic` |
| `IRIS_LM_API_KEY` | Optional provider credential | empty |
| `IRIS_LM_THINKING` | Request endpoint-supported thinking | `1` |
| `IRIS_CONTEXT_LIMIT` | Context limit used by token projection | `32768` |
| `IRIS_STATE` | State and compatibility-projection directory | `./state` |
| `IRIS_DB` | SQLite database path | `$IRIS_STATE/iris.db` |
| `IRIS_BOUNDARY` | Boundary declaration | `boundary/imagine_and_chat.yaml` |
| `IRIS_PORT` | FastAPI port | `8000` |

Set `IRIS_LM_API=openai` for `/v1/chat/completions`. The default Anthropic-compatible path is
`/v1/messages`.

### Other commands

```bash
.venv/bin/python run.py --attest
.venv/bin/python run.py --show
.venv/bin/python run.py --seed-profile path/to/profile.yaml

cd web
npm run build

cd ..
PYTHONPATH=.:.venv/lib/python3.12/site-packages pytest -q
```

Profile imports are hash-recorded, versioned, idempotent, and applied in one SQLite transaction.
Stop the server before importing into its database.

## Repository map

```text
boundary/imagine_and_chat.yaml  declared nomination vocabulary and limits
iris/kernel.py                  parsing, admission, trial execution, invariants
iris/store.py                   SQLite schema and transactional persistence
iris/server.py                  API, model streaming, chat and Imagination orchestration
iris/graph.py                   current entity/world schema and visibility projection
iris/tools.py                   nomination implementations and invariants
iris/projection.py              Self-centered federation, ranking, traversal, and prompt budgeting
tools/context_pipeline_eval.py  repeated grounded/expression context audit harness (two calls max)
web/src/App.tsx                 application shell and navigation
web/src/ImaginationView.tsx     world dialogue, autonomous batches, live world pane
web/src/MemoryView.tsx          current shared graph renderer and Memory lenses
web/src/SelfSystemView.tsx      Self/System/Capabilities/Tool receipts
docs/CHAT_SPEC.md               chat behavior and atomicity specification
docs/BRAID_UI_SPEC.md           Affect–Memory–Language model
docs/SELF_SYSTEM_TOOLS_SPEC.md  state-owner and capability architecture
docs/CONTEXT_PIPELINE_ROADMAP.md identity/role/retrieval/tool/expression remediation plan
docs/CHAT_STATE_BOUNDARIES_ROADMAP.md chat/Self/Memory/Affect/Imagination ownership roadmap
docs/CONTEXT_BRAID_DESIGN.md     joint Context, Memory, Affect, grounding, and expression contract
```

## Current design questions

These are active architecture decisions, not hidden implementation details:

1. **World versus Memory graph.** Define a first-class imagined-world projection and canvas,
   including world-specific node types, inspectors, temporal events, constraints, and visual
   language. Keep Memory provenance and semantics in a separate projection.
2. **Worlds as state owners.** Decide whether one `imagination_world_json` remains adequate or
   whether each imagined world owns a stable ID, graph, history, status, and boundary.
3. **Memory of imagination.** Resolved for now: Imagination stays fully isolated from
   autobiographical Memory. No automatic summary write-back — if the user wants something from an
   imagined world remembered as an autobiographical fact, that requires an explicit nomination.
4. **Temporal world semantics.** `occur` currently produces graph state, but the UI lacks a real
   timeline, eras, causal ordering, and current-versus-historical world views.
5. **Replay.** The ledger contains enough turn and mutation evidence for substantial inspection,
   but historical state reconstruction and turn replay are not yet first-class UI operations.
6. **Legacy state paths.** Migrate or retire the JSON CLI so all entry points share SQLite and the
   same boundaries.
7. **Self migration.** Retire or explicitly redefine legacy `self/memory/*` now that canonical Self
   claims exist.

## Graph separation roadmap

The goal is to make the Imagination graph a view of its own imagined-world store — not a Memory
view with different data passed into it, and not the same store as the seeded/known-entity graph.
Phases 1–3 below are done; this landed as small, inspectable slices.

> **Imagination sequencing guardrail:** the active trait-constellation work is character-only
> (Who they are, What they're about, Why they're here, What they bring, Flaws). Villain Pack MacGuffins and lairs are
> losslessly reserved for the next **Holdings** pass. Do not reclassify them as character traits,
> discard their fields, or admit a trait bundle as a World entity. Holdings must later preserve
> Artifacts and Strongholds as distinct, independently saved drafts.

### Phase 1 — Separate names, API surfaces, and storage ✅

- `/api/world` is the known/seeded entity graph (`state["world"]`) that Memory projects.
- `/api/imagination/world` is the separate, fictional graph (`state["imagination_world"]`) that
  Imagination's verbs write to — a distinct `canonical_state.imagination_world_json` column, not a
  shared store. `/api/imagination/nodes/{id}` mirrors `/api/memory/nodes/{id}` for that graph.
- `/api/memory/*` stays for Memory channels, retrieval, timelines, and Memory projections.
- No compatibility alias was kept for the old `/api/memory/world` path — the one frontend caller
  migrated in the same change that introduced `/api/world`, so there was nothing left to alias.

**Done when:** no Imagination code imports a component named for Memory or fetches its world through
a Memory URL, **and** an Imagination-created entity cannot appear in, or overwrite, the seeded
known-entity graph, or vice versa. ✅ verified end-to-end (chat/autonomous Imagination turns only
ever mutate `imagination_world_json`; profile import only ever mutates `world_json`).

### Phase 2 — Extract neutral rendering primitives ✅

- `GraphCanvas.tsx` holds the shared Sigma lifecycle, force-directed layout, camera, zoom/fit, and
  selection-highlight reducers.
- Graph construction, node-type color palettes, and copy stay in `ImaginationWorldGraph.tsx` and
  `MemoryView.tsx` respectively.
- Camera still animates to the newly committed entity via the existing `selected`/`onSelect`
  contract.

**Done when:** World and Memory can share rendering mechanics without sharing node semantics or UI
copy. ✅

### Phase 3 — Build the Imagination world projection ✅

- `ImaginationWorldGraph.tsx` is a dedicated component reading `/api/imagination/world`.
- Node coloring keys off world-native categories (place, person, organization, object, event,
  concept), falling back to a hash palette for free-form types.
- Copy reads “Canonical World” / “entities” / “relations” — no “Living memory” language.
- `WorldEntityInspector` shows properties, relations, constraints, aliases, and creation
  provenance, reading `/api/imagination/nodes/{id}`.

**Done when:** a user can watch the fictional world develop and inspect what exists in that world
without encountering Memory-channel concepts. ✅

### Phase 4 — Build the Memory projection independently

- Give Memory its own projection over experience, cognitive meaning, emotional meaning, scopes,
  provenance, and derivation.
- Keep current Affect as an independent owner; show historical Affect context on Memory records
  without turning Affect into a graph-owned value.
- Ensure Memory filters never remove or rewrite entities in the imagined world.

**Done when:** the Memory graph answers “what does Halcyon remember and how was meaning derived?”
while the World graph answers “what exists and has happened in the imagined world?”

### Phase 5 — Add world history without duplicating Memory

- Project committed world mutations as an inspectable world history.
- Add temporal ordering for events and distinguish current facts from historical facts.
- Link world changes to governance evidence and originating turns.
- Decide explicitly which world-building experiences deserve separate autobiographical Memory;
  do not copy every fictional entity into Memory automatically.

**Done when:** the world has an evidence-backed history while Memory remains Halcyon's experience
and meaning system.

### Deferred decision — one world or many

The server has one canonical `imagination_world_json` shared by all Imagination sessions (separate
from the one canonical `world_json` Memory projects — see Phase 1). Phases 4–5 should preserve that
simple model. Multiple named imagined worlds would require stable world IDs, world selection in
Context, per-world boundaries and versions, and explicit cross-world Memory. That expansion should
happen only after the single-imagined-world projection is clean.

## System & architecture roadmap

Beyond the Graph Separation Roadmap, the following architecture refactorings are planned:

### 1. Server route modularization (`server.py`)

Split the monolithic ~1,000-line `iris/server.py` into focused FastAPI routers and service modules:
- `iris/routers/chat.py` — turn execution, message history, token counting, active retrieval context.
- `iris/routers/imagination.py` — persistent world sessions, streaming autonomous batches, run controls.
- `iris/routers/system.py` — Affect vector state, System Identity projections, Self claims, capabilities, MCP declarations.
- `iris/services/turn_executor.py` — atomic adjudication, model streaming, trial commit logic.
- `iris/services/stream_hub.py` — SSE event streaming hub (`StreamHub`) and client channel lifecycle.

### 2. Legacy CLI & self migration

- **SQLite CLI Integration**: Refactor `run.py` and `--imagine` CLI flags to use `Store` (SQLite WAL) instead of the legacy JSON `Memory` class to prevent state divergence when running CLI and server concurrently.
- **Canonical Self Claims**: Deprecate the legacy `remember` verb (`self.memory` dictionary) in favor of nominations writing directly to `self_claims` with versioning vectors.

### 3. Test suite & integration hardening

- **Autonomous Run Testing**: Add automated integration tests for multi-turn `Imagination` runs, pause/stop states, and batch counters.
- **Gate Invariant Breach Tests**: Test rollback mechanics when trial states breach boundary constraints.
- **Concurrency & Re-adjudication**: Unit test optimistic lock conflict retries and single-turn conversation lock guards.


## Experimental limits

- This is a local single-user experimental runtime.
- There is no authentication or multi-tenant isolation.
- MCP declarations are not yet a general remote execution system.
- Token counting is estimated unless the provider reports authoritative usage.
- Provider-exposed thinking is stored and displayed only when the endpoint supplies it.
- Secret and PII admission policy is incomplete.
- Snapshot, rollback, branching, and full historical replay remain unfinished.
- State ownership is the intended architecture, but the initial combined world/self boundary and
  legacy CLI still contain transitional design debt.

The guiding principle remains simple: a model statement is not evidence that an effect happened.
The receipt and authoritative state transition are the evidence.
