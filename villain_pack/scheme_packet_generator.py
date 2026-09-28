from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict

import yaml

from world_derivation import load_card

HERE = Path(__file__).resolve().parent
SCHEMES_PATH = HERE / "villain_schemes.yaml"
TAXONOMY_PATH = HERE / "villain_story_mechanics.yaml"
OUTPUTS_DIR = HERE / "scheme_packets"


def load_schemes() -> Dict[str, Any]:
    return yaml.safe_load(SCHEMES_PATH.read_text(encoding="utf-8"))["schemes"]


def load_taxonomy() -> Dict[str, Any]:
    return yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))["schemes"]


def choose_scheme(card: Dict[str, Any], schemes: Dict[str, Any], rng: random.Random) -> tuple[str, Dict[str, Any]]:
    family = card["villain_family"]
    compatible = [(key, value) for key, value in schemes.items() if family in value.get("family_tags", [])]
    pool = compatible or list(schemes.items())
    return rng.choice(pool)


def _pick(pool: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    return rng.choice(list(pool.values()))


def render_packet(card: Dict[str, Any], key: str, scheme: Dict[str, Any], taxonomy: Dict[str, Any], rng: random.Random) -> str:
    plot_goal = _pick(taxonomy["plot_goals"], rng)
    plot_shape = _pick(taxonomy["plot_shapes"], rng)
    betrayal = _pick(taxonomy["betrayals"], rng)
    reversal = _pick(taxonomy["reversals"], rng)
    meta_voice = rng.choice(taxonomy["meta_voice"])
    lines = [
        f"# {scheme['label']}",
        "",
        f"**Villain:** {card['title']}",
        f"**Category:** {scheme['category']}",
        f"**Phase:** {scheme['phase']}",
        f"**Target Surface:** {scheme['target']}",
        f"**Betrayal Surface:** {scheme['betrayal_surface']}",
        f"**Twist Shape:** {scheme['twist_shape']}",
        f"**Failure Condition:** {scheme['failure_condition']}",
        "",
        "## Executive Summary",
        f"- official objective smell: {plot_goal['name']}",
        f"- real engine: {plot_shape['name']}",
        f"- likely collapse point: {betrayal['name']}",
        f"- recontextualization mode: {reversal['name']}",
        f"- prize object pressure: {card['macguffin']['label']}",
        "",
        "## Why This Scheme Exists",
        (
            f"This packet assumes a villain built around {card['dramatic_function']} who prefers "
            f"{card['favorite_leverage']} and is comfortable letting {card['institutional_exposure']['label'].lower()} "
            f"do half the moral work. The scheme is less about winning cleanly than about making "
            f"{scheme['target'].lower()} feel like the only available terrain. The object at the center is "
            f"{card['macguffin']['label']}, which promises {card['macguffin']['public_myth']} while actually existing to {card['macguffin']['real_function']}."
        ),
        "",
        "## Scheme Summary",
        scheme['summary'],
        "",
        "## Story Mechanics",
        f"- plot goal: {plot_goal['name']} ({plot_goal['structural_mechanic']})",
        f"- plot shape: {plot_shape['name']} ({plot_shape['structural_mechanic']})",
        f"- betrayal mode: {betrayal['name']} ({betrayal['structural_mechanic']})",
        f"- reversal mode: {reversal['name']} ({reversal['structural_mechanic']})",
        f"- satirical garnish: {meta_voice}",
        "",
        "## Operational Moves",
    ]
    lines.extend(f"- {item}" for item in scheme['scheme_moves'])
    if scheme.get('category') == 'heist_adjacent':
        lines.extend([
            "",
            "## Heist Beats",
        ])
        lines.extend(f"- {item}" for item in taxonomy['heist_beats'])
        lines.extend([
            "",
            "## Standard Crew Roles",
        ])
        lines.extend(f"- {item}" for item in taxonomy['heist_roles'][:8])
    lines.extend([
        "",
        "## Villain Fit",
        f"- favorite leverage: {card['favorite_leverage']}",
        f"- exposure lane: {card['institutional_exposure']['label']}",
        f"- competency stack: {', '.join(card['core_competencies']['items'][:3])}",
        f"- sidekick pressure: {card['sidekick']['role_label']} handling {card['sidekick']['task_label']}",
        f"- betrayal magnet: {card['macguffin']['betrayal_magnet']}",
        "",
        "## Failure Forecast",
        f"- current failure mode already in the room: {card['failure_mode']}",
        f"- everyday tell that will probably leak first: {card['petty_atrocity']['label']}",
        f"- betrayal surface named by packet: {scheme['betrayal_surface']}",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a villain scheme packet from a villain card JSON.")
    parser.add_argument("card_json", type=str)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    card = load_card(Path(args.card_json))
    schemes = load_schemes()
    taxonomy = load_taxonomy()
    key, scheme = choose_scheme(card, schemes, rng)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS_DIR / (Path(args.card_json).stem + ".md")
    out.write_text(render_packet(card, key, scheme, taxonomy, rng), encoding="utf-8")
    print(json.dumps({"input": args.card_json, "output": str(out), "scheme": key}, ensure_ascii=False))


if __name__ == "__main__":
    main()
