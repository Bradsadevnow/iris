from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import Counter

import yaml

HERE = Path(__file__).resolve().parent
DEFAULT_SKIN = "generic"

CATEGORY_COMMONS_TARGETED = {
    "bathroom_household_desecration": {"type": "space", "scope": "shared"},
    "household_deception": {"type": "trust", "scope": "shared"},
    "borrowing_lending_crimes": {"type": "property", "scope": "personal"},
    "office_kitchen_biohazards": {"type": "food", "scope": "shared"},
    "workplace_humiliations": {"type": "time", "scope": "shared"},
    "public_space_crimes": {"type": "space", "scope": "public"},
    "public_space_table_sins": {"type": "food", "scope": "shared"},
    "digital_etiquette_crimes": {"type": "attention", "scope": "shared"},
    "institutional_douchebaggery": {"type": "infrastructure", "scope": "institutional"},
}

SANCTION_PROFILE_BY_SEVERITY = {
    "medium": {"likely_reactions": ["side_eye", "gossip", "avoidance"], "confrontation_risk": "medium"},
    "high": {"likely_reactions": ["gossip", "confrontation", "avoidance"], "confrontation_risk": "high"},
    "extreme": {"likely_reactions": ["gossip", "confrontation", "ostracism"], "confrontation_risk": "high"},
}

MORAL_TEXTURE_MODIFIER_PRESSURE = {
    "resource_selfishness": ["intimacy_parasite", "performance_genius", "inherited_heir"],
    "burden_shifting": ["false_savior", "bureaucratic_sadist", "performance_genius"],
    "bureaucratic_sadism": ["bureaucratic_sadist", "optimization_addict", "false_savior"],
    "gaslighting": ["intimacy_parasite", "false_savior", "performance_genius"],
    "queue_parasitism": ["intimacy_parasite", "performance_genius", "collapse_prophet"],
    "contamination": ["grieving_zealot", "collapse_prophet", "intimacy_parasite"],
    "time_theft": ["bureaucratic_sadist", "optimization_addict", "performance_genius"],
    "administrative_cowardice": ["bureaucratic_sadist", "false_savior", "optimization_addict"],
    "public_humiliation": ["performance_genius", "bureaucratic_sadist", "intimacy_parasite"],
    "privacy_conscripting": ["intimacy_parasite", "bureaucratic_sadist", "false_savior"],
    "performative_listening": ["false_savior", "optimization_addict", "performance_genius"],
    "civilizational_failure": ["collapse_prophet", "bureaucratic_sadist", "intimacy_parasite"],
}

MORAL_TEXTURE_FAMILY_PRESSURE = {
    "resource_selfishness": ["corporate_predator", "seductive_deceiver", "mastermind"],
    "burden_shifting": ["institutional_enforcer", "corporate_predator", "mastermind"],
    "bureaucratic_sadism": ["institutional_enforcer", "corporate_predator", "rogue_ai"],
    "gaslighting": ["seductive_deceiver", "corporate_predator", "rogue_ai"],
    "queue_parasitism": ["chaos_psychopath", "seductive_deceiver", "corporate_predator"],
    "contamination": ["monstrous_other", "hubristic_creator", "chaos_psychopath"],
    "time_theft": ["corporate_predator", "institutional_enforcer", "rogue_ai"],
    "administrative_cowardice": ["corporate_predator", "institutional_enforcer", "rogue_ai"],
    "public_humiliation": ["mastermind", "corporate_predator", "chaos_psychopath"],
    "privacy_conscripting": ["seductive_deceiver", "rogue_ai", "institutional_enforcer"],
    "performative_listening": ["corporate_predator", "rogue_ai", "hubristic_creator"],
    "civilizational_failure": ["chaos_psychopath", "rogue_ai", "mastermind"],
}


def load_yaml(name: str) -> Dict[str, Any]:
    with (HERE / name).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def choose(rng: random.Random, values: List[str]) -> str:
    return rng.choice(values)


