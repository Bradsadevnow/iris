from __future__ import annotations

import json
import os
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib import error, request

from assembler import slugify

HERE = Path(__file__).resolve().parent
OUTPUTS_DIR = HERE / "outputs"
PROMPT_TEMPLATE = HERE / "templates" / "build_a_villain_prompt.txt"

TITLE_FRAMES = [
    "The {word}",
    "A {word} For The Witnesses",
    "What {family_word} Calls Mercy",
    "How To Survive {word}",
    "The {modifier_word} {word}",
]

FALLBACK_HOOK_FRAMES = [
    "The villain is less interested in victory than in teaching the room a worse definition of normal.",
    "The real threat is not violence but the institutional permission structure surrounding it.",
    "By the time somebody names the monster correctly, the monster has already become a workflow.",
    "This build wins by making resistance feel badly formatted.",
]

OPENING_IMAGE_FRAMES = {
    "architectural_power": "An elevated room waits above everyone else, already arranged for explanation.",
    "ceremonial_luxury": "A flawless surface reflects somebody who has never apologized honestly.",
    "clean_horror": "Everything is sterilized so thoroughly it starts to feel accusatory.",
    "investor_glass": "A glass wall promises transparency while hiding exactly the right thing.",
    "ritual_procedure": "Fluorescent corridors teach you the rules before anyone speaks them aloud.",
    "mirror_logic": "A room full of reflections suggests intimacy was staged here long before you arrived.",
    "body_horror": "Something wet, living, or almost living has already crossed the category boundary.",
    "interface_glow": "Soft status lights imply care while the system quietly narrows your options.",
}

SAMPLE_LINE_FRAMES = {
    "euphemism": [
        "This will read better in the official report.",
        "You are confusing fear with pattern recognition.",
        "We can call it harm later if the rollout underperforms.",
    ],
    "fake_empathy": [
        "I hear how upsetting this is, which is why I need you to comply now.",
        "Your distress matters to us, but the process cannot pause for it.",
        "Support is available once you stop resisting the form.",
    ],
    "literal_optimization": [
        "The model is not punishing you. It is reducing noise.",
        "Mercy only looks cruel when measured from the edge case.",
        "You keep calling it control because you were never meant to see the dashboard.",
    ],
}


def resolve_lm_studio_url() -> str:
    direct = os.environ.get("LM_STUDIO_URL")
    if direct:
        return direct
    base = os.environ.get("LM_STUDIO_BASE_URL") or "http://127.0.0.1:1234/v1"
    return base.rstrip("/") + "/chat/completions"


