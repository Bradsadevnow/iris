from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from world_derivation import derive_company, derive_job_posting, load_card

HERE = Path(__file__).resolve().parent
OUTPUTS_DIR = HERE / "company_pages"


def render_company(card: dict, company: dict, jobs: list[dict]) -> str:
    mission = company['mission_statement'].rstrip('.')
    lines = [
        f"# {company['name']}",
        "",
        f"**Sector:** {company['sector']}",
        f"**Mission Statement:** {company['mission_statement']}",
        f"**Actual Function:** {company['actual_function']}",
        f"**Leadership Style:** {company['leadership_style']}",
        f"**Average Employee Review:** {company['average_employee_review']}",
        f"**Ongoing Scandal:** {company['ongoing_scandal']}",
        "",
        "## Employer Snapshot",
        f"- operating principle: {card['dramatic_function']}",
        f"- reputational weather: {card['moral_texture']['primary'].replace('_', ' ')}",
        f"- credential pipeline: {company['institution_name']}",
        f"- sidekick bench: {card['sidekick']['role_label']} handling {card['sidekick']['task_label']}",
        f"- strategic prize object: {card['macguffin']['label']}",
        "",
        "## About The Company",
        (
            f"{company['name']} presents as a {company['sector']} organization built to {mission.lower()}. "
            f"In practice it {company['actual_function']}, under a leadership culture better described as "
            f"{company['leadership_style']} than management. Current strategic obsession centers on "
            f"{card['macguffin']['label']}, which the company describes as {card['macguffin']['institutional_cover_story']}."
        ),
        "",
        "## Leadership",
        f"- principal villain: {card['title']}",
        f"- favorite leverage: {card['favorite_leverage']}",
        f"- power source: {card['power_source']}",
        f"- current tolerated rot: {card['petty_atrocity']['label']}",
        f"- protected object: {card['macguffin']['label']}",
        "",
        "## Current Openings",
    ]
    lines.extend(f"- {job['title']} ({job['department']}) -> reports to {job['reports_to']}" for job in jobs)
    lines.extend([
        "",
        "## Culture And Risk",
        f"- flagship competency: {card['core_competencies']['items'][0]}",
        f"- secondary competency: {card['core_competencies']['items'][1]}",
        f"- dominant exposure lane: {card['institutional_exposure']['label']}",
        f"- likely failure mode: {card['failure_mode']}",
        "",
        "## Employee Reality",
        f"- average review mood: {company['average_employee_review']}",
        f"- active scandal surface: {company['ongoing_scandal']}",
        f"- sidekick bottleneck: {card['sidekick']['role_label']} currently owns {card['sidekick']['task_label']}",
        f"- daily moral weather: {card['petty_atrocity']['label']}",
        f"- prize-object labor demand: {card['macguffin']['containment_needs']}",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a company page from a villain card JSON.")
    parser.add_argument("card_json", type=str)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--jobs", type=int, default=3)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    card = load_card(Path(args.card_json))
    company = derive_company(card, rng)
    jobs = [derive_job_posting(card, company, rng) for _ in range(max(1, args.jobs))]
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS_DIR / (Path(args.card_json).stem + ".md")
    out.write_text(render_company(card, company, jobs), encoding="utf-8")
    print(json.dumps({"input": args.card_json, "output": str(out), "company": company['name']}, ensure_ascii=False))


if __name__ == "__main__":
    main()
