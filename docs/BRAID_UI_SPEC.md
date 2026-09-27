# Iris Affect–Memory–Language UI

Status: Implemented experimental slice v0.1

The interface renders three separately authoritative concerns as one inspectable braid:

- Memory experience: what happened.
- Memory cognitive semantics: what Iris thinks it means.
- Memory emotional semantics: what the experience felt like and emotionally means.
- Affect: the separate canonical eight-value state and its timestamped trajectory.

The emotional-semantic channel never owns current Affect. Historical affect attached to a
memory is context, not a replay instruction. Model language never becomes state merely by
describing learning or emotion.

## Memory lenses

Memory provides Graph, Explorer, Timeline, and Affect lenses. Channel filters use the
human-readable names Experience, Meaning, and Emotional meaning while API records retain
`experience`, `cognitive_semantic`, and `emotional_semantic`.

Graph remains a projection of canonical world state. Explorer and Timeline expose scoped
channel records. Affect displays all eight values independently, their baseline, direction,
history, and nearby emotional-semantic memories without synthesizing a single mood score.

## Retrieval

Every chat context includes Global, selected Skill scopes, active World, and active Task.
Only entries within those scopes are eligible. Eligibility is not retrieval: the context router
selects a smaller supplied set, and later bound tools may return a separate tool-retrieved set.
The captured turn context must store eligible, supplied, omitted, and tool-retrieved Memory IDs
separately so Context Used shows what the model actually received.

The complete joint vocabulary and lifecycle are defined in
[`CONTEXT_BRAID_DESIGN.md`](CONTEXT_BRAID_DESIGN.md).

## Ordinary-turn Affect boundary

Ordinary chat does not create cognitive-semantic or emotional-semantic memories. The runtime
supplies the effective canonical Affect vector to Language. The model may react from that state
and proposes exactly one complete next vector. The deterministic Affect boundary checks exact
dimensions, finite values, the `1–100` range, and the configured maximum movement per dimension.
The admitted vector, Affect history, finalized response, and canonical sequence commit in the
same SQLite transaction. A failed vector rolls the finalization back.

The two semantic channels are populated later by reflection/dreaming over experience and Affect
history. They are not mechanically manufactured during each conversation turn.
