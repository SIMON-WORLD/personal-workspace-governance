# Architecture

## Purpose

Personal Workspace Governance separates durable logical identity from the many places where work happens. It is designed for people whose long-lived work spans cloud AI projects, local folders on multiple machines, GitHub resources, research workspaces, content systems, and agent-assisted workflows.

The architecture intentionally avoids requiring one filesystem root, one knowledge application, or one database to become the universal source of truth.

## Core structure

```text
                 Governance Spec
                        |
                        v
                 Personal Registry
                        |
          +-------------+-------------+
          |             |             |
      Objects       Surfaces      Relationships
          |             |             |
          |             +-------> Machines
          |                            |
          |                            v
          |                        Local Map
          |
          +----------------------> Project-local rules

Transient discovery observations and generated indexes sit beside this model,
but are not canonical durable state.
```

## Source-of-truth boundaries

### Governance

Governance answers: **How should the system behave?**

It owns:

- identity semantics;
- type vocabulary;
- lifecycle semantics;
- registration threshold;
- surface and relationship rules;
- change protocol;
- discovery and reconciliation rules;
- privacy and safety boundaries;
- machine-readable schema contracts.

Governance does not own a person's real project inventory.

### Private personal registry

The registry answers: **What durable objects and bindings currently exist?**

It may contain:

- Workspace Objects;
- Surfaces;
- Relationships;
- Machines;
- durable structural Events;
- Policy Exceptions.

It should not become a task manager, knowledge base, chat archive, bookmark store, or secret store.

### Machine-local state

Machine-local state answers: **How is this registry realized on this device?**

It may contain:

- local Surface ID to path mappings;
- trusted discovery roots;
- transient observations;
- generated indexes and caches;
- local host preferences.

Absolute paths are intentionally outside the shared logical identity model.

### Project-local rules

Project-local rules answer: **How does this concrete workspace operate internally?**

Examples include:

- `AGENTS.md`;
- repository build and test commands;
- environment configuration;
- `mise.toml`;
- dev container configuration;
- local repository hygiene rules;
- project-specific verification expectations.

Personal Workspace Governance does not duplicate those details centrally.

### Secret stores

Credentials, API keys, tokens, cookies, private keys, and equivalent secrets belong in appropriate secret-management systems. They are not registry facts.

## Object versus Surface

Use a Surface when the thing is merely one durable representation of an existing Workspace Object.

Use a new Workspace Object when the thing independently deserves its own:

- stable identity;
- type;
- lifecycle;
- surfaces;
- structural history.

Examples:

- A GitHub organization representing a long-lived brand namespace can be an `identity` Surface of the brand.
- A repository inside that organization that has independent maintenance, lifecycle, and execution should be its own Workspace Object, connected by a Relationship if appropriate.
- A cloud project visible from multiple desktop and web clients remains one cloud Surface, not one Surface per client.

## Relationship model

Relationships connect independent Workspace Objects without merging their identity.

Initial vocabulary:

- `part_of` — stable structural belonging;
- `supports` — provides a functional capability or workflow to another object;
- `uses_standard` — follows a reusable standard or playbook represented by another object;
- `depends_on` — a stronger operational dependency;
- `supersedes` — replaces an older object without rewriting historical identity.

Relationships do not cascade lifecycle or destruction.

## Machine model

A Machine is a logical device identity, not a hardware serial number. Its profile should emphasize semantic capabilities and roles. Different machines may have different subsets of the same portfolio and entirely different physical paths.

A shared schema is desirable; identical directory layouts are not.

## Registry versus reality

The registry represents the last verified durable structural state. External systems and filesystems may drift.

A desired future move, clone, split, or migration is not current registry state until it has actually happened and been independently verified.

This distinction enables conservative reconciliation rather than blind synchronization.

## Generated indexes

A SQLite database, search index, or similar derived representation may be used for efficient querying. It must remain rebuildable and must not become the only source of truth.

Recommended derived metadata includes the source registry revision or commit from which the index was built so stale indexes can be detected automatically.

## Architecture constraints

The architecture should remain useful if:

- a specific AI product changes its UI;
- one machine is lost;
- a local path changes;
- a GitHub repository is renamed;
- an external connector temporarily becomes unavailable;
- the user adds a new machine;
- the system is read manually without a specialized agent.

Durability and interpretability take precedence over maximizing automation.
