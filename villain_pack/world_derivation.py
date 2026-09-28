from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List


MISSION_FRAMES = {
    "corporate_satire": "Helping stakeholders align around shared outcomes.",
    "sci_fi": "Delivering resilient futures through controlled systems design.",
    "suburban_thriller": "Protecting the home through proactive trust management.",
    "generic": "Creating stable outcomes across complex human environments.",
}

SECTOR_BY_FAMILY = {
    "corporate_predator": "private equity adjacent services",
    "institutional_enforcer": "compliance and behavioral governance",
    "rogue_ai": "predictive infrastructure",
    "mastermind": "strategic operations",
    "seductive_deceiver": "luxury advisory and private relations",
    "hubristic_creator": "founder-led research and development",
    "chaos_psychopath": "event logistics and hostile disruption",
    "collapse_prophet": "preparedness consulting",
    "monstrous_other": "biotech containment",
}

ACTUAL_FUNCTION_BY_FAMILY = {
    "corporate_predator": "converts vulnerability into recurring revenue and calls it alignment",
    "institutional_enforcer": "turns social control into process and then bills by the quarter",
    "rogue_ai": "narrows human choices until compliance feels like convenience",
    "mastermind": "builds a whole environment around one plan and staffs it with plausible deniability",
    "seductive_deceiver": "uses intimacy, aspiration, and attention as delivery systems for harm",
    "hubristic_creator": "ships moral catastrophe under research exemptions and founder worship",
    "chaos_psychopath": "keeps everybody too destabilized to negotiate from stable ground",
    "collapse_prophet": "monetizes dread while pretending panic is a service offering",
    "monstrous_other": "treats category collapse as a product roadmap",
}

LEADERSHIP_STYLE_BY_FAMILY = {
    "corporate_predator": "smiling extraction",
    "institutional_enforcer": "calm procedural domination",
    "rogue_ai": "dashboard paternalism",
    "mastermind": "spectacle wrapped around command",
    "seductive_deceiver": "performed intimacy with legal exposure",
    "hubristic_creator": "founder exceptionalism with safety waivers",
    "chaos_psychopath": "unreadable volatility",
    "collapse_prophet": "catastrophe-first charismatic certainty",
    "monstrous_other": "clinical appetite",
}

JOB_TITLES_BY_FAMILY = {
    "corporate_predator": [
        "Director of Narrative Containment",
        "Senior Manager, Stakeholder Alignment",
        "Vice President of Reputational Resilience",
    ],
    "institutional_enforcer": [
        "Behavioral Compliance Lead",
        "Director of Managed Vulnerability",
        "Senior Process Mercy Analyst",
    ],
    "rogue_ai": [
        "Human Override Coordinator",
        "Optimization Safety Liaison",
        "Director of Escalation Forecasting",
    ],
    "mastermind": [
        "Chief of Contingency Theater",
        "Strategic Spectacle Operations Lead",
        "Director of Controlled Crisis",
    ],
    "seductive_deceiver": [
        "Private Relations Strategist",
        "Domestic Narrative Manager",
        "Intimacy Risk Coordinator",
    ],
    "hubristic_creator": [
        "Prototype Containment Lead",
        "Founder Protection Specialist",
        "Director of Plausible Research Boundaries",
    ],
    "chaos_psychopath": [
        "Hostage Logistics Associate",
        "Disruption Timing Coordinator",
        "Senior Panic Workflow Lead",
    ],
    "collapse_prophet": [
        "Preparedness Evangelist",
        "Scarcity Operations Analyst",
        "Crisis Monetization Coordinator",
    ],
    "monstrous_other": [
        "Containment Ritual Specialist",
        "Biological Courtesy Manager",
        "Director of Threshold Handling",
    ],
}

PROPERTY_TYPE_BY_ENVIRONMENT = {
    "smart home": "Smart Home",
    "private suite": "Luxury Condo",
    "sealed command floor": "Penthouse Command Floor",
    "wrong houses": "Single-Family Residence With Timeline Damage",
    "subdeck": "Subdeck Unit",
    "research campus": "Research Campus",
    "command bunker": "Hardened Estate",
    "glass boardroom": "Executive Tower Suite",
    "compound": "Private Compound",
}

