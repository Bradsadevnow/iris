# Chat, State, Affect, and Memory Roadmap

Status: agreed direction; implementation pending
Scope: ordinary chat turns, compression, Memory, Affect, Hal's server world, and Imagination canon

## Decision

The system has four state owners with different write paths:

| Owner | Meaning | Ordinary chat | Dedicated writer |
|---|---|---|---|
| Self | Who Hal is: identity, values, commitments, relationships, stable preferences | Read only | Compression |
| Memory | What Hal retains from experience and can later retrieve | Bounded proposals and admissions | Memory boundary |
| Affect | Hal's current emotional motion | Bounded transition | Affect boundary |
| Imaginary world | Deliberately created fictional canon | Discuss and reference only | Imagination admission |

Hal's **world** is the server and its observable runtime: tools, files, processes, configuration,
capabilities, and other available environment state. It is not the fictional world graph. Changes
to the server world happen through authorized tools and leave tool receipts.

These rules are hard invariants:

1. Ordinary chat cannot mutate Self. Self changes only during compression.
2. Ordinary chat cannot admit, revise, or delete imaginary-world canon.
3. Imagination changes canon only through an explicit user action in the Imagination area.
4. Memory cannot serve as an indirect Self or imaginary-world mutation channel.
5. Affect may change attention and expression, never authorization, truth, identity, or canon.
6. Every accepted effect and its evidence commit atomically with the completed turn.

## Current mismatch

The current implementation predates this ownership model:

- `boundary/imagine_and_chat.yaml` allows both `world/*` and `self/memory/*` nominations during
  ordinary chat.
- `remember` writes into `state["self"]["memory"]`, making retained experience part of canonical
  Self.
- Chat verbs `create`, `relate`, `constrain`, `occur`, and `name` write directly into
  `state["imagination_world"]`.
- `Store.finalize()` can persist Self, known-world, imaginary-world, Affect, and conversation state
  in one generalized completion path.
- `world` is overloaded: `world_json` currently stores seeded known/domain knowledge, while the
  product meaning of "Hal's world" is the server runtime.
- Memory admission is represented by the same single `NOMINATE` grammar used for fictional-world
  mutation instead of an independently owned effect.

The transaction is already usefully atomic. The work is to narrow its legal effects and separate
their owners, not to weaken that atomicity.

## Target turn flow

```text
durably record user event
        ↓
capture immutable context manifest
        ├── Self projection (read only)
        ├── current conversation and explicit attachments
        ├── relevant Memory
        ├── authorized server-world observations/capabilities
        ├── imaginary-world references (read only in chat)
        └── current Affect
        ↓
grounded model pass
        ├── visible response
        ├── optional Memory proposal
        └── required Affect proposal
        ↓
independent deterministic boundaries
        ├── Memory: admit / deny / no-op
        └── Affect: admit / deny
        ↓
expression pass (last; no effect authority)
        ↓
one finalization transaction
        ├── finalized assistant message
        ├── accepted Memory write, if any
        ├── accepted Affect transition
        ├── proposal, decision, and receipt records
        └── terminal turn status
```

An Imagination admission is a different command path. It may share transaction utilities, but it
does not pass through the ordinary chat effect vocabulary.

## Phase 0 — Freeze the contracts

- Add explicit owner names to code and documentation: `self`, `memory`, `affect`,
  `server_environment`, and `imagination_world`.
- Reserve `known_world` or `domain_knowledge` for the seeded graph currently stored as
  `world_json`; stop describing it as Hal's world.
- Define an `EffectBundle` contract whose entries have `owner`, `operation`, `target`, `payload`,
  and proposal provenance.
- Define command-origin metadata: `chat`, `compression`, `imagination`, `tool`, or `import`.
- State that expression receives no writable effects and cannot add or revise proposals.

Acceptance:

- Every mutable target has exactly one named owning boundary.
- Every route capable of a write declares its command origin.
- Documentation and UI use “imaginary world” only for fictional canon and “server environment” for
  Hal's world.

## Phase 1 — Close illegal chat write paths

- Replace `imagine_and_chat.yaml` with an ordinary-chat boundary that contains no `world/*` or
  `self/*` state scope.
- Remove the five imaginary-world verbs from the chat `TOOLS` registry. Keep them behind the
  existing blueprint/admission service used by Imagination.
- Remove `remember -> self/memory/*` from the chat gate.
- Add defense-in-depth checks in finalization: a `chat` origin must reject any diff to Self,
  known/domain knowledge, or imaginary-world canon even if a parser or boundary declaration is
  misconfigured.
