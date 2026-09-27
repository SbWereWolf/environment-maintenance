import json

import pytest

from environment_maintenance.catalogue import load_catalog
from environment_maintenance.engine import execute
from v2_helpers import FIXTURES, action, catalog, fixture_action, requirement, result_action, stateful_requirement


def run(tmp_path, item, *, operation="run", dry_run=False):
    return execute(load_catalog(catalog(tmp_path, [item])), operation, dry_run=dry_run, environ={})


def serialized(value):
    return value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))


def assert_parameter_execution(tmp_path, role, parameter_type, value, origin):
    encoded = serialized(value)
    observed = tmp_path / "mutation-observed.json"
    cwd = tmp_path / ("cwd-" + encoded)
    cwd.mkdir()
    selected = fixture_action(
        "capture_execution.py",
        observed,
        role,
        "${value}",
        cwd="${root}/cwd-${value}",
        env={"COLLISION": "declared", "VALUE": "${value}"},
    )
    if role == "check":
        item = requirement(check=selected)
        state = log = None
    else:
        initial = "missing" if role == "install" else "invalid"
        item, state, log = stateful_requirement(tmp_path, initial)
        item[role] = selected
    declaration = {"type": parameter_type}
    values = {}
    overrides = []
    environ = {
        "ALLOWED": "host",
        "COLLISION": "host",
        "SECRET": "must-not-leak",
    }
    if origin == "default":
        declaration["default"] = value
    elif origin == "values":
        values["value"] = value
    elif origin == "environment":
        declaration["env"] = "PARAM_VALUE"
        environ["PARAM_VALUE"] = value if isinstance(value, str) else encoded
    else:
        overrides.append("value=" + json.dumps(value, separators=(",", ":")))
    root = catalog(
        tmp_path,
        [item],
        parameters={
            "root": {"type": "string", "default": str(tmp_path)},
            "value": declaration,
        },
        inherit_env=["ALLOWED", "COLLISION"],
    )
    result = execute(
        load_catalog(root),
        "run",
        values=values,
        overrides=overrides,
        environ=environ,
    )
    assert result["status"] == ("ready" if role == "check" else "failed")
    assert json.loads(observed.read_text(encoding="utf-8")) == {
        "argv": [encoded],
        "cwd": str(cwd),
        "environment": {
            "ALLOWED": "host",
            "COLLISION": "declared",
            "VALUE": encoded,
        },
    }
    if role != "check":
        assert log.read_text(encoding="utf-8").splitlines() == ["check", "check"]
        assert state.read_text(encoding="utf-8") == initial


def assert_secret_result_redaction(tmp_path, role, origin):
    secret = f"SYNTHETIC_SECRET_{role}_{origin}"
    observed = tmp_path / "secret-observed.json"
    secret_cwd = tmp_path / secret
    secret_cwd.mkdir()
    selected = fixture_action(
        "secret_capture.py",
        observed,
        role,
        "${secret}",
        cwd="${root}/${secret}",
        env={"TOKEN": "${secret}"},
    )
    if role == "check":
        item = requirement(check=selected)
    else:
        initial = "missing" if role == "install" else "invalid"
        item, _, _ = stateful_requirement(tmp_path, initial)
        item[role] = selected
    declaration = {"type": "string", "secret": True}
    values = {}
    overrides = []
    environ = {}
    if origin == "default":
        declaration["default"] = secret
    elif origin == "values":
        values["secret"] = secret
    elif origin == "environment":
        declaration["env"] = "PARAM_SECRET"
        environ["PARAM_SECRET"] = secret
    else:
        overrides.append(f'secret="{secret}"')
    root = catalog(
        tmp_path,
        [item],
        parameters={
            "root": {"type": "string", "default": str(tmp_path)},
            "secret": declaration,
        },
    )

    result = execute(
        load_catalog(root),
        "run",
        values=values,
        overrides=overrides,
        environ=environ,
    )

    assert json.loads(observed.read_text(encoding="utf-8")) == {
        "argv": [secret],
        "cwd": str(secret_cwd),
        "token": secret,
    }
    public_json = json.dumps(result, sort_keys=True)
    assert secret not in public_json
    assert result["parameters"]["secret"] == "[REDACTED]"
    assert "safe-diagnostic:[REDACTED]" in public_json


@pytest.mark.parametrize("role", ["check", "install", "repair"])
@pytest.mark.parametrize("origin", ["default", "values", "environment", "cli"])
def test_secret_values_are_redacted_from_complete_public_result(tmp_path, role, origin):
    assert_secret_result_redaction(tmp_path, role, origin)