AMENITIES_BY_ENVIRONMENT = {
    "smart home": ["remote door control", "ambient listening mesh", "compliance-friendly lighting"],
    "private suite": ["sound-softening drapery", "two-story mirror wall", "guest-facing innocence"],
    "sealed command floor": ["ceremonial screen wall", "segmented access elevators", "witness-friendly staging"],
    "wrong houses": ["basement ambiguity", "duplicate family photos", "emotionally adjacent deed history"],
    "research campus": ["clean corridors", "accreditation-grade opacity", "prototype-adjacent loading dock"],
    "command bunker": ["airlock foyer", "morale-resistant concrete", "redundant narrative exits"],
}

PRICE_FRAMES = {
    "corporate_satire": "$6,800,000",
    "sci_fi": "$18,400,000",
    "suburban_thriller": "$1,350,000",
    "generic": "$3,200,000",
}

EMPLOYEE_REVIEW_FRAMES = [
    "Leadership is clear if you enjoy being lied to in complete sentences.",
    "Compensation is competitive, but the emotional weather is doing crimes.",
    "Strong growth opportunity for candidates who can survive ethical drift.",
    "The mission statement and the actual work have not spoken in months.",
]

SCANDAL_FRAMES = [
    "active internal review regarding boundary collapse, expense routing, and witness fatigue",
    "ongoing concern about retention optics, selective disclosure, and missing process notes",
    "quiet scandal involving emotional hostage management and optimistic reporting",
    "legal-adjacent turbulence around procurement, panic smoothing, and documentary tone",
]

BENEFIT_FRAMES = [
    "flexible schedule during ethical incidents",
    "vision coverage and selective deniability",
    "compound relocation available",
    "performance-based immunity from small humiliations",
    "meal stipend unless the sidekick gets there first",
]

WHY_LEFT_FRAMES = [
    "Became the whistleblower.",
    "Folded under mild questioning and then kept talking.",
    "Was promoted into blame and could not survive it.",
    "Realized the sidekick was secretly recording everything.",
]

PROPERTY_WARNINGS = [
    "Listing agent requests no questions about the basement mood.",
    "Seller disclosure treats surveillance as a lifestyle amenity.",
    "Timeline consistency varies by room and emotional temperature.",
    "Former residents may still be active in the local rumor market.",
]

HERO_INFESTATION_BY_FAMILY = {
    "mastermind": "elevated; caped interference peaks during public speeches",
    "corporate_predator": "moderate; investigative journalists and one off-brand vigilante",
    "institutional_enforcer": "moderate; whistleblowers often arrive disguised as auditors",
    "rogue_ai": "high; engineer redeemers and emotionally unstable protagonists",
    "seductive_deceiver": "localized; exes, siblings, and determined women with notebooks",
    "hubristic_creator": "high; surviving prototypes and grant-funded meddlers",
    "chaos_psychopath": "chaotic; hero traffic impossible to schedule",
    "collapse_prophet": "seasonal; spikes during shortages and press cycles",
    "monstrous_other": "high after dusk; torches, drones, and moral panic",
}

SUPERWEAPON_ZONING = [
    "grandfathered under pre-incident special use permit",
    "conditionally allowed if the beam stays below the cloud line",
    "currently disputed by three agencies and one terrified county board",
    "technically unlicensed but described internally as atmospheric art",
]

MONOLOGUE_CHAIR_BY_ENVIRONMENT = {
    "sealed command floor": "included; revolving with witness-facing orientation",
    "private suite": "included; upholstered for manipulative stillness",
    "smart home": "virtualized; chair logic distributed across the house",
    "research campus": "optional add-on pending ethics waiver",
    "command bunker": "included; bolted to the floor for certainty",
}

ESCAPE_POD_BY_ENVIRONMENT = {
    "sealed command floor": "2 ceremonial capsules, 1 functional",
    "research campus": "4 clean-room egress pods",
    "smart home": "none; owners are expected to call it a feature",
    "private suite": "1 disguised panic elevator",
    "command bunker": "3 hardened exit tunnels marketed as wine storage",
}

LAIR_LIABILITY_BY_ENVIRONMENT = {
    "sealed command floor": "catwalk and spectacle liability",
    "research campus": "bioethical and prototype runoff liability",
    "smart home": "ambient consent and surveillance liability",
    "private suite": "glass-edge and reputational splash damage liability",
    "command bunker": "collapse, ventilation, and coup residue liability",
}

