"""Public catalog/v2 command line for the independent distribution."""

import argparse
import json
from pathlib import Path
import sys

from .catalogue import ContractError, load_catalog, read_json
from .engine import execute


def main(argv=None):
    parser = argparse.ArgumentParser(description="Проверка и обслуживание окружения")
    parser.add_argument("command", choices=["check", "run"])
    parser.add_argument("--catalog-dir", required=True, type=Path)
    parser.add_argument("--values", action="append", default=[], type=Path)
    parser.add_argument("--set", dest="overrides", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
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
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return result["exit_code"]
