# Context–Memory–Affect Braid

Status: proposed implementation contract

This document extracts the useful ideas from the experimental context builder and tightens them
with Memory and Affect as one system. The three concerns remain independently owned, but every
turn carries an inspectable braid showing exactly what each contributed and what changed.

## Core rule

No stage may claim access, meaning, feeling, or execution that belongs to another stage.

- Context selects and labels material; it does not own the selected records.
- Memory owns durable experience and derived meaning; it does not own current emotion.
- Affect owns the current vector and transition history; it does not turn emotion into fact.
- Roles shape method; they do not become identity or grant knowledge.
- Tools retrieve or act through boundaries; registry descriptions are not executions.
- Expression renders an admitted grounded representation; it does not revise its claims.

## Turn pipeline

```text
canonical snapshots
  Self + active Context + Memory candidates + Affect
                         |
                         v
                  task interpretation
                         |
              +----------+-----------+
              |          |           |
           roles      domain      operation
                      routers       intent
              |          |           |
              +----------+-----------+
                         |
             supplied-context manifest
                         |
               optional bound-tool loop
                         |
                grounded representation
                         |
          gate preview + Affect validation
                         |
                 expression rendering
                         |
             atomic finalization + receipts
```

The model may be nondeterministic. Every boundary between these stages must be deterministic or
captured as a durable input/output receipt.

## Canonical input snapshots

At turn start, capture immutable versions of:

- canonical Self version;
- active Context version and scopes;
- Memory version plus eligible scope query;
- Affect version, effective vector, baselines, and timestamp;
- known-world and Imagination graph versions;
- capability-registry and boundary versions;
- current-conversation message IDs included in the request.

The turn must continue using those snapshots until final adjudication. A conflicting canonical
write may trigger re-adjudication, but must not silently change what the model was told.

## Context manifest

The context builder returns a structured manifest before rendering prompt text:

```json
{
  "identity_kernel": [],
  "activated_self_claims": [],
  "task_context": {},
  "roles": [],
  "conversation_history": [],
  "memory": {
    "eligible": [],
    "supplied": [],
    "omitted": []
  },
  "knowledge": {
    "known_world": [],
    "imagination": []
  },
  "tools": {
    "registered": [],
    "bound": []
  },
  "affect_snapshot": {},
  "expansion_handles": [],
  "budgets": {},
  "versions": {}
}
```

Prompt prose is a rendering of this manifest. It is not the authoritative record of what was
selected.

## Memory lifecycle and vocabulary

Use these terms precisely:

1. **Eligible Memory** — records visible under current Global, World, Task, and Skill scopes.
2. **Supplied Memory** — eligible records actually included in the initial grounded-model request.
3. **Tool-retrieved Memory** — records returned later by a receipted `memory.search` call.
4. **Referenced Memory** — supplied or tool-retrieved records cited by the grounded representation.
5. **Omitted Memory** — eligible records not supplied because of relevance, privacy, or budget.
6. **Formed Memory** — a new record admitted later by its owning reflection/dreaming boundary.

`retrieved_memory` must never mean “all eligible records.” Persist each category separately.

Conversation history is not automatically semantic Memory:

- Current-conversation messages may be supplied as transcript history.
- Cross-conversation messages are episodic records and require explicit scoped retrieval.
- Exact quotations require an included message ID or a tool-result receipt.
- Ordinary chat finalization does not automatically create cognitive or emotional meaning.

### Memory selection

Memory selection is its own router, not a branch of generic graph ranking.

Required inputs:

- meaningful task terms after stop-word removal and normalization;
- active scopes;
- channel policy;
- recency policy;
- explicit entity/message references;
- optional Affect salience contribution.

Affect may influence salience only through a named, bounded score contribution. It may not:

- change the truth status of a memory;
- turn an emotional-semantic record into current Affect;
- admit an otherwise unauthorized scope;
- make a low-relevance memory appear factual or recent.

Every supplied Memory record must include selection reasons, matched terms, scope, channel,
provenance, recency contribution, Affect-salience contribution, and token cost.

## Affect lifecycle

Use four distinct Affect states:

1. **Stored Affect** — canonical vector and baseline values in SQLite.
2. **Effective Affect snapshot** — homeostasis-adjusted vector captured at turn start.
3. **Proposed Affect transition** — complete next vector emitted by the grounded pass.
4. **Committed Affect** — validated vector atomically written during finalization.

The grounded pass receives the effective snapshot as governed control state, not as knowledge or
persona. It proposes a complete next vector. Before expression:

