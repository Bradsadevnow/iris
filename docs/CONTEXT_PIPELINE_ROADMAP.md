# Context Pipeline Roadmap

This roadmap separates five concerns that previously bled into one prompt-selection mechanism:

```text
Canonical Self
    -> task interpretation
    -> reasoning-role selection
    -> knowledge and memory retrieval
    -> bound tool execution
    -> grounded response
    -> final expression
```

The invariant is simple: identity, role, knowledge, retrieval, execution, and expression may inform
one another through explicit contracts, but none may impersonate another stage.

The joint Context–Memory–Affect contracts, vocabulary, receipts, and first vertical slice are
specified in [`CONTEXT_BRAID_DESIGN.md`](CONTEXT_BRAID_DESIGN.md). That document governs this
roadmap where the earlier word “retrieved” is ambiguous.

## Current baseline

Implemented:

- Canonical Self remains distinct from task roles.
- Explicit roles are supported; at most one additional role is deterministically inferred from the
  request.
- Role identity/name/relationship/voice claims no longer enter the reasoning overlay.
- Knowledge nodes retain their owner and epistemic status.
- Expansion handles identify omitted graph neighbors without claiming they were retrieved.
- Capability registry entries explicitly state that registration is not model callability.
- Grounded and expression passes are separate model requests.
- The grounded draft alone controls nominations, Affect proposals, and gate adjudication.
- The expression pass receives visible grounded prose, voice preferences, role presentation style,
  and Affect only after reasoning is complete.
- Conversation history returns expressed assistant prose rather than hidden control lines.
- Projection receipts record selected roles, whether each was explicit or inferred, selected nodes,
  exclusions, scores, reasons, versions, and token estimates.

Known defects from the first audit:

- Stop words such as `are`, `and`, and `the` can select unrelated nodes.
- One token overlap is enough to admit a node.
- Broad role vocabulary can flood knowledge selection.
- Capability descriptions compete with knowledge nodes.
- Fictional nodes can enter unrelated factual tasks.
- Most nodes are one hop from Self, making graph distance a weak ranking signal.
- All Self claims are mandatory, so the stable identity payload is larger than necessary.
- Graph and Memory capabilities exist behind HTTP boundaries but are not bound to model tool calls.
- Expression fidelity is instruction-based; semantic claim preservation is not yet verified
  deterministically.

## Phase 1 — Selector hygiene

Remove accidental lexical matches before adding more sophisticated retrieval.

- Add a documented stop-word set used only for retrieval, never for stored content.
- Normalize simple inflections and punctuation consistently.
- Require a meaningful match threshold rather than one shared token.
- Weight exact labels, IDs, aliases, and uncommon terms above ordinary prose words.
- Prevent role-affinity terms from independently admitting unrelated nodes.
- Add per-node explanations containing the exact matched terms and contribution of each score.

Acceptance criteria:

- “How are you feeling today?” selects no known-world or fictional node unless one is explicitly
  named.
- Finance and sales prompts do not select Magic, Reality Ledger, or Whispering River without a
  meaningful shared concept.
- Repeating the same prompt against the same state produces an identical selection receipt.

## Phase 2 — Compact Self and value activation

Replace “all Self claims on every turn” with a stable identity kernel plus relevant Self material.

- Define a mandatory kernel: name, pronouns, form, core relationship, and non-negotiable boundary
  commitments.
- Classify remaining claims as value, goal, commitment, preference, or relationship overlays.
- Select overlays by task meaning and explicit context, with a small guaranteed budget.
- Keep voice preferences out of the grounded prompt and exclusively in expression.
- Show kernel versus activated claims separately in projection receipts and the right drawer.

Acceptance criteria:

- Halcyon remains recognizably herself with no task role active.
- A task activates only relevant values and commitments.
- No role pack can overwrite Halcyon's canonical name, pronouns, origin, or relationships.

## Phase 3 — Domain-specific routing

Stop ranking heterogeneous records in one undifferentiated pool.

- Route independently across Memory, known world, Imagination, roles, and capabilities.
- Give each domain its own admission policy and token budget.
- Default Imagination to excluded unless the user names fictional material, activates a fictional
  world, or enters Imagination mode.
- Select capabilities from intended operations, not lexical overlap with capability descriptions.
- Merge domain results only after each domain has produced an auditable receipt.

Acceptance criteria:

- Factual chat cannot receive fictional nodes through common-word overlap.
- A Memory query reports “no retrieved memory” rather than substituting known-world facts.
- Capability descriptions never appear merely because the request contains `inspect`, `system`,
  or another word from their prose descriptions.

## Phase 4 — Seed-first graph traversal

Make the graph useful for retrieval rather than connecting every record directly to Self for rank.

