# Change Protocol

Durable workspace governance must distinguish a proposed change from an observed event and from the current registered state.

## Command, Event, State

- **Command / Proposal** — a requested or proposed structural change.
- **Event** — an immutable record that a validated structural change occurred.
- **State** — the current durable registry representation after successful verification.

Agents should not mutate durable state while they are still deciding what the change means.

## Canonical flow

```text
OBSERVE
  -> PROPOSE
  -> VALIDATE
  -> APPROVE
  -> APPLY
  -> VERIFY
  -> RECORD
```

### Observe

Read fresh authoritative state from the registry and affected external/local surfaces.

### Propose

Generate a bounded Change Set describing intended semantic changes without applying them.

### Validate

Check schema, policy, identity, expected revision, surface reachability, privacy constraints, and operation-specific preconditions.

### Approve

Apply policy-based authorization. Low-risk deterministic maintenance may be pre-authorized; durable semantic mutation should normally require explicit approval unless a trusted automation policy says otherwise.

### Apply

Perform the requested mutation against the appropriate source of truth or external surface.

### Verify

Reacquire affected state independently. A successful write response is not sufficient proof that the intended durable state now exists.

### Record

Update canonical state only after verification and append an immutable structural Event.

## Recommended operations

### Workspace Object

- `REGISTER`
- `RENAME`
- `RETYPE`
- `PROMOTE`
- `ARCHIVE`
- `RESTORE`

### Surface

- `ATTACH_SURFACE`
- `DETACH_SURFACE`
- `UPDATE_SURFACE`

### Relationship

- `LINK_OBJECTS`
- `UNLINK_OBJECTS`

### Machine

- `REGISTER_MACHINE`
- `RETIRE_MACHINE`

### Local mapping

- `MAP_LOCAL_PATH`
- `REMAP_LOCAL_PATH`
- `UNMAP_LOCAL_PATH`

Object merge and split are intentionally deferred because they are identity migrations rather than ordinary metadata changes.

## Risk classes

### Observe-safe

Examples:

- schema validation;
- reading registered state;
- rebuilding a derived index;
- checking path existence;
- checking provider identity;
- generating findings and proposed Change Sets.

These actions may normally run without structural approval.

### Propose-by-default

Examples:

- registering a new object;
- renaming or retyping an object;
- lifecycle transitions;
- adding or removing durable surfaces;
- changing relationships;
- remapping local paths;
- retiring machines.

Agents may propose these automatically but should not silently apply them unless an explicit trusted policy authorizes the operation.

### High-risk external/destructive

Examples:

- deleting directories;
- deleting repositories;
- deleting cloud projects;
- overwriting data;
- moving large directory trees;
- mutating credentials or secret stores.

These are not ordinary governance maintenance and require specific explicit authorization and specialized verification.

## Change Sets

A Change Set groups multiple semantic operations that belong to one user intention.

Example:

```text
Change Set: graduate example tool

1. RETYPE tool -> repo
2. PROMOTE incubator -> active
3. ATTACH_SURFACE github/source
4. ATTACH_SURFACE local/exec
```

A Change Set should support dry-run output before mutation.

## Revision control

Mutable durable entities should carry a monotonically increasing `revision`.

A mutation should include the expected current revision. If the actual revision differs, the operation should fail closed with a stale-state conflict and require reacquisition/replanning.

This provides lightweight optimistic concurrency without requiring a distributed database lock.

## Event records

Durable structural Events should be immutable and should normally contain:

- `schema_version`;
- `event_id`;
- timestamp;
- operation;
- target kind and ID;
- actor type and ID;
- reason;
- before/after revision;
- explicit changed fields.

Event history should record structural governance changes, not ordinary task activity, chat creation, commits, file edits, or routine project work.

If an old Event is wrong, append a correction Event rather than silently rewriting history.

## No implicit cascade

No Relationship or parent-like structure may automatically archive, delete, move, or otherwise mutate related Workspace Objects.

Every durable mutation must target explicit entities through the Change Protocol.

## Intent versus reality

A plan to move, clone, split, or migrate a workspace remains intent until execution completes and reality is independently verified.

The registry should not claim a future Surface or path already exists merely because a migration was planned.