- parse the proposal;
- verify all dimensions, finite values, range, and maximum delta;
- calculate the proposed delta;
- construct an expression-safe emotional trajectory containing current vector, proposed direction,
  and the fact that it remains uncommitted.

Expression should not receive raw Affect protocol lines. It receives only the bounded trajectory
needed for tone. If Affect validation fails, the turn fails before the expression request and no
state changes.

The committed transition remains atomic with the assistant message, gate receipt, and admitted
state mutation.

## Role and knowledge routing

Role selection and knowledge selection are independent.

- A role is selected from explicit configuration or task intent.
- A role contributes reasoning priorities, preferred evidence, and traversal relations.
- A role cannot independently admit a knowledge node.
- Role voice preferences are held for expression only.

Route domains separately:

- Self overlays;
- Memory;
- known-world entities;
- Imagination;
- capabilities/tools.

Each router has its own threshold, exclusions, and token budget. Imagination defaults to excluded
outside fictional context. Capability registry entries never compete with knowledge nodes.

## Tool lifecycle

Use these states:

```text
registered -> authorized -> bound -> invoked -> succeeded | denied | failed
```

Only `bound` tools enter the model request. Every invocation produces a receipt. Every result sent
back to the model contains its receipt ID and provenance. A model statement such as “I searched”
without a matching invocation receipt is an evaluation failure.

Memory and graph tools return observations; they do not automatically form Memory or mutate any
graph.

## Grounded representation

The grounded pass should produce a structured envelope rather than free prose plus hidden lines:

```json
{
  "claims": [],
  "uncertainties": [],
  "availability_boundaries": [],
  "recommendations": [],
  "citations": [],
  "referenced_memory_ids": [],
  "tool_receipt_ids": [],
  "visible_draft": "",
  "nomination": null,
  "affect_proposal": {}
}
```

The gate consumes `nomination`; the Affect boundary consumes `affect_proposal`; expression consumes
only the visible semantic fields. Free-text compatibility parsing may remain temporarily, but the
structured envelope is the target contract.

## Expression contract

Expression is last. It may change:

- diction;
- rhythm;
- warmth;
- formatting;
- context-earned humor and symbolism.

It may not change:

- entities, identifiers, numbers, quotations, or sources;
- polarity or negation;
- confidence and uncertainty;
- available/unavailable distinctions;
- registered/bound/invoked tool states;
- proposed/committed state;
- recommendations or refusals.

Validate the expressed response against the grounded envelope. On any mismatch, use the grounded
visible draft and record an expression-fallback receipt.

## Cancellation and failure semantics

Check cancellation:

- during and immediately after grounding;
- during and immediately after every tool call;
- during and immediately after expression;
- immediately before finalization.

Cancellation before finalization commits no assistant message, gate effect, Affect transition, or
formed Memory. Expression failure falls back to grounded visible prose; grounding, tool-boundary,
gate, or Affect-validation failure fails the turn.

## Required receipts

One completed turn must expose:

- input version vector;
- identity kernel and activated Self claims;
- task interpretation and role-selection receipt;
- eligible/supplied/omitted Memory IDs;
- known-world and Imagination selection receipts;
- initial and tool-retrieved context separately;
- registered and bound tool manifests;
- invocation receipts and results;
- grounded envelope;
- Affect snapshot, proposal, validation, and committed transition;
- expression profile, expression output, fidelity result, and fallback status;
- gate decision and final canonical sequence.

The Context Used UI should render these stages directly rather than inferring them from a combined
prompt string.

## First implementation slice

Status: implemented and covered by deterministic tests. Atomic-unit boundary tuning remains the
next refinement; this slice intentionally does not redefine graph-node or Memory-record granularity.

Tighten the braid in one vertical slice:

1. Introduce the structured context manifest and persist it.
2. Split eligible and supplied Memory in storage and UI.
3. Add stop words, meaningful-match thresholds, and domain-specific routers.
4. Default Imagination off outside fictional context.
5. Remove capabilities from lexical knowledge selection.
6. Parse and validate Affect before expression; pass expression an uncommitted trajectory.
7. Persist the expression profile and add the missing post-expression cancellation check.
8. Add grounded/expression fidelity checks for availability, negation, identifiers, and numbers.
9. Add deterministic tests spanning Context, Memory, Affect, cancellation, and receipts.

This slice deliberately precedes semantic/vector retrieval and model-bound tools. It establishes
honest stage boundaries first; better retrieval can then be added without hiding ownership errors.
