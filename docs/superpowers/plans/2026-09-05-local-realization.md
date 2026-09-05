# Phase 2 Local Realization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first safe machine-local realization and read-only reconciliation toolkit for Personal Workspace Governance.

**Architecture:** A small Python package reads the private registry and machine-local YAML state, performs bounded Git metadata discovery inside explicit trusted roots, and emits conservative reconciliation findings. It never uploads absolute paths or mutates the registry/filesystem during reconciliation.

**Tech Stack:** Python 3.11+, standard library, PyYAML, unittest, GitHub Actions on Ubuntu and Windows.

**Spec:** `docs/superpowers/specs/2026-09-05-local-realization-design.md`

## Global Constraints

- Absolute local paths remain machine-local.
- No whole-disk scanning.
- No automatic filesystem moves.
- No automatic registry writes from reconciliation.
- No content indexing for identity.
- Trusted-root discovery is explicit and depth-limited.
- Non-Git move recovery remains manual in Phase 2.1.
- Tests run on Ubuntu and Windows.

---

### Task 1: Specify local-state contracts and test behavior

**Files:**
- Create: `tests/test_local_realization.py`
- Create: `.github/workflows/test-local-realization.yml`
- Create: `schemas/local-realization-config.schema.json`
- Create: `schemas/trusted-roots.schema.json`

**Interfaces:**
- Tests consume future functions from `pwg.local_state`, `pwg.git_identity`, and `pwg.reconcile`.
- Schemas define machine-local config and trusted-root files.

- [ ] Write tests for bootstrap, mapping revisions, remote normalization, bounded discovery, reconciliation classifications, and read-only behavior.
- [ ] Add cross-platform GitHub Actions test workflow.
- [ ] Run the workflow and confirm tests fail because the `pwg` implementation does not exist.

### Task 2: Implement local state and registry loading

**Files:**
- Create: `pyproject.toml`
- Create: `src/pwg/__init__.py`
- Create: `src/pwg/local_state.py`
- Create: `src/pwg/registry.py`

**Interfaces:**
- `bootstrap_local_state(home, machine_id, registry_path) -> None`
- `set_mapping(home, surface_id, path, registry_path=None) -> dict`
- `add_trusted_root(home, path, max_depth=4) -> dict`
- `RegistrySnapshot.load(root) -> RegistrySnapshot`

- [ ] Implement minimal local-state creation with fail-closed machine ownership.
- [ ] Implement registry entity loading and local-Surface validation.
- [ ] Implement atomic YAML writes and Local Map revision increments.
- [ ] Run tests and keep implementation minimal.

### Task 3: Implement Git identity and bounded discovery

**Files:**
- Create: `src/pwg/git_identity.py`
- Create: `src/pwg/discovery.py`

**Interfaces:**
- `canonicalize_github_remote(url) -> str | None`
- `read_origin_remote(path) -> tuple[str | None, str | None]`
- `discover_git_candidates(trusted_roots) -> DiscoveryResult`

- [ ] Normalize HTTPS and SSH GitHub remotes.
- [ ] Inspect `origin` using Git metadata only.
- [ ] Walk trusted roots with explicit depth bounds and cache/dependency exclusions.
- [ ] Return unreachable roots separately instead of treating them as missing workspaces.
- [ ] Run tests on both CI operating systems.

### Task 4: Implement read-only reconciliation

**Files:**
- Create: `src/pwg/model.py`
- Create: `src/pwg/reconcile.py`

**Interfaces:**
- `Finding.to_dict() -> dict`
- `reconcile(home, registry_path=None, include_trusted=False) -> list[Finding]`

- [ ] Compare each registered local Surface against machine-local mappings.
- [ ] Emit `MATCH`, `DRIFT`, `MISSING`, `AMBIGUOUS`, `UNREACHABLE`, and `UNREGISTERED` conservatively.
- [ ] Propose `MAP_LOCAL_PATH`, `REMAP_LOCAL_PATH`, or `REVIEW_IDENTITY` without applying them.
- [ ] Verify reconciliation leaves machine-local files unchanged.

### Task 5: Add CLI and operator documentation

**Files:**
- Create: `src/pwg/cli.py`
- Create: `docs/local-realization.md`
- Modify: `README.md`
- Modify: `scripts/validate.py`

**Interfaces:**
- Console command: `pwg`
- Subcommands: `bootstrap`, `map-set`, `trust-add`, `reconcile`

- [ ] Wire CLI commands to tested library functions.
- [ ] Document local-only privacy boundary and bootstrap sequence.
- [ ] Include new machine-local schemas in governance schema validation.
- [ ] Run governance validation and local-realization tests.

### Task 6: Final verification

**Files:**
- Review all Phase 2.1 changed files.

- [ ] Confirm public diff contains no personal absolute path or registry data.
- [ ] Confirm GitHub Actions governance validation passes.
- [ ] Confirm local-realization tests pass on Ubuntu and Windows.
- [ ] Confirm reconciliation has no write path beyond explicit `map-set`/`trust-add`.
- [ ] Merge only after all checks pass.
