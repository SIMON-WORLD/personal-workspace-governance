# Surface Realization & Discovery

Phase 2.2 makes the relationship between a registered Local Surface and its physical
realization explicit, and makes discovery of unregistered Git candidates bounded and
excludable.

This document is the accepted design for Phase 2.2. It generalizes the Phase 2.1
local-realization toolkit without changing the Phase 2.1 data model.

## 1. Realization kinds

A Local Surface (`kind: local`) may declare how it is realized on a machine using an
optional additive field `realization_kind`:

- `git` — the mapped path is a Git worktree whose origin must agree with one specific
  provider repository Surface.
- `directory` — the mapped path is a plain working directory. Git metadata is not read.
- `container` — the mapped path is a container / meta-workspace directory that may host
  nested repositories or other content. The container root's own Git metadata is not
  read, even when the Workspace Object also has a GitHub source Surface.

`schema_version` stays `1`; the new fields are additive and optional.

## 2. Explicit Git binding

A `git` Local Surface declares `binds_to_surface_id`, an optional string reference to a
Surface record. Constraints (enforced by the registry validator):

- `binds_to_surface_id` is only meaningful on a `local` Surface with
  `realization_kind: git`.
- The referenced Surface must exist.
- The referenced Surface must have the same `object_id` as the Local Surface, `kind:
  github`, and `resource_type: repository`.

When present, the expected Git identity for reconciliation comes **only** from the
bound GitHub repository Surface — never from an Object-level search.

## 3. directory / container semantics

- `directory` and `container` realizations **forbid** `binds_to_surface_id`.
- Reconciliation checks that the mapped directory exists and reports
  `MATCH` with medium confidence.
- Reconciliation does **not** read Git metadata at the mapped path for these kinds,
  even if the Object also has a GitHub source Surface (this is the meta-workspace case).

## 4. Multiple clone semantics

- One GitHub repository Surface may be realized by `0..many` Local Surfaces.
- One Local Surface binds to at most one provider repository Surface.
- Multiple clones of the same GitHub remote on one machine are legal and must not, by
  themselves, produce an error or an `AMBIGUOUS` finding.
- `AMBIGUOUS` has one precise meaning:

  > While recovering the realization of a **specific** registered Local Surface whose
  > mapped path is missing, more than one equally authoritative unclaimed candidate
  > matches the expected identity, and the system cannot decide which one to propose.

Candidate selection during recovery uses claimed-candidate filtering:

- candidate paths are canonicalized in a Windows-aware way (resolve, normalize
  separators, compare case-insensitively on Windows);
- the subject Surface's own current candidate is never treated as claimed by another
  Surface;
- only candidates that another registered Local Surface has mapped and actually claimed
  are excluded;
- most-recent / first-hit / closest-folder / arbitrary ordering selectors are forbidden.

## 5. Discovery exclusions

Each machine-local trusted root may carry an optional `exclude_globs` list.

- Patterns are relative to the trusted root, normalized to `/`.
- Matching is case-insensitive on Windows.
- `*` and `**` are supported.
- A directory that matches a pattern is pruned before the bounded BFS descends into it.
- Absolute globs are forbidden.
- Built-in skip directories (`.git`, `.venv`, `node_modules`, caches, ...) are kept.

Exclusions affect **candidate discovery only**:

- `UNREGISTERED` candidate discovery;
- missing-Git-realization candidate recovery.

Exclusions never affect **registered verification**: a registered Local Surface that
already has a mapping inside an excluded subtree is still checked by registered-only
reconciliation.

Vendor / tool / temporary noise is a discovery-policy concern, not a Policy Exception.

## 6. Two pipelines

- **Registered verification**: starts from every registered Local Surface for the
  machine, reads the machine-local map, and checks the mapped path against the
  realization kind. Read-only. Exclusions are not consulted.
- **Candidate discovery**: starts from explicit trusted roots, applies built-in skips
  and exclusions, and produces Git candidates used for `UNREGISTERED` findings and for
  missing-realization recovery.

## 7. Backward compatibility / legacy inference

Surfaces that do not declare `realization_kind` keep legacy behavior:

- if the Object has exactly one GitHub repository Surface, the Local Surface is treated
  with legacy Git inference;
- otherwise it is treated with legacy directory inference.

Findings produced by legacy inference must label their evidence as legacy inference.
Legacy inference never overrides an explicit realization.

## 8. Synthetic example

```yaml
surfaces:
  - id: surf-local-orchestrator
    object_id: obj-example-orchestrator
    kind: local
    role: exec
    machine_id: pc-a
    realization_kind: git
    binds_to_surface_id: surf-repo-github
  - id: surf-local-lab
    object_id: obj-example-lab
    kind: local
    role: exec
    machine_id: pc-a
    realization_kind: container
  - id: surf-local-paper
    object_id: obj-example-paper
    kind: local
    role: exec
    machine_id: pc-a
    realization_kind: directory
```

The example uses only fictional identifiers. No real absolute paths or personal data
appear anywhere in this repository.
