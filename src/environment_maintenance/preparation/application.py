"""Prepare every selected chain, then retain only actually attempted work."""
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..actions.application import ResultInterpreter


RequirementsReader = Callable[[str | Path, str, list[str] | str], list[dict[str, Any]]]
ActionOperation = Callable[..., dict[str, Any]]


def prepare_resources(
    config_path: str | Path,
    operation: str,
    selection: list[str] | str,
    parameters: dict[str, Any],
    *,
    base_dir: str | Path,
    interpreters: dict[str, ResultInterpreter],
    reader: RequirementsReader,
    planner: ActionOperation,
    executor: ActionOperation,
) -> dict[str, Any]:
    try:
        requirements = reader(config_path, operation, selection)
    except ValueError as exc:
        raise ValueError(f"{operation} configuration: {exc}") from exc

    for requirement in requirements:
        try:
            planner(requirement, parameters, base_dir=base_dir, interpreters=interpreters)
        except ValueError as exc:
            raise ValueError(f"{operation} requirement {requirement['id']}: {exc}") from exc

    records = []
    for requirement in requirements:
        result = executor(requirement, parameters, base_dir=base_dir, interpreters=interpreters)
        records.append(dict(id=requirement['id'], result=result))
        if result['status'] == 'failed':
            return dict(operation=operation, status='failed', requirements=records,
                        error=f"{operation} requirement {requirement['id']}: {result['error']}")
    return dict(operation=operation, status='succeeded', requirements=records, error=None)
