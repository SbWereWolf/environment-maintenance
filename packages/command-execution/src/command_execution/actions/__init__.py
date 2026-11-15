"""Public action operations composed with the external process adapter."""

from pathlib import Path
from typing import Any

from .application import ActionExecutor, ResultInterpreter, prepare_action


def plan_action(
    action: dict[str, Any], parameters: dict[str, Any], *,
    base_dir: str | Path, interpreters: dict[str, ResultInterpreter],
) -> dict[str, Any]:
    """Prepare every declared command without running processes or interpreters."""
    return prepare_action(action, parameters, base_dir=base_dir, interpreters=interpreters)


def execute_action(
    action: dict[str, Any], parameters: dict[str, Any], *,
    base_dir: str | Path, interpreters: dict[str, ResultInterpreter],
) -> dict[str, Any]:
    """Run the prepared chain and preserve each attempted command's full result."""
    from .process import run_command

    return ActionExecutor(run_command).execute(
        action, parameters, base_dir=base_dir, interpreters=interpreters
    )
