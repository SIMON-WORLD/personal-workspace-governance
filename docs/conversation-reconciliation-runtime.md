# Read-only conversation reconciliation runtime (Phase 2.3A/B)

This implementation follows [the Phase 2.3 design](chatgpt-conversation-reconciliation.md)
and ADR-019. It produces a candidate for independent Parent review, never account
mutation. It does not make ordinary conversations into Registry objects.

## Current execution contract

1. Bind a stable semantic purpose and explicit account/project scope outside titles.
2. Discover current read capabilities. `route()` calls each supplied provider's
   discovery method on every execution. A missing, failed, wrong-scope, expired or
   previous-session provider cannot be selected. Equivalent candidates use input order.
3. Enumerate active and archived partitions within page/item bounds. Only explicit
   provider exhaustion counts as termination. Empty/short pages, unavailable archives,
   cursor loops, errors, scope mismatches and budget exhaustion remain named boundaries.
4. Deduplicate by native ID within the selected provider/account namespace. Conflicting
   observations are `SKIP`; titles never establish identity or Brain authority.
5. Classify deterministically, checkpoint only derived metadata, and return aggregate
   evidence. Read-only refresh starts a new inventory generation; absence from a later
   bounded window does not establish deletion or archive state.
6. Independently reacquire the candidate head, CI and local checkpoint for Parent review.

The provider protocol in `pwg.conversations` has only discovery, list and bounded
context reads. It deliberately has no mutation callback. `RenameBoundary` describes
the future exact mission/proposal/batch/old-title/target-title binding, but its `apply`
always rejects. It is not a Phase 2.3C authorization or implementation.

## Minimal provider integration

Implement `ReadProvider.discover(session, scope)`, `list_page(scope, archive, cursor)`
and, if safely available, `minimal_context(id, max_chars)`. Return typed `Metadata`
and `Page` objects, not native response dictionaries. Discovery reports every required
read capability as `OBSERVABLE`, `PARTIAL`, or `UNOBSERVABLE`. Capabilities are valid
only for that session/scope and for five minutes. Rediscover after a meaningful
provider/session boundary even within that interval.

The host and adapter are trusted executable code, not a sandbox for arbitrary plugins.
They must use a read-only transport and accurately report scope and exhaustion. An
adapter must not claim an account-wide terminal page from a recent-window projection.
The core cannot independently prove an external provider's assertion of exhaustion.

`DesktopReadProvider` is an optional adapter, not the core architecture. Its current
contract is native list schema version 4 and `list_threads(limit=50)`:

| Semantic capability | Current Desktop adapter classification |
| --- | --- |
| conversation.list | PARTIAL: recent mixed-task window, no active cursor |
| conversation.read_metadata | PARTIAL: only returned ChatGPT rows |
| conversation.read_minimal_context | UNOBSERVABLE: host output is not guaranteed ephemeral |
| conversation.observe_project_membership | PARTIAL: visible project ID; null is not verified absence |
| conversation.observe_archive | UNOBSERVABLE: Codex archive API is not a ChatGPT archive API |
| conversation.observe_pin | PARTIAL: app pin projection, not independently verified ChatGPT pin state |

Codex rows are excluded. Archive flags stay null, not false. Pin flags describe only
the app projection, interpreted together with the PARTIAL classification. Project
filtering narrows a window; it does not turn that window into a complete project list.
No private backend endpoint or credential extraction is used.

## Local checkpoint and recovery

Default storage is `~/.workspace-governance/conversation-missions/`, outside both
repositories and cloud-synced project directories. `PWG_HOME` / `--home` can select a
different machine-local home. Git roots, worktrees and their descendants are rejected
after resolving links. Callers managing a non-Git Registry must also supply its path
as `MissionStore(..., forbidden_roots=(registry_root,))`; do not choose Registry storage.

Version 1 is an exact allowlist enforced by `conversation_state.validate()`:

- `schema_version`, `revision`, `semantic`, `scope`, `provider`;
- `inventory_generation`, `observed_at`, `proposal_revision`, `next_safe_action`;
- `proposals`: only native ID, title, project ID, nullable archive/pin flags,
  derived status/reason and optional proposed title;
- `summary`: counts, partition termination/page counts and historical observability.

No runtime session ID, cursor, raw provider error, summary/snippet, body, attachment,
mapping tree or credential is checkpointed. Unknown fields at every nesting level are
rejected. The host must keep source content out of its own transcripts/logs too;
bounded input size alone does not guarantee privacy.

Semantic recovery uses exact purpose + account/project scope across at most 100
checkpoints: zero matches is `not_found`, one is `recover`, multiple is `ambiguous`.
Malformed/oversized checkpoints fail closed rather than being silently ignored. There
is no newest-file fallback. Account binding is a host responsibility: a friendly alias
does not prove which account is currently signed in. If that binding cannot be
reestablished after replacement/account switching, stop for an account-scope boundary.
Changing providers does not silently merge their native identity namespaces.

Writes validate first, flush a temporary file, then atomically replace the checkpoint.
Expected revision detects stale sequential writers; this is a single local executor
contract, not concurrent-writer locking. A failed generation can safely restart reads;
uncommitted pages are not persisted. Recovery always returns
`rediscover_then_refresh_read_only`; saved capabilities are historical evidence.

