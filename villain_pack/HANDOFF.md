# Villain Pack Handoff

Last updated: 2026-06-01
Repo: `~/skynet/villain_pack`
Status: active, structurally strong, still in stateless-surface expansion mode

## 1. What This Repo Is Now

`villain_pack` is no longer just a villain card generator.
It is a reusable villain-substrate and cursed world-surface engine.

The current product shape is:
- generate one villain as a canonical object
- derive multiple stateless surfaces from that object
- let those surfaces imply a world without requiring shared state yet

The standing framing is:
- this is a world generator disguised as a profile generator
- do not build the shared spine/world state until a surface genuinely needs cross-object continuity
- the hero remains intentionally parked until after the spine exists

## 2. Current Core Thesis

The villain is not the final output.
The villain is the assembled object that downstream generators use.

That object now carries:
- family
- modifier
- power source
- signifier package
- dialogue grammar
- narrative payoff
- operating environment
- failure mode
- petty atrocity
- rot profile
- moral texture
- institutional exposure
- core competencies
- sidekick ecosystem
- fake institution credentialing
- MacGuffin / prize-object layer

This object is the authoritative substrate for every wrapper page.

## 3. What Is Implemented

### 3.1 Core generation
- `generator.py`
  Batch generator with novelty pressure.
- `build_a_villain.py`
  Interactive workshop CLI.
- `assembler.py`
  Canonical object assembly.
- `expander.py`
  Scaffold and optional LM-backed surface writing.

### 3.2 Existing stateless surfaces
- `villain_profile_renderer.py`
- `institution_page_generator.py`
- `company_page_generator.py`
- `job_posting_generator.py`
- `property_listing_generator.py`
- `scheme_packet_generator.py`
- `lair_dossier_generator.py`
- `job_board_generator.py`

### 3.3 Doctrine files already in play
- `villain_families.yaml`
- `villain_modifiers.yaml`
- `signifier_packages.yaml`
- `dialogue_grammars.yaml`
- `payoff_patterns.yaml`
- `skins.yaml`
- `petty_atrocities.yaml`
- `villain_exposures.yaml`
- `villain_competencies.yaml`
- `sidekick_parts.yaml`
- `villain_institutions.yaml`
- `villain_jobboard.yaml`
- `villain_lairs.yaml`
- `villain_schemes.yaml`
- `villain_story_mechanics.yaml`
- `villain_macguffins.yaml`
- `villain_slots.yaml`

## 4. Big Design Decisions Already Settled

### 4.1 Petty atrocities stay universal
The bucket of ordinary unforgivable behavior is intentionally shared across all villain types.
Do not skin-split it unless there is a very good reason.
The joke is that all evil collapses into the same civilian rot.

### 4.2 Sidekicks, not henchmen
V1 uses `sidekicks` because relationship is funnier and more useful than organization-chart mass.
The sidekick layer is compositional and should stay that way for now.

### 4.3 Stateless wrappers first
We deliberately did not build shared world state.
Wrapper pages should keep getting better until cross-object relationship pressure becomes unavoidable.
That is the signal to build the spine.

### 4.4 MacGuffins are plot engines, not loot
The right abstraction is not “cool object.”
The right abstraction is “plot pressure in item form.”
That is now reflected in the doctrine and render paths.

## 5. Current MacGuffin Layer

The MacGuffin layer was added in two passes.

### 5.1 First pass
Added first-class prize objects via:
- `villain_macguffins.yaml`
- `assembler.py`
- `expander.py`
- `build_a_villain.py`
- `generator.py`
- wrapper-page generators

Initial writer-facing fields:
- `artifact_class`
- `public_myth`
- `real_function`
- `desired_by`
- `misread_by`
- `activation_condition`
- `use_cost`
- `containment_needs`
- `betrayal_magnet`
- `plot_family_bias`
- `lair_compatibility`
- `institutional_cover_story`
- `portability`
- `custody_state`
- `side_effects`

### 5.2 Second pass
Deepened with attribute-matrix doctrine from `deep-research-report (4).md`.
Additional fields now present:
- `promise_family`
- `stakes_scale`
- `visual_form`
- `genre_lane`
- `portability_band`
- `resolution_type`
- `subversion_lane`

The important shift is that the MacGuffin layer now knows:
- what fantasy it sells
- what scale of stakes it implies
- what genre lane it belongs to
- what its likely ending shape is
- what the good subversion angle is

## 6. Current Surface Quality

The stateless page shapes were recently upgraded from “field dump” to more native product surfaces.

### 6.1 Surfaces that now feel meaningfully shaped
- professional profile
  LinkedIn-adjacent; stronger summary rails and open-to-work logic
- institution page
  fake school page with more legible reputation and placement framing
- company page
  mission vs actual function is more visible
- job posting
  clearer role summary and hiring climate
- property listing
  villain MLS / Zillow with stronger agent remarks and risk flags
- scheme packet
  more executive-summary / ops-logic feel
- lair dossier
  more architecture-crit / threat-assessment shape
- job board packet
  stronger opportunity framing and contractor-demand logic

### 6.2 Still true
These are still markdown artifacts, not a UI.
The important thing right now is page contract and content shape, not front-end polish.

