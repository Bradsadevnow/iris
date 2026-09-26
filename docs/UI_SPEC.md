# Iris Server UI — Product and Interaction Specification

Status: Draft v0.1  
Product surface: Browser-first server UI  
Theme: Dark-first  

## 1. Product definition

Iris is a conversational interface to a persistent identity whose world, self-memory, and history are governed by a deterministic admission boundary.

The UI must feel like a polished consumer chat application. Governance is available as inspectable evidence, not presented as a workflow the user must operate. The primary experience is talking to Iris; memory exploration and replay deepen that experience without obstructing it.

This is the main Iris product surface, not an administrative harness.

### Product promise

> Talk naturally. See what Iris remembers. Inspect why it was allowed. Replay how her state changed.

### Experience principles

1. **Chat first.** A user can begin and continue a conversation without understanding nominations, boundaries, receipts, graphs, or invariants.
2. **Governance without theater.** No compliance scores, command-center visuals, ceremonial approvals, or persistent success banners.
3. **Progressive disclosure.** State changes appear as small annotations. Full evidence is one click away.
4. **No hidden claims.** The UI distinguishes model speech, proposed mutations, gate decisions, committed state, and reconstructed historical state.
5. **Linked provenance.** A message can lead to the memory it created; a memory can lead back to its originating turn and receipt.
6. **Stable spatial context.** Inspecting a graph node must not unexpectedly destroy the current view or rearrange the graph.
7. **Dark by design.** Dark mode is the canonical visual treatment rather than a mechanical inversion of a light theme.

## 2. Goals and non-goals

### Goals

- Deliver a familiar, low-friction desktop chat experience.
- Make current world and self-memory legible without reading JSON.
- Support exact inspection and deterministic replay of committed state transitions.
- Make denials and execution errors understandable without overwhelming ordinary conversation.
- Preserve the kernel as the sole authority for canonical state mutations.
- Establish a browser-first architecture that can later be packaged as a desktop application.

### Non-goals for the first release

- Direct visual editing of the graph.
- Manual approval of every memory mutation.
- Multi-user collaboration or permissions.
- Cloud synchronization.
- Arbitrary branching or merging of canonical timelines.
- A general workflow builder.
- Analytics dashboards or governance scoring.
- Mobile-first layout.

## 3. Information architecture

The application has four primary destinations:

1. **Chat** — conversation and message-level memory annotations.
2. **Memory** — explorer, graph, and timeline views of canonical memory.
3. **Governance** — proposals, gate decisions, receipts, and the active boundary declaration.
4. **Settings** — model endpoint, model selection, appearance, and server status.

### Sidebar

The left sidebar is collapsible and contains:

- New chat action.
- Conversation history grouped by recency.
- A quiet divider.
- Memory.
- Governance, with nested Proposals, Gate Decisions, Receipts, and Boundary destinations when expanded.
- Settings.

When collapsed, the sidebar becomes a narrow icon rail. Conversation content retains its readable maximum width and recenters within the remaining viewport.

Governance destinations must not display notification dots for successful routine activity. A visible status indicator is reserved for actionable server, persistence, or boundary failures.

## 4. Application shell

### Desktop layout

- Persistent top-level window.
- Collapsible left sidebar: 248 px expanded, 56 px collapsed.
- Main content fills the remaining width.
- Chat transcript uses a readable centered column, maximum width 760 px.
- Composer remains attached to the bottom of the conversation region.
- Contextual inspectors open as a right drawer, 360–420 px wide, without navigating away.

### Responsive behavior

- At widths below 900 px, the sidebar becomes an overlay.
- At widths below 720 px, inspectors become full-height overlays.
- Graph controls remain reachable by keyboard and do not overlap node details.
- The initial release optimizes for laptop and desktop use down to 720 px.

## 5. Chat experience

### Empty state

The empty state contains:

- Iris's name.
- One short invitation to speak.
- The composer.

It does not contain feature cards, suggested governance actions, capability marketing, or setup theater. If the model server is unavailable, the invitation is replaced by a concise connection error and a route to Settings.

### Messages

Messages show:

