from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .discovery import (
    DiscoveryResult,
    GitCandidate,
    canonical_candidate_key,
    discover_git_candidates,
)
from .git_identity import GitInspectionError, canonicalize_github_remote, read_origin_remote
from .local_state import LocalStateError, load_config, load_local_map, load_trusted_roots
from .model import Finding
from .registry import RegistryError, RegistrySnapshot


def _candidate_index(discovery: DiscoveryResult) -> dict[str, list[GitCandidate]]:
    index: dict[str, list[GitCandidate]] = defaultdict(list)
    for candidate in discovery.candidates:
        if candidate.github_full_name:
            index[candidate.github_full_name].append(candidate)
    return index


def _claimed_paths(local_map: dict, subject_surface_id: str) -> set[str]:
    """Paths already mapped and claimed by *other* registered Local Surfaces."""
    workspaces = local_map.get("workspaces", {})
    claimed: set[str] = set()
    if not isinstance(workspaces, dict):
        return claimed
    for surface_id, entry in workspaces.items():
        if surface_id == subject_surface_id:
            continue
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            claimed.add(canonical_candidate_key(entry["path"]))
    return claimed


def _realization_mode(
    surface: dict,
    snapshot: RegistrySnapshot,
) -> tuple[str, str | None, bool]:
    """Resolve (mode, expected_canonical_github, is_legacy) for a Local Surface.

    mode is one of ``git``, ``directory``, ``container``. Explicit realization
    always wins; legacy inference only applies when no realization_kind is set.
    """
    realization_kind = surface.get("realization_kind")
    object_id = surface.get("object_id")
    if realization_kind in ("directory", "container"):
        return realization_kind, None, False
    if realization_kind == "git":
        full = snapshot.github_full_name_for_surface(surface.get("binds_to_surface_id"))
        expected = canonicalize_github_remote(f"https://github.com/{full}") if full else None
        return "git", expected, False
    # Legacy inference.
    repositories = snapshot.github_repository_surfaces(object_id)
    if len(repositories) == 1:
        locator = repositories[0].get("locator")
        full_name = locator.get("full_name") if isinstance(locator, dict) else None
        if isinstance(full_name, str) and full_name:
            expected = canonicalize_github_remote(f"https://github.com/{full_name}")
            return "git", expected, True
    return "directory", None, True


def _evidence_note(mode: str, is_legacy: bool) -> str:
    if is_legacy:
        return "legacy inference"
    return f"explicit {mode} realization"


def _missing_git_or_moved(
    surface: dict,
    declared: dict,
    expected: str | None,
    candidates_by_remote: dict[str, list[GitCandidate]],
    claimed: set[str],
    *,
    has_mapping: bool,
    is_legacy: bool,
) -> Finding:
    subject_path: str | None = declared.get("path")
    subject_key = canonical_candidate_key(subject_path) if subject_path else None
    matches = []
    if expected:
        for candidate in candidates_by_remote.get(expected, []):
            if candidate.path and canonical_candidate_key(candidate.path) in claimed:
                continue
            if subject_key is not None and canonical_candidate_key(candidate.path) == subject_key:
                continue
            matches.append(candidate)
    if len(matches) == 1:
        operation = "REMAP_LOCAL_PATH" if has_mapping else "MAP_LOCAL_PATH"
        observed = {"candidate_path": str(matches[0].path)}
        if matches[0].raw_remote:
            observed["origin"] = matches[0].raw_remote
        return Finding(
            classification="DRIFT",
            subject_id=surface["id"],
            declared=declared,
            observed=observed,
            evidence=[
                "exactly one unclaimed trusted-root Git candidate matches the expected identity",
                _evidence_note("git", is_legacy),
            ],
            confidence="high",
            suggested_operation=operation,
            risk="medium",
        )
    if len(matches) > 1:
        return Finding(
            classification="AMBIGUOUS",
            subject_id=surface["id"],
            declared=declared,
            observed={"candidate_paths": [str(item.path) for item in matches]},
            evidence=[
                "multiple unclaimed trusted-root Git candidates match the expected identity",
                _evidence_note("git", is_legacy),
            ],
            confidence="high",
            suggested_operation=None,
            risk="high",
        )
    return Finding(
        classification="MISSING",
        subject_id=surface["id"],
        declared=declared,
        observed={"path_exists": False},
        evidence=["registered Local Surface has no observable workspace at its mapped location"],
        confidence="medium" if has_mapping else "low",
        suggested_operation=None if has_mapping else "MAP_LOCAL_PATH",
        risk="medium",
    )


