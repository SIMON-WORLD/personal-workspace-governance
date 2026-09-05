# Architecture Decision Record Index

Status meanings:

- **Accepted** — part of the Architecture v0.2 baseline.
- **Provisional** — usable design direction, but implementation experience may still refine details.

The initial decisions below were extracted from repeated architecture dogfood across multi-machine development, research, content systems, cloud-only hubs, local labs, migrations, capture workflows, and upstream-contribution workflows. The public statements are generalized and contain no personal registry data.

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Stable identity is independent of name, type, lifecycle, machine, and path. | Accepted |
| ADR-002 | Surface and Workspace Object are distinct concepts. | Accepted |
| ADR-003 | Independent long-lived objects use explicit Relationships rather than inferred hierarchy. | Accepted |
| ADR-004 | One account-level cloud project remains one Surface across multiple clients. | Accepted |
| ADR-005 | Prefer provider-native stable identity over mutable names and locators. | Accepted |
| ADR-006 | Policy drift may be explicitly deferred instead of forcing immediate repair. | Accepted |
| ADR-007 | Relationships never create implicit lifecycle or destructive cascades. | Accepted |
| ADR-008 | Global governance and project-local workspace hygiene are separate policy layers. | Accepted |
| ADR-009 | Registration is based on durable identity/commitment, not first appearance. | Accepted |
| ADR-010 | Incubator is not an inbox. | Accepted |
| ADR-011 | Chats and scheduled automations are internal resources by default. | Accepted |
| ADR-012 | Brand identity and operating/content systems are separate objects when they can evolve independently. | Accepted |
| ADR-013 | An empty directory is not a Local Surface by default. | Accepted |
| ADR-014 | Pre-registry capture exists outside the durable registry. | Accepted |
| ADR-015 | Workspace Object birth occurs at the durable identity boundary. | Accepted |
| ADR-016 | Connector/tool capability is not a Surface unless the object itself exists on that platform. | Accepted |
| ADR-017 | Hub inactivity is not sufficient evidence of retirement. | Accepted |
| ADR-018 | Local Surface realization is explicit (git / directory / container) and may bind to one provider repository Surface. | Accepted |

## Notes

Individual ADR files may be introduced when a decision needs deeper rationale, alternatives, or implementation consequences. Until then, this index plus `SPEC.md` and `docs/surface-realization-and-discovery.md` (Phase 2.2) is normative for the v0.2 baseline.
