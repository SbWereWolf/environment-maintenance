"""Explicit catalog maintenance and resource-preparation command routes."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .catalogue import ContractError, load_catalog, read_json
from .engine import execute


def main(argv=None):
    parser = argparse.ArgumentParser(description="Проверка и обслуживание окружения")
    parser.add_argument(
        "--version", action="version", version=f"environment-maintenance {__version__}"
    )
    parser.add_argument("command", choices=["check", "run", "infra", "deps", "adjust"])
    parser.add_argument("--catalog-dir", type=Path)
    parser.add_argument("--values", action="append", default=[], type=Path)
    parser.add_argument("--set", dest="overrides", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--parameters", type=Path)
    parser.add_argument("--base-dir", type=Path)
    parser.add_argument("--requirements")
    args = parser.parse_args(argv)
    preparation_arguments = (
        ('config', '--config'),
        ('parameters', '--parameters'),
        ('base_dir', '--base-dir'),
        ('requirements', '--requirements'),
    )
    if args.command in ('infra', 'deps', 'adjust'):
        for name, flag in (('catalog_dir', '--catalog-dir'), ('values', '--values'),
                           ('overrides', '--set'), ('dry_run', '--dry-run')):
            if getattr(args, name):
                parser.error(f"{flag} is not supported for {args.command}")
        for name, flag in preparation_arguments:
            if getattr(args, name) is None:
                parser.error(f"{flag} is required for {args.command}")
        from .preparation.cli import run_preparation
        return run_preparation(args.command, args.config, args.parameters,
                               args.base_dir, args.requirements)
    for name, flag in preparation_arguments:
        if getattr(args, name) is not None:
            parser.error(f"{flag} is only supported for infra/deps/adjust")
    if args.catalog_dir is None:
        parser.error("--catalog-dir is required for check/run")
    try:
        values = {}
        for path in args.values:
            values.update(read_json(path))
        result = execute(
            load_catalog(args.catalog_dir),
            args.command,
            values=values,
            overrides=args.overrides,
            dry_run=args.dry_run,
        )
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return result["exit_code"]
