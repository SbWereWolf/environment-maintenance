"""Strict input contract for one selected catalog/v2 directory."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any


CATALOG_SCHEMA = "environment-maintenance/catalog/v2"
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*\Z")
ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class ContractError(ValueError):
    """Invalid input is rejected before any action starts."""


@dataclass(frozen=True)
class Catalogue:
    root: Path
    manifest_path: Path
    data: dict[str, Any]


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = json.loads(raw, object_pairs_hook=_unique_pairs)
    except ContractError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise ContractError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"Expected JSON object: {path}")
    return value


def _fields(value: dict, required: set[str], label: str) -> None:
    if set(value) != required:
        missing = sorted(required - set(value))
        extra = sorted(set(value) - required)
        raise ContractError(f"{label} fields: missing={missing}, unknown={extra}")


def _valid_env(name: Any) -> bool:
    return isinstance(name, str) and bool(ENV_NAME.fullmatch(name))


def _valid_parameter_value(kind: str, value: Any) -> bool:
    if kind == "string":
        return isinstance(value, str) and "\0" not in value
    if kind == "integer":
        return type(value) is int
    if kind == "boolean":
        return type(value) is bool
    return type(value) is int or (type(value) is float and math.isfinite(value))


def validate_parameters(spec: Any) -> None:
    if not isinstance(spec, dict):
        raise ContractError("parameters must be an object")
    for name, declaration in spec.items():
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ContractError(f"Invalid parameter name: {name}")
        if not isinstance(declaration, dict):
            raise ContractError(f"{name}: parameter declaration must be an object")
        if "type" not in declaration or set(declaration) - {"type", "default", "env", "secret"}:
            raise ContractError(f"{name}: parameter fields")
        kind = declaration["type"]
        if kind not in ("string", "integer", "number", "boolean"):
            raise ContractError(f"{name}: unknown parameter type")
        if "default" in declaration and not _valid_parameter_value(kind, declaration["default"]):
            raise ContractError(f"{name}: invalid default")
        if "env" in declaration and not _valid_env(declaration["env"]):
            raise ContractError(f"{name}: invalid env")
        if "secret" in declaration and type(declaration["secret"]) is not bool:
            raise ContractError(f"{name}: invalid secret")


ACTION_FIELDS = {"argv", "cwd", "env", "output", "max_output_bytes", "execution_bound_seconds"}


def validate_action(action: Any, label: str) -> None:
    if not isinstance(action, dict):
        raise ContractError(f"{label}: action must be object")
    _fields(action, ACTION_FIELDS, "action")
    argv = action["argv"]
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(part, str) or "\0" in part for part in argv)
        or not argv[0]
    ):
        raise ContractError(f"{label}: invalid argv")
    cwd = action["cwd"]
    if not isinstance(cwd, str) or not cwd or "\0" in cwd:
        raise ContractError(f"{label}: invalid cwd")
    env = action["env"]
    if not isinstance(env, dict) or any(
        not _valid_env(key) or not isinstance(value, str) or "\0" in value
        for key, value in env.items()
    ):
        raise ContractError(f"{label}: invalid env")
    output = action["output"]
    if not isinstance(output, dict) or set(output) != {"schema"}:
        raise ContractError(f"{label}: invalid output")
    schema = output["schema"]
    if not isinstance(schema, str) or not schema or "\0" in schema:
        raise ContractError(f"{label}: invalid output schema")
    limit = action["max_output_bytes"]
    if type(limit) is not int or not 1 <= limit <= 16_777_216:
        raise ContractError(f"{label}: invalid max_output_bytes")
    bound = action["execution_bound_seconds"]
    if type(bound) not in (int, float) or not math.isfinite(bound) or not 0 < bound <= 3600:
        raise ContractError(f"{label}: invalid execution_bound_seconds")


def load_catalog(path: str | Path) -> Catalogue:
    root = Path(path).resolve()
    if not root.is_dir():
        raise ContractError(f"Selected catalog directory does not exist: {root}")
    manifest = root / "catalog.json"
    raw = read_json(manifest)
    _fields(raw, {"schema", "parameters", "inherit_env", "requirements"}, "catalog")
    if raw["schema"] != CATALOG_SCHEMA:
        raise ContractError("Unsupported catalog schema")
    validate_parameters(raw["parameters"])
    inherited = raw["inherit_env"]
    if not isinstance(inherited, list) or any(not _valid_env(name) for name in inherited):
        raise ContractError("invalid inherit_env")
    if len(set(inherited)) != len(inherited):
        raise ContractError("duplicate inherit_env")
    items = raw["requirements"]
    if not isinstance(items, list):
        raise ContractError("requirements must be an array")
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ContractError(f"requirement {index} must be object")
        _fields(item, {"id", "check", "install", "repair"}, "requirement")
        identifier = item["id"]
        if not isinstance(identifier, str) or not NAME.fullmatch(identifier) or identifier in seen:
            raise ContractError(f"Invalid or duplicate requirement id: {identifier}")
        seen.add(identifier)
        for role in ("check", "install", "repair"):
            validate_action(item[role], role)
    return Catalogue(root, manifest.resolve(), raw)
