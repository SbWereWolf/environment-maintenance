import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

import pytest

from environment_maintenance.catalogue import ContractError, load_catalog
from environment_maintenance.engine import execute
from environment_maintenance.process import run_action
from v2_helpers import FIXTURES, action, catalog, fixture_action, requirement, result_action


BUILD_PYTHON = Path("/usr/bin/python3")


def test_action_environment_uses_only_allowlist_plus_declared_values(tmp_path):
    selected = fixture_action("action_env.py", env={"DECLARED": "catalog"})
    item = requirement(check=selected)
    loaded = load_catalog(catalog(tmp_path, [item], inherit_env=["ALLOWED"]))
    result = execute(
        loaded,
        "check",
        environ={"ALLOWED": "host", "SECRET": "must-not-leak"},
    )
    assert result["requirements"][0]["initial_check"]["response"]["seen"] == [
        "host",
        "catalog",
        "absent",
    ]


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


def test_declared_output_schema_controls_protocol_validation(tmp_path):
    declared = "test.example/action-result/v7"
    valid = result_action("check-custom-schema.json", output_schema=declared)
    assert run_action(valid, "sample", "check", cwd=tmp_path, environ={})["status"] == "passed"
    mismatch = result_action("check-satisfied.json", output_schema=declared)
    assert run_action(mismatch, "sample", "check", cwd=tmp_path, environ={})["status"] == "protocol_failure"


@pytest.mark.parametrize("bound", [0.08, 0.25])
def test_timeout_enforces_declared_bound_and_kills_delayed_effect(tmp_path, bound):
    marker = tmp_path / "late-effect"
    delayed_effect_seconds = 0.6
    selected = fixture_action("delayed_effect.py", marker, delayed_effect_seconds, bound=bound)
    started = time.monotonic()
    result = run_action(selected, "sample", "check", cwd=tmp_path, environ={})
    elapsed = time.monotonic() - started
    assert result["status"] == "protocol_failure" and result["timed_out"] is True
    assert bound * 0.5 <= elapsed < bound + 0.2
    deadline = started + delayed_effect_seconds + 0.2
    while time.monotonic() < deadline:
        assert not marker.exists()
        time.sleep(0.02)


@pytest.mark.parametrize("limit", [16, 64])
def test_output_limit_applies_to_stdout_and_stderr(tmp_path, limit):
    selected = fixture_action("output_flood.py", limit=limit)
    result = run_action(selected, "sample", "check", cwd=tmp_path, environ={})
    assert result["status"] == "protocol_failure" and result["capture_complete"] is False
    assert result["stdout"] == "x" * limit
    assert result["stderr"] == "y" * limit


def test_relative_cwd_is_anchored_to_catalog_directory(tmp_path):
    root = catalog(tmp_path)
    child = root / "child"
    child.mkdir()
    selected = fixture_action("cwd_report.py", cwd="child")
    result = run_action(selected, "sample", "check", cwd=root, environ={})
    assert result["response"]["cwd"] == str(child)


def test_arguments_are_not_interpreted_by_a_shell(tmp_path):
    marker = tmp_path / "owned"
    hostile = "; touch " + str(marker)
    selected = fixture_action("echo_argument.py", hostile)
    result = run_action(selected, "sample", "check", cwd=tmp_path, environ={})
    assert result["response"]["value"] == hostile and not marker.exists()


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


def test_distribution_and_release_path_are_independent_and_v2_only(tmp_path):
    root = Path(__file__).resolve().parents[1]
    package = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "environment-maintenance"' in package
    assert "maintenance-repair" not in package
    forbidden = ("requirements.json", "repairs.json", "--repairs", "second-file", "'apply'", '"apply"')
    paths = [root / "src", root / "examples", root / "pyproject.toml"]
    for selected in paths:
        files = [selected] if selected.is_file() else [p for p in selected.rglob("*") if p.is_file()]
        for path in files:
            text = path.read_text(encoding="utf-8")
            assert not any(token in text for token in forbidden), (path, forbidden)
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
