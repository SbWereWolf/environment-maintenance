"""The six configured maintenance and named application command routes."""
import argparse
from pathlib import Path
import sys

from . import __version__
from .configuration.json_file import read_json
from .invocation import parse_requirement_selection, resolve_invocation
from .output import OUTPUT_FORMATS
from .running.domain import validate_environment_title


_ACTIONS = {'run': ('list',), 'stop': ('list', 'all')}


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise argparse.ArgumentError(None, message)


def _parser(warnings):
    def output_value(value):
        if value not in OUTPUT_FORMATS:
            warnings.append(f'недопустимое значение --output: {value!r}; используется one-line')
            return 'one-line'
        return value

    def output_option(target):
        target.add_argument('--output', nargs='?', const='pretty', default=argparse.SUPPRESS,
            type=output_value, metavar='FORMAT',
            help='Формат JSON: pretty или one-line; без значения pretty, без опции one-line')

    parser = _ArgumentParser(description='Обслуживание окружения и управление приложениями')
    version = dict(action='version', version=f'environment-maintenance {__version__}')
    parser.add_argument('--version', **version)
    output_option(parser)
    parser.set_defaults(output='one-line', action=None, config=None, parameters=None,
                        base_dir=None, requirements=None, env=None, app=None)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('infra', 'deps', 'adjust', 'check', 'run', 'stop'):
        command = commands.add_parser(name)
        command.add_argument('--version', **version)
        output_option(command)
        if name in _ACTIONS:
            command.add_argument('action', nargs='?', default=argparse.SUPPRESS,
                                 help=' / '.join(_ACTIONS[name]))
        if name != 'stop':
            command.add_argument('--config', type=Path, default=argparse.SUPPRESS)
            command.add_argument('--parameters', type=Path, default=argparse.SUPPRESS)
            command.add_argument('--base-dir', type=Path, default=argparse.SUPPRESS)
        if name in ('infra', 'deps', 'adjust'):
            command.add_argument('--requirements', default=argparse.SUPPRESS)
        if name in ('run', 'stop'):
            command.add_argument('--env', default=argparse.SUPPRESS)
            command.add_argument('--app', default=argparse.SUPPRESS)
    return parser


def _validate_args(args):
    if args.env is not None:
        try:
            validate_environment_title(args.env)
        except ValueError as exc:
            raise ValueError(f'--env {args.env!r}: {exc}') from exc
    if args.command == 'stop' and args.app is not None and args.env is None:
        raise ValueError('stop --app requires --env')
    if args.command in ('infra', 'deps', 'adjust') and args.requirements is not None:
        try:
            parse_requirement_selection(args.requirements)
        except ValueError as exc:
            raise ValueError(f'{args.command} {exc}') from exc


def _parse_args(argv):
    warnings = []
    parser = _parser(warnings)
    args = None
    try:
        args, unknown = parser.parse_known_args(argv)
        if args.command in _ACTIONS and args.action is not None and args.action not in _ACTIONS[args.command]:
            unknown.append(args.action)
            args.action = None
        if unknown:
            warnings.append('неизвестные аргументы пропущены: ' + ' '.join(unknown))
        _validate_args(args)
    except (argparse.ArgumentError, ValueError) as exc:
        warnings.append(str(exc))
        args = None
    finally:
        for warning in warnings:
            print('Предупреждение: ' + warning, file=sys.stderr)
    return args, parser


def main(argv=None):
    args, parser = _parse_args(sys.argv[1:] if argv is None else argv)
    if args is None:
        return 2
    try:
        if args.command == 'run':
            from .running.cli import run_launch
            return run_launch(args, action=args.action)
        if args.command == 'stop':
            from .running.cli import run_stop
            return run_stop(args, action=args.action)
        invocation = resolve_invocation(args.command, args.config, args.parameters, args.base_dir,
            getattr(args, 'requirements', None), instance_root=Path.cwd(), read_document=read_json)
    except ValueError as exc:
        argparse.ArgumentParser.error(parser, str(exc))
    if args.command == 'check':
        from .checking.cli import run_checks
        return run_checks(invocation.config_path, invocation.parameters_path, invocation.base_dir,
                          output=args.output)
    from .preparation.cli import run_preparation
    return run_preparation(args.command, invocation.config_path, invocation.parameters_path,
                           invocation.base_dir, invocation.raw_selection, output=args.output)
