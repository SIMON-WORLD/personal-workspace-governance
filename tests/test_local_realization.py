from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from pwg.discovery import discover_git_candidates
from pwg.git_identity import canonicalize_github_remote
from pwg.local_state import LocalStateError, add_trusted_root, bootstrap_local_state, set_mapping
from pwg.reconcile import reconcile


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def make_registry(root: Path, *, include_repo: bool = True) -> None:
    write_yaml(
        root / "machines" / "pc-a.yaml",
        {"schema_version": 1, "revision": 1, "id": "pc-a", "name": "PC A", "status": "active", "classes": []},
    )
    if not include_repo:
        return
    write_yaml(
        root / "objects" / "obj-repo.yaml",
        {
            "schema_version": 1,
            "revision": 1,
            "id": "obj-repo",
            "slug": "example-repo",
            "name": "Example Repo",
            "type": "repo",
            "lifecycle": "active",
            "aliases": [],
        },
    )
    write_yaml(
        root / "surfaces" / "surf-local.yaml",
        {
            "schema_version": 1,
            "revision": 1,
            "id": "surf-local",
            "object_id": "obj-repo",
            "kind": "local",
            "role": "exec",
            "resource_type": "directory",
            "machine_id": "pc-a",
        },
    )
    write_yaml(
        root / "surfaces" / "surf-github.yaml",
        {
            "schema_version": 1,
            "revision": 1,
            "id": "surf-github",
            "object_id": "obj-repo",
            "kind": "github",
            "role": "source",
            "resource_type": "repository",
            "provider_identity": {"id": 123},
            "locator": {"full_name": "example-org/example-repo"},
        },
    )


def init_git_repo(path: Path, remote: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote],
        check=True,
        capture_output=True,
        text=True,
    )


