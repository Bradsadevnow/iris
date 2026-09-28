from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict

import yaml

from world_derivation import derive_company, load_card

HERE = Path(__file__).resolve().parent
JOBBOARD_PATH = HERE / "villain_jobboard.yaml"
TAXONOMY_PATH = HERE / "villain_story_mechanics.yaml"
OUTPUTS_DIR = HERE / "job_board_packets"


def load_jobboard() -> Dict[str, Any]:
    return yaml.safe_load(JOBBOARD_PATH.read_text(encoding="utf-8"))


def load_taxonomy() -> Dict[str, Any]:
    return yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))["schemes"]


def _pick(pool: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    return rng.choice(list(pool.values()))


def _pick_list(pool: Dict[str, Any], key: str, rng: random.Random) -> str:
    return rng.choice(pool[key])


def render_packet(card: Dict[str, Any], company: Dict[str, Any], board: Dict[str, Any], taxonomy: Dict[str, Any], rng: random.Random) -> str:
    agenda = _pick(board['strategic_agendas'], rng)
    complication = _pick(board['structural_complications'], rng)
    contractor_class_key = rng.choice(list(board['contractor_classes'].keys()))
    contractor = _pick_list(board['contractor_classes'], contractor_class_key, rng)
    reversal_key = rng.choice(list(board['post_victory_reversal_states'].keys()))
    reversal = board['post_victory_reversal_states'][reversal_key]
    plot_shape = _pick(taxonomy['plot_shapes'], rng)
    betrayal = _pick(taxonomy['betrayals'], rng)
    meta_voice = rng.choice(taxonomy['meta_voice'])
    plot_family_key = rng.choice(list(taxonomy['plot_families'].keys()))
    plot_family = taxonomy['plot_families'][plot_family_key]
    motive_key = rng.choice(list(taxonomy['motive_clusters'].keys()))
    motive_note = taxonomy['motive_clusters'][motive_key]
    venue = rng.choice(board['venue_pool'])
    convincer = rng.choice(board['convincer_pool'])
    contingency = rng.choice(board['contingency_pool'])
    betrayal_slot = rng.choice(board['betrayal_slot_pool'])
    reveal_mechanism = rng.choice(board['reveal_mechanism_pool'])
    moral_invoice = rng.choice(board['moral_invoice_pool'])
    lines = [
        f"# {agenda['label']} Contract Posting",
        "",
        f"**Employer:** {company['name']}",
        f"**Issued By:** {card['title']}",
        f"**Target Scale:** {agenda['target_scale']}",
        f"**Capital Cost:** {agenda['asset_capital_cost']}",
        f"**Primary Required Resource:** {agenda['primary_required_resource']}",
        f"**Alignment Bias:** {agenda['systemic_alignment_bias']}",
        "",
        "## Posting Summary",
        f"- plot family: {plot_family_key.replace('_', ' ')}",
        f"- operative mood: {motive_key.replace('_', ' ')}",
        f"- likely headache: {complication['label']}",
        f"- post-success misery: {reversal_key.replace('_', ' ')}",
        f"- prize object: {card['macguffin']['label']}",
        f"- promise family: {card['macguffin']['promise_family']} / {card['macguffin']['stakes_scale']}",
        "",
        "## Opportunity Overview",
        (
            f"{company['name']} is seeking outside help for a live agenda organized around "
            f"{agenda['label'].lower()}. This is best understood as {plot_family['core_objective'].lower()}, "
            f"with enough structural cover to make the resulting disaster sound intentional. Core object pressure centers on "
            f"{card['macguffin']['label']}, sold internally as {card['macguffin']['institutional_cover_story']}."
        ),
        "",
        "## Operational Shape",
        f"- plot family: {plot_family_key.replace('_', ' ')} ({plot_family['core_objective']})",
        f"- plot shape: {plot_shape['name']} ({plot_shape['structural_mechanic']})",
        f"- likely betrayal mode: {betrayal['name']} ({betrayal['structural_mechanic']})",
        f"- motive cluster: {motive_key.replace('_', ' ')} ({motive_note})",
        f"- satirical garnish: {meta_voice}",
        "",
        "## Structural Complication",
        f"- {complication['label']}",
        f"- impact: {complication['systemic_impact']}",
        f"- lair prerequisite: {complication['lair_prerequisite']}",
        "",
        "## Plot Kit Slots",
        f"- venue: {venue}",
        f"- convincer: {convincer}",
        f"- contingency: {contingency}",
        f"- betrayal slot: {betrayal_slot}",
        f"- reveal mechanism: {reveal_mechanism}",
        f"- moral invoice: {moral_invoice}",
        "",
        "## Requested Contractor Profile",
        f"- contractor class: {contractor_class_key.replace('_', ' ')}",
        f"- immediate need: {contractor}",
        f"- must work comfortably around {card['favorite_leverage']} and {card['petty_atrocity']['label']}",
        f"- must not flinch at {card['macguffin']['containment_needs']}",
        f"- should understand likely end state: {card['macguffin']['resolution_type']}",
        "",
        "## Compensation And Risk",
        f"- compensation climate: {company['average_employee_review']}",
        f"- active scandal exposure: {company['ongoing_scandal']}",
        f"- sidekick oversight: {card['sidekick']['role_label']} handling {card['sidekick']['task_label']}",
        f"- likely management weather: {card['failure_mode']}",
        "",
        "## Post-Victory Reversal State",
        reversal,
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an underworld job-board packet from a villain card JSON.")
    parser.add_argument("card_json", type=str)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    card = load_card(Path(args.card_json))
    company = derive_company(card, rng)
    board = load_jobboard()
    taxonomy = load_taxonomy()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS_DIR / (Path(args.card_json).stem + ".md")
    out.write_text(render_packet(card, company, board, taxonomy, rng), encoding="utf-8")
    print(json.dumps({"input": args.card_json, "output": str(out), "employer": company['name']}, ensure_ascii=False))


if __name__ == "__main__":
    main()