def load_data() -> Dict[str, Any]:
    return {
        "families": load_yaml("villain_families.yaml")["families"],
        "modifiers": load_yaml("villain_modifiers.yaml")["modifiers"],
        "signifiers": load_yaml("signifier_packages.yaml")["signifiers"],
        "dialogues": load_yaml("dialogue_grammars.yaml")["dialogue_grammars"],
        "payoffs": load_yaml("payoff_patterns.yaml")["payoffs"],
        "skins": load_yaml("skins.yaml")["skins"],
        "slots": load_yaml("villain_slots.yaml")["slots"],
        "petty_atrocities": load_yaml("petty_atrocities.yaml")["petty_atrocities"],
        "institutions": load_yaml("villain_institutions.yaml")["institutions"],
        "exposures": load_yaml("villain_exposures.yaml")["exposures"],
        "competencies": load_yaml("villain_competencies.yaml")["competencies"],
        "macguffins": load_yaml("villain_macguffins.yaml")["macguffins"],
        "sidekicks": load_yaml("sidekick_parts.yaml")["sidekicks"],
    }


def titleize_key(key: str) -> str:
    return key.replace("_", " ").title()


def derive_moral_texture(petty_atrocity: Dict[str, Any]) -> Dict[str, Any]:
    tags = petty_atrocity.get("tags", [])
    primary = tags[0] if tags else petty_atrocity.get("category", "ambient_corruption")
    secondary = tags[1:3]
    category = petty_atrocity.get("category", "shared_bucket")
    severity = petty_atrocity.get("severity", "medium")
    commons_targeted = CATEGORY_COMMONS_TARGETED.get(category, {"type": "trust", "scope": "shared"})
    sanction_profile = SANCTION_PROFILE_BY_SEVERITY.get(
        severity,
        {"likely_reactions": ["gossip", "side_eye"], "confrontation_risk": "medium"},
    )
    return {
        "primary": primary,
        "secondary": secondary,
        "source": petty_atrocity.get("key"),
        "commons_targeted": commons_targeted,
        "sanction_profile": sanction_profile,
    }


def _materialize_petty_atrocity(key: str, value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": key,
        "label": value.get("label"),
        "detail": value.get("detail"),
        "category": value.get("category"),
        "severity": value.get("severity"),
        "tags": value.get("tags", []),
    }


def build_petty_atrocity_profile(
    petty_atrocities: Dict[str, Any],
    rng: random.Random,
    primary_key: str,
    *,
    count: int = 6,
) -> List[Dict[str, Any]]:
    primary = _materialize_petty_atrocity(primary_key, petty_atrocities[primary_key])
    if count <= 1:
        return [primary]

    selected = [primary]
    selected_keys = {primary_key}
    category_counts = Counter([primary["category"]])
    primary_tags = set(primary.get("tags", []))

    while len(selected) < min(count, len(petty_atrocities)):
        candidates: List[str] = []
        weights: List[float] = []
        for key, value in petty_atrocities.items():
            if key in selected_keys:
                continue
            tags = set(value.get("tags", []))
            shared_tag_count = len(primary_tags & tags)
            same_category = 1 if value.get("category") == primary.get("category") else 0
            severity_bonus = {"medium": 0.8, "high": 1.1, "extreme": 1.4}.get(value.get("severity"), 1.0)
            diversity_penalty = 1.0 + (category_counts[value.get("category")] * 1.25)
            score = (1.0 + shared_tag_count * 4.0 + same_category * 1.5 + severity_bonus) / diversity_penalty
            candidates.append(key)
            weights.append(max(score, 0.1))
        chosen = rng.choices(candidates, weights=weights, k=1)[0]
        selected_keys.add(chosen)
        materialized = _materialize_petty_atrocity(chosen, petty_atrocities[chosen])
        selected.append(materialized)
        category_counts[materialized["category"]] += 1

    return selected


def compatible_modifiers(modifiers: Dict[str, Any], family_key: str) -> Dict[str, Any]:
    return {
        key: value
        for key, value in modifiers.items()
        if family_key in value.get("compatible_families", [])
    }


def list_skin_options(data: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"key": k, "label": titleize_key(k), "detail": v.get("framing", "")} for k, v in data["skins"].items()]


def list_body_options(data: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"key": k, "label": titleize_key(k), "detail": v.get("dramatic_function", "")} for k, v in data["families"].items()]


def list_modifier_options(data: Dict[str, Any], family_key: str) -> List[Dict[str, str]]:
    return [{"key": k, "label": titleize_key(k), "detail": v.get("texture", "")} for k, v in compatible_modifiers(data["modifiers"], family_key).items()]


