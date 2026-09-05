# Lifecycle and Registration

## Why registration is a boundary

Not every idea, chat, screenshot, bookmark, research seed, or temporary experiment deserves a durable Workspace Object.

Registration happens when something crosses a **durable identity boundary**: it becomes useful to ask what it is, where it exists, whether it is still being pursued, and how it relates to other long-lived work.

## Pre-registry capture

Pre-registry capture is intentionally lightweight and may live in ordinary chat, a capture hub, a notes system, or another transient surface.

Typical capture material includes:

- a research idea;
- a screenshot from a phone;
- a news link;
- a technical observation;
- an AI workflow idea;
- a one-off bug report candidate;
- an early learning question.

Capture is not part of the durable registry by default.

## Registration signals

A candidate usually deserves registration when multiple signals are present:

1. **Return** — it is likely to be revisited repeatedly.
2. **Context** — it needs independent long-running context.
3. **Lifecycle** — it needs an explicit incubator/active/hub/archive state.
4. **Surface** — it already has, or clearly needs, an independent cloud/local/GitHub presence.
5. **Distinction** — it must be clearly separated from neighboring ideas or projects.

These are decision aids, not a mechanical score.

## Lifecycle vocabulary

### `incubator`

Use when the object deserves durable identity but commitment is not yet established.

Examples:

- a repository prototype with real code but uncertain continuation;
- a research direction with repeated feasibility work;
- an experimental workflow that is likely to be revisited.

Incubator is not an inbox.

### `active`

Use when the user has explicitly committed to meaningful execution or delivery.

A repository can be `incubator` even if it already exists on GitHub. Type and lifecycle answer different questions.

### `hub`

Use for persistent identities, responsibilities, systems, labs, information centers, brands, and other contexts with no bounded completion target.

Inactivity does not retire a Hub. A Hub is retired only when the durable function or identity itself is no longer needed.

### `archive`

Use when a registered object is inactive, completed, abandoned, or retired.

Archive is reversible and non-destructive. Physical files, cloud projects, repositories, chats, and data may continue to exist.

## Common transitions

```text
capture
  |
  | crosses durable identity boundary
  v
incubator ----commit----> active
    |                       |
    | stop                  | complete/stop
    v                       v
 archive <---------------- archive

persistent function/identity
  |
  v
 hub --------retire------> archive
```

Archive may later restore to incubator, active, or hub when justified by renewed intent.

## Research seeds

Early research activity often begins with background reading, literature search, data feasibility, and repeated conversation before any repository or local workspace exists.

That activity may remain pre-registry until the user decides that the research direction should be preserved as a durable independent object.

A local directory created in anticipation of a project does not by itself force registration or activation of a local Surface.

## Empty directories

An empty directory should normally remain outside the durable Surface model.

A local Surface becomes meaningful when there is explicit activation evidence, such as:

- real project content;
- a workspace identity marker;
- a Git repository;
- use by an agent or desktop workspace as an execution root;
- a declared ongoing local workflow;
- explicit user confirmation that the directory is now the real local execution workspace.

## Lab graduation

A lab may contain many transient experiments that never become Workspace Objects.

An experiment graduates when it gains durable independent identity, such as:

- repeated work;
- its own cloud brain;
- its own Git repository;
- a dedicated local execution workspace;
- a distinct lifecycle.

Graduation registers a new Workspace Object. The originating lab remains a separate persistent object.

## Automations and chats

Ordinary chats and scheduled automations are internal resources by default, not first-class Workspace Objects.

They become independent objects only when they themselves acquire durable independent lifecycle and identity.

## Capture hubs

A persistent cloud-only capture and triage system may itself be a `system` or `hub` Workspace Object even though the individual captured items remain outside the registry.

Its job is to receive, interpret, triage, and route material—not to force every captured item into durable governance.
