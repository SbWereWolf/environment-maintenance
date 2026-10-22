"""Represent only raw process streams with a standard reversible encoding."""
import base64
from copy import deepcopy
from typing import Any


def encode_result(result: dict[str, Any]) -> dict[str, Any]:
    encoded = deepcopy(result)
    for requirement in encoded['requirements']:
        for command in requirement['result']['commands']:
            for field in ('stdout', 'stderr'):
                command[field] = dict(
                    encoding='base64', data=base64.b64encode(command[field]).decode('ascii')
                )
    return encoded
