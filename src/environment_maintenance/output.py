"""JSON formatting of already encoded CLI results, without execution or I/O."""
import json
from typing import Any


OUTPUT_FORMATS = ('pretty', 'one-line')


def format_json(value: Any, mode: str = 'one-line') -> str:
    if mode == 'pretty':
        return json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False)
    if mode == 'one-line':
        return json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False)
    raise ValueError(f'Unknown JSON output format: {mode}')
