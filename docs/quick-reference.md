# Personal Workspace Governance — Quick Reference

This is the human-facing cheat sheet for day-to-day use. It is intentionally shorter than `SPEC.md` and the architecture documents.

## 1. Lifecycle → ChatGPT Section

| Canonical lifecycle | ChatGPT section projection | Meaning |
|---|---|---|
| `hub` | `🧭 Hubs · 常驻` | Persistent identity, system, brand, lab, area, or long-running context. |
| `active` | `🚧 Projects · 进行中` | Committed work with an active execution outcome. |
| `incubator` | `🧪 Incubator · 孵化` | Registered and worth preserving, but not yet committed. |
| `archive` | `📦 Archive · 归档` | Inactive, completed, abandoned, or retired; reversible and non-destructive. |

Unsectioned / ordinary chat space may be used for lightweight capture or inbox-style triage. It is not a fifth canonical lifecycle state.

## 2. Naming

Canonical human-facing project name:

```text
Type · Stable Name
```

Examples:

```text
Paper · Example Demand Study
Repo · example-orchestrator
Brand · Example Studio
System · Example Content OS
Intel · Example Intelligence
Lab · Local Experiments
```

When the same logical object has a machine-bound local execution project, append the execution role:

```text
Type · Stable Name · Exec
```

Do not encode lifecycle, priority, machine identity, or temporary ordering into the stable project name.

## 3. What each UI cue means

| Cue | Meaning |
|---|---|
| Section | Lifecycle/status projection |
| Project name | Stable object identity |
| Project icon | Type/object cue |
| Project color | Environment or machine cue |
| Pin | Current focus/priority |
| Chat title | Thread role inside the object |

Avoid encoding the same semantic dimension twice.

## 4. Chat numbering

Use numbering only for long-lived structural threads. Ordinary one-off chats do not need a number.

| Range | Role |
|---|---|
| `00` | Brain / Parent Brain / 总控 |
| `10–19` | Research / Literature / Facts / Monitoring |
| `20–29` | Design / Architecture / Strategy / Method |
| `30–39` | Execute / Implementation / Experiment |
| `40–49` | Verify / Review / Test / Audit |
| `50–59` | Write / Docs / Content |
| `60–69` | Ops / Publish / Deploy / Maintenance |
| `90–99` | Meta / Decision Log / Review / Index / Retrospective |

Use gaps. A `00` Brain should keep the current goal, key decisions, state, and next routing; heavy research, debugging, or execution logs belong in specialist threads.

## 5. Type cues

Current first-class type vocabulary:

```text
paper
research
repo
tool
product
brand
system
series
intel
learn
area
lab
project
```

Recommended icon cues are semantic rather than product-specific identifiers because available built-in icons may change:

| Type | Suggested visual cue |
|---|---|
| `paper`, `research` | academic / book / flask |
| `repo` | code / repository |
| `tool` | wrench / tool |
| `product` | cube / package |
| `brand` | pen / flag / megaphone |
| `system` | gear / network |
| `series` | collection / stack |
| `intel` | globe / radar |
| `learn` | book / graduation |
| `area` | compass / domain-specific cue |
| `lab` | flask / experiment |
| `project` | folder / checklist |

The icon is a hint for recognition, not canonical state.

## 6. Color policy

Use color to distinguish environment or host, not priority or lifecycle.

Recommended policy:

- Cloud/account-level projects: neutral/default color.
- Local execution projects: one stable distinct color per machine.
- Keep a machine's color stable over time.
- Store the actual machine-to-color assignment in the private personal registry, not in this public repository.
- Use Pin for temporary priority instead of changing colors.

## 7. Machine identity

Machine IDs should remain neutral and stable even when the machine's role changes.

A simple sequential convention is valid:

```text
pc-a
pc-b
pc-c
pc-d
...
```

Descriptive or changeable properties belong in `name`, `classes`, and UI preferences rather than in the immutable machine ID.

Example:

```yaml
id: pc-c
name: Example Laptop
classes:
  - portable
  - writing
```

The same convention may continue for future laptops, desktops, workstations, or virtual machines unless scale later justifies a separate namespace.

## 8. Registration rule

Do not create a Workspace Object merely because an idea, screenshot, link, empty folder, or one-off chat exists.

Register when the thing crosses a durable identity boundary: it needs its own long-running context, lifecycle, recurring return, independent surface, or clear distinction from neighboring work.

`Incubator` is not an inbox.

## 9. Surface reminders

- One account-level ChatGPT Project visible from web, desktop, mobile, or multiple machines is still one cloud Surface.
- A GitHub repository or organization may be a Surface when the governed object itself exists there.
- A Connector, plugin, MCP server, or runtime capability is not automatically a Surface.
- An empty local directory is not a local Surface by default.
- Absolute local paths remain machine-local state.

## 10. Source-of-truth map

```text
Public Governance
  ├─ rules / schemas / naming / UI projection conventions
  └─ synthetic examples only
          ↓
Private Personal Registry
  ├─ real Workspace Objects
  ├─ real Surfaces / Relationships / Machines
  └─ actual machine UI preferences such as pc-a → color
          ↓
Machine-local State
  ├─ absolute local paths
  ├─ discovery roots
  └─ caches / observations / generated indexes
```

When in doubt, remember:

```text
Section = lifecycle
Name    = identity
Icon    = type cue
Color   = machine/environment cue
Pin     = current focus
```