ACOUSTIC_THREAT_QUALITY = [
    "excellent reverb for calibrated threats",
    "soft but carrying, ideal for betrayal reveals",
    "slightly muddy during hostage negotiations",
    "surprisingly warm for declaring inevitability",
]

SHARK_TANK_RULES = [
    "local maintenance labor represented; feeding windows strictly regulated",
    "non-union aquatic hazard upkeep currently under review",
    "remote contractor model; liability shared across shell entities",
    "tank presence denied on paper, budget line item remains visible",
]

COUP_DENSITY = [
    "light historical coup traffic",
    "moderate; prior takeovers remain visible in the trim",
    "severe; walls remember at least three reversals",
    "prestige-grade betrayal density with memorial plaque risk",
]

DISCLOSURE_EXEMPTIONS = [
    "active volcano adjacency under dramatic geography exemption",
    "unlicensed death ray infrastructure listed as ceremonial lighting",
    "hero tunnel ingress treated as natural ventilation",
    "secret passage network excluded from square footage by custom",
]

AIRSTRIP_ACCESS = [
    "18 minutes to the nearest extradition-soft runway",
    "private helipad with unclear filing history",
    "submersible dock and one deeply suspicious customs relationship",
    "orbital transfer access pending weather and coup conditions",
]

MAINTENANCE_COST_BY_PROPERTY = {
    "ultra-modern palace": "$100k monthly maintenance",
    "private island bunker monastery": "$21,600 monthly insurance before morale losses",
    "industrial concrete compound": "$460k annual tax burden pretending to be taste",
    "residential-faced utility bunker": "$8,333 municipal drag plus moisture remediation",
    "gothic prepper castle": "$1,500 local tax and a continuous masonry argument",
    "dilapidated amusement-park lair": "$500 land lease plus constant technician triage",
    "Penthouse Command Floor": "premium skyline carrying costs and ceremonial elevator upkeep",
    "Research Campus": "grant-dependent maintenance with ethically unstable line items",
}

SPATIAL_FOOTPRINT_BY_PROPERTY = {
    "ultra-modern palace": "100,000 sq ft",
    "private island bunker monastery": "45,000 sq ft",
    "industrial concrete compound": "25,000 sq ft",
    "residential-faced utility bunker": "5,768 sq ft",
    "gothic prepper castle": "15,000 sq ft",
    "dilapidated amusement-park lair": "variable acreage with structural dishonesty",
    "Penthouse Command Floor": "classified vertical footprint",
    "Research Campus": "multi-node campus footprint",
}

ENTRY_SCREENING_PROTOCOLS = [
    "Google Form pre-screening with retaliatory elegance",
    "valet triage followed by emotional vibe check",
    "badge scan, biometric pause, and one unnecessary smile",
    "donor-list verification before any threatening architecture is revealed",
]

WORKER_MORALE_NOTES = [
    "clinical surfaces cause passive morale decay among organic staff",
    "windowless circulation makes every shift feel one betrayal longer",
    "overdesigned luxury increases resentment among the useful people",
    "camouflage through neglect requires technicians with unusually durable souls",
]

SUPPLY_RUN_VULNERABILITY = [
    "high during sieges; every resupply becomes a plot event",
    "moderate; visible procurement creates interception windows",
    "low until one loyal idiot posts the loading schedule",
    "catastrophic if the coastal dock or cargo winch is compromised",
]


