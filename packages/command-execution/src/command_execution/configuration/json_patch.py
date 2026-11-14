"""Adapt the supported change operations to the standard JSON Patch engine."""

from copy import deepcopy
from typing import Any

from jsonpatch import JsonPatch, JsonPatchException
from jsonpointer import JsonPointerException


def apply_changes(
    requirement: dict[str, Any], changes: list[dict[str, Any]]
) -> dict[str, Any]:
    if not isinstance(changes, list):
        raise ValueError("changes must be an array")
    result = deepcopy(requirement)
    for position, change in enumerate(changes):
        if not isinstance(change, dict):
            raise ValueError(f"changes[{position}] must be an object")
        operation = change.get("op")
        if not isinstance(operation, str) or operation not in {
            "add",
            "replace",
            "remove",
        }:
            raise ValueError(f"changes[{position}].op is unsupported: {operation}")
        path = change.get("path")
        if not isinstance(path, str):
            raise ValueError(f"changes[{position}].path must be a string")
        try:
            result = JsonPatch([deepcopy(change)]).apply(result, in_place=True)
        except (JsonPatchException, JsonPointerException) as exc:
            raise ValueError(
                f"changes[{position}] {operation} {path!r}: {exc}"
            ) from exc
    return result
