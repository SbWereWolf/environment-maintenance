"""Deliver attempted check streams without fabricating unexecuted action results."""
from copy import deepcopy
from typing import Any

from ..actions.transport import encode_action_result


def encode_result(result: dict[str, Any]) -> dict[str, Any]:
    encoded = deepcopy(result)
    for resource in encoded['resources']:
        resource['presence'] = encode_action_result(resource['presence'])
        availability = resource['availability']
        if availability['result'] is not None:
            availability['result'] = encode_action_result(availability['result'])
    for check in encoded['checks']:
        check['result'] = encode_action_result(check['result'])
    return encoded
