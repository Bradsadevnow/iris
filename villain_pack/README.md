# Villain Pack

A reusable villain archetype starter pack and composition engine.

This module is intentionally more generic than `halltime` or `skynet_generator`.
It exists to generate villain profiles that can later be skinned into different apps, genres, settings, and interactive systems.

## What it does

It composes villains from a small set of reusable layers:
- family
- modifier
- power source
- signifier package
- dialogue grammar
- narrative payoff
- operating environment
- failure mode
- petty atrocity
- institutional exposure
- core competencies
- sidekick ecosystem
- fake institution credentialing

## Quick start

Generate a batch:

```bash
python generator.py --count 3
```

Use the workshop:

```bash
python build_a_villain.py
```


Generate a company page:

```bash
python company_page_generator.py outputs/<card>.json
```

Generate a job posting:

```bash
python job_posting_generator.py outputs/<card>.json
```

Generate a Zillow-style property listing:

```bash
python property_listing_generator.py outputs/<card>.json
```

The Zillow lane now emits villain-MLS fields like hero infestation risk, superweapon zoning status, monologue-chair inclusion, escape-pod access, disclosure exemptions, maintenance burdens, footprint, screening protocol, morale notes, and supply-run vulnerability.


Generate a scheme packet:

```bash
python scheme_packet_generator.py outputs/<card>.json
```

Generate a lair dossier:

```bash
python lair_dossier_generator.py outputs/<card>.json
```

Generate an underworld job-board packet:

```bash
python job_board_generator.py outputs/<card>.json
```


Theme a batch:

```bash
python generator.py --count 3 --skin sci_fi
python generator.py --count 3 --skin suburban_thriller
python generator.py --count 3 --skin corporate_satire
```

Outputs are saved under `outputs/` as JSON and markdown cards.

Every build now includes one completely normal but morally unforgivable act from a shared doctrine bucket.
That bucket is intentionally universal, not skin-specific: biotech monsters, rogue AIs, suburban manipulators, and glossy executives are all capable of the same spiritually unforgivable civilian behavior.

The petty-atrocity layer now carries:
- category
- severity
- tags
- derived moral texture
- compatibility pressure

The exposure layer now adds:
- resume-coded institutional rot
- financial exposure
- operational exposure
- legal exposure
- predatory exposure

The competency layer now adds:
- professionally certified bastard skills
- summarized competency stacks
- reusable downstream operational identity

The sidekick layer now adds:
- visible sidekick role selection
- compositional loyalty / task / competence / fold-risk assembly
- much higher variety than a fixed henchman list
- a small local ecosystem around the villain instead of a lone-monster output

The credential layer now adds:
- fake institution name
- field of study
- motto
- accreditation body
- notable alumni line
- registrar voice

The second research artifact now feeds a reusable taxonomy file: `villain_story_mechanics.yaml`, which holds plot goals, gambit/plot-shape jargon, betrayal modes, reversal modes, lair features, story-function logic, and satirical meta voice.

The latest plot research also upgraded the structural doctrine: `villain_story_mechanics.yaml` now carries plot families, motive clusters, twist types, the ten-part core plot kit, and tension/payoff beats.

The final lair artifact also added an `architecture_grammar` layer for villain habitats, so lair outputs can talk about public masks, threshold tests, ceremonial voids, operations rings, private sanctums, and hidden escape routes as explicit structural stages.
