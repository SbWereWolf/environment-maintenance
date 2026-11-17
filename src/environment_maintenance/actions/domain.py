"""Rules for declared command chains and interpreted execution outcomes."""

from copy import deepcopy
from typing import Any


def validate_command(command: dict[str, Any], index: int) -> None:
    """Apply the same required-field rules before and after substitution."""
    context = f"commands[{index}]"
    if not isinstance(command, dict):
        raise ValueError(f"{context} must be an object")
    argv = command.get("argv")
    if (
        not isinstance(argv, list) or not argv
        or any(not isinstance(part, str) for part in argv) or not argv[0]
    ):
        raise ValueError(f"{context}.argv must be a string array with a nonempty executable")
    cwd = command.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        raise ValueError(f"{context}.cwd must be a nonempty string")
    env = command.get("env")
    if not isinstance(env, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in env.items()
    ):
        raise ValueError(f"{context}.env must be a string map")
    interpreter = command.get("interpreter")
    if not isinstance(interpreter, dict):
        raise ValueError(f"{context}.interpreter must be an object")
    name = interpreter.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{context}.interpreter.name must be a nonempty string")
    if not isinstance(interpreter.get("options"), dict):
        raise ValueError(f"{context}.interpreter.options must be an object")


def declared_commands(action: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(action, dict):
        raise ValueError("action must be an object")
    commands = action.get("commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("action.commands must be a nonempty array")
    for index, command in enumerate(commands):
        validate_command(command, index)
    return deepcopy(commands)


def interpreted_result(answer: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(answer, dict):
        raise ValueError("interpreter result must be an object")
    for field in ("success", "value", "error"):
        if field not in answer:
            raise ValueError(f"interpreter result requires {field}")
    if type(answer["success"]) is not bool:
        raise ValueError("interpreter result.success must be bool")
    if answer["success"]:
        if answer["error"] is not None:
            raise ValueError("successful interpreter result.error must be None")
    elif not isinstance(answer["error"], str) or not answer["error"]:
        raise ValueError("failed interpreter result.error must be a nonempty string")
    return deepcopy(answer)


def chain_options(command: dict[str, Any], index: int) -> dict[str, Any]:
    """Validate only the additional policy of the new chain contract."""
    mode = command.get("mode", "sync")
    enabled = command.get("enabled", True)
    policy = command.get("on_error", "stop")
    if mode not in ("sync", "async"):
        raise ValueError(f"commands[{index}].mode must be sync or async")
    if type(enabled) is not bool:
        raise ValueError(f"commands[{index}].enabled must be bool")
    if policy not in ("continue", "stop"):
        raise ValueError(f"commands[{index}].on_error must be continue or stop")
    return dict(mode=mode, enabled=enabled, on_error=policy)
