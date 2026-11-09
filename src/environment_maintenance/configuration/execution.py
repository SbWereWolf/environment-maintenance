"""Execution-only missing-ID policy; strict public configuration SDK stays strict."""
from .application import ConfigurationReader
from .json_file import read_json


def read_for_execution(config_path, operation, selection, warn):
    rows, missing = ConfigurationReader(read_json).read_for_execution(config_path, operation, selection)
    for identifier in missing:
        warn(f"{operation} configuration {config_path}: unknown id {identifier}; skipped")
    return rows
