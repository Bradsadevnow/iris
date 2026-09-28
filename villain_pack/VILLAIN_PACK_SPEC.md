# Villain Pack Spec

Status: active working spec
Last updated: 2026-05-30
Scope: `~/skynet/villain_pack`

## 1. Purpose

Villain Pack is no longer just a villain card generator.
It is the core substrate for an evil professional-network world generator.

It is meant to sit underneath more specific generators such as:
- HallTime
- sci-fi villain systems
- corporate satire engines
- fantasy dark-lord packs
- haunted interactive apps
- an out-of-work villain LinkedIn

The system should generate portable villain logic and then place that logic inside a world of institutions, employers, and labor demand.

## 2. Core Thesis

Most generators die because every object is isolated.
Villain Pack should not generate isolated objects.
It should generate graph edges.

A villain references:
- petty atrocities
- moral texture
- institutional exposure
- competencies
- sidekicks
- institutions

An institution references:
- alumni
- accrediting bodies
- placement outcomes
- public and hidden reputation

A company references:
- leadership style
- actual function versus mission statement
- current openings
- scandal conditions

A job posting references:
- labor demand created by villainy
- required competencies
- tolerated moral drift
- reasons the last employee left

Each generated object should create demand for other objects.
That is how the world emerges.

## 3. V1 World Graph

V1 should stay intentionally small.
It consists of four core entities:
- villain
- institution
- company
- job_posting

Do not build recommendations, recruiters, scandal feeds, or alumni social graphs as first-class systems yet.
Those should emerge later from these four.

### 3.1 Villain

The villain is the anchor entity.

Required fields:
- headline
- summary
- petty_atrocity
- petty_atrocity_profile
- moral_texture
- institutional_exposure
- core_competencies
- sidekick
- credentialed_by
- open_to_work_status
- ecosystem_tone

### 3.2 Institution

The institution is where bastardry gets formalized.

Required fields:
- name
- motto
- field_of_study
- accreditation_body
- notable_alumni
- public_reputation
- hidden_reputation
- placement_outcomes
- top_employers

### 3.3 Company

The company is the operational habitat that converts villain traits into labor structure.

Required fields:
- name
- sector
- mission_statement
- actual_function
- leadership_style
- average_employee_review
- current_openings
- ongoing_scandal

### 3.4 Job Posting

The job posting is how the world leaks its needs.

Required fields:
- title
- department
- responsibilities
- requirements
- benefits
- why_previous_employee_left
- employer
- reports_to

## 4. Existing Villain Card Substrate

The current villain object already composes from:
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

This remains the canonical substrate for villain-entity generation.

## 5. Current Villain Layers

### 5.1 Baseline Human Rot

The petty-atrocity layer proves the villain was already rotten before scale.

Fields:
- primary petty atrocity
- 6-item rot profile
- category
- severity
- tags

### 5.2 Institutional Exposure

This is the villain lateral of experience.
It should sound like a normal resume word for a second and then become obviously corrupt.

Exposure should carry:
- financial exposure
- operational exposure
- legal exposure
- predatory exposure

### 5.3 Core Competencies

Competencies are certified bastard skills.
They imply:
- measured repeatability
- institutional approval
- operationalization of personal moral failure

### 5.4 Sidekicks

V1 uses sidekicks rather than henchmen.
The point is relationship, not infrastructure.

The sidekick layer should reveal:
- role
- why they stay
- what they handle
- competence band
- fold risk

### 5.5 Fake Institutions

Institutions provide formal legitimacy for spiritual failure.
Their voice should be bureaucratically solemn and socially wrong.

## 6. Design Principles

### 6.1 Function before skin

Do not start with genre wrapper.
Start with dramatic function and social role, then skin it.

### 6.2 Relationship over isolation

Objects must point to other objects.
A villain without references is incomplete.

### 6.3 Bureaucratic language is load-bearing

Humor comes from solemn administrative framing applied to obvious rot.
This must remain true across profiles, institutions, companies, and jobs.

### 6.4 Variety pressure matters

Repeat collapse kills the joke.
Novelty pressure should demote recent repetition across:
- villain families and modifiers
- petty-atrocity profiles
- exposure and competency stacks
- sidekick ecosystems
- institutions

### 6.5 Profile generator disguised as world generator

The product may look like profile generation.
Its real function is world emergence through graph demand.

## 7. Current Deliverables

Implemented:
- Build-A-Villain workshop CLI
- batch villain generator
- petty-atrocity doctrine
- exposure doctrine
- competency doctrine
- sidekick doctrine
- fake-institution doctrine
- novelty pressure across recent outputs

New V1 deliverables:
- villain professional profile renderer
- institution page generator
- company page generator
- job posting generator
- property listing generator
- scheme packet generator
- lair dossier generator
- underworld job-board generator

## 8. Immediate Build Order

1. villain profile renderer
2. institution page generator
3. company page generator
4. job posting generator
5. property listing generator
6. scheme packet generator
7. lair dossier generator
8. entity linking layer

The first two are the current focus.
