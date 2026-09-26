# Halcyon Self, System Identity, and Capability Architecture

Status: Build specification v0.1

## 1. Core model

Halcyon is a projection of independently governed canonical systems. Each system exclusively
owns its own state and may be modified only through its declared boundary. Language owns no
canonical state.

```text
Self + Memory + Affect + Context + Capabilities + Governance
                              ↓
                    System Identity projection
                              ↓
                         Language / UI
```

Cross-system influence occurs through projections and explicit events. One system never
mutates another system's private state.

## 2. State owners

### Self

Self owns durable identity-level claims: name, values, preferences, commitments, stable
self-understanding, durable relationships, and long-term goals. A Self claim contains an ID,
kind, subject, predicate, value, status, provenance, creation time, and Self version.

Self does not own current emotion, active work, remembered experience, external facts,
capability authorization, or prompt text. Self is deliberately expensive to change.

### Memory

Memory owns experience, cognitive-semantic meaning, emotional-semantic meaning, scope,
sources, and derivation. Memory may reference historical Affect without owning it.

### Affect

Affect owns the current eight-dimensional vector, baselines, homeostasis policy, and
transition history. Ordinary Language proposes one complete next vector; it does not create
semantic meaning during the turn.

### Context

Context owns the active World, Task, and Skill scopes used by retrieval. Global is always
active. Context activation does not move or rewrite memories.

### Capabilities

Capabilities owns the registry of built-in and MCP tools, schemas, effect classes,
availability, local scope, and limits. A tool description advertises a capability; it never
grants permission.

### Governance ledger

Governance preserves boundary versions, proposals, decisions, executions, and evidence.
It is append-only evidence of what the owning boundaries decided and what executors observed.

## 3. System Identity projection

System Identity is not independently writable. It is assembled from owner projections:

```json
{
  "self": {},
  "memory": {},
  "affect": {},
  "context": {},
  "capabilities": {},
  "boundaries": {},
  "versions": {
    "self": 1,
    "memory": 4,
    "affect": 9,
    "context": 2,
    "capabilities": 1
  }
}
```

Every captured model context stores this version vector. It identifies the exact composed
Halcyon from which Language reasoned without creating a second source of truth.

## 4. System boundaries

Each owner exposes a distinct write boundary:

| System | Boundary question |
|---|---|
| Self | May this become part of Halcyon's durable understanding of who she is? |
| Memory | May this become something Halcyon remembers? |
| Affect | Is this complete next vector reachable from the current vector? |
| Context | May these scopes become active now? |
| Capabilities | May this capability be attempted with these arguments here? |

Boundary declarations are versioned configuration in V1. They are not self-modifying state.
An internal transaction coordinator may atomically commit several already-admitted changes,
but it cannot bypass any owner boundary.

## 5. Capability and tool model

Every capability declares:

```text
stable tool ID
source: builtin or mcp:<server>
effect: observe, modify, communicate, or execute
argument schema
local scope
limits
availability
boundary version
```

The lifecycle is:

```text
Language proposes → Capability boundary decides → Executor attempts
→ evidence is captured → observation returns to Language
```

These facts remain distinct:

```text
call admitted ≠ execution succeeded ≠ model understood result ≠ result became Memory
```

### Built-in tools in V1

- `system.inspect`: observe the composed System Identity projection.
- `memory.search`: observe scoped Memory entries matching a query.
- `affect.inspect`: observe effective Affect and recent trajectory.

All are read-only `observe` effects.

### Governed MCP boundary

MCP discovery supplies remote names, descriptions, and schemas. Local Capabilities state maps
them to effect classes and authorization. Disconnected or unregistered MCP tools are denied.
V1 records MCP capability declarations and denial receipts; it does not fabricate an executor
or treat the remote server's description as local policy.

## 6. Tool receipts

Every attempt records:

```text
proposal ID
tool ID and source
raw and normalized arguments
active context
capability version
decision and ordered checks
execution status
result or error
timestamps
```

Results are observations. Memory receives them only through a later Memory nomination.

## 7. UI plan

### Navigation

Add **Self** as a quiet primary destination beside Memory. Governance remains grouped below.
Self contains four coordinated lenses:

```text
Identity | System | Capabilities | Tool receipts
```

### Identity lens

Display canonical Self claims grouped by kind. The page uses an identity header followed by
values, commitments, preferences, relationships, goals, and self-understanding. Each claim
shows status and provenance on inspection. Temporary Affect or active tasks never appear as
Self claims.

### System lens

Display the composed System Identity as a calm constellation of owner cards:

- Self: durable identity claim count and version.
- Memory: active scopes, channel counts, and version.
- Affect: current vector summary and version.
- Context: active World, Task, and Skills.
- Capabilities: available built-ins/MCP tools and version.
- Governance: active boundary versions.

Selecting an owner opens its exact projection. The page labels the whole view **Projection**,
not canonical state.

### Capabilities lens

List tools by source and effect class. Each row exposes availability, scope, schema, limits,
and boundary version. MCP descriptions are visibly labeled as remote declarations; local
authorization is shown separately.

### Tool receipts lens

Show admitted, denied, successful, and failed tool attempts without dashboard theater. Each
receipt expands into proposal, checks, normalized arguments, execution evidence, and result.

### Chat integration

Context Used gains a **System** section containing the captured System Identity and version
vector. Tool calls later appear inline as quiet expandable observations. A successful tool
call never displays a Remembered annotation unless a separate Memory commit occurred.

Chat also exposes a persistent **Self** action in its header. It opens a right-side popout
without leaving the conversation. The popout is a live, explicitly labeled System Identity
projection containing:

- Canonical Self claims.
- Current effective Affect.
- Active World, Task, and Skill scopes.
- Available capabilities.
- Per-domain version vector.

The popout does not edit Self and is not another state store. It includes **Open full Self**
for the Identity, System, Capabilities, and Tool receipts lenses. On narrow screens it becomes
a full-height overlay. Closing it returns focus to the header action.

The legacy `World / Self` switch inside Memory refers only to the old self-memory collection;
it must not be presented as the canonical Self model. The new Self surface and popout are the
authoritative UI projections of the Self system.

## 8. V1 acceptance criteria

- Self claims are canonical records behind a Self-only write path.
- System Identity is rebuilt from owner projections and cannot be written directly.
- Every projection includes per-domain versions.
- Built-in tools execute only after capability authorization and always leave receipts.
- Unknown and disconnected MCP tools are denied and receipted.
- Tool output does not automatically enter Memory or Self.
- UI clearly separates canonical Self from temporary System Identity.
- Captured turn context can show the exact System projection used for reasoning.
