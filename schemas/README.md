# Schemas

These JSON Schema documents define the initial machine-readable contracts for Architecture v0.2 and the Phase 2.1 machine-local realization layer.

Current schema version: `1`.

Canonical / registry-facing schemas:

- `workspace-object.schema.json`
- `surface.schema.json`
- `relationship.schema.json`
- `machine.schema.json`
- `local-map.schema.json`
- `policy-exception.schema.json`
- `change-event.schema.json`

Machine-local realization schemas:

- `local-realization-config.schema.json`
- `trusted-roots.schema.json`

The latter describe local-only state. Their presence in this public repository defines structure; it does not mean actual machine config, trusted roots, or absolute paths belong in Git.

## Canonical text format

A private registry may serialize human-maintained canonical state as YAML, provided the data validates against the equivalent JSON data model represented by these schemas.

Implementations should use a strict YAML subset and avoid anchors, merge keys, custom tags, executable extensions, and parser-dependent implicit typing.

Dates and timestamps should be explicit strings in RFC 3339 / ISO 8601 form.

## Versioning

`schema_version` is an integer and changes only for machine-readable structural compatibility changes. Governance documentation may evolve independently under its own project version.

Schema migrations should be explicit, reviewable, dry-runnable, and validated before canonical state is rewritten.

## Validation philosophy

Schemas intentionally validate structure, vocabulary, and basic invariants. Cross-entity invariants such as referential integrity, duplicate identities, relationship self-links, revision monotonicity, and provider-specific constraints belong in higher-level validators rather than being forced into JSON Schema where that would reduce clarity or portability.
