from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .registry import RegistryError, RegistrySnapshot


class LocalStateError(ValueError):
    pass


def default_home() -> Path:
    override = os.environ.get("PWG_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".workspace-governance").resolve()


def _home_path(home: str | Path | None) -> Path:
    return default_home() if home is None else Path(home).expanduser().resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LocalStateError(f"missing local state file: {path}") from exc
    except (OSError, yaml.YAMLError) as exc:
        raise LocalStateError(f"cannot read local state file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LocalStateError(f"local state file must be a mapping: {path}")
    return data


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    tmp = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def load_config(home: str | Path | None = None) -> dict[str, Any]:
    return _load_yaml(_home_path(home) / "config.yaml")


def load_local_map(home: str | Path | None = None) -> dict[str, Any]:
    return _load_yaml(_home_path(home) / "local-map.yaml")


def load_trusted_roots(home: str | Path | None = None) -> dict[str, Any]:
    return _load_yaml(_home_path(home) / "trusted-roots.yaml")


def bootstrap_local_state(
    home: str | Path | None,
    machine_id: str,
    registry_path: str | Path,
) -> None:
    home_path = _home_path(home)
    registry_root = Path(registry_path).expanduser().resolve()
    try:
        snapshot = RegistrySnapshot.load(registry_root)
        snapshot.require_machine(machine_id)
    except RegistryError as exc:
        raise LocalStateError(str(exc)) from exc

    config_path = home_path / "config.yaml"
    desired_config = {
        "schema_version": 1,
        "machine_id": machine_id,
        "registry_path": str(registry_root),
    }

    if config_path.exists():
        current = _load_yaml(config_path)
        if current.get("machine_id") != machine_id:
            raise LocalStateError(
                f"local state belongs to machine {current.get('machine_id')}, not {machine_id}"
            )
        current_registry = current.get("registry_path")
        if current_registry and Path(current_registry).expanduser().resolve() != registry_root:
            raise LocalStateError("local state is already bound to a different registry path")
    else:
        _atomic_write_yaml(config_path, desired_config)

    local_map_path = home_path / "local-map.yaml"
    if local_map_path.exists():
        local_map = _load_yaml(local_map_path)
        if local_map.get("machine_id") != machine_id:
            raise LocalStateError("local-map machine_id does not match config")
    else:
        _atomic_write_yaml(
            local_map_path,
            {
                "schema_version": 1,
                "revision": 1,
                "machine_id": machine_id,
                "workspaces": {},
            },
        )

    trusted_path = home_path / "trusted-roots.yaml"
    if not trusted_path.exists():
        _atomic_write_yaml(trusted_path, {"schema_version": 1, "roots": []})


def _snapshot_from_config(
    home_path: Path,
    registry_path: str | Path | None = None,
) -> tuple[dict[str, Any], RegistrySnapshot]:
    config = _load_yaml(home_path / "config.yaml")
    selected = (
        Path(registry_path).expanduser().resolve()
        if registry_path
        else Path(config["registry_path"]).expanduser().resolve()
    )
    try:
        snapshot = RegistrySnapshot.load(selected)
        snapshot.require_machine(config["machine_id"])
    except (KeyError, RegistryError) as exc:
        raise LocalStateError(str(exc)) from exc
    return config, snapshot


def set_mapping(
    home: str | Path | None,
    surface_id: str,
    path: str | Path,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    home_path = _home_path(home)
    config, snapshot = _snapshot_from_config(home_path, registry_path)
    try:
        snapshot.require_local_surface(surface_id, config["machine_id"])
    except RegistryError as exc:
        raise LocalStateError(str(exc)) from exc

    local_map_path = home_path / "local-map.yaml"
    local_map = _load_yaml(local_map_path)
    if local_map.get("machine_id") != config["machine_id"]:
        raise LocalStateError("local-map machine_id does not match config")
    workspaces = local_map.setdefault("workspaces", {})
    resolved = str(Path(path).expanduser().resolve())
    current = workspaces.get(surface_id, {}).get("path")
    if current == resolved:
        return local_map
    workspaces[surface_id] = {"path": resolved}
    local_map["revision"] = int(local_map.get("revision", 0)) + 1
    _atomic_write_yaml(local_map_path, local_map)
    return local_map


def _validate_exclude_globs(exclude_globs: list[str]) -> None:
    for pattern in exclude_globs:
        if not isinstance(pattern, str) or not pattern:
            raise LocalStateError("exclude_globs entries must be non-empty strings")
        if pattern.startswith(("/", "\\")):
            raise LocalStateError(
                f"exclude_glob must be relative to its trusted root: {pattern!r}"
            )
        if len(pattern) >= 2 and pattern[1] == ":":
            raise LocalStateError(
                f"exclude_glob must be relative to its trusted root: {pattern!r}"
            )


def add_trusted_root(
    home: str | Path | None,
    path: str | Path,
    *,
    max_depth: int = 4,
    exclude_globs: list[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(max_depth, int) or not 0 <= max_depth <= 12:
        raise LocalStateError("max_depth must be an integer between 0 and 12")
    globs = list(exclude_globs or [])
    _validate_exclude_globs(globs)
    home_path = _home_path(home)
    _load_yaml(home_path / "config.yaml")
    trusted_path = home_path / "trusted-roots.yaml"
    trusted = _load_yaml(trusted_path)
    roots = trusted.setdefault("roots", [])
    resolved = str(Path(path).expanduser().resolve())

    for item in roots:
        if item.get("path") == resolved:
            changed = False
            if item.get("max_depth") != max_depth:
                item["max_depth"] = max_depth
                changed = True
            existing = item.setdefault("exclude_globs", [])
            for pattern in globs:
                if pattern not in existing:
                    existing.append(pattern)
                    changed = True
            if existing:
                existing.sort(key=lambda value: value.casefold())
                item["exclude_globs"] = existing
            else:
                item.pop("exclude_globs", None)
            if changed:
                _atomic_write_yaml(trusted_path, trusted)
            return trusted

    entry: dict[str, Any] = {"path": resolved, "max_depth": max_depth}
    if globs:
        globs.sort(key=lambda value: value.casefold())
        entry["exclude_globs"] = globs
    roots.append(entry)
    roots.sort(key=lambda item: item["path"].casefold())
    _atomic_write_yaml(trusted_path, trusted)
    return trusted


def remove_trusted_root(
    home: str | Path | None,
    path: str | Path,
    *,
    exclude_glob: str | None = None,
) -> dict[str, Any]:
    home_path = _home_path(home)
    _load_yaml(home_path / "config.yaml")
    trusted_path = home_path / "trusted-roots.yaml"
    trusted = _load_yaml(trusted_path)
    roots = trusted.setdefault("roots", [])
    resolved = str(Path(path).expanduser().resolve())

    for item in list(roots):
        if item.get("path") != resolved:
            continue
        if exclude_glob is None:
            roots.remove(item)
        else:
            existing = item.get("exclude_globs", [])
            if exclude_glob not in existing:
                raise LocalStateError(
                    f"trusted root {resolved} has no exclusion {exclude_glob!r}"
                )
            existing = [value for value in existing if value != exclude_glob]
            if existing:
                item["exclude_globs"] = existing
            else:
                item.pop("exclude_globs", None)
        _atomic_write_yaml(trusted_path, trusted)
        return trusted
    raise LocalStateError(f"unknown trusted root: {resolved}")


def list_trusted_roots(home: str | Path | None = None) -> list[dict[str, Any]]:
    trusted = load_trusted_roots(home)
    roots = trusted.get("roots", [])
    if not isinstance(roots, list):
        raise LocalStateError("trusted-roots roots must be a list")
    return list(roots)