- Role and content.
- Timestamp on hover or focus.
- Streaming state for the active Iris response.
- An expandable Thinking disclosure when the model supplies a reasoning artifact.
- Optional mutation annotation after adjudication.

Raw `NOMINATE` protocol lines are removed from the displayed Iris message and retained in the underlying turn record. A developer-oriented receipt view may show the exact original model output.

### Thinking and context

When the model endpoint provides a distinct reasoning or reasoning-summary stream, the Iris message shows a compact **Thinking** disclosure above the final answer. It may be expanded during generation and after completion.

Thinking content is labeled by provenance:

- **Model reasoning summary** — content explicitly returned by the configured model endpoint for display.
- **Model analysis** — raw analysis explicitly exposed by a local model endpoint and deliberately enabled by the operator.

The UI never invents reasoning, reconstructs hidden chain-of-thought, or labels ordinary response text as thinking. If the endpoint supplies no reasoning artifact, the disclosure is absent.

The expanded disclosure includes a **Context used** action. Its inspector separates:

- **Instructions** — the compiled system prompt and active boundary vocabulary supplied to the model.
- **Knowledge** — the canonical self/world projection included in context.
- **Conversation** — the prior messages included in the request.

Each section reflects the exact captured request context for that turn, not current state. Secrets and endpoint credentials are never included. This separation exists to demonstrate the difference between prompting and persistent knowledge without implying that either reveals unavailable hidden reasoning.

### Mutation annotations

After a response is adjudicated, at most one compact annotation appears beneath it:

- **Remembered** — a state mutation committed.
- **No change** — an admitted operation produced a no-op; hidden by default and available in message details.
- **Not remembered** — a nomination was denied.
- **Could not save** — admission succeeded but execution or persistence failed.

Routine successful annotations use neutral text and a small icon. They must not appear as banners or colored cards.

Selecting an annotation opens the appropriate memory or receipt inspector.

### Composer

- Multiline text input.
- Enter sends; Shift+Enter inserts a newline.
- Visible stop control while generating.
- Disabled send state when empty or disconnected.
- No user-facing nomination controls in the standard composer.
- Model and connection settings live in Settings, not permanently beside the input.
- A compact token counter shows projected context usage before sending and output usage during generation.

The token counter expands to separate instructions, canonical knowledge, conversation, and current draft usage. Exact provider or model-tokenizer counts are labeled as authoritative; fallback estimates are visibly marked with `~`. Warning treatment appears only near the configured model context limit, and the UI never invents monetary cost for unknown or local models.

### Streaming

Iris answer text streams into the active assistant message over Server-Sent Events. When a distinct model reasoning channel is available, reasoning streams independently into the expandable Thinking disclosure. Neither stream is authoritative until turn finalization commits.

The transcript follows new content only while the user is near the bottom. Reading an earlier message disables automatic scrolling. On completion, the client replaces transient accumulated text with the server's durable finalized message.

Connection loss does not silently duplicate a turn or cancel generation. The client reconnects using the turn ID and stream cursor; when buffered events are unavailable, it resynchronizes from the durable turn resource.

### Failure behavior

- Model request failure preserves the user's message and marks the turn incomplete.
- Gate denial preserves both messages and explains the denial in message details.
- Persistence failure must never be presented as a successful memory change.
- Retrying model generation creates a new attempt under the same user turn and never overwrites the failed attempt.

## 6. Memory experience

Memory has three coordinated views: Explorer, Graph, and Timeline. They share selection state. Selecting an entity in one view makes it the active entity in the other views without forcing navigation.

### 6.1 Explorer

Explorer is the default memory view and the primary accessibility fallback for the graph.

It provides:

- Search across node names, aliases, relations, constraints, and self-memory keys.
- Scope switcher: World / Self.
- Type filter generated from actual node types.
- A compact result list.
- Selection opening the node inspector.

Each world result shows its name, type, and relationship count. Each self-memory result shows its key and value. Provenance is available in the inspector rather than repeated in every row.

### 6.2 Graph

The graph visualizes the world graph. Self-memory is not mixed into the world graph by default because this would blur the structural wall between collections.