```sh
pwg --home /machine-local/pwg conversation-recover \
  --mission garden-title-reconciliation --account synthetic-account
```

The output is aggregate-only and labels recovered observations historical. Inspect
individual proposals only in the local checkpoint, never in public CI or GitHub.

## Metadata-only Desktop host bridge

For a host with native tools, call the current `list_threads` first, then immediately
project only ChatGPT `kind`, `id`, `title`, `projectId` rows into this stdin envelope:

```json
{
  "session": "current-host-session",
  "observed_at": "2026-01-01T12:00:00+00:00",
  "scope": {"account": "synthetic-account", "project": null},
  "snapshot": {
    "schemaVersion": 4,
    "pinnedThreads": [],
    "threads": [{"kind": "chatgpt", "id": "synthetic-chat", "title": "Garden study", "projectId": null}]
  }
}
```

Pipe it to `pwg --home /machine-local/pwg conversation-observe-desktop --mission
garden-title-reconciliation --account synthetic-account`. Use a fresh timestamp, not
the example timestamp. The bridge rejects envelopes older than five minutes, raw
native-response fields and Codex rows. It consumes one observation, invokes the same
adapter/core/checkpoint path, and prints counts only. The envelope is an input boundary
for a live host, not an independent ChatGPT connection or proof of account identity.
Do not replay a saved inventory with a new timestamp and call it runtime discovery.

## Proposal policy and validation

Descriptive ordinary titles are kept; whitespace normalization may propose a rename.
Generic, short, duplicate and structurally numbered titles require a decision.
Structural role must come from external governance evidence, never title inference.

Optional policy-authored keyword rules can derive fixed natural-language titles from
at most 1,200 ephemeral characters per chat, at most 20 reads per invocation. They are
disabled by default. Zero or multiple matches abstain. Text is never copied into a
proposal; target collisions also abstain. The Desktop adapter does not enable this
route because its host output cannot promise ephemeral context.

`EphemeralContextReadProvider` is the narrow opt-in bridge for a host that can make
that promise. The host must explicitly attest `ephemeral_context=True`; the adapter
then advertises `conversation.read_minimal_context` as `OBSERVABLE`, validates the
conversation ID, 1,200-character bound and returned text, and drops the text when
the call returns. Without the attestation it forces the capability to
`UNOBSERVABLE` and never calls the supplied reader. The host remains responsible for
keeping source text out of its own transcript and logs. Current PC-B native and
browser surfaces do not expose a programmatic ephemeral callback that can be bound
to this adapter; rendered browser messages are not treated as that contract. The
current proposal pool therefore remains read-only and context-assisted rows remain
ungenerated.

Run `python -m unittest discover -s tests -v` with `PYTHONPATH=src`, followed by
`python scripts/validate.py`. Synthetic tests cover routing and freshness, both list
partitions, exhaustion/cursor/scope/error boundaries, deduplication/conflicts, proposal
abstention and fixed context rules, recursive privacy validation, process replacement,
semantic ambiguity, revision checks and repository exclusion. Existing Phase 2.1/2.2
tests remain part of the same suite. Real dogfood evidence stays machine-local;
publish only bounded counts and named capability boundaries with the exact PR head.

## Stage C0 rename canary boundary

`pwg.rename_c0` is the narrow preparation layer for the first real canary. A
`MutationProbe` exposes only `discover_rename(session, scope)`; it has no rename
callback. The returned surface must report all four facts as `OBSERVABLE` before
the route can be `FOUND`: `conversation.rename`, exact metadata reacquisition,
title verification, and non-target verification. Provider exceptions are discarded
from evidence. Stale observations (older than five minutes), wrong sessions, and
incomplete capability maps fail closed.

`prepare_exact_batch()` accepts only `RENAME_PROPOSED` items whose reason is a
policy-backed high-confidence cleanup (`title_whitespace` or `context_rule`). It
auto-binds the whole pool only when exactly three proposals are eligible. Fewer
remains `BLOCKED`; when more are eligible, Parent must pass an explicit selection of
exactly three native IDs. The selection is sorted and frozen into the batch, with no
substitution or expansion after preparation. Each prepared item binds the provider
native ID, expected old title, target title, proposal revision, inventory generation,
route, and a fresh execution generation. The exact batch is machine-local and its
fingerprint is derived from the binding. Structural, generic, duplicate, stale, or
ambiguous proposals never enter it.

`C0Store` keeps aggregate evidence and the exact batch as one actionable authorization
unit outside Git and the private Registry. The evidence records the batch fingerprint,
proposal revision, inventory generation, and execution generation; recovery returns a
batch only when every binding matches exactly. A prepared payload is written before
its evidence and a failure between those writes removes the payload. A later blocked
write revokes any older payload before publishing blocked evidence. Public evidence
contains only route/capability states, counts, revisions, privacy status, and
`chatgpt_write_requests=0`; the local batch is the only place exact IDs and titles can
appear. C0 evidence is not C1 authorization: `c1_safe_to_authorize` is true only when
a complete route and exactly three bound items both exist. A blocked route or missing
candidate leaves the batch absent and requires Parent `AUTHORIZE C1` before any future
write work.
