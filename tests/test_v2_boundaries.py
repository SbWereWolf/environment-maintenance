import json
from email.parser import Parser
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
import tomllib
import zipfile

import pytest

from environment_maintenance.catalogue import ContractError, load_catalog
from environment_maintenance.engine import execute
from environment_maintenance.process import run_action
from v2_helpers import FIXTURES, RESULT_SCHEMA, action, catalog, fixture_action, requirement, result_action


BUILD_PYTHON = Path(sys.executable)
TEXT_RELEASE_SUFFIXES = {".json", ".md", ".py", ".toml", ".txt"}
TEXT_RELEASE_NAMES = {"PKG-INFO"}


def assert_v2_only_sources(paths, forbidden, forbidden_basenames):
    for selected in paths:
        files = (
            [selected]
            if selected.is_file()
            else [path for path in selected.rglob("*") if path.is_file()]
        )
        for path in files:
            assert path.name not in forbidden_basenames
            assert "repairs" not in path.parts
            if path.suffix in TEXT_RELEASE_SUFFIXES or path.name in TEXT_RELEASE_NAMES:
                text = path.read_text(encoding="utf-8")
                assert not any(token in text for token in forbidden), (path, forbidden)


def invoke_cli(command, *arguments, env=None):
    return subprocess.run(
        [*map(str, command), *map(str, arguments)],
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
    )


def assert_complete_failure_record(result):
    assert result["status"] == "protocol_failure"
    assert isinstance(result["invocation"], dict)
    assert {"argv", "cwd", "env"} <= result["invocation"].keys()
    assert result["exit_code"] is None or isinstance(result["exit_code"], int)
    assert isinstance(result["stdout"], str)
    assert isinstance(result["stderr"], str)
    assert isinstance(result["capture_complete"], bool)
    assert isinstance(result["timed_out"], bool)
    assert isinstance(result["error"], str) and result["error"]


def assert_cli_rejects_invalid_value_inputs(command, base, env):
    from v2_helpers import stateful_requirement

    base.mkdir()
    item, state, log = stateful_requirement(base, "missing")
    root = catalog(
        base,
        [item],
        parameters={"count": {"type": "integer"}},
    )
    values_root = base / "values"
    values_root.mkdir()
    invalid_utf8 = values_root / "invalid-utf8.json"
    invalid_utf8.write_bytes(b"\xff\xfe")
    directory = values_root / "directory.json"
    directory.mkdir()
    cases = {
        "absent.json": None,
        "invalid-utf8.json": None,
        "directory.json": None,
        "malformed.json": "not-json",
        "duplicate.json": '{"count":1,"count":1}',
        "null.json": "null",
        "list.json": "[]",
        "string.json": '"value"',
        "number.json": "1",
        "boolean.json": "true",
        "unknown.json": '{"unknown":1}',
        "wrong-type.json": '{"count":"wrong"}',
    }
    missing_value = invoke_cli(command, "check", "--catalog-dir", root, env=env)
    assert missing_value.returncode == 2
    assert missing_value.stdout == "" and missing_value.stderr != ""
    assert state.read_text(encoding="utf-8") == "missing"
    assert not log.exists()
    for name, content in cases.items():
        path = values_root / name
        if content is not None:
            path.write_text(content, encoding="utf-8")
        failed = invoke_cli(command, "check", "--catalog-dir", root, "--values", path, env=env)
        assert failed.returncode == 2, name
        assert failed.stdout == "" and failed.stderr != "", name
        assert state.read_text(encoding="utf-8") == "missing"
        assert not log.exists()
    for arguments in [
        ("--set", "broken"),
        ("--set", "unknown=1"),
        ("--set", 'count="wrong"'),
        ("--set", "count=NaN"),
        ("--set", "count=1", "--set", "count=2"),
    ]:
        failed = invoke_cli(command, "check", "--catalog-dir", root, *arguments, env=env)
        assert failed.returncode == 2, arguments
        assert failed.stdout == "" and failed.stderr != "", arguments
        assert state.read_text(encoding="utf-8") == "missing"
        assert not log.exists()