def list_signifier_options(data: Dict[str, Any], family_key: str) -> List[Dict[str, str]]:
    family = data["families"][family_key]
    return [{"key": k, "label": titleize_key(k), "detail": data["signifiers"][k].get("room_logic", "")} for k in family.get("signifier_tags", [])]


def list_dialogue_options(data: Dict[str, Any], family_key: str) -> List[Dict[str, str]]:
    family = data["families"][family_key]
    return [{"key": k, "label": titleize_key(k), "detail": data["dialogues"][k].get("speech_pattern", "")} for k in family.get("dialogue_tags", [])]


def list_power_source_options(data: Dict[str, Any], family_key: str) -> List[Dict[str, str]]:
    return [{"key": v, "label": v, "detail": "power source"} for v in data["families"][family_key].get("power_sources", [])]


def list_environment_options(data: Dict[str, Any], family_key: str) -> List[Dict[str, str]]:
    return [{"key": v, "label": v, "detail": "operating environment"} for v in data["families"][family_key].get("environments", [])]


def list_leverage_options(data: Dict[str, Any], family_key: str) -> List[Dict[str, str]]:
    return [{"key": v, "label": v, "detail": "favorite leverage"} for v in data["families"][family_key].get("leverage_modes", [])]


def list_justification_options(data: Dict[str, Any], family_key: str) -> List[Dict[str, str]]:
    return [{"key": v, "label": v, "detail": "self-justification"} for v in data["families"][family_key].get("justification_logics", [])]


def list_petty_atrocity_options(data: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"key": k, "label": v.get("label", k.replace("_", " ")), "detail": f"[{v.get('category', 'shared_bucket')}] {v.get('detail', '')}"} for k, v in data["petty_atrocities"].items()]


def list_exposure_options(data: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"key": k, "label": v.get("label", titleize_key(k)), "detail": v.get("summary", "")} for k, v in data["exposures"].items()]


def list_competency_options(data: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"key": k, "label": v.get("label", titleize_key(k)), "detail": ", ".join(v.get("items", [])[:2])} for k, v in data["competencies"].items()]


def list_sidekick_role_options(data: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"key": k, "label": v.get("label", titleize_key(k)), "detail": v.get("detail", "")} for k, v in data["sidekicks"]["roles"].items()]


def list_macguffin_options(data: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"key": k, "label": v.get("label", titleize_key(k)), "detail": v.get("real_function", "")} for k, v in data["macguffins"].items()]


def list_institution_options(data: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"key": k, "label": v.get("institution_name", titleize_key(k)), "detail": v.get("field_of_study", "")} for k, v in data["institutions"].items()]


def list_payoff_options(data: Dict[str, Any], family_key: str) -> List[Dict[str, str]]:
    return [{"key": k, "label": titleize_key(k), "detail": data["payoffs"][k].get("resolution", "")} for k in data["families"][family_key].get("payoff_tags", [])]


def weighted_selection(rng: random.Random, options: List[str], favored: List[str], strong_weight: int = 4, default_weight: int = 1) -> str:
    if not options:
        raise ValueError("weighted_selection requires non-empty options")
    favored_set = set(favored)
    weights = [strong_weight if option in favored_set else default_weight for option in options]
    return rng.choices(options, weights=weights, k=1)[0]


def random_selection(rng: random.Random, options: List[Dict[str, str]]) -> str:
    return choose(rng, [item["key"] for item in options])


def _favored_keys_from_tags(pool: Dict[str, Any], *tag_sets: List[List[str]]) -> List[str]:
    favored: List[str] = []
    desired = {tag for tags in tag_sets for tag in tags if tag}
    for key, value in pool.items():
        item_tags = set(value.get("tags", []))
        if item_tags & desired:
            favored.append(key)
    return favored


def pick_institution_key(data: Dict[str, Any], rng: random.Random, family_key: str, modifier_key: str, moral_texture: Dict[str, Any], institution_key: Optional[str]) -> str:
    if institution_key is not None:
        return institution_key
    favored = _favored_keys_from_tags(data["institutions"], [family_key, modifier_key, moral_texture["primary"]])
    return weighted_selection(rng, list(data["institutions"].keys()), favored, strong_weight=4, default_weight=1)