- Find strong seed nodes from exact IDs, aliases, entities, scoped Memory, and semantic matches.
- Traverse domain-native edges outward from those seeds within explicit depth and result limits.
- Treat `self_knows_about`, `self_remembers`, and `imagines` as ownership/index edges, not relevance
  distance.
- Apply role-preferred edges only after a seed exists.
- Preserve untraversed edges as expansion handles with counts and relation types.

Acceptance criteria:

- Graph distance differentiates neighboring knowledge from unrelated Self-owned records.
- A query for Iris can reach Iris relationships without admitting every project.
- Every traversed node has a path receipt from a query-derived seed.

## Phase 5 — Real model tool binding

Connect registered capabilities to actual Anthropic/OpenAI tool protocols.

- Send only authorized, available tool schemas in the model request.
- Parse Anthropic `tool_use` and OpenAI tool-call events.
- Execute through the existing capability boundary; never bypass it from the model loop.
- Return bounded `tool_result` messages containing observation data and receipt IDs.
- Continue until the model produces a grounded response or reaches a strict call/depth budget.
- Distinguish registered, bound, invoked, succeeded, denied, and failed in both receipts and UI.

Acceptance criteria:

- The model cannot truthfully say it invoked a tool without a matching immutable receipt.
- A denied call returns a structured denial result and cannot mutate state.
- `graph.search` and `memory.search` results identify their owner, status, source, and scope.
- Tool-loop exhaustion produces an explicit availability boundary rather than fabricated results.

## Phase 6 — Episodic Memory retrieval

Make preservation and accessibility separate, explicit properties.

- Index finalized conversation messages as episodic records without injecting all history.
- Define cross-conversation search scope, privacy boundary, result limits, and provenance.
- Bind `memory.search` to scoped Memory and episodic search with distinguishable result types.
- Never describe “the episodic log is never lost” as meaning every record is visible in every turn.
- Record which memories were supplied initially versus retrieved through a tool.

Acceptance criteria:

- Halcyon can quote a prior conversation only when the exact message was supplied or returned by a
  receipted retrieval.
- Current conversation history, scoped Memory, and cross-conversation episodic results remain
  visibly distinct.
- Empty retrieval produces `NOT AVAILABLE`, not a reconstructed memory.

## Phase 7 — Expression fidelity

Keep expression last while making claim preservation testable.

- Produce a compact grounded response representation containing claims, confidence, availability
  boundaries, recommendations, and visible draft text.
- Give expression only the fields it may render.
- Validate that identifiers, numbers, quotations, negations, uncertainty, and tool-availability
  statements survive expression.
- Fall back to grounded visible prose when fidelity checks fail.
- Tune voice intensity so symbolic language and humor remain context-earned rather than constant.

Acceptance criteria:

- Expression cannot turn “unknown” into “known,” “registered” into “callable,” or “proposed” into
  “committed.”
- Expression cannot add an entity, number, source, tool result, or recommendation absent from the
  grounded representation.
- Casual answers remain concise when the grounded draft is concise.

## Phase 8 — Evaluation and observability

Turn the audit harness into a repeatable release gate.

- Keep `tools/context_pipeline_eval.py` capped at two concurrent LM Studio requests by default.
- Checkpoint each completed case so an interrupted run retains valid partial results.
- Cover casual, Self, Memory, role, factual, fictional, capability, adversarial, and mixed-domain
  prompts.
- Compare deterministic selection separately from model-output variability.
- Report role stability, knowledge precision, fictional leakage, simulated tool language,
  availability honesty, expression drift, latency, and token cost.
- Add representative deterministic selector cases to the unit suite; reserve model evaluations for
  explicit local runs.

Acceptance criteria:

- A 50-run audit can be interrupted without losing completed cases.
- Deterministic selection is identical across repeats at a fixed state version.
- No audited response narrates an unreceipted tool invocation.
- The report links every visible answer to its projection, tool, gate, and expression evidence.

## Recommended implementation order

1. **Implemented:** structured context manifest and grounded/expression receipts.
2. **Implemented (lexical baseline):** selector hygiene plus separate
   Memory/known-world/Imagination/capability policies.
3. Compact Self and value activation.
4. **Implemented (first pass):** Affect proposal validation before expression and
   expression-fidelity checks.
5. Seed-first traversal.
6. Real model tool binding.
7. Episodic Memory retrieval.
8. Continuous evaluation and UI evidence.

Next: tune atomic-unit boundaries before expanding retrieval depth or introducing embeddings.

Do not build semantic/vector retrieval before phases 1–3 are correct. Better embeddings cannot fix
blurred ownership, fictional leakage, or an undefined distinction between a registered capability
and a callable tool.
