# Phase 2 Local Realization and Reconciliation Design

Status: approved implementation continuation of Architecture v0.2

## Goal

Add a conservative, machine-local realization layer that lets a person bind registered local Surfaces to real filesystem paths, discover Git workspaces only inside explicit trusted roots, and compare observed local reality with the private registry without uploading absolute paths or mutating the registry.

## Scope

Phase 2.1 implements:

- one machine-local governance home per device;
- bootstrap for a registered Machine ID;
- machine-local `local-map.yaml` and trusted-root configuration;
- explicit local Surface → path mapping;
- bounded, metadata-first Git discovery;
- GitHub remote normalization and identity comparison;
- read-only reconciliation findings for registered local Surfaces;
- conservative classifications: `MATCH`, `DRIFT`, `MISSING`, `UNREGISTERED`, `AMBIGUOUS`, and `UNREACHABLE`;
- machine-readable JSON and concise human output;
- Linux and Windows CI coverage.

Phase 2.1 deliberately does not implement:

- whole-disk scanning;
- automatic filesystem moves;
- automatic registry writes;
- automatic reconciliation apply;
- ChatGPT Project mutation;
- provider polling;
- content indexing;
- workspace-marker adoption for non-Git move recovery;
- background daemons or scheduled reconciliation.

Those are separate later decisions.

## Local state home

The implementation uses a small fixed governance home that does not constrain where projects live.

Default:

```text
~/.workspace-governance/
```

Override:

```text
PWG_HOME=<path>
```

Files:

```text
config.yaml
local-map.yaml
trusted-roots.yaml
```

`config.yaml` contains the stable `machine_id` and local path to a checked-out private registry. These files are machine-local and may contain absolute paths. They MUST NOT be committed to the public governance repository or the private personal registry.

## Data model

### `config.yaml`

```yaml
schema_version: 1
machine_id: pc-a
registry_path: "C:/local/private-registry"
```

### `local-map.yaml`

Uses the existing governance Local Map schema:

```yaml
schema_version: 1
revision: 1
machine_id: pc-a
workspaces:
  surf-example:
    path: "D:/Work/example"
```

Every explicit mapping change increments `revision`.

### `trusted-roots.yaml`

```yaml
schema_version: 1
roots:
  - path: "D:/Work"
    max_depth: 4
```

Trusted roots are opt-in. Missing/unmounted roots are reported as `UNREACHABLE`, not interpreted as deletion.

## Identity evidence

For local Git workspaces, expected identity comes from a GitHub Surface attached to the same Workspace Object.

Comparison order:

1. registered local Surface identity;
2. registered GitHub `locator.full_name` for the same Object;
3. local Git `origin` remote normalized to `owner/repo`;
4. explicit machine-local path mapping.

Supported GitHub remote forms include HTTPS and SSH variants.

If a registered Git-backed local path exists and its GitHub remote matches, the result is `MATCH` with high confidence.

If the mapped path is gone and exactly one trusted-root candidate has the expected GitHub remote, the result is `DRIFT` with proposed `REMAP_LOCAL_PATH`.

If more than one candidate matches, the result is `AMBIGUOUS`. No automatic choice is made.

If an existing mapped Git workspace points at a different GitHub repository, the result is high-risk `DRIFT` with a review recommendation; it is never silently adopted.

For non-Git local Surfaces, an existing mapped directory can be reported as `MATCH` with medium confidence. Move recovery for non-Git workspaces remains manual until a marker design is separately accepted.

## Discovery bounds

Trusted-root discovery is breadth-first and depth-limited. It:

- never starts at a disk root unless the user explicitly configured that root;
- skips repository metadata directories and common dependency/cache directories;
- may detect nested repositories inside a trusted meta-workspace;
- reads only filesystem metadata and Git remote metadata;
- does not read project content for identity.

## Findings

Every finding contains:

- `classification`;
- `subject_id`;
- declared facts;
- observed facts;
- evidence;
- confidence;
- suggested operation;
- risk.

Phase 2.1 reconciliation is read-only. Suggested operations are plans, not mutations.

## CLI

The public toolkit exposes `pwg`:

```text
pwg bootstrap --machine-id pc-a --registry <private-registry-path>
pwg map-set --surface-id <surface-id> --path <workspace-path>
pwg trust-add --path <trusted-root> --max-depth 4
pwg reconcile
pwg reconcile --trusted
pwg reconcile --trusted --json
```

`bootstrap` verifies that the Machine ID exists in the supplied private registry and refuses to overwrite a local home owned by another Machine ID.

`map-set` verifies that the Surface exists, is `kind: local`, and belongs to the configured machine before writing a path.

`trust-add` is explicit local authorization for bounded discovery.

`reconcile` never writes the registry or filesystem realization.

## Error handling

The CLI fails closed on:

- unknown machine IDs;
- malformed local state;
- unknown or wrong-machine local Surface IDs;
- unreadable registry files;
- invalid trusted-root depth;
- Git inspection failures that prevent identity comparison.

A temporarily unavailable trusted root is a finding, not a fatal mutation trigger.

## Security and privacy

Absolute paths remain in machine-local files only.

The toolkit does not upload local state. The public repository contains schemas, code, tests, and synthetic fixtures only.

No command deletes, moves, clones, resets, or rewrites user projects in Phase 2.1.

## Testing

CI runs on both Ubuntu and Windows.

Tests cover:

- bootstrap creation and machine mismatch protection;
- Local Map revision changes;
- GitHub remote normalization;
- registered Git workspace `MATCH`;
- unique moved candidate → `DRIFT` / `REMAP_LOCAL_PATH`;
- duplicate moved candidates → `AMBIGUOUS`;
- unknown trusted-root Git repo → `UNREGISTERED`;
- missing trusted root → `UNREACHABLE`;
- bounded scan depth;
- mismatched Git identity → high-risk `DRIFT`;
- non-Git mapped directory → medium-confidence `MATCH`;
- reconciliation read-only behavior.
