"""Synthetic Stage C0 tests; no real account identifiers or titles appear here."""
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from pwg.conversations import Scope, now
from pwg.conversation_state import ConversationError
from pwg.rename_c0 import (
    C0Store,
    MutationSurface,
    StaticMutationProbe,
    discover_rename_route,
    make_evidence,
    prepare_exact_batch,
    validate_evidence,
)


SCOPE = Scope("synthetic-account")


def synthetic_state(count=3):
    proposals = []
    for index in range(count):
        title = f"Topic {index}"
        proposals.append({
            "metadata": {"id": f"synthetic-{index}", "title": title, "project": None,
                         "archived": False, "pinned": None},
            "status": "RENAME_PROPOSED", "proposed_title": f"Topic {index} revised",
            "reason": "title_whitespace",
        })
    return {
        "schema_version": 1, "revision": 1, "semantic": "synthetic-reconciliation",
        "scope": asdict(SCOPE), "provider": "synthetic-provider", "inventory_generation": 4,
        "observed_at": now(), "proposal_revision": 7,
        "next_safe_action": "rediscover_then_refresh_read_only", "proposals": proposals,
        "summary": {"inventory_count": count,
                     "statuses": {"KEEP": 0, "RENAME_PROPOSED": count,
                                   "NEEDS_DECISION": 0, "SKIP": 0},
                     "termination": {"active": "exhausted", "archived": "exhausted"},
                     "pages": {"active": 1, "archived": 1}, "complete": True,
                     "duplicates": 0, "conflicts": 0, "context_reads": 0,
                     "chatgpt_write_requests": 0,
                     "observability": {"conversation.list": "OBSERVABLE",
                                        "conversation.read_metadata": "OBSERVABLE",
                                        "conversation.read_minimal_context": "UNOBSERVABLE",
                                        "conversation.observe_project_membership": "OBSERVABLE",
                                        "conversation.observe_archive": "OBSERVABLE",
                                        "conversation.observe_pin": "OBSERVABLE"}},
    }


def surface(status="FOUND", route="synthetic-ui"):
    states = {name: "OBSERVABLE" for name in (
        "conversation.rename", "conversation.read_metadata",
        "conversation.verify_title", "conversation.verify_non_target_fields_unchanged")}
    if status == "BLOCKED":
        states["conversation.rename"] = "UNOBSERVABLE"
        reason = "synthetic route lacks title-only mutation"
    else:
        reason = "synthetic route supports exact canary"
    return MutationSurface("synthetic", route, "synthetic-session", now(), states, status, reason)


