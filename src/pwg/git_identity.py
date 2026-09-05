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


def read_origin_remote(path: str | Path) -> tuple[str | None, str | None]:
    workspace = Path(path)
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "remote", "get-url", "origin"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError as exc:
        raise GitInspectionError("git executable is not available") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitInspectionError(f"cannot inspect git remote for {workspace}: {exc}") from exc
    if result.returncode != 0:
        return None, None
    raw = result.stdout.strip()
    return raw, canonicalize_github_remote(raw)
