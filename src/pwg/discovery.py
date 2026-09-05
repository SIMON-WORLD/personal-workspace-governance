from __future__ import annotations

import fnmatch
import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .git_identity import GitInspectionError, is_git_workspace, read_origin_remote

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "vendor",
}


def canonical_candidate_key(path: str | Path) -> str:
    """Windows-aware canonical identity for a candidate path.

    Separators are normalized and, on Windows, comparison is case-insensitive.
    """
    resolved = str(Path(path).expanduser().resolve()).replace("\\", "/")
    return resolved.casefold() if os.name == "nt" else resolved


def _fold(value: str) -> str:
    return value.casefold() if os.name == "nt" else value


def _is_absolute_glob(pattern: str) -> bool:
    if not isinstance(pattern, str) or not pattern:
        return False
    if pattern.startswith(("/", "\\")):
        return True
    if len(pattern) >= 2 and pattern[1] == ":":
        return True
    return os.path.isabs(pattern)


def _glob_match(pattern: str, relative: str) -> bool:
    """Match a root-relative POSIX path against a glob supporting * and **.

    ``**`` matches zero or more path segments. Matching is case-insensitive on
    Windows and case-sensitive elsewhere.
    """
    pat_parts = [part for part in pattern.replace("\\", "/").strip("/").split("/") if part]
    rel_parts = [part for part in relative.strip("/").split("/") if part]
    if not pat_parts:
        return False

    def rec(pi: int, ri: int) -> bool:
        if pi == len(pat_parts):
            return ri == len(rel_parts)
        segment = pat_parts[pi]
        if segment == "**":
            for skip in range(ri, len(rel_parts) + 1):
                if rec(pi + 1, skip):
                    return True
            return False
        if ri >= len(rel_parts):
            return False
        if fnmatch.fnmatchcase(_fold(rel_parts[ri]), _fold(segment)):
            return rec(pi + 1, ri + 1)
        return False

    return rec(0, 0)


def _exclusion_matches(exclude_globs: list[str], relative: str) -> bool:
    for pattern in exclude_globs:
        if _glob_match(pattern, relative):
            return True
    return False


@dataclass(frozen=True)
class GitCandidate:
    path: Path
    raw_remote: str | None
    github_full_name: str | None


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: list[GitCandidate]
    unreachable_roots: list[Path]


def _discover_root(root: Path, max_depth: int, exclude_globs: list[str]) -> list[GitCandidate]:
    queue: deque[tuple[Path, int]] = deque([(root, 0)])
    candidates: list[GitCandidate] = []
    seen: set[str] = set()
    while queue:
        current, depth = queue.popleft()
        key = canonical_candidate_key(current)
        if key in seen:
            continue
        seen.add(key)

        if is_git_workspace(current):
            try:
                raw, canonical = read_origin_remote(current)
            except GitInspectionError:
                raw, canonical = None, None
            candidates.append(GitCandidate(current.resolve(), raw, canonical))

        if depth >= max_depth:
            continue
        try:
            with os.scandir(current) as entries:
                children = []
                for entry in entries:
                    if entry.name in _SKIP_DIRS:
                        continue
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    child = Path(entry.path)
                    try:
                        relative = child.relative_to(root).as_posix()
                    except ValueError:
                        relative = child.name
                    if _exclusion_matches(exclude_globs, relative):
                        continue
                    children.append(child)
        except (OSError, PermissionError):
            continue
        for child in sorted(children, key=lambda path: path.name.casefold()):
            queue.append((child, depth + 1))
    return candidates


def discover_git_candidates(trusted_roots: list[dict[str, Any]]) -> DiscoveryResult:
    candidates: list[GitCandidate] = []
    unreachable: list[Path] = []
    seen_candidates: set[str] = set()
    for item in trusted_roots:
        root = Path(item["path"]).expanduser().resolve()
        max_depth = int(item.get("max_depth", 4))
        raw_globs = item.get("exclude_globs", []) or []
        exclude_globs = [str(value) for value in raw_globs]
        for pattern in exclude_globs:
            if _is_absolute_glob(pattern):
                raise ValueError(
                    f"exclude_glob must be relative to its trusted root: {pattern!r}"
                )
        if not root.is_dir():
            unreachable.append(root)
            continue
        for candidate in _discover_root(root, max_depth, exclude_globs):
            key = canonical_candidate_key(candidate.path)
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            candidates.append(candidate)
    candidates.sort(key=lambda item: canonical_candidate_key(item.path))
    unreachable.sort(key=lambda path: canonical_candidate_key(path))
    return DiscoveryResult(candidates=candidates, unreachable_roots=unreachable)
