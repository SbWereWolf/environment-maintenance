"""Execute ordered catalog requirements through the declared action protocol."""

from copy import deepcopy
import json
import os
import re

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


def _redact_tokens(value, secrets):
    if not isinstance(value, str):
        return value
    for secret in secrets:
        pattern = rf"(?<!\w){re.escape(secret)}(?!\w)"
        value = re.sub(pattern, REDACTED, value)
    return value


def _redact_diagnostic(value, secrets, action_secrets):
    return _redact_tokens(_redact_text(value, action_secrets), secrets)


def _redact_opaque(value, secrets, action_secrets):
    if isinstance(value, str):
        return _redact_diagnostic(value, secrets, action_secrets)
    if isinstance(value, list):
        return [_redact_opaque(item, secrets, action_secrets) for item in value]
    if isinstance(value, dict):
        return {
            key: _redact_opaque(item, secrets, action_secrets)
            for key, item in value.items()
        }
    return value


def _contains(value, selected):
    if isinstance(value, str):
        return selected in value
    if isinstance(value, list):
        return any(_contains(item, selected) for item in value)
    if isinstance(value, dict):
        return any(_contains(item, selected) for item in value.values())
    return False


def _contains_token(value, selected):
    if isinstance(value, str):
        return re.search(rf"(?<!\w){re.escape(selected)}(?!\w)", value) is not None
    if isinstance(value, list):
        return any(_contains_token(item, selected) for item in value)
    if isinstance(value, dict):
        return any(_contains_token(item, selected) for item in value.values())
    return False


def _action_secrets(template, action, secret_values, inherited_bindings):
    selected = []
    for name, secret in secret_values:
        if _contains(template, "${" + name + "}") and secret not in selected:
            selected.append(secret)
    for source, secret in inherited_bindings:
        if source not in action["env"] and secret not in selected:
            selected.append(secret)
    return sorted(selected, key=len, reverse=True)


def _transport_secrets(invocation, secrets, action_secrets):
    selected = list(action_secrets)
    for secret in secrets:
        if secret not in selected and _contains_token(invocation, secret):
            selected.append(secret)
    return sorted(selected, key=len, reverse=True)


def _public_value(value, secrets, action_secrets):
    return _redact_diagnostic(value, secrets, action_secrets)


def _public_action_result(result, secrets, action_secrets, schema_secrets):
    public = deepcopy(result)
    invocation = public["invocation"]
    transport_secrets = _transport_secrets(invocation, secrets, action_secrets)
    public["invocation"] = {
        "argv": [
            _public_value(value, secrets, action_secrets)
            for value in invocation["argv"]
        ],
        "cwd": _public_value(invocation["cwd"], secrets, action_secrets),
        "env": {
            name: _public_value(value, secrets, action_secrets)
            for name, value in invocation["env"].items()
        },
    }
    incomplete = public["timed_out"] or not public["capture_complete"]
    for field in ("stdout", "stderr"):
        if incomplete and transport_secrets and public[field]:
            public[field] = REDACTED
        else:
            public[field] = _redact_diagnostic(
                public[field],
                secrets,
                transport_secrets,
            )
    public["error"] = _redact_diagnostic(public["error"], secrets, transport_secrets)
    if "response" in public:
        response = public["response"]
        response["schema"] = _redact_text(response["schema"], schema_secrets)
        for field in ("cause", "recommendations"):
            if field in response:
                response[field] = _redact_opaque(
                    response[field],
                    secrets,
                    action_secrets,
                )
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
            if text:
                secret_values.append((name, text))
    secret_values.sort(key=lambda item: len(item[1]), reverse=True)
    secrets = []
    for _, text in secret_values:
        if text not in secrets:
            secrets.append(text)
    inherited_bindings = []
    for declaration in catalogue.data["parameters"].values():
        source = declaration.get("env") if declaration.get("secret") else None
        if source in inherited and inherited[source]:
            binding = (source, inherited[source])
            if binding not in inherited_bindings:
                inherited_bindings.append(binding)
            if inherited[source] not in secrets:
                secrets.append(inherited[source])
    secrets.sort(key=len, reverse=True)
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
            _action_secrets(
                template["check"],
                check_action,
                secret_values,
                inherited_bindings,
            ),
            _action_secrets(
                template["check"]["output"]["schema"],
                check_action,
                secret_values,
                (),
            ),
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
                    _action_secrets(
                        template[mutation_role],
                        item[mutation_role],
                        secret_values,
                        inherited_bindings,
                    ),
                    _action_secrets(
                        template[mutation_role]["output"]["schema"],
                        item[mutation_role],
                        secret_values,
                        (),
                    ),
                )
                final = _public_action_result(
                    final,
                    secrets,
                    _action_secrets(
                        template["check"],
                        check_action,
                        secret_values,
                        inherited_bindings,
                    ),
                    _action_secrets(
                        template["check"]["output"]["schema"],
                        check_action,
                        secret_values,
                        (),
                    ),
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
