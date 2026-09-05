# Personal Workspace Governance Specification

Status: Architecture v0.2 baseline

This specification defines a durable, tool-agnostic governance model for long-lived personal AI workspaces spanning cloud projects, local machines, GitHub resources, and agent-assisted workflows.

## 1. Normative language

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be interpreted as normative requirements.

## 2. Core entities

### 2.1 Workspace Object

A Workspace Object is the durable logical identity of a long-lived thing that deserves independent lifecycle, context, or execution tracking.

A Workspace Object MUST have a stable immutable `id`. Its human-facing `name`, `type`, `lifecycle`, and aliases MAY change without changing identity.

The stable ID MUST NOT encode type, lifecycle, machine, or physical path.

Recommended first-class object types:

- `paper`
- `research`
- `repo`
- `tool`
- `product`
- `brand`
- `system`
- `series`
- `intel`
- `learn`
- `area`
- `lab`
- `project`

New types SHOULD be added only when the existing vocabulary cannot express a recurring class of object.

### 2.2 Surface

A Surface is a durable representation or execution presence of a Workspace Object on a platform or machine.

Examples include:

- a ChatGPT cloud project used as a long-running brain;
- a GitHub repository used as an authoritative source surface;
- a GitHub organization used as an identity surface;
- a local machine workspace used for execution.

A Surface is not a new Workspace Object unless the represented thing independently deserves its own identity and lifecycle.

Recommended surface roles:

- `brain`
- `exec`
- `source`
- `publish`
- `reference`
- `identity`

Cloud visibility from multiple clients MUST NOT create duplicate cloud surfaces. A single account-level cloud project remains one Surface even when visible from web, desktop, mobile, or multiple machines.

Runtime connectors, plugins, MCP servers, tools, and account capabilities MUST NOT be modeled as Surfaces unless the governed object itself exists on that platform.

### 2.3 Relationship

A Relationship is an explicit directional semantic link between two independent Workspace Objects.

Initial relationship vocabulary:

- `part_of`
- `supports`
- `uses_standard`
- `depends_on`
- `supersedes`

Relationships MUST NOT imply automatic lifecycle, archive, delete, filesystem, or other destructive cascades.

Platform placement MUST NOT automatically infer semantic relationships. For example, placing a repository in an organization's GitHub namespace does not by itself prove that the repository is semantically `part_of` that organization's corresponding Workspace Object.

### 2.4 Machine

A Machine is a stable logical execution device identity.

Machine identity SHOULD describe role and capability rather than hardware serials or private operating-system identifiers. A machine profile MAY declare semantic classes such as `heavy-dev`, `data-analysis`, `writing`, or `portable`.

### 2.5 Local Map

A Local Map is machine-local state that maps registered local Surface IDs to physical filesystem paths.

Absolute paths MUST NOT be part of Workspace Object identity. Local Maps SHOULD remain local by default and SHOULD NOT be stored in the public governance repository.

### 2.6 Policy Exception

A Policy Exception records a known policy mismatch that has been intentionally accepted or deferred.

A Policy Exception MUST NOT rewrite the underlying Workspace Object into a false compliant state. It records that drift is known, why it is not being repaired yet, and how it should be reviewed later.

## 3. Lifecycle

The canonical lifecycle vocabulary is intentionally small:

- `hub` — persistent identity, responsibility, system, lab, or long-running context without a bounded completion target;
- `active` — committed work with an active execution outcome;
- `incubator` — registered work worth preserving independently but not yet committed;
- `archive` — inactive, completed, abandoned, or retired portfolio state.

A UI section MAY project these lifecycle values into product-specific navigation labels. Product UI labels MUST NOT become independent lifecycle sources of truth.

Archive is a portfolio state, not deletion. Archiving a Workspace Object MUST NOT automatically delete its cloud projects, repositories, local folders, chats, or data.

Hub inactivity MUST NOT by itself imply retirement.

## 4. Registration threshold

Ordinary chats, screenshots, links, bookmarks, research seeds, one-off experiments, and temporary ideas do not automatically become Workspace Objects.

An item SHOULD cross the registration boundary when it requires a durable independent identity. Useful signals include:

