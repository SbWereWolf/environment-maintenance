"""Represent only raw process streams with a standard reversible encoding."""
from copy import deepcopy
from typing import Any

from ..actions.transport import encode_action_result


def encode_result(result: dict[str, Any]) -> dict[str, Any]:
    encoded = deepcopy(result)
    for requirement in encoded['requirements']:
        requirement['result'] = encode_action_result(requirement['result'])
    return encoded
