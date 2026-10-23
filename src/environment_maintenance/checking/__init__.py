"""Public resource checking composed with the existing configuration and action owners."""
from pathlib import Path
from typing import Any

from ..actions import execute_action, plan_action
from ..actions.application import ResultInterpreter
from ..configuration import read_requirements
from .application import check_resources as _check_resources


def check_resources(
    config_path: str | Path, parameters: dict[str, Any], *,
    base_dir: str | Path, interpreters: dict[str, ResultInterpreter],
) -> dict[str, Any]:
    """Check declared conditions without installing or adjusting resources."""
    return _check_resources(config_path, parameters, base_dir=base_dir,
        interpreters=interpreters, reader=read_requirements,
        planner=plan_action, executor=execute_action)
