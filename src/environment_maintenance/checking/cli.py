"""Compose explicit checking CLI inputs and ordinary JSON delivery."""
from pathlib import Path
import sys

from ..actions import execute_action
from ..actions.transport import load_interpreters, plan_for_json_transport
from ..configuration.json_file import read_json
from ..configuration import read_requirements
from ..output import format_json
from .application import check_resources
from .presentation import encode_result


def run_checks(config_path: Path, parameters_path: Path, base_dir: Path, *,
               output: str = 'one-line') -> int:
    try:
        parameters = read_json(parameters_path)
        interpreters = load_interpreters(read_json(config_path))
        result = check_resources(config_path, parameters, base_dir=base_dir,
            interpreters=interpreters, reader=read_requirements,
            planner=plan_for_json_transport, executor=execute_action)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(format_json(encode_result(result), output))
    return 0 if result['status'] == 'succeeded' else 1
