"""Explicit preparation CLI inputs, composition and result delivery."""
import json
from pathlib import Path
import sys

from ..catalogue import read_json
from . import prepare_resources
from .plugins import load_interpreters
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
        result = prepare_resources(config_path, operation, selection, parameters,
                                   base_dir=base_dir, interpreters=interpreters)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(encode_result(result), ensure_ascii=True, separators=(',', ':'), allow_nan=False))
    return 0 if result['status'] == 'succeeded' else 1
