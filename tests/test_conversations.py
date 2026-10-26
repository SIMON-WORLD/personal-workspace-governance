"""All conversations, account bindings and provider fixtures here are synthetic."""
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pwg.conversations import (Capabilities, ConversationError, Metadata, Page, Scope,
                               READ_CAPABILITIES, RenameBoundary, TitlePolicy, inventory, now, route)
from pwg.conversation_providers import DesktopReadProvider, DesktopRenameSurfaceProbe
from pwg.conversation_state import MissionStore, validate
from pwg.conversation_host import observe_desktop
from pwg.rename_c0 import RENAME_CAPABILITIES, discover_rename_route


SCOPE = Scope("synthetic-account")


class Provider:
    def __init__(self, pages=None, name="synthetic", observations=None):
        self.pages = pages or {
            (False, None): Page((Metadata("a", "Research garden growth", archived=False),), SCOPE, exhausted=True),
            (True, None): Page((), SCOPE, exhausted=True),
        }
        self.name = name
        self.observations = observations or dict.fromkeys(READ_CAPABILITIES, "OBSERVABLE")
        self.calls = []

    def discover(self, session, scope):
        self.calls.append("discover")
        return Capabilities(self.name, session, scope, now(), self.observations)

    def list_page(self, scope, archive, cursor):
        self.calls.append((archive, cursor))
        result = self.pages[(archive, cursor)]
        if isinstance(result, Exception):
            raise result
        return result

    def minimal_context(self, conversation_id, max_chars):
        self.calls.append("context")
        return "private snippet: garden seedlings"


def run(provider=None, **kwargs):
    provider = provider or Provider()
    p, cap = route([provider], "session-a", SCOPE)
    return inventory(p, cap, session="session-a", **kwargs)


def native_snapshot():
    return {"schemaVersion": 4, "threads": [
        {"kind": "chatgpt", "id": "a", "title": "Garden growth study", "projectId": None},
        {"kind": "chatgpt", "id": "b", "title": "New chat", "projectId": "synthetic-project"},
    ], "pinnedThreads": []}


class CapabilityTests(unittest.TestCase):
    def test_routing_uses_runtime_observations_and_fallback(self):
        weak = Provider(name="weak", observations=dict.fromkeys(READ_CAPABILITIES, "PARTIAL"))
        strong = Provider(name="strong")
        selected, _ = route([weak, strong], "new-session", SCOPE)
        self.assertIs(selected, strong)
        self.assertEqual(weak.calls, ["discover"])
        strong.observations = dict.fromkeys(READ_CAPABILITIES, "UNOBSERVABLE")
        self.assertIs(route([weak, strong], "next-session", SCOPE)[0], weak)
        with self.assertRaises(ConversationError):
            route([strong], "next-session", SCOPE)

    def test_failed_discovery_does_not_log_secret(self):
        class Broken(Provider):
            def discover(self, session, scope):
                raise RuntimeError("secret-payload")
        with self.assertRaisesRegex(ConversationError, "no current read") as caught:
            route([Broken()], "s", SCOPE)
        self.assertNotIn("secret", str(caught.exception))

    def test_stale_session_timestamp_and_scope_rejected(self):
        provider = Provider()
        cap = provider.discover("s", SCOPE)
        with self.assertRaises(ConversationError):
            inventory(provider, cap, session="replacement")
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with self.assertRaises(ConversationError):
            inventory(provider, replace(cap, observed_at=old), session="s")
        class WrongScope(Provider):
            def discover(self, session, scope):
                return super().discover(session, Scope("different-account"))
        with self.assertRaises(ConversationError):
            route([WrongScope()], "s", SCOPE)

    def test_native_scope_filter_kind_and_named_boundaries(self):
        snapshot = native_snapshot()
        snapshot["threads"].append({"kind": "codex", "id": "other", "title": "Do not govern"})
        calls = []
        def read(name, args):
            calls.append(name)
            return snapshot
        provider = DesktopReadProvider(read, {"list_threads", "read_thread", "list_archived_threads"}, bound_scope=SCOPE)
        result = run(provider)
        self.assertEqual(len(result.proposals), 2)
        self.assertEqual(result.termination, {"active": "no_pagination", "archived": "unavailable"})
        self.assertEqual(result.capabilities.reads[READ_CAPABILITIES[2]], "UNOBSERVABLE")
        self.assertIsNone(result.proposals[0].metadata.archived)
        self.assertEqual(calls, ["list_threads"])
        self.assertFalse(result.summary()["complete"])

    def test_unadvertised_or_schema_drift_native_fails_closed(self):
        for available, payload in [(set(), native_snapshot()), ({"list_threads"}, {"schemaVersion": 99})]:
            with self.assertRaises(ConversationError):
                run(DesktopReadProvider(lambda *_: payload, available, bound_scope=SCOPE))

    def test_desktop_rename_surface_probe_is_discovery_only_and_fail_closed(self):
        blocked = DesktopRenameSurfaceProbe(
            {"conversation.read_metadata": "PARTIAL"}, bound_scope=SCOPE
        )
        result = discover_rename_route([blocked], "session-a", SCOPE)
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.candidates[0].capabilities["conversation.rename"], "UNOBSERVABLE")
        self.assertFalse(hasattr(blocked, "rename"))

        found = DesktopRenameSurfaceProbe(
            dict.fromkeys(RENAME_CAPABILITIES, "OBSERVABLE"), bound_scope=SCOPE
        )
        result = discover_rename_route([found], "session-a", SCOPE)
        self.assertEqual((result.status, result.selected.route), ("FOUND", "codex-app-native"))
        self.assertFalse(hasattr(found, "rename"))

    def test_desktop_rename_surface_probe_rejects_scope_mismatch(self):
        probe = DesktopRenameSurfaceProbe({}, bound_scope=SCOPE)
        with self.assertRaises(ConversationError):
            probe.discover_rename("session-a", Scope("different-account"))