def assert_cli_value_precedence(command, base, env):
    base.mkdir()
    observed = base / "observed.json"
    selected = fixture_action(
        "capture_execution.py",
        observed,
        "check",
        "${priority}",
    )
    root = catalog(
        base,
        [requirement(check=selected)],
        parameters={
            "priority": {
                "type": "string",
                "default": "default",
                "env": "PARAMETER_PRIORITY",
            },
        },
    )
    values = base / "values.json"
    values.write_text('{"priority":"values"}', encoding="utf-8")
    cases = [
        ([], env, "default"),
        (["--values", values], env, "values"),
        (["--values", values], {**env, "PARAMETER_PRIORITY": "environment"}, "environment"),
        (
            ["--values", values, "--set", 'priority="cli"'],
            {**env, "PARAMETER_PRIORITY": "environment"},
            "cli",
        ),
    ]
    for arguments, selected_env, expected in cases:
        completed = invoke_cli(
            command,
            "check",
            "--catalog-dir",
            root,
            *arguments,
            env=selected_env,
        )
        assert completed.returncode == 0 and completed.stderr == ""
        assert json.loads(completed.stdout)["status"] == "ready"
        assert json.loads(observed.read_text(encoding="utf-8"))["argv"] == [expected]


def test_action_environment_uses_only_allowlist_plus_declared_values(tmp_path):
    observed = tmp_path / "environment.json"
    selected = fixture_action(
        "action_env.py",
        observed,
        "check",
        env={"DECLARED": "catalog", "ALLOWED": "declared"},
    )
    item = requirement(check=selected)
    loaded = load_catalog(catalog(tmp_path, [item], inherit_env=["ALLOWED"]))
    result = execute(
        loaded,
        "check",
        environ={"ALLOWED": "host", "SECRET": "must-not-leak"},
    )
    assert result["status"] == "ready"
    assert json.loads(observed.read_text(encoding="utf-8")) == {
        "ALLOWED": "declared",
        "DECLARED": "catalog",
    }


@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_every_action_uses_the_same_exact_environment_boundary(tmp_path, role):
    observed = tmp_path / f"{role}-environment.json"
    selected = fixture_action(
        "action_env.py",
        observed,
        role,
        env={"DECLARED": "catalog", "COLLISION": "declared"},
    )
    result = run_action(
        selected,
        "sample",
        role,
        cwd=tmp_path,
        environ={"ALLOWED": "host", "COLLISION": "host"},
    )
    assert result["status"] == "passed"
    assert json.loads(observed.read_text(encoding="utf-8")) == {
        "ALLOWED": "host",
        "COLLISION": "declared",
        "DECLARED": "catalog",
    }


def test_action_cwd_symlink_loop_is_protocol_failure_without_effect(tmp_path):
    loop = tmp_path / "loop"
    sentinel = tmp_path / "executed"
    os.symlink("loop", loop)
    selected = action(
        "import pathlib;pathlib.Path('executed').touch()",
        cwd=loop,
    )

    result = run_action(selected, "sample", "check", cwd=tmp_path, environ={})

    assert_complete_failure_record(result)
    assert result["exit_code"] is None
    assert result["invocation"]["cwd"] == str(loop)
    assert not sentinel.exists()


