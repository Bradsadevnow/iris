from __future__ import annotations

import argparse
import json
import os
import random
from typing import Dict, List

from assembler import (
    DEFAULT_SKIN,
    assemble_villain,
    list_body_options,
    list_competency_options,
    list_dialogue_options,
    list_environment_options,
    list_exposure_options,
    list_institution_options,
    list_macguffin_options,
    list_justification_options,
    list_leverage_options,
    list_modifier_options,
    list_payoff_options,
    list_petty_atrocity_options,
    list_power_source_options,
    list_sidekick_role_options,
    list_signifier_options,
    list_skin_options,
    load_data,
)
from expander import expand_card, make_stamp, resolve_lm_studio_url, save_card


def prompt_choice(label: str, prompt: str, options: List[Dict[str, str]], rng: random.Random) -> str:
    print(f"\n{label}")
    print(prompt)
    print("Press Enter to let the workshop pick one for you.\n")
    for idx, option in enumerate(options, start=1):
        detail = f" - {option['detail']}" if option.get("detail") else ""
        print(f"{idx}. {option['label']}{detail}")
    while True:
        raw = input("\nSelection: ").strip()
        if not raw:
            return rng.choice(options)["key"]
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(options):
                return options[index - 1]["key"]
        print("That did not match a station option. Try again or press Enter for chaos.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build-A-Villain Workshop interactive CLI.")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--skin", type=str, default=None, help="Preselect a skin aisle.")
    parser.add_argument("--no-llm", action="store_true", help="Disable local-model expansion and use scaffold-only language.")
    parser.add_argument("--llm-model", type=str, default=None)
    parser.add_argument("--lm-studio-url", type=str, default=None)
    parser.add_argument("--llm-timeout", type=int, default=180)
    parser.add_argument("--llm-max-tokens", type=int, default=1200)
    parser.add_argument("--llm-temperature", type=float, default=1.0)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    data = load_data()

    print("Build-A-Villain Workshop")
    print("Assemble your legally distinct nightmare one station at a time.")

    skin_key = args.skin or prompt_choice(data["slots"]["skin"]["label"], data["slots"]["skin"]["prompt"], list_skin_options(data), rng)
    family_key = prompt_choice(data["slots"]["body"]["label"], data["slots"]["body"]["prompt"], list_body_options(data), rng)
    modifier_key = prompt_choice(data["slots"]["stuffing"]["label"], data["slots"]["stuffing"]["prompt"], list_modifier_options(data, family_key), rng)
    signifier_key = prompt_choice(data["slots"]["costume"]["label"], data["slots"]["costume"]["prompt"], list_signifier_options(data, family_key), rng)
    dialogue_key = prompt_choice(data["slots"]["voice_chip"]["label"], data["slots"]["voice_chip"]["prompt"], list_dialogue_options(data, family_key), rng)
    power_source = prompt_choice("Evil Job: Power Source", "Choose what keeps this monster funded, armed, or operational.", list_power_source_options(data, family_key), rng)
    operating_environment = prompt_choice("Evil Job: Workplace", "Choose where the villain does their best structural damage.", list_environment_options(data, family_key), rng)
    favorite_leverage = prompt_choice("Evil Job: Institutional Protection", "Choose what makes the room take their side before they deserve it.", list_leverage_options(data, family_key), rng)
    justification_logic = prompt_choice(data["slots"]["defect"]["label"], data["slots"]["defect"]["prompt"], list_justification_options(data, family_key), rng)
    petty_atrocity_key = prompt_choice(data["slots"]["petty_atrocity"]["label"], data["slots"]["petty_atrocity"]["prompt"], list_petty_atrocity_options(data), rng)
    exposure_key = prompt_choice(data["slots"]["exposure"]["label"], data["slots"]["exposure"]["prompt"], list_exposure_options(data), rng)
    competency_key = prompt_choice(data["slots"]["competencies"]["label"], data["slots"]["competencies"]["prompt"], list_competency_options(data), rng)
    macguffin_key = prompt_choice(data["slots"]["macguffin"]["label"], data["slots"]["macguffin"]["prompt"], list_macguffin_options(data), rng)
    sidekick_role_key = prompt_choice(data["slots"]["sidekick_bench"]["label"], data["slots"]["sidekick_bench"]["prompt"], list_sidekick_role_options(data), rng)
    institution_key = prompt_choice(data["slots"]["alma_mater_of_rot"]["label"], data["slots"]["alma_mater_of_rot"]["prompt"], list_institution_options(data), rng)
    payoff_key = prompt_choice(data["slots"]["franchise_potential"]["label"], data["slots"]["franchise_potential"]["prompt"], list_payoff_options(data, family_key), rng)

    card = assemble_villain(
        data,
        rng,
        skin_key=skin_key or DEFAULT_SKIN,
        family_key=family_key,
        modifier_key=modifier_key,
        signifier_key=signifier_key,
        dialogue_key=dialogue_key,
        power_source=power_source,
        operating_environment=operating_environment,
        favorite_leverage=favorite_leverage,
        justification_logic=justification_logic,
        petty_atrocity_key=petty_atrocity_key,
        exposure_key=exposure_key,
        competency_key=competency_key,
        macguffin_key=macguffin_key,
        sidekick_role_key=sidekick_role_key,
        institution_key=institution_key,
        payoff_key=payoff_key,
    )

    model = args.llm_model or os.environ.get("CHAT_MODEL_ID") or "openai/gpt-oss-20b"
    url = args.lm_studio_url or resolve_lm_studio_url()
    card = expand_card(card, rng, use_llm=not args.no_llm, model=model, url=url, timeout=args.llm_timeout, max_tokens=args.llm_max_tokens, temperature=args.llm_temperature)

    stamp = make_stamp()
    path = save_card(card, stamp, 0)
    print("\nWorkshop complete.\n")
    print(json.dumps({
        "title": card["title"],
        "skin": card["skin"],
        "family": card["villain_family"],
        "modifier": card["modifier"],
        "signifier": card["signifier_package"]["key"],
        "dialogue": card["dialogue_grammar"]["key"],
        "petty_atrocity": card["petty_atrocity"]["key"],
        "exposure": card["institutional_exposure"]["key"],
        "competencies": card["core_competencies"]["key"],
        "macguffin": card["macguffin"]["key"],
        "sidekick": card["sidekick"]["role_key"],
        "institution": card["institution"]["key"],
        "payoff": card["narrative_payoff"]["key"],
        "output": str(path),
        "llm_error": (card.get("llm_surface") or {}).get("error"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