@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_secret_stdout_is_redacted_from_direct_execute_result(tmp_path, role):
    secret = f"SYNTHETIC_STDOUT_SECRET_{role}"
    secret_cwd = tmp_path / secret
    secret_cwd.mkdir()
    observed = tmp_path / f"{role}-secret-stdout.json"
    selected = fixture_action(
        "secret_stdout.py",
        observed,
        "${secret}",
        cwd="${root}/${secret}",
        env={"TOKEN": "${secret}"},
    )
    if role == "check":
        item = requirement(check=selected)
    else:
        initial = "missing" if role == "install" else "invalid"
        item, _, _ = stateful_requirement(tmp_path, initial)
        item[role] = selected
    root = catalog(
        tmp_path,
        [item],
        parameters={
            "root": {"type": "string", "default": str(tmp_path)},
            "secret": {"type": "string", "default": secret, "secret": True},
        },
    )

    result = execute(load_catalog(root), "run", environ={})
    row = result["requirements"][0]
    action_result = row["initial_check"] if role == "check" else row["mutation"]

    assert result["status"] == "failed"
    assert action_result["status"] == "protocol_failure"
    assert action_result["stdout"] == "[REDACTED]\n"
    assert action_result["stderr"] == "safe-diagnostic:[REDACTED]\n"
    assert action_result["invocation"]["argv"][-1] == "[REDACTED]"
    assert action_result["invocation"]["env"]["TOKEN"] == "[REDACTED]"
    assert action_result["invocation"]["cwd"].endswith("/[REDACTED]")
    assert secret not in json.dumps(result, sort_keys=True)
    assert json.loads(observed.read_text(encoding="utf-8")) == {
        "argument": secret,
        "cwd": str(secret_cwd),
        "token": secret,
    }
    if role != "check":
        assert row["final_check"]["status"] == "passed"


def test_short_secret_does_not_corrupt_unrelated_protocol_fields(tmp_path):
    secret = "check"
    secret_cwd = tmp_path / secret
    secret_cwd.mkdir()
    observed = tmp_path / "short-secret.json"
    selected = fixture_action(
        "secret_capture.py",
        observed,
        "check",
        "${secret}",
        cwd="${root}/${secret}",
        env={"TOKEN": "${secret}"},
    )
    root = catalog(
        tmp_path,
        [requirement(check=selected)],
        parameters={
            "root": {"type": "string", "default": str(tmp_path)},
            "secret": {"type": "string", "default": secret, "secret": True},
        },
    )

    result = execute(load_catalog(root), "check", environ={})
    action_result = result["requirements"][0]["initial_check"]

    assert result["status"] == "ready"
    assert action_result["status"] == "passed"
    assert action_result["response"]["action"] == "check"
    assert action_result["response"]["state"] == "satisfied"
    assert action_result["invocation"]["argv"][-1] == "[REDACTED]"
    assert action_result["invocation"]["env"]["TOKEN"] == "[REDACTED]"
    assert action_result["invocation"]["cwd"].endswith("/[REDACTED]")
    assert action_result["stderr"] == "safe-diagnostic:[REDACTED]\n"


def test_satisfied_runs_only_check(tmp_path):
    item, state, log = stateful_requirement(tmp_path, "satisfied")
    result = run(tmp_path, item)
    assert result["status"] == "ready"
    assert result["requirements"][0]["state"] == "satisfied"
    assert log.read_text() == "check\n"
    assert state.read_text() == "satisfied"


@pytest.mark.parametrize(
    ("initial", "expected_action"),
    [("missing", "install"), ("invalid", "repair")],
)
def test_mutation_is_selected_by_state_and_followed_by_same_check(tmp_path, initial, expected_action):
    item, state, log = stateful_requirement(tmp_path, initial)
    result = run(tmp_path, item)
    row = result["requirements"][0]
    assert result["status"] == "ready"
    assert row["initial_state"] == initial
    assert row["mutation"]["response"]["action"] == expected_action
    assert row["state"] == "satisfied"
    assert log.read_text().splitlines() == ["check", expected_action, "check"]
    assert row["initial_check"]["invocation"]["argv"] == row["final_check"]["invocation"]["argv"]


def test_unavailable_preserves_cause_and_recommendations_without_mutation(tmp_path):
    item, state, log = stateful_requirement(tmp_path, None)
    item["check"] = result_action("check-unavailable.json")
    result = run(tmp_path, item)
    row = result["requirements"][0]
    assert result["status"] == "unavailable" and result["exit_code"] == 3
    assert row["cause"] == "offline repository"
    assert row["recommendations"] == ["Connect the package mirror."]
    assert "mutation" not in row
    assert not state.exists() and not log.exists()