def test_cli_never_serializes_known_secret_values(tmp_path):
    secret = "SYNTHETIC_CLI_SECRET"
    observed = tmp_path / "cli-secret.json"
    secret_cwd = tmp_path / secret
    secret_cwd.mkdir()
    selected = fixture_action(
        "secret_stdout.py",
        observed,
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
    source = Path(__file__).resolve().parents[1] / "src"

    completed = invoke_cli(
        [sys.executable, "-S", "-B", "-m", "environment_maintenance"],
        "check",
        "--catalog-dir",
        root,
        env={"PYTHONPATH": str(source)},
    )

    assert completed.returncode == 4 and completed.stderr == ""
    assert secret not in completed.stdout
    payload = json.loads(completed.stdout)
    action_result = payload["requirements"][0]["initial_check"]
    assert payload["parameters"]["secret"] == "[REDACTED]"
    assert payload["status"] == "failed"
    assert action_result["status"] == "protocol_failure"
    assert action_result["stdout"] == "[REDACTED]\n"
    assert action_result["stderr"] == "safe-diagnostic:[REDACTED]\n"
    assert action_result["invocation"]["cwd"].endswith("/[REDACTED]")
    assert json.loads(observed.read_text(encoding="utf-8")) == {
        "argument": secret,
        "cwd": str(secret_cwd),
        "token": secret,
    }


def test_cli_redacts_literal_secret_values_and_resolved_cwd(tmp_path):
    secret = "SYNTHETIC_CLI_LITERAL_SECRET"
    observed = tmp_path / "cli-literal-secret.json"
    selected = fixture_action(
        "secret_capture.py",
        observed,
        "check",
        secret,
        cwd="link",
        env={"TOKEN": secret},
    )
    root = catalog(
        tmp_path,
        [requirement(check=selected)],
        parameters={"secret": {"type": "string", "default": secret, "secret": True}},
    )
    target = root / secret
    target.mkdir()
    (root / "link").symlink_to(target, target_is_directory=True)
    source = Path(__file__).resolve().parents[1] / "src"

    completed = invoke_cli(
        [sys.executable, "-S", "-B", "-m", "environment_maintenance"],
        "check",
        "--catalog-dir",
        root,
        env={"PYTHONPATH": str(source)},
    )

    assert completed.returncode == 0 and completed.stderr == ""
    assert secret not in completed.stdout
    payload = json.loads(completed.stdout)
    invocation = payload["requirements"][0]["initial_check"]["invocation"]
    assert invocation["argv"][-1] == "[REDACTED]"
    assert invocation["env"]["TOKEN"] == "[REDACTED]"
    assert invocation["cwd"].endswith("/[REDACTED]")
    assert json.loads(observed.read_text(encoding="utf-8")) == {
        "argv": [secret],
        "cwd": str(target),
        "token": secret,
    }


@pytest.mark.parametrize(
    "script",
    [
        "print('not-json')",
        result_action("check-wrong-id.json"),
        result_action("check-wrong-action.json"),
        result_action("check-unavailable-incomplete.json"),
    ],
)
def test_protocol_failure_never_becomes_a_domain_state(tmp_path, script):
    selected = action(script) if isinstance(script, str) else script
    item = requirement(check=selected)
    result = execute(load_catalog(catalog(tmp_path, [item])), "run", environ={})
    assert result["status"] == "failed"
    assert result["requirements"][0]["initial_check"]["status"] == "protocol_failure"


@pytest.mark.parametrize(
    "variant",
    [
        "empty",
        "malformed",
        "missing-schema",
        "missing-requirement_id",
        "missing-action",
        "missing-state",
        "invalid-utf8",
        "multiple",
        "top-level-null",
        "top-level-list",
        "top-level-string",
        "top-level-number",
        "top-level-boolean",
        "duplicate-key",
        "unknown-field",
        "wrong-schema",
        "wrong-schema-type",
        "wrong-id",
        "wrong-id-type",
        "wrong-action",
        "wrong-action-type",
        "forbidden-recognized-field",
        "forbidden-advice-field",
        "wrong-state-type",
        "unsupported-state",
        "unavailable-empty-cause",
        "unavailable-blank-cause",
        "unavailable-wrong-cause",
        "unavailable-empty-recommendations",
        "unavailable-wrong-recommendations",
        "unavailable-empty-recommendation",
        "unavailable-blank-recommendation",
        "unavailable-wrong-recommendation-item",
        "unavailable-forbidden-outcome",
        "unavailable-missing-cause",
        "unavailable-missing-recommendations",
    ],
)
def test_complete_check_protocol_rejects_every_invalid_equivalence_class(tmp_path, variant):
    selected = fixture_action("emit_protocol_variant.py", "check", variant)
    result = execute(
        load_catalog(catalog(tmp_path, [requirement(check=selected)])),
        "run",
        environ={},
    )
    row = result["requirements"][0]
    assert result["status"] == "failed"
    assert row["initial_check"]["status"] == "protocol_failure"
    assert "mutation" not in row


@pytest.mark.parametrize("role", ["install", "repair"])
@pytest.mark.parametrize(
    "variant",
    [
        "empty",
        "malformed",
        "missing-schema",
        "missing-requirement_id",
        "missing-action",
        "missing-outcome",
        "invalid-utf8",
        "multiple",
        "top-level-null",
        "top-level-list",
        "top-level-string",
        "top-level-number",
        "top-level-boolean",
        "duplicate-key",
        "unknown-field",
        "wrong-schema",
        "wrong-schema-type",
        "wrong-id",
        "wrong-id-type",
        "wrong-action",
        "wrong-action-type",
        "forbidden-recognized-field",
        "forbidden-advice-field",
        "wrong-outcome-type",
        "unsupported-outcome",
    ],
)
def test_complete_mutation_protocol_failure_is_followed_by_same_check(tmp_path, role, variant):
    from v2_helpers import stateful_requirement

    initial = "missing" if role == "install" else "invalid"
    item, state, log = stateful_requirement(tmp_path, initial)
    item[role] = fixture_action("emit_protocol_variant.py", role, variant)
    result = execute(load_catalog(catalog(tmp_path, [item])), "run", environ={})
    row = result["requirements"][0]
    assert result["status"] == "failed"
    assert row["mutation"]["status"] == "protocol_failure"
    assert row["initial_check"]["invocation"]["argv"] == row["final_check"]["invocation"]["argv"]
    assert log.read_text(encoding="utf-8").splitlines() == ["check", "check"]
    assert state.read_text(encoding="utf-8") == initial


def test_nonzero_exit_with_success_payload_is_protocol_failure(tmp_path):
    script = fixture_action(
        "emit_result_and_exit.py",
        FIXTURES / "results" / "check-satisfied.json",
        9,
    )
    result = execute(
        load_catalog(catalog(tmp_path, [requirement(check=script)])),
        "check",
        environ={},
    )
    assert result["status"] == "failed"


@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_declared_output_schema_controls_protocol_validation(tmp_path, role):
    declared = "test.example/action-result/v7"
    valid = fixture_action("emit_valid_result.py", role, declared, output_schema=declared)
    assert run_action(valid, "sample", role, cwd=tmp_path, environ={})["status"] == "passed"
    mismatch = fixture_action("emit_valid_result.py", role, RESULT_SCHEMA, output_schema=declared)
    assert run_action(mismatch, "sample", role, cwd=tmp_path, environ={})["status"] == "protocol_failure"


@pytest.mark.parametrize(
    ("bound", "minimum_elapsed", "maximum_elapsed"),
    [
        (0.06, 0.03, 0.14),
        (0.35, 0.25, 0.60),
    ],
)
@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_timeout_enforces_declared_bound_and_kills_delayed_effect(
    tmp_path,
    bound,
    minimum_elapsed,
    maximum_elapsed,
    role,
):
    marker = tmp_path / "late-effect"
    delayed_effect_seconds = 0.6
    selected = fixture_action("delayed_effect.py", marker, delayed_effect_seconds, bound=bound)
    started = time.monotonic()
    result = run_action(selected, "sample", role, cwd=tmp_path, environ={})
    elapsed = time.monotonic() - started
    assert_complete_failure_record(result)
    assert result["timed_out"] is True
    assert minimum_elapsed <= elapsed < maximum_elapsed
    deadline = started + delayed_effect_seconds + 0.2
    while time.monotonic() < deadline:
        assert not marker.exists()
        time.sleep(0.02)


@pytest.mark.parametrize("limit", [16, 64])
def test_output_limit_applies_to_stdout_and_stderr(tmp_path, limit):
    selected = fixture_action("output_flood.py", limit=limit)
    result = run_action(selected, "sample", "check", cwd=tmp_path, environ={})
    assert_complete_failure_record(result)
    assert result["capture_complete"] is False
    assert result["stdout"] == "x" * limit
    assert result["stderr"] == "y" * limit


@pytest.mark.parametrize(("limit", "size", "complete"), [(16, 15, True), (16, 16, True), (16, 17, False)])
@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_output_limit_has_exact_byte_boundary_for_every_action(tmp_path, role, limit, size, complete):
    selected = fixture_action("output_exact.py", size, limit=limit)
    result = run_action(selected, "sample", role, cwd=tmp_path, environ={})
    assert_complete_failure_record(result)
    assert result["capture_complete"] is complete
    assert len(result["stdout"].encode("utf-8")) == min(size, limit)


@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_continuous_output_is_terminated_at_the_declared_limit(tmp_path, role):
    marker = tmp_path / "writer"
    selected = fixture_action("stream_output.py", marker, limit=1024, bound=2)
    started = time.monotonic()
    result = run_action(selected, "sample", role, cwd=tmp_path, environ={})
    assert time.monotonic() - started < 1.0
    assert_complete_failure_record(result)
    assert result["capture_complete"] is False
    assert len(result["stdout"].encode("utf-8")) == 1024
    assert len(result["stderr"].encode("utf-8")) == 1024
    first = marker.stat().st_mtime_ns
    time.sleep(0.15)
    assert marker.stat().st_mtime_ns == first


@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_timeout_kills_the_complete_process_group(tmp_path, role):
    marker = tmp_path / "descendant-effect"
    selected = fixture_action(
        "spawn_delayed_descendant.py",
        FIXTURES / "write_after_delay.py",
        marker,
        0.35,
        bound=0.06,
    )
    result = run_action(selected, "sample", role, cwd=tmp_path, environ={})
    assert_complete_failure_record(result)
    assert result["timed_out"] is True
    deadline = time.monotonic() + 0.55
    while time.monotonic() < deadline:
        assert not marker.exists()
        time.sleep(0.02)


@pytest.mark.parametrize(
    "selected",
    [
        {**action("pass"), "argv": ["/definitely/absent/environment-maintenance-command"]},
        {**action("pass"), "cwd": "absent-directory"},
        fixture_action("invalid_utf8_output.py"),
    ],
)
@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_launch_and_decode_failures_are_structured_protocol_failures(tmp_path, selected, role):
    result = run_action(selected, "sample", role, cwd=tmp_path, environ={})
    assert_complete_failure_record(result)
    assert result["timed_out"] is False


@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_non_executable_argv_is_a_structured_protocol_failure(tmp_path, role):
    executable = tmp_path / "not-executable"
    executable.write_text("plain text", encoding="utf-8")
    executable.chmod(0o600)
    selected = {**action("pass"), "argv": [str(executable)]}
    result = run_action(selected, "sample", role, cwd=tmp_path, environ={})
    assert_complete_failure_record(result)
    assert result["timed_out"] is False


@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_file_cwd_is_a_structured_protocol_failure(tmp_path, role):
    cwd_file = tmp_path / "cwd-file"
    cwd_file.write_text("not a directory", encoding="utf-8")
    selected = {**action("pass"), "cwd": str(cwd_file)}
    result = run_action(selected, "sample", role, cwd=tmp_path, environ={})
    assert_complete_failure_record(result)
    assert result["timed_out"] is False


@pytest.mark.parametrize(
    ("limit", "complete", "stdout"),
    [(3, False, "é"), (4, True, "éé"), (5, True, "éé")],
)
@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_output_limit_counts_utf8_bytes_without_partial_code_points(
    tmp_path,
    role,
    limit,
    complete,
    stdout,
):
    selected = fixture_action("utf8_output.py", 2, limit=limit)
    result = run_action(selected, "sample", role, cwd=tmp_path, environ={})
    assert_complete_failure_record(result)
    assert result["capture_complete"] is complete
    assert result["stdout"] == stdout
    assert len(result["stdout"].encode("utf-8")) <= limit


@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_relative_cwd_is_anchored_to_catalog_directory(tmp_path, role):
    root = catalog(tmp_path)
    child = root / "child"
    child.mkdir()
    observed = tmp_path / "cwd.txt"
    selected = fixture_action("cwd_report.py", observed, role, cwd="child")
    result = run_action(selected, "sample", role, cwd=root, environ={})
    assert result["status"] == "passed"
    assert observed.read_text(encoding="utf-8") == str(child)


@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_arguments_are_not_interpreted_by_a_shell(tmp_path, role):
    marker = tmp_path / "owned"
    observed = tmp_path / "argument.txt"
    hostile = "; touch " + str(marker)
    selected = fixture_action("echo_argument.py", observed, hostile, role)
    result = run_action(selected, "sample", role, cwd=tmp_path, environ={})
    assert result["status"] == "passed"
    assert observed.read_text(encoding="utf-8") == hostile and not marker.exists()


def test_cli_selects_directory_and_emits_v2_result(tmp_path):
    root = catalog(tmp_path, [requirement()])
    source = Path(__file__).resolve().parents[1] / "src"
    completed = subprocess.run(
        [sys.executable, "-S", "-B", "-m", "environment_maintenance", "check", "--catalog-dir", str(root)],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(source)},
        timeout=10,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["schema"] == "environment-maintenance/result/v2"


def test_source_cli_covers_operations_dry_run_parameters_and_failures(tmp_path):
    from v2_helpers import stateful_requirement

    source = Path(__file__).resolve().parents[1] / "src"
    command = [sys.executable, "-S", "-B", "-m", "environment_maintenance"]
    cli_env = {"PYTHONPATH": str(source), "TEXT": "environment"}

    cases = tmp_path / "cases"
    cases.mkdir()
    dry_case = cases / "dry"
    dry_case.mkdir()
    item, state, log = stateful_requirement(dry_case, "missing")
    dry_catalog = catalog(dry_case, [item])
    dry = invoke_cli(command, "run", "--catalog-dir", dry_catalog, "--dry-run", env=cli_env)
    assert dry.returncode == 2 and dry.stderr == ""
    assert json.loads(dry.stdout)["status"] == "action_required"
    assert state.read_text(encoding="utf-8") == "missing"
    assert log.read_text(encoding="utf-8") == "check\n"

    run_case = cases / "run"
    run_case.mkdir()
    item, state, log = stateful_requirement(run_case, "missing")
    run_catalog = catalog(run_case, [item])
    ran = invoke_cli(command, "run", "--catalog-dir", run_catalog, env=cli_env)
    assert ran.returncode == 0 and ran.stderr == ""
    assert json.loads(ran.stdout)["status"] == "ready"
    assert log.read_text(encoding="utf-8").splitlines() == ["check", "install", "check"]

    parameter_case = cases / "parameters"
    parameter_case.mkdir()
    observed = parameter_case / "observed.json"
    selected = fixture_action(
        "capture_execution.py",
        observed,
        "check",
        "${text}",
        "${count}",
        "${ratio}",
        "${enabled}",
    )
    parameter_catalog = catalog(
        parameter_case,
        [requirement(check=selected)],
        parameters={
            "text": {"type": "string", "default": "default", "env": "TEXT"},
            "count": {"type": "integer"},
            "ratio": {"type": "number", "default": 1.5},
            "enabled": {"type": "boolean", "default": False},
        },
    )
    values = parameter_case / "values.json"
    values.write_text('{"count":2}', encoding="utf-8")
    checked = invoke_cli(
        command,
        "check",
        "--catalog-dir",
        parameter_catalog,
        "--values",
        values,
        "--set",
        'text="cli"',
        "--set",
        "enabled=true",
        env=cli_env,
    )
    assert checked.returncode == 0 and checked.stderr == ""
    assert json.loads(checked.stdout)["status"] == "ready"
    assert json.loads(observed.read_text(encoding="utf-8"))["argv"] == [
        "cli",
        "2",
        "1.5",
        "true",
    ]

    for arguments in [(), ("check",), ("unknown",), ("check", "--unknown")]:
        failed = invoke_cli(command, *arguments, env=cli_env)
        assert failed.returncode == 2
        assert failed.stdout == "" and failed.stderr != ""
    assert_cli_rejects_invalid_value_inputs(command, cases / "invalid-values", cli_env)
    assert_cli_value_precedence(command, cases / "value-precedence", cli_env)


@pytest.mark.parametrize(
    ("result_name", "exit_code", "status"),
    [
        ("check-satisfied.json", 0, "ready"),
        ("check-unavailable.json", 3, "unavailable"),
        ("check-unavailable-incomplete.json", 4, "failed"),
    ],
)
def test_cli_maps_domain_status_to_exact_exit_code(tmp_path, result_name, exit_code, status):
    root = catalog(tmp_path, [requirement(check=result_action(result_name))])
    source = Path(__file__).resolve().parents[1] / "src"
    command = [sys.executable, "-S", "-B", "-m", "environment_maintenance"]
    completed = invoke_cli(command, "check", "--catalog-dir", root, env={"PYTHONPATH": str(source)})
    assert completed.returncode == exit_code and completed.stderr == ""
    assert json.loads(completed.stdout)["status"] == status


def test_release_source_scanner_does_not_decode_generated_bytecode(tmp_path):
    source = tmp_path / "src"
    cache = source / "__pycache__"
    cache.mkdir(parents=True)
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (cache / "module.cpython.pyc").write_bytes(b"\xcb\x00")

    assert_v2_only_sources([source], ("forbidden-token",), {"forbidden.py"})


def test_distribution_and_release_path_are_independent_and_v2_only(tmp_path):
    root = Path(__file__).resolve().parents[1]
    package = (root / "pyproject.toml").read_text(encoding="utf-8")
    metadata = tomllib.loads(package)["project"]
    assert 'name = "environment-maintenance"' in package
    assert "maintenance-repair" not in package
    forbidden = ("requirements.json", "repairs.json", "--repairs", "second-file", "'apply'", '"apply"')
    forbidden_basenames = {"requirements.json", "repairs.json", "repair.py"}
    paths = [root / "src", root / "examples", root / "pyproject.toml"]
    assert_v2_only_sources(paths, forbidden, forbidden_basenames)
    for path in (root / "src").rglob("*.py"):
        assert "import poise" not in path.read_text(encoding="utf-8")

    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    source_copy = tmp_path / "source"
    shutil.copytree(
        root,
        source_copy,
        ignore=shutil.ignore_patterns(".git", "build", "*.egg-info", "__pycache__"),
    )
    backend_probe = subprocess.run(
        [str(BUILD_PYTHON), "-c", "import setuptools.build_meta,wheel"],
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert backend_probe.returncode == 0, backend_probe.stderr
    built = subprocess.run(
        [
            str(BUILD_PYTHON),
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--no-index",
            "--wheel-dir",
            str(wheelhouse),
            str(source_copy),
        ],
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert built.returncode == 0, built.stderr
    sdist_dir = tmp_path / "sdist"
    sdist_dir.mkdir()
    sdist = subprocess.run(
        [
            str(BUILD_PYTHON),
            str(FIXTURES / "build_sdist.py"),
            str(sdist_dir),
        ],
        cwd=source_copy,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert sdist.returncode == 0, sdist.stderr
    wheels = list(wheelhouse.glob("environment_maintenance-*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        entry_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        entry_points = archive.read(entry_name).decode("utf-8")
        assert entry_points.strip() == (
            "[console_scripts]\n"
            "environment-maintenance = environment_maintenance.cli:main"
        )
        assert not any("environment_maintenance/repairs/" in name for name in names)
        assert "environment_maintenance/repair.py" not in names
        assert not any(Path(name).name in forbidden_basenames for name in names)
        assert not any(
            Path(name).suffix == ".pyc" or "__pycache__" in Path(name).parts
            for name in names
        )
    archives = list(sdist_dir.glob("*.tar.gz"))
    assert len(archives) == 1
    backend_result = json.loads(sdist.stdout.splitlines()[-1])
    assert backend_result == {"sdist": archives[0].name}
    with tarfile.open(archives[0], "r:gz") as archive:
        names = archive.getnames()
        assert not any(Path(name).name in forbidden_basenames for name in names)
        assert not any("/repairs/" in name for name in names)
        assert not any(
            Path(name).suffix == ".pyc" or "__pycache__" in Path(name).parts
            for name in names
        )
        package_metadata = [name for name in names if name.endswith("/PKG-INFO")]
        assert package_metadata
        for name in package_metadata:
            extracted = archive.extractfile(name)
            assert extracted is not None
            headers = Parser().parsestr(extracted.read().decode("utf-8"))
            assert headers["Name"] == metadata["name"]
            assert headers["Version"] == metadata["version"]

    environment = tmp_path / "installed"
    created = subprocess.run(
        [str(BUILD_PYTHON), "-m", "venv", str(environment)],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert created.returncode == 0, created.stderr
    installed = subprocess.run(
        [
            str(environment / "bin" / "python"),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            str(wheels[0]),
        ],
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert installed.returncode == 0, installed.stderr
    installed_files = [
        path
        for path in environment.rglob("*")
        if path.is_file()
        and any(part.startswith("environment_maintenance") for part in path.parts)
    ]
    assert not any(path.name in forbidden_basenames for path in installed_files)
    assert not any("repairs" in path.parts for path in installed_files)
    selected = catalog(tmp_path, [requirement()])
    executed = subprocess.run(
        [
            str(environment / "bin" / "environment-maintenance"),
            "check",
            "--catalog-dir",
            str(selected),
        ],
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert executed.returncode == 0, executed.stderr
    assert json.loads(executed.stdout)["schema"] == "environment-maintenance/result/v2"

    from v2_helpers import stateful_requirement

    installed_command = [environment / "bin" / "environment-maintenance"]
    installed_case = tmp_path / "installed-case"
    installed_case.mkdir()
    item, state, log = stateful_requirement(installed_case, "invalid")
    installed_catalog = catalog(installed_case, [item])
    dry = invoke_cli(
        installed_command,
        "run",
        "--catalog-dir",
        installed_catalog,
        "--dry-run",
        env={},
    )
    assert dry.returncode == 2 and json.loads(dry.stdout)["status"] == "action_required"
    assert state.read_text(encoding="utf-8") == "invalid"
    ran = invoke_cli(installed_command, "run", "--catalog-dir", installed_catalog, env={})
    assert ran.returncode == 0 and json.loads(ran.stdout)["status"] == "ready"
    assert log.read_text(encoding="utf-8").splitlines() == [
        "check",
        "check",
        "repair",
        "check",
    ]

    parameter_case = tmp_path / "installed-parameters"
    parameter_case.mkdir()
    observed = parameter_case / "observed.json"
    selected = fixture_action("capture_execution.py", observed, "check", "${value}")
    parameter_catalog = catalog(
        parameter_case,
        [requirement(check=selected)],
        parameters={"value": {"type": "integer", "default": 1}},
    )
    checked = invoke_cli(
        installed_command,
        "check",
        "--catalog-dir",
        parameter_catalog,
        "--set",
        "value=2",
        env={},
    )
    assert checked.returncode == 0 and checked.stderr == ""
    assert json.loads(observed.read_text(encoding="utf-8"))["argv"] == ["2"]
    assert_cli_rejects_invalid_value_inputs(
        installed_command,
        tmp_path / "installed-invalid-values",
        {},
    )
    assert_cli_value_precedence(
        installed_command,
        tmp_path / "installed-value-precedence",
        {},
    )
