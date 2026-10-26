"""Small optional Desktop adapter; the core depends only on ReadProvider.

The host supplies a current-session read callback (no credentials). Native responses
are projected immediately; summaries, paths, transcripts and tool output never reach
the checkpoint. Archive listing for Codex tasks is deliberately NOT used for ChatGPT.
"""
from __future__ import annotations

from typing import Callable

from .conversations import (Capabilities, ConversationError, Metadata, Page,
                            READ_CAPABILITIES, ReadProvider, Scope, bounded_text, now)


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


class EphemeralContextReadProvider:
    """Add an explicitly attested, bounded context reader to a read provider.

    The host must set ``ephemeral_context=True`` only when the callback reads the
    current session without writing source content to a transcript, log or
    checkpoint. The adapter validates the bounded call and result, retains neither,
    and never exposes a mutation callback. Without that attestation the capability
    is forced back to ``UNOBSERVABLE`` even if the wrapped provider overclaims it.
    """

    _MAX_CONTEXT_CHARS = 1_200

    def __init__(
        self,
        base: ReadProvider,
        read_context: Callable,
        *,
        bound_scope: Scope,
        ephemeral_context: bool,
        provider: str = "ephemeral-context",
    ):
        if not callable(read_context) or type(ephemeral_context) is not bool:
            raise ConversationError("invalid ephemeral context adapter")
        self._base = base
        self._read_context = read_context
        self._scope = bound_scope
        self._ephemeral = ephemeral_context
        self._provider = provider

    def discover(self, session: str, scope: Scope) -> Capabilities:
        if scope != self._scope:
            raise ConversationError("ephemeral context scope mismatch")
        try:
            base_cap = self._base.discover(session, scope)
        except Exception:
            raise ConversationError("wrapped read provider unavailable") from None
        if base_cap.session != session or base_cap.scope != scope:
            raise ConversationError("wrapped read provider scope mismatch")
        reads = dict(base_cap.reads)
        reads["conversation.read_minimal_context"] = (
            "OBSERVABLE" if self._ephemeral else "UNOBSERVABLE"
        )
        return Capabilities(self._provider, session, scope, base_cap.observed_at, reads)

    def list_page(self, scope: Scope, archive: bool, cursor: str | None) -> Page:
        if scope != self._scope:
            raise ConversationError("ephemeral context scope mismatch")
        return self._base.list_page(scope, archive, cursor)

    def minimal_context(self, conversation_id: str, max_chars: int) -> str:
        if not self._ephemeral:
            raise ConversationError("ephemeral minimal context is not attested")
        try:
            bounded_text(conversation_id, 200)
            if type(max_chars) is not int or not 1 <= max_chars <= self._MAX_CONTEXT_CHARS:
                raise ValueError()
            value = self._read_context(conversation_id, max_chars)
            return bounded_text(value, max_chars, empty=True)
        except Exception:
            # Do not let provider errors or source content cross the adapter boundary.
            raise ConversationError("invalid ephemeral minimal context") from None
