#!/usr/bin/env python3
"""Wake Halcyon up.

    python3 run.py                 # chat with her (a REPL)
    python3 run.py --imagine 5     # let her grow her world autonomously, N turns
    python3 run.py --attest        # print what this boundary actually enforces, and exit
    python3 run.py --show          # print her world + self, and exit
    python3 run.py --list-identity-packs           # list the seeds/identity_packs/*.json packs
    python3 run.py --identity-pack seeds/identity_packs/engineer.json   # put on a pack (retires the current Self)

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
    print("\nhalcyon>", reply)
    c = receipt.get("claim")
    if c:
        basis = receipt["decision_basis"][-1]
        print(f"   └─ [{receipt['decision']}] {c['verb']} {json.dumps(c['args'])}  ({basis[0]}: {basis[2]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imagine", type=int, default=0, help="autonomous world-growth turns")
    ap.add_argument("--attest", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--server", action="store_true", help="run the Halcyon web server")
    ap.add_argument("--seed-profile", metavar="PATH", help="atomically merge a versioned profile seed")
    ap.add_argument("--identity-pack", metavar="PATH", help="install a Self manifest + capabilities pack (see seeds/identity_packs/)")
    ap.add_argument("--identity-pack-mode", choices=["switch", "layer"], default="switch",
                    help="switch (default): retire the current active Self first. layer: add without retiring anything")
    ap.add_argument("--list-identity-packs", action="store_true", help="list the packs under seeds/identity_packs/ and exit")
    args = ap.parse_args()

    if args.seed_profile:
        from iris.store import Store
        from iris.profile_seed import import_seed
        state_dir = os.environ.get("IRIS_STATE", "state")
        store = Store(os.environ.get("IRIS_DB", str(Path(state_dir) / "iris.db")), state_dir)
        print(json.dumps(import_seed(store, args.seed_profile), indent=2))
        return

    if args.list_identity_packs:
        from iris.identity_packs import list_packs
        print(json.dumps(list_packs(Path(__file__).parent / "seeds" / "identity_packs"), indent=2))
        return

    if args.identity_pack:
        from iris.store import Store
        from iris.identity_packs import install_identity_pack
        state_dir = os.environ.get("IRIS_STATE", "state")
        store = Store(os.environ.get("IRIS_DB", str(Path(state_dir) / "iris.db")), state_dir)
        print(json.dumps(install_identity_pack(store, args.identity_pack, args.identity_pack_mode), indent=2))
        return

    if args.server:
        import uvicorn
        port = int(os.environ.get("IRIS_PORT", "8000"))
        uvicorn.run("iris.server:app", host="127.0.0.1", port=port, reload=False)
        return

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

    print("halcyon is awake. talk to her.  (ctrl-D to let her sleep)\n")
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
