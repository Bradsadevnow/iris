# Identity packs

A pack is a JSON manifest of `self_claims` (identity, values, commitments,
goals — the same shape `seeds/halcyon_identity.json` uses) plus a
`capabilities` list (the persona's declared toolkit).

**In the app, these compile into task stances.** Halcyon's own Self stays canonical and always
active. A user may select multiple packs; all manually selected profiles compose as explicit peer
stances and persist until removed. The selector may add at most one inferred support profile for a
single turn. Inferred support never persists or overrides explicit profiles.

The runtime discards pack identity/name claims during stance use and compiles the remaining material
into attributable attention priorities, reasoning principles, methods, graph preferences, and
expression guidance. Declared pack capabilities are methods, not executable tools. Known tensions
between selected profiles become explicit reasoning requirements rather than blended identities.
This writes nothing to `self_claims` or the executable capability registry.

There is also a CLI-only **permanent identity swap** path, for anyone who
wants a genuinely separate persistent identity rather than an overlay:

```bash
python3 run.py --list-identity-packs
python3 run.py --identity-pack seeds/identity_packs/engineer.json
python3 run.py --identity-pack seeds/halcyon_identity.json   # switch back
```

That path (`iris.identity_packs.install_identity_pack`) writes the pack's
claims into the real `self_claims`/`capabilities` tables — `mode="switch"`
(default) retires every other active claim first; `mode="layer"` blends
instead. It's a different, rarer use case than the UI overlay above and the
two don't interact.

## What's here

Seven packs, each synthesized fresh (not copied) from the flavor of one
division of [`msitarzewski/agency-agents`](https://github.com/msitarzewski/agency-agents)
(MIT-licensed) — used as inspiration, not as source text, so there's no
verbatim agent copy anywhere in these files:

| Pack | Persona | Drawn from |
|---|---|---|
| `engineer.json` | The Engineer | Engineering division |
| `game-developer.json` | The Game Developer | Game Development division |
| `financer.json` | The Financer | Finance division |
| `academic.json` | The Academic | Academic division (culture/geography/history/narrative/psychology) |
| `security.json` | The Security Architect | Security division |
| `strategist.json` | The Strategist | Business Strategist |
| `sales.json` | The Closer | Sales division |

None of them carry any trace of a real person's biography — they're
built to be uploaded and worked on by anyone, which is also why
`seeds/halcyon_identity.json` picked up a `name` field: it's now just
another pack, loadable and revertible the same way.

## Format

```json
{
  "id": "engineer",
  "name": "The Engineer",
  "version": 1,
  "tagline": "Every decision has a trade-off — name it.",
  "claims": [
    {"id": "self:engineer:...", "kind": "identity", "subject": "The Engineer",
     "predicate": "holds the role", "value": "..."}
  ],
  "capabilities": [
    {"id": "engineer.architecture_review", "effect_class": "observe", "description": "..."}
  ]
}
```

The identity-shaped format remains supported because these artifacts can still be installed as a
genuinely different persistent Self through the CLI. Normal UI use treats the same file as a source
bundle and compiles only its bounded stance fragments.

`kind` must be one of `identity`, `value`, `preference`, `commitment`,
`relationship`, `goal`, `self_understanding` — the same set
`Store.add_self_claim` already validates, so a pack's claims render
identically to hand-added ones everywhere the system projects Self
(`/api/system/projection`, `model_context`'s `# CANONICAL SELF CLAIMS`).

## Install semantics (`iris/identity_packs.py`)

- **`mode="switch"` (default).** Every other currently-active claim is
  retired first, then the pack's claims install as the new active Self.
  Packs are personas you put on, not traits that pile up.
- **`mode="layer"`.** Skips the retirement step, for deliberately blending
  more than one pack's claims.
- **Capabilities are always additive**, regardless of mode — installing a
  second pack never removes the first pack's tools, and none of a
  capability's own here have side effects: they declare `effect_class:
  "observe"` and exist as an inspectable catalog, same as Halcyon's three
  builtin capabilities.
- **Restart-safe.** `Store._install_identity` (which idempotently keeps
  Halcyon's own manifest current on every boot) now checks whether some
  other subject already holds the active claims and, if so, leaves it
  alone — so an installed pack survives a server restart instead of
  reverting to Halcyon on the next boot.

## Writing a new one

Copy the shape above. Keep `claims` to the identity/values/commitments/
goals/voice/relationships pattern the existing packs use — that's what
renders cleanly into `model_context`. Each `capabilities` entry is a line
in the persona's declared toolkit, not a wired tool; give it an `id`
namespaced to the pack (`<pack-id>.<verb>`) and a one-line `description`.
