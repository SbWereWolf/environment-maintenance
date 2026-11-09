"""Accepted run/stop contracts through the real CLI, state files and owned OS groups."""
import base64
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

import pytest

from run_stop_support import Lab, ROOT, FIXTURES, STARTER, application, command, fixture, wait_for, write
from npm_delivery_support import living_group


@pytest.fixture
def lab(tmp_path):
    instance = Lab(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def run_result(lab, result, title, *, planned, received, ids, exists=True, status="succeeded"):
    assert result["operation"] == "run" and result["status"] == status
    assert result["environment"] == title
    assert result["file"] == str(lab.state_path(title)) and Path(result["file"]).is_absolute()
    assert result["file_exists"] is exists
    assert lab.state_path(title).exists() is exists
    assert type(result["planned"]) is int and result["planned"] == planned
    assert type(result["received_pgids"]) is int and result["received_pgids"] == received
    assert [row["id"] for row in result["applications"]] == ids
    assert isinstance(result["errors"], list)
    if status == "succeeded":
        assert result["errors"] == []


def state_result(lab, title, groups):
    actual = lab.state(title)
    assert set(actual) == {"format-version", "environment-title", "applications"}
    assert actual["format-version"] == 1 and actual["environment-title"] == title
    assert actual["applications"] == {name: {"pgid": group} for name, group in groups.items()}


def stopped(result):
    return {(row["environment"], row["id"], row["pgid"]) for row in result["stopped"]}


def test_run_list_stop_roundtrip(lab):
    result = lab.answer('run', '--env', 'smoke-E', '--app', 'A')
    group = lab.started('A')['pgid']
    assert result['applications'][0]['pgid'] == group and living_group(group)
    assert lab.answer('run', 'list', '--env', 'smoke-E')['applications'] == ['B', 'C']
    final = lab.answer('stop', '--env', 'smoke-E')
    assert stopped(final) == {('smoke-E', 'A', group)} and final['errors'] == []
    lab.dead(group)
    assert not lab.state_path('smoke-E').exists()


def test_fixture_script_and_real_zutty_are_available(lab):
    """Infrastructure control; failure here is never product RED."""
    group = lab.spawn("control-script")
    assert group == lab.started("control-script")["pgid"] == os.getpgid(group)
    argv = ["/usr/bin/zutty", "-font", "DejaVuSansMono", "-fontpath",
            "/usr/share/fonts/truetype/dejavu", "-title", "EM-RED-fixture-control",
            "-e", sys.executable, "-B", str(FIXTURES / "worker.py"),
            str(lab.root), "control-terminal"]
    child = subprocess.Popen(argv, env=lab.env, start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    lab.children.append(child)
    lab.terminal_groups.append(child.pid)
    observed = lab.started("control-terminal")
    assert observed["tty"].startswith("/dev/pts/")
    view = subprocess.run(["/usr/bin/xwininfo", "-id", observed["window"]],
                          env=lab.env, capture_output=True, timeout=5)
    assert view.returncode == 0 and b"IsViewable" in view.stdout
    os.killpg(child.pid, signal.SIGTERM)
    lab.dead(child.pid)
    lab.dead(observed["pgid"])


@pytest.mark.parametrize("arguments,ids", fixture("run-forms.json"))
def test_four_run_forms_register_exact_selected_groups(lab, arguments, ids):
    result = lab.answer("run", *arguments)
    title = result["environment"]
    if "--env" in arguments:
        assert title == arguments[arguments.index("--env") + 1]
    else:
        assert str(uuid.UUID(title)) == title
    run_result(lab, result, title, planned=len(ids), received=len(ids), ids=ids)
    groups = {label: lab.started(label)["pgid"] for label in ids}
    assert {row["id"]: row["pgid"] for row in result["applications"]} == groups
    assert all(living_group(group) for group in groups.values())
    state_result(lab, title, groups)
    assert lab.labels() == ids


def test_append_preserves_earlier_apps_and_rejects_duplicate_and_full_run(lab):
    first = lab.answer("run", "--env", "E", "--app", "A")
    group_a = first["applications"][0]["pgid"]
    lab.answer("run", "--env", "E", "--app", "B")
    group_b = lab.started("B")["pgid"]
    state_result(lab, "E", {"A": group_a, "B": group_b})
    before = lab.state_path("E").read_bytes()
    for args in [("run", "--env", "E"), ("run", "--env", "E", "--app", "A")]:
        completed = lab.call(*args)
        assert completed.returncode != 0
        assert "E" in (completed.stdout + completed.stderr).decode()
        refused = json.loads(completed.stdout)
        assert refused["environment"] == "E" and refused["file"] == str(lab.state_path("E"))
        assert refused["file_exists"] is True and refused["errors"]
        assert lab.state_path("E").read_bytes() == before
    assert lab.labels() == ["A", "B"]


def test_run_list_is_read_only_and_missing_env_does_not_become_all(lab):
    result = lab.answer("run", "list")
    assert result["operation"] == "run-list" and result["applications"] == ["A", "B", "C"]
    assert not lab.store.exists() and lab.labels() == []
    absent = lab.answer("run", "list", "--env", "missing")
    assert absent["found"] is False and absent["applications"] == []
    assert "missing" in json.dumps(absent) and not lab.store.exists()
    lab.answer("run", "--env", "E", "--app", "A")
    before = lab.state_path("E").read_bytes()
    pending = lab.answer("run", "list", "--env", "E")
    assert pending["found"] is True and pending["applications"] == ["B", "C"]
    assert lab.state_path("E").read_bytes() == before and lab.labels() == ["A"]


def test_runtime_failure_continues_apps_but_not_the_failed_chain(lab):
    broken = application("B", "fail")
    broken["commands"].append(command("must-not-run"))
    lab.run_rows([application("A"), broken, application("C")])
    result = lab.answer("run", "--env", "E", code=1)
    run_result(lab, result, "E", planned=3, received=2, ids=["A", "B", "C"], status="failed")
    assert lab.labels() == ["A", "B", "C"]
    assert [row["id"] for row in result["errors"]] == ["B"]
    assert result["applications"][1]["pgid"] is None
    assert len(result["applications"][1]["result"]["commands"]) == 1
    state_result(lab, "E", {name: lab.started(name)["pgid"] for name in ["A", "C"]})


@pytest.mark.parametrize("rows,app", [([], None), ([application("A")], "missing")])
def test_zero_plan_returns_address_and_removes_empty_final_file(lab, rows, app):
    lab.run_rows(rows)
    arguments = ("--app", app) if app else ()
    completed = lab.call("run", "--env", "E", *arguments)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    run_result(lab, result, "E", planned=0, received=0, ids=[], exists=False)
    assert lab.labels() == []
    if app:
        assert app.encode() in completed.stderr


def test_literal_all_app_is_one_app_and_unknown_app_never_selects_all(lab):
    lab.run_rows([application("literal", identifier="all"), application("other")])
    result = lab.answer("run", "--env", "E", "--app", "all")
    run_result(lab, result, "E", planned=1, received=1, ids=["all"])
    assert lab.labels() == ["literal"]


@pytest.mark.parametrize("title", ["all", "", "space here", "../other", "x;echo", "x*"])
def test_unsafe_or_reserved_env_is_rejected_before_storage_or_launch(lab, title):
    result = lab.call("run", "--env", title, "--app", "A")
    assert result.returncode != 0
    assert lab.labels() == [] and not lab.store.exists()


def test_completed_group_is_registered_without_a_health_gate(lab):
    lab.run_rows([application("A", "dead")])
    result = lab.answer("run", "--env", "E")
    run_result(lab, result, "E", planned=1, received=1, ids=["A"])
    group = lab.started("A")["pgid"]
    assert not living_group(group)
    state_result(lab, "E", {"A": group})
    result = lab.answer("stop", "--env", "E")
    assert result["stopped"] == [] and result["errors"] == []
    assert result["message"] == "Ничего не остановлено."
    assert not lab.state_path("E").exists()


def test_invalid_pgid_is_an_app_error_and_later_app_still_starts(lab):
    lab.run_rows([application("bad", "bad-pgid"), application("C")])
    result = lab.answer("run", "--env", "E", code=1)
    run_result(lab, result, "E", planned=2, received=1, ids=["bad", "C"], status="failed")
    assert [row["id"] for row in result["errors"]] == ["bad"]
    state_result(lab, "E", {"C": lab.started("C")["pgid"]})


def test_returned_pgid_survives_real_save_failure_without_auto_stop(lab):
    assert os.geteuid() != 0, "Permission scenario requires ordinary user"
    lab.run_rows([application("A", "no-save")])
    result = lab.answer("run", "--env", "E", code=1)
    group = lab.started("A")["pgid"]
    assert result["environment"] == "E" and result["file"] == str(lab.state_path("E"))
    assert result["file_exists"] is lab.state_path("E").exists()
    assert result["planned"] == result["received_pgids"] == 1
    assert result["applications"][0]["pgid"] == group and result["errors"]
    assert lab.labels() == ["A"] and living_group(group)


def test_reservation_precedes_commands_and_creation_lock_is_short(lab):
    lab.run_rows([application("A", "reservation")])
    lab.answer("run", "--env", "E")
    assert json.loads((lab.root / "reservation-observed.json").read_text()) == {
        "reserved": True, "launch_outside_lock": True}


def test_external_creation_lock_serializes_a_later_create(lab):
    lab.run_rows([])
    lab.answer("run", "--env", "seed")
    assert not lab.state_path("seed").exists()
    locks = list(lab.store.iterdir())
    assert len(locks) == 1
    lab.run_rows([application("A", "reservation")])
    with locks[0].open("r+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        fcntl.lockf(stream, fcntl.LOCK_EX)
        child = subprocess.Popen([sys.executable, "-B", "-m", "environment_maintenance",
                                  "run", "--env", "E"], cwd=lab.root, env=lab.env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        lab.children.append(child)
        time.sleep(.2)  # Bounded fixture observation, not a product timeout.
        assert child.poll() is None and not lab.state_path("E").exists()
        assert lab.labels() == []
        fcntl.lockf(stream, fcntl.LOCK_UN)
        fcntl.flock(stream, fcntl.LOCK_UN)
    stdout, stderr = child.communicate(timeout=10)
    assert child.returncode == 0, stderr
    run_result(lab, json.loads(stdout), "E", planned=1, received=1, ids=["A"])


def test_failed_reservation_returns_address_and_releases_creation_lock(lab):
    assert os.geteuid() != 0, "Permission scenario requires ordinary user"
    lab.run_rows([])
    lab.answer("run", "--env", "seed")
    lab.run_rows([application("A")])
    lab.store.chmod(0o500)
    failed = lab.call("run", "--env", "E")
    assert failed.returncode != 0
    result = json.loads(failed.stdout)
    assert result["environment"] == "E" and result["file"] == str(lab.state_path("E"))
    assert result["file_exists"] is False and result["errors"]
    assert result["received_pgids"] == 0 and lab.labels() == []
    lab.store.chmod(0o700)
    retried = lab.answer("run", "--env", "E")
    assert retried["received_pgids"] == 1


@pytest.mark.parametrize("arguments", [("stop",), ("stop", "list")])
def test_stop_list_reads_payload_names_without_launching_or_creating(lab, arguments):
    lab.main.unlink()
    lab.values.unlink()
    empty = lab.answer(*arguments)
    assert empty["operation"] == "stop-list" and empty["environments"] == []
    assert not lab.store.exists()
    lab.seed("payload-title", {}, basename="misleading-name", version=99)
    result = lab.answer(*arguments)
    assert [row["environment"] for row in result["environments"]] == ["payload-title"]
    assert lab.labels() == []


def test_stop_list_selects_one_env_and_missing_is_nonfatal(lab):
    lab.seed("one", {})
    lab.seed("two", {})
    result = lab.answer("stop", "list", "--env", "two")
    assert [row["environment"] for row in result["environments"]] == ["two"]
    assert lab.answer("stop", "list", "--env", "absent")["environments"] == []


@pytest.mark.parametrize("prefix", [(), ("all",)])
def test_stop_entire_env_preserves_other_env_even_same_app_id(lab, prefix):
    a, b, c = lab.spawn("one-a"), lab.spawn("one-b"), lab.spawn("two-a")
    lab.seed("one", {"A": a, "B": b})
    lab.seed("two", {"A": c})
    before = lab.state_path("two").read_bytes()
    lab.main.unlink()
    lab.values.unlink()
    result = lab.answer("stop", *prefix, "--env", "one", cwd=lab.base)
    assert stopped(result) == {("one", "A", a), ("one", "B", b)}
    assert result["errors"] == []
    lab.dead(a)
    lab.dead(b)
    assert living_group(c) and lab.state_path("two").read_bytes() == before
    assert not lab.state_path("one").exists()


def test_stop_one_app_preserves_other_app_and_other_env(lab):
    a, b, c = lab.spawn("A"), lab.spawn("B"), lab.spawn("C")
    lab.seed("one", {"A": a, "B": b})
    lab.seed("two", {"A": c})
    result = lab.answer("stop", "--env", "one", "--app", "A")
    assert stopped(result) == {("one", "A", a)} and result["errors"] == []
    lab.dead(a)
    state_result(lab, "one", {"B": b})
    state_result(lab, "two", {"A": c})
    assert living_group(b) and living_group(c)


def test_stop_all_processes_all_envs_and_cleans_last_files(lab):
    a, b = lab.spawn("A"), lab.spawn("B")
    lab.seed("one", {"A": a})
    lab.seed("two", {"B": b})
    result = lab.answer("stop", "all")
    assert stopped(result) == {("one", "A", a), ("two", "B", b)}
    assert result["errors"] == []
    lab.dead(a)
    lab.dead(b)
    assert list(lab.store.glob("env-*.json")) == []


@pytest.mark.parametrize("arguments", [
    ("--env", "absent"), ("--env", "E", "--app", "absent"), ("all",),
])
def test_stop_missing_targets_are_not_errors(lab, arguments):
    lab.seed("E", {})
    result = lab.answer("stop", *arguments)
    assert result["stopped"] == [] and result["errors"] == []
    assert result["message"] == "Ничего не остановлено."


def test_stop_app_without_env_is_not_global_addressing(lab):
    group = lab.spawn("A")
    lab.seed("E", {"A": group})
    result = lab.call("stop", "--app", "A")
    assert result.returncode != 0 and living_group(group)
    state_result(lab, "E", {"A": group})


def test_stop_error_keeps_failed_mapping_and_continues_other_targets(lab):
    a, b = lab.spawn("A"), lab.spawn("B")
    lab.seed("E", {"A": a, "B": b})
    result = lab.answer("stop", "--env", "E", deny=a, code=1)
    assert stopped(result) == {("E", "B", b)}
    assert result["errors"][0]["id"] == "A" and result["errors"][0]["error"]
    assert living_group(a)
    lab.dead(b)
    state_result(lab, "E", {"A": a})
    retry = lab.answer("stop", "--env", "E")
    assert stopped(retry) == {("E", "A", a)}
    lab.dead(a)
    assert not lab.state_path("E").exists()


def test_unreadable_env_does_not_prevent_stopping_another(lab):
    assert os.geteuid() != 0, "Permission scenario requires ordinary user"
    a, b = lab.spawn("A"), lab.spawn("B")
    lab.seed("bad", {"A": a})
    lab.seed("good", {"B": b})
    lab.state_path("bad").chmod(0)
    result = lab.answer("stop", "all", code=1)
    assert stopped(result) == {("good", "B", b)} and result["errors"]
    assert str(lab.state_path("bad")) in json.dumps(result["errors"], ensure_ascii=False)
    assert living_group(a)
    lab.dead(b)
    lab.state_path("bad").chmod(0o600)
    lab.answer("stop", "--env", "bad")
    lab.dead(a)


def test_corrupt_env_is_reported_while_other_env_is_stopped(lab):
    group = lab.spawn("good")
    lab.seed("good", {"A": group})
    broken = lab.state_path("broken")
    broken.write_bytes(b'{broken JSON')
    result = lab.answer("stop", "all", code=1)
    assert stopped(result) == {("good", "A", group)}
    assert result["errors"] and str(broken) in json.dumps(result["errors"])
    assert broken.read_bytes() == b'{broken JSON'
    lab.dead(group)


def test_file_format_version_is_not_a_stop_compatibility_gate(lab):
    group = lab.spawn("A")
    lab.seed("E", {"A": group}, version=99)
    result = lab.answer("stop", "--env", "E")
    assert stopped(result) == {("E", "A", group)} and result["errors"] == []
    lab.dead(group)


def test_real_script_launcher_returns_pgid_and_keeps_append_logs(lab):
    out, err = lab.root / "starter.out", lab.root / "starter.err"
    out.write_bytes(b"previous output\n")
    err.write_bytes(b"previous error\n")
    child = subprocess.run([sys.executable, "-B", str(STARTER), "--stdout-log", str(out),
                            "--stderr-log", str(err), "--", sys.executable, "-B",
                            str(FIXTURES / "worker.py"), str(lab.root), "script"],
                           env=lab.env, capture_output=True, timeout=10)
    assert child.returncode == 0 and child.stderr == b""
    result = json.loads(child.stdout)
    observed = lab.started("script")
    assert result == {"status": "submitted", "pgid": observed["pgid"]}
    assert os.getpgid(observed["pid"]) == observed["pgid"]
    assert out.read_bytes() == b"previous output\n" and err.read_bytes() == b"previous error\n"


def test_two_real_zutty_groups_stop_independently_through_cli(lab):
    lab.run_rows([lab.terminal_row("terminal-A"), lab.terminal_row("terminal-B")])
    result = lab.answer("run", "--env", "E")
    groups = {row["id"]: row["pgid"] for row in result["applications"]}
    lab.terminal_groups.extend(groups.values())
    a, b = lab.started("terminal-A"), lab.started("terminal-B")
    assert a["tty"].startswith("/dev/pts/") and b["tty"].startswith("/dev/pts/")
    stopped_one = lab.answer("stop", "--env", "E", "--app", "terminal-A")
    assert stopped(stopped_one) == {("E", "terminal-A", groups["terminal-A"])}
    lab.dead(groups["terminal-A"])
    lab.dead(a["pgid"])
    assert living_group(groups["terminal-B"]) and living_group(b["pgid"])
    lab.answer("stop", "all")
    lab.dead(groups["terminal-B"])
    lab.dead(b["pgid"])


def test_run_preserves_raw_warning_like_bytes_and_command_order(lab):
    app = application("A")
    app["commands"].insert(0, command("prelude", "marker"))
    lab.run_rows([app])
    result = lab.answer("run", "--env", "E")
    first = result["applications"][0]["result"]["commands"][0]
    assert base64.b64decode(first["stdout"]["data"]) == b"WARNING fixture\xff\x00\n"
    assert base64.b64decode(first["stderr"]["data"]) == b"fixture diagnostic\x00\n"
    assert first["invocation"]["cwd"] == str(lab.root)
    assert first["invocation"]["env"]["PROBE_TOKEN"] == "chosen-token-Ω"
    assert lab.labels() == ["prelude", "A"]