- Keep chat able to read referenced imaginary-world nodes and explicit draft snapshots.
- Return an inspectable denial if legacy or adversarial output asks chat to mutate a forbidden
  owner.

Acceptance:

- A chat response containing a valid-looking `world/*` nomination cannot change
  `imagination_world_json`.
- A chat response containing a valid-looking `self/*` nomination cannot change Self.
- A normal chat turn can still complete, update Affect, and write admitted Memory.
- Imagination's explicit **Add to World** flow still admits a complete blueprint atomically.

## Phase 2 — Separate Memory from Self

- Define Memory records outside canonical Self. Reuse and tighten the existing memory-entry/event
  tables rather than introducing another graph by default.
- Give each record a lifetime and kind:
  - working: active intent, unresolved matter, or temporary conversational state;
  - episodic: an attributable event or interaction;
  - semantic: a stabilized fact, preference, relationship observation, or learned meaning.
- Require provenance, source turn/event, scope, confidence, timestamps, and status for every durable
  record.
- Replace the legacy one-line `remember` mutation with a structured Memory proposal and a dedicated
  Memory decision receipt.
- Keep explicit chat attachments, including character snapshots, as conversation context unless a
  separate Memory proposal is admitted.
- Migrate existing `self.memory` entries losslessly into Memory records. Preserve source IDs and
  import provenance; do not reinterpret or delete the legacy material during migration.
- After verification, make the legacy `self.memory` map read-only compatibility data and then remove
  it from the Self projection.

Acceptance:

- Remembering an experience changes Memory's version, not Self's version.
- A character snapshot is available to later turns in that conversation without becoming Self,
  Memory, or canon automatically.
- Memory records cannot target Self claims or imaginary-world entities as mutations; they may only
  reference them by stable ID.
- Migration is idempotent and preserves every legacy value.

## Phase 3 — Make compression the only Self writer

- Introduce a dedicated compression command and service with an explicit input set, policy version,
  and immutable receipt.
- Compression may read conversation events, Memory, prior Self, Affect history, and user-supplied
  corrections. Reading does not imply admission.
- Produce a reviewable Self candidate/diff before commit.
- Run Self-specific invariants: protected identity fields, provenance, size budgets, contradictions,
  and relationship continuity.
- Commit the new Self version in one compare-and-swap transaction.
- Record which evidence supported, contradicted, or was excluded from each changed claim.
- Do not allow compression to mutate Memory, Affect, the server environment, or imaginary-world
  canon in the same command.

Initial product posture:

- Compression is manual and user-confirmed.
- Scheduling or automatic compression remains deferred until its review and rollback semantics are
  proven.

Acceptance:

- Repository-wide tests demonstrate that only the compression service can update Self.
- Failed, denied, stale, or cancelled compression leaves Self unchanged.
- Every Self version links to its predecessor, evidence set, policy version, and receipt.

## Phase 4 — Tighten Affect as a separate bounded effect

- Keep stimulus appraisal after grounding and before expression so emotional movement can color the
  rendered response.
- Preserve the current complete-vector, finite-range, per-dimension maximum-delta, homeostasis, and
  source-event idempotency checks.
- Give Affect an explicit decision record distinct from the Memory decision.
- Make failure behavior explicit: invalid Affect fails finalization or falls back to a declared
  no-transition policy; it must never partially apply.
- Ensure Affect influences retrieval weights, stance, and expression only through captured inputs.
- Prohibit Affect from changing permissions, confidence of factual claims, tool authorization,
  Memory admission, Self admission, or Imagination admission.
- Keep expression last and validate semantic fidelity against the grounded response.

Acceptance:

- Identical admitted Affect events cannot apply twice.
- A denied Memory proposal does not suppress an otherwise valid Affect transition.
- Extreme proposed movement is rejected without changing the stored vector.
- Expression can sound emotionally different but cannot change identifiers, facts, uncertainty,
  availability, or effect outcomes.

## Phase 5 — Refactor finalization around independent effects

- Split generalized adjudication into an orchestrator plus owner-specific boundaries:
  `MemoryBoundary`, `AffectBoundary`, `CompressionBoundary`, `ImaginationBoundary`, and the existing
  capability/tool boundary.
- Store one decision per proposed effect rather than overloading a single turn outcome.
- Derive the quiet transcript annotation from effect decisions (`Remembered`, `Not remembered`, or
  no annotation), never from model language.
- Preserve one short finalization transaction for chat:
  assistant message + accepted Memory + accepted Affect + receipts + terminal status.
- Preserve optimistic version checks per changed owner. Avoid incrementing unrelated domain
  versions.
