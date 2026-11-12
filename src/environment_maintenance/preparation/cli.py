"""Explicit preparation CLI inputs, composition and result delivery."""
from pathlib import Path
import shlex
import sys

from ..configuration.json_file import read_json
from ..actions import execute_action
from ..actions.transport import load_interpreters, plan_for_json_transport, validate_json_data
from ..configuration.execution import read_for_execution
from ..invocation import parse_requirement_selection
from ..output import format_json
from .application import prepare_resources
from .presentation import encode_result


def run_preparation(
    operation: str,
    config_path: Path,
    parameters_path: Path,
    base_dir: Path,
    raw_selection: str,
    *,
    output: str = 'one-line',
) -> int:
    try:
        selection = parse_requirement_selection(raw_selection)
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
                                   reader=lambda config, op, selected: read_for_execution(config, op, selected,
                                       lambda message: print(message, file=sys.stderr)),
                                   planner=plan_for_json_transport,
                                   executor=execute_action, network_adjuster=network_adjuster)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(format_json(encode_result(result), output))
    return 0 if result['status'] == 'succeeded' else 1