#### Rendering

- Sigma.js renders the graph using WebGL.
- Graphology is the in-browser graph model.
- Layout positions are cached and reused between visits.
- A layout change animates between positions and honors reduced-motion preferences.
- The graph remains useful at the declared boundary maximum of 5,000 elements.

#### Node encoding

- Node size reflects degree within a clamped range.
- Node color reflects type using a restrained, stable palette.
- Labels appear based on zoom, importance, hover, focus, or selection.
- Selection is indicated by both outline/halo and label, never color alone.

#### Edge encoding

- Edges are visually subordinate to nodes.
- The selected node's incident edges and neighbors are emphasized.
- Non-neighborhood content is dimmed, not removed.
- Edge labels appear on selection or in the inspector, not permanently across the canvas.

#### Interaction

- Click selects a node.
- Double-click centers and fits its immediate neighborhood.
- Clicking empty canvas clears selection.
- Scroll/pinch zooms; drag pans.
- Keyboard users can traverse a synchronized neighbor list in the inspector.
- Search results can focus a node without changing the underlying layout.
- A “Reset view” action restores the full fitted graph.

The first release does not permit drag-to-edit, edge creation, or graph mutation from the canvas.

### 6.3 Node inspector

The inspector contains:

- Canonical name.
- Type.
- Aliases.
- Incoming and outgoing relationships.
- Applicable constraints.
- Creation receipt and originating turn, when provenance exists.
- Actions: Open conversation, View receipt, Center in graph.

Missing provenance is labeled “Provenance unavailable”; it is never inferred.

### 6.4 Timeline

Timeline displays turns and state transitions in chronological order. It supports filtering by:

- All turns.
- Committed changes.
- Denials.
- Errors.
- Self-memory changes.
- World changes.

Selecting an item opens replay at that turn.

## 7. Replay

Replay is a read-only historical inspection mode. It reconstructs canonical state at a selected sequence number and synchronizes the conversation, graph, and receipt views.

### Replay entry points

- Message details → Replay turn.
- Mutation annotation → Replay change.
- Receipt → Replay turn.
- Node provenance → Replay creation.
- Timeline item → Replay.

### Replay presentation

Entering replay adds a slim persistent replay bar above the composer or at the bottom of non-chat views. The bar contains:

- “Replay” label.
- Current turn and timestamp.
- Previous/next state-changing turn controls.
- Timeline scrubber.
- Return to present action.

The composer is disabled while viewing historical state and is replaced with “Return to present to continue chatting.” Historical mode must be unmistakable without covering the content in warning colors.

### Turn replay stages

For a selected turn, the user can inspect:

1. State immediately before the turn.
2. User message.
3. Exact model response.
4. Parsed nomination, if one exists.
5. Ordered gate checks.
6. Trial mutation result.
7. Invariant results.
8. Commit, denial, no-op, or error.
9. State immediately after the turn.

“Play” may animate these stages, but step controls are always available and animation is not required to understand the result.

### Replay truth guarantees

- Replay never invokes the language model.
- Replay never reapplies effects to live canonical state.
- Historical state is reconstructed from committed events and verified snapshots.
- Model text and rationale are displayed exactly as originally recorded in receipt details.
- If state cannot be verified, replay displays an integrity error rather than an approximation.
- The initial release does not allow forking from a past turn. The data model must leave room for later timeline branches.

## 8. Governance experience

### Proposals

Proposals are the normalized nominations found in finalized model responses, regardless of their eventual outcome. The Proposals view shows:

- Timestamp and originating turn.
- Verb and target path.
- Normalized arguments when parsing succeeded.
- Parse status when nomination-like text was malformed.
- Linked gate decision.
- Linked resulting memory entity when committed.

Selecting a proposal opens its exact raw line, surrounding model output, normalized claim, and provenance. A proposal is never styled as though it changed memory merely because the model emitted it.

### Gate Decisions

Gate Decisions show the adjudication of proposals as an ordered pipeline:

