# Local Realization

Phase 2.1 adds a conservative machine-local realization toolkit. It connects private Registry facts to real local paths without requiring a common project root and without uploading absolute paths.

## What is local

Each machine has a small governance home:

```text
~/.workspace-governance/
```

Set `PWG_HOME` to override it.

The home contains:

```text
config.yaml
local-map.yaml
trusted-roots.yaml
```

These files are local-only state. They may contain absolute paths and should not be committed to the public Governance repository or the private Personal Registry.

## Install

From a checkout of this public repository:

```bash
python -m pip install -e .
```

The `pwg` command becomes available.

## Bootstrap a machine

First keep a local checkout of the private Personal Registry somewhere convenient. The governance toolkit does not require either repository to live beside your projects.

Then initialize the machine:

```bash
pwg bootstrap --machine-id pc-a --registry <path-to-private-registry>
```

Bootstrap:

1. reads the private registry;
2. verifies that the Machine ID exists and is active;
3. creates machine-local config;
4. creates an empty Local Map;
5. creates an empty trusted-root list.

It refuses to silently reuse a local home owned by a different Machine ID.

## Map a registered local Surface

A local Surface must already exist in the private Registry.

```bash
pwg map-set --surface-id surf-example --path <workspace-path>
```

The command verifies that the Surface:

- exists;
- is `kind: local`;
- belongs to this machine.

The absolute path is written only to local `local-map.yaml`. Each real mapping change increments the Local Map revision.

## Add a trusted root

Trusted-root discovery is opt-in:

```bash
pwg trust-add --path <trusted-root> --max-depth 4
```

A trusted root authorizes bounded metadata discovery below that path. It is not a request to index file contents.

Use the smallest useful roots. Do not configure an entire disk unless that broad scope is intentionally required.

## Reconcile registered state

Registered-only check:

```bash
pwg reconcile
```

Include explicit trusted roots:

```bash
pwg reconcile --trusted
```

Machine-readable output:

```bash
pwg reconcile --trusted --json
```

Phase 2.1 reconciliation is read-only.

It may report:

- `MATCH` — observed realization agrees with registered identity;
- `DRIFT` — a durable binding or Git identity differs;
- `MISSING` — a registered local realization cannot be located;
- `AMBIGUOUS` — multiple candidates match the same expected identity;
- `UNREGISTERED` — a trusted-root Git repository is not represented in the Registry;
- `UNREACHABLE` — a configured trusted root is currently unavailable;
- `UNOBSERVABLE` — required metadata cannot currently be read.

A suggested operation is a proposal, not an automatic mutation.

## Git move recovery

For an Object that has both a local Surface and a GitHub repository Surface:

1. the Registry supplies the expected GitHub `owner/repo`;
2. the Local Map supplies the last mapped path;
3. Git supplies the current `origin` remote;
4. trusted-root discovery can locate bounded candidates.

If the mapped path disappeared and exactly one trusted-root candidate has the expected remote, reconciliation reports:

```text
DRIFT -> REMAP_LOCAL_PATH
```

If two or more candidates match, it reports:

```text
AMBIGUOUS
```

and does not choose one.

If the mapped path still exists but now points at a different GitHub repository, the result is high-risk identity `DRIFT` and the toolkit proposes review rather than adoption.

## Non-Git workspaces

If a registered non-Git path exists, Phase 2.1 can report `MATCH` with medium confidence.

If that workspace is moved outside its mapped location, Phase 2.1 does not guess its new identity from folder names. Non-Git move recovery remains manual until a separate workspace-marker design is accepted.

## Discovery bounds

Discovery:

- starts only from explicit trusted roots;
- uses a maximum depth per root;
- skips `.git` internals and common dependency/cache directories;
- can still detect nested repositories inside a meta-workspace;
- reads filesystem and Git metadata only;
- does not inspect papers, datasets, notes, source contents, screenshots, or other project content merely to identify a workspace.

A missing or unmounted trusted root is `UNREACHABLE`; it is not evidence that its projects were deleted.

## What Phase 2.1 does not do

No Phase 2.1 command:

- scans the whole computer by default;
- moves or deletes workspaces;
- clones repositories;
- changes Git remotes;
- modifies ChatGPT Projects;
- writes reconciliation results into the private Registry;
- indexes project content;
- runs continuously in the background.

Those capabilities require separate design and acceptance.

## Machine sequence

Stable logical Machine IDs such as:

```text
pc-a
pc-b
pc-c
pc-d
```

can continue across desktops, laptops, workstations, and virtual machines. Device roles remain mutable metadata; the stable Machine ID does not encode a temporary role.
