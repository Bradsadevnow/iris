# Session handoff

Dated log of what happened, in the spirit of BoneAmanita's `SESSION_HANDOFF.md`
(same author, same habit). Newest entry first. Read the latest entry before
touching any of the systems it names.

## 2026-09-26 — Graph separation, identity packs, role overlays

**RESUME HERE.** Three commits landed this session, in order, each building on
the last: `0bc74c1` → `c405430` → `c78f546`. All 23 backend tests pass
(`PYTHONPATH=.:.venv/lib/python3.12/site-packages pytest -q tests/`), frontend
typechecks and builds clean, everything below was verified against the real
running server + browser, not just unit tests.

### 1. `0bc74c1` — Imagination's world is no longer Bradley's biography

**The bug, concretely:** `iris/profile_seed.py` seeds real biography (Navy
service, work history, etc.) into `canonical_state.world_json`. Imagination's
`create`/`relate`/`constrain`/`occur`/`name` verbs *also* wrote into
`world_json` — same store. So opening Imagination showed Bradley's real
biography as the "canonical world," and a NOMINATE could in principle land a
fictional edit on top of a real fact. Brad caught this by looking at a
screenshot mid-session ("bro. that's NOT the imagination graph").

**Fix:** a second canonical store, `imagination_world_json`
(`iris/store.py`), migrated live on existing DBs. `iris/tools.py`'s five
imagination verbs now write there exclusively; `world_json` is only ever
touched by profile import. New endpoints `/api/imagination/world` +
`/api/imagination/nodes/{id}` serve the fictional graph;
`/api/world` + `/api/memory/nodes/{id}` keep serving the biography one, as
before. `iris/server.py`'s `model_context()` was split so chat sees both
(`WHAT YOU KNOW` + `THE WORLD YOU ARE IMAGINING`) while dedicated Imagination
turns omit `WHAT YOU KNOW` and the `experience`/`cognitive_semantic` Memory
channels — Brad's call: Halcyon should be able to read/nominate into the
imagined world from *any* turn, not just the Imagination view.

**Frontend:** `GraphCanvas.tsx` (new) is the domain-neutral Sigma primitive
(layout, camera, selection highlighting); `ImaginationWorldGraph.tsx` (new)
and `MemoryView.tsx`'s `MemoryGraph` both build on it but never share copy or
node taxonomy again.

**A real bug this caught, fixed in the same commit:**
`Store._install_identity` ran on *every* `Store()` construction and
unconditionally force-reactivated Halcyon's own `self_claims` — harmless
before this session, but it would have silently undone anything that ever
changed the active Self. Now skips itself if some other subject already
holds the active claims.

No alias was kept for the old `/api/memory/world` path — the one frontend
caller migrated in the same change, so there was nothing left to alias
against.

### 2. `c405430` — Identity packs (CLI-only, permanent swap)

Seven personas (`seeds/identity_packs/*.json`: Engineer, Game Developer,
Financer, Academic, Security Architect, Strategist, Closer), each a
self-contained manifest of `self_claims` + declared `capabilities`,
synthesized fresh from the *flavor* of the matching division in
`msitarzewski/agency-agents` (MIT, inspiration only — no verbatim agent text,
no personal biography in any pack, safe to open-source).

`iris/identity_packs.py`: `load_pack`/`list_packs`/`install_identity_pack`.
`run.py --identity-pack PATH` (`--identity-pack-mode switch|layer`,
`--list-identity-packs`). `mode="switch"` (default) retires every other
active claim first; `mode="layer"` blends. This is the mechanism that
exposed the `_install_identity` bug above.

**Superseded in spirit by commit 3 below** — Brad's actual product direction
turned out to be role *overlays*, not identity *swaps*. This CLI path still
works and is documented (`seeds/identity_packs/README.md`), but it has no UI
and is the rarer use case now. Don't be surprised it exists alongside a
completely different (and now primary) mechanism for the same seed files.

### 3. `c78f546` — Role overlays (the actual UI feature, built on the packs above)

Brad's spec: *"Halcyon's self always active, these are overlaid depending on
what role Hal needs to fill."* Planned via `EnterPlanMode`/`ExitPlanMode`
(plan file: `/home/unicorn-warehouse/.claude/plans/robust-wobbling-bonbon.md`
— outside the repo, in this machine's Claude Code plans directory, FYI to
whoever picks this up on a different machine).

**Design, the part worth remembering:** a role overlay writes *nothing* to
`self_claims` or `capabilities`. Which packs are "equipped" lives in
`active_context.roles` (new column, same migration pattern as
`imagination_world_json`). `model_context()` reads it and appends a
`# ACTIVE ROLE OVERLAY` prompt section per equipped pack, per request — fully
stateless, instant, reversible. A pack's `capabilities` render as
descriptive "Known methods" prose *inside that section*, not merged into the
real `capabilities` table — that table backs an actual "Run" button
(`/api/tools/execute`) in `SelfSystemView.tsx`, and pack capabilities have no
executor behind them. Merging them in would put a working-looking button in
front of something that just 404s/errors.

New: `GET /api/system/roles` (catalog), `GET /api/system/roles/{id}` (full
pack detail), `roles` field on `GET`/`PUT /api/context/active` (422 on an
unknown id — skills are filtered silently because they're free-text, roles
are a fixed catalog so a typo should surface). UI: a "Roles" section in the
chat header's `SelfDrawer` popout (quick toggle) and a full "Roles" tab in
`SelfSystemView.tsx` (card grid, expandable claims/methods per pack, fetched
lazily via the detail endpoint). Equipped roles also show as pills in
`MemoryView.tsx`'s existing scope-pills row.

**A process mistake worth naming so it doesn't repeat:** added the
`/api/system/roles/{id}` route *after* the most recent `preview_stop`/
`preview_start` cycle, kept testing in the browser, got a 404, spent a minute
confused before remembering `run.py --server` calls `uvicorn.run(...,
reload=False)`. There is no hot-reload on the backend — every `iris/*.py`
edit needs an explicit restart before the next browser check, no exceptions.
The frontend (Vite) does hot-reload; the backend does not.

### Open / not done

- The identity-pack *switch/layer* CLI path (commit 2) has no UI and no
  planned one — it's intentionally the rare path now.
- No emoji/color metadata on the pack JSON files (agency-agents personas
  have them; ours don't). Cosmetic, would make the Roles-tab cards nicer.
- Nothing wires a role overlay's presence back into `/api/self/claims`'s
  Identity tab or the Capabilities tab, by design (see "Design" above) — if
  a future ask wants role capabilities to be *actually runnable*, that's a
  real executor-wiring task, not a display change.
- BoneAmanita (`../BoneAmanita` from this repo's parent, separate git repo,
  Brad's friend Gordon's project) has its own `docs/SESSION_HANDOFF.md` with
  a freshly-added "Track E: The Halcyon Integration" entry (2026-09-26,
  unprompted by this session) planning to port `iris/store.py` +
  `iris/kernel.py` into their `cycle.py`. Discussed but not touched this
  session — Brad and Gordon are doing a separate build-off; nothing in this
  repo currently depends on that.
- `.claude/launch.json` (untracked, this machine only) runs `iris-server`
  (port 8000, `python run.py --server`) and `iris-web` (port 5173,
  `npm run dev`) via the Browser pane's `preview_start`. Recreate it if
  missing; see any of this session's tool calls for the exact JSON.