- Schema.
- Rationale presence.
- Scope.
- Verb authorization and write scope.
- Arguments.
- Invariants.
- Execution.
- Durable commit outcome.

The list view shows outcome, proposal summary, failed or terminal stage, turn, and timestamp. The detail view shows every check in order and links to the proposal, receipt, conversation, and resulting mutation.

Admission, execution, and persistence are distinct. An admitted proposal whose execution or transaction failed is never shown as committed.

### Receipts

Receipts are shown as a quiet, searchable table or list with:

- Timestamp.
- Turn.
- Verb.
- Target.
- Decision.
- Short decision basis.

Selecting a receipt opens a detail inspector containing the exact claim, original model output, ordered decision basis, execution result, and links to the associated conversation and memory entities.

Decision language must distinguish:

- **Admitted and committed**.
- **Admitted but no-op**.
- **Denied**.
- **Admitted but execution failed**.
- **No nomination**.

The existing top-level receipt `decision` value alone is insufficient for these user-facing states; the server must derive or store an explicit outcome.

### Boundary

The Boundary view presents the compiled attestation, not merely the source YAML. It contains:

- Active task.
- State scopes.
- Authorized verbs and their write scopes.
- Argument rules.
- Invariants and limits.
- Boundary version or content hash.

The source declaration may be shown in a secondary code view. Boundary editing is out of scope for the first release.

## 9. Dark visual system

### Character

The interface is calm, dense enough for serious use, and materially quiet. It uses graphite surfaces, warm light text, a restrained iris-violet accent, and minimal borders. It must not resemble a security operations dashboard.

### Color roles

Final color values will be tuned during implementation, but roles are fixed:

- Canvas: near-black graphite.
- Elevated surface: slightly lighter graphite.
- Hover surface: subtle neutral lift.
- Primary text: warm off-white.
- Secondary text: neutral gray with accessible contrast.
- Accent: desaturated iris violet.
- Accepted: muted green, used only when status meaning is necessary.
- Denied/error: muted red, used only for actionable or inspected status.
- Warning: muted amber.

Large areas never use status colors. Graph category colors use low-saturation fills and remain distinguishable in common color-vision deficiencies.

### Typography

- Interface: modern sans-serif with a neutral, human tone.
- Protocol, receipt IDs, and raw paths: monospace.
- Default chat text: 15–16 px equivalent.
- Line length capped for comfortable reading.
- Two primary weights: regular and medium.

### Shape and depth

- Moderate corner radius; no excessive pill treatment.
- Borders are used only to clarify boundaries.
- Shadows are subtle and limited to overlays and floating inspectors.
- The composer may be elevated; ordinary messages are not placed in cards.

### Motion

- Sidebar collapse: 160–220 ms.
- Inspector transitions: 180–240 ms.
- Graph focus and replay transitions preserve spatial continuity.
- No looping animation, pulsing governance status, or decorative particle effects.
- `prefers-reduced-motion` removes nonessential movement.

## 10. Accessibility

- All core chat, memory, receipt, and replay functions are keyboard accessible.
- Visible focus states meet contrast requirements.
- Text and essential controls meet WCAG 2.2 AA contrast.
- Status is never communicated through color alone.
- The Explorer provides a complete textual alternative to graph navigation.
- Graph selection changes are announced through an ARIA live region.
- Inspectors use correct dialog/drawer semantics and return focus on close.
- Replay stage changes announce the current stage and outcome.
- Streaming content does not repeatedly steal screen-reader focus.

## 11. Technical architecture

### Frontend

- React and TypeScript.
- Vite for the initial browser application.
- Sigma.js plus Graphology for graph rendering and traversal.
- A small token-based CSS system with purpose-built components.
- SSE for streamed assistant output and turn lifecycle events.
- Standard HTTP APIs for queries, replay, settings, and history.

The frontend is a projection and control surface. It does not adjudicate nominations or mutate canonical memory directly.

### Backend

- FastAPI application wrapping the existing Iris modules.
- The gate remains the only canonical graph writer.
- A single writer serializes turn and mutation commits.
- Read APIs expose conversations, graph projections, receipts, boundary attestation, and historical reconstruction.
- The LM adapter gains a streaming interface while preserving a non-streaming fallback.