@pytest.mark.parametrize(("operation", "dry_run"), [("check", False), ("run", True)])
@pytest.mark.parametrize("initial", ["missing", "invalid"])
def test_check_and_dry_run_never_mutate(tmp_path, operation, dry_run, initial):
    item, state, log = stateful_requirement(tmp_path, initial)
    result = run(tmp_path, item, operation=operation, dry_run=dry_run)
    assert result["status"] == "action_required"
    assert result["requirements"][0]["planned_action"] == (
        "install" if initial == "missing" else "repair"
    )
    assert log.read_text() == "check\n"
    assert state.read_text() == initial


def test_successful_mutation_is_not_success_without_successful_recheck(tmp_path):
    item, state, log = stateful_requirement(tmp_path, "missing")
    item["install"] = result_action("install-completed.json")
    result = run(tmp_path, item)
    assert result["status"] == "failed" and result["exit_code"] == 4
    assert result["requirements"][0]["state"] == "missing"
    assert log.read_text() == "check\ncheck\n"


def test_failed_mutation_is_still_followed_by_check(tmp_path):
    item, state, log = stateful_requirement(tmp_path, "invalid")
    item["repair"] = action("raise SystemExit(7)")
    result = run(tmp_path, item)
    assert result["status"] == "failed"
    assert result["requirements"][0]["mutation"]["status"] == "protocol_failure"
    assert log.read_text() == "check\ncheck\n"


@pytest.mark.parametrize(("initial", "role"), [("missing", "install"), ("invalid", "repair")])
@pytest.mark.parametrize("failure", ["nonzero", "nonzero-success", "timeout", "overflow"])
def test_every_mutation_transport_failure_is_followed_by_identical_check(
    tmp_path,
    initial,
    role,
    failure,
):
    item, state, log = stateful_requirement(tmp_path, initial)
    if failure == "nonzero":
        selected = action("raise SystemExit(7)")
    elif failure == "nonzero-success":
        selected = fixture_action(
            "emit_result_and_exit.py",
            FIXTURES / "results" / f"{role}-completed.json",
            7,
        )
    elif failure == "timeout":
        selected = fixture_action("delayed_effect.py", tmp_path / "late", 1, bound=0.03)
    else:
        selected = fixture_action("output_flood.py", limit=16)
    item[role] = selected
    result = run(tmp_path, item)
    row = result["requirements"][0]
    assert result["status"] == "failed"
    assert row["mutation"]["status"] == "protocol_failure"
    assert row["initial_check"]["invocation"]["argv"] == row["final_check"]["invocation"]["argv"]
    assert log.read_text(encoding="utf-8").splitlines() == ["check", "check"]
    assert state.read_text(encoding="utf-8") == initial


@pytest.mark.parametrize("role", ["check", "install", "repair"])
@pytest.mark.parametrize(
    ("parameter_type", "value"),
    [("string", "text"), ("integer", 7), ("number", 1.5), ("boolean", True)],
)
@pytest.mark.parametrize("origin", ["default", "values", "environment", "cli"])
def test_every_action_expands_every_type_and_origin_with_exact_environment(
    tmp_path,
    role,
    parameter_type,
    value,
    origin,
):
    assert_parameter_execution(tmp_path, role, parameter_type, value, origin)


@pytest.mark.parametrize(
    ("parameter_type", "value"),
    [
        ("integer", -(2**63)),
        ("integer", 0),
        ("integer", 2**63 - 1),
        ("number", -1e308),
        ("number", 0.0),
        ("number", 1e308),
    ],
)
@pytest.mark.parametrize("origin", ["default", "values", "environment", "cli"])
def test_finite_numeric_boundaries_from_every_source_are_serialized_at_execution(
    tmp_path,
    parameter_type,
    value,
    origin,
):
    assert_parameter_execution(tmp_path, "install", parameter_type, value, origin)


def test_multiple_requirements_run_in_catalog_order(tmp_path):
    log = tmp_path / "ordered.log"
    items = []
    for identifier in ("one", "two"):
        items.append(requirement(identifier, check=fixture_action("ordered_check.py", log, identifier)))
    result = execute(load_catalog(catalog(tmp_path, items)), "run", environ={})
    assert result["status"] == "ready"
    assert log.read_text().splitlines() == ["one", "two"]
