"""Public preparation use case composed with the accepted external adapters."""
from pathlib import Path
from typing import Any

from ..actions import execute_action, plan_action
from ..actions.application import ResultInterpreter
from ..configuration import read_requirements
from .application import prepare_resources as prepare_use_case


def prepare_resources(
    config_path: str | Path,
    operation: str,
    selection: list[str] | str,
    parameters: dict[str, Any],
    *,
    base_dir: str | Path,
    interpreters: dict[str, ResultInterpreter],
) -> dict[str, Any]:
    return prepare_use_case(
        config_path, operation, selection, parameters,
        base_dir=base_dir, interpreters=interpreters,
        reader=read_requirements, planner=plan_action, executor=execute_action,
    )
