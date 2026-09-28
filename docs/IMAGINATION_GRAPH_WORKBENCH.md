# Imagination Graph Workbench

Imagination is a graph workbench for constructing fictional worlds from reusable
creative ideas. Villain Pack is its first rich doctrine source, not its permanent
upper-level identity.

## State boundaries

1. **Doctrine** describes what could exist. Packs contribute immutable creative
   primitives, typed relationships, lenses, policies, surface recipes, guidance,
   and noncanonical taste exemplars.
2. **Workbench** describes what might exist. A durable blueprint records manual
   selections, Halcyon suggestions, derivations, locks, rejected suggestions,
   unresolved questions, and deliberately retained tensions.
3. **World** describes what does exist. Only admission can turn a blueprint into
   canonical entities, relationships, lore, genealogy, and consequences.

Installing or validating a pack never creates fictional entities, activates a
capability, or mutates the World.

## Trait constellations

The Imagination browser begins with reusable trait spaces rather than characters
or other finished entities. The character classification exposes five TTRPG-shaped
constellations: Who they are, What they're about, Why they're here, What they bring,
and Flaws. Smaller distinctions such as knack versus training remain clusters
inside a constellation rather than becoming more navigation categories. Every selectable
character card has one constellation home; broader domains and tags create graph
connections without duplicating the card across sections.

Selections become durable trait-bundle drafts. A trait bundle is an ingredient
for later entity construction or enrichment; it is not itself a character and
cannot be admitted as a World entity. Existing characters remain untouched until
an explicit attachment or enrichment workflow is designed.

### Deferred Holdings boundary — preserve losslessly

MacGuffins and lairs are reserved for a later **Holdings** constellation. They are
not character traits and must not be deleted, flattened, atomized into character
qualities, or hidden by destructive migration during the character pass. Preserve
their complete source records, provenance, compiled primitives, relationships, and
future ability to become independently saved Artifact and Stronghold drafts.

The current implementation pass is character-only: Who they are, What they're about,
Why they're here, What they bring, and Flaws. Holdings is explicitly the next classification/construction
pass. Plot machinery also remains in the source pack but is not forced into character
constellations.

Visual signifier packages, genre skins, and authored institutions are preserved
losslessly as deferred setting/world material. Their room logic, object logic,
atmosphere, framing, and organizational identity do not appear as character traits
merely because an archetype or background references them.

Petty atrocities are likewise preserved losslessly outside character selection as
deferred plot devices. Their categories, severity, tags, and authored detail remain
available for later scene friction, recurring gags, escalation, and character reveals.

Overly granular character phrases compile into canonical selectable profiles with
their complete authored nodes retained as non-selectable variants. Cards collapse
only when they share both meaning and character-sheet function; similar themes in
different sections remain separate and connected rather than being merged.

Doctrine relationship types retain distinct meanings:

- `compatible_with`: structural possibility
- `suggests`: creative association
- `requires`: construction dependency
- `intensifies`: increased dramatic pressure
- `soft_conflict_with`: productive tension
- `expresses_as`: presentation or manifestation
- `resolves_through`: likely payoff
- `creates_demand_for`: consequence after admission
- `tagged_with`: authored cross-domain vocabulary

## Blueprints and genealogy

A blueprint is a versioned noncanonical graph namespace, not transient UI state.
Its eventual admission receipt becomes the artifact's creative genealogy: what the
user chose, what Halcyon suggested, what graph traversal derived, what contradiction
was retained, and what world dependencies were created.

Composition is deterministic for a given blueprint revision and pinned pack version.
It produces draft-namespaced entities and edges, initial Markdown lore, induced
doctrine relationships, world dependencies, a content hash, and a genealogy receipt.
Composition creates another blueprint revision; it does not mutate canonical World.

Admission requires the current blueprint revision and exact candidate content hash. The
candidate graph, draft-to-canonical identity mapping, initial lore, immutable admission
receipt, genealogy, blueprint transition, and World sequence advance commit in one SQLite
transaction. Entity collisions or invalid edges roll the complete transaction back.

## World pressure loop

Admitted artifacts may create unresolved pressures such as a missing custodian,
contested ownership, unmet containment, institutional secrecy, or an unfilled role.
A pressure never generates content automatically. It exposes possible resolutions
that the user and Halcyon may open as another Workbench blueprint.

Pressures are persisted during the same transaction that admits their originating
artifact. Exploring one creates a durable blueprint and marks the pressure as
`exploring` atomically; repeated exploration returns the existing blueprint rather
than branching duplicate drafts.

```text
Doctrine -> Workbench -> World -> Pressure -> Workbench -> World
```
