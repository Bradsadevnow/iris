#!/usr/bin/env python3
"""Wake Iris up.

    python3 run.py                 # chat with her (a REPL)
    python3 run.py --imagine 5     # let her grow her world autonomously, N turns
    python3 run.py --attest        # print what this boundary actually enforces, and exit
    python3 run.py --show          # print her world + self, and exit

State lives under $IRIS_STATE (default ./state). Boundary declaration is
$IRIS_BOUNDARY (default ./boundary/imagine_and_chat.yaml).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from iris.kernel import Boundary, Gate            # noqa: E402
from iris.memory import Memory                    # noqa: E402
from iris.tools import TOOLS, build_invariants    # noqa: E402
from iris import loop                             # noqa: E402


def build():
    spec = yaml.safe_load(Path(os.environ.get("IRIS_BOUNDARY", "boundary/imagine_and_chat.yaml")).read_text())
    boundary = Boundary(spec)
    memory = Memory(os.environ.get("IRIS_STATE", "state"))
    gate = Gate(boundary, memory.state, TOOLS, build_invariants(spec))
    return boundary, memory, gate


def _report(reply: str, receipt: dict) -> None:
    print("\niris>", reply)
    c = receipt.get("claim")
    if c:
        basis = receipt["decision_basis"][-1]
        print(f"   └─ [{receipt['decision']}] {c['verb']} {json.dumps(c['args'])}  ({basis[0]}: {basis[2]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imagine", type=int, default=0, help="autonomous world-growth turns")
    ap.add_argument("--attest", action="store_true")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    boundary, memory, gate = build()

    if args.attest:
        # The first receipt: the compiler stating what this instance enforces.
        print(json.dumps(boundary.attestation(), indent=2))
        return
    if args.show:
        print("# SELF\n" + memory.render_self() + "\n\n" + memory.render_world())
        return

    history: list[dict] = []

    if args.imagine:
        seed = ("Grow your world. Add something true-to-itself and connected to what is already "
                "there. Say what you are adding and why, then nominate the one change.")
        for i in range(args.imagine):
            reply, receipt = loop.turn(gate, memory, seed, history)
            _report(reply, receipt)
        return

    print("iris is awake. talk to her.  (ctrl-D to let her sleep)\n")
    while True:
        try:
            user = input("you> ").strip()
        except EOFError:
            print("\n(she sleeps — her memory is saved)")
            break
        if not user:
            continue
        reply, receipt = loop.turn(gate, memory, user, history)
        _report(reply, receipt)


if __name__ == "__main__":
    main()
