"""Compose prepared commands without conflating chain data and interpretation."""
from copy import deepcopy
import json
from pathlib import Path
from threading import Thread
from typing import Any, Callable

from .application import ActionExecutor, ProcessRunner, ResultInterpreter, prepare_action
from .domain import chain_options


def _encode(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')


def prepare_chain(action, parameters, *, input_data, base_dir, interpreters):
    _encode(input_data)
    snapshot = deepcopy(action)
    plan = prepare_action(snapshot, parameters, base_dir=base_dir, interpreters=interpreters)
    for index, (prepared, declared) in enumerate(zip(plan['commands'], snapshot['commands'], strict=True)):
        prepared.update(chain_options(declared, index))
    return plan


def plan_chain(
    action: dict[str, Any], parameters: dict[str, Any], *, input_data: Any,
    base_dir: str | Path, interpreters: dict[str, ResultInterpreter],
) -> dict[str, Any]:
    """Prepare the complete ordered chain without processes or interpreters."""
    return prepare_chain(action, parameters, input_data=input_data,
                         base_dir=base_dir, interpreters=interpreters)


def execute_chain(
    action: dict[str, Any], parameters: dict[str, Any], *, input_data: Any,
    base_dir: str | Path, interpreters: dict[str, ResultInterpreter],
    run_command: ProcessRunner | None = None,
    on_result: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Return synchronous state; background completion updates only its record."""
    if run_command is None:
        from .process import run_command
    if not callable(run_command) or (on_result is not None and not callable(on_result)):
        raise ValueError('run_command and on_result must be callable')
    plan = prepare_chain(action, parameters, input_data=input_data,
                         base_dir=base_dir, interpreters=interpreters)
    executor = ActionExecutor(run_command)
    current = deepcopy(input_data)
    result = dict(status='succeeded', data=deepcopy(current), commands=[], error=None)

    def complete(command, index, snapshot):
        row = executor.execute_command(
            command, interpreters[command['interpreter']['name']], index,
            stdin=_encode(snapshot), capture_exception=True,
        )
        row.update(index=index, input_data=deepcopy(snapshot), state='completed')
        answer = row['interpretation']
        if answer is not None and 'next_input' in answer:
            try:
                _encode(answer['next_input'])
            except (TypeError, ValueError) as exc:
                row.update(error=f'commands[{index}] next_input: {exc}',
                           exception={'type': type(exc).__name__, 'message': str(exc)})
        return row

    def notify(row):
        if on_result is not None:
            on_result(deepcopy(row))

    def background(command, index, snapshot, row):
        row.update(complete(command, index, snapshot))
        notify(row)

    for index, command in enumerate(plan['commands']):
        if not command['enabled']:
            continue
        snapshot = deepcopy(current)
        if command['mode'] == 'async':
            row = dict(index=index, input_data=deepcopy(snapshot), state='running',
                       invocation={key: deepcopy(command[key]) for key in ('argv', 'cwd', 'env')},
                       interpreter=deepcopy(command['interpreter']), exit_code=None,
                       stdout=None, stderr=None, interpretation=None, error=None, exception=None)
            result['commands'].append(row)
            try:
                Thread(target=background, args=(command, index, snapshot, row), daemon=False).start()
            except Exception as exc:
                row.update(state='completed', error=f'commands[{index}] dispatch: {exc}',
                           exception={'type': type(exc).__name__, 'message': str(exc)})
                notify(row)
            continue
        row = complete(command, index, snapshot)
        result['commands'].append(row)
        answer = row['interpretation']
        if row['exception'] is None and answer is not None and 'next_input' in answer:
            current = deepcopy(answer['next_input'])
        result['data'] = deepcopy(current)
        if row['error'] is not None:
            result['status'] = 'failed'
            if result['error'] is None:
                result['error'] = row['error']
        notify(row)
        if row['error'] is not None and command['on_error'] == 'stop':
            break
    return result
