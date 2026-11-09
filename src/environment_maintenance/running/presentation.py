"""Reuse the existing reversible raw-stream transport for attempted actions."""
from copy import deepcopy
from ..actions.transport import encode_action_result


def encode_run_result(result):
    result = deepcopy(result)
    for row in result['applications']:
        row['result'] = encode_action_result(row['result'])
    return result
