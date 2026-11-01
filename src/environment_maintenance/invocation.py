"""Resolve persistent invocation inputs at the CLI delivery boundary."""

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ResolvedInvocation:
    config_path: Path
    parameters_path: Path
    base_dir: Path
    raw_selection: str | None


def _configured_path(value: Any, main: Path, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{main}: invocation.{field} must be a nonempty path")
    path = Path(value)
    return path if path.is_absolute() else main.parent / path


def _configured_selection(invocation: dict, main: Path, operation: str) -> str:
    selections = invocation.get('requirements')
    if not isinstance(selections, dict) or operation not in selections:
        raise ValueError(f"{main}: invocation.requirements.{operation} is required")
    selection = selections[operation]
    if selection == 'all':
        return selection
    if not isinstance(selection, list) or any(not isinstance(item, str) for item in selection):
        raise ValueError(
            f"{main}: invocation.requirements.{operation} must be an identifier array or all"
        )
    return json.dumps(selection)


def resolve_invocation(
    operation: str,
    config_path: Path | None,
    parameters_path: Path | None,
    base_dir: Path | None,
    raw_selection: str | None,
    *,
    instance_root: Path,
    read_document: Callable[[Path], dict[str, Any]],
) -> ResolvedInvocation:
    main = (config_path if config_path is not None else instance_root / 'start-app.json').absolute()
    needs_selection = operation != 'check' and raw_selection is None
    if parameters_path is None or base_dir is None or needs_selection:
        invocation = read_document(main).get('invocation')
        if not isinstance(invocation, dict):
            raise ValueError(f"{main}: invocation must be an object")
        if parameters_path is None:
            parameters_path = _configured_path(invocation.get('parameters'), main, 'parameters')
        if base_dir is None:
            base_dir = _configured_path(invocation.get('base_dir'), main, 'base_dir')
        if needs_selection:
            raw_selection = _configured_selection(invocation, main, operation)
    return ResolvedInvocation(main, parameters_path.absolute(), base_dir, raw_selection)
