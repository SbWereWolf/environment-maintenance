"""F01-F07: literal public output, parser diagnostics and real owned effects."""
import base64
import json
import os
from pathlib import Path
import signal
import sys

import pytest

from npm_delivery_support import living_group
from run_stop_support import Lab, ROOT, FIXTURES as RUN_FIXTURES, application, write


OUTPUT_FIXTURES = ROOT / "tests/fixtures/cli-output"
WARNING = "Предупреждение:".encode()


def cases(group):
    return json.loads((OUTPUT_FIXTURES / "cases.json").read_text())[group]


@pytest.fixture
def lab(tmp_path):
    instance = Lab(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def input_snapshot(lab):
    return {path: path.read_bytes() for path in lab.root.glob("*.json")}


def assert_inputs_unchanged(before):
    assert all(path.read_bytes() == raw for path, raw in before.items())


def assert_no_resources(lab):
    assert not list(lab.store.glob("env-*.json"))
    assert not list(lab.root.glob("*.started.json"))


def prepare_route(lab, model):
    if model in ("infra", "deps", "adjust"):
        return [model, "--requirements", "[]"]
    if model == "check":
        for name in ("infra", "deps", "check"):
            write(lab.root / (name + ".json"), {"requirements": []})
        return ["check"]
    if model == "run-empty":
        lab.run_rows([])
        return ["run", "--env", "FMT"]
    if model == "stop-empty":
        return ["stop", "--env", "absent"]
    if model == "run-list":
        return ["run", "list"]
    if model == "stop-list":
        return ["stop", "list"]
    if model == "run-list-unicode":
        return ["run", "list", "--env", "Код-1"]
    raise AssertionError("Unknown test-owned model: " + model)


def literal_output(lab, model, mode):
    raw = (OUTPUT_FIXTURES / (model + "." + mode + ".json")).read_bytes()
    # Substitute an arranged path, never a value obtained from product output.
    return raw.replace(b"${owned_registry}", os.fsencode(lab.store))


def assert_golden(completed, lab, model, mode):
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == literal_output(lab, model, mode)
    actual = json.loads(completed.stdout)
    assert actual == json.loads(literal_output(lab, model, "one-line"))
    if model == "run-empty":
        assert actual["file"] == str(lab.store / "env-FMT.json")
    return actual


def assert_warning(completed, *tokens, known_output=False):
    assert WARNING in completed.stderr, completed.stderr
    for token in tokens:
        assert token.encode() in completed.stderr, completed.stderr
    if known_output:
        assert "неизвестные аргументы".encode() not in completed.stderr


def assert_pretty(completed, operation, code=0):
    assert completed.returncode == code, completed.stderr
    assert completed.stdout.startswith(b'{\n  "operation": ')
    assert completed.stdout.endswith(b"\n}\n")
    assert b"\r" not in completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["operation"] == operation
    return payload


def assert_marker_action(result, lab, label):
    assert set(result) == {"status", "commands", "error"}
    assert result["status"] == "succeeded" and result["error"] is None
    assert len(result["commands"]) == 1
    command = result["commands"][0]
    expected = json.loads((OUTPUT_FIXTURES / "marker-command.json").read_text())
    invocation = expected["invocation"]
    invocation["argv"][:4] = [sys.executable, str(RUN_FIXTURES / "probe.py"), str(lab.root), label]
    invocation["cwd"] = str(lab.root)
    invocation["env"].update(TMPDIR=str(lab.tmp), DISPLAY=os.environ.get("DISPLAY", ""), HOME=str(Path.home()))
    assert command == expected
    assert base64.b64decode(command["stdout"]["data"], validate=True) == b"WARNING fixture\xff\x00\n"
    assert base64.b64decode(command["stderr"]["data"], validate=True) == b"fixture diagnostic\x00\n"


MODELS = ("infra", "deps", "adjust", "check", "run-empty", "stop-empty", "run-list", "stop-list")


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("mode,options", [("one-line", []), ("pretty", ["--output"])])
def test_json_routes_preserve_data_and_format(lab, model, mode, options):
    argv = prepare_route(lab, model)
    before = input_snapshot(lab)
    completed = lab.call(*argv, *options)
    assert_golden(completed, lab, model, mode)
    assert completed.stderr == b""
    assert lab.labels() == []
    assert_inputs_unchanged(before)
    assert_no_resources(lab)


@pytest.mark.parametrize("row", cases("F02"), ids=lambda row: row["id"])
def test_output_argument_positions(lab, row):
    prepare_route(lab, row["model"])
    substitutions = {"${main}": str(lab.main), "${values}": str(lab.values), "${root}": str(lab.root)}
    argv = [substitutions.get(token, token) for token in row["argv"]]
    before = input_snapshot(lab)
    completed = lab.call(*argv)
    assert_golden(completed, lab, row["model"], row["format"])
    assert completed.stderr == b""
    assert lab.labels() == []
    assert_inputs_unchanged(before)
    assert_no_resources(lab)


@pytest.mark.parametrize("row", cases("F03"), ids=lambda row: row["id"])
def test_invalid_format_warns_and_preserves_request(lab, row):
    before = input_snapshot(lab)
    completed = lab.call(*row["argv"])
    if row.get("model"):
        assert_golden(completed, lab, row["model"], row["format"])
        assert lab.labels() == []
    else:
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.count(b"\n") == 1
        payload = json.loads(completed.stdout)
        assert payload["operation"] == "infra" and payload["status"] == "succeeded"
        assert [item["id"] for item in payload["requirements"]] == ["beta"]
        assert lab.labels() == ["beta"]
        assert_marker_action(payload["requirements"][0]["result"], lab, "beta")
    assert_warning(completed, "--output", "wide", known_output=True)
    assert_inputs_unchanged(before)
    assert_no_resources(lab)


@pytest.mark.parametrize("row", cases("F04"), ids=lambda row: row["id"])
def test_malformed_argv_warns_without_application_effects(lab, row):
    before = input_snapshot(lab)
    completed = lab.call(*row["argv"])
    assert completed.returncode == 2, (completed.stdout, completed.stderr)
    assert completed.stdout == b""
    token = next((value for value in row["argv"] if value.startswith("--")), None)
    assert_warning(completed, *([token] if token else []))
    if row["id"] == "unknown-command":
        assert b"not-an-operation" in completed.stderr
    assert lab.labels() == []
    assert_inputs_unchanged(before)
    assert_no_resources(lab)


@pytest.mark.parametrize("row", cases("F05"), ids=["recoverable-format", "malformed-selection", "duplicate-selection", "missing-value"])
def test_warnings_precede_invocation_resolution(lab, row):
    before = input_snapshot(lab)
    completed = lab.call("-B", str(OUTPUT_FIXTURES / "invocation_observer.py"),
                         *row["argv"], entry=sys.executable)
    assert_warning(completed)
    marker = b"INVOCATION_BOUNDARY\n"
    if "wide" in row["argv"]:
        assert_warning(completed, "--output", "wide", known_output=True)
        assert completed.returncode == 0
        assert completed.stderr.index(WARNING) < completed.stderr.index(marker)
        assert lab.labels() == ["beta"]
    else:
        assert completed.returncode == 2
        assert marker not in completed.stderr
        assert completed.stdout == b"" and lab.labels() == []
        if "beta" in " ".join(row["argv"]):
            message = completed.stderr.decode().casefold()
            assert "beta" in message and "infra" in message
            assert any(word in message for word in ("duplicate", "повтор"))
            assert any(word in message for word in ("remove", "удал", "unique", "уникал"))
    assert_inputs_unchanged(before)
    assert_no_resources(lab)


@pytest.mark.parametrize("row", cases("F06"), ids=lambda row: row["id"])
def test_formatted_operations_keep_effects_and_failure_contracts(lab, row):
    kind = row["id"]
    if kind in ("servicing-failure", "run-failure"):
        if kind == "servicing-failure":
            write(lab.root / "infra.json", {"requirements": [application("A", "fail")]})
        else:
            lab.run_rows([application("A", "fail")])
    before = input_snapshot(lab)
    if kind == "servicing-streams":
        completed = lab.call("infra", "--requirements", '["beta"]', "--output")
        payload = assert_pretty(completed, "infra")
        assert [item["id"] for item in payload["requirements"]] == ["beta"]
        assert lab.labels() == ["beta"]
        assert_marker_action(payload["requirements"][0]["result"], lab, "beta")
    elif kind == "checking-streams":
        completed = lab.call("check", "--output")
        payload = assert_pretty(completed, "check")
        assert lab.labels() == ["presence-alpha", "presence-beta", "presence-vendor", "extra"]
        assert [item["id"] for item in payload["resources"]] == ["alpha", "beta", "vendor"]
        assert [item["id"] for item in payload["checks"]] == ["extra"]
        for item in payload["resources"]:
            assert_marker_action(item["presence"], lab, "presence-" + item["id"])
            assert item["availability"] == {"status": "not_configured", "result": None, "reason": None}
        assert_marker_action(payload["checks"][0]["result"], lab, "extra")
    elif kind == "run-and-selected-stop":
        completed = lab.call("run", "--env", "OUTPUT", "--app", "B", "--output")
        payload = assert_pretty(completed, "run")
        group = lab.started("B")["pgid"]
        assert living_group(group)
        assert payload["environment"] == "OUTPUT"
        assert payload["planned"] == payload["received_pgids"] == 1
        assert [item["id"] for item in payload["applications"]] == ["B"]
        assert payload["applications"][0]["pgid"] == group and payload["errors"] == []
        assert lab.state("OUTPUT")["applications"] == {"B": {"pgid": group}}
        assert lab.labels() == ["B"]
        assert not (lab.root / "A.started.json").exists() and not (lab.root / "C.started.json").exists()
        final = lab.call("stop", "--env", "OUTPUT", "--app", "B", "--output")
        stopped = assert_pretty(final, "stop")
        assert stopped["stopped"] == [{"environment": "OUTPUT", "id": "B", "pgid": group}]
        assert stopped["errors"] == [] and final.stderr == b""
        lab.dead(group)
        handshake = json.loads((lab.root / "B.stopped.json").read_text())
        assert handshake == {"label": "B", "pid": group, "signal": signal.SIGTERM}
        assert not lab.state_path("OUTPUT").exists()
    elif kind in ("servicing-failure", "run-failure"):
        operation = "infra" if kind == "servicing-failure" else "run"
        selection = ["--requirements", '["A"]'] if operation == "infra" else ["--env", "FAILED", "--app", "A"]
        completed = lab.call(operation, *selection, "--output", "pretty")
        payload = assert_pretty(completed, operation, code=1)
        assert payload["status"] == "failed" and lab.labels() == ["A"]
        records = payload["requirements"] if operation == "infra" else payload["applications"]
        assert [item["id"] for item in records] == ["A"]
        command = records[0]["result"]["commands"][0]
        assert command["exit_code"] == 7
        assert base64.b64decode(command["stderr"]["data"], validate=True) == b"fixture selected failure\n"
        assert not list(lab.store.glob("env-*.json"))
        if operation == "run":
            assert payload["received_pgids"] == 0 and payload["errors"]
    else:
        operation = "run" if kind == "run-input-json" else "check"
        missing = lab.root / "missing-main.json"
        argv = [operation, "--config", str(missing), "--parameters", str(lab.values),
                "--base-dir", str(lab.root), "--output", "pretty"]
        if operation == "run":
            argv += ["--env", "INPUT"]
        completed = lab.call(*argv)
        assert completed.returncode == 2
        assert str(missing).encode() in completed.stderr and WARNING not in completed.stderr
        assert lab.labels() == []
        if operation == "run":
            payload = assert_pretty(completed, "run", code=2)
            assert payload["status"] == "failed" and payload["environment"] == "INPUT"
            assert payload["applications"] == [] and payload["received_pgids"] == 0
            assert payload["errors"] and str(missing) in payload["errors"][0]["error"]
        else:
            assert completed.stdout == b""
    if kind not in ("run-input-json", "check-input-stderr"):
        assert completed.stderr == b""
    assert_inputs_unchanged(before)


@pytest.mark.parametrize("row", cases("F07"), ids=["root-help", "command-help", "version"])
def test_help_and_version_remain_nonexecuting_text(lab, row):
    before = input_snapshot(lab)
    completed = lab.call(*row["argv"])
    assert completed.returncode == 0 and completed.stderr == b""
    assert not completed.stdout.startswith(b"{")
    if "--help" in row["argv"]:
        assert all(value in completed.stdout for value in (b"--output", b"pretty", b"one-line"))
    else:
        assert completed.stdout.startswith(b"environment-maintenance ") and completed.stdout.endswith(b"\n")
    assert lab.labels() == []
    assert_inputs_unchanged(before)
    assert_no_resources(lab)
