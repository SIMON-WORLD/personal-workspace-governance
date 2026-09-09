"""Strict, atomic, machine-local checkpoints. Never serialize provider responses."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .conversations import (ConversationError, Inventory, Metadata, READ_CAPABILITIES,
                            OBSERVABILITY, REASONS, STATUSES, TERMINATIONS, bounded_text)


def _keys(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ConversationError("checkpoint schema rejected")


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ConversationError("checkpoint integer rejected")


def validate(state: dict) -> None:
    """Allowlist every object recursively; unknown fields (including payloads) fail closed."""
    _keys(state, "schema_version revision semantic scope provider inventory_generation observed_at "
          "proposal_revision next_safe_action proposals summary")
    if type(state["schema_version"]) is not int or state["schema_version"] != 1:
        raise ConversationError("unsupported checkpoint schema")
    for key in ("revision", "inventory_generation", "proposal_revision"):
        _integer(state[key], 1)
    bounded_text(state["semantic"], 200)
    bounded_text(state["provider"], 100)
    bounded_text(state["observed_at"], 100)
    _keys(state["scope"], "account project")
    bounded_text(state["scope"]["account"], 200)
    if state["scope"]["project"] is not None:
        bounded_text(state["scope"]["project"], 200)
    if state["next_safe_action"] != "rediscover_then_refresh_read_only":
        raise ConversationError("unsafe checkpoint continuation")
    if not isinstance(state["proposals"], list) or len(state["proposals"]) > 10000:
        raise ConversationError("checkpoint inventory bound rejected")
    ids = set()
    for p in state["proposals"]:
        _keys(p, "metadata status proposed_title reason")
        _keys(p["metadata"], "id title project archived pinned")
        m = Metadata(**p["metadata"])
        if m.id in ids:
            raise ConversationError("duplicate checkpoint identity")
        ids.add(m.id)
        if p["status"] not in STATUSES or p["reason"] not in REASONS:
            raise ConversationError("checkpoint proposal rejected")
        if p["status"] == "RENAME_PROPOSED":
            bounded_text(p["proposed_title"], 300)
            if p["proposed_title"] == m.title:
                raise ConversationError("no-op proposal rejected")
        elif p["proposed_title"] is not None:
            raise ConversationError("unexpected proposal title")
    summary = state["summary"]
    _keys(summary, "inventory_count statuses termination pages complete duplicates conflicts "
          "context_reads chatgpt_write_requests observability")
    for key in ("inventory_count", "duplicates", "conflicts", "context_reads", "chatgpt_write_requests"):
        _integer(summary[key])
    if summary["chatgpt_write_requests"] != 0 or summary["inventory_count"] != len(ids):
        raise ConversationError("checkpoint count invariant rejected")
    _keys(summary["statuses"], " ".join(STATUSES))
    for status, count in summary["statuses"].items():
        _integer(count)
        if count != sum(p["status"] == status for p in state["proposals"]):
            raise ConversationError("checkpoint status count rejected")
    _keys(summary["termination"], "active archived")
    _keys(summary["pages"], "active archived")
    for value in summary["pages"].values():
        _integer(value)
    if not set(summary["termination"].values()) <= TERMINATIONS:
        raise ConversationError("checkpoint termination rejected")
    complete = all(v == "exhausted" for v in summary["termination"].values()) and not summary["conflicts"]
    if type(summary["complete"]) is not bool or summary["complete"] != complete:
        raise ConversationError("checkpoint completeness rejected")
    _keys(summary["observability"], " ".join(READ_CAPABILITIES))
    if not set(summary["observability"].values()) <= OBSERVABILITY:
        raise ConversationError("checkpoint observation rejected")


class MissionStore:
    def __init__(self, home: Path, *, forbidden_roots: tuple[Path, ...] = ()):
        self.home = Path(home).expanduser().resolve()
        for ancestor in (self.home, *self.home.parents):
            if (ancestor / ".git").exists():
                raise ConversationError("mission state must be outside Git repositories")
        for root in forbidden_roots:
            if self.home.is_relative_to(Path(root).expanduser().resolve()):
                raise ConversationError("mission state cannot use a Registry or evidence repository")

    def _read(self, path: Path) -> dict:
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(self.home):
                raise ConversationError("checkpoint link rejected")
            if path.stat().st_size > 4_000_000:
                raise ConversationError("checkpoint size limit")
            state = json.loads(path.read_text(encoding="utf-8"))
            validate(state)
            return state
        except Exception:
            raise ConversationError("invalid local checkpoint; recovery fails closed") from None

    def recover(self, semantic: str, scope: dict) -> tuple[str, dict | None]:
        bounded_text(semantic, 200)
        files = sorted(self.home.glob("*.json"))
        if len(files) > 100:
            raise ConversationError("semantic recovery scan bound exceeded")
        matches = []
        for path in files:
            state = self._read(path)
            if state["semantic"] == semantic and state["scope"] == scope:
                matches.append(state)
        if len(matches) > 1:
            return "ambiguous", None
        return ("recover", matches[0]) if matches else ("not_found", None)

    def checkpoint(self, semantic: str, result: Inventory, *, expected_revision: int = 0) -> dict:
        # Recheck location at write time as well as construction (e.g. a new .git marker).
        MissionStore(self.home)
        scope = asdict(result.capabilities.scope)
        status, previous = self.recover(semantic, scope)
        if status == "ambiguous":
            raise ConversationError("ambiguous semantic mission; fail closed")
        revision = previous["revision"] if previous else 0
        if revision != expected_revision:
            raise ConversationError("checkpoint revision changed; reacquire mission")
        if previous and previous["provider"] != result.capabilities.provider:
            # No cross-provider identity merge without an explicit identity equivalence contract.
            raise ConversationError("provider changed; explicit identity rebinding required")
        state = {"schema_version": 1, "revision": revision + 1, "semantic": semantic,
                 "scope": scope, "provider": result.capabilities.provider,
                 "inventory_generation": (previous["inventory_generation"] if previous else 0) + 1,
                 "observed_at": result.capabilities.observed_at,
                 "proposal_revision": (previous["proposal_revision"] if previous else 0) + 1,
                 "next_safe_action": "rediscover_then_refresh_read_only",
                 "proposals": [asdict(p) for p in result.proposals], "summary": result.summary()}
        validate(state)
        # Semantic identity, not latest timestamp or a user-relayed opaque run ID.
        digest = hashlib.sha256(json.dumps([semantic, scope], sort_keys=True).encode()).hexdigest()
        target = self.home / (digest + ".json")
        if previous:
            matching = [p for p in self.home.glob("*.json") if self._read(p) == previous]
            if len(matching) != 1:
                raise ConversationError("checkpoint changed during recovery")
            target = matching[0]
        self.home.mkdir(parents=True, exist_ok=True)
        data = json.dumps(state, ensure_ascii=True, indent=2) + "\n"
        if len(data.encode()) > 4_000_000:
            raise ConversationError("checkpoint size limit")
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.home,
                                             prefix=".checkpoint-", suffix=".tmp", delete=False)
        tmp = Path(handle.name)
        try:
            with handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
        return state