- repeated return over time;
- independent long-running context;
- a lifecycle that needs to be managed;
- an independent cloud, local, or GitHub surface;
- a clear need to distinguish it from related ideas or work.

`Incubator` is not an inbox. Pre-registry capture remains outside the durable registry until the identity threshold is crossed.

An empty local directory is not sufficient evidence of an active local Surface unless it has been explicitly activated or contains meaningful workspace evidence.

## 5. Change protocol

Durable structural changes SHOULD follow:

`OBSERVE -> PROPOSE -> VALIDATE -> APPROVE -> APPLY -> VERIFY -> RECORD`

The current registry records verified durable state. A proposed future action or migration intent does not become registry reality until it has been applied and verified.

Recommended structural operations include:

- `REGISTER`
- `RENAME`
- `RETYPE`
- `PROMOTE`
- `ARCHIVE`
- `RESTORE`
- `ATTACH_SURFACE`
- `DETACH_SURFACE`
- `UPDATE_SURFACE`
- `REGISTER_MACHINE`
- `RETIRE_MACHINE`
- `MAP_LOCAL_PATH`
- `REMAP_LOCAL_PATH`
- `UNMAP_LOCAL_PATH`
- `LINK_OBJECTS`
- `UNLINK_OBJECTS`

Higher-risk identity migrations such as object merge and split MAY be introduced later but SHOULD NOT be silently simulated through ordinary rename or delete operations.

## 6. Discovery and reconciliation

Discovery MUST be bounded and metadata-first. A local discovery engine SHOULD expand scope gradually from the current workspace, to registered local workspaces, to configured trusted roots, and only then to an explicitly authorized wider search.

Discovery MUST NOT default to indexing arbitrary personal content or scanning entire disks merely to identify workspace structure.

Findings SHOULD be classified using at least:

- `MATCH`
- `DRIFT`
- `MISSING`
- `UNREGISTERED`
- `AMBIGUOUS`
- `UNREACHABLE`
- `UNOBSERVABLE`
- `POLICY_MISMATCH`

`UNREACHABLE` and `UNOBSERVABLE` MUST NOT be treated as proof of deletion or absence.

Reconciliation MAY result in:

- `ADOPT` — accept verified external reality and update durable state;
- `REPAIR` — restore reality to the registered policy/state;
- `DETACH` or `RETIRE` — explicitly remove a no-longer-valid binding;
- `DEFER` — leave a known mismatch unresolved, normally with an explicit Policy Exception when durable review is needed.

Before applying a reconciliation plan, affected targets SHOULD be freshly reacquired and preconditions revalidated.

## 7. Identity matching

Identity matching SHOULD prefer stable provider-native identity over mutable names, URLs, and folder names.

For GitHub resources, provider-native repository or organization identity SHOULD be retained when available while human-facing locators such as names or URLs MAY change.

For non-Git local workspaces, an optional lightweight workspace identity marker MAY be used to survive moves. Duplicate markers MUST be treated conservatively because a copy is not necessarily a move.

Path string equality alone MUST NOT be used as workspace identity, particularly on Windows where case, separators, junctions, symlinks, and mapped storage can differ.

## 8. Storage boundaries

The recommended deployment model is:

- public governance: Markdown documentation, schemas, validation, synthetic examples;
- private personal registry: real Workspace Objects, Surfaces, Relationships, Machines, durable Events, and Policy Exceptions;
- machine-local state: absolute local path maps, transient observations, caches, and generated indexes;
- project-local state: repository instructions, build/test commands, environment configuration, and workspace-internal rules;
- secret store: credentials and tokens.

A generated database or search index MUST NOT be the only source of truth. Derived indexes SHOULD be rebuildable from canonical text-based state plus machine-local maps as appropriate.

## 9. Privacy

The public governance repository MUST use synthetic examples only and MUST follow `PRIVACY.md`.

Private registries SHOULD still avoid secrets. Credentials belong in an appropriate secret store, not in governance or registry files.

## 10. Layered policy

Global governance defines identity, lifecycle, registration, relationships, change control, and reconciliation semantics.

It MUST NOT automatically override project-local workspace hygiene. A local lab may forbid nested repositories while another meta-workspace may intentionally contain multiple repositories. Lower-level project or workspace standards remain authoritative for their own internal layout.
