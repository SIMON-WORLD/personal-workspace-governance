# Personal Workspace Governance

A governance specification and reference toolkit for long-lived personal AI workspaces across cloud projects, local machines, GitHub, and agent workflows.

This project defines a durable model for organizing and reconciling personal work across research, software development, content systems, long-running information hubs, and other AI-assisted workflows without requiring a single filesystem root or a single application to become the source of truth.

> **Start here for day-to-day use:** [`docs/quick-reference.md`](docs/quick-reference.md) — lifecycle ↔ Section mapping, naming, icons, colors, machine IDs, chat numbering, and the one-page source-of-truth map.

## Status

Architecture v0.2 is the current design baseline. It has been stress-tested against multi-machine, cloud-only, local-only, GitHub-backed, research, brand, system, lab, automation, migration, and capture scenarios. The repository is now moving from architecture dogfood into a reviewed specification phase.

## Core model

The durable model is intentionally small:

- **Workspace Object** — the stable identity of a long-lived thing.
- **Surface** — where that object exists or is represented, such as a ChatGPT cloud project, a GitHub resource, or a local execution workspace.
- **Relationship** — an explicit, bounded semantic link between two independent Workspace Objects.
- **Machine** — a logical execution device and its capabilities.
- **Local Map** — machine-local mapping from registered local surfaces to physical paths.
- **Policy Exception** — an explicit, reviewable waiver for known policy drift that should not be repaired immediately.
- **Pre-registry Capture** — a lightweight layer for ideas, screenshots, links, research seeds, and other material that has not crossed the registration threshold.

## Design principles

1. Logical identity is not a filesystem path.
2. Shared policy is not machine-specific state.
3. The registry records durable identity and verified state, not every task, chat, note, or file.
4. Cloud surfaces are singular even when visible from many clients.
5. Provider-native stable identity is preferred over mutable names and URLs when available.
6. Connectors, tools, plugins, and runtime capabilities are not surfaces unless the governed object itself exists on that platform.
7. Incubator is not an inbox.
8. Empty directories do not become local surfaces by default.
9. Relationships never imply destructive or lifecycle cascades.
10. Reconciliation is conservative: observe, propose, validate, approve, apply, verify, record.

## Privacy boundary

This public repository contains only generic specifications, schemas, tooling, and synthetic examples. It must not contain personal registries, absolute personal filesystem paths, unpublished research ideas or materials, conversation exports, credentials, tokens, private capture content, or other sensitive personal data. See [PRIVACY.md](PRIVACY.md).

A real personal instance belongs in a separate private registry. Machine-local path maps should remain local by default.

## Repository map

- [`docs/quick-reference.md`](docs/quick-reference.md) — human cheat sheet / one-page operating map.
- [`SPEC.md`](SPEC.md) — normative specification and vocabulary.
- [`docs/architecture.md`](docs/architecture.md) — architecture and source-of-truth boundaries.
- [`docs/lifecycle-and-registration.md`](docs/lifecycle-and-registration.md) — capture, registration, lifecycle, graduation, and retirement.
- [`docs/chatgpt-ui-conventions.md`](docs/chatgpt-ui-conventions.md) — ChatGPT-specific Section, naming, icon, color, pin, chat-title, cloud/local, and machine-ID conventions.
- [`profiles/chatgpt-default.yaml`](profiles/chatgpt-default.yaml) — machine-readable default ChatGPT UI projection profile.
- [`docs/change-protocol.md`](docs/change-protocol.md) — safe structural mutation protocol.
- [`docs/discovery-reconciliation.md`](docs/discovery-reconciliation.md) — discovery, identity matching, drift classification, and reconciliation.
- [`adr/README.md`](adr/README.md) — accepted architecture decisions from the v0.2 design phase.
- [`schemas/`](schemas/) — machine-readable schema contracts.
- [`examples/synthetic/`](examples/synthetic/) — synthetic examples only.

## Relationship to lower-level workspace standards

This project governs **what long-lived workspace objects exist, where they are represented, how they move through lifecycle, and how drift is reconciled**. It deliberately does not prescribe the internal layout of every local workspace. Project-local conventions, repository instructions, agent task folders, development environments, and hygiene standards remain lower-level concerns.

## License

MIT. See [`LICENSE`](LICENSE).
