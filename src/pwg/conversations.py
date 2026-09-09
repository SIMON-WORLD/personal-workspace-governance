"""Phase 2.3A/B: provider-neutral, read-only conversation reconciliation.

Providers and policies are trusted executable code; their content is untrusted data.
No write transport or account mutation exists in this module.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Protocol


class ConversationError(ValueError):
    """Errors deliberately contain no provider payload or conversation identity."""


READ_CAPABILITIES = (
    "conversation.list", "conversation.read_metadata",
    "conversation.read_minimal_context", "conversation.observe_project_membership",
    "conversation.observe_archive", "conversation.observe_pin",
)
OBSERVABILITY = {"OBSERVABLE", "PARTIAL", "UNOBSERVABLE"}
STATUSES = {"KEEP", "RENAME_PROPOSED", "NEEDS_DECISION", "SKIP"}
REASONS = {"descriptive_title", "title_whitespace", "ambiguous_title",
           "duplicate_title", "structural_title", "metadata_conflict", "context_rule"}
TERMINATIONS = {"exhausted", "no_pagination", "unavailable", "page_limit",
                "cursor_cycle", "provider_error", "scope_mismatch"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bounded_text(value: object, limit: int, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (not empty and not value):
        raise ConversationError("invalid bounded metadata")
    if any(ord(c) < 32 for c in value):
        raise ConversationError("control character in metadata")
    return value


@dataclass(frozen=True)
class Scope:
    # Explicit account binding supplied by the runtime host, never inferred from a title.
    account: str
    project: str | None = None

    def __post_init__(self):
        bounded_text(self.account, 200)
        if self.project is not None:
            bounded_text(self.project, 200)


@dataclass(frozen=True)
class Metadata:
    id: str
    title: str
    project: str | None = None
    archived: bool | None = None
    pinned: bool | None = None

    def __post_init__(self):
        bounded_text(self.id, 200)
        bounded_text(self.title, 300, empty=True)
        if self.project is not None:
            bounded_text(self.project, 200)
        if any(v is not None and type(v) is not bool for v in (self.archived, self.pinned)):
            raise ConversationError("invalid observable flag")


@dataclass(frozen=True)
class Capabilities:
    provider: str
    session: str
    scope: Scope
    observed_at: str
    reads: dict[str, str]

    def __post_init__(self):
        bounded_text(self.provider, 100)
        bounded_text(self.session, 100)
        try:
            stamp = datetime.fromisoformat(self.observed_at)
            if stamp.tzinfo is None:
                raise ValueError()
        except (ValueError, TypeError):
            raise ConversationError("invalid observation timestamp") from None
        if set(self.reads) != set(READ_CAPABILITIES) or not set(self.reads.values()) <= OBSERVABILITY:
            raise ConversationError("invalid capability declaration")


@dataclass(frozen=True)
class Page:
    items: tuple[Metadata, ...]
    scope: Scope
    next_cursor: str | None = None
    # Exhaustion is an explicit provider observation, never inferred from a short page.
    exhausted: bool = False


class ReadProvider(Protocol):
    def discover(self, session: str, scope: Scope) -> Capabilities: ...
    def list_page(self, scope: Scope, archive: bool, cursor: str | None) -> Page: ...
    def minimal_context(self, conversation_id: str, max_chars: int) -> str: ...


def route(providers: list[ReadProvider], session: str, scope: Scope) -> tuple[ReadProvider, Capabilities]:
    """Discover each current candidate; deterministic preference for more observable reads."""
    candidates = []
    for index, provider in enumerate(providers):
        try:
            cap = provider.discover(session, scope)
            if cap.session != session or cap.scope != scope:
                continue
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(cap.observed_at)).total_seconds()
            if not 0 <= age <= 300:
                continue
            if any(cap.reads[k] == "UNOBSERVABLE" for k in READ_CAPABILITIES[:2]):
                continue
            score = sum({"UNOBSERVABLE": 0, "PARTIAL": 1, "OBSERVABLE": 2}[v]
                        for v in cap.reads.values())
            candidates.append((-score, index, provider, cap))
        except Exception:
            # Never log provider exceptions: they may contain content or credentials.
            continue
    if not candidates:
        raise ConversationError("no current read provider for scope")
    _, _, provider, cap = min(candidates, key=lambda c: c[:2])
    return provider, cap


@dataclass(frozen=True)
class Proposal:
    metadata: Metadata
    status: str
    proposed_title: str | None
    reason: str


class TitlePolicy:
    """Conservative deterministic policy. No authority is inferred from structural titles.

    Optional context rules map keyword tuples to fixed, policy-authored titles. Raw
    context is never copied into a proposal; zero/multiple matching rules abstain.
    """
    generic = {"new chat", "untitled", "hello", "test", "候选", "继续", "新对话", "你好"}

    def __init__(self, context_rules: tuple[tuple[tuple[str, ...], str], ...] = ()):
        for keywords, title in context_rules:
            bounded_text(title, 120)
            if not keywords or re.match(r"^\d{2}\s*[·|]", title):
                raise ConversationError("invalid context title policy")
        self.context_rules = context_rules

    def propose(self, item: Metadata, duplicate: bool, context: str | None = None) -> Proposal:
        title = " ".join(item.title.split())
        if re.match(r"^(?:\d{2}\s*[·|]|[①-⑳])", title):
            return Proposal(item, "NEEDS_DECISION", None, "structural_title")
        ambiguous = duplicate or len(title) < 4 or title.casefold() in self.generic
        if ambiguous:
            if context and self.context_rules:
                matches = {target for words, target in self.context_rules
                           if all(word.casefold() in context.casefold() for word in words)}
                if len(matches) == 1:
                    return Proposal(item, "RENAME_PROPOSED", matches.pop(), "context_rule")
            return Proposal(item, "NEEDS_DECISION", None,
                            "duplicate_title" if duplicate else "ambiguous_title")
        if title != item.title:
            return Proposal(item, "RENAME_PROPOSED", title, "title_whitespace")
        return Proposal(item, "KEEP", None, "descriptive_title")


@dataclass
class Inventory:
    capabilities: Capabilities
    proposals: list[Proposal]
    termination: dict[str, str]
    pages: dict[str, int]
    duplicates: int
    conflicts: int
    context_reads: int

    def summary(self) -> dict:
        return {"inventory_count": len(self.proposals),
                "statuses": {s: sum(p.status == s for p in self.proposals) for s in sorted(STATUSES)},
                "termination": self.termination, "pages": self.pages,
                "complete": all(v == "exhausted" for v in self.termination.values()) and not self.conflicts,
                "duplicates": self.duplicates, "conflicts": self.conflicts,
                "context_reads": self.context_reads, "chatgpt_write_requests": 0,
                "observability": dict(self.capabilities.reads)}


def inventory(provider: ReadProvider, cap: Capabilities, *, session: str,
              policy: TitlePolicy | None = None, max_pages: int = 20,
              max_items: int = 2000, context_budget: int = 0) -> Inventory:
    if session != cap.session:
        raise ConversationError("rediscover capabilities after session boundary")
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(cap.observed_at)).total_seconds()
    if not 0 <= age <= 300:
        raise ConversationError("rediscover expired capability observations")
    if not 1 <= max_pages <= 100 or not 1 <= max_items <= 10000 or not 0 <= context_budget <= 20:
        raise ConversationError("invalid inventory budget")
    policy = policy or TitlePolicy()
    items: dict[str, Metadata] = {}
    conflicts: set[str] = set()
    duplicates = 0
    termination, pages = {}, {}
    for archive, partition in ((False, "active"), (True, "archived")):
        pages[partition] = 0
        if archive and cap.reads["conversation.observe_archive"] == "UNOBSERVABLE":
            termination[partition] = "unavailable"
            continue
        cursor, seen = None, set()
        termination[partition] = "page_limit"
        for _ in range(max_pages):
            try:
                page = provider.list_page(cap.scope, archive, cursor)
                if not isinstance(page, Page) or any(not isinstance(i, Metadata) for i in page.items):
                    raise ConversationError("invalid provider page")
                if page.scope != cap.scope:
                    termination[partition] = "scope_mismatch"
                    break
                if page.exhausted and page.next_cursor is not None:
                    raise ConversationError("contradictory provider termination")
                if page.next_cursor is not None:
                    bounded_text(page.next_cursor, 500)
                if len(page.items) > max_items or len(set(items) | {i.id for i in page.items}) > max_items:
                    termination[partition] = "page_limit"
                    break
                if cap.scope.project is not None and any(i.project != cap.scope.project for i in page.items):
                    termination[partition] = "scope_mismatch"
                    break
                pages[partition] += 1
                for item in page.items:
                    if item.archived is not None and item.archived != archive:
                        conflicts.add(item.id)
                    if item.id in items:
                        duplicates += 1
                        if item != items[item.id]:
                            conflicts.add(item.id)
                    else:
                        items[item.id] = item
                if page.exhausted:
                    termination[partition] = "exhausted"
                    break
                if page.next_cursor is None:
                    termination[partition] = "no_pagination"
                    break
                if page.next_cursor in seen:
                    termination[partition] = "cursor_cycle"
                    break
                seen.add(page.next_cursor)
                cursor = page.next_cursor
            except Exception:
                termination[partition] = "provider_error"
                break
    counts = Counter(" ".join(i.title.split()).casefold() for i in items.values())
    proposals, reads = [], 0
    for item in sorted(items.values(), key=lambda i: i.id):
        if item.id in conflicts:
            proposals.append(Proposal(item, "SKIP", None, "metadata_conflict"))
            continue
        duplicate = counts[" ".join(item.title.split()).casefold()] > 1
        proposal = policy.propose(item, duplicate)
        if (proposal.reason in {"ambiguous_title", "duplicate_title"} and policy.context_rules
                and reads < context_budget and cap.reads[READ_CAPABILITIES[2]] != "UNOBSERVABLE"):
            reads += 1
            try:
                context = provider.minimal_context(item.id, 1200)
                if isinstance(context, str) and len(context) <= 1200:
                    proposal = policy.propose(item, duplicate, context)
                context = None
            except Exception:
                pass
        proposals.append(proposal)
    # Even fixed context labels must not manufacture a new collision.
    targets = Counter((p.proposed_title or " ".join(p.metadata.title.split())).casefold() for p in proposals)
    proposals = [Proposal(p.metadata, "NEEDS_DECISION", None, "duplicate_title")
                 if p.proposed_title and targets[p.proposed_title.casefold()] > 1 else p for p in proposals]
    return Inventory(cap, proposals, termination, pages, duplicates, len(conflicts), reads)


@dataclass(frozen=True)
class RenameBoundary:
    """Future exact-batch binding only; Phase 2.3A/B never executes it."""
    mission: str
    proposal_revision: int
    batch: str
    expected: tuple[tuple[str, str, str], ...]  # native ID, old title, target title

    def apply(self) -> None:
        raise ConversationError("Phase 2.3A/B is read-only; Parent review required")
