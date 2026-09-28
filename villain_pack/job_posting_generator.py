from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from world_derivation import derive_company, derive_job_posting, load_card

HERE = Path(__file__).resolve().parent
OUTPUTS_DIR = HERE / "job_postings"


def render_job(job: dict, company: dict, card: dict) -> str:
    lines = [
        f"# {job['title']}",
        "",
        f"**Employer:** {job['employer']}",
        f"**Department:** {job['department']}",
        f"**Reports To:** {job['reports_to']}",
        "",
        "## Job Snapshot",
        "- this role exists because the company needs somebody to keep the lie moving without naming it",
        f"- operating context: {company['actual_function']}",
        f"- prestige wrapper: {company['mission_statement']}",
        "",
        "## Role Summary",
        (
            f"This posting sits inside a {company['sector']} environment where the stated mission is "
            f"'{company['mission_statement']}' and the actual day-to-day work is {company['actual_function']}. "
            f"The right candidate will be comfortable turning confusion into continuity around {card['macguffin']['label']}."
        ),
        "",
        "## Responsibilities",
    ]
    lines.extend(f"- {item}" for item in job['responsibilities'])
    lines.extend([
        "",
        "## Requirements",
    ])
    lines.extend(f"- {item}" for item in job['requirements'])
    lines.extend([
        "",
        "## Benefits",
    ])
    lines.extend(f"- {item}" for item in job['benefits'])
    lines.extend([
        "",
        "## Prize-Object Exposure",
        f"- current object: {card['macguffin']['label']}",
        f"- public cover story: {card['macguffin']['institutional_cover_story']}",
        f"- containment burden: {card['macguffin']['containment_needs']}",
        f"- betrayal magnet: {card['macguffin']['betrayal_magnet']}",
        "",
        "## Hiring Climate",
        f"- review environment: {company['average_employee_review']}",
        f"- leadership style: {company['leadership_style']}",
        f"- active scandal exposure: {company['ongoing_scandal']}",
        "",
        "## Why The Previous Employee Left",
        job['why_previous_employee_left'],
        "",
        "## Employer Snapshot",
        f"- sector: {company['sector']}",
        f"- mission: {company['mission_statement']}",
        f"- actual function: {company['actual_function']}",
        f"- leadership style: {company['leadership_style']}",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a villain job posting from a villain card JSON.")
    parser.add_argument("card_json", type=str)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    card = load_card(Path(args.card_json))
    company = derive_company(card, rng)
    job = derive_job_posting(card, company, rng)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS_DIR / (Path(args.card_json).stem + ".md")
    out.write_text(render_job(job, company, card), encoding="utf-8")
    print(json.dumps({"input": args.card_json, "output": str(out), "job": job['title']}, ensure_ascii=False))


if __name__ == "__main__":
    main()
