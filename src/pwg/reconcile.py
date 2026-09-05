from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .discovery import DiscoveryResult, GitCandidate, discover_git_candidates
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


def _missing_or_moved(
    surface: dict,
    declared: dict,
    expected: str | None,
    candidates_by_remote: dict[str, list[GitCandidate]],
    *,
    has_mapping: bool,
) -> Finding:
    matches = candidates_by_remote.get(expected, []) if expected else []
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
            evidence=["exactly one trusted-root Git candidate matches the registered GitHub identity"],
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
            evidence=["multiple trusted-root Git candidates match the registered GitHub identity"],
            confidence="high",
            suggested_operation=None,
            risk="high",
        )
    return Finding(
        classification="MISSING",
        subject_id=surface["id"],
        declared=declared,
        observed={"path_exists": False},
        evidence=["registered local Surface has no observable workspace at its mapped location"],
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
        expected_raw = snapshot.github_full_name_for_object(surface["object_id"])
        expected = canonicalize_github_remote(
            f"https://github.com/{expected_raw}" if expected_raw else None
        )
        entry = workspaces.get(surface["id"])
        declared = {
            "object_id": surface["object_id"],
            "machine_id": surface["machine_id"],
        }
        if expected_raw:
            declared["github_full_name"] = expected_raw

        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            findings.append(
                _missing_or_moved(
                    surface,
                    declared,
                    expected,
                    candidates_by_remote,
                    has_mapping=False,
                )
            )
            continue

        mapped_path = Path(entry["path"]).expanduser().resolve()
        declared["path"] = str(mapped_path)
        if not mapped_path.exists():
            findings.append(
                _missing_or_moved(
                    surface,
                    declared,
                    expected,
                    candidates_by_remote,
                    has_mapping=True,
                )
            )
            continue

        if expected:
            try:
                raw_remote, actual = read_origin_remote(mapped_path)
            except GitInspectionError as exc:
                findings.append(
                    Finding(
                        classification="UNOBSERVABLE",
                        subject_id=surface["id"],
                        declared=declared,
                        observed={"path_exists": True},
                        evidence=[str(exc)],
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
                        subject_id=surface["id"],
                        declared=declared,
                        observed=observed,
                        evidence=["mapped path exists and Git origin matches registered GitHub identity"],
                        confidence="high",
                        risk="low",
                    )
                )
            else:
                findings.append(
                    Finding(
                        classification="DRIFT",
                        subject_id=surface["id"],
                        declared=declared,
                        observed=observed,
                        evidence=["mapped path exists but Git origin does not match registered GitHub identity"],
                        confidence="high",
                        suggested_operation="REVIEW_IDENTITY",
                        risk="high",
                    )
                )
        else:
            findings.append(
                Finding(
                    classification="MATCH",
                    subject_id=surface["id"],
                    declared=declared,
                    observed={"path_exists": True},
                    evidence=["mapped directory exists; no provider-backed Git identity is registered"],
                    confidence="medium",
                    risk="low",
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
                        evidence=["trusted-root Git repository is not represented by a registered GitHub repository Surface"],
                        confidence="medium",
                        suggested_operation="REGISTER_OR_IGNORE",
                        risk="low",
                    )
                )

    return findings
