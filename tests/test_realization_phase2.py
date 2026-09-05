from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from pwg.local_state import (
    LocalStateError,
    add_trusted_root,
    bootstrap_local_state,
    list_trusted_roots,
    load_trusted_roots,
    remove_trusted_root,
    set_mapping,
)
from pwg.cli import main
from pwg.reconcile import reconcile
from pwg.discovery import discover_git_candidates
from pwg.realization import validate_surface_realizations

EXAMPLE_REMOTE = "https://github.com/example-org/example-repo.git"
EXAMPLE_FULL = "example-org/example-repo"
OTHER_REMOTE = "https://github.com/other-org/other-repo.git"
OTHER_FULL = "other-org/other-repo"


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def init_git_repo(path: Path, remote: str) -> None:
    import subprocess

    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote],
        check=True,
        capture_output=True,
        text=True,
    )


def machine(root: Path, machine_id: str = "pc-a") -> None:
    write_yaml(
        root / "machines" / f"{machine_id}.yaml",
        {
            "schema_version": 1,
            "revision": 1,
            "id": machine_id,
            "name": machine_id.upper(),
            "status": "active",
            "classes": [],
        },
    )


def obj(root: Path, oid: str, kind: str = "repo", lifecycle: str = "active") -> None:
    write_yaml(
        root / "objects" / f"{oid}.yaml",
        {
            "schema_version": 1,
            "revision": 1,
            "id": oid,
            "slug": oid,
            "name": oid,
            "type": kind,
            "lifecycle": lifecycle,
            "aliases": [],
        },
    )


def local_surface(
    root: Path,
    sid: str,
    oid: str,
    *,
    machine_id: str = "pc-a",
    realization_kind: str | None = None,
    binds_to: str | None = None,
    resource_type: str = "directory",
) -> None:
    record = {
        "schema_version": 1,
        "revision": 1,
        "id": sid,
        "object_id": oid,
        "kind": "local",
        "role": "exec",
        "resource_type": resource_type,
        "machine_id": machine_id,
    }
    if realization_kind is not None:
        record["realization_kind"] = realization_kind
    if binds_to is not None:
        record["binds_to_surface_id"] = binds_to
    write_yaml(root / "surfaces" / f"{sid}.yaml", record)


def github_surface(
    root: Path,
    sid: str,
    oid: str,
    full_name: str,
    *,
    role: str = "source",
) -> None:
    write_yaml(
        root / "surfaces" / f"{sid}.yaml",
        {
            "schema_version": 1,
            "revision": 1,
            "id": sid,
            "object_id": oid,
            "kind": "github",
            "role": role,
            "resource_type": "repository",
            "provider_identity": {"id": 1},
            "locator": {"full_name": full_name},
        },
    )


def make_base_registry(root: Path, machine_id: str = "pc-a") -> Path:
    registry = root / "registry"
    machine(registry, machine_id)
    return registry


def bootstrap(root: Path, machine_id: str = "pc-a") -> tuple[Path, Path]:
    registry = make_base_registry(root, machine_id)
    home = root / "home"
    bootstrap_local_state(home, machine_id, registry)
    return home, registry


