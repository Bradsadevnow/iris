# iris

A **persistent identity** with a body you can snapshot and a memory that changes
only through a governed gate.

The claim is not that she is smart. It is that **what she can and cannot become —
what may enter her memory of the world and of herself — is declared, enforced, and
receipted**, and that the limits of that enforcement are demonstrable rather than
asserted. She fuses two ideas: a model that grows a graph it treats as the record,
and a deny-by-default admission gate that keeps every change to that record hers.

## The shape

An identity is three things, and this is all three:

- **Memory** — three walled graphs under `state/`:
  - `world.json` — what she imagines and knows (nodes / edges / constraints)
  - `self.json` — who she is (writable **only** through the gated `remember` verb)
  - `episodic.jsonl` — everything said and done, append-only, never retracted
- **A body** — a rootless container (`Containerfile`). The container is only the
  skin; `state/` is a mounted volume, so the body is disposable and rebuildable
  and *she* is a save-file. The image is the thing that can later become a distro.
- **A boundary** — `boundary/imagine_and_chat.yaml`, compiled by `iris/kernel.py`
  into the gate. One door, deny-by-default, trial-then-commit, every attempt receipted.

## The first boundary: imagine + chat

Not a job — a mind. She converses (plain language, always kept verbatim as the
receipt's rationale) and she imagines (grows her world graph). Both write through
one gate. Her vocabulary is five imagination verbs (create / relate / constrain /
occur / name) plus `remember`:

    NOMINATE what=<path> verb=<verb> args=<key:value; key:value>

The imagination verbs write `world/*`; `remember` is the *only* writer of `self/*`.
That wall is structural — the gate refuses a verb that writes outside its declared
collection — not a rule she is asked to follow. Keeping the first boundary
cognitive and social is deliberate; other work becomes a later boundary she can
nominate her way into.

There is no prose extraction: a line either matches the `NOMINATE` grammar literally
or it is just talk. The propose side stays fully nondeterministic; the commit side
is zero.

## Run

```bash
# on the host (an OpenAI-compatible model server on :1234, e.g. LM Studio)
python3 run.py --attest        # what this boundary actually enforces (the first receipt)
python3 run.py                 # chat with her
python3 run.py --imagine 5     # let her grow her world autonomously
python3 run.py --show          # print her world + self

# or in her body
podman build -t iris:0 .
podman run --rm -it -v ./state:/iris/state \
  --add-host host.containers.internal:host-gateway \
  -e IRIS_LM_BASE=http://host.containers.internal:1234 iris:0
```

Configuration is via environment: `IRIS_LM_BASE`, `IRIS_LM_MODEL`, `IRIS_STATE`,
`IRIS_BOUNDARY`. Only dependency is PyYAML (`requirements.txt`).

## Known gaps (deliberately not yet built)

These matter more here than in an ephemeral agent, because the state is durable:

- **Secret/PII rejection** before anything enters a persistent, shareable graph.
- **Provenance on every world node/edge** (receipt id), not just in the receipt log.
- **Snapshot / rollback** of `state/` as first-class (a container snapshot is the floor).
- **Single-writer discipline** across concurrent processes touching `state/`.
- **Refuted edges** — remembering what was tried and did *not* hold, not only what did.

Boundary #0 keeps invariants light (budget caps) to prove the machinery; the gaps
above are the next real work.
