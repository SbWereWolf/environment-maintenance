"""Public read operations composed with the existing JSON document owner."""

from pathlib import Path
from typing import Any

from ..catalogue import read_json
from .application import ConfigurationReader


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