def pick_exposure_key(data: Dict[str, Any], rng: random.Random, family_key: str, modifier_key: str, moral_texture: Dict[str, Any], institution_tags: List[str], exposure_key: Optional[str]) -> str:
    if exposure_key is not None:
        return exposure_key
    favored = _favored_keys_from_tags(data["exposures"], [family_key, modifier_key, moral_texture["primary"]], institution_tags)
    return weighted_selection(rng, list(data["exposures"].keys()), favored, strong_weight=4, default_weight=1)


def pick_competency_key(data: Dict[str, Any], rng: random.Random, family_key: str, modifier_key: str, moral_texture: Dict[str, Any], institution_tags: List[str], exposure_tags: List[str], competency_key: Optional[str]) -> str:
    if competency_key is not None:
        return competency_key
    favored = _favored_keys_from_tags(data["competencies"], [family_key, modifier_key, moral_texture["primary"]], institution_tags, exposure_tags)
    return weighted_selection(rng, list(data["competencies"].keys()), favored, strong_weight=4, default_weight=1)


def pick_sidekick_role_key(data: Dict[str, Any], rng: random.Random, family_key: str, modifier_key: str, moral_texture: Dict[str, Any], exposure_tags: List[str], competency_tags: List[str], role_key: Optional[str]) -> str:
    if role_key is not None:
        return role_key
    favored = _favored_keys_from_tags(data["sidekicks"]["roles"], [family_key, modifier_key, moral_texture["primary"]], exposure_tags, competency_tags)
    return weighted_selection(rng, list(data["sidekicks"]["roles"].keys()), favored, strong_weight=4, default_weight=1)


def pick_macguffin_key(data: Dict[str, Any], rng: random.Random, family_key: str, modifier_key: str, moral_texture: Dict[str, Any], institution_tags: List[str], exposure_tags: List[str], competency_tags: List[str], macguffin_key: Optional[str]) -> str:
    if macguffin_key is not None:
        return macguffin_key
    favored = _favored_keys_from_tags(data["macguffins"], [family_key, modifier_key, moral_texture["primary"]], institution_tags, exposure_tags, competency_tags)
    return weighted_selection(rng, list(data["macguffins"].keys()), favored, strong_weight=4, default_weight=1)


def pick_sidekick_component(rng: random.Random, pool: Dict[str, Any], tags: List[str]) -> str:
    favored = _favored_keys_from_tags(pool, tags)
    return weighted_selection(rng, list(pool.keys()), favored, strong_weight=4, default_weight=1)


def build_workshop_summary(card: Dict[str, Any]) -> List[str]:
    return [
        f"{card['villain_family'].replace('_', ' ').title()} body",
        f"{card['modifier'].replace('_', ' ').title()} stuffing",
        f"{card['signifier_package']['key'].replace('_', ' ').title()} costume",
        f"{card['dialogue_grammar']['key'].replace('_', ' ').title()} voice chip",
        f"{card['power_source']} evil job",
        f"{card['justification_logic']} internal lie",
        f"{card['petty_atrocity']['label']} primary petty atrocity",
        f"{len(card['petty_atrocity_profile'])}-item rot profile",
        f"{card['moral_texture']['primary'].replace('_', ' ')} moral texture",
        f"{card['institutional_exposure']['label']} exposure lateral",
        f"{card['core_competencies']['label']} competency rubric",
        f"{card['macguffin']['label']} prize counter",
        f"{card['sidekick']['role_label']} sidekick bench",
        f"{card['institution']['institution_name']} credential counter",
        f"{card['compatibility_pressure']['modifier_bias'].replace('_', ' ').title()} compatibility pull",
        f"{card['narrative_payoff']['key'].replace('_', ' ').title()} franchise potential",
    ]


