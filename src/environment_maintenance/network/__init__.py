"""Compose internal file-backed network agreement with its concrete adapters."""


def adjust_network(requirements, parameters, *, parameters_path, retry_command):
    from ..configuration.json_file import write_json
    from .application import NetworkAdjustment
    from .linux import confirm_owner, reserve_port

    return NetworkAdjustment(reserve_port, confirm_owner, write_json).adjust(
        requirements, parameters, parameters_path=parameters_path, retry_command=retry_command)
