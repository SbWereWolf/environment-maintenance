"""CLI grammar, independent selections, current SDK and versioned producer contract."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

import pytest
import environment_maintenance as api

from run_stop_support import Lab, ROOT, FIXTURES, application, fixture, write


@pytest.fixture
def lab(tmp_path):
    instance = Lab(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def test_help_has_six_commands_and_no_historical_flags(lab):
    completed = lab.call("--help")
    assert completed.returncode == 0
    choices = re.search(rb"\{([^{}]+)\}", completed.stdout)
    assert choices and set(choices[1].decode().split(",")) == {
        "infra", "deps", "adjust", "check", "run", "stop"}
    assert b"--catalog-dir" not in completed.stdout
    assert b"--dry-run" not in completed.stdout


@pytest.mark.parametrize("operation,required,absent", fixture("help-flags.json"))
def test_help_lists_applicable_exact_flags(lab, operation, required, absent):
    completed = lab.call(operation, "--help")
    assert completed.returncode == 0
    for flag in required:
        assert flag.encode() in completed.stdout
    for flag in absent:
        assert flag.encode() not in completed.stdout


@pytest.mark.parametrize("operation,labels", fixture("default-effects.json"))
def test_default_all_does_not_require_invocation_preselection(lab, operation, labels):
    before = {path: path.read_bytes() for path in lab.root.glob("*.json")}
    result = lab.answer(operation)
    assert result["status"] == "succeeded" and lab.labels() == labels
    assert all(path.read_bytes() == value for path, value in before.items())


@pytest.mark.parametrize("operation", ["infra", "deps", "adjust", "check", "run", "stop"])
def test_unknown_arguments_warn_without_changing_known_request(lab, operation):
    args = ["--env", "E", "--app", "A"] if operation == "run" else ["--env", "absent"] if operation == "stop" else []
    completed = lab.call(operation, *args, "--unknown-fixture-option", "unused-value")
    assert completed.returncode == 0, completed.stderr
    assert b"--unknown-fixture-option" in completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "succeeded"
    if operation == "run":
        assert result["environment"] == "E" and result["planned"] == 1


def test_check_unknown_requirements_flag_does_not_filter_checks(lab):
    completed = lab.call("check", "--requirements", '["alpha"]')
    assert completed.returncode == 0 and b"--requirements" in completed.stderr
    assert lab.labels() == ["presence-alpha", "presence-beta", "presence-vendor", "extra"]


def test_removed_catalog_mode_is_not_a_source_or_a_compatibility_route(lab):
    catalog = lab.base / "old-catalog"
    catalog.mkdir()
    shutil.copyfile(FIXTURES / "removed-catalog.json", catalog / "catalog.json")
    completed = lab.call("check", "--catalog-dir", catalog)
    assert completed.returncode == 0 and b"--catalog-dir" in completed.stderr
    assert json.loads(completed.stdout)["operation"] == "check"
    assert lab.labels() == ["presence-alpha", "presence-beta", "presence-vendor", "extra"]
    caller = lab.base / "no-main"
    caller.mkdir()
    rejected = lab.call("check", "--catalog-dir", catalog, cwd=caller)
    assert rejected.returncode != 0 and b"start-app.json" in rejected.stderr


def test_removed_dry_run_flag_does_not_suppress_canonical_effects(lab):
    completed = lab.call("infra", "--dry-run")
    assert completed.returncode == 0 and b"--dry-run" in completed.stderr
    assert lab.labels() == ["alpha", "beta"]


def test_missing_cli_ids_warn_skip_and_do_not_expand_to_all(lab):
    selected = lab.call("infra", "--requirements", '["beta","missing","alpha"]')
    assert selected.returncode == 0 and b"missing" in selected.stderr
    assert lab.labels() == ["beta", "alpha"]
    assert [row["id"] for row in json.loads(selected.stdout)["requirements"]] == ["beta", "alpha"]
    lab.events.unlink()
    missing = lab.call("infra", "--requirements", '["missing"]')
    assert missing.returncode == 0 and b"missing" in missing.stderr
    assert json.loads(missing.stdout)["requirements"] == [] and lab.labels() == []


@pytest.mark.parametrize("kind", ["declaration", "selection"])
def test_repeated_ids_reject_the_whole_request_with_context(lab, kind):
    if kind == "declaration":
        path = lab.root / "infra.json"
        value = json.loads(path.read_text())
        value["requirements"].append(value["requirements"][0])
        write(path, value)
        selection = '["beta"]'
    else:
        selection = '["alpha","beta","alpha"]'
    completed = lab.call("infra", "--requirements", selection)
    assert completed.returncode == 2 and lab.labels() == []
    message = (completed.stdout + completed.stderr).decode().casefold()
    assert "alpha" in message
    assert any(word in message for word in ["duplicate", "повтор"])
    assert "infra" in message
    assert any(word in message for word in ["remove", "удал", "unique", "уникал", "assign", "назнач"])


def test_sdk_rejects_repeated_selection_but_preserves_strict_missing_read(lab):
    with pytest.raises(ValueError, match="alpha"):
        api.read_requirements(lab.main, "infra", ["alpha", "beta", "alpha"])
    with pytest.raises(ValueError, match="missing"):
        api.read_requirements(lab.main, "infra", ["alpha", "missing"])
    assert lab.labels() == []


def test_run_read_crud_uses_applications_and_preserves_other_data(lab):
    others = {path: path.read_bytes() for path in lab.root.glob("*.json") if path.name != "run.json"}
    assert api.list_requirement_ids(lab.main, "run") == ["A", "B", "C"]
    api.add_requirement(lab.main, "run", application("D"))
    api.update_requirement(lab.main, "run", "B", [{"op": "add", "path": "/label", "value": "changed"}])
    api.delete_requirement(lab.main, "run", "A")
    actual = json.loads((lab.root / "run.json").read_text())
    assert [row["id"] for row in actual["applications"]] == ["B", "C", "D"]
    assert actual["applications"][0]["label"] == "changed"
    assert actual["owner"]["keep"] == [False, 0, "metadata"] and "requirements" not in actual
    before = (lab.root / "run.json").read_bytes()
    with pytest.raises(ValueError):
        api.add_requirement(lab.main, "run", application("B"))
    assert (lab.root / "run.json").read_bytes() == before
    api.clear_requirements(lab.main, "run")
    assert json.loads((lab.root / "run.json").read_text())["applications"] == []
    assert all(path.read_bytes() == value for path, value in others.items())


def test_only_run_mapping_changes_its_array_name(lab):
    main = json.loads(lab.main.read_text())
    main["operations"]["applications"] = "custom.json"
    write(lab.main, main)
    write(lab.root / "custom.json", {"requirements": [{"id": "custom"}]})
    assert api.list_requirement_ids(lab.main, "applications") == ["custom"]
    assert api.list_requirement_ids(lab.main, "infra") == ["alpha", "beta"]
    assert api.list_requirement_ids(lab.main, "run") == ["A", "B", "C"]


@pytest.mark.parametrize("raw", [b"[]", b"{broken", b"\xff", b'{"requirements":[],"requirements":[]}'])
def test_shared_json_reader_failures_still_precede_external_effects(lab, raw):
    (lab.root / "infra.json").write_bytes(raw)
    with pytest.raises(ValueError):
        api.read_requirements(lab.main, "infra", "all")
    assert lab.labels() == []


def test_full_explicit_source_works_from_foreign_cwd_without_invocation(lab):
    main = json.loads(lab.main.read_text())
    del main["invocation"]
    write(lab.main, main)
    result = lab.answer("infra", "--config", lab.main, "--parameters", lab.values,
                        "--base-dir", lab.root, "--requirements", '["beta"]', cwd=lab.base)
    assert [row["id"] for row in result["requirements"]] == ["beta"]
    assert lab.labels() == ["beta"]


def test_selected_chain_preflight_precedes_all_effects(lab):
    rows = [application("A"), application("B")]
    rows[1]["commands"][0]["argv"].append("${missing-fixture-parameter}")
    lab.run_rows(rows)
    completed = lab.call("run", "--env", "E")
    assert completed.returncode != 0
    assert "missing-fixture-parameter" in (completed.stdout + completed.stderr).decode()
    assert lab.labels() == []


def test_unselected_command_body_is_not_executed_or_preflighted(lab):
    rows = [application("A"), application("B")]
    rows[1]["commands"][0]["argv"] = []
    lab.run_rows(rows)
    result = lab.answer("run", "--env", "E", "--app", "A")
    assert result["received_pgids"] == 1 and lab.labels() == ["A"]


def test_python_and_npm_metadata_identify_one_incompatible_major(lab):
    python = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    npm = json.loads((ROOT / "package.json").read_text())
    assert int(npm["version"].split(".")[0]) > 3
    assert python["version"] == npm["version"] == api.__version__
    assert python["scripts"] == {"start-app": "environment_maintenance.cli:main"}
    assert set(npm["bin"]) == {"start-app"}


def test_executable_preparation_walkthrough_has_no_successful_repeated_selection(lab):
    observed = lab.base / "walkthrough-calls.jsonl"
    completed = subprocess.run([sys.executable, "-B", str(FIXTURES / "observe_walkthrough.py"),
        str(ROOT / "examples/resource-preparation/walkthrough.py"), str(observed)],
        cwd=lab.root, env=lab.env, capture_output=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    calls = [json.loads(line) for line in observed.read_text().splitlines()]
    assert any(row["operation"] == "infra" and row["selection"] == "all" for row in calls)
    assert any(row["operation"] == "deps" and row["selection"] == "all" for row in calls)
    for row in calls:
        selection = row["selection"]
        if isinstance(selection, list) and len(selection) != len(set(selection)):
            assert row["outcome"] == "refused"


def test_old_catalog_executable_example_is_not_shipped():
    assert not (ROOT / "examples/catalog-v2/probe.py").exists()
