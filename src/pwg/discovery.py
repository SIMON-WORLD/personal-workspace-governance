from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import os
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


@dataclass(frozen=True)
class GitCandidate:
    path: Path
    raw_remote: str | None
    github_full_name: str | None


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: list[GitCandidate]
    unreachable_roots: list[Path]


def _discover_root(root: Path, max_depth: int) -> list[GitCandidate]:
    queue: deque[tuple[Path, int]] = deque([(root, 0)])
    candidates: list[GitCandidate] = []
    seen: set[str] = set()
    while queue:
        current, depth = queue.popleft()
        key = str(current.resolve()).casefold()
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
                children = sorted(
                    (
                        Path(entry.path)
                        for entry in entries
                        if entry.name not in _SKIP_DIRS and entry.is_dir(follow_symlinks=False)
                    ),
                    key=lambda path: path.name.casefold(),
                )
        except (OSError, PermissionError):
            continue
        for child in children:
            queue.append((child, depth + 1))
    return candidates


def discover_git_candidates(trusted_roots: list[dict[str, Any]]) -> DiscoveryResult:
    candidates: list[GitCandidate] = []
    unreachable: list[Path] = []
    seen_candidates: set[str] = set()
    for item in trusted_roots:
        root = Path(item["path"]).expanduser().resolve()
        max_depth = int(item.get("max_depth", 4))
        if not root.is_dir():
            unreachable.append(root)
            continue
        for candidate in _discover_root(root, max_depth):
            key = str(candidate.path).casefold()
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            candidates.append(candidate)
    candidates.sort(key=lambda item: str(item.path).casefold())
    unreachable.sort(key=lambda path: str(path).casefold())
    return DiscoveryResult(candidates=candidates, unreachable_roots=unreachable)