- Add idempotency keys for turn submission and effect application.
- Emit `assistant.completed` only after the authoritative transaction commits.
- Keep projection-file refresh after commit and make it owner-specific; projection failure cannot
  falsify the committed result.

Acceptance:

- Fault injection at every finalization statement yields all-or-nothing results.
- Memory and Affect can both commit in one turn while retaining separate decisions and provenance.
- No-op and denied effects do not increment unrelated state versions.
- Retry after a transport failure cannot duplicate a Memory or Affect event.

## Phase 6 — Deliberate Imagination admission

- Keep browsing, drafting, composing, and chat discussion non-canonical.
- Require a stable blueprint ID, revision, candidate content hash, and explicit user admission
  action for every canon change.
- Route admission exclusively through the Imagination boundary.
- Store the admitted blueprint, graph patch, lore revision, pressures, receipt, and new
  imaginary-world version in one transaction.
- Reject stale blueprint revisions and mismatched content hashes.
- Treat later revisions as new admissions; never silently rewrite an earlier admitted artifact.
- In chat, reference admitted entities and draft snapshots by ID and status so “draft,” “candidate,”
  and “canon” remain distinguishable.

Acceptance:

- Discussing or attaching a creation in chat never changes canon.
- Only an explicit Imagination admission changes `imagination_world_json`.
- Admission rollback leaves no partial node, edge, lore revision, or pressure.
- The UI plainly distinguishes conversation attachment, draft candidate, and admitted canon.

## Phase 7 — Hal's server world and tool effects

- Inventory server-world observations and actions separately from semantic/domain knowledge.
- Bind model tool calls only to authorized, available capabilities.
- Run every action through the capability boundary and persist request, authorization, execution,
  result, and failure receipts.
- Keep tool observations ephemeral unless independently admitted into Memory.
- Do not let a successful tool call mutate Self or imaginary-world canon as a hidden side effect.
- Capture exactly which server observations and tool results entered the grounded response.

Acceptance:

- The model cannot claim a tool action without a matching receipt.
- Tool availability is never inferred from prose or registration alone.
- Server-world changes follow tool-specific authorization and are not reported as Memory, Self, or
  Imagination mutations.

## Phase 8 — UI evidence and operational hardening

- Update **Context used** to show Self, Memory, Affect, server environment, domain knowledge,
  imaginary-world references, roles, and conversation as separately labeled inputs.
- Update receipt UI to show independent effect decisions under one turn.
- Add compression history and Self-version comparison outside ordinary chat.
- Show Memory provenance and lifecycle without exposing protocol noise in the transcript.
- Show Imagination admission evidence only in Imagination and linked entity details.
- Add recovery tests for generation, finalization, compression, and Imagination admission crashes.
- Add adversarial tests for cross-owner mutation attempts and prompt-injected protocol lines.
- Add an audit query that proves which subsystem wrote each versioned state change.

Acceptance:

- A user can answer “what changed, why, and which boundary allowed it?” from one receipt path.
- No UI label claims a proposal was committed before persistence succeeds.
- Every persisted mutation has one origin, one owning boundary, and immutable provenance.

## Recommended implementation order

1. Freeze terminology and `EffectBundle`/origin contracts.
2. Close chat writes to Self and imaginary-world canon, with defense-in-depth tests.
3. Move legacy `self.memory` into independently owned Memory.
4. Introduce the manual compression-only Self writer.
5. Split Memory and Affect decisions while preserving atomic turn completion.
6. Finish deliberate Imagination-only admission and remove legacy chat imagination verbs.
7. Bind server-world tools through the capability boundary.
8. Finish UI evidence, recovery, adversarial, and fault-injection coverage.

Phases 1–3 are the critical boundary correction. Retrieval tuning, embeddings, automatic
compression, and richer autonomous behavior should wait until those ownership guarantees are
enforced in code and tests.

## Explicit non-goals

- No automatic Self mutation from chat, Memory, Affect, roles, or personas.
- No chat-driven fictional canon mutation, even when the user casually says “make it canon.”
- No use of Affect as permission or truth evidence.
- No automatic promotion of conversation attachments into Memory.
- No destructive cleanup of legacy `self.memory` before verified migration.
- No multi-world architecture required for this boundary pass.
- No semantic/vector retrieval prerequisite for correcting state ownership.

## Completion definition

This roadmap is complete when ordinary chat can change only conversation history, admitted Memory,
and bounded Affect; compression is the sole writer of Self; Imagination admission is the sole writer
of fictional canon; authorized tools are the sole writers of Hal's server world; and every accepted
effect is independently receipted and atomically persisted.
