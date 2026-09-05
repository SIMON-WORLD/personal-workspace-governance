from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class RegistryError(ValueError):
    pass


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RegistryError(f"cannot read registry record {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RegistryError(f"registry record must be a mapping: {path}")
    return data


def _load_dir(root: Path, name: str) -> dict[str, dict[str, Any]]:
    directory = root / name
    records: dict[str, dict[str, Any]] = {}
    if not directory.exists():
        return records
    if not directory.is_dir():
        raise RegistryError(f"registry path is not a directory: {directory}")
    for path in sorted(directory.glob("*.yaml")):
        record = _load_yaml(path)
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise RegistryError(f"registry record lacks id: {path}")
        if record_id in records:
            raise RegistryError(f"duplicate registry id {record_id}")
        records[record_id] = record
    return records


@dataclass(frozen=True)
class RegistrySnapshot:
    root: Path
    objects: dict[str, dict[str, Any]]
    surfaces: dict[str, dict[str, Any]]
    machines: dict[str, dict[str, Any]]

    @classmethod
    def load(cls, root: str | Path) -> "RegistrySnapshot":
        root_path = Path(root).expanduser().resolve()
        if not root_path.is_dir():
            raise RegistryError(f"registry directory does not exist: {root_path}")
        return cls(
            root=root_path,
            objects=_load_dir(root_path, "objects"),
            surfaces=_load_dir(root_path, "surfaces"),
            machines=_load_dir(root_path, "machines"),
        )

    def require_machine(self, machine_id: str) -> dict[str, Any]:
        machine = self.machines.get(machine_id)
        if machine is None:
            raise RegistryError(f"unknown machine id: {machine_id}")
        if machine.get("status") == "retired":
            raise RegistryError(f"machine is retired: {machine_id}")
        return machine

    def require_local_surface(self, surface_id: str, machine_id: str) -> dict[str, Any]:
        surface = self.surfaces.get(surface_id)
        if surface is None:
            raise RegistryError(f"unknown surface id: {surface_id}")
        if surface.get("kind") != "local":
            raise RegistryError(f"surface is not local: {surface_id}")
        if surface.get("machine_id") != machine_id:
            raise RegistryError(
                f"surface {surface_id} belongs to {surface.get('machine_id')}, not {machine_id}"
            )
        return surface

    def local_surfaces(self, machine_id: str) -> list[dict[str, Any]]:
        self.require_machine(machine_id)
        return sorted(
            (
                surface
                for surface in self.surfaces.values()
                if surface.get("kind") == "local" and surface.get("machine_id") == machine_id
            ),
            key=lambda item: item["id"],
        )

    def github_repository_surfaces(self, object_id: str) -> list[dict[str, Any]]:
        """Return every GitHub repository Surface bound to an object."""
        return [
            surface
            for surface in self.surfaces.values()
            if surface.get("object_id") == object_id
            and surface.get("kind") == "github"
            and surface.get("resource_type") == "repository"
        ]

    def github_full_name_for_surface(self, surface_id: str) -> str | None:
        """Return the GitHub full name of the Surface a Local Surface binds to."""
        target = self.surfaces.get(surface_id) if surface_id else None
        if target is None:
            return None
        if target.get("kind") != "github" or target.get("resource_type") != "repository":
            return None
        locator = target.get("locator")
        if not isinstance(locator, dict):
            return None
        full_name = locator.get("full_name")
        return full_name if isinstance(full_name, str) else None

    def github_full_name_for_object(self, object_id: str) -> str | None:
        candidates = [
            surface
            for surface in self.surfaces.values()
            if surface.get("object_id") == object_id
            and surface.get("kind") == "github"
            and surface.get("resource_type") == "repository"
            and isinstance(surface.get("locator"), dict)
            and isinstance(surface["locator"].get("full_name"), str)
        ]
        source_candidates = [surface for surface in candidates if surface.get("role") == "source"]
        selected = source_candidates or candidates
        if len(selected) != 1:
            return None
        return selected[0]["locator"]["full_name"]

    def github_repository_names(self) -> set[str]:
        names: set[str] = set()
        for surface in self.surfaces.values():
            if surface.get("kind") != "github" or surface.get("resource_type") != "repository":
                continue
            locator = surface.get("locator")
            if isinstance(locator, dict) and isinstance(locator.get("full_name"), str):
                names.add(locator["full_name"])
        return names
