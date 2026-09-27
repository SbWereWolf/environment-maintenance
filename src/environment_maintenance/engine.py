"""Execute ordered catalog requirements through the declared action protocol."""

from copy import deepcopy
import json
import os
from pathlib import Path

from .catalogue import ContractError, validate_action
from .parameters import expand, resolve
from .process import run_action


RESULT_SCHEMA = "environment-maintenance/result/v2"
REDACTED = "[REDACTED]"


def _parameter_text(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def _redact_text(value, secrets):
    if not isinstance(value, str):
        return value
    for secret in secrets:
        value = value.replace(secret, REDACTED)
    return value


def _redact_opaque(value, secrets):
    if isinstance(value, str):
        return _redact_text(value, secrets)
    if isinstance(value, list):
        return [_redact_opaque(item, secrets) for item in value]
    if isinstance(value, dict):
        return {key: _redact_opaque(item, secrets) for key, item in value.items()}
    return value


def _public_cwd(action, root):
    directory = Path(action["cwd"])
    if not directory.is_absolute():
        directory = Path(root) / directory
    try:
        return str(directory.resolve())
    except (OSError, RuntimeError):
        return str(directory)


def _public_action_result(result, action, root, inherited, secrets):
    public = deepcopy(result)
    environment = {
        name: _redact_text(value, secrets)
        for name, value in inherited.items()
    }
    environment.update(action["env"])
    public["invocation"] = {
        "argv": list(action["argv"]),
        "cwd": _public_cwd(action, root),
        "env": environment,
    }
    for field in ("stdout", "stderr", "error"):
        public[field] = _redact_text(public[field], secrets)
    if "response" in public:
        response = public["response"]
        response["schema"] = action["output"]["schema"]
        for field in ("cause", "recommendations"):
            if field in response:
                response[field] = _redact_opaque(response[field], secrets)
    return public


def _outcome(rows):
    states = {row.get("status") for row in rows}
    if "failed" in states:
        return "failed", 4
    if "unavailable" in states:
        return "unavailable", 3
    if "action_required" in states:
        return "action_required", 2
    return "ready", 0


def execute(catalogue, operation, *, values=None, overrides=None, environ=None, dry_run=False):
    if operation not in {"check", "run"}:
        raise ContractError(f"Unknown operation: {operation}")
    host = dict(os.environ if environ is None else environ)
    parameters, origins = resolve(catalogue.data["parameters"], values, host, overrides)
    inherited = {name: host[name] for name in catalogue.data["inherit_env"] if name in host}
    items = expand(catalogue.data["requirements"], parameters)
    public_parameters = {
        name: REDACTED if declaration.get("secret") else parameters[name]
        for name, declaration in catalogue.data["parameters"].items()
    }
    public_items = expand(catalogue.data["requirements"], public_parameters)
    secrets = []
    for name, declaration in catalogue.data["parameters"].items():
        if declaration.get("secret"):
            text = _parameter_text(parameters[name])
            if text and text not in secrets:
                secrets.append(text)
    secrets.sort(key=len, reverse=True)
    for item in items:
        for role in ("check", "install", "repair"):
            validate_action(item[role], role)
    rows = []
    for item, public_item in zip(items, public_items, strict=True):
        identifier = item["id"]
        check_action = item["check"]
        initial = run_action(check_action, identifier, "check", cwd=catalogue.root, environ=inherited)
        initial = _public_action_result(
            initial,
            public_item["check"],
            catalogue.root,
            inherited,
            secrets,
        )
        row = {"id": identifier, "initial_check": initial}
        if initial["status"] != "passed":
            row["status"] = "failed"
            rows.append(row)
            continue
        state = initial["response"]["state"]
        row.update(initial_state=state, state=state)
        if state == "satisfied":
            row["status"] = "ready"
        elif state == "unavailable":
            row.update(
                status="unavailable",
                cause=initial["response"]["cause"],
                recommendations=initial["response"]["recommendations"],
            )
        else:
            mutation_role = "install" if state == "missing" else "repair"
            if operation == "check" or dry_run:
                row.update(status="action_required", planned_action=mutation_role)
            else:
                mutation = run_action(
                    item[mutation_role], identifier, mutation_role, cwd=catalogue.root, environ=inherited
                )
                final = run_action(check_action, identifier, "check", cwd=catalogue.root, environ=inherited)
                mutation = _public_action_result(
                    mutation,
                    public_item[mutation_role],
                    catalogue.root,
                    inherited,
                    secrets,
                )
                final = _public_action_result(
                    final,
                    public_item["check"],
                    catalogue.root,
                    inherited,
                    secrets,
                )
                row.update(mutation=mutation, final_check=final)
                if final["status"] == "passed":
                    row["state"] = final["response"]["state"]
                row["status"] = (
                    "ready"
                    if mutation["status"] == "passed" and final["status"] == "passed" and row["state"] == "satisfied"
                    else "failed"
                )
        rows.append(row)
    status, code = _outcome(rows)
    visible = {
        name: REDACTED if declaration.get("secret") else parameters[name]
        for name, declaration in catalogue.data["parameters"].items()
    }
    return {
        "schema": RESULT_SCHEMA,
        "operation": operation,
        "dry_run": dry_run,
        "status": status,
        "exit_code": code,
        "parameters": visible,
        "parameter_sources": origins,
        "requirements": rows,
    }