def reconcile(
    home: str | Path | None,
    registry_path: str | Path | None = None,
    *,
    include_trusted: bool = False,
) -> list[Finding]:
    config = load_config(home)
    local_map = load_local_map(home)
    selected_registry = registry_path or config.get("registry_path")
    if not selected_registry:
        raise LocalStateError("registry_path is missing from local config")
    try:
        snapshot = RegistrySnapshot.load(selected_registry)
        snapshot.require_machine(config["machine_id"])
    except RegistryError as exc:
        raise LocalStateError(str(exc)) from exc
    if local_map.get("machine_id") != config["machine_id"]:
        raise LocalStateError("local-map machine_id does not match config")

    discovery = DiscoveryResult(candidates=[], unreachable_roots=[])
    if include_trusted:
        trusted = load_trusted_roots(home)
        roots = trusted.get("roots", [])
        if not isinstance(roots, list):
            raise LocalStateError("trusted-roots roots must be a list")
        discovery = discover_git_candidates(roots)

    candidates_by_remote = _candidate_index(discovery)
    findings: list[Finding] = []
    workspaces = local_map.get("workspaces", {})
    if not isinstance(workspaces, dict):
        raise LocalStateError("local-map workspaces must be a mapping")

    for surface in snapshot.local_surfaces(config["machine_id"]):
        surface_id = surface["id"]
        mode, expected, is_legacy = _realization_mode(surface, snapshot)
        entry = workspaces.get(surface_id)
        declared: dict = {
            "object_id": surface["object_id"],
            "machine_id": surface["machine_id"],
            "realization": mode,
        }
        if is_legacy:
            declared["realization_inference"] = "legacy"
        if mode == "git":
            bound = surface.get("binds_to_surface_id")
            if bound:
                declared["binds_to_surface_id"] = bound
                declared["github_full_name"] = snapshot.github_full_name_for_surface(bound)
                declared["github_full_name"] = (
                    snapshot.github_full_name_for_surface(bound)
                    if bound
                    else declared.get("github_full_name")
                )

        has_mapping = isinstance(entry, dict) and isinstance(entry.get("path"), str)
        if has_mapping:
            mapped_path = Path(entry["path"]).expanduser().resolve()
            declared["path"] = str(mapped_path)

        if mode in ("directory", "container"):
            if not has_mapping:
                findings.append(
                    Finding(
                        classification="MISSING",
                        subject_id=surface_id,
                        declared=declared,
                        observed={"path_exists": False},
                        evidence=[
                            "registered Local Surface has no mapped path",
                            _evidence_note(mode, is_legacy),
                        ],
                        confidence="low",
                        suggested_operation="MAP_LOCAL_PATH",
                        risk="low",
                    )
                )
                continue
            if not mapped_path.exists():
                findings.append(
                    Finding(
                        classification="MISSING",
                        subject_id=surface_id,
                        declared=declared,
                        observed={"path_exists": False},
                        evidence=[
                            "registered mapped directory does not exist",
                            _evidence_note(mode, is_legacy),
                        ],
                        confidence="medium",
                        risk="medium",
                    )
                )
                continue
            findings.append(
                Finding(
                    classification="MATCH",
                    subject_id=surface_id,
                    declared=declared,
                    observed={"path_exists": True},
                    evidence=[
                        "mapped directory exists",
                        _evidence_note(mode, is_legacy),
                    ],
                    confidence="medium",
                    risk="low",
                )
            )
            continue

        # git mode (explicit or legacy inference).
        if not has_mapping:
            claimed = _claimed_paths(local_map, surface_id)
            findings.append(
                _missing_git_or_moved(
                    surface,
                    declared,
                    expected,
                    candidates_by_remote,
                    claimed,
                    has_mapping=False,
                    is_legacy=is_legacy,
                )
            )
            continue
        if expected is None:
            findings.append(
                Finding(
                    classification="UNOBSERVABLE",
                    subject_id=surface_id,
                    declared=declared,
                    observed={"path_exists": True if mapped_path.exists() else False},
                    evidence=[
                        "explicit git realization has no valid GitHub binding; "
                        "expected identity cannot be determined"
                    ],
                    confidence="high",
                    risk="medium",
                )
            )
            continue
        if not mapped_path.exists():
            claimed = _claimed_paths(local_map, surface_id)
            findings.append(
                _missing_git_or_moved(
                    surface,
                    declared,
                    expected,
                    candidates_by_remote,
                    claimed,
                    has_mapping=True,
                    is_legacy=is_legacy,
                )
            )
            continue

        try:
            raw_remote, actual = read_origin_remote(mapped_path)
        except GitInspectionError as exc:
            findings.append(
                Finding(
                    classification="UNOBSERVABLE",
                    subject_id=surface_id,
                    declared=declared,
                    observed={"path_exists": True},
                    evidence=[str(exc), _evidence_note(mode, is_legacy)],
                    confidence="high",
                    risk="medium",
                )
            )
            continue
        observed = {"path_exists": True, "github_full_name": actual}
        if raw_remote:
            observed["origin"] = raw_remote
        if actual == expected:
            findings.append(
                Finding(
                    classification="MATCH",
                    subject_id=surface_id,
                    declared=declared,
                    observed=observed,
                    evidence=[
                        "mapped path exists and Git origin matches registered GitHub identity",
                        _evidence_note(mode, is_legacy),
                    ],
                    confidence="high",
                    risk="low",
                )
            )
        else:
            findings.append(
                Finding(
                    classification="DRIFT",
                    subject_id=surface_id,
                    declared=declared,
                    observed=observed,
                    evidence=[
                        "mapped path exists but Git origin does not match registered GitHub identity",
                        _evidence_note(mode, is_legacy),
                    ],
                    confidence="high",
                    suggested_operation="REVIEW_IDENTITY",
                    risk="high",
                )
            )

    if include_trusted:
        for root in discovery.unreachable_roots:
            findings.append(
                Finding(
                    classification="UNREACHABLE",
                    subject_id=f"trusted-root:{root}",
                    declared={"path": str(root)},
                    observed={"reachable": False},
                    evidence=["configured trusted root is not currently an accessible directory"],
                    confidence="high",
                    risk="low",
                )
            )

        registered_names = {
            canonical
            for name in snapshot.github_repository_names()
            if (canonical := canonicalize_github_remote(f"https://github.com/{name}"))
        }
        for candidate in discovery.candidates:
            if candidate.github_full_name and candidate.github_full_name not in registered_names:
                findings.append(
                    Finding(
                        classification="UNREGISTERED",
                        subject_id=f"candidate:{candidate.path}",
                        declared={},
                        observed={
                            "path": str(candidate.path),
                            "github_full_name": candidate.github_full_name,
                            "origin": candidate.raw_remote,
                        },
                        evidence=[
                            "trusted-root Git repository is not represented by a registered GitHub repository Surface"
                        ],
                        confidence="medium",
                        suggested_operation="REGISTER_OR_IGNORE",
                        risk="low",
                    )
                )

    return findings
