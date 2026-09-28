from __future__ import annotations

import argparse
import json
import os
import random
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List

from assembler import DEFAULT_SKIN, assemble_villain, load_data
from expander import expand_card, make_stamp, resolve_lm_studio_url, save_card

HERE = Path(__file__).resolve().parent
OUTPUTS_DIR = HERE / "outputs"


def _signature_tokens(card: Dict[str, object]) -> List[str]:
    petty = card.get("petty_atrocity") or {}
    petty_profile = card.get("petty_atrocity_profile") or [petty]
    exposure = card.get("institutional_exposure") or {}
    competencies = card.get("core_competencies") or {}
    institution = card.get("institution") or {}
    macguffin = card.get("macguffin") or {}
    signifier = card.get("signifier_package") or {}
    payoff = card.get("narrative_payoff") or {}
    moral_texture = card.get("moral_texture") or {}
    sidekick = card.get("sidekick") or {}

    family = card.get("villain_family", "unknown_family")
    modifier = card.get("modifier", "unknown_modifier")
    petty_key = petty.get("key", "no_petty")
    profile_keys = [item.get("key", "no_profile_item") for item in petty_profile if isinstance(item, dict)]
    exposure_key = exposure.get("key", "no_exposure")
    competency_key = competencies.get("key", "no_competencies")
    institution_key = institution.get("key", "no_institution")
    macguffin_key = macguffin.get("key", "no_macguffin")
    signifier_key = signifier.get("key", "no_signifier")
    payoff_key = payoff.get("key", "no_payoff")
    moral_primary = moral_texture.get("primary", "no_moral_texture")
    sidekick_role = sidekick.get("role_key", "no_sidekick_role")
    sidekick_loyalty = sidekick.get("loyalty_key", "no_sidekick_loyalty")
    sidekick_task = sidekick.get("task_key", "no_sidekick_task")
    sidekick_competence = sidekick.get("competence_key", "no_sidekick_competence")
    sidekick_fold = sidekick.get("fold_key", "no_sidekick_fold")

    return [
        f"family:{family}",
        f"modifier:{modifier}",
        f"family_modifier:{family}::{modifier}",
        f"petty:{petty_key}",
        *[f"petty_profile:{key}" for key in profile_keys],
        f"petty_profile_bundle:{'::'.join(sorted(profile_keys))}",
        f"exposure:{exposure_key}",
        f"competencies:{competency_key}",
        f"institution:{institution_key}",
        f"macguffin:{macguffin_key}",
        f"payoff:{payoff_key}",
        f"signifier:{signifier_key}",
        f"sidekick_role:{sidekick_role}",
        f"sidekick_loyalty:{sidekick_loyalty}",
        f"sidekick_task:{sidekick_task}",
        f"sidekick_competence:{sidekick_competence}",
        f"sidekick_fold:{sidekick_fold}",
        f"role_loyalty:{sidekick_role}::{sidekick_loyalty}",
        f"role_task:{sidekick_role}::{sidekick_task}",
        f"role_fold:{sidekick_role}::{sidekick_fold}",
        f"task_fold:{sidekick_task}::{sidekick_fold}",
        f"sidekick_full:{sidekick_role}::{sidekick_loyalty}::{sidekick_task}::{sidekick_competence}::{sidekick_fold}",
        f"exposure_competencies:{exposure_key}::{competency_key}",
        f"petty_sidekick:{petty_key}::{sidekick_role}",
        f"moral_texture:{moral_primary}",
    ]


def _recent_counts(limit: int) -> Counter:
    counts: Counter = Counter()
    if not OUTPUTS_DIR.exists():
        return counts
    files = sorted(OUTPUTS_DIR.glob('*.json'))[-limit:]
    for path in files:
        try:
            card = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        counts.update(_signature_tokens(card))
    return counts


def _novelty_penalty(card: Dict[str, object], recent: Counter, batch: Counter) -> float:
    weights = {
        'family_modifier:': 4.5,
        'petty:': 4.0,
        'exposure:': 3.5,
        'competencies:': 3.5,
        'institution:': 2.5,
        'macguffin:': 3.0,
        'payoff:': 2.0,
        'signifier:': 1.5,
        'sidekick_role:': 5.0,
        'sidekick_loyalty:': 3.0,
        'sidekick_task:': 3.0,
        'sidekick_competence:': 2.5,
        'sidekick_fold:': 3.0,
        'role_loyalty:': 6.0,
        'role_task:': 6.0,
        'role_fold:': 5.0,
        'task_fold:': 4.0,
        'sidekick_full:': 15.0,
        'exposure_competencies:': 5.0,
        'petty_sidekick:': 4.0,
        'moral_texture:': 1.5,
    }
    score = 0.0
    tokens = _signature_tokens(card)
    for token in tokens:
        weight = 1.0
        for prefix, candidate_weight in weights.items():
            if token.startswith(prefix):
                weight = candidate_weight
                break
        score += recent[token] * weight
        score += batch[token] * weight * 3.5
    return score


def _update_counts(counter: Counter, card: Dict[str, object]) -> None:
    counter.update(_signature_tokens(card))


def _choose_card(data: Dict[str, object], rng: random.Random, skin: str, recent: Counter, batch: Counter, candidate_pool: int) -> Dict[str, object]:
    best_card = None
    best_score = None
    for _ in range(candidate_pool):
        card = assemble_villain(data, rng, skin_key=skin)
        score = _novelty_penalty(card, recent, batch)
        if best_card is None or score < best_score:
            best_card = card
            best_score = score
    assert best_card is not None
    _update_counts(batch, best_card)
    return best_card


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Build-A-Villain Workshop cards.")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--skin", type=str, default=DEFAULT_SKIN)
    parser.add_argument("--no-llm", action="store_true", help="Disable LM Studio surface generation and use scaffold-only language.")
    parser.add_argument("--llm-model", type=str, default=None)
    parser.add_argument("--lm-studio-url", type=str, default=None)
    parser.add_argument("--llm-timeout", type=int, default=180)
    parser.add_argument("--llm-max-tokens", type=int, default=1200)
    parser.add_argument("--llm-temperature", type=float, default=1.0)
    parser.add_argument("--candidate-pool", type=int, default=6, help="How many assembled villain candidates to score per output before picking the freshest one.")
    parser.add_argument("--novelty-window", type=int, default=48, help="How many recent output cards to look at when demoting repeats.")
    args = parser.parse_args()

    data = load_data()
    if args.skin not in data["skins"]:
        raise SystemExit(f"unknown skin: {args.skin}")

    rng = random.Random(args.seed)
    stamp = make_stamp()
    model = args.llm_model or os.environ.get("CHAT_MODEL_ID") or "openai/gpt-oss-20b"
    url = args.lm_studio_url or resolve_lm_studio_url()
    use_llm = not args.no_llm
    recent = _recent_counts(args.novelty_window)
    batch: Counter = Counter()

    for idx in range(args.count):
        card = _choose_card(data, rng, args.skin, recent, batch, max(1, args.candidate_pool))
        card = expand_card(
            card,
            rng,
            use_llm=use_llm,
            model=model,
            url=url,
            timeout=args.llm_timeout,
            max_tokens=args.llm_max_tokens,
            temperature=args.llm_temperature,
        )
        path = save_card(card, stamp, idx)
        print(json.dumps({
            "title": card["title"],
            "family": card["villain_family"],
            "modifier": card["modifier"],
            "skin": card["skin"],
            "sidekick": card["sidekick"]["role_key"],
            "output": str(path),
            "llm_error": (card.get("llm_surface") or {}).get("error"),
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
