"""Typed values, precedence, and one-pass expansion."""

import json
import re
from typing import Any

from .catalogue import ContractError, _valid_parameter_value, validate_parameters


TOKEN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.-]*)\}")


def _typed_input(raw: str, kind: str, name: str, *, from_environment: bool) -> Any:
    if kind == "string":
        value = raw if from_environment else _string_override(raw)
    else:
        try:
            value = json.loads(raw, parse_constant=lambda constant: None)
        except (TypeError, ValueError, RecursionError) as exc:
            raise ContractError(f"{name}: invalid typed value") from exc
    if not _valid_parameter_value(kind, value):
        raise ContractError(f"{name}: invalid typed value")
    return value


def _string_override(raw: str) -> str:
    if raw.startswith('"'):
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            raise ContractError("Invalid string override") from exc
        if not isinstance(parsed, str):
            raise ContractError("String override must contain text")
        return parsed
    return raw


def resolve(spec, values=None, environ=None, overrides=None):
    validate_parameters(spec)
    values = {} if values is None else values
    environ = {} if environ is None else environ
    overrides = [] if overrides is None else overrides
    if not isinstance(values, dict):
        raise ContractError("values must be an object")
    if set(values) - set(spec):
        raise ContractError("Unknown values: " + ",".join(sorted(set(values) - set(spec))))
    effective: dict[str, Any] = {}
    origins: dict[str, str] = {}
    for name, declaration in spec.items():
        kind = declaration["type"]
        if "default" in declaration:
            effective[name] = declaration["default"]
            origins[name] = "default"
        if name in values:
            effective[name] = values[name]
            origins[name] = "values"
        if declaration.get("env") in environ:
            effective[name] = _typed_input(environ[declaration["env"]], kind, name, from_environment=True)
            origins[name] = "environment"
    seen: set[str] = set()
    for pair in overrides:
        if not isinstance(pair, str) or "=" not in pair:
            raise ContractError("Override must be name=value")
        name, raw = pair.split("=", 1)
        if name not in spec or name in seen:
            raise ContractError(f"Unknown or duplicate override: {name}")
        seen.add(name)
        effective[name] = _typed_input(raw, spec[name]["type"], name, from_environment=False)
        origins[name] = "cli"
    for name, declaration in spec.items():
        if name not in effective:
            raise ContractError(f"Missing parameter: {name}")
        if not _valid_parameter_value(declaration["type"], effective[name]):
            raise ContractError(f"{name}: expected {declaration['type']}")
    return effective, origins


def expand(value, params):
    if isinstance(value, str):
        def substitute(match):
            name = match.group(1)
            if name not in params:
                raise ContractError(f"Unknown placeholder: {name}")
            item = params[name]
            if isinstance(item, str):
                return item
            return json.dumps(item, separators=(",", ":"), allow_nan=False)
        return TOKEN.sub(substitute, value)
    if isinstance(value, list):
        return [expand(item, params) for item in value]
    if isinstance(value, dict):
        return {key: expand(item, params) for key, item in value.items()}
    return value
