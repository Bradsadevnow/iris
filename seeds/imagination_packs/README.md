# Imagination Packs

Imagination packs are versioned generative doctrine, not canonical world state.

A pack manifest may describe future capabilities and entity types, but loading or
validating a seed must not activate those capabilities, mutate an imagined world,
or create lore. Runtime registration and governed generation are separate steps.

Each doctrine source is explicitly allowlisted and content-addressed. Changing a
source requires a manifest version bump and a new SHA-256 value. Generated output,
model transport, and persistence code do not belong to the seed boundary.

Validate a manifest with:

```bash
python -m iris.imagination_pack seeds/imagination_packs/villain/manifest.yaml
```