class SurfaceRealizationValidationTests(unittest.TestCase):
    def _objects(self):
        return [{"id": "obj-a", "type": "repo"}, {"id": "obj-b", "type": "repo"}]

    def _surfaces(self):
        return []

    def test_explicit_git_without_binding_is_invalid(self) -> None:
        surfaces = [
            {"id": "s", "object_id": "obj-a", "kind": "local", "realization_kind": "git"}
        ]
        errors = validate_surface_realizations(self._objects(), surfaces)
        self.assertTrue(any("requires binds_to_surface_id" in e for e in errors))

    def test_binding_to_other_object_is_invalid(self) -> None:
        surfaces = [
            {
                "id": "s",
                "object_id": "obj-a",
                "kind": "local",
                "realization_kind": "git",
                "binds_to_surface_id": "gh-b",
            },
            {
                "id": "gh-b",
                "object_id": "obj-b",
                "kind": "github",
                "resource_type": "repository",
            },
        ]
        errors = validate_surface_realizations(self._objects(), surfaces)
        self.assertTrue(any("belongs to object" in e for e in errors))

    def test_binding_to_non_github_is_invalid(self) -> None:
        surfaces = [
            {
                "id": "s",
                "object_id": "obj-a",
                "kind": "local",
                "realization_kind": "git",
                "binds_to_surface_id": "chatgpt-b",
            },
            {"id": "chatgpt-b", "object_id": "obj-a", "kind": "chatgpt", "resource_type": "project"},
        ]
        errors = validate_surface_realizations(self._objects(), surfaces)
        self.assertTrue(any("kind=github" in e for e in errors))

    def test_binding_to_non_repository_is_invalid(self) -> None:
        surfaces = [
            {
                "id": "s",
                "object_id": "obj-a",
                "kind": "local",
                "realization_kind": "git",
                "binds_to_surface_id": "org",
            },
            {
                "id": "org",
                "object_id": "obj-a",
                "kind": "github",
                "resource_type": "organization",
            },
        ]
        errors = validate_surface_realizations(self._objects(), surfaces)
        self.assertTrue(any("resource_type=repository" in e for e in errors))

    def test_binding_to_missing_surface_is_invalid(self) -> None:
        surfaces = [
            {
                "id": "s",
                "object_id": "obj-a",
                "kind": "local",
                "realization_kind": "git",
                "binds_to_surface_id": "nope",
            }
        ]
        errors = validate_surface_realizations(self._objects(), surfaces)
        self.assertTrue(any("does not reference an existing surface" in e for e in errors))

    def test_directory_or_container_with_binding_is_invalid(self) -> None:
        for kind in ("directory", "container"):
            with self.subTest(kind=kind):
                surfaces = [
                    {
                        "id": "s",
                        "object_id": "obj-a",
                        "kind": "local",
                        "realization_kind": kind,
                        "binds_to_surface_id": "gh",
                    },
                    {"id": "gh", "object_id": "obj-a", "kind": "github", "resource_type": "repository"},
                ]
                errors = validate_surface_realizations(self._objects(), surfaces)
                self.assertTrue(any("must not declare binds_to_surface_id" in e for e in errors))

    def test_non_local_surface_with_realization_fields_is_invalid(self) -> None:
        for fields in (
            {"realization_kind": "directory"},
            {"binds_to_surface_id": "x"},
        ):
            with self.subTest(fields=fields):
                surfaces = [
                    {"id": "c", "object_id": "obj-a", "kind": "chatgpt", "resource_type": "project", **fields}
                ]
                errors = validate_surface_realizations(self._objects(), surfaces)
                self.assertTrue(any("non-local surface" in e for e in errors))

    def test_valid_explicit_realizations_pass(self) -> None:
        objects = [
            {"id": "obj-repo", "type": "repo"},
            {"id": "obj-paper", "type": "paper"},
            {"id": "obj-hub", "type": "brand"},
        ]
        surfaces = [
            {"id": "gh", "object_id": "obj-repo", "kind": "github", "resource_type": "repository"},
            {
                "id": "s-git",
                "object_id": "obj-repo",
                "kind": "local",
                "realization_kind": "git",
                "binds_to_surface_id": "gh",
            },
            {"id": "s-dir", "object_id": "obj-paper", "kind": "local", "realization_kind": "directory"},
            {"id": "s-container", "object_id": "obj-hub", "kind": "local", "realization_kind": "container"},
        ]
        errors = validate_surface_realizations(objects, surfaces)
        self.assertEqual(errors, [])


