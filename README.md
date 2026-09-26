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

A normal server turn has three phases:

```text
begin transaction        model stream                 finalization transaction
-----------------        ------------                 ------------------------
conversation/message --> transient text/thinking --> gate + Affect checks
turn = generating        no canonical effects         assistant + evidence
                                                       admitted state changes
                                                       turn = complete
```

The server never holds a database transaction open while waiting for the model. Streaming chunks
have no authority. Only the finalized response is adjudicated. For admitted changes, the assistant
message, receipts, mutations, canonical state, and Affect transition commit atomically. A state
version conflict retries adjudication against the new authoritative state once.

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
- Chat turns and autonomous turns share one conversation, one canonical entity graph, and the
  same gate and transaction machinery.
- An autonomous counter advances only after a world mutation commits. A malformed or denied
  attempt receives one governed retry before the run fails.
- Each committed step refreshes the right-hand graph and focuses the changed entity when possible.

### Important graph distinction

The repository currently has a conceptual naming collision:

1. **Imagined world graph** — fictional entities, places, events, relations, aliases, and
   constraints created by Imagination.
2. **Memory graph** — experiences and cognitive/emotional meanings connected by scope,
   derivation, provenance, and retrieval relationships.

These are not the same graph.

At present, canonical SQLite stores an entity graph under `canonical_state.world_json`. The
Imagination pane renders that graph, which is correct in source data, but it reuses `WorldGraph`
from the Memory UI. That renderer includes memory-oriented labels such as “Living memory” and the
Memory page can augment its projection with semantic-memory nodes. The reuse makes the Imagination
pane look like a memory graph even when its input is only the world entity graph.

The next graph pass should separate domain projection from rendering:

```text
canonical imagined world ----> WorldProjection ----> WorldCanvas
canonical Memory channels ----> MemoryProjection --> MemoryCanvas
```

Shared low-level graph primitives are fine. Domain labels, node taxonomy, inspectors, filters,
layout rules, and update animations should remain separate. See **Current design questions** below.

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

## Self and capabilities

Halcyon's canonical identity is seeded from `seeds/halcyon_identity.json`. Self claims are
versioned and visible in the Self page and the right-side Self popout.

Built-in V1 observation capabilities are:

- `system.inspect`
- `memory.search`
- `affect.inspect`

Every tool attempt passes through the capability boundary and leaves a tool receipt. Tool success
does not automatically become Memory. MCP capability declarations can be registered, but a remote
description never grants local authority, and disconnected MCP tools are denied.

## Storage

In server mode, SQLite/WAL is authoritative. The default database is `state/iris.db`.

Important durable records include:

- conversations, turns, messages, and captured contexts;
- proposals, gate decisions, receipts, and mutations;
- canonical world and legacy self-memory JSON inside the canonical-state row;
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

### Model configuration

| Variable | Purpose | Default |
|---|---|---|
| `IRIS_LM_BASE` | Model server base URL | `http://localhost:1234` |
| `IRIS_LM_MODEL` | Provider model identifier | `openai/gpt-oss-20b` |
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
web/src/App.tsx                 application shell and navigation
web/src/ImaginationView.tsx     world dialogue, autonomous batches, live world pane
web/src/MemoryView.tsx          current shared graph renderer and Memory lenses
web/src/SelfSystemView.tsx      Self/System/Capabilities/Tool receipts
docs/CHAT_SPEC.md               chat behavior and atomicity specification
docs/BRAID_UI_SPEC.md           Affect–Memory–Language model
docs/SELF_SYSTEM_TOOLS_SPEC.md  state-owner and capability architecture
```

## Current design questions

These are active architecture decisions, not hidden implementation details:

1. **World versus Memory graph.** Define a first-class imagined-world projection and canvas,
   including world-specific node types, inspectors, temporal events, constraints, and visual
   language. Keep Memory provenance and semantics in a separate projection.
2. **Worlds as state owners.** Decide whether one `world_json` remains adequate or whether each
   imagined world owns a stable ID, graph, history, status, and boundary.
3. **Memory of imagination.** Decide what Halcyon remembers about creating or discussing a world
   without copying every fictional entity into autobiographical Memory.
4. **Temporal world semantics.** `occur` currently produces graph state, but the UI lacks a real
   timeline, eras, causal ordering, and current-versus-historical world views.
5. **Replay.** The ledger contains enough turn and mutation evidence for substantial inspection,
   but historical state reconstruction and turn replay are not yet first-class UI operations.
6. **Legacy state paths.** Migrate or retire the JSON CLI so all entry points share SQLite and the
   same boundaries.
7. **Self migration.** Retire or explicitly redefine legacy `self/memory/*` now that canonical Self
   claims exist.

## Graph separation roadmap

The immediate goal is to make the Imagination graph a view of the imagined world—not a Memory
view with different data passed into it. This should land in small, inspectable slices.

### Phase 1 — Separate names and API surfaces

- Add `/api/world` as the explicit canonical imagined-world read endpoint.
- Keep `/api/memory/*` for Memory channels, retrieval, timelines, and Memory projections.
- Rename the current ambiguous frontend graph component.
- Preserve `/api/memory/world` temporarily as a compatibility alias, then remove it after callers
  migrate.

**Done when:** no Imagination code imports a component named for Memory or fetches its world through
a Memory URL.

### Phase 2 — Extract neutral rendering primitives

- Extract the shared Sigma lifecycle, camera, zoom, fit, selection, and resize behavior into a
  domain-neutral `GraphCanvas`.
- Keep graph construction and domain labels outside that primitive.
- Preserve visible focus and camera movement when a committed patch identifies a changed entity.

**Done when:** World and Memory can share rendering mechanics without sharing node semantics or UI
copy.

### Phase 3 — Build the Imagination world projection

- Create a dedicated `ImaginationWorldGraph` and world projection.
- Use world-native categories such as place, person, organization, object, event, concept, and
  reference.
- Give relations, aliases, constraints, and occurred events distinct visual treatment.
- Replace “Living memory” language with world-state language.
- Add an inspector for entity properties, relationships, constraints, aliases, event involvement,
  creation turn, source proposal, and commit receipt.

**Done when:** a user can watch the fictional world develop and inspect what exists in that world
without encountering Memory-channel concepts.

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

The current server has one canonical `world_json` shared by all Imagination sessions. The first
four phases should preserve that simple model. Multiple worlds would require stable world IDs,
world selection in Context, per-world boundaries and versions, and explicit cross-world Memory.
That expansion should happen only after the single-world projection is clean.

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
