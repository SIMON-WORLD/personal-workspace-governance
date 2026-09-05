# Privacy Boundary

This repository is intentionally public. It documents a reusable governance model and therefore accepts **generic specifications, schemas, tooling, and synthetic examples only**.

## Never commit

Do not commit any of the following:

- a real personal workspace registry or complete project inventory;
- absolute personal filesystem paths, drive layouts, usernames, or device-specific private locations;
- unpublished research ideas, drafts, datasets, notes, or sensitive academic materials;
- private screenshots, bookmarks, inbox/capture contents, conversation exports, or personal knowledge-base dumps;
- account identifiers, installation identifiers, session identifiers, credentials, API keys, tokens, cookies, secrets, or `.env` contents;
- personal health, finance, legal, identity, family, or similarly sensitive records;
- private repository contents or proprietary work copied only for examples.

## Synthetic examples only

Examples in this repository must use fictional names and non-sensitive placeholder locations. They should demonstrate structure without recreating an individual's real inventory.

Good:

```text
Paper · Example Demand Study
Repo · example-orchestrator
D:/Research/example-study
example-org/example-repo
```

Bad:

```text
A real unpublished paper title
A real personal absolute path
A private repository name
A copied ChatGPT conversation
```

## Separation of concerns

The intended deployment model is:

1. **Public governance repository** — reusable policy, architecture, schemas, validation, synthetic examples.
2. **Private personal registry** — real Workspace Objects, Surfaces, Machines, Relationships, Events, and durable personal state.
3. **Machine-local state** — absolute local path maps, caches, observations, and other host-specific state; local by default.
4. **Secret store** — credentials and secrets; never stored in any of the above layers as plaintext governance data.

## Sanitizing design evidence

Real-world dogfood may motivate a rule or architecture decision, but public documentation must record the generalized lesson, not the underlying private case. A path migration issue, for example, should be described as a synthetic legacy-workspace scenario rather than preserving the original path or project identity.

## History matters

Removing sensitive data in a later commit does not make a prior public commit private. Before every public write, contributors and agents must review the complete proposed diff for privacy violations.