class C0Tests(unittest.TestCase):
    def test_discovery_prefers_current_complete_route_and_does_not_mutate(self):
        blocked = StaticMutationProbe(surface("BLOCKED", "desktop-native"))
        found = StaticMutationProbe(surface("FOUND", "browser-ui"))
        discovery = discover_rename_route([blocked, found], "synthetic-session", SCOPE)
        self.assertEqual(discovery.status, "FOUND")
        self.assertEqual(discovery.selected.route, "browser-ui")
        self.assertEqual(len(discovery.candidates), 2)
        self.assertFalse(hasattr(found, "rename_title"))

    def test_discovery_fail_closed_on_expired_or_broken_provider(self):
        blocked = StaticMutationProbe(surface("BLOCKED"))
        old = datetime.fromtimestamp(0, timezone.utc).isoformat()
        with self.assertRaises(ConversationError):
            MutationSurface("synthetic", "old", "synthetic-session", old,
                            {name: "OBSERVABLE" for name in (
                                "conversation.rename", "conversation.read_metadata",
                                "conversation.verify_title", "conversation.verify_non_target_fields_unchanged")},
                            "FOUND", "old")
        class Broken:
            def discover_rename(self, session, scope):
                raise RuntimeError("credential-header-not-for-output")
        result = discover_rename_route([Broken(), blocked], "synthetic-session", SCOPE)
        self.assertEqual(result.status, "BLOCKED")
        self.assertNotIn("credential", result.reason)

    def test_exact_three_batch_binds_revisions_and_native_preconditions(self):
        state = synthetic_state()
        result = prepare_exact_batch(
            state, discover_rename_route([StaticMutationProbe(surface())], "synthetic-session", SCOPE),
            mission=state["semantic"], scope=SCOPE, execution_generation="generation-1",
        )
        self.assertEqual(result.status, "PREPARED")
        self.assertEqual(len(result.batch.items), 3)
        self.assertEqual(result.batch.proposal_revision, 7)
        self.assertEqual(result.batch.inventory_generation, 4)
        self.assertTrue(result.batch.fingerprint())
        self.assertEqual([item.conversation_id for item in result.batch.items],
                         ["synthetic-0", "synthetic-1", "synthetic-2"])

    def test_batch_requires_exactly_three_and_never_substitutes(self):
        route = discover_rename_route([StaticMutationProbe(surface())], "synthetic-session", SCOPE)
        for count in (0, 2, 4):
            result = prepare_exact_batch(synthetic_state(count), route,
                                         mission="synthetic-reconciliation", scope=SCOPE)
            self.assertEqual(result.status, "BLOCKED")
            self.assertIsNone(result.batch)
            self.assertEqual(result.requested_size, 3)
        blocked = discover_rename_route([StaticMutationProbe(surface("BLOCKED"))], "synthetic-session", SCOPE)
        result = prepare_exact_batch(synthetic_state(), blocked,
                                     mission="synthetic-reconciliation", scope=SCOPE)
        self.assertEqual((result.status, result.eligible_count), ("BLOCKED", 3))

    def test_c0_evidence_is_aggregate_only_and_requires_zero_writes(self):
        state = synthetic_state(2)
        discovery = discover_rename_route([StaticMutationProbe(surface("BLOCKED"))], "synthetic-session", SCOPE)
        preparation = prepare_exact_batch(state, discovery, mission=state["semantic"], scope=SCOPE)
        evidence = make_evidence(state, discovery, preparation)
        validate_evidence(evidence)
        serialized = str(evidence)
        self.assertNotIn("synthetic-0", serialized)
        self.assertNotIn("Topic 0", serialized)
        self.assertFalse(evidence["c1_safe_to_authorize"])
        with self.assertRaises(ConversationError):
            make_evidence(state, discovery, preparation, chatgpt_write_requests=1)

    def test_historical_evidence_remains_readable_after_capability_expiry(self):
        state = synthetic_state(2)
        discovery = discover_rename_route([StaticMutationProbe(surface("BLOCKED"))], "synthetic-session", SCOPE)
        evidence = make_evidence(state, discovery,
                                 prepare_exact_batch(state, discovery, mission=state["semantic"], scope=SCOPE))
        evidence["observed_at"] = "2000-01-01T00:00:00+00:00"
        validate_evidence(evidence)

    def test_local_store_rejects_repo_and_registry_roots_and_writes_batch_atomically(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "c0"
            state = synthetic_state()
            discovery = discover_rename_route([StaticMutationProbe(surface())], "synthetic-session", SCOPE)
            prep = prepare_exact_batch(state, discovery, mission=state["semantic"], scope=SCOPE,
                                       execution_generation="generation-1")
            evidence = make_evidence(state, discovery, prep)
            evidence_path, batch_path = C0Store(home, forbidden_roots=(Path(temporary) / "registry",)).write(evidence, prep.batch)
            self.assertTrue(evidence_path.exists())
            self.assertTrue(batch_path.exists())
            stored = batch_path.read_text(encoding="utf-8")
            self.assertIn("generation-1", stored)
            self.assertIn("synthetic-0", stored)
            repo = Path(temporary) / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            with self.assertRaises(ConversationError):
                C0Store(repo / "state")
            with self.assertRaises(ConversationError):
                C0Store(Path(temporary) / "registry" / "state", forbidden_roots=(Path(temporary) / "registry",))

    def test_batch_rejects_structural_or_ambiguous_proposals(self):
        state = synthetic_state()
        state["proposals"][0]["reason"] = "structural_title"
        result = prepare_exact_batch(state,
                                     discover_rename_route([StaticMutationProbe(surface())], "synthetic-session", SCOPE),
                                     mission=state["semantic"], scope=SCOPE)
        self.assertEqual((result.status, result.eligible_count), ("BLOCKED", 2))


if __name__ == "__main__":
    unittest.main()
