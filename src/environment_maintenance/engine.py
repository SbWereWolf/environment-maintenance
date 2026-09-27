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


def _contains(value, selected):
    if isinstance(value, str):
        return selected in value
    if isinstance(value, list):
        return any(_contains(item, selected) for item in value)
    if isinstance(value, dict):
        return any(_contains(item, selected) for item in value.values())
    return False


def _literal_action_value(action, secret):
    return (
        secret in action["argv"]
        or secret in action["env"].values()
        or secret in Path(action["cwd"]).parts
    )


def _action_secrets(template, action, secret_values):
    return [
        secret
        for name, secret in secret_values
        if _contains(template, "${" + name + "}") or _literal_action_value(action, secret)
    ]


def _public_value(value, secrets, action_secrets):
    if value in secrets:
        return REDACTED
    return _redact_text(value, action_secrets)


def _public_path(value, secrets, action_secrets):
    path = Path(value)
    parts = [
        REDACTED if part in secrets else _redact_text(part, action_secrets)
        for part in path.parts
    ]
    if path.is_absolute():
        return str(Path(parts[0], *parts[1:]))
    return str(Path(*parts))


def _public_action_result(result, secrets, action_secrets):
    public = deepcopy(result)
    invocation = public["invocation"]
    public["invocation"] = {
        "argv": [
            _public_value(value, secrets, action_secrets)
            for value in invocation["argv"]
        ],
        "cwd": _public_path(invocation["cwd"], secrets, action_secrets),
        "env": {
            name: _public_value(value, secrets, action_secrets)
            for name, value in invocation["env"].items()
        },
    }
    incomplete = public["timed_out"] or not public["capture_complete"]
    for field in ("stdout", "stderr"):
        if incomplete and action_secrets and public[field]:
            public[field] = REDACTED
        else:
            public[field] = _redact_text(public[field], action_secrets)
    public["error"] = _redact_text(public["error"], action_secrets)
    if "response" in public:
        response = public["response"]
        response["schema"] = _public_value(response["schema"], secrets, action_secrets)
        for field in ("cause", "recommendations"):
            if field in response:
                response[field] = _redact_opaque(response[field], action_secrets)
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
    templates = catalogue.data["requirements"]
    items = expand(templates, parameters)
    secret_values = []
    for name, declaration in catalogue.data["parameters"].items():
        if declaration.get("secret"):
            text = _parameter_text(parameters[name])
            if text and all(text != existing for _, existing in secret_values):
                secret_values.append((name, text))
    secret_values.sort(key=lambda item: len(item[1]), reverse=True)
    secrets = [text for _, text in secret_values]
    for item in items:
        for role in ("check", "install", "repair"):
            validate_action(item[role], role)
    rows = []
    for template, item in zip(templates, items, strict=True):
        identifier = item["id"]
        check_action = item["check"]
        initial = run_action(check_action, identifier, "check", cwd=catalogue.root, environ=inherited)
        initial = _public_action_result(
            initial,
            secrets,
            _action_secrets(template["check"], check_action, secret_values),
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
                    secrets,
                    _action_secrets(template[mutation_role], item[mutation_role], secret_values),
                )
                final = _public_action_result(
                    final,
                    secrets,
                    _action_secrets(template["check"], check_action, secret_values),
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
