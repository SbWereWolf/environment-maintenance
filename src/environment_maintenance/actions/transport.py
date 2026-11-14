"""Compatibility imports; the independent package owns this behavior."""

from command_execution.actions.transport import (
    JsonResultInterpreter,
    validate_json_data,
    load_interpreters,
    plan_for_json_transport,
    encode_action_result,
)