class LocalRealizationTests(unittest.TestCase):
    def test_bootstrap_creates_local_state_and_rejects_machine_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            home = root / "home"
            make_registry(registry)

            bootstrap_local_state(home, "pc-a", registry)
            self.assertTrue((home / "config.yaml").is_file())
            self.assertTrue((home / "local-map.yaml").is_file())
            self.assertTrue((home / "trusted-roots.yaml").is_file())

            bootstrap_local_state(home, "pc-a", registry)
            with self.assertRaises(LocalStateError):
                bootstrap_local_state(home, "pc-b", registry)

    def test_bootstrap_rejects_unknown_registry_machine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            make_registry(registry)
            with self.assertRaises(LocalStateError):
                bootstrap_local_state(root / "home", "pc-z", registry)

    def test_set_mapping_validates_surface_and_increments_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            home = root / "home"
            make_registry(registry)
            bootstrap_local_state(home, "pc-a", registry)

            local_map = set_mapping(home, "surf-local", root / "workspace")
            self.assertEqual(local_map["revision"], 2)
            self.assertEqual(local_map["workspaces"]["surf-local"]["path"], str((root / "workspace").resolve()))

            with self.assertRaises(LocalStateError):
                set_mapping(home, "surf-missing", root / "other")

    def test_remote_normalization_supports_https_and_ssh(self) -> None:
        variants = [
            "https://github.com/Example-Org/Example-Repo.git",
            "git@github.com:Example-Org/Example-Repo.git",
            "ssh://git@github.com/Example-Org/Example-Repo.git",
        ]
        for value in variants:
            with self.subTest(value=value):
                self.assertEqual(canonicalize_github_remote(value), "example-org/example-repo")

    def test_registered_git_workspace_matches_expected_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            home = root / "home"
            repo = root / "repo"
            make_registry(registry)
            init_git_repo(repo, "https://github.com/example-org/example-repo.git")
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-local", repo)

            findings = reconcile(home)
            local = next(item for item in findings if item.subject_id == "surf-local")
            self.assertEqual(local.classification, "MATCH")
            self.assertEqual(local.confidence, "high")

    def test_missing_mapped_path_with_unique_candidate_proposes_remap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            home = root / "home"
            trusted = root / "trusted"
            moved = trusted / "moved-repo"
            make_registry(registry)
            init_git_repo(moved, "git@github.com:example-org/example-repo.git")
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-local", root / "old-missing")
            add_trusted_root(home, trusted, max_depth=3)

            findings = reconcile(home, include_trusted=True)
            local = next(item for item in findings if item.subject_id == "surf-local")
            self.assertEqual(local.classification, "DRIFT")
            self.assertEqual(local.suggested_operation, "REMAP_LOCAL_PATH")
            self.assertEqual(Path(local.observed["candidate_path"]), moved.resolve())

    def test_duplicate_candidates_are_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            home = root / "home"
            trusted = root / "trusted"
            make_registry(registry)
            init_git_repo(trusted / "one", "https://github.com/example-org/example-repo.git")
            init_git_repo(trusted / "two", "https://github.com/example-org/example-repo.git")
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-local", root / "old-missing")
            add_trusted_root(home, trusted, max_depth=2)

            findings = reconcile(home, include_trusted=True)
            local = next(item for item in findings if item.subject_id == "surf-local")
            self.assertEqual(local.classification, "AMBIGUOUS")
            self.assertEqual(len(local.observed["candidate_paths"]), 2)
            self.assertIsNone(local.suggested_operation)

    def test_unknown_trusted_git_repo_is_unregistered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            home = root / "home"
            trusted = root / "trusted"
            make_registry(registry)
            init_git_repo(trusted / "known", "https://github.com/example-org/example-repo.git")
            init_git_repo(trusted / "unknown", "https://github.com/other-org/other-repo.git")
            bootstrap_local_state(home, "pc-a", registry)
            add_trusted_root(home, trusted, max_depth=2)

            findings = reconcile(home, include_trusted=True)
            unknown = [item for item in findings if item.classification == "UNREGISTERED"]
            self.assertEqual(len(unknown), 1)
            self.assertEqual(unknown[0].observed["github_full_name"], "other-org/other-repo")

    def test_missing_trusted_root_is_unreachable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            home = root / "home"
            make_registry(registry)
            bootstrap_local_state(home, "pc-a", registry)
            missing = root / "offline-drive"
            add_trusted_root(home, missing, max_depth=2)

            findings = reconcile(home, include_trusted=True)
            unreachable = [item for item in findings if item.classification == "UNREACHABLE"]
            self.assertEqual(len(unreachable), 1)
            self.assertEqual(Path(unreachable[0].declared["path"]), missing.resolve())

    def test_discovery_respects_max_depth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trusted = root / "trusted"
            init_git_repo(trusted / "one" / "two" / "repo", "https://github.com/example-org/deep.git")

            shallow = discover_git_candidates([{"path": str(trusted), "max_depth": 2}])
            deep = discover_git_candidates([{"path": str(trusted), "max_depth": 3}])
            self.assertEqual(shallow.candidates, [])
            self.assertEqual(len(deep.candidates), 1)

    def test_mismatched_git_identity_is_high_risk_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            home = root / "home"
            repo = root / "repo"
            make_registry(registry)
            init_git_repo(repo, "https://github.com/other-org/other-repo.git")
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-local", repo)

            findings = reconcile(home)
            local = next(item for item in findings if item.subject_id == "surf-local")
            self.assertEqual(local.classification, "DRIFT")
            self.assertEqual(local.risk, "high")
            self.assertEqual(local.suggested_operation, "REVIEW_IDENTITY")

    def test_existing_non_git_mapping_matches_with_medium_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            home = root / "home"
            workspace = root / "notes"
            workspace.mkdir()
            make_registry(registry, include_repo=False)
            write_yaml(
                registry / "objects" / "obj-notes.yaml",
                {
                    "schema_version": 1,
                    "revision": 1,
                    "id": "obj-notes",
                    "slug": "example-notes",
                    "name": "Example Notes",
                    "type": "research",
                    "lifecycle": "active",
                    "aliases": [],
                },
            )
            write_yaml(
                registry / "surfaces" / "surf-notes.yaml",
                {
                    "schema_version": 1,
                    "revision": 1,
                    "id": "surf-notes",
                    "object_id": "obj-notes",
                    "kind": "local",
                    "role": "exec",
                    "resource_type": "directory",
                    "machine_id": "pc-a",
                },
            )
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-notes", workspace)

            findings = reconcile(home)
            notes = next(item for item in findings if item.subject_id == "surf-notes")
            self.assertEqual(notes.classification, "MATCH")
            self.assertEqual(notes.confidence, "medium")

    def test_reconcile_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            home = root / "home"
            make_registry(registry)
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-local", root / "missing")
            before = (home / "local-map.yaml").read_bytes()

            reconcile(home, include_trusted=True)

            after = (home / "local-map.yaml").read_bytes()
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