class RealizationReconcileTests(unittest.TestCase):
    def test_explicit_git_binding_matches_high(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            obj(registry, "obj-repo")
            github_surface(registry, "gh", "obj-repo", EXAMPLE_FULL)
            local_surface(registry, "surf-git", "obj-repo", realization_kind="git", binds_to="gh")
            repo = root / "clone"
            init_git_repo(repo, EXAMPLE_REMOTE)
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-git", repo)

            findings = reconcile(home)
            item = next(f for f in findings if f.subject_id == "surf-git")
            self.assertEqual(item.classification, "MATCH")
            self.assertEqual(item.confidence, "high")
            self.assertNotIn("legacy", " ".join(item.evidence).lower())

    def test_container_with_github_source_matches_medium_without_git_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            obj(registry, "obj-hub", kind="brand")
            github_surface(registry, "gh", "obj-hub", EXAMPLE_FULL)
            local_surface(registry, "surf-container", "obj-hub", realization_kind="container")
            workspace = root / "container"
            workspace.mkdir()
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-container", workspace)

            findings = reconcile(home)
            item = next(f for f in findings if f.subject_id == "surf-container")
            self.assertEqual(item.classification, "MATCH")
            self.assertEqual(item.confidence, "medium")

    def test_non_git_paper_directory_matches_medium(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            obj(registry, "obj-paper", kind="paper")
            local_surface(registry, "surf-paper", "obj-paper", realization_kind="directory")
            workspace = root / "paper-dir"
            workspace.mkdir()
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-paper", workspace)

            findings = reconcile(home)
            item = next(f for f in findings if f.subject_id == "surf-paper")
            self.assertEqual(item.classification, "MATCH")
            self.assertEqual(item.confidence, "medium")

    def test_two_registered_clones_both_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            obj(registry, "obj-repo")
            github_surface(registry, "gh", "obj-repo", EXAMPLE_FULL)
            local_surface(registry, "surf-a", "obj-repo", realization_kind="git", binds_to="gh")
            local_surface(registry, "surf-b", "obj-repo", realization_kind="git", binds_to="gh")
            trusted = root / "trusted"
            init_git_repo(trusted / "clone-a", EXAMPLE_REMOTE)
            init_git_repo(trusted / "clone-b", EXAMPLE_REMOTE)
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-a", trusted / "clone-a")
            set_mapping(home, "surf-b", trusted / "clone-b")
            add_trusted_root(home, trusted, max_depth=2)

            findings = reconcile(home, include_trusted=True)
            by_id = {f.subject_id: f for f in findings}
            self.assertEqual(by_id["surf-a"].classification, "MATCH")
            self.assertEqual(by_id["surf-b"].classification, "MATCH")
            self.assertFalse(any(f.classification == "AMBIGUOUS" for f in findings))

    def test_missing_git_unique_unclaimed_candidate_proposes_remap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            obj(registry, "obj-repo")
            github_surface(registry, "gh", "obj-repo", EXAMPLE_FULL)
            local_surface(registry, "surf-git", "obj-repo", realization_kind="git", binds_to="gh")
            trusted = root / "trusted"
            init_git_repo(trusted / "moved", EXAMPLE_REMOTE)
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-git", root / "old-missing")
            add_trusted_root(home, trusted, max_depth=2)

            findings = reconcile(home, include_trusted=True)
            item = next(f for f in findings if f.subject_id == "surf-git")
            self.assertEqual(item.classification, "DRIFT")
            self.assertEqual(item.suggested_operation, "REMAP_LOCAL_PATH")
            self.assertEqual(Path(item.observed["candidate_path"]), (trusted / "moved").resolve())

    def test_missing_git_two_unclaimed_candidates_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            obj(registry, "obj-repo")
            github_surface(registry, "gh", "obj-repo", EXAMPLE_FULL)
            local_surface(registry, "surf-git", "obj-repo", realization_kind="git", binds_to="gh")
            trusted = root / "trusted"
            init_git_repo(trusted / "one", EXAMPLE_REMOTE)
            init_git_repo(trusted / "two", EXAMPLE_REMOTE)
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-git", root / "old-missing")
            add_trusted_root(home, trusted, max_depth=2)

            findings = reconcile(home, include_trusted=True)
            item = next(f for f in findings if f.subject_id == "surf-git")
            self.assertEqual(item.classification, "AMBIGUOUS")
            self.assertEqual(len(item.observed["candidate_paths"]), 2)

    def test_candidate_claimed_by_other_surface_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            obj(registry, "obj-repo")
            github_surface(registry, "gh", "obj-repo", EXAMPLE_FULL)
            local_surface(registry, "surf-a", "obj-repo", realization_kind="git", binds_to="gh")
            local_surface(registry, "surf-b", "obj-repo", realization_kind="git", binds_to="gh")
            trusted = root / "trusted"
            init_git_repo(trusted / "clone-a", EXAMPLE_REMOTE)
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-a", trusted / "clone-a")
            set_mapping(home, "surf-b", root / "missing-b")
            add_trusted_root(home, trusted, max_depth=2)

            findings = reconcile(home, include_trusted=True)
            item_a = next(f for f in findings if f.subject_id == "surf-a")
            item_b = next(f for f in findings if f.subject_id == "surf-b")
            self.assertEqual(item_a.classification, "MATCH")
            self.assertEqual(item_b.classification, "MISSING")
            self.assertIsNone(item_b.suggested_operation)

    def test_directory_missing_is_missing_without_candidate_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            obj(registry, "obj-paper", kind="paper")
            local_surface(registry, "surf-paper", "obj-paper", realization_kind="directory")
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-paper", root / "gone")

            findings = reconcile(home)
            item = next(f for f in findings if f.subject_id == "surf-paper")
            self.assertEqual(item.classification, "MISSING")

    def test_legacy_inference_is_labeled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            obj(registry, "obj-repo")
            github_surface(registry, "gh", "obj-repo", EXAMPLE_FULL)
            local_surface(registry, "surf-legacy", "obj-repo")
            repo = root / "clone"
            init_git_repo(repo, EXAMPLE_REMOTE)
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-legacy", repo)

            findings = reconcile(home)
            item = next(f for f in findings if f.subject_id == "surf-legacy")
            self.assertEqual(item.classification, "MATCH")
            self.assertIn("legacy", " ".join(item.evidence).lower())

    def test_legacy_directory_inference_is_labeled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            obj(registry, "obj-notes", kind="research")
            local_surface(registry, "surf-notes", "obj-notes")
            workspace = root / "notes"
            workspace.mkdir()
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-notes", workspace)

            findings = reconcile(home)
            item = next(f for f in findings if f.subject_id == "surf-notes")
            self.assertEqual(item.classification, "MATCH")
            self.assertEqual(item.confidence, "medium")
            self.assertIn("legacy", " ".join(item.evidence).lower())


class DiscoveryExclusionTests(unittest.TestCase):
    def test_exclude_globs_prune_vendor_and_tmp_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            registry = make_base_registry(root)
            bootstrap_local_state(home, "pc-a", registry)
            trusted = root / "trusted"
            init_git_repo(trusted / ".agents" / "skills" / "vendor-skill", OTHER_REMOTE)
            init_git_repo(trusted / "05_tmp" / "scratch", OTHER_REMOTE)
            init_git_repo(trusted / "work" / "real", EXAMPLE_REMOTE)
            add_trusted_root(
                home,
                trusted,
                max_depth=4,
                exclude_globs=[".agents/skills/**", "05_tmp/**"],
            )

            roots = load_trusted_roots(home)["roots"]
            result = discover_git_candidates(roots)
            names = {str(c.path) for c in result.candidates}
            self.assertIn(str((trusted / "work" / "real").resolve()), names)
            self.assertNotIn(str((trusted / ".agents" / "skills" / "vendor-skill").resolve()), names)
            self.assertNotIn(str((trusted / "05_tmp" / "scratch").resolve()), names)

    def test_excluded_subtree_registered_surface_still_reconciles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            obj(registry, "obj-notes", kind="research")
            local_surface(registry, "surf-notes", "obj-notes", realization_kind="directory")
            trusted = root / "trusted"
            registered_dir = trusted / ".agents" / "skills" / "registered"
            registered_dir.mkdir(parents=True)
            init_git_repo(trusted / ".agents" / "skills" / "vendor-skill", OTHER_REMOTE)
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            set_mapping(home, "surf-notes", registered_dir)
            add_trusted_root(
                home,
                trusted,
                max_depth=4,
                exclude_globs=[".agents/skills/**"],
            )

            registered = reconcile(home)
            item = next(f for f in registered if f.subject_id == "surf-notes")
            self.assertEqual(item.classification, "MATCH")

            trusted_findings = reconcile(home, include_trusted=True)
            item2 = next(f for f in trusted_findings if f.subject_id == "surf-notes")
            self.assertEqual(item2.classification, "MATCH")
            self.assertFalse(any(f.classification == "UNREGISTERED" for f in trusted_findings))


class TrustedRootCliTests(unittest.TestCase):
    def test_trust_add_merges_and_deduplicates_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            registry = make_base_registry(root)
            bootstrap_local_state(home, "pc-a", registry)
            trusted = root / "trusted"
            trusted.mkdir()

            add_trusted_root(home, trusted, max_depth=3, exclude_globs=[".a/**", "tmp/**"])
            add_trusted_root(home, trusted, max_depth=3, exclude_globs=["tmp/**", "vendor/**"])

            roots = load_trusted_roots(home)["roots"]
            self.assertEqual(len(roots), 1)
            self.assertEqual(roots[0]["exclude_globs"], [".a/**", "tmp/**", "vendor/**"])

    def test_trust_list_and_trust_rm_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            registry = make_base_registry(root)
            bootstrap_local_state(home, "pc-a", registry)
            trusted_a = root / "a"
            trusted_b = root / "b"
            trusted_a.mkdir()
            trusted_b.mkdir()

            add_trusted_root(home, trusted_a, max_depth=2, exclude_globs=["x/**", "y/**"])
            add_trusted_root(home, trusted_b, max_depth=2)
            listed = list_trusted_roots(home)
            self.assertEqual(len(listed), 2)

            remove_trusted_root(home, trusted_a, exclude_glob="x/**")
            roots = load_trusted_roots(home)["roots"]
            entry_a = next(r for r in roots if r["path"] == str(trusted_a.resolve()))
            self.assertEqual(entry_a["exclude_globs"], ["y/**"])

            remove_trusted_root(home, trusted_a)
            roots = load_trusted_roots(home)["roots"]
            self.assertEqual([r["path"] for r in roots], [str(trusted_b.resolve())])

    def test_trust_add_rejects_absolute_glob(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            registry = make_base_registry(root)
            bootstrap_local_state(home, "pc-a", registry)
            trusted = root / "trusted"
            trusted.mkdir()
            with self.assertRaises(LocalStateError):
                add_trusted_root(home, trusted, max_depth=2, exclude_globs=["C:/Users/x/**"])



    def test_cli_trust_commands_smoke(self) -> None:
        import io
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = make_base_registry(root)
            home = root / "home"
            bootstrap_local_state(home, "pc-a", registry)
            trusted = root / "trusted"
            trusted.mkdir()

            def run(*argv: str) -> str:
                buffer = io.StringIO()
                original = sys.stdout
                sys.stdout = buffer
                try:
                    code = main(["--home", str(home), *argv])
                finally:
                    sys.stdout = original
                self.assertEqual(code, 0)
                return buffer.getvalue()

            out = run("trust-add", "--path", str(trusted), "--max-depth", "2",
                      "--exclude-glob", ".agents/skills/**", "--exclude-glob", "05_tmp/**")
            self.assertIn("Trusted root added", out)
            listed = run("trust-list")
            self.assertIn(".agents/skills/**", listed)
            self.assertIn("05_tmp/**", listed)
            run("trust-rm", "--path", str(trusted), "--exclude-glob", "05_tmp/**")
            listed2 = run("trust-list")
            self.assertNotIn("05_tmp/**", listed2)
            self.assertIn(".agents/skills/**", listed2)
            run("trust-rm", "--path", str(trusted))
            listed3 = run("trust-list")
            self.assertEqual(listed3.strip(), "")

if __name__ == "__main__":
    unittest.main()
