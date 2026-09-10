"""Phase 2.3C Stage C0: discover a rename surface and prepare, never apply, a batch.

This module intentionally has no mutation callback. It records capability facts and
binds an exact batch locally so a later Parent-authorized C1 executor can reacquire
and fence it. C0 itself has zero ChatGPT write requests.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Protocol
import uuid

from .conversation_state import validate as validate_reconciliation_state
from .conversations import ConversationError, Scope, bounded_text


RENAME_CAPABILITIES = (
    "conversation.rename",
    "conversation.read_metadata",
    "conversation.verify_title",
    "conversation.verify_non_target_fields_unchanged",
)
CAPABILITY_STATES = {"OBSERVABLE", "PARTIAL", "UNOBSERVABLE", "UNAVAILABLE"}
ROUTE_STATUSES = {"FOUND", "BLOCKED"}
HIGH_CONFIDENCE_REASONS = {"title_whitespace", "context_rule"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp(value: str) -> None:
    stamp = _historical_timestamp(value)
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    if not 0 <= age <= 300:
        raise ConversationError("expired C0 capability observation")


def _historical_timestamp(value: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ConversationError("invalid C0 observation timestamp") from None
    if stamp.tzinfo is None:
        raise ConversationError("C0 timestamp must include timezone")
    return stamp


def _keys(value: object, expected: str) -> None:
    if not isinstance(value, dict) or set(value) != set(expected.split()):
        raise ConversationError("C0 schema rejected")


@dataclass(frozen=True)
class MutationSurface:
    provider: str
    route: str
    session: str
    observed_at: str
    capabilities: dict[str, str]
    status: str
    reason: str

    def __post_init__(self) -> None:
        bounded_text(self.provider, 100)
        bounded_text(self.route, 120)
        bounded_text(self.session, 120)
        bounded_text(self.reason, 500)
        _timestamp(self.observed_at)
        if self.status not in ROUTE_STATUSES:
            raise ConversationError("invalid C0 route status")
        if set(self.capabilities) != set(RENAME_CAPABILITIES):
            raise ConversationError("incomplete C0 capability observation")
        if not set(self.capabilities.values()) <= CAPABILITY_STATES:
            raise ConversationError("invalid C0 capability state")
        required = all(self.capabilities[name] == "OBSERVABLE" for name in RENAME_CAPABILITIES)
        if (self.status == "FOUND") != required:
            raise ConversationError("C0 status does not match capability facts")


class MutationProbe(Protocol):
    def discover_rename(self, session: str, scope: Scope) -> MutationSurface: ...


@dataclass(frozen=True)
class RouteDiscovery:
    status: str
    selected: MutationSurface | None
    candidates: tuple[MutationSurface, ...]
    reason: str

    def __post_init__(self) -> None:
        if self.status not in ROUTE_STATUSES:
            raise ConversationError("invalid C0 discovery result")
        bounded_text(self.reason, 500)
        if self.status == "FOUND" and self.selected is None:
            raise ConversationError("C0 found route without selection")
        if self.status == "BLOCKED" and self.selected is not None:
            raise ConversationError("C0 blocked route has selection")


def discover_rename_route(
    probes: list[MutationProbe], session: str, scope: Scope
) -> RouteDiscovery:
    """Run only provider discovery callbacks; never call a rename transport."""
    candidates: list[MutationSurface] = []
    for probe in probes:
        try:
            surface = probe.discover_rename(session, scope)
            if not isinstance(surface, MutationSurface) or surface.session != session:
                continue
            candidates.append(surface)
        except Exception:
            # Provider exceptions may carry headers/content; keep them out of evidence.
            continue
    for surface in candidates:
        if surface.status == "FOUND":
            return RouteDiscovery("FOUND", surface, tuple(candidates), "usable exact rename route")
    if not candidates:
        return RouteDiscovery("BLOCKED", None, (), "no current rename-capable provider")
    return RouteDiscovery(
        "BLOCKED", None, tuple(candidates),
        "current providers lack the complete exact rename/precondition/verification contract",
    )


class StaticMutationProbe:
    """A discovery-only probe used by adapters and tests; it has no write method."""

    def __init__(self, surface: MutationSurface):
        self.surface = surface

    def discover_rename(self, session: str, scope: Scope) -> MutationSurface:
        if self.surface.session != session:
            raise ConversationError("probe belongs to another runtime session")
        return self.surface


@dataclass(frozen=True)
class ExactRenameItem:
    conversation_id: str
    expected_old_title: str
    target_title: str

    def __post_init__(self) -> None:
        bounded_text(self.conversation_id, 220)
        bounded_text(self.expected_old_title, 300, empty=True)
        bounded_text(self.target_title, 300)
        if self.expected_old_title == self.target_title:
            raise ConversationError("C0 batch contains a no-op title")
        if len(self.target_title) < 4:
            raise ConversationError("C0 target title is too short")
        if self.target_title.startswith(("/", "\\")):
            raise ConversationError("C0 target title cannot be a path")


@dataclass(frozen=True)
class ExactRenameBatch:
    mission: str
    scope: Scope
    proposal_revision: int
    inventory_generation: int
    provider: str
    route: str
    execution_generation: str
    items: tuple[ExactRenameItem, ...]

    def __post_init__(self) -> None:
        bounded_text(self.mission, 200)
        for value in (self.proposal_revision, self.inventory_generation):
            if type(value) is not int or value < 1:
                raise ConversationError("invalid C0 batch revision")
        bounded_text(self.provider, 100)
        bounded_text(self.route, 120)
        bounded_text(self.execution_generation, 80)
        if len(self.items) != 3:
            raise ConversationError("C0 exact batch must contain exactly 3 items")
        ids = [item.conversation_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ConversationError("C0 exact batch has duplicate identity")

    def fingerprint(self) -> str:
        payload = {
            "mission": self.mission,
            "scope": asdict(self.scope),
            "proposal_revision": self.proposal_revision,
            "inventory_generation": self.inventory_generation,
            "provider": self.provider,
            "route": self.route,
            "execution_generation": self.execution_generation,
            "items": [asdict(item) for item in self.items],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _batch_to_dict(batch: ExactRenameBatch) -> dict:
    return {
        "schema_version": 1,
        "stage": "C0",
        "mission": batch.mission,
        "scope": asdict(batch.scope),
        "proposal_revision": batch.proposal_revision,
        "inventory_generation": batch.inventory_generation,
        "provider": batch.provider,
        "route": batch.route,
        "execution_generation": batch.execution_generation,
        "items": [asdict(item) for item in batch.items],
        "fingerprint": batch.fingerprint(),
    }


def _batch_from_dict(value: object) -> ExactRenameBatch:
    _keys(value, "schema_version stage mission scope proposal_revision inventory_generation "
          "provider route execution_generation items fingerprint")
    if value["schema_version"] != 1 or value["stage"] != "C0":
        raise ConversationError("unsupported C0 batch")
    _keys(value["scope"], "account project")
    scope = Scope(value["scope"]["account"], value["scope"]["project"])
    if not isinstance(value["items"], list) or len(value["items"]) != 3:
        raise ConversationError("C0 batch item count rejected")
    items = []
    for item in value["items"]:
        _keys(item, "conversation_id expected_old_title target_title")
        items.append(ExactRenameItem(**item))
    batch = ExactRenameBatch(
        value["mission"], scope, value["proposal_revision"], value["inventory_generation"],
        value["provider"], value["route"], value["execution_generation"], tuple(items),
    )
    if value["fingerprint"] != batch.fingerprint():
        raise ConversationError("C0 batch fingerprint mismatch")
    return batch


def _batch_binding(batch: ExactRenameBatch | None) -> dict | None:
    if batch is None:
        return None
    return {
        "fingerprint": batch.fingerprint(),
        "proposal_revision": batch.proposal_revision,
        "inventory_generation": batch.inventory_generation,
        "execution_generation": batch.execution_generation,
    }


@dataclass(frozen=True)
class BatchPreparation:
    requested_size: int
    eligible_count: int
    status: str
    batch: ExactRenameBatch | None
    reason: str

    def __post_init__(self) -> None:
        if self.requested_size != 3 or self.eligible_count < 0:
            raise ConversationError("invalid C0 batch preparation counts")
        if self.status not in {"PREPARED", "BLOCKED"}:
            raise ConversationError("invalid C0 batch preparation status")
        bounded_text(self.reason, 500)
        if self.status == "PREPARED" and self.batch is None:
            raise ConversationError("prepared C0 batch is missing")
        if self.status == "BLOCKED" and self.batch is not None:
            raise ConversationError("blocked C0 batch must not carry mutable targets")


def prepare_exact_batch(
    reconciliation_state: dict,
    discovery: RouteDiscovery,
    *,
    mission: str,
    scope: Scope,
    execution_generation: str | None = None,
    selected_ids: list[str] | tuple[str, ...] | None = None,
) -> BatchPreparation:
    """Bind an explicit exact-three selection, or fail closed without guessing."""
    validate_reconciliation_state(reconciliation_state)
    if reconciliation_state["semantic"] != mission:
        raise ConversationError("C0 mission does not match reconciliation checkpoint")
    if reconciliation_state["scope"] != asdict(scope):
        raise ConversationError("C0 scope does not match reconciliation checkpoint")
    eligible = []
    for proposal in reconciliation_state["proposals"]:
        if proposal["status"] not in {"RENAME_PROPOSED"}:
            continue
        if proposal["reason"] not in HIGH_CONFIDENCE_REASONS or not proposal["proposed_title"]:
            continue
        metadata = proposal["metadata"]
        eligible.append(ExactRenameItem(metadata["id"], metadata["title"], proposal["proposed_title"]))
    eligible_by_id = {item.conversation_id: item for item in eligible}
    if selected_ids is None:
        if len(eligible) != 3:
            reason = (
                "C0 has fewer than three eligible proposals; no substitution"
                if len(eligible) < 3 else
                "C0 has more than three eligible proposals; explicit three-ID selection is required"
            )
            return BatchPreparation(3, len(eligible), "BLOCKED", None, reason)
        selected = eligible
    else:
        valid_shape = isinstance(selected_ids, (list, tuple)) and len(selected_ids) == 3
        valid_values = valid_shape and all(
            isinstance(value, str) and bool(value) for value in selected_ids
        )
        if (not valid_shape or not valid_values
                or len(set(selected_ids)) != 3
                or any(value not in eligible_by_id for value in selected_ids)):
            return BatchPreparation(3, len(eligible), "BLOCKED", None,
                                    "C0 explicit selection must contain exactly three eligible identities")
        selected = [eligible_by_id[value] for value in selected_ids]
    if discovery.status != "FOUND" or discovery.selected is None:
        return BatchPreparation(3, len(eligible), "BLOCKED", None,
                                "C0 has a bounded selection but no usable current exact rename route")
    generation = execution_generation or str(uuid.uuid4())
    batch = ExactRenameBatch(
        mission, scope, reconciliation_state["proposal_revision"],
        reconciliation_state["inventory_generation"], discovery.selected.provider,
        discovery.selected.route, generation, tuple(sorted(selected, key=lambda item: item.conversation_id)),
    )
    return BatchPreparation(3, len(eligible), "PREPARED", batch, "exact high-confidence batch bound locally")


def make_evidence(
    reconciliation_state: dict,
    discovery: RouteDiscovery,
    preparation: BatchPreparation,
    *,
    chatgpt_write_requests: int = 0,
    privacy_check: str = "PASS",
) -> dict:
    """Aggregate-only C0 evidence; IDs/titles are intentionally absent."""
    if chatgpt_write_requests != 0 or privacy_check != "PASS":
        raise ConversationError("C0 evidence invariant failed")
    selected = discovery.selected
    # When every route is blocked, retain the preferred route's observed facts
    # without presenting it as a usable selection. This distinguishes a missing
    # native rename operation from a total lack of runtime discovery.
    observed = selected or (discovery.candidates[0] if discovery.candidates else None)
    return {
        "schema_version": 1,
        "stage": "C0",
        "mission": reconciliation_state["semantic"],
        "scope": {"account": reconciliation_state["scope"]["account"],
                  "project": reconciliation_state["scope"]["project"]},
        "proposal_revision": reconciliation_state["proposal_revision"],
        "inventory_generation": reconciliation_state["inventory_generation"],
        "mutation_surface": discovery.status,
        "route_provider": observed.provider if observed else None,
        "route": observed.route if observed else None,
        "capabilities": observed.capabilities if observed else {
            name: "UNAVAILABLE" for name in RENAME_CAPABILITIES
        },
        "route_candidates": len(discovery.candidates),
        "batch_requested": 3,
        "batch_eligible": preparation.eligible_count,
        "batch_prepared": 3 if preparation.batch else 0,
        "batch_binding": _batch_binding(preparation.batch),
        "confidence_class": "HIGH_CONFIDENCE_ONLY",
        "privacy_check": privacy_check,
        "chatgpt_write_requests": chatgpt_write_requests,
        "c1_safe_to_authorize": bool(
            preparation.batch and discovery.status == "FOUND" and chatgpt_write_requests == 0
        ),
        "blocker": None if preparation.batch else preparation.reason,
        "observed_at": _now(),
    }


def validate_evidence(evidence: dict) -> None:
    _keys(evidence, "schema_version stage mission scope proposal_revision inventory_generation "
          "mutation_surface route_provider route capabilities route_candidates batch_requested "
          "batch_eligible batch_prepared batch_binding confidence_class privacy_check "
          "chatgpt_write_requests c1_safe_to_authorize blocker observed_at")
    if evidence["schema_version"] != 1 or evidence["stage"] != "C0":
        raise ConversationError("unsupported C0 evidence")
    bounded_text(evidence["mission"], 200)
    _keys(evidence["scope"], "account project")
    bounded_text(evidence["scope"]["account"], 200)
    if evidence["scope"]["project"] is not None:
        bounded_text(evidence["scope"]["project"], 200)
    for key in ("proposal_revision", "inventory_generation", "route_candidates", "batch_requested",
                "batch_eligible", "batch_prepared", "chatgpt_write_requests"):
        if type(evidence[key]) is not int or evidence[key] < 0:
            raise ConversationError("invalid C0 evidence count")
    if evidence["batch_requested"] != 3 or evidence["batch_prepared"] not in {0, 3}:
        raise ConversationError("invalid C0 batch size")
    if evidence["batch_eligible"] < evidence["batch_prepared"]:
        raise ConversationError("C0 candidate count invariant failed")
    if evidence["batch_prepared"] == 0:
        if evidence["batch_binding"] is not None:
            raise ConversationError("blocked C0 evidence cannot reference a batch")
    else:
        _keys(evidence["batch_binding"],
              "fingerprint proposal_revision inventory_generation execution_generation")
        bounded_text(evidence["batch_binding"]["fingerprint"], 64)
        if (len(evidence["batch_binding"]["fingerprint"]) != 64
                or any(char not in "0123456789abcdef" for char in evidence["batch_binding"]["fingerprint"])):
            raise ConversationError("invalid C0 batch fingerprint")
        for key in ("proposal_revision", "inventory_generation"):
            if (type(evidence["batch_binding"][key]) is not int
                    or evidence["batch_binding"][key] < 1):
                raise ConversationError("invalid C0 batch binding revision")
        bounded_text(evidence["batch_binding"]["execution_generation"], 80)
        if evidence["batch_binding"]["proposal_revision"] != evidence["proposal_revision"]:
            raise ConversationError("C0 batch proposal revision mismatch")
        if evidence["batch_binding"]["inventory_generation"] != evidence["inventory_generation"]:
            raise ConversationError("C0 batch inventory generation mismatch")
    if evidence["mutation_surface"] not in ROUTE_STATUSES:
        raise ConversationError("invalid C0 mutation surface")
    if set(evidence["capabilities"]) != set(RENAME_CAPABILITIES):
        raise ConversationError("invalid C0 capability evidence")
    if not set(evidence["capabilities"].values()) <= CAPABILITY_STATES:
        raise ConversationError("invalid C0 capability evidence state")
    if evidence["privacy_check"] != "PASS" or evidence["chatgpt_write_requests"] != 0:
        raise ConversationError("C0 privacy/write invariant failed")
    if type(evidence["c1_safe_to_authorize"]) is not bool:
        raise ConversationError("invalid C0 authorization state")
    # Historical evidence remains independently readable; capability freshness is
    # enforced on MutationSurface discovery, immediately before any future C1 gate.
    _historical_timestamp(evidence["observed_at"])
    if evidence["c1_safe_to_authorize"] != (
        evidence["batch_prepared"] == 3 and evidence["mutation_surface"] == "FOUND"
        and evidence["batch_binding"] is not None
    ):
        raise ConversationError("C0 authorization state inconsistent")


class C0Store:
    """Machine-local evidence/batch store with one actionable authorization unit.

    A prepared batch is written before its evidence. Recovery only treats it as
    actionable when the evidence binding exactly matches the batch fingerprint,
    revisions, and execution generation. A blocked write removes any prior batch
    before publishing blocked evidence.
    """

    def __init__(self, home: str | Path, *, forbidden_roots: tuple[str | Path, ...] = ()):
        self.home = Path(home).expanduser().resolve()
        for ancestor in (self.home, *self.home.parents):
            if (ancestor / ".git").exists():
                raise ConversationError("C0 state must be outside Git repositories")
        for root in forbidden_roots:
            if self.home.is_relative_to(Path(root).expanduser().resolve()):
                raise ConversationError("C0 state cannot use Registry/repository storage")

    def write(self, evidence: dict, batch: ExactRenameBatch | None = None) -> tuple[Path, Path | None]:
        validate_evidence(evidence)
        if (batch is None) != (evidence["batch_prepared"] == 0):
            raise ConversationError("C0 evidence and batch disagree")
        if batch is not None:
            if not evidence["c1_safe_to_authorize"]:
                raise ConversationError("cannot store an unsafe prepared batch")
            if (batch.mission != evidence["mission"]
                    or batch.proposal_revision != evidence["proposal_revision"]
                    or batch.inventory_generation != evidence["inventory_generation"]
                    or evidence["batch_binding"] != _batch_binding(batch)):
                raise ConversationError("C0 batch binding mismatch")
        self.home.mkdir(parents=True, exist_ok=True)
        evidence_path, batch_path = self._paths(evidence["mission"])
        if batch is None:
            # A blocked run revokes local actionability before its aggregate evidence
            # is published. If the evidence write fails, recovery still sees no batch.
            batch_path.unlink(missing_ok=True)
            self._atomic(evidence_path, evidence)
            return evidence_path, None

        # Write the exact payload first. If evidence replacement fails, remove the
        # payload; an older evidence file can then only fail closed on recovery.
        self._atomic(batch_path, _batch_to_dict(batch))
        try:
            self._atomic(evidence_path, evidence)
        except Exception:
            batch_path.unlink(missing_ok=True)
            raise
        return evidence_path, batch_path

    def recover(self, mission: str) -> tuple[dict | None, ExactRenameBatch | None]:
        """Read history and return an actionable batch only on exact binding match."""
        evidence_path, batch_path = self._paths(mission)
        if not evidence_path.exists():
            return None, None
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            validate_evidence(evidence)
        except Exception:
            raise ConversationError("invalid C0 evidence; recovery fails closed") from None
        if evidence["batch_prepared"] == 0 or not evidence["c1_safe_to_authorize"]:
            return evidence, None
        if not batch_path.exists():
            return evidence, None
        try:
            batch = _batch_from_dict(json.loads(batch_path.read_text(encoding="utf-8")))
        except Exception:
            return evidence, None
        binding = evidence["batch_binding"]
        if (batch.mission != evidence["mission"]
                or batch.proposal_revision != evidence["proposal_revision"]
                or batch.inventory_generation != evidence["inventory_generation"]
                or binding != _batch_binding(batch)):
            return evidence, None
        return evidence, batch

    def _paths(self, mission: str) -> tuple[Path, Path]:
        bounded_text(mission, 200)
        stem = hashlib.sha256(mission.encode()).hexdigest()[:24]
        return (self.home / f"{stem}-c0-evidence.json",
                self.home / f"{stem}-c0-batch.json")

    @staticmethod
    def _atomic(path: Path, value: dict) -> None:
        text = json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=".c0-", suffix=".tmp", delete=False)
        temporary = Path(handle.name)
        try:
            with handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
