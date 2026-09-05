# Discovery and Reconciliation

Discovery and reconciliation keep the durable registry aligned with reality without turning the governance system into an unrestricted scanner or destructive synchronizer.

## Design goal

The reconciler compares registered durable state with freshly observed reality, classifies drift, proposes a safe resolution, and verifies any applied change.

It is conservative by default.

## Scope expansion

Local discovery should expand gradually:

1. current workspace;
2. registered local workspaces on the current machine;
3. configured trusted roots;
4. a wider user-authorized temporary search scope.

Whole-disk recursive discovery is not a default behavior.

## Metadata-first discovery

Workspace discovery should prefer structural metadata over content indexing.

Examples of useful identity metadata:

- filesystem existence and path metadata;
- Git repository root;
- provider remote identity;
- repository or organization provider ID;
- optional workspace identity marker;
- project-local configuration or manifest evidence.

Discovery should not read private documents, datasets, screenshots, `.env` files, research drafts, or arbitrary personal content merely to decide whether a workspace exists.

## Adapter model

Each surface family should have an adapter with explicit capabilities such as:

- `discover`
- `read_identity`
- `read_metadata`
- `mutate`
- `verify`

Capability may vary by runtime and provider. Lack of visibility must remain explicit.

A ChatGPT adapter, for example, may be partial or manual when stable project metadata is not machine-readable. `UNOBSERVABLE` is a valid result and must not be treated as absence.

## Identity matching

Identity matching should prefer stronger evidence over names.

For GitHub-backed work, useful evidence ordering is typically:

1. provider-native repository/organization identity;
2. canonical remote identity;
3. known registered Surface identity;
4. human-facing name or folder name.

A repository rename should normally update the mutable locator while preserving the same provider identity and Surface identity.

For non-Git local workspaces, an optional lightweight identity marker may strengthen move detection. Duplicate markers must be treated as ambiguous because copying a directory can preserve the same marker.

## Finding classes

### `MATCH`

Registered state and observed reality agree.

Default action: none.

### `DRIFT`

A known object's observed durable attributes differ from registered state.

Default action: propose reconciliation.

### `MISSING`

A registered Surface or local mapping is authoritatively absent in an otherwise reachable environment.

Default action: do not delete automatically; propose restore, re-clone, detach, remap, or another bounded resolution.

### `UNREGISTERED`

A candidate durable object or Surface exists in the discovery scope but is not represented in the registry.

Default action: propose register/attach/ignore. Discovery does not imply registration.

### `AMBIGUOUS`

Identity cannot be established reliably or multiple candidates compete for the same logical identity.

Default action: fail closed and request resolution.

### `UNREACHABLE`

A disk, network location, provider, or account cannot currently be reached.

Default action: preserve durable state; do not infer deletion.

### `UNOBSERVABLE`

The current adapter or runtime lacks sufficient capability to verify the target.

Default action: preserve durable state and expose the observability limit.

### `POLICY_MISMATCH`

Reality is valid and identifiable but does not satisfy a governance or workspace-placement policy.

Default action: propose repair or explicit defer/waiver.

## Reconciliation dispositions

### `ADOPT`

Accept verified external reality and update durable registered state.

Example: a workspace was intentionally moved to a new path and strong identity evidence confirms the move.

### `REPAIR`

Restore external reality to the registered or governed state.

Example: a local remote points to a stale locator after a provider rename.

### `DETACH` / `RETIRE`

Explicitly remove a no-longer-valid Surface or Machine relationship.

### `DEFER`

Keep the mismatch unresolved because immediate repair would be unsafe or undesirable. Durable recurring exceptions should be represented as Policy Exceptions rather than repeatedly producing noisy findings.

## Freshness

A reconciliation plan must not rely indefinitely on stale observations.

Before applying a change, affected targets should be freshly reacquired and preconditions revalidated. If the expected revision or observed identity changed, the plan should fail closed and be recomputed.

## Windows-specific path handling

Path identity must not rely on naive string equality.

Implementations should account for:

- case-insensitive path semantics where applicable;
- `\` versus `/` separators;
- trailing separators;
- junctions and symlinks;
- mapped/network drives;
- cloud-sync placeholders;
- canonical filesystem resolution where safe.

User-facing paths and normalized runtime paths may be distinct representations.

## Same object, multiple local instances

A Workspace Object may legitimately have multiple local Surfaces on one machine or across machines.

Examples include:

- a primary clone and a worktree;
- an experimental checkout;
- two independent local execution instances;
- machine-specific lab realizations.

Same remote identity is not sufficient evidence to merge or delete local instances.

## Recommended operating modes

### Quick

Inspect only the current workspace and its registered identity.

Suitable for routine agent entry checks.

### Registered

Inspect all registered local Surfaces for the current machine.

Suitable for periodic health/reconciliation review.

### Discover

Inspect configured trusted roots for unregistered candidates.

Suitable for explicit or low-frequency portfolio discovery, not every agent startup.

## Project health is separate

Workspace reconciliation should not absorb ordinary project health concerns such as:

- dirty Git state;
- failing tests;
- red CI;
- stale dependencies;
- branch divergence.

Those belong to project execution and verification layers.

## Privacy boundary

Discovery observes only what is necessary for structural identity unless the user explicitly authorizes content-aware analysis for a separate task.

Sensitive domains such as research, finance, health, and personal archives must not be implicitly indexed merely because their Workspace Object exists in the registry.