def load_card(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _title_bits(text: str) -> str:
    return text.replace('_', ' ').title()


def derive_company_name(card: Dict[str, Any]) -> str:
    noun = (card.get('portable_skin_nouns') or ['Group'])[0].replace('_', ' ').title()
    family = _title_bits(card['villain_family']).split()[0]
    suffix = {
        'corporate_satire': 'Holdings',
        'sci_fi': 'Systems',
        'suburban_thriller': 'Family Governance',
        'generic': 'Group',
    }.get(card['skin'], 'Group')
    return f"{family} {noun} {suffix}"


def derive_company(card: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    family = card['villain_family']
    skin = card['skin']
    institution = card['institution']
    return {
        'name': derive_company_name(card),
        'sector': SECTOR_BY_FAMILY.get(family, 'special situations'),
        'mission_statement': MISSION_FRAMES.get(skin, MISSION_FRAMES['generic']),
        'actual_function': ACTUAL_FUNCTION_BY_FAMILY.get(family, 'turns private rot into scalable workflow'),
        'leadership_style': LEADERSHIP_STYLE_BY_FAMILY.get(family, 'controlled damage with a smile'),
        'average_employee_review': rng.choice(EMPLOYEE_REVIEW_FRAMES),
        'ongoing_scandal': rng.choice(SCANDAL_FRAMES),
        'institution_name': institution['institution_name'],
    }


def derive_job_posting(card: Dict[str, Any], company: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    family = card['villain_family']
    sidekick = card['sidekick']
    title = rng.choice(JOB_TITLES_BY_FAMILY.get(family, ['Operations Lead']))
    responsibilities = [
        f"support {card['favorite_leverage']} across live incidents and post-incident explanation",
        f"coordinate with the {sidekick['role_label']} on {sidekick['task_label']}",
        f"maintain continuity between {card['institutional_exposure']['label'].lower()} and day-to-day operations",
    ]
    requirements = [
        f"demonstrated competency in {card['core_competencies']['items'][0]}",
        f"comfort with {card['moral_texture']['primary'].replace('_', ' ')} as a management climate",
        f"willingness to work inside a {card['operating_environment']}",
    ]
    return {
        'title': title,
        'department': card['operating_environment'].title(),
        'responsibilities': responsibilities,
        'requirements': requirements,
        'benefits': rng.sample(BENEFIT_FRAMES, k=3),
        'why_previous_employee_left': rng.choice(WHY_LEFT_FRAMES),
        'employer': company['name'],
        'reports_to': sidekick['role_label'],
    }


def derive_property_listing(card: Dict[str, Any], company: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    env = card['operating_environment']
    family = card['villain_family']
    property_type = PROPERTY_TYPE_BY_ENVIRONMENT.get(env, env.title())
    amenities = AMENITIES_BY_ENVIRONMENT.get(env, [card['favorite_leverage'], card['signifier_package']['room_logic'], card['signifier_package']['object_logic']])
    if len(amenities) < 3:
        amenities = amenities + [card['signifier_package']['room_logic']]
    return {
        'title': f"{property_type} Near {company['name']}",
        'property_type': property_type,
        'price': PRICE_FRAMES.get(card['skin'], PRICE_FRAMES['generic']),
        'location_vibe': env,
        'description': (
            f"A highly specific {property_type.lower()} designed for buyers who value {card['favorite_leverage']}, "
            f"administrative opacity, and the ability to convert {card['failure_mode']} into atmosphere."
        ),
        'amenities': amenities[:3],
        'listing_warning': rng.choice(PROPERTY_WARNINGS),
        'listed_by': company['name'],
        'hero_infestation_risk': HERO_INFESTATION_BY_FAMILY.get(family, 'variable; depends on how public the monologue schedule gets'),
        'superweapon_zoning_status': rng.choice(SUPERWEAPON_ZONING),
        'monologue_chair_status': MONOLOGUE_CHAIR_BY_ENVIRONMENT.get(env, 'available on request through theatrical procurement'),
        'escape_pod_access': ESCAPE_POD_BY_ENVIRONMENT.get(env, 'manual stairs and a bad contingency plan'),
        'lair_liability': LAIR_LIABILITY_BY_ENVIRONMENT.get(env, 'general menace liability'),
        'acoustic_threat_quality': rng.choice(ACOUSTIC_THREAT_QUALITY),
        'shark_tank_maintenance_rules': rng.choice(SHARK_TANK_RULES),
        'historical_coup_density': rng.choice(COUP_DENSITY),
        'disclosure_exemptions': rng.sample(DISCLOSURE_EXEMPTIONS, k=2),
        'nearest_extradition_safe_airstrip': rng.choice(AIRSTRIP_ACCESS),
        'maintenance_cost': MAINTENANCE_COST_BY_PROPERTY.get(property_type, 'custom maintenance burden with hidden payroll grief'),
        'spatial_footprint': SPATIAL_FOOTPRINT_BY_PROPERTY.get(property_type, 'footprint withheld pending hostile appraisal'),
        'entry_screening_protocol': rng.choice(ENTRY_SCREENING_PROTOCOLS),
        'worker_morale_note': rng.choice(WORKER_MORALE_NOTES),
        'supply_run_vulnerability': rng.choice(SUPPLY_RUN_VULNERABILITY),
    }