def extract_chat_text(data: Dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("No choices in LM Studio response")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "".join(parts)
    raise RuntimeError(f"Unrecognized content payload: {content!r}")


def parse_json_object(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError("No JSON object found in model response")
    return json.loads(text[start:end + 1])


def build_scaffold_title(rng: random.Random, card: Dict[str, Any]) -> str:
    word = rng.choice(card.get("portable_skin_nouns") or [card["narrative_payoff"]["key"].replace("_", " ").title()])
    modifier_word = card["modifier"].replace("_", " ").title()
    family_word = card["villain_family"].replace("_", " ").title()
    frame = rng.choice(TITLE_FRAMES)
    return frame.format(word=word.title(), modifier_word=modifier_word, family_word=family_word)


def clean_line(text: str) -> str:
    value = text.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


def dedupe_preserve(items: List[str], fallback: List[str], limit: int) -> List[str]:
    deduped: List[str] = []
    seen = set()
    for value in items + fallback:
        cleaned = clean_line(value)
        if not cleaned or cleaned in seen:
            continue
        deduped.append(cleaned)
        seen.add(cleaned)
        if len(deduped) >= limit:
            break
    return deduped


def compact_surface_payload(card: Dict[str, Any]) -> Dict[str, Any]:
    sidekick = card["sidekick"]
    profile = card.get("petty_atrocity_profile", [card["petty_atrocity"]])
    return {
        "skin": card["skin"],
        "villain_family": card["villain_family"],
        "modifier": card["modifier"],
        "power_source": card["power_source"],
        "dramatic_function": card["dramatic_function"],
        "justification_logic": card["justification_logic"],
        "operating_environment": card["operating_environment"],
        "favorite_leverage": card["favorite_leverage"],
        "failure_mode": card["failure_mode"],
        "moral_texture": card["moral_texture"],
        "petty_atrocity": card["petty_atrocity"],
        "petty_atrocity_profile": [
            {
                "key": item["key"],
                "label": item["label"],
                "category": item["category"],
                "severity": item["severity"],
            }
            for item in profile[:6]
        ],
        "institutional_exposure": {
            "key": card["institutional_exposure"]["key"],
            "label": card["institutional_exposure"]["label"],
            "summary": card["institutional_exposure"]["summary"],
        },
        "core_competencies": {
            "key": card["core_competencies"]["key"],
            "label": card["core_competencies"]["label"],
            "summary": card["core_competencies"]["summary"],
            "items": card["core_competencies"]["items"][:4],
        },
        "macguffin": {
            "key": card["macguffin"]["key"],
            "label": card["macguffin"]["label"],
            "artifact_class": card["macguffin"]["artifact_class"],
            "promise_family": card["macguffin"]["promise_family"],
            "stakes_scale": card["macguffin"]["stakes_scale"],
            "visual_form": card["macguffin"]["visual_form"],
            "genre_lane": card["macguffin"]["genre_lane"],
            "portability_band": card["macguffin"]["portability_band"],
            "resolution_type": card["macguffin"]["resolution_type"],
            "subversion_lane": card["macguffin"]["subversion_lane"],
            "public_myth": card["macguffin"]["public_myth"],
            "real_function": card["macguffin"]["real_function"],
            "activation_condition": card["macguffin"]["activation_condition"],
            "use_cost": card["macguffin"]["use_cost"],
            "containment_needs": card["macguffin"]["containment_needs"],
            "betrayal_magnet": card["macguffin"]["betrayal_magnet"],
            "plot_family_bias": card["macguffin"]["plot_family_bias"],
        },
        "sidekick": {
            "role_label": sidekick["role_label"],
            "loyalty_label": sidekick["loyalty_label"],
            "task_label": sidekick["task_label"],
            "competence_label": sidekick["competence_label"],
            "fold_label": sidekick["fold_label"],
        },
        "institution": {
            "institution_name": card["institution"]["institution_name"],
            "field_of_study": card["institution"]["field_of_study"],
            "motto": card["institution"]["motto"],
            "accreditation_body": card["institution"]["accreditation_body"],
        },
        "narrative_payoff": card["narrative_payoff"],
        "escalation_pattern": card["escalation_pattern"],
        "signifier_package": {
            "key": card["signifier_package"]["key"],
            "room_logic": card["signifier_package"]["room_logic"],
            "object_logic": card["signifier_package"]["object_logic"],
            "visual_cues": card["signifier_package"]["visual_cues"][:4],
        },
        "dialogue_grammar": {
            "key": card["dialogue_grammar"]["key"],
            "speech_pattern": card["dialogue_grammar"]["speech_pattern"],
            "cue_words": card["dialogue_grammar"]["cue_words"][:5],
        },
    }


def fallback_surfaces(rng: random.Random, card: Dict[str, Any]) -> Dict[str, Any]:
    signifier_key = card["signifier_package"]["key"]
    dialogue_key = card["dialogue_grammar"]["key"]
    atrocity = card["petty_atrocity"]
    atrocity_profile = card.get("petty_atrocity_profile", [atrocity])
    atrocity_labels = [item["label"] for item in atrocity_profile]
    secondary_rot = ", ".join(atrocity_labels[1:4]) if len(atrocity_labels) > 1 else atrocity_labels[0]
    moral_texture = card["moral_texture"]
    institution = card["institution"]
    exposure = card["institutional_exposure"]
    competencies = card["core_competencies"]
    sidekick = card["sidekick"]
    macguffin = card["macguffin"]
    opening_image = OPENING_IMAGE_FRAMES.get(signifier_key, rng.choice(FALLBACK_HOOK_FRAMES))
    hooks = dedupe_preserve(
        [
            rng.choice(FALLBACK_HOOK_FRAMES),
            f"Even before the grand scheme, the villain was already the kind of person who would be {atrocity['label']}, and the wider rot profile includes {secondary_rot}.",
            f"The audience trusts the build less the moment they learn even the {sidekick['role_label']} is hanging around because they are {sidekick['loyalty_label']}.",
        ],
        FALLBACK_HOOK_FRAMES,
        3,
    )
    sample_lines = dedupe_preserve(
        SAMPLE_LINE_FRAMES.get(dialogue_key, []),
        [
            f"If {atrocity['label']} bothers you, wait until you hear the rest of my rot profile. Then meet my {sidekick['role_label']}",
            f"My core competencies include {competencies['items'][0]}, and my {sidekick['role_label']} handles {sidekick['task_label']}.",
            "If this sounds compassionate, you are already inside the problem.",
        ],
        3,
    )
    return {
        "title": build_scaffold_title(rng, card),
        "workshop_pitch": (
            f"You selected {card['villain_family'].replace('_', ' ').title()} plus {card['modifier'].replace('_', ' ').title()} and got a villain whose favorite workplace protection is {card['favorite_leverage']}. Their primary moral texture is {moral_texture['primary'].replace('_', ' ')}. Their exposure lateral is {exposure['label']}. Their core competency stack is {competencies['label']}. They are currently fixated on {macguffin['label']}. Their sidekick is a {sidekick['role_label']} who stays because they are {sidekick['loyalty_label']}. Their formal training comes from {institution['institution_name']}."
        ),
        "opening_image": opening_image,
        "dossier_summary": (
            f"This build runs on {card['power_source']} inside a {card['operating_environment']}. At the story level, it {card['dramatic_function']}. The primary moral texture is {moral_texture['primary'].replace('_', ' ')}. The internal lie is simple: {card['justification_logic']}. The exposure profile is {exposure['label'].lower()}, which operationalized into {competencies['label'].lower()}. The current prize object is {macguffin['label']}, publicly sold as {macguffin['public_myth']} and privately valued for its actual function: {macguffin['real_function']}. The local ecosystem includes a {sidekick['role_label']} who handles {sidekick['task_label']}. Before any grand plan begins, the daily proof of rot is {atrocity['label']}, but the full civilian rot profile also includes {secondary_rot}."
        ),
        "public_facing_bio": (
            f"Publicly, this figure presents as polished, necessary, and strangely inevitable. Privately, they are a pure engine of {moral_texture['primary'].replace('_', ' ')} shaped by {exposure['label'].lower()} and confident enough to treat {competencies['items'][0]} like a normal leadership behavior. Their chosen prize, {macguffin['label']}, lets them pretend the whole thing is about destiny instead of appetite. The {sidekick['role_label']} nearby makes the whole thing feel alarmingly maintainable."
        ),
        "internal_memo": (
            f"Internal note: continue protecting the principal from low-level reputation damage tied to {atrocity['label']}. Pattern review now includes {secondary_rot}. Their current strengths remain {', '.join(competencies['items'][:3])}. MacGuffin containment around {macguffin['label']} remains active; public language should stay with {macguffin['public_myth']}, not the actual function: {macguffin['real_function']}. The {sidekick['role_label']} remains responsible for {sidekick['task_label']} and is currently {sidekick['loyalty_label']}. Do not mention the {institution['accreditation_body']} matter in writing."
        ),
        "signature_scene": (
            f"The villain stages a scene inside the {card['operating_environment']} where {card['favorite_leverage']} briefly passes for order until the room notices too late that the real agenda is this: {card['escalation_pattern']}. At the center of the scene sits {macguffin['label']}, which claims to be {macguffin['public_myth']} but is really prized for one thing: {macguffin['real_function']}. The {sidekick['role_label']} quietly handles {sidekick['task_label']} in the background, which is why the whole thing almost works. Somewhere in the room, somebody realizes too late that the sidekick is {sidekick['competence_label']} and {sidekick['fold_label']}."
        ),
        "fake_trailer": (
            f"In a world shaped by {card['skin'].replace('_', ' ')}, one {card['villain_family'].replace('_', ' ')} build will learn that {card['narrative_payoff']['resolution'].lower()}. Exposure: {exposure['label']}. Core competencies: {competencies['items'][0]}, {competencies['items'][1]}. Prize object: {macguffin['label']}. Sidekick: {sidekick['role_label']} on {sidekick['task_label']}. Somebody is definitely {atrocity['label']} in act one, but the real warning is that the rot profile also includes {secondary_rot}."
        ),
        "sequel_slop": (
            f"Franchise extension: somebody rebuilds the same logic with fresher branding, and the receipts get harder to kill. The petty tell survives too, because evil this scalable still finds time for {atrocity['label']}. The wider rot profile survives too: {secondary_rot}. So does {macguffin['label']}, because objects like that never stay buried once institutions learn the cover story. Another {sidekick['role_label']} arrives, still {sidekick['loyalty_label']}, still handling {sidekick['task_label']}."
        ),
        "sample_lines": sample_lines,
        "hooks": hooks,
    }


def build_surface_prompt(card: Dict[str, Any]) -> str:
    template = PROMPT_TEMPLATE.read_text(encoding="utf-8")
    return template.replace("{{ASSEMBLED_VILLAIN}}", json.dumps(compact_surface_payload(card), indent=2, ensure_ascii=False))


def llm_generate_surfaces(card: Dict[str, Any], model: str, url: str, timeout: int, max_tokens: int, temperature: float) -> Dict[str, Any]:
    prompt = build_surface_prompt(card)
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": "You are a precise creative generator for a Build-A-Villain Workshop. Return only valid JSON. Keep the assembly legible and the language funny, specific, and reusable.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {os.environ.get('LM_STUDIO_API_KEY', 'lm-studio')}"}, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    return parse_json_object(extract_chat_text(json.loads(raw)))


def expand_card(card: Dict[str, Any], rng: random.Random, *, use_llm: bool, model: str, url: str, timeout: int, max_tokens: int, temperature: float) -> Dict[str, Any]:
    fallback = fallback_surfaces(rng, card)
    card.update(fallback)
    card["llm_surface"] = {"enabled": use_llm, "error": None}
    if not use_llm:
        return card
    try:
        generated = llm_generate_surfaces(card, model, url, timeout, max_tokens, temperature)
        for key in ["title", "workshop_pitch", "opening_image", "dossier_summary", "public_facing_bio", "internal_memo", "signature_scene", "fake_trailer", "sequel_slop"]:
            value = generated.get(key)
            if isinstance(value, str) and value.strip():
                card[key] = clean_line(value)
        card["sample_lines"] = dedupe_preserve([item for item in generated.get("sample_lines", []) if isinstance(item, str)], card["sample_lines"], 3)
        card["hooks"] = dedupe_preserve([item for item in generated.get("hooks", []) if isinstance(item, str)], card["hooks"], 3)
    except Exception as exc:
        card["llm_surface"]["error"] = f"{type(exc).__name__}: {exc}"
    return card


def render_markdown(card: Dict[str, Any]) -> str:
    sidekick = card["sidekick"]
    lines = [
        f"# {card['title']}",
        "",
        f"**Skin:** {card['skin']}",
        f"**Family:** {card['villain_family']}",
        f"**Modifier:** {card['modifier']}",
        f"**Power Source:** {card['power_source']}",
        f"**Dramatic Function:** {card['dramatic_function']}",
        f"**Justification Logic:** {card['justification_logic']}",
        f"**Operating Environment:** {card['operating_environment']}",
        f"**Favorite Leverage:** {card['favorite_leverage']}",
        f"**Failure Mode:** {card['failure_mode']}",
        f"**Primary Moral Texture:** {card['moral_texture']['primary'].replace('_', ' ')}",
        f"**Petty Atrocity:** {card['petty_atrocity']['label']}",
        f"**Rot Profile Size:** {len(card.get('petty_atrocity_profile', [card['petty_atrocity']]))}",
        f"**Institutional Exposure:** {card['institutional_exposure']['label']}",
        f"**Core Competencies:** {', '.join(card['core_competencies']['items'][:3])}",
        f"**Sidekick:** {sidekick['role_label']} ({sidekick['loyalty_label']})",
        f"**MacGuffin:** {card['macguffin']['label']}",
        f"**MacGuffin Promise:** {card['macguffin']['promise_family']}",
        f"**Credentialed By:** {card['institution']['institution_name']}",
        "",
        "## Build Receipt",
    ]
    lines.extend(f"- {item}" for item in card["assembly_receipt"])
    lines.extend([
        "",
        "## Workshop Pitch",
        card["workshop_pitch"],
        "",
        "## Opening Image",
        card["opening_image"],
        "",
        "## Dossier Summary",
        card["dossier_summary"],
        "",
        "## Public-Facing Bio",
        card["public_facing_bio"],
        "",
        "## Internal Memo",
        card["internal_memo"],
        "",
        "## Moral Texture",
        card["moral_texture"]["primary"],
        f"- secondary: {', '.join(card['moral_texture']['secondary']) if card['moral_texture']['secondary'] else 'none'}",
        f"- commons targeted: {card['moral_texture']['commons_targeted']['type']} / {card['moral_texture']['commons_targeted']['scope']}",
        f"- likely reactions: {', '.join(card['moral_texture']['sanction_profile']['likely_reactions'])}",
        f"- confrontation risk: {card['moral_texture']['sanction_profile']['confrontation_risk']}",
        "",
        "## Petty Atrocity",
        card["petty_atrocity"]["label"],
        f"- detail: {card['petty_atrocity']['detail']}",
        f"- category: {card['petty_atrocity']['category']}",
        f"- severity: {card['petty_atrocity']['severity']}",
        f"- tags: {', '.join(card['petty_atrocity']['tags'])}",
        "",
        "## Rot Profile",
    ])
    lines.extend(f"- petty sin: {item['label']} ({item['category']}, {item['severity']})" for item in card.get("petty_atrocity_profile", [card["petty_atrocity"]]))
    lines.extend([
        "",
        "## Institutional Exposure",
        card["institutional_exposure"]["label"],
        f"- summary: {card['institutional_exposure']['summary']}",
        f"- financial: {card['institutional_exposure']['financial']}",
        f"- operational: {card['institutional_exposure']['operational']}",
        f"- legal: {card['institutional_exposure']['legal']}",
        f"- predatory: {card['institutional_exposure']['predatory']}",
        f"- tags: {', '.join(card['institutional_exposure']['tags'])}",
        "",
        "## Core Competencies",
        card["core_competencies"]["label"],
        f"- summary: {card['core_competencies']['summary']}",
    ])
    lines.extend(f"- competency: {item}" for item in card["core_competencies"]["items"])
    lines.extend([
        f"- tags: {', '.join(card['core_competencies']['tags'])}",
        "",
        "## MacGuffin",
        card["macguffin"]["label"],
        f"- artifact class: {card['macguffin']['artifact_class']}",
        f"- promise family: {card['macguffin']['promise_family']}",
        f"- stakes scale: {card['macguffin']['stakes_scale']}",
        f"- visual form: {card['macguffin']['visual_form']}",
        f"- genre lane: {card['macguffin']['genre_lane']}",
        f"- portability band: {card['macguffin']['portability_band']}",
        f"- resolution type: {card['macguffin']['resolution_type']}",
        f"- subversion lane: {card['macguffin']['subversion_lane']}",
        f"- public myth: {card['macguffin']['public_myth']}",
        f"- real function: {card['macguffin']['real_function']}",
        f"- activation condition: {card['macguffin']['activation_condition']}",
        f"- use cost: {card['macguffin']['use_cost']}",
        f"- containment needs: {card['macguffin']['containment_needs']}",
        f"- betrayal magnet: {card['macguffin']['betrayal_magnet']}",
        f"- lair compatibility: {card['macguffin']['lair_compatibility']}",
        f"- institutional cover story: {card['macguffin']['institutional_cover_story']}",
        f"- portability: {card['macguffin']['portability']}",
        f"- custody state: {card['macguffin']['custody_state']}",
        f"- side effects: {card['macguffin']['side_effects']}",
        f"- tags: {', '.join(card['macguffin']['tags'])}",
        "",
        "## Sidekick",
        sidekick["role_label"],
        f"- role detail: {sidekick['role_detail']}",
        f"- why they stay: {sidekick['loyalty_label']}",
        f"- loyalty detail: {sidekick['loyalty_detail']}",
        f"- what they handle: {sidekick['task_label']}",
        f"- task detail: {sidekick['task_detail']}",
        f"- competence band: {sidekick['competence_label']}",
        f"- competence detail: {sidekick['competence_detail']}",
        f"- fold risk: {sidekick['fold_label']}",
        f"- fold detail: {sidekick['fold_detail']}",
        "",
        "## Fake Institution",
        card["institution"]["institution_name"],
        f"- field of study: {card['institution']['field_of_study']}",
        f"- motto: {card['institution']['motto']}",
        f"- accreditation body: {card['institution']['accreditation_body']}",
        f"- notable alumni: {card['institution']['notable_alumni']}",
        f"- registrar voice: {card['institution']['registrar_voice']}",
        f"- tags: {', '.join(card['institution']['tags'])}",
        "",
        "## Signature Scene",
        card["signature_scene"],
        "",
        "## Signifier Package",
        f"- key: {card['signifier_package']['key']}",
    ])
    lines.extend(f"- visual cue: {cue}" for cue in card["signifier_package"]["visual_cues"])
    lines.extend([
        f"- room logic: {card['signifier_package']['room_logic']}",
        f"- object logic: {card['signifier_package']['object_logic']}",
        "",
        "## Dialogue Grammar",
        f"- key: {card['dialogue_grammar']['key']}",
        f"- pattern: {card['dialogue_grammar']['speech_pattern']}",
    ])
    lines.extend(f"- cue word: {word}" for word in card["dialogue_grammar"]["cue_words"])
    lines.extend([
        "",
        "## Narrative Payoff",
        f"- key: {card['narrative_payoff']['key']}",
        f"- resolution: {card['narrative_payoff']['resolution']}",
        "",
        "## Sample Lines",
    ])
    lines.extend(f'- "{clean_line(line)}"' for line in card["sample_lines"])
    lines.extend(["", "## Hooks"])
    lines.extend(f"- {hook}" for hook in card["hooks"])
    lines.extend([
        "",
        "## Fake Trailer",
        card["fake_trailer"],
        "",
        "## Franchise Sequel Slop",
        card["sequel_slop"],
        "",
        "## Surface Generation",
        f"- enabled: {card['llm_surface'].get('enabled')}",
        f"- error: {card['llm_surface'].get('error')}",
    ])
    return "\n".join(lines) + "\n"


def save_card(card: Dict[str, Any], stamp: str, index: int) -> Path:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(card["title"])
    stem = f"{stamp}-{index:04d}-{slug}"
    json_path = OUTPUTS_DIR / f"{stem}.json"
    md_path = OUTPUTS_DIR / f"{stem}.md"
    json_path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(card), encoding="utf-8")
    return md_path


def make_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")
