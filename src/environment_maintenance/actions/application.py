"""Prepare actions once and execute their ordered commands through narrow ports."""

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from string import Template
from typing import Any, Protocol

from .domain import declared_commands, interpreted_result


class ResultInterpreter(Protocol):
    def interpret(self, result: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
        ...


ProcessRunner = Callable[[dict[str, Any]], dict[str, Any]]


def _prepare_command(
    command: dict[str, Any], parameters: dict[str, Any], base_dir: Path, index: int
) -> dict[str, Any]:
    try:
        argv = [Template(part).substitute(parameters) for part in command["argv"]]
        cwd = Template(command["cwd"]).substitute(parameters)
        env = {
            key: Template(value).substitute(parameters)
            for key, value in command["env"].items()
        }
    except (KeyError, ValueError) as exc:
        raise ValueError(f"commands[{index}] template: {exc}") from exc
    directory = Path(cwd)
    if not directory.is_absolute():
        directory = base_dir / directory
    return dict(
        argv=argv, cwd=str(directory), env=env,
        interpreter=deepcopy(command["interpreter"]),
    )


def prepare_action(
    action: dict[str, Any], parameters: dict[str, Any], *,
    base_dir: str | Path, interpreters: dict[str, ResultInterpreter],
) -> dict[str, Any]:
    commands = declared_commands(action)
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be a scalar map")
    for name, value in parameters.items():
        if not isinstance(name, str) or not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"parameters[{name}]: expected a named scalar")
    if (
        not isinstance(base_dir, (str, Path)) or not str(base_dir)
        or not Path(base_dir).is_absolute()
    ):
        raise ValueError("base_dir must be an absolute path")
    if not isinstance(interpreters, dict):
        raise ValueError("interpreters must be a map")
    prepared = []
    for index, command in enumerate(commands):
        name = command["interpreter"]["name"]
        if name not in interpreters or not callable(
            getattr(interpreters[name], "interpret", None)
        ):
            raise ValueError(f"commands[{index}].interpreter {name}: callable interpret is required")
        prepared.append(_prepare_command(command, parameters, Path(base_dir), index))
    return dict(commands=prepared)


class ActionExecutor:
    def __init__(self, run_command: ProcessRunner):
        self._run_command = run_command

    def execute(
        self, action: dict[str, Any], parameters: dict[str, Any], *,
        base_dir: str | Path, interpreters: dict[str, ResultInterpreter],
    ) -> dict[str, Any]:
        plan = prepare_action(action, parameters, base_dir=base_dir, interpreters=interpreters)
        records = []
        error = None
        for index, command in enumerate(plan["commands"]):
            record = self._execute_command(
                command, interpreters[command["interpreter"]["name"]], index
            )
            records.append(record)
            error = record["error"]
            if error is not None:
                break
        return dict(
            status="succeeded" if error is None else "failed",
            commands=records, error=error,
        )

    def _execute_command(
        self, command: dict[str, Any], interpreter: ResultInterpreter, index: int
    ) -> dict[str, Any]:
        invocation = {field: deepcopy(command[field]) for field in ("argv", "cwd", "env")}
        record = dict(
            invocation=invocation, interpreter=deepcopy(command["interpreter"]),
            exit_code=None, stdout=b"", stderr=b"", interpretation=None, error=None,
        )
        try:
            raw = self._run_command(deepcopy(invocation))
        except (OSError, ValueError) as exc:
            record["error"] = f"commands[{index}] launch argv/cwd: {exc}"
            return record
        record.update(raw)
        interpretation, error = self._interpret(raw, command["interpreter"], interpreter)
        record.update(interpretation=interpretation, error=error)
        return record

    def _interpret(
        self, raw: dict[str, Any], configuration: dict[str, Any], interpreter: ResultInterpreter
    ) -> tuple[dict[str, Any] | None, str | None]:
        name = configuration["name"]
        try:
            answer = interpreter.interpret(
                deepcopy(raw), deepcopy(configuration["options"])
            )
            interpretation = interpreted_result(answer)
        except Exception as exc:
            return None, f"interpreter {name}: {exc}"
        error = (
            None if interpretation["success"]
            else f"interpreter {name}: {interpretation['error']}"
        )
        return interpretation, error