def assemble_villain(
    data: Dict[str, Any],
    rng: random.Random,
    *,
    skin_key: str = DEFAULT_SKIN,
    family_key: Optional[str] = None,
    modifier_key: Optional[str] = None,
    signifier_key: Optional[str] = None,
    dialogue_key: Optional[str] = None,
    power_source: Optional[str] = None,
    operating_environment: Optional[str] = None,
    favorite_leverage: Optional[str] = None,
    justification_logic: Optional[str] = None,
    petty_atrocity_key: Optional[str] = None,
    exposure_key: Optional[str] = None,
    competency_key: Optional[str] = None,
    sidekick_role_key: Optional[str] = None,
    macguffin_key: Optional[str] = None,
    institution_key: Optional[str] = None,
    payoff_key: Optional[str] = None,
) -> Dict[str, Any]:
    families = data["families"]
    modifiers = data["modifiers"]
    signifiers = data["signifiers"]
    dialogues = data["dialogues"]
    payoffs = data["payoffs"]
    skins = data["skins"]
    petty_atrocities = data["petty_atrocities"]
    institutions = data["institutions"]
    exposures = data["exposures"]
    competencies = data["competencies"]
    macguffins = data["macguffins"]
    sidekicks = data["sidekicks"]

    if skin_key not in skins:
        raise ValueError(f"Unknown skin: {skin_key}")

    petty_atrocity_key = petty_atrocity_key or random_selection(rng, list_petty_atrocity_options(data))
    petty_atrocity = petty_atrocities[petty_atrocity_key]
    petty_atrocity_profile = build_petty_atrocity_profile(petty_atrocities, rng, petty_atrocity_key, count=6)
    moral_texture = derive_moral_texture({"key": petty_atrocity_key, **petty_atrocity})

    if family_key is None:
        family_key = weighted_selection(rng, list(families.keys()), MORAL_TEXTURE_FAMILY_PRESSURE.get(moral_texture["primary"], []), strong_weight=3, default_weight=1)
    family = families[family_key]

    if modifier_key is None:
        modifier_options = list(compatible_modifiers(modifiers, family_key).keys())
        modifier_key = weighted_selection(rng, modifier_options, MORAL_TEXTURE_MODIFIER_PRESSURE.get(moral_texture["primary"], []), strong_weight=5, default_weight=1)
    modifier = modifiers[modifier_key]

    institution_key = pick_institution_key(data, rng, family_key, modifier_key, moral_texture, institution_key)
    institution = institutions[institution_key]

    exposure_key = pick_exposure_key(data, rng, family_key, modifier_key, moral_texture, institution.get("tags", []), exposure_key)
    exposure = exposures[exposure_key]

    competency_key = pick_competency_key(data, rng, family_key, modifier_key, moral_texture, institution.get("tags", []), exposure.get("tags", []), competency_key)
    competency = competencies[competency_key]

    macguffin_key = pick_macguffin_key(data, rng, family_key, modifier_key, moral_texture, institution.get("tags", []), exposure.get("tags", []), competency.get("tags", []), macguffin_key)
    macguffin = macguffins[macguffin_key]

    role_key = pick_sidekick_role_key(data, rng, family_key, modifier_key, moral_texture, exposure.get("tags", []), competency.get("tags", []), sidekick_role_key)
    role = sidekicks["roles"][role_key]
    sidekick_tags = [family_key, modifier_key, moral_texture["primary"], role_key] + role.get("tags", []) + exposure.get("tags", []) + competency.get("tags", [])
    loyalty_key = pick_sidekick_component(rng, sidekicks["loyalty_modes"], sidekick_tags)
    task_key = pick_sidekick_component(rng, sidekicks["task_domains"], [role_key] + role.get("tags", []))
    competence_key = pick_sidekick_component(rng, sidekicks["competence_profiles"], [role_key] + role.get("tags", []))
    fold_key = pick_sidekick_component(rng, sidekicks["fold_profiles"], [loyalty_key, competence_key, role_key] + role.get("tags", []))
    loyalty = sidekicks["loyalty_modes"][loyalty_key]
    task = sidekicks["task_domains"][task_key]
    competence_profile = sidekicks["competence_profiles"][competence_key]
    fold_profile = sidekicks["fold_profiles"][fold_key]

    signifier_key = signifier_key or random_selection(rng, list_signifier_options(data, family_key))
    signifier = signifiers[signifier_key]
    dialogue_key = dialogue_key or random_selection(rng, list_dialogue_options(data, family_key))
    dialogue = dialogues[dialogue_key]
    power_source = power_source or random_selection(rng, list_power_source_options(data, family_key))
    operating_environment = operating_environment or random_selection(rng, list_environment_options(data, family_key))
    favorite_leverage = favorite_leverage or random_selection(rng, list_leverage_options(data, family_key))
    justification_logic = justification_logic or random_selection(rng, list_justification_options(data, family_key))
    payoff_key = payoff_key or random_selection(rng, list_payoff_options(data, family_key))

    payoff = payoffs[payoff_key]
    skin = skins[skin_key]

    card = {
        "title": None,
        "skin": skin_key,
        "skin_framing": skin.get("framing"),
        "villain_family": family_key,
        "modifier": modifier_key,
        "power_source": power_source,
        "dramatic_function": family.get("dramatic_function"),
        "justification_logic": justification_logic,
        "operating_environment": operating_environment,
        "signifier_package": {
            "key": signifier_key,
            "visual_cues": signifier.get("visual_cues", []),
            "room_logic": signifier.get("room_logic"),
            "object_logic": signifier.get("object_logic"),
        },
        "dialogue_grammar": {
            "key": dialogue_key,
            "speech_pattern": dialogue.get("speech_pattern"),
            "cue_words": dialogue.get("cue_words", []),
        },
        "favorite_leverage": favorite_leverage,
        "failure_mode": modifier.get("texture"),
        "petty_atrocity": {
            "key": petty_atrocity_key,
            "label": petty_atrocity.get("label"),
            "detail": petty_atrocity.get("detail"),
            "category": petty_atrocity.get("category"),
            "severity": petty_atrocity.get("severity"),
            "tags": petty_atrocity.get("tags", []),
        },
        "petty_atrocity_profile": petty_atrocity_profile,
        "moral_texture": moral_texture,
        "institutional_exposure": {
            "key": exposure_key,
            "label": exposure.get("label"),
            "summary": exposure.get("summary"),
            "financial": exposure.get("financial"),
            "operational": exposure.get("operational"),
            "legal": exposure.get("legal"),
            "predatory": exposure.get("predatory"),
            "tags": exposure.get("tags", []),
        },
        "core_competencies": {
            "key": competency_key,
            "label": competency.get("label"),
            "summary": competency.get("summary"),
            "items": competency.get("items", []),
            "tags": competency.get("tags", []),
        },
        "macguffin": {
            "key": macguffin_key,
            "label": macguffin.get("label"),
            "artifact_class": macguffin.get("artifact_class"),
            "promise_family": macguffin.get("promise_family"),
            "stakes_scale": macguffin.get("stakes_scale"),
            "visual_form": macguffin.get("visual_form"),
            "genre_lane": macguffin.get("genre_lane"),
            "portability_band": macguffin.get("portability_band"),
            "resolution_type": macguffin.get("resolution_type"),
            "subversion_lane": macguffin.get("subversion_lane"),
            "public_myth": macguffin.get("public_myth"),
            "real_function": macguffin.get("real_function"),
            "desired_by": macguffin.get("desired_by"),
            "misread_by": macguffin.get("misread_by"),
            "activation_condition": macguffin.get("activation_condition"),
            "use_cost": macguffin.get("use_cost"),
            "containment_needs": macguffin.get("containment_needs"),
            "betrayal_magnet": macguffin.get("betrayal_magnet"),
            "plot_family_bias": macguffin.get("plot_family_bias"),
            "lair_compatibility": macguffin.get("lair_compatibility"),
            "institutional_cover_story": macguffin.get("institutional_cover_story"),
            "portability": macguffin.get("portability"),
            "custody_state": macguffin.get("custody_state"),
            "side_effects": macguffin.get("side_effects"),
            "tags": macguffin.get("tags", []),
        },
        "sidekick": {
            "role_key": role_key,
            "role_label": role.get("label"),
            "role_detail": role.get("detail"),
            "loyalty_key": loyalty_key,
            "loyalty_label": loyalty.get("label"),
            "loyalty_detail": loyalty.get("detail"),
            "task_key": task_key,
            "task_label": task.get("label"),
            "task_detail": task.get("detail"),
            "competence_key": competence_key,
            "competence_label": competence_profile.get("label"),
            "competence_detail": competence_profile.get("detail"),
            "fold_key": fold_key,
            "fold_label": fold_profile.get("label"),
            "fold_detail": fold_profile.get("detail"),
        },
        "institution": {
            "key": institution_key,
            "institution_name": institution.get("institution_name"),
            "field_of_study": institution.get("field_of_study"),
            "motto": institution.get("motto"),
            "accreditation_body": institution.get("accreditation_body"),
            "notable_alumni": institution.get("notable_alumni"),
            "registrar_voice": institution.get("registrar_voice"),
            "tags": institution.get("tags", []),
        },
        "compatibility_pressure": {
            "family_bias": family_key if family_key in MORAL_TEXTURE_FAMILY_PRESSURE.get(moral_texture["primary"], []) else (MORAL_TEXTURE_FAMILY_PRESSURE.get(moral_texture["primary"], [family_key])[0] if MORAL_TEXTURE_FAMILY_PRESSURE.get(moral_texture["primary"]) else family_key),
            "modifier_bias": modifier_key if modifier_key in MORAL_TEXTURE_MODIFIER_PRESSURE.get(moral_texture["primary"], []) else (MORAL_TEXTURE_MODIFIER_PRESSURE.get(moral_texture["primary"], [modifier_key])[0] if MORAL_TEXTURE_MODIFIER_PRESSURE.get(moral_texture["primary"]) else modifier_key),
            "exposure_bias": exposure_key,
            "competency_bias": competency_key,
            "macguffin_bias": macguffin_key,
            "sidekick_bias": role_key,
        },
        "narrative_payoff": {"key": payoff_key, "resolution": payoff.get("resolution")},
        "escalation_pattern": modifier.get("effect"),
        "portable_skin_nouns": skin.get("nouns", []),
        "portable_institutions": skin.get("institutions", []),
    }
    card["workshop"] = {
        "skin": {"station": data["slots"]["skin"]["label"], "selection": skin_key, "detail": skin.get("framing")},
        "body": {"station": data["slots"]["body"]["label"], "selection": family_key, "detail": family.get("dramatic_function")},
        "stuffing": {"station": data["slots"]["stuffing"]["label"], "selection": modifier_key, "detail": modifier.get("texture")},
        "costume": {"station": data["slots"]["costume"]["label"], "selection": signifier_key, "detail": signifier.get("room_logic")},
        "voice_chip": {"station": data["slots"]["voice_chip"]["label"], "selection": dialogue_key, "detail": dialogue.get("speech_pattern")},
        "evil_job": {"station": data["slots"]["evil_job"]["label"], "power_source": power_source, "operating_environment": operating_environment, "favorite_leverage": favorite_leverage},
        "defect": {"station": data["slots"]["defect"]["label"], "selection": justification_logic, "failure_mode": modifier.get("texture"), "escalation_pattern": modifier.get("effect")},
        "petty_atrocity": {"station": data["slots"]["petty_atrocity"]["label"], "selection": petty_atrocity.get("label"), "detail": petty_atrocity.get("detail"), "category": petty_atrocity.get("category"), "severity": petty_atrocity.get("severity"), "tags": petty_atrocity.get("tags", []), "profile_size": len(petty_atrocity_profile)},
        "exposure": {"station": data["slots"]["exposure"]["label"], "selection": exposure.get("label"), "summary": exposure.get("summary")},
        "competencies": {"station": data["slots"]["competencies"]["label"], "selection": competency.get("label"), "items": competency.get("items", [])},
        "macguffin": {"station": data["slots"]["macguffin"]["label"], "selection": macguffin.get("label"), "artifact_class": macguffin.get("artifact_class"), "promise_family": macguffin.get("promise_family"), "stakes_scale": macguffin.get("stakes_scale"), "resolution_type": macguffin.get("resolution_type"), "real_function": macguffin.get("real_function")},
        "sidekick_bench": {"station": data["slots"]["sidekick_bench"]["label"], "selection": role.get("label"), "loyalty": loyalty.get("label"), "task": task.get("label")},
        "alma_mater_of_rot": {"station": data["slots"]["alma_mater_of_rot"]["label"], "selection": institution.get("institution_name"), "field_of_study": institution.get("field_of_study"), "accreditation_body": institution.get("accreditation_body")},
        "franchise_potential": {"station": data["slots"]["franchise_potential"]["label"], "selection": payoff_key, "detail": payoff.get("resolution")},
    }
    card["assembly_receipt"] = build_workshop_summary(card)
    return card
