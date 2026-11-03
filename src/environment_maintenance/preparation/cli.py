"""Explicit preparation CLI inputs, composition and result delivery."""
import json
from pathlib import Path
import shlex
import sys

from ..catalogue import read_json
from ..actions import execute_action
from ..actions.transport import load_interpreters, plan_for_json_transport, validate_json_data
from ..configuration import read_requirements
from .application import prepare_resources
from .presentation import encode_result


def _selection(raw: str) -> list[str] | str:
    if raw == 'all':
        return raw
    try:
        selected = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"--requirements selection: {exc}") from exc
    if not isinstance(selected, list) or any(not isinstance(item, str) for item in selected):
        raise ValueError("--requirements selection must be an identifier array or all")
    return selected


def run_preparation(
    operation: str,
    config_path: Path,
    parameters_path: Path,
    base_dir: Path,
    raw_selection: str,
) -> int:
    try:
        selection = _selection(raw_selection)
        parameters = read_json(parameters_path)
        interpreters = load_interpreters(read_json(config_path))
        network_adjuster = None
        if operation == 'adjust':
            from ..network import adjust_network

            retry_command = shlex.join([
                sys.executable, '-m', 'environment_maintenance', 'adjust',
                '--config', str(config_path), '--parameters', str(parameters_path),
                '--base-dir', str(base_dir), '--requirements', raw_selection,
            ])

            def network_adjuster(requirements, values):
                validate_json_data(values)
                return adjust_network(requirements, values, parameters_path=parameters_path,
                                      retry_command=retry_command)

        result = prepare_resources(config_path, operation, selection, parameters,
                                   base_dir=base_dir, interpreters=interpreters,
                                   reader=read_requirements, planner=plan_for_json_transport,
                                   executor=execute_action, network_adjuster=network_adjuster)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(encode_result(result), ensure_ascii=True, separators=(',', ':'), allow_nan=False))
    return 0 if result['status'] == 'succeeded' else 1
