from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


class GitInspectionError(RuntimeError):
    pass


_SCP_GITHUB = re.compile(r"^(?:[^@/]+@)?github\.com:(?P<path>.+)$", re.IGNORECASE)


def canonicalize_github_remote(url: str | None) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None
    value = url.strip()
    match = _SCP_GITHUB.match(value)
    if match:
        repo_path = match.group("path")
    else:
        parsed = urlparse(value)
        if (parsed.hostname or "").lower() != "github.com":
            return None
        repo_path = parsed.path.lstrip("/")
    repo_path = repo_path.rstrip("/")
    if repo_path.lower().endswith(".git"):
        repo_path = repo_path[:-4]
    parts = [part for part in repo_path.split("/") if part]
    if len(parts) != 2:
        return None
    return f"{parts[0].lower()}/{parts[1].lower()}"


def is_git_workspace(path: str | Path) -> bool:
    return (Path(path) / ".git").exists()


def _run_git(workspace: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(workspace), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError as exc:
        raise GitInspectionError("git executable is not available") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitInspectionError(f"cannot inspect git workspace {workspace}: {exc}") from exc


def read_origin_remote(path: str | Path) -> tuple[str | None, str | None]:
    workspace = Path(path)
    result = _run_git(workspace, ["remote", "get-url", "origin"])
    if result.returncode == 0:
        raw = result.stdout.strip()
        return raw, canonicalize_github_remote(raw)
    # The origin could not be read. Distinguish "valid repo without an origin"
    # from "repo metadata is currently unreadable" (e.g. not a git checkout,
    # permission/ownership errors) so callers do not misclassify the latter as
    # identity drift.
    probe = _run_git(workspace, ["rev-parse", "--is-inside-work-tree"])
    if probe.returncode != 0:
        detail = (probe.stderr or result.stderr or "").strip()
        raise GitInspectionError(f"cannot inspect git workspace {workspace}: {detail}")
    return None, None
