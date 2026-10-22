"""Public configuration operations composed with their external adapters."""

from pathlib import Path
from typing import Any

from ..catalogue import read_json
from .application import ConfigurationReader, ConfigurationWriter


def list_requirement_ids(config_path: str | Path, operation: str) -> list[str]:
    """Return identifiers from the explicitly selected operation configuration."""
    return ConfigurationReader(read_json).list_ids(config_path, operation)


def read_requirements(
    config_path: str | Path,
    operation: str,
    selection: list[str] | str,
) -> list[dict[str, Any]]:
    """Return complete objects for an identifier array or the literal all mode."""
    return ConfigurationReader(read_json).read(config_path, operation, selection)


def _writer() -> ConfigurationWriter:
    from .json_file import write_json
    from .json_patch import apply_changes

    return ConfigurationWriter(read_json, write_json, apply_changes)


def add_requirement(
    config_path: str | Path, operation: str, requirement: dict[str, Any]
) -> None:
    """Append one complete requirement to the selected configuration."""
    _writer().add(config_path, operation, requirement)


def update_requirement(
    config_path: str | Path,
    operation: str,
    identifier: str,
    changes: list[dict[str, Any]],
) -> None:
    """Apply the supported standard patch operations to one selected requirement."""
    _writer().update(config_path, operation, identifier, changes)


def delete_requirement(
    config_path: str | Path, operation: str, identifier: str
) -> None:
    """Remove one selected requirement and preserve the remaining document."""
    _writer().delete(config_path, operation, identifier)


def clear_requirements(config_path: str | Path, operation: str) -> None:
    """Explicitly empty the selected requirement list and preserve its metadata."""
    _writer().clear(config_path, operation)
