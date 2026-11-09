"""The six configured maintenance and named application command routes."""
import argparse
from pathlib import Path
import sys

from . import __version__
from .configuration.json_file import read_json
from .invocation import resolve_invocation


def _parser():
    parser = argparse.ArgumentParser(description='Обслуживание окружения и управление приложениями')
    version = dict(action='version', version=f'environment-maintenance {__version__}')
    parser.add_argument('--version', **version)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('infra', 'deps', 'adjust', 'check', 'run', 'stop'):
        command = commands.add_parser(name)
        command.add_argument('--version', **version)
        if name != 'stop':
            command.add_argument('--config', type=Path)
            command.add_argument('--parameters', type=Path)
            command.add_argument('--base-dir', type=Path)
        if name in ('infra', 'deps', 'adjust'):
            command.add_argument('--requirements')
        if name in ('run', 'stop'):
            command.add_argument('--env')
            command.add_argument('--app')
    return parser


def _action_arguments(argv):
    action = None
    if len(argv) > 1 and ((argv[0] == 'run' and argv[1] == 'list') or
                         (argv[0] == 'stop' and argv[1] in ('list', 'all'))):
        action = argv[1]
        argv = [argv[0], *argv[2:]]
    return action, argv


def main(argv=None):
    action, arguments = _action_arguments(list(sys.argv[1:] if argv is None else argv))
    parser = _parser()
    args, unknown = parser.parse_known_args(arguments)
    if unknown:
        print('Предупреждение: неизвестные аргументы пропущены: ' + ' '.join(unknown), file=sys.stderr)
    if args.command == 'stop' and args.app is not None and args.env is None:
        parser.error('stop --app requires --env')
    try:
        if args.command == 'run':
            from .running.cli import run_launch
            return run_launch(args, action=action)
        if args.command == 'stop':
            from .running.cli import run_stop
            return run_stop(args, action=action)
        invocation = resolve_invocation(args.command, args.config, args.parameters, args.base_dir,
            getattr(args, 'requirements', None), instance_root=Path.cwd(), read_document=read_json)
    except ValueError as exc:
        parser.error(str(exc))
    if args.command == 'check':
        from .checking.cli import run_checks
        return run_checks(invocation.config_path, invocation.parameters_path, invocation.base_dir)
    from .preparation.cli import run_preparation
    return run_preparation(args.command, invocation.config_path, invocation.parameters_path,
                           invocation.base_dir, invocation.raw_selection)
