"""Execute ordered catalog requirements through the declared action protocol."""

import os

from .catalogue import ContractError, validate_action
from .parameters import expand, resolve
from .process import run_action


RESULT_SCHEMA = "environment-maintenance/result/v2"


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
    for item in items:
        for role in ("check", "install", "repair"):
            validate_action(item[role], role)
    rows = []
    for item in items:
        identifier = item["id"]
        check_action = item["check"]
        initial = run_action(check_action, identifier, "check", cwd=catalogue.root, environ=inherited)
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
        name: "[REDACTED]" if declaration.get("secret") else parameters[name]
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