class InventoryTests(unittest.TestCase):
    def test_paginated_active_archived_dedup_and_termination(self):
        a = Metadata("a", "Garden design", archived=False)
        b = Metadata("b", "Soil study", archived=False)
        c = Metadata("c", "Archived rainfall study", archived=True)
        result = run(Provider({(False, None): Page((a,), SCOPE, "next"),
                               (False, "next"): Page((a, b), SCOPE, exhausted=True),
                               (True, None): Page((c,), SCOPE, exhausted=True)}))
        self.assertTrue(result.summary()["complete"])
        self.assertEqual(result.duplicates, 1)
        self.assertEqual(result.pages, {"active": 2, "archived": 1})
        self.assertEqual(len(result.proposals), 3)

    def test_empty_or_short_page_is_not_exhaustion(self):
        result = run(Provider({(False, None): Page((), SCOPE), (True, None): Page((), SCOPE)}))
        self.assertFalse(result.summary()["complete"])
        self.assertEqual(result.termination["active"], "no_pagination")

    def test_cursor_cycle_and_page_budget(self):
        provider = Provider({(False, None): Page((), SCOPE, "loop"),
                             (False, "loop"): Page((), SCOPE, "loop"),
                             (True, None): Page((), SCOPE, exhausted=True)})
        self.assertEqual(run(provider).termination["active"], "cursor_cycle")
        self.assertEqual(run(provider, max_pages=1).termination["active"], "page_limit")

    def test_scope_mismatch_exception_and_inconsistent_end(self):
        for page, expected in [(Page((), Scope("other"), exhausted=True), "scope_mismatch"),
                               (RuntimeError("credential-header"), "provider_error"),
                               (Page((), SCOPE, "next", True), "provider_error")]:
            result = run(Provider({(False, None): page, (True, None): Page((), SCOPE, exhausted=True)}))
            self.assertEqual(result.termination["active"], expected)
            self.assertFalse(result.summary()["complete"])
            self.assertNotIn("credential", json.dumps(result.summary()))

    def test_conflicting_identity_never_last_wins(self):
        result = run(Provider({(False, None): Page((Metadata("a", "First topic"), Metadata("a", "Other topic")), SCOPE, exhausted=True),
                               (True, None): Page((), SCOPE, exhausted=True)}))
        self.assertEqual(result.conflicts, 1)
        self.assertEqual(result.proposals[0].status, "SKIP")
        self.assertFalse(result.summary()["complete"])

    def test_wrong_archive_partition_is_conflict(self):
        result = run(Provider({(False, None): Page((Metadata("a", "First topic", archived=True),), SCOPE, exhausted=True),
                               (True, None): Page((), SCOPE, exhausted=True)}))
        self.assertEqual(result.proposals[0].status, "SKIP")

    def test_large_bounded_sample_and_stable_order(self):
        records = tuple(Metadata(str(i), f"Garden experiment {i}") for i in range(40))
        result = run(Provider({(False, None): Page(records[::-1], SCOPE, exhausted=True),
                               (True, None): Page((), SCOPE, exhausted=True)}))
        self.assertEqual(len(result.proposals), 40)
        self.assertEqual([p.metadata.id for p in result.proposals], sorted(r.id for r in records))
        self.assertEqual(result.summary()["chatgpt_write_requests"], 0)
        limited = run(Provider({(False, None): Page(records, SCOPE, exhausted=True),
                                (True, None): Page((), SCOPE, exhausted=True)}), max_items=10)
        self.assertFalse(limited.summary()["complete"])


