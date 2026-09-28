from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List

import yaml


HERE = Path(__file__).resolve().parent
OUTPUTS_DIR = HERE / "institution_pages"
INSTITUTIONS_PATH = HERE / "villain_institutions.yaml"
EMPLOYER_POOL = [
    "Narrative Containment Group",
    "Hearthstone Family Governance",
    "The Institute for Managed Vulnerability",
    "Cinder Ledger Capital",
    "Aperture Enrichment Registrar",
    "Bellweather Compliance Partners",
    "Managed Outcome Holdings",
    "The Quiet Compound Collective",
    "Forecast Mercy Systems",
    "Domestic Optics Unlimited",
]
PUBLIC_REPUTATIONS = [
    "prestige-adjacent with strong placement outcomes",
    "rigorous, selective, and politely opaque",
    "beloved by people who mistake polish for ethics",
    "quietly respected in the worst possible circles",
]
HIDDEN_REPUTATIONS = [
    "produces emotionally radioactive middle management at scale",
    "teaches plausible deniability as a life skill",
    "has an alarming alumni network in containment and family governance",
    "treats leverage as a healing modality",
]
PLACEMENT_OUTCOMES = [
    "narrative containment",
    "family governance",
    "executive exception handling",
    "compliance theater",
    "crisis reframing",
    "managed vulnerability",
    "hostage-adjacent logistics",
]


def load_institutions() -> Dict[str, Any]:
    data = yaml.safe_load(INSTITUTIONS_PATH.read_text(encoding="utf-8"))
    return data["institutions"]


def render_page(key: str, institution: Dict[str, Any], rng: random.Random) -> str:
    top_employers = rng.sample(EMPLOYER_POOL, k=3)
    placements = rng.sample(PLACEMENT_OUTCOMES, k=3)
    public_rep = rng.choice(PUBLIC_REPUTATIONS)
    hidden_rep = rng.choice(HIDDEN_REPUTATIONS)
    placement_rate = rng.randint(82, 99)
    lines = [
        f"# {institution['institution_name']}",
        "",
        f"**Field of Study:** {institution['field_of_study']}",
        f"**Motto:** {institution['motto']}",
        f"**Accreditation Body:** {institution['accreditation_body']}",
        f"**Public Reputation:** {public_rep}",
        f"**Hidden Reputation:** {hidden_rep}",
        f"**Placement Rate:** {placement_rate}%",
        "",
        "## Institution Snapshot",
        f"- registrar voice: {institution['registrar_voice']}",
        f"- alignment tags: {', '.join(institution.get('tags', []))}",
        f"- institutional promise: turns {institution['field_of_study'].lower()} into a socially defensible credential",
        "",
        "## Why Applicants Apply",
        "- because they want prestige without conscience",
        "- because euphemism already feels like home",
        "- because leverage sounds better with a seal on it",
        "",
        "## Program Overview",
        (
            f"{institution['institution_name']} positions itself as a serious training ground in "
            f"{institution['field_of_study']}, with a campus tone best described as "
            f"{institution['registrar_voice']}. Its real value proposition is teaching students how to "
            f"carry status through obviously corrosive behavior without ever naming the rot directly."
        ),
        "",
        "## Notable Alumni",
        f"- {institution['notable_alumni']}",
        "",
        "## Placement Outcomes",
    ]
    lines.extend(f"- {item}" for item in placements)
    lines.extend([
        "",
        "## Top Employers",
    ])
    lines.extend(f"- {item}" for item in top_employers)
    lines.extend([
        "",
        "## Admissions Signals",
        "- demonstrated comfort with euphemism under pressure",
        "- prior evidence of ambition outrunning conscience",
        "- willingness to confuse polish with virtue",
        "",
        "## Student Experience",
        f"- public-facing campus mood: {public_rep}",
        f"- hidden campus mood: {hidden_rep}",
        f"- placement weather: {placement_rate}% of graduates land somewhere plausibly deniable",
        "",
        "## Registrar Voice",
        institution['registrar_voice'],
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate institution pages from villain institutions.")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--institution", type=str, default=None, help="Specific institution key to render.")
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    institutions = load_institutions()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.institution:
        keys: List[str] = [args.institution]
    else:
        keys = rng.sample(list(institutions.keys()), k=min(args.count, len(institutions)))

    for key in keys:
        page = render_page(key, institutions[key], rng)
        out = OUTPUTS_DIR / f"{key}.md"
        out.write_text(page, encoding="utf-8")
        print(json.dumps({"institution": key, "output": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
