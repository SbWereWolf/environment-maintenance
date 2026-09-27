import json

import pytest

from environment_maintenance.catalogue import load_catalog
from environment_maintenance.engine import execute
from v2_helpers import FIXTURES, action, catalog, fixture_action, requirement, result_action, stateful_requirement


def run(tmp_path, item, *, operation="run", dry_run=False):
    return execute(load_catalog(catalog(tmp_path, [item])), operation, dry_run=dry_run, environ={})


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


def test_multiple_requirements_run_in_catalog_order(tmp_path):
    log = tmp_path / "ordered.log"
    items = []
    for identifier in ("one", "two"):
        items.append(requirement(identifier, check=fixture_action("ordered_check.py", log, identifier)))
    result = execute(load_catalog(catalog(tmp_path, items)), "run", environ={})
    assert result["status"] == "ready"
    assert log.read_text().splitlines() == ["one", "two"]
