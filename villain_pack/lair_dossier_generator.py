from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict

import yaml

from world_derivation import load_card

HERE = Path(__file__).resolve().parent
LAIRS_PATH = HERE / "villain_lairs.yaml"
TAXONOMY_PATH = HERE / "villain_story_mechanics.yaml"
OUTPUTS_DIR = HERE / "lair_dossiers"


def load_lairs() -> Dict[str, Any]:
    return yaml.safe_load(LAIRS_PATH.read_text(encoding="utf-8"))["lairs"]


def load_taxonomy() -> Dict[str, Any]:
    return yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))["lairs"]


def choose_lair(card: Dict[str, Any], lairs: Dict[str, Any], rng: random.Random) -> tuple[str, Dict[str, Any]]:
    family = card["villain_family"]
    compatible = [(key, value) for key, value in lairs.items() if family in value.get("family_tags", [])]
    pool = compatible or list(lairs.items())
    return rng.choice(pool)


def render_dossier(card: Dict[str, Any], key: str, lair: Dict[str, Any], taxonomy: Dict[str, Any], rng: random.Random) -> str:
    features = rng.sample(list(taxonomy['features'].values()), k=3)
    functions = rng.sample(list(taxonomy['story_functions'].values()), k=2)
    meta_voice = rng.choice(taxonomy['meta_voice'])
    architecture_grammar = taxonomy.get('architecture_grammar', [])
    function_axes = taxonomy.get('function_axes', [])
    lines = [
        f"# {lair['label']}",
        "",
        f"**Villain:** {card['title']}",
        f"**Category:** {lair['category']}",
        f"**Property Type:** {lair['property_type']}",
        f"**Location Vibe:** {lair['location_vibe']}",
        f"**Access Pattern:** {lair['access_pattern']}",
        f"**Defense Logic:** {lair['defense_logic']}",
        f"**Hospitality Cover:** {lair['hospitality_cover']}",
        f"**Primary Vulnerability:** {lair['vulnerability']}",
        "",
        "## Site Snapshot",
        f"- shell type: {lair['property_type']}",
        f"- worldview pressure: {lair['summary']}",
        f"- likely petty tell in space: {card['petty_atrocity']['label']}",
        f"- resident prize object: {card['macguffin']['label']}",
        f"- object scale: {card['macguffin']['stakes_scale']} / {card['macguffin']['visual_form']}",
        "",
        "## Site Read",
        (
            f"This lair works because it turns {lair['location_vibe']} into infrastructure. "
            f"Its main spatial lie is that {lair['hospitality_cover'].lower()}, while the real operating logic "
            f"is {lair['defense_logic']}. The site is most persuasive when visitors start treating "
            f"{card['favorite_leverage']} like architecture instead of behavior. It is especially good at making "
            f"{card['macguffin']['label']} feel inevitable rather than chosen."
        ),
        "",
        "## Lair Summary",
        lair['summary'],
        "",
        "## Functional Features",
    ]
    lines.extend(f"- {item['name']}: {item['structural_mechanic']}" for item in features)
    lines.extend([
        "",
        "## Spatial Grammar",
    ])
    lines.extend(f"- {item}" for item in architecture_grammar)
    lines.extend([
        "",
        "## Evaluation Axes",
    ])
    lines.extend(f"- {item}" for item in function_axes)
    lines.extend([
        "",
        "## Story-Function Logic",
    ])
    lines.extend(f"- {item['name']}: {item['structural_mechanic']}" for item in functions)
    lines.extend([
        "",
        "## Prize-Object Fit",
        f"- public myth: {card['macguffin']['public_myth']}",
        f"- containment needs: {card['macguffin']['containment_needs']}",
        f"- activation condition: {card['macguffin']['activation_condition']}",
        f"- betrayal magnet: {card['macguffin']['betrayal_magnet']}",
        f"- likely end state: {card['macguffin']['resolution_type']}",
        "",
        "## Access And Hospitality",
        f"- access pattern: {lair['access_pattern']}",
        f"- hospitality cover: {lair['hospitality_cover']}",
        f"- primary vulnerability: {lair['vulnerability']}",
        "",
        "## Meta Voice",
        meta_voice,
        "",
        "## Villain Fit",
        f"- operating environment echo: {card['operating_environment']}",
        f"- signifier logic: {card['signifier_package']['room_logic']}",
        f"- favorite leverage: {card['favorite_leverage']}",
        f"- sidekick traffic: {card['sidekick']['role_label']} on {card['sidekick']['task_label']}",
        f"- tolerated everyday rot nearby: {card['petty_atrocity']['label']}",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a villain lair dossier from a villain card JSON.")
    parser.add_argument("card_json", type=str)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    card = load_card(Path(args.card_json))
    lairs = load_lairs()
    taxonomy = load_taxonomy()
    key, lair = choose_lair(card, lairs, rng)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS_DIR / (Path(args.card_json).stem + ".md")
    out.write_text(render_dossier(card, key, lair, taxonomy, rng), encoding="utf-8")
    print(json.dumps({"input": args.card_json, "output": str(out), "lair": key}, ensure_ascii=False))


if __name__ == "__main__":
    main()
