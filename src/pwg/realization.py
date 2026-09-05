from __future__ import annotations

from typing import Any, Iterable

"""Cross-record validation for explicit Local Surface realization.

Phase 2.2: a Local Surface may declare ``realization_kind`` (git / directory /
container) and, for git realizations, ``binds_to_surface_id`` pointing at the
GitHub repository Surface that provides the expected Git identity.

JSON Schema covers per-record constraints (surface.schema.json). This module
covers cross-record constraints that a single record cannot express.
"""


def validate_surface_realizations(
    objects: Iterable[dict[str, Any]],
    surfaces: Iterable[dict[str, Any]],
) -> list[str]:
    """Return a list of human-readable errors, or an empty list when valid."""
    errors: list[str] = []
    object_ids = {item.get("id") for item in objects}
    surface_by_id: dict[str, dict[str, Any]] = {item.get("id"): item for item in surfaces}

    for surface in surfaces:
        surface_id = surface.get("id")
        kind = surface.get("kind")
        realization_kind = surface.get("realization_kind")
        binds_to = surface.get("binds_to_surface_id")

        if kind != "local" and (realization_kind is not None or binds_to is not None):
            errors.append(
                f"surface {surface_id}: non-local surface must not declare "
                "realization_kind or binds_to_surface_id"
            )
            continue

        if realization_kind is None:
            if binds_to is not None:
                errors.append(
                    f"surface {surface_id}: binds_to_surface_id requires "
                    "realization_kind: git"
                )
            continue

        if realization_kind not in ("git", "directory", "container"):
            errors.append(
                f"surface {surface_id}: unknown realization_kind "
                f"{realization_kind!r}"
            )
            continue

        if realization_kind == "git":
            if not binds_to:
                errors.append(
                    f"surface {surface_id}: realization_kind=git requires "
                    "binds_to_surface_id"
                )
                continue
            target = surface_by_id.get(binds_to)
            if target is None:
                errors.append(
                    f"surface {surface_id}: binds_to_surface_id {binds_to!r} "
                    "does not reference an existing surface"
                )
                continue
            target_object_id = surface.get("object_id")
            if target.get("object_id") != target_object_id:
                errors.append(
                    f"surface {surface_id}: binding target {binds_to} belongs to "
                    f"object {target.get('object_id')}, not {target_object_id}"
                )
            if target.get("kind") != "github":
                errors.append(
                    f"surface {surface_id}: binding target {binds_to} must be "
                    f"kind=github, not {target.get('kind')!r}"
                )
            if target.get("resource_type") != "repository":
                errors.append(
                    f"surface {surface_id}: binding target {binds_to} must be "
                    "resource_type=repository"
                )
        elif binds_to is not None:
            errors.append(
                f"surface {surface_id}: realization_kind={realization_kind} "
                "must not declare binds_to_surface_id"
            )

    return errors


def require_valid_surface_realizations(
    objects: Iterable[dict[str, Any]],
    surfaces: Iterable[dict[str, Any]],
) -> None:
    errors = validate_surface_realizations(objects, surfaces)
    if errors:
        raise ValueError("surface realization validation failed: " + "; ".join(errors))