### Process shape

For the first release, one server process owns one Iris state directory. Multi-process writers are prohibited until locking or a transactional store is implemented.

## 12. Persistence and event model

Exact replay requires one ordered source of truth. Separate timestamped JSONL files are not sufficient because writes can fail between files and timestamps do not establish transactional ordering.

### Event envelope

Every durable event contains:

```json
{
  "sequence": 42,
  "event_id": "evt_...",
  "turn_id": "turn_...",
  "attempt_id": "attempt_...",
  "timestamp": "2026-09-25T18:42:12.123Z",
  "type": "mutation_committed",
  "boundary_hash": "sha256:...",
  "payload": {}
}
```

`sequence` is monotonic within one Iris timeline. `event_id` and `turn_id` are stable identifiers. `attempt_id` distinguishes retries under the same user turn.

### Required event types

- `turn_started`
- `user_message_recorded`
- `generation_started`
- `assistant_delta_recorded` or an equivalent finalized streaming record
- `assistant_message_recorded`
- `nomination_adjudicated`
- `mutation_committed`
- `mutation_noop`
- `mutation_denied`
- `mutation_failed`
- `turn_completed`
- `turn_failed`
- `boundary_activated`
- `snapshot_created`

Streaming deltas may be transient, but the finalized assistant message is durable and exact.

### Committed mutation event

A committed event stores enough information to verify and reconstruct state without calling tool code whose implementation may later change:

- Claim and normalized arguments.
- Decision basis.
- Explicit mutation patch or canonical before/after values for touched paths.
- Result.
- Tool implementation version.
- Boundary hash.
- Originating message and receipt IDs.

### Projections

- `world.json` and `self.json` remain current-state projections for simple inspection and compatibility.
- Conversation history, receipts, and timeline are projections of the ordered event log.
- Projection files can be rebuilt from the event log plus a verified snapshot.

### Snapshots

- Snapshot after a configurable number of committed mutations, initially 100.
- Snapshot contains canonical world and self state, last sequence, boundary hash, and a checksum.
- Replay loads the nearest verified snapshot at or before the target sequence, then applies subsequent committed patches in order.
- Snapshot creation is atomic.

### Atomicity

A turn may span several events, but a state mutation and its committed event must succeed atomically from the UI's perspective. The server must never report a committed memory if the durable commit failed.

SQLite in WAL mode is the preferred first implementation for the ordered event store, transactions, queries, and single-writer discipline. JSON exports remain available for portability and inspection.

## 13. API contract

Exact shapes will be formalized with generated OpenAPI types. Required endpoints:

### Conversation

- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/conversations/{conversation_id}`
- `POST /api/conversations/{conversation_id}/turns`
- `GET /api/turns/{turn_id}`
- `GET /api/turns/{turn_id}/stream` or an SSE response from turn creation

### World

- `GET /api/world` — known/seeded entity graph (real people, places, organizations) that Memory projects.

### Imagination

- `GET /api/imagination/world` — the separate, fictional world graph Imagination's nomination verbs write to.
- `GET /api/imagination/nodes/{node_id}` — entity detail (properties, relations, constraints, provenance) within that graph.

### Memory

- `GET /api/memory/self`
- `GET /api/memory/search?q=...`
- `GET /api/memory/nodes/{node_id}` — entity detail within the known/seeded entity graph.
- `GET /api/memory/nodes/{node_id}/provenance`

### Governance

- `GET /api/receipts`
- `GET /api/receipts/{receipt_id}`
- `GET /api/proposals`
- `GET /api/proposals/{proposal_id}`
- `GET /api/gate-decisions`
- `GET /api/gate-decisions/{decision_id}`
- `GET /api/boundary/attestation`

### Replay

- `GET /api/replay/range`
- `GET /api/replay/state?sequence=...`
- `GET /api/replay/turns/{turn_id}`

### Operations

- `GET /api/health`
- `GET /api/settings`
- `PATCH /api/settings`

All mutation-capable endpoints are explicit. Memory and replay endpoints are read-only.

## 14. Security and privacy baseline

- The first release binds to localhost by default.
- Non-local binding requires explicit configuration and authentication.
- Raw model endpoints and secrets are never returned by settings APIs.
- Logs avoid message bodies unless verbose local debugging is explicitly enabled.
- The UI clearly identifies that current state may contain durable personal information.
- Secret/PII admission controls remain a known kernel gap and must be addressed before remote or shared deployment.

## 15. Delivery phases

### Phase 1 — Product shell

- SQLite/WAL authoritative storage and atomic turn/memory transactions.
- Dark application shell.
- Collapsible sidebar.
- Conversation list and chat transcript.
- Streaming composer and server connection state.
- Existing gate wired behind chat.
- Compact mutation annotations.

Phase 1 is defined in detail by [Iris Chat — Feature Specification](./CHAT_SPEC.md). No successful turn or memory state may be presented before its authoritative transaction commits.

### Phase 2 — Inspectable memory

- Explorer.
- Sigma graph.
- Node inspector.
- Receipt list and detail.
- Compiled boundary view.
- Bidirectional links among messages, nodes, and receipts.

### Phase 3 — Exact replay

- Ordered transactional event store.
- Turn IDs, attempt IDs, and explicit outcomes.
- State patches and provenance.
- Snapshots and verification.
- Replay bar, timeline, and turn-stage inspector.

Phase 3 persistence work may begin before Phase 2 UI completion because provenance captured late cannot be reconstructed honestly from incomplete historical data.

### Phase 4 — Packaging and hardening

- Accessibility audit.
- Performance testing at boundary limits.
- Crash and partial-write recovery testing.
- Export and backup.
- Optional Tauri desktop packaging.

## 16. Acceptance criteria

### Chat

- A new user can send a first message without encountering governance terminology.
- Assistant text streams and remains readable at all supported desktop widths.
- Raw nomination syntax is absent from the standard transcript.
- Every completed turn has an inspectable outcome.
- The UI never labels an unpersisted mutation as remembered.

### Memory

- Search can find any canonical world node or self-memory key.
- Selecting a graph node opens its relationships without rearranging the graph.
- A keyboard-only user can inspect the same node facts available through the canvas.
- A user can navigate from an attributed node to its originating receipt and conversation.
- Missing provenance is disclosed rather than fabricated.

### Governance

- The Boundary view matches the kernel's compiled attestation.
- Every parsed nomination appears in Proposals and links to its originating turn.
- Every adjudicated proposal links to an ordered Gate Decision.
- A proposal is visually distinct from a committed mutation.
- A denial shows the exact failed check and preserves the original model output.
- Admission, execution, and persistence outcomes are visibly distinct.
- Governance UI does not interrupt successful ordinary chat.

### Replay

- Selecting a historical turn reconstructs verified state immediately before and after it.
- Replay performs no LM calls and cannot mutate current state.
- Chat, graph, and receipt selection remain synchronized at the replayed turn.
- Returning to present restores the current canonical state and enables the composer.
- Corrupt or unverifiable history produces an integrity error, never an approximate state.

### Visual quality

- Dark mode is complete across empty, loading, populated, error, inspector, graph, and replay states.
- No screen resembles an analytics dashboard unless the content genuinely requires one.
- Status colors are sparse and semantic.
- At 5,000 graph elements, interaction remains responsive on a representative laptop.
- Reduced-motion mode retains full comprehension and control.

## 17. Open decisions

These decisions should be made during implementation without changing the product model:

- Exact font family and final color values.
- SQLite schema and patch representation.
- Graph layout algorithm and when layout computation moves to a worker.
- Whether conversation boundaries are purely presentational or affect LM context.
- When to introduce branching from a historical turn.
- Whether the first packaged desktop build uses Tauri or remains browser-only.

## 18. Product guardrails

Before adding a persistent UI element, ask:

1. Does it help the user talk, understand memory, or verify a real state transition?
2. Is it actionable now?
3. Can it appear only when relevant?
4. Does it represent a fact the system can prove?

If the answer is no, omit it.
