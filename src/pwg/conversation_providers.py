"""Small optional Desktop adapter; the core depends only on ReadProvider.

The host supplies a current-session read callback (no credentials). Native responses
are projected immediately; summaries, paths, transcripts and tool output never reach
the checkpoint. Archive listing for Codex tasks is deliberately NOT used for ChatGPT.
"""
from __future__ import annotations

from typing import Callable

from .conversations import (Capabilities, ConversationError, Metadata, Page,
                            READ_CAPABILITIES, Scope, now)


class DesktopReadProvider:
    def __init__(self, read: Callable, available_tools: set[str], *, bound_scope: Scope):
        self._read = read
        self._tools = set(available_tools)
        self._scope = bound_scope
        self._snapshot = None

    def discover(self, session: str, scope: Scope) -> Capabilities:
        if scope != self._scope or "list_threads" not in self._tools:
            raise ConversationError("Desktop scope or read capability unavailable")
        self._snapshot = self._read("list_threads", {"limit": 50})
        data = self._snapshot
        if (not isinstance(data, dict) or data.get("schemaVersion") != 4
                or not isinstance(data.get("threads"), list)
                or not isinstance(data.get("pinnedThreads"), list)):
            raise ConversationError("unsupported Desktop list response")
        reads = dict.fromkeys(READ_CAPABILITIES, "UNOBSERVABLE")
        reads["conversation.list"] = "PARTIAL"
        reads["conversation.read_metadata"] = "PARTIAL"
        # Membership field may be null and pin projection may differ from ChatGPT UI.
        reads["conversation.observe_project_membership"] = "PARTIAL"
        reads["conversation.observe_pin"] = "PARTIAL"
        # read_thread persists tool output in the host transcript and cannot guarantee
        # a minimal ephemeral content contract; do not advertise it here.
        return Capabilities("desktop-native", session, scope, now(), reads)

    def list_page(self, scope: Scope, archive: bool, cursor: str | None) -> Page:
        if archive or cursor is not None or self._snapshot is None or scope != self._scope:
            raise ConversationError("Desktop enumeration boundary")
        data = self._snapshot
        items = []
        for key, pinned in (("pinnedThreads", True), ("threads", False)):
            for row in data[key]:
                if row.get("kind") != "chatgpt":
                    continue
                if scope.project is not None and row.get("projectId") != scope.project:
                    continue
                items.append(Metadata(row["id"], row["title"], row.get("projectId"),
                                      None, pinned))
        self._snapshot = None  # do not retain provider payloads after projection
        return Page(tuple(items), scope, exhausted=False)

    def minimal_context(self, conversation_id: str, max_chars: int) -> str:
        raise ConversationError("ephemeral minimal context unavailable on Desktop transport")
