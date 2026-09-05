# ChatGPT UI Conventions

This document defines a product-specific projection profile for applying Personal Workspace Governance inside ChatGPT. It is intentionally downstream of the canonical governance model: ChatGPT UI state is a presentation layer, not the source of truth for identity or lifecycle.

## Projection boundary

The canonical registry stores durable facts such as:

- Workspace Object `type`;
- Workspace Object `lifecycle`;
- Surface role;
- Machine identity;
- machine UI preferences where appropriate.

ChatGPT-facing conventions derive presentation from those facts.

Do not duplicate derived UI state in the canonical registry when it can be deterministically inferred.

## Sections

Recommended section projection:

| Lifecycle | Section label |
|---|---|
| `hub` | `🧭 Hubs · 常驻` |
| `active` | `🚧 Projects · 进行中` |
| `incubator` | `🧪 Incubator · 孵化` |
| `archive` | `📦 Archive · 归档` |

The unsectioned area may be used as a capture/inbox convenience, but it is not a fifth lifecycle state.

Moving a ChatGPT Project between these Sections may indicate lifecycle drift, but external UI movement should be reconciled conservatively: adopt the change if it reflects real intent, or repair the UI if it was accidental.

## Project naming

Use:

```text
Type · Stable Name
```

For a local execution counterpart of an existing logical object:

```text
Type · Stable Name · Exec
```

Do not add lifecycle markers such as `进行中`, `Incubator`, stars, arbitrary ordering numbers, or machine IDs to the stable project name.

Examples:

```text
Repo · example-orchestrator
Paper · Example Demand Study
Brand · Example Studio
System · Example Content OS
Lab · Local Experiments · Exec
```

## Icons

Project icons should act as recognition cues for object type.

The governance model does not depend on a fixed product icon catalog. If ChatGPT changes the available built-in icons, choose the nearest semantic cue rather than changing the Workspace Object type.

Suggested cue families:

- academic/book/flask for `paper` and `research`;
- code/repository for `repo`;
- wrench/tool for `tool`;
- cube/package for `product`;
- pen/flag/megaphone for `brand`;
- gear/network for `system`;
- stack/collection for `series`;
- globe/radar for `intel`;
- book/graduation for `learn`;
- compass/domain-specific cue for `area`;
- flask/experiment for `lab`;
- folder/checklist for generic `project`.

Icons are presentation hints only and MUST NOT be used as identity evidence during reconciliation.

## Colors

Color encodes environment/host identity, not lifecycle or urgency.

Recommended rules:

1. Cloud/account-level projects use a neutral/default color where practical.
2. Each machine used for local execution gets one stable distinct color.
3. Machine-to-color assignments belong to the private personal registry as user-specific UI preferences.
4. Public governance documents describe the policy but do not publish a real user's machine-color mapping.
5. Pinning, not color changes, represents temporary focus or priority.

A machine role may change while its color remains stable because the color is attached to the machine identity, not to its current workload.

## Pins

Pin is an orthogonal focus signal.

Pinning does not change:

- Workspace Object lifecycle;
- object type;
- project name;
- machine identity;
- registration state.

Pins are high-frequency UI state and are not part of the canonical registry in the current architecture.

## Conversation titles

Number only long-lived structural threads.

Recommended role bands:

| Number | Role |
|---|---|
| `00` | Brain / Parent Brain / 总控 |
| `10–19` | Research / Literature / Facts / Monitoring |
| `20–29` | Design / Architecture / Strategy / Method |
| `30–39` | Execute / Implementation / Experiment |
| `40–49` | Verify / Review / Test / Audit |
| `50–59` | Write / Docs / Content |
| `60–69` | Ops / Publish / Deploy / Maintenance |
| `90–99` | Meta / Decision Log / Review / Index / Retrospective |

Use gaps so new durable threads can be inserted without renumbering everything.

A `00` Brain should remain lightweight: current goal, accepted decisions, current state, and routing. Specialist work belongs in specialist threads, which return conclusions and evidence to the Brain.

Ordinary temporary chats should normally remain unnumbered.

## Cloud versus local

Do not use `Web Project` versus `Desktop Project` as the conceptual distinction.

Use:

- **Cloud Project** — account-level ChatGPT context visible across clients;
- **Local Surface** — machine-bound folder/workspace used for execution.

One Cloud Project visible from multiple desktops and web clients remains one cloud Surface.

A local folder opened by ChatGPT Desktop or Codex is a machine-bound local Surface when it has actually been activated as a durable workspace.

## Machine IDs

Machine IDs should be stable, neutral logical identifiers. A sequential convention such as `pc-a`, `pc-b`, `pc-c` is suitable when the user wants a simple long-lived namespace.

Do not encode temporary role, physical location, model number, drive path, or priority into the immutable machine ID. Put those facts in mutable fields such as `name`, `classes`, and machine-local state.

The sequence may continue across laptops, desktops, workstations, or virtual machines. If a future environment contains many ephemeral virtual machines, governance may later introduce a separate namespace without changing the identity of already-registered machines.

## Derived-state rule

The following should normally be derived rather than duplicated:

```text
object.lifecycle → ChatGPT Section
object.type      → icon cue
surface.role     → optional name suffix such as · Exec
machine UI prefs → local execution color
```

This avoids contradictory states such as an object whose canonical lifecycle is `active` but whose registry separately claims the Section is `Incubator`.

## Product capability caveat

ChatGPT product capabilities and UI details can change. Section, icon, color, and client-sync behavior should therefore be treated as adapter/profile behavior. If a UI feature is unavailable or not observable through current tooling, record that limitation as `UNOBSERVABLE` rather than inventing canonical state.
