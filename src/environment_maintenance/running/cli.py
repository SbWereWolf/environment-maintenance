"""Compose named application operations without losing submitted group facts."""
import json
from pathlib import Path
import sys
from uuid import uuid4

from ..actions import execute_action
from ..actions.transport import load_interpreters, plan_for_json_transport
from ..configuration import list_requirement_ids
from ..configuration.execution import read_for_execution
from ..configuration.json_file import read_json
from ..invocation import resolve_invocation
from ..registry.files import FileRegistry
from .application import RunApplications, StopApplications
from .domain import validate_environment_title
from .presentation import encode_run_result
from .process_groups import terminate_group


def _print(result):
    print(json.dumps(result, ensure_ascii=True, separators=(',', ':'), allow_nan=False))
    return 0 if result['status'] == 'succeeded' else 1


def run_launch(args, *, action=None):
    registry = FileRegistry()
    use_case = RunApplications(registry, plan_for_json_transport, execute_action)
    if action == 'list':
        if args.env is not None:
            validate_environment_title(args.env)
        config = (args.config or Path.cwd() / 'start-app.json').absolute()
        return _print(use_case.list_available(list_requirement_ids(config, 'run'), args.env))
    title = validate_environment_title(args.env if args.env is not None else str(uuid4()))
    result = {'operation': 'run', 'status': 'succeeded', 'environment': title,
              'file': str(registry.path_for(title)), 'file_exists': False,
              'planned': 0, 'received_pgids': 0, 'applications': [], 'errors': []}
    code = None
    try:
        invocation = resolve_invocation('run', args.config, args.parameters, args.base_dir,
            None, instance_root=Path.cwd(), read_document=read_json)
        rows = read_for_execution(invocation.config_path, 'run',
            'all' if args.app is None else [args.app], lambda message: print(message, file=sys.stderr))
        result['planned'] = len(rows)
        parameters = read_json(invocation.parameters_path)
        interpreters = load_interpreters(read_json(invocation.config_path))
        use_case.run(rows, parameters, invocation.base_dir, interpreters, title, args.app, result)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        result['errors'].append({'environment': title, 'error': str(exc)})
        code = 2
    except OSError as exc:
        result['errors'].append({'environment': title, 'error': str(exc)})
    result['file_exists'] = Path(result['file']).exists()
    if result['errors']:
        result['status'] = 'failed'
    actual = _print(encode_run_result(result))
    return actual if code is None else code


def run_stop(args, *, action=None):
    if args.env is not None:
        validate_environment_title(args.env)
    use_case = StopApplications(FileRegistry(), terminate_group)
    if action == 'list' or (action is None and args.env is None and args.app is None):
        return _print(use_case.list_environments(args.env))
    return _print(use_case.stop(args.env, args.app))
