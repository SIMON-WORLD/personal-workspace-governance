# ChatGPT Conversation Reconciliation

Status: **Phase 2.3 design baseline**

This document defines the minimal governance contract for reconciling ChatGPT conversation titles at scale. It applies to ordinary ChatGPT conversations as internal resources. It does not promote chats into Workspace Objects and does not define Project rename, archive/delete, pin mutation, or Codex-session governance.

## 1. Goal

The immediate goal is narrow:

> Safely inventory, classify, propose, and later rename large numbers of ChatGPT conversation titles without turning conversation content into canonical registry state or coupling the workflow to one provider implementation.

The target workflow is:

```text
Observe
-> classify
-> propose
-> authorize bounded batch
-> apply exact title mutation
-> independently reacquire
-> verify
-> checkpoint
```

## 2. Provider-neutral capability contract

Conversation reconciliation is defined in terms of required capabilities, not a permanent provider.

Read capabilities:

- `conversation.list`
- `conversation.read_metadata`
- `conversation.read_minimal_context`
- `conversation.observe_project_membership`
- `conversation.observe_archive`
- `conversation.observe_pin`

Write capability:

- `conversation.rename`

Verification capabilities:

- `conversation.verify_title`
- `conversation.verify_non_target_fields_unchanged`

A provider may be ChatGPT-native/Desktop, a logged-in browser surface, a connected tool, or another runtime surface that is actually available and authorized at execution time. Provider selection follows current runtime capability discovery. Historical availability is not proof of current availability.

The normal sequence is:

```text
authority / mission bind
-> canonical refresh
-> runtime capability discovery
-> choose the smallest sufficient route/provider
```

Read-only work may continue when write capability is unavailable.

## 3. Conversation identity

Provider-native conversation identity is authoritative for a conversation instance. Titles are mutable presentation metadata and must never be used as the sole identity key.

A structural title such as `00 · Brain · ...` does not grant Brain authority. Conversation title, transcript, summary, and UI placement remain interaction/context surfaces rather than control truth.

## 4. Durable machine-local reconciliation mission

Large-scale reconciliation must survive session replacement and execution interruption without relying on transcript memory.

Mission state is machine-local and must not be written into the public governance repository or private Workspace Registry.

A minimal durable mission should track:

- mission semantic identity;
- schema version and revision;
- inventory generation and observation time;
- proposal revision;
- current/previous batch identity;
- per-conversation outcome such as `proposed`, `needs_decision`, `authorized`, `renamed`, `verified`, `stale`, `failed`, `skipped`;
- bounded retry state;
- next safe action.

Recovery is semantic and bounded:

- zero valid matches -> `not_found`;
- exactly one valid match -> recover;
- more than one valid match -> `ambiguous` and fail closed.

There is no generic "resume most recent" fallback and the user must not relay internal run, batch, or conversation identifiers as normal control flow.

Capability observations are freshness-scoped runtime evidence. Persisting a prior observation must never convert it into timeless proof that the same capability is still executable.

## 5. Pointer-not-payload and privacy

Ordinary chats remain internal resources under ADR-011.

Do not create one Registry object/file per conversation. Do not copy full chat inventories into the Workspace Registry or public governance repository.

Machine-local reconciliation state may persist only the minimum metadata required to reconcile and resume, such as:

- provider-native conversation ID;
- current title;
- relevant timestamps;
- observable project/archive/pin flags;
- proposed title;
- classification/confidence;
- execution/verification outcome.

Conversation body, mapping trees, attachments, snippets, credentials, cookies, access tokens, and authorization headers must not be persisted by default.

When the existing title is insufficient for classification, bounded minimal context may be read ephemerally. Raw content is not persisted; only the derived proposal/classification may be retained.

Brain-facing checkpoints should be aggregated and exception-oriented rather than payload dumps.

## 6. Thin Brain and bounded execution authority

The authoritative Brain owns:

- naming policy;
- classification/confidence policy;
- batch policy;
- mutation scope;
- escalation boundary;
- milestone acceptance.

The Brain does not approve every ordinary title one by one when a bounded policy already authorizes the batch.

A rename executor may only act on an explicitly authorized exact batch. The authorization must bind at least:

- exact reconciliation mission;
- exact proposal revision;
- exact batch;
- exact conversation IDs;
- expected old titles;
- target titles.

The executor may perform only:

- precondition checks for those conversations;
- title rename for those conversations;
- independent post-write reacquisition/verification;
- recording results for the same batch.

It must not infer authority to archive, delete, pin/unpin, move Project membership, rename Projects, expand the batch, rewrite naming policy, or create a new reconciliation mission.

If an execution session is replaced while the same mutable title resources are in scope, stale-session fencing or equivalent generation semantics must prevent the superseded writer from continuing new mutations.

This is a narrow execution-safety contract, not a generic RBAC, scheduler, lease, or distributed-lock framework.

## 7. Rename precondition and verification

Before a title mutation, reacquire the exact conversation by provider-native identity and verify that the current title still equals the proposal's expected old title.

If the title has changed, classify the proposal as stale and do not mutate it.

After mutation, independently reacquire the exact conversation and verify:

- provider-native identity is unchanged;
- title equals the intended target;
- observable non-target state covered by the provider remains unchanged.

A successful mutation response alone is not final acceptance evidence.

## 8. Phase 2.3 milestones

### Phase 2.3A — Conversation Reconciliation Foundation

Implement the smallest reusable foundation for:

- provider-neutral capability declarations/routing;
- runtime capability bootstrap;
- machine-local durable mission/checkpoint;
- semantic recovery;
- privacy boundary;
- proposal representation;
- bounded rename-authorization contract skeleton.

No real ChatGPT mutation is required for 2.3A acceptance.

### Phase 2.3B — Complete Inventory + Proposal

Prove that the chosen current runtime route can obtain a sufficiently complete and deduplicated inventory for the intended reconciliation scope, then generate rename proposals with bounded ephemeral context where needed.

Mutation count must remain zero.

### Phase 2.3C — Rename Safe-Apply Canary

After 2.3A/B acceptance, authorize only a tiny exact batch of high-confidence conversations. Require exact-ID preconditions, reacquisition, persistence verification, stale handling, checkpoint/resume, and one-writer semantics.

### Phase 2.3D — Account Migration

Expand only from successful dogfood evidence, for example:

```text
3
-> 10-20
-> 50 per batch
-> larger account migration
```

Remaining ambiguous or low-confidence conversations stay as explicit exceptions rather than being force-renamed for a clean count.

## 9. Non-goals

Phase 2.3 does not justify:

- a generic workflow engine;
- generic RBAC or distributed locking;
- multi-Parent or multi-Brain hierarchy;
- a global static ChatGPT capability registry;
- transcript warehousing;
- conversation-as-Workspace-Object modeling;
- Project rename architecture;
- Codex session governance;
- automatic archive/delete cleanup;
- a general-purpose UI automation framework.

Complexity must be earned by real reconciliation dogfood.
