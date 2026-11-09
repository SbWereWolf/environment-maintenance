"""Check actual serviced-application files and selected queue settings."""
import argparse
import json
from pathlib import Path
import sys

from jsonpointer import JsonPointer, JsonPointerException

from environment_maintenance.configuration.json_file import read_json
from environment_maintenance.configuration import read_requirements


def check_file_presence(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"Resource file is absent: {path}")
    return dict(status='succeeded', check='presence')


def check_file_availability(path: Path) -> dict:
    read_json(path)
    return dict(status='succeeded', check='availability')


def _selected_value(requirement: dict, pointer: JsonPointer) -> str:
    try:
        value = pointer.resolve(requirement)
    except JsonPointerException as exc:
        raise ValueError(f"{requirement['id']} {pointer.path}: {exc}") from exc
    if not isinstance(value, str) or not value:
        raise ValueError(f"{requirement['id']} {pointer.path}: expected a nonempty string")
    return value


def check_consistency(config_path: Path, operation: str, writer: str,
                      reader: str, variable: str) -> dict:
    pointer = JsonPointer.from_parts(['commands', '0', 'env', variable])
    selected = read_requirements(config_path, operation, [writer, reader])
    values = [_selected_value(requirement, pointer) for requirement in selected]
    if values[0] != values[1]:
        raise ValueError(f"{writer}/{reader} {variable}: selected queue settings differ")
    return dict(status='succeeded', check='consistency', writer=writer,
                reader=reader, variable=variable, value=values[0])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Проверка ресурсов и согласованности настроек')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('presence', 'availability'):
        command = commands.add_parser(name)
        command.add_argument('--path', type=Path, required=True)
    consistency = commands.add_parser('consistency')
    consistency.add_argument('--config', type=Path, required=True)
    consistency.add_argument('--operation', required=True)
    consistency.add_argument('--writer', required=True)
    consistency.add_argument('--reader', required=True)
    consistency.add_argument('--queue-variable', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'presence':
            result = check_file_presence(args.path)
        elif args.command == 'availability':
            result = check_file_availability(args.path)
        else:
            result = check_consistency(args.config, args.operation, args.writer,
                                       args.reader, args.queue_variable)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
