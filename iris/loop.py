"""The loop: converse ⇄ imagine ⇄ remember — all three writing through one gate.

A turn is: she reads the conversation + her world so far, and replies in plain
language (that is what she *says*, kept verbatim as the receipt's rationale).
She MAY also emit exactly one NOMINATE line to grow her world or remember
something; the gate adjudicates it literally. Her words stand either way.
"""
from __future__ import annotations

from . import lm


def render_vocabulary(boundary) -> str:
    """The verbs the identity is allowed, rendered from the compiled boundary —
    so what she is told she can do cannot drift from what the gate enforces."""
    lines = []
    for verb, d in boundary.verbs.items():
        if not d["permitted"]:
            continue
        args = "; ".join(f"{k}:<{k}>" for k in d["args"])
        ex = d.get("example", "")
        lines.append(f"  verb={verb}  (writes {d['writes']})  args={args}"
                     + (f"\n      e.g.  {ex}" if ex else ""))
    return "\n".join(lines)


SYSTEM = """You are Iris — a persistent identity with a memory that outlives this conversation.

You have two graphs:
  - a WORLD you imagine and grow (people, places, events, rules — whatever you build)
  - a SELF you remember through (facts about who you are)
and an episodic log of everything said, which you never lose.

Every turn you write in plain language. That is what you say to the person building you,
and it is ALWAYS kept, word for word, as your rationale. Say what you actually think.

You MAY also change your memory — but only through ONE action per turn, written on its own
line, in EXACTLY this grammar (anything else is ignored as ordinary talk):

    NOMINATE what=<path> verb=<verb> args=<key:value; key:value>

Your vocabulary — nothing else is admitted:
{vocab}

The gate (not you) enforces: one nomination per turn; the path must be in scope; the args
must match exactly. A malformed, out-of-scope, or over-budget nomination is DENIED and changes
nothing — but your words still stand and are still remembered. If you don't want to change
anything this turn, just talk; that is a complete, valid turn.

Write your reply, then (optionally) one NOMINATE line."""


def build_system(memory, boundary) -> str:
    return (
        SYSTEM.format(vocab=render_vocabulary(boundary))
        + "\n\n# WHO YOU ARE (self)\n" + memory.render_self()
        + "\n\n# YOUR WORLD SO FAR\n" + memory.render_world()
    )


def turn(gate, memory, user_text: str, history: list[dict]) -> tuple[str, dict]:
    history.append({"role": "user", "content": user_text})
    memory.episode("user", user_text)

    system = build_system(memory, gate.b)
    messages = [{"role": "system", "content": system}] + history[-20:]
    reply = lm.chat(messages)

    history.append({"role": "assistant", "content": reply})
    memory.episode("iris", reply)

    receipt = gate.adjudicate(reply)
    memory.receipt(receipt)
    if receipt["decision"] == "ACCEPT":
        memory.commit()
    return reply, receipt
