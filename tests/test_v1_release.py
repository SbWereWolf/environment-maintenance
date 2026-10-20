"""Black-box release checks with test-owned values and resource actions."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tomllib

import pytest

from v2_helpers import catalog, fixture_action, requirement, stateful_requirement


ROOT = Path(__file__).resolve().parents[1]


def invoke(argv, cwd, **options):
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
    return subprocess.run(
        list(map(str, argv)), cwd=cwd, env=environment,
        capture_output=True, text=True, **options,
    )


@pytest.fixture(scope="module")
def release_files(tmp_path_factory):
    output = tmp_path_factory.mktemp("release artifacts")
    built = invoke(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", output],
        ROOT,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    wheels = list(output.glob("*.whl"))
    sources = list(output.glob("*.tar.gz"))
    assert len(wheels) == len(sources) == 1
    return wheels[0], sources[0]


@pytest.fixture(scope="module")
def consumer(release_files, tmp_path_factory):
    root = tmp_path_factory.mktemp("independent app with spaces")
    prefix = root / ".venv"
    created = invoke([sys.executable, "-m", "venv", "--copies", prefix], root)
    assert created.returncode == 0, created.stdout + created.stderr
    python = prefix / "bin" / "python"
    installed = invoke(
        [python, "-I", "-m", "pip", "install", "--no-index", "--no-deps", release_files[0]],
        root,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    cwd = root / "unrelated working directory"
    cwd.mkdir()
    return root, python, cwd


def cli(consumer, *arguments):
    _, python, cwd = consumer
    return invoke([python, "-I", "-m", "environment_maintenance", *arguments], cwd)


def short_entry(consumer, kind):
    root, _, _ = consumer
    if kind == "root":
        source = ROOT / "start-app"
        assert source.is_file(), "The application root must supply start-app"
        entry = root / "start-app"
        shutil.copy2(source, entry)
    else:
        entry = root / ".venv" / "bin" / "start-app"
    assert entry.is_file(), "The installed distribution must supply start-app"
    assert os.access(entry, os.X_OK), "start-app must be executable"
    return entry


def test_source_has_literal_release_version():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert metadata["project"]["version"] == "1.0.0"


def test_installed_metadata_and_public_version_are_one(consumer):
    _, python, cwd = consumer
    code = "import importlib.metadata as m; print(m.version('environment-maintenance'))"
    result = invoke([python, "-I", "-c", code], cwd)
    assert (result.returncode, result.stdout, result.stderr) == (0, "1.0.0\n", "")
    result = invoke(
        [python, "-I", "-c", "import environment_maintenance as e; print(e.__version__)"], cwd,
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, "1.0.0\n", "")


def test_module_reports_version_without_requiring_an_operation(consumer):
    result = cli(consumer, "--version")
    assert (result.returncode, result.stdout, result.stderr) == (
        0, "environment-maintenance 1.0.0\n", "",
    )


def test_installed_start_app_exposes_version_and_help(consumer):
    root, _, cwd = consumer
    entry = root / ".venv" / "bin" / "start-app"
    assert entry.is_file(), "The installed distribution must supply start-app"
    version = invoke([entry, "--version"], cwd)
    assert (version.returncode, version.stdout, version.stderr) == (
        0, "environment-maintenance 1.0.0\n", "",
    )
    help_result = invoke([entry, "--help"], cwd)
    assert help_result.returncode == 0
    assert "check" in help_result.stdout and "run" in help_result.stdout
    assert "--catalog-dir" in help_result.stdout


@pytest.mark.parametrize("kind", ["installed", "root"])
@pytest.mark.parametrize("operation", ["check", "run"])
def test_short_entry_forwards_actual_arguments_and_action_output(consumer, tmp_path, kind, operation):
    entry = short_entry(consumer, kind)
    _, _, cwd = consumer
    parent = tmp_path / "catalog source with spaces"
    parent.mkdir()
    selected = catalog(
        parent,
        [requirement(check=fixture_action("v1_release_action.py", "echo-marker", "${marker}"))],
        parameters={"marker": {"type": "string"}},
    )
    values = tmp_path / "selected values with spaces.json"
    values.write_text(json.dumps({"marker": "value from file"}))
    result = invoke(
        [entry, operation, "--catalog-dir", selected, "--values", values,
         "--set", "marker=explicit value with spaces", "--dry-run"], cwd,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    response = json.loads(result.stdout)
    assert response["operation"] == operation
    assert response["status"] == "ready"
    assert response["dry_run"] is True
    assert response["parameters"] == {"marker": "explicit value with spaces"}
    action = response["requirements"][0]["initial_check"]
    assert action["invocation"]["argv"][-1] == "explicit value with spaces"
    assert action["stderr"] == "fixture note: explicit value with spaces\n"


@pytest.mark.parametrize("kind", ["installed", "root"])
def test_short_entry_preserves_input_refusal_and_stderr(consumer, tmp_path, kind):
    entry = short_entry(consumer, kind)
    _, _, cwd = consumer
    result = invoke([entry, "check", "--catalog-dir", tmp_path / "absent"], cwd)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Selected catalog directory does not exist" in result.stderr


def test_root_start_app_uses_its_own_installation_from_another_cwd(consumer):
    source = ROOT / "start-app"
    assert source.is_file(), "The application root must supply start-app"
    root, _, cwd = consumer
    entry = root / "start-app"
    shutil.copy2(source, entry)
    result = invoke([entry, "--version"], cwd)
    assert (result.returncode, result.stdout, result.stderr) == (
        0, "environment-maintenance 1.0.0\n", "",
    )


def test_root_start_app_explains_missing_runtime_without_installing(tmp_path):
    source = ROOT / "start-app"
    assert source.is_file(), "The application root must supply start-app"
    entry = tmp_path / "start-app"
    shutil.copy2(source, entry)
    result = invoke([entry, "--help"], tmp_path)
    assert result.returncode != 0
    assert result.stdout == ""
    assert ".venv" in result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["start-app"]


def test_installed_import_belongs_to_the_consumer(consumer):
    root, python, cwd = consumer
    result = invoke(
        [python, "-I", "-c", "import environment_maintenance as e; print(e.__file__)"], cwd,
    )
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()).is_relative_to(root / ".venv")
    assert result.stderr == ""


def test_source_distribution_contains_owned_project_materials(release_files):
    wheel, source = release_files
    assert wheel.name == "environment_maintenance-1.0.0-py3-none-any.whl"
    assert source.name == "environment_maintenance-1.0.0.tar.gz"
    with tarfile.open(source) as archive:
        paths = [Path(name) for name in archive.getnames()]
    relative = {Path(*p.parts[1:]).as_posix() for p in paths if len(p.parts) > 1}
    assert {
        "start-app", "README.md", "pyproject.toml", "tests/smoke.sh",
        "src/environment_maintenance/cli.py", "examples/catalog-v2/catalog.json",
        "examples/catalog-v2/probe.py",
        "tests/v2_helpers.py", "tests/fixtures/v1_release_action.py",
        "tests/fixtures/state_check.py", "tests/fixtures/state_install.py",
        "tests/fixtures/state_repair.py", "tests/fixtures/results/check-satisfied.json",
    } <= relative
    assert any(name.startswith("tests/test_") for name in relative)
    assert not any({".venv", ".git", "build"} & set(p.parts) for p in paths)


def test_source_distribution_contains_operator_documentation(release_files):
    _, source = release_files
    with tarfile.open(source) as archive:
        relative = [Path(*Path(name).parts[1:]).as_posix() for name in archive.getnames()]
    assert any(name.startswith("docs/") and name.endswith(".md") for name in relative)


@pytest.mark.parametrize(
    ("initial", "operation", "extra", "status", "exit_code", "actions", "final"),
    [
        ("satisfied", "check", [], "ready", 0, ["check"], "satisfied"),
        (None, "check", [], "action_required", 2, ["check"], None),
        (None, "run", [], "ready", 0, ["check", "install", "check"], "satisfied"),
        ("invalid", "run", [], "ready", 0, ["check", "repair", "check"], "satisfied"),
        (None, "run", ["--dry-run"], "action_required", 2, ["check"], None),
    ],
)
def test_installed_cli_preserves_resource_actions(
    consumer, tmp_path, initial, operation, extra, status, exit_code, actions, final,
):
    item, state, log = stateful_requirement(tmp_path, initial)
    selected = catalog(tmp_path, [item])
    result = cli(consumer, operation, "--catalog-dir", selected, *extra)
    assert result.returncode == exit_code, result.stderr
    assert result.stderr == ""
    response = json.loads(result.stdout)
    assert response["schema"] == "environment-maintenance/result/v2"
    assert response["status"] == status
    assert response["exit_code"] == exit_code
    assert response["operation"] == operation
    assert response["dry_run"] is bool(extra)
    assert log.read_text().splitlines() == actions
    assert (state.read_text() if state.exists() else None) == final


def test_installed_cli_reports_unavailable_without_mutation(consumer, tmp_path):
    check = fixture_action("v1_release_action.py", "unavailable")
    selected = catalog(tmp_path, [requirement(check=check)])
    result = cli(consumer, "run", "--catalog-dir", selected)
    assert result.returncode == 3
    response = json.loads(result.stdout)
    assert response["status"] == "unavailable"
    assert response["requirements"][0]["cause"] == "fixture resource unavailable"
    assert response["requirements"][0]["recommendations"] == ["Prepare the fixture resource"]
    assert "mutation" not in response["requirements"][0]


def test_installed_cli_preserves_failed_mutation_and_final_check(consumer, tmp_path):
    item, state, log = stateful_requirement(tmp_path, None)
    item["install"] = fixture_action("v1_release_action.py", "mutation-fails")
    selected = catalog(tmp_path, [item])
    result = cli(consumer, "run", "--catalog-dir", selected)
    assert result.returncode == 4
    response = json.loads(result.stdout)
    row = response["requirements"][0]
    assert response["status"] == row["status"] == "failed"
    assert row["mutation"]["exit_code"] == 7
    assert row["mutation"]["stderr"] == "fixture mutation failed\n"
    assert log.read_text().splitlines() == ["check", "check"]
    assert not state.exists()


def test_installed_cli_reports_protocol_failure(consumer, tmp_path):
    selected = catalog(tmp_path, [requirement(check=fixture_action("v1_release_action.py", "malformed"))])
    result = cli(consumer, "check", "--catalog-dir", selected)
    assert result.returncode == 4
    response = json.loads(result.stdout)
    assert response["status"] == "failed"
    assert response["requirements"][0]["initial_check"]["status"] == "protocol_failure"


def test_installed_cli_preserves_values_spaces_and_action_stderr(consumer, tmp_path):
    check = fixture_action("v1_release_action.py", "echo-marker", "${marker}")
    selected = catalog(
        tmp_path, [requirement(check=check)],
        parameters={"marker": {"type": "string"}},
    )
    values = tmp_path / "selected values with spaces.json"
    values.write_text(json.dumps({"marker": "value from file"}))
    result = cli(
        consumer, "check", "--catalog-dir", selected, "--values", values,
        "--set", "marker=explicit value with spaces",
    )
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    action = response["requirements"][0]["initial_check"]
    assert response["parameters"] == {"marker": "explicit value with spaces"}
    assert response["parameter_sources"] == {"marker": "cli"}
    assert action["invocation"]["argv"][-1] == "explicit value with spaces"
    assert action["stderr"] == "fixture note: explicit value with spaces\n"
    assert result.stderr == ""


def test_invalid_selected_input_is_cli_refusal_not_action_failure(consumer, tmp_path):
    result = cli(consumer, "check", "--catalog-dir", tmp_path / "absent")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Selected catalog directory does not exist" in result.stderr
