"""Metadata-only stdin bridge for a live tool host; no network, credentials or writes.

The host must invoke list_threads in the CURRENT session, project only the permitted
ChatGPT metadata fields, and pipe the envelope immediately. A saved inventory is not
a runtime provider. This bridge rejects stale envelopes and raw response fields.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

from .conversation_providers import DesktopReadProvider
from .conversation_state import MissionStore, _keys
from .conversations import ConversationError, Scope, bounded_text, inventory, route


def observe_desktop(home: Path, semantic: str, scope: Scope, stream=None) -> dict:
    stream = stream or sys.stdin
    try:
        text = stream.read(1_000_001)
        if len(text) > 1_000_000:
            raise ValueError()
        envelope = json.loads(text)
        _keys(envelope, "session observed_at scope snapshot")
        bounded_text(envelope["session"], 100)
        _keys(envelope["scope"], "account project")
        if envelope["scope"] != {"account": scope.account, "project": scope.project}:
            raise ValueError()
        stamp = datetime.fromisoformat(envelope["observed_at"])
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
        if not 0 <= age <= 300:
            raise ValueError()
        snapshot = envelope["snapshot"]
        _keys(snapshot, "schemaVersion pinnedThreads threads")
        if snapshot["schemaVersion"] != 4:
            raise ValueError()
        for key in ("pinnedThreads", "threads"):
            if not isinstance(snapshot[key], list) or len(snapshot[key]) > 500:
                raise ValueError()
            for row in snapshot[key]:
                _keys(row, "kind id title projectId")
                if row["kind"] != "chatgpt":
                    raise ValueError()
    except Exception:
        raise ConversationError("invalid or stale metadata-only host envelope") from None
    used = False

    def read(name, arguments):
        nonlocal used
        if name != "list_threads" or arguments != {"limit": 50} or used:
            raise ConversationError("host read boundary")
        used = True
        return snapshot

    provider = DesktopReadProvider(read, {"list_threads"}, bound_scope=scope)
    selected, cap = route([provider], envelope["session"], scope)
    result = inventory(selected, cap, session=envelope["session"])
    if result.termination["active"] == "provider_error":
        raise ConversationError("invalid Desktop metadata observation")
    store = MissionStore(home)
    status, previous = store.recover(semantic, envelope["scope"])
    if status == "ambiguous":
        raise ConversationError("ambiguous semantic mission")
    state = store.checkpoint(semantic, result, expected_revision=previous["revision"] if previous else 0)
    return {"recovery": status, "revision": state["revision"],
            "inventory_generation": state["inventory_generation"],
            "next_safe_action": state["next_safe_action"], **state["summary"]}
