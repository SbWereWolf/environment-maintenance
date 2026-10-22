"""Align two serviced-application queue settings through the public configuration API."""
import argparse
import json
from pathlib import Path
import sys

from jsonpointer import JsonPointer, JsonPointerException

from environment_maintenance.configuration import read_requirements, update_requirement


def queue_value(requirement: dict, pointer: JsonPointer):
    """Read one selected queue setting and retain its owning identifier in errors."""
    try:
        return pointer.resolve(requirement)
    except JsonPointerException as exc:
        raise ValueError(f"{requirement['id']} {pointer.path}: {exc}") from exc


def align_queue(
    config_path: Path,
    operation: str,
    writer: str,
    reader: str,
    variable: str,
    queue: str,
) -> dict:
    """Validate both positions, update only those settings and confirm saved values."""
    pointer = JsonPointer.from_parts(['commands', '0', 'env', variable])
    identifiers = [writer, reader]
    selected = read_requirements(config_path, operation, identifiers)
    for requirement in selected:
        queue_value(requirement, pointer)
    for identifier in identifiers:
        update_requirement(config_path, operation, identifier,
                           [dict(op='replace', path=pointer.path, value=queue)])
    for requirement in read_requirements(config_path, operation, identifiers):
        if queue_value(requirement, pointer) != queue:
            raise ValueError(f"{requirement['id']} {pointer.path}: queue alignment was not confirmed")
    return dict(status='succeeded', writer=writer, reader=reader,
                variable=variable, queue=queue)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Согласование настроек очереди приложений')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--operation', required=True)
    parser.add_argument('--writer', required=True)
    parser.add_argument('--reader', required=True)
    parser.add_argument('--queue-variable', required=True)
    parser.add_argument('--queue', required=True)
    args = parser.parse_args(argv)
    try:
        result = align_queue(args.config, args.operation, args.writer,
                             args.reader, args.queue_variable, args.queue)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