## 7. Known Good Output Proofs

Representative artifacts worth opening first:

### Core villain cards
- `outputs/20260531-144758-0000-a-user-base-for-the-witnesses.md`
- `outputs/20260531-140632-0000-what-hubristic-creator-calls-mercy.md`
- `outputs/20260531-140520-0000-what-seductive-deceiver-calls-mercy.md`

### Profile / wrapper proofs
- `professional_profiles/20260531-144758-0000-a-user-base-for-the-witnesses.md`
- `professional_profiles/20260531-140520-0000-what-seductive-deceiver-calls-mercy.md`
- `property_listings/20260531-140520-0000-what-seductive-deceiver-calls-mercy.md`
- `job_board_packets/20260531-140520-0000-what-seductive-deceiver-calls-mercy.md`
- `lair_dossiers/20260531-140520-0000-what-seductive-deceiver-calls-mercy.md`

These prove:
- MacGuffins are in the object model
- stateless surfaces can leak the object into the world
- the wrapper pages still work after the recent redesign

## 8. Current Worktree Reality

At time of handoff, the worktree contains active modifications to:
- `assembler.py`
- `build_a_villain.py`
- `company_page_generator.py`
- `expander.py`
- `generator.py`
- `job_board_generator.py`
- `job_posting_generator.py`
- `lair_dossier_generator.py`
- `property_listing_generator.py`
- `scheme_packet_generator.py`
- `villain_profile_renderer.py`
- `villain_slots.yaml`
- `villain_macguffins.yaml`

There are also newly generated output artifacts under:
- `outputs/`
- `professional_profiles/`
- `property_listings/`
- `job_board_packets/`
- `lair_dossiers/`

There are modified `__pycache__/*.pyc` files from compile checks.
Those are runtime noise, not authored doctrine.

## 9. Validation Commands That Worked

Compile checks:
```bash
python3 -m py_compile assembler.py expander.py generator.py build_a_villain.py villain_profile_renderer.py company_page_generator.py job_posting_generator.py property_listing_generator.py scheme_packet_generator.py lair_dossier_generator.py job_board_generator.py
```

Generate a fresh villain card without LM surfaces:
```bash
python3 generator.py --count 1 --no-llm --skin corporate_satire
```

Render key wrappers for an existing card:
```bash
python3 villain_profile_renderer.py outputs/<card>.json
python3 property_listing_generator.py outputs/<card>.json
python3 lair_dossier_generator.py outputs/<card>.json
python3 job_board_generator.py outputs/<card>.json
```

Interactive workshop:
```bash
python3 build_a_villain.py
```

## 10. Known Seams / Risks

### 10.1 LM JSON robustness
The local-model path can still fail when asked to return strict JSON.
This is not a schema problem; it is an output-discipline/runtime problem.
The scaffold path remains reliable.

Recommended next hardening if needed:
- retries on parse failure
- JSON repair pass
- smaller surface calls instead of one big one
- better provider abstraction if external APIs get used more heavily

### 10.2 Some sentences still want copy polish
The stateless layer is much better than it was, but some generated phrases can still come out slightly stiff or grammatically weird depending on the specific combination.
This is mostly copy-shape polish, not architecture risk.

### 10.3 Surface redesign changed output feel
The wrappers are now more native-feeling, but that also means any future markdown post-processing or UI assumptions should be checked against the current headings and section order.

## 11. Current Strategic Stance

The villain generator itself is basically done enough.
Do not keep adding core villain fields forever by reflex.
Treat the villain object as infrastructure now.

Current best framing:
- the core generator is substrate
- the fun now is in what surfaces that substrate contaminates
- do not build the shared spine until a wrapper genuinely needs continuity between multiple objects

## 12. Best Next Moves

### 12.1 Good next moves that stay stateless
- keep tightening the wrapper page contracts
- deepen the MacGuffin doctrine if more reports land
- improve language polish in awkward combinations
- add more doctrine where it obviously plugs into existing slots

### 12.2 High-signal future directions
- more native company-page voice
- more native Zillow / LoopNet absurdity
- richer institution pages
- company/job/property pages that lean harder into “product surface” conventions
- more story-pressure leakage from scheme/lair into other pages

### 12.3 What not to do yet
- do not build hero generation yet
- do not build shared world state yet
- do not build recommendation feeds / alumni networks / recruiter systems yet
- do not overcomplicate with cross-object persistence before there is a concrete need

## 13. If Picking This Back Up Cold

Open in this order:
1. `README.md`
2. `VILLAIN_PACK_SPEC.md`
3. `professional_network_spec.md`
4. `villain_macguffins.yaml`
5. one recent card in `outputs/`
6. its corresponding wrapper pages
7. `assembler.py`
8. `expander.py`

That is the fastest path to current truth.

## 14. Short Summary

What exists now is strong:
- villain substrate
- world-adjacent stateless wrappers
- novelty pressure
- sidekick ecology
- fake institutions
- scheme and lair grammar
- villain MLS
- job-board logic
- MacGuffin layer with writer-facing doctrine

The repo is in a good place.
The smartest thing from here is disciplined expansion, not wholesale redesign.
