"""S1-S7: real CLI, independent resource literals and owned process facts."""
import json
import socket

import pytest

from application_resources_support import (
    arrange_resources, assert_read_only, environment_record, expected_list,
    expected_started, persisted_resources, resource_fixture, set_values, unchanged_inputs,
)
from npm_delivery_support import living_group
from run_stop_support import Lab, application


@pytest.fixture
def lab(tmp_path):
    instance = Lab(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def test_fixture_cli_and_owned_worker_control(lab):
    """A failing setup is not resource-contract RED."""
    answer = lab.answer("run", "--env", "control", "--app", "A")
    group = lab.started("A")["pgid"]
    assert answer["applications"][0]["pgid"] == group and living_group(group)
    answer = lab.answer("stop", "--env", "control", "--app", "A")
    assert answer["errors"] == [] and answer["stopped"][0]["pgid"] == group
    lab.dead(group)
    assert not lab.state_path("control").exists()


def test_required_resources_are_exact_and_read_only(lab):
    arrange_resources(lab)
    before = unchanged_inputs(lab)
    completed = lab.call("run", "list")
    assert completed.returncode == 0 and completed.stderr == b""
    assert_read_only(lab, before)
    answer = json.loads(completed.stdout)
    assert answer == expected_list(lab), "RESOURCE_REQUIRED_MAP: independent declarations"
    assert list(answer["applications"]) == ["web", "worker-a", "worker-b", "worker-c", "scheduler", "plain"]
    assert type(answer["applications"]["web"]["port"]) is int


def test_explicit_invocation_selects_resource_values(lab):
    arrange_resources(lab)
    selected = lab.root / "other parameters Ω.json"
    set_values(lab, "b", path=selected)
    before = unchanged_inputs(lab)
    selected_raw = selected.read_bytes()
    answer = lab.answer("run", "list", "--config", lab.main,
                        "--parameters", selected, "--base-dir", lab.root, cwd=lab.base)
    assert_read_only(lab, before)
    assert selected.read_bytes() == selected_raw
    assert answer == expected_list(lab, "b"), "RESOURCE_OVERRIDE: selected invocation"


def test_filter_keeps_only_unregistered_resource_records(lab):
    arrange_resources(lab)
    absent = lab.answer("run", "list", "--env", "missing")
    assert absent["found"] is False and absent["applications"] == {}
    assert not lab.store.exists()
    lab.answer("run", "--env", "E", "--app", "web")
    before = lab.state_path("E").read_bytes()
    answer = lab.answer("run", "list", "--env", "E")
    expected = expected_list(lab)["applications"]
    del expected["web"]
    assert answer["found"] is True and answer["applications"] == expected
    assert lab.state_path("E").read_bytes() == before and lab.labels() == ["web"]


@pytest.mark.parametrize("change", ["replace", "remove"])
def test_saved_resources_survive_changed_or_missing_config(lab, change):
    arrange_resources(lab)
    run = lab.answer("run", "--env", "saved", "--app", "web")
    group = lab.started("web")["pgid"]
    assert run["applications"][0]["pgid"] == group and living_group(group)
    expected = expected_started(lab, ["web"])
    if change == "replace":
        set_values(lab, "b")
        # Change the declaration too; neither it nor the parameters own old facts.
        row = application("web")
        row["resources"] = {"host": "127.0.0.99", "port": 48739}
        lab.run_rows([row])
    else:
        for path in (lab.main, lab.values, lab.root / "run.json"):
            path.unlink()
    listed = environment_record(lab.answer("stop", "list"), "saved")
    assert listed["file"] == str(lab.state_path("saved"))
    # Observe cleanup before any missing-resource assertion aborts this test.
    stopped = lab.answer("stop", "--env", "saved", "--app", "web")
    assert stopped["stopped"] == [{"environment": "saved", "id": "web", "pgid": group}]
    lab.dead(group)
    assert not lab.state_path("saved").exists()
    assert listed["applications"] == expected, "RESOURCE_SNAPSHOT: original launch survives config change"


def test_two_launches_keep_distinct_resource_snapshots(lab):
    arrange_resources(lab)
    lab.answer("run", "--env", "A", "--app", "web")
    first_group = lab.started("web")["pgid"]
    first = expected_started(lab, ["web"])
    # Keep both independently reported groups even though the label is reused.
    lab.terminal_groups.append(first_group)
    (lab.root / "web.started.json").unlink()
    set_values(lab, "b")
    current = lab.answer("run", "list")
    lab.answer("run", "--env", "B", "--app", "web")
    second = expected_started(lab, ["web"], "b")
    answer = lab.answer("stop", "list")
    assert living_group(first_group) and living_group(second["web"]["pgid"])
    assert current == expected_list(lab, "b")
    assert environment_record(answer, "A")["applications"] == first
    assert environment_record(answer, "B")["applications"] == second


def test_append_remove_preserve_resource_facts_and_other_environment(lab):
    arrange_resources(lab)
    lab.answer("run", "--env", "E", "--app", "web")
    lab.answer("run", "--env", "E", "--app", "worker-a")
    lab.answer("run", "--env", "other", "--app", "scheduler")
    expected = expected_started(lab, ["web", "worker-a"])
    other = lab.state_path("other").read_bytes()
    before = persisted_resources(lab, "E")
    stopped = lab.answer("stop", "--env", "E", "--app", "web")
    lab.dead(expected["web"]["pgid"])
    assert stopped["errors"] == []
    after = persisted_resources(lab, "E")
    assert lab.state_path("other").read_bytes() == other
    assert before == expected, "RESOURCE_APPEND: retain first snapshot"
    assert after == {"worker-a": expected["worker-a"]}, "RESOURCE_REMOVE: retain neighbour snapshot"


def test_legacy_is_readable_and_stoppable_without_current_configs(lab):
    arrange_resources(lab)
    legacy = lab.spawn("legacy")
    lab.seed("old", {"web": legacy})
    lab.answer("run", "--env", "new", "--app", "scheduler")
    new_before = lab.state_path("new").read_bytes()
    for path in (lab.main, lab.values, lab.root / "run.json"):
        path.unlink()
    answer = lab.answer("stop", "list")
    assert environment_record(answer, "old")["applications"] == {"web": {"pgid": legacy}}
    stopped = lab.answer("stop", "--env", "old", "--app", "web")
    assert stopped["stopped"] == [{"environment": "old", "id": "web", "pgid": legacy}]
    lab.dead(legacy)
    assert not lab.state_path("old").exists()
    assert lab.state_path("new").read_bytes() == new_before


def test_busy_declared_port_does_not_add_run_admission(lab):
    arrange_resources(lab)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        row = application("web")
        row["resources"] = {"host": "127.0.0.1", "port": port}
        lab.run_rows([row])
        listed = lab.answer("run", "list")
        run = lab.answer("run", "--env", "busy", "--app", "web")
        group = lab.started("web")["pgid"]
        assert run["errors"] == [] and run["applications"][0]["pgid"] == group
        assert living_group(group)
        assert listed["applications"] == {"web": {"pgid": None, "host": "127.0.0.1", "port": port}}
        assert persisted_resources(lab, "busy")["web"] == {"pgid": group, "host": "127.0.0.1", "port": port}


@pytest.mark.parametrize("case", resource_fixture("invalid.json"), ids=lambda row: row["id"])
@pytest.mark.parametrize("operation", ["list", "run"])
def test_invalid_resources_are_input_errors_without_effects(lab, case, operation):
    row = application("web")
    row["resources"] = case["resources"]
    lab.run_rows([row])
    before = unchanged_inputs(lab)
    argv = ["run", "list"] if operation == "list" else ["run", "--env", "bad"]
    completed = lab.call(*argv)
    assert completed.returncode == 2, "RESOURCE_INPUT_ERROR: invalid declaration accepted"
    assert b"web" in completed.stderr and case["field"].encode() in completed.stderr
    assert_read_only(lab, before)


@pytest.mark.parametrize("operation", ["run-list", "stop-list"])
@pytest.mark.parametrize("options,pretty,warning", [
    ([], False, False), (["--output"], True, False),
    (["--output", "pretty"], True, False), (["--output", "one-line"], False, False),
    (["--output", "wide"], False, True),
])
def test_resource_data_and_format_are_independent(lab, operation, options, pretty, warning):
    arrange_resources(lab)
    if operation == "run-list":
        argv = ["run", "list"]
        expected = expected_list(lab)
    else:
        lab.answer("run", "--env", "format", "--app", "web")
        argv = ["stop", "list"]
        expected = expected_started(lab, ["web"])
    before = unchanged_inputs(lab)
    completed = lab.call(*argv, *options)
    assert completed.returncode == 0
    if pretty:
        assert completed.stdout.startswith(b'{\n  "operation": ')
        assert completed.stdout.endswith(b"\n}\n")
    else:
        assert completed.stdout.count(b"\n") == 1 and completed.stdout.endswith(b"\n")
    if warning:
        assert "Предупреждение:".encode() in completed.stderr and b"wide" in completed.stderr
    else:
        assert completed.stderr == b""
    assert all(path.read_bytes() == raw for path, raw in before.items())
    answer = json.loads(completed.stdout)
    if operation == "stop-list":
        answer = environment_record(answer, "format")["applications"]
    assert answer == expected, "RESOURCE_FORMAT_DATA: literal resource facts"


def test_partial_launch_preserves_successful_resource_record(lab):
    arrange_resources(lab)
    rows = json.loads((lab.root / "run.json").read_text())["applications"]
    rows.insert(0, application("broken", "fail"))
    lab.run_rows(rows)
    answer = lab.answer("run", "--env", "partial", code=1)
    assert [row["id"] for row in answer["errors"]] == ["broken"]
    names = ["web", "worker-a", "worker-b", "worker-c", "scheduler", "plain"]
    assert lab.labels() == ["broken", *names]
    assert all(living_group(lab.started(name)["pgid"]) for name in names)
    assert persisted_resources(lab, "partial") == expected_started(lab, names)


def test_failed_stop_keeps_resource_facts_and_continues_other_targets(lab):
    arrange_resources(lab)
    lab.answer("run", "--env", "E", "--app", "web")
    lab.answer("run", "--env", "E", "--app", "worker-a")
    expected = expected_started(lab, ["web"])
    group = expected["web"]["pgid"]
    other = lab.started("worker-a")["pgid"]
    answer = lab.answer("stop", "--env", "E", deny=group, code=1)
    assert answer["errors"][0]["id"] == "web"
    assert answer["stopped"] == [{"environment": "E", "id": "worker-a", "pgid": other}]
    lab.dead(other)
    assert living_group(group)
    assert persisted_resources(lab, "E") == expected, "RESOURCE_FAILED_STOP: failed target retains snapshot"


def test_corrupt_neighbour_does_not_hide_readable_resource_record(lab):
    arrange_resources(lab)
    lab.answer("run", "--env", "good", "--app", "web")
    expected = expected_started(lab, ["web"])
    before = lab.state_path("good").read_bytes()
    broken = lab.state_path("broken")
    broken.write_bytes(b"{broken JSON")
    answer = lab.answer("stop", "list", code=1)
    assert answer["errors"] and str(broken) in json.dumps(answer["errors"])
    assert len(answer["environments"]) == 1
    assert answer["environments"][0]["environment"] == "good"
    assert lab.state_path("good").read_bytes() == before
    assert broken.read_bytes() == b"{broken JSON"
    assert answer["environments"][0]["applications"] == expected


def test_oracle_distinguishes_missing_or_current_resource_facts(lab):
    """The fixture comparison rejects plausible wrong answers without product code."""
    expected = expected_list(lab)["applications"]
    assert list(expected) != expected
    assert expected_list(lab, "b")["applications"] != expected
    assert {"pgid": None} != expected["web"]
    assert expected["worker-a"]["queue"] != expected["worker-b"]["queue"]
    assert expected["worker-a"]["queue"] != expected["worker-c"]["queue"]