class ProposalTests(unittest.TestCase):
    def test_conservative_titles_duplicates_structural_no_authority(self):
        policy = TitlePolicy()
        fixtures = [("New chat", False, "NEEDS_DECISION"), ("候选", False, "NEEDS_DECISION"),
                    ("00 · Brain · Garden", False, "NEEDS_DECISION"),
                    ("Rainfall analysis", True, "NEEDS_DECISION"),
                    ("Rainfall analysis", False, "KEEP"), ("  Rainfall   analysis ", False, "RENAME_PROPOSED")]
        for title, duplicate, expected in fixtures:
            self.assertEqual(policy.propose(Metadata("a", title), duplicate).status, expected)

    def test_context_ephemeral_derived_fixed_title_only(self):
        provider = Provider({(False, None): Page((Metadata("a", "New chat"),), SCOPE, exhausted=True),
                             (True, None): Page((), SCOPE, exhausted=True)})
        policy = TitlePolicy(((('garden', 'seedlings'), 'Garden seedling study'),))
        result = run(provider, policy=policy, context_budget=1)
        self.assertEqual(result.proposals[0].proposed_title, "Garden seedling study")
        self.assertEqual(result.context_reads, 1)
        self.assertNotIn("private snippet", json.dumps(asdict(result)))
        self.assertEqual(run(provider, policy=policy).context_reads, 0)

    def test_multiple_context_matches_abstain_and_no_write_skeleton(self):
        policy = TitlePolicy(((('garden',), 'Garden study'), (('seedlings',), 'Seedling study')))
        self.assertEqual(policy.propose(Metadata("a", "New chat"), False, "garden seedlings").status, "NEEDS_DECISION")
        with self.assertRaises(ConversationError):
            RenameBoundary("mission", 1, "batch", (("a", "old", "new"),)).apply()


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "missions"
        self.store = MissionStore(self.home)

    def checkpoint(self):
        return self.store.checkpoint("garden-title-reconciliation", run())

    def test_not_found_recover_ambiguous_and_revision(self):
        self.assertEqual(self.store.recover("garden-title-reconciliation", asdict(SCOPE))[0], "not_found")
        state = self.checkpoint()
        status, recovered = MissionStore(self.home).recover(state["semantic"], asdict(SCOPE))
        self.assertEqual((status, recovered), ("recover", state))
        with self.assertRaises(ConversationError):
            self.checkpoint()
        newer = self.store.checkpoint(state["semantic"], run(), expected_revision=1)
        self.assertEqual(newer["inventory_generation"], 2)
        (self.home / "duplicate.json").write_text(json.dumps(newer), encoding="utf-8")
        self.assertEqual(self.store.recover(state["semantic"], asdict(SCOPE)), ("ambiguous", None))
        with self.assertRaises(ConversationError):
            self.store.checkpoint(state["semantic"], run(), expected_revision=2)

    def test_schema_privacy_unknown_fields_at_every_layer(self):
        state = self.checkpoint()
        for location in ((), ("scope",), ("summary",), ("proposals", 0), ("proposals", 0, "metadata")):
            bad = copy.deepcopy(state)
            target = bad
            for key in location:
                target = target[key]
            target["body"] = "PRIVATE RAW CONTENT"
            with self.assertRaises(ConversationError):
                validate(bad)
        raw = " ".join(p.read_text() for p in self.home.glob("*.json"))
        for forbidden in ("PRIVATE RAW CONTENT", "snippet", "cookie", "session-a"):
            self.assertNotIn(forbidden, raw)

    def test_invalid_schema_counts_and_unsafe_action(self):
        state = self.checkpoint()
        for key, value in [("schema_version", 99), ("revision", True), ("next_safe_action", "rename")]:
            bad = copy.deepcopy(state)
            bad[key] = value
            with self.assertRaises(ConversationError):
                validate(bad)
        state["summary"]["chatgpt_write_requests"] = 1
        with self.assertRaises(ConversationError):
            validate(state)

    def test_corrupt_state_never_silently_ignored(self):
        self.home.mkdir()
        (self.home / "bad.json").write_text('{"body":"secret"}', encoding="utf-8")
        with self.assertRaisesRegex(ConversationError, "recovery fails closed"):
            self.store.recover("any", asdict(SCOPE))

    def test_failed_atomic_replace_preserves_previous_checkpoint(self):
        state = self.checkpoint()
        with patch("pwg.conversation_state.os.replace", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                self.store.checkpoint(state["semantic"], run(), expected_revision=1)
        self.assertEqual(self.store.recover(state["semantic"], asdict(SCOPE)), ("recover", state))
        self.assertEqual(len(list(self.home.iterdir())), 1)

    def test_rechecks_git_boundary_at_checkpoint_time(self):
        self.home.mkdir()
        (self.home / ".git").mkdir()
        with self.assertRaises(ConversationError):
            self.checkpoint()

    def test_reject_git_and_registry_roots_and_provider_rebind(self):
        root = Path(self.tmp.name) / "repo"
        root.mkdir()
        (root / ".git").write_text("gitdir: elsewhere")
        with self.assertRaises(ConversationError):
            MissionStore(root / "state")
        with self.assertRaises(ConversationError):
            MissionStore(self.home, forbidden_roots=(Path(self.tmp.name),))
        self.checkpoint()
        with self.assertRaisesRegex(ConversationError, "provider changed"):
            self.store.checkpoint("garden-title-reconciliation", run(Provider(name="new")), expected_revision=1)

    def test_process_replacement_semantic_cli_recovery(self):
        state = self.checkpoint()
        # A wholly separate interpreter receives semantic purpose/scope, no opaque run ID.
        code = "from pwg.conversation_state import MissionStore; from pathlib import Path; import sys,json; s,v=MissionStore(Path(sys.argv[1])).recover(sys.argv[2],{'account':'synthetic-account','project':None}); print(json.dumps({'status':s,'revision':v['revision'],'next':v['next_safe_action']}))"
        result = subprocess.run([sys.executable, "-c", code, str(self.home), state["semantic"]],
                                capture_output=True, text=True, check=True)
        value = json.loads(result.stdout)
        self.assertEqual(value, {"status": "recover", "revision": 1, "next": "rediscover_then_refresh_read_only"})

    def test_live_metadata_host_and_replay_privacy_rejection(self):
        envelope = {"session": "synthetic-session", "observed_at": now(),
                    "scope": asdict(SCOPE), "snapshot": native_snapshot()}
        summary = observe_desktop(self.home, "garden", SCOPE, io.StringIO(json.dumps(envelope)))
        self.assertEqual(summary["inventory_count"], 2)
        self.assertNotIn("Garden growth", json.dumps(summary))
        envelope["snapshot"]["threads"][0]["summary"] = "RAW BODY"
        with self.assertRaises(ConversationError):
            observe_desktop(self.home, "garden", SCOPE, io.StringIO(json.dumps(envelope)))
        del envelope["snapshot"]["threads"][0]["summary"]
        envelope["observed_at"] = "2000-01-01T00:00:00+00:00"
        with self.assertRaises(ConversationError):
            observe_desktop(self.home, "garden", SCOPE, io.StringIO(json.dumps(envelope)))


if __name__ == "__main__":
    unittest.main()
