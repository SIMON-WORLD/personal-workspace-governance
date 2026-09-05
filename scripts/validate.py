#!/usr/bin/env python3
"""Validate governance schemas, synthetic examples, and core cross-entity invariants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
EXAMPLE_FILE = ROOT / "examples" / "synthetic" / "architecture-dogfood.yaml"

SCHEMA_FILES = {
    "object": "workspace-object.schema.json",
    "surface": "surface.schema.json",
    "relationship": "relationship.schema.json",
    "machine": "machine.schema.json",
    "local_map": "local-map.schema.json",
    "policy_exception": "policy-exception.schema.json",
    "change_event": "change-event.schema.json",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_unique(records: list[dict[str, Any]], label: str) -> None:
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise AssertionError(f"duplicate {label} ids detected")


def main() -> None:
    schemas = {name: load_json(SCHEMA_DIR / filename) for name, filename in SCHEMA_FILES.items()}

    for name, schema in schemas.items():
        Draft202012Validator.check_schema(schema)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise AssertionError(f"{name} does not declare JSON Schema draft 2020-12")

    with EXAMPLE_FILE.open("r", encoding="utf-8") as handle:
        example = yaml.safe_load(handle)

    objects = example.get("objects", [])
    surfaces = example.get("surfaces", [])
    relationships = example.get("relationships", [])
    machines = example.get("machines", [])
    local_maps = example.get("local_maps", {})
    policy_exceptions = example.get("policy_exceptions", [])

    for item in objects:
        Draft202012Validator(schemas["object"]).validate(item)
    for item in surfaces:
        Draft202012Validator(schemas["surface"]).validate(item)
    for item in relationships:
        Draft202012Validator(schemas["relationship"]).validate(item)
    for item in machines:
        Draft202012Validator(schemas["machine"]).validate(item)
    for item in local_maps.values():
        Draft202012Validator(schemas["local_map"]).validate(item)
    for item in policy_exceptions:
        Draft202012Validator(schemas["policy_exception"]).validate(item)

    assert_unique(objects, "Workspace Object")
    assert_unique(surfaces, "Surface")
    assert_unique(relationships, "Relationship")
    assert_unique(machines, "Machine")
    assert_unique(policy_exceptions, "Policy Exception")

    object_ids = {item["id"] for item in objects}
    surface_by_id = {item["id"]: item for item in surfaces}
    machine_ids = {item["id"] for item in machines}
    relationship_ids = {item["id"] for item in relationships}

    for surface in surfaces:
        if surface["object_id"] not in object_ids:
            raise AssertionError(f"Surface {surface['id']} references unknown object {surface['object_id']}")
        if surface["kind"] == "local" and surface.get("machine_id") not in machine_ids:
            raise AssertionError(f"Local Surface {surface['id']} references unknown machine")

    for relationship in relationships:
        source = relationship["from_object_id"]
        target = relationship["to_object_id"]
        if source not in object_ids or target not in object_ids:
            raise AssertionError(f"Relationship {relationship['id']} references an unknown object")
        if source == target:
            raise AssertionError(f"Relationship {relationship['id']} must not self-link")

    for map_key, local_map in local_maps.items():
        machine_id = local_map["machine_id"]
        if map_key != machine_id:
            raise AssertionError(f"Local map key {map_key} does not match machine_id {machine_id}")
        if machine_id not in machine_ids:
            raise AssertionError(f"Local map references unknown machine {machine_id}")
        for surface_id in local_map["workspaces"]:
            surface = surface_by_id.get(surface_id)
            if surface is None:
                raise AssertionError(f"Local map references unknown Surface {surface_id}")
            if surface["kind"] != "local":
                raise AssertionError(f"Local map entry {surface_id} is not a local Surface")
            if surface.get("machine_id") != machine_id:
                raise AssertionError(
                    f"Local map entry {surface_id} belongs to {surface.get('machine_id')}, not {machine_id}"
                )

    target_indexes = {
        "workspace_object": object_ids,
        "surface": set(surface_by_id),
        "relationship": relationship_ids,
        "machine": machine_ids,
    }
    for exception in policy_exceptions:
        target = exception["target"]
        if target["id"] not in target_indexes[target["kind"]]:
            raise AssertionError(
                f"Policy Exception {exception['id']} references unknown {target['kind']} {target['id']}"
            )

    print(
        "Validation passed: "
        f"{len(schemas)} schemas, {len(objects)} objects, {len(surfaces)} surfaces, "
        f"{len(relationships)} relationships, {len(machines)} machines, "
        f"{len(local_maps)} local maps, {len(policy_exceptions)} policy exceptions."
    )


if __name__ == "__main__":
    main()
