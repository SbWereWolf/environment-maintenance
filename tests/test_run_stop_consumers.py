"""Actual consumer publishers and forwarding owners; effects use only own fixture groups."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from run_stop_support import FIXTURES, ROOT, Lab, application, fixture, write
from npm_delivery_support import living_group
from consumer_command_contract import assert_command_meanings


@pytest.fixture
def subjects():
    path = Path(os.environ["EM_RUN_STOP_CONSUMER_INPUTS"]).resolve()
    values = json.loads(path.read_text())
    assert set(values) == {"erp", "poise-op", "stride", "workspace-recover"}
    for row in values.values():
        for key in ("python", "spec"):
            assert Path(row[key]).is_file(), "Prepare actual consumer inputs: " + row[key]
        assert Path(row["source"]).is_dir()
    return path, values


def subject_call(subjects, name, mode, directory, *args, pythonpath=None):
    path, descriptors = subjects
    row = descriptors[name]
    env = dict(os.environ, PYTHONPATH=pythonpath or row["module_path"])
    argv = [row["python"], "-B", str(FIXTURES / "consumer_subject.py"),
            mode, str(path), name, str(directory), *map(str, args)]
    result = subprocess.run(argv, cwd=directory.parent, env=env,
                            capture_output=True, timeout=30)
    prefix = directory.parent / (name + "-" + mode)
    prefix.with_suffix(".stdout").write_bytes(result.stdout)
    prefix.with_suffix(".stderr").write_bytes(result.stderr)
    write(prefix.with_suffix(".json"), {"argv": argv, "cwd": str(directory.parent),
                                      "exit_code": result.returncode})
    return result


@pytest.mark.parametrize("name", ["erp", "poise-op", "stride", "workspace-recover"])
def test_actual_consumer_component_infrastructure(subjects, tmp_path, name):
    result = subject_call(subjects, name, "imports", tmp_path / "profile")
    assert result.returncode == 0 and result.stdout.strip() == b"Consumer components imported", result.stderr


def source_command_rows(subjects, name):
    descriptor = subjects[1][name]
    spec = json.loads(Path(descriptor["spec"]).read_text())
    key = "operation_documents" if descriptor["kind"] == "profile" else "documents"
    declaration = next(row for row in spec[key] if row["destination"] == "run.json")
    document = json.loads((Path(descriptor["source"]) / declaration["source"]).read_text())
    # The before-migration source is an independent input for oracle controls.
    # This does not add a legacy document route to the application under test.
    return document["applications"] if "applications" in document else document["requirements"]


@pytest.mark.parametrize("name", ["erp", "poise-op", "stride", "workspace-recover"])
def test_before_source_commands_match_independent_meaning_contract(subjects, name):
    assert_command_meanings(name, source_command_rows(subjects, name))


def test_meaning_guard_rejects_actual_erp_stale_target(subjects):
    rows = source_command_rows(subjects, "erp")
    wrong = next(row for row in rows if row["id"] == "system-admin-web")
    argv = wrong["commands"][-1]["argv"]
    argv[argv.index("run-process") + 1] = "calculation-service-web"
    with pytest.raises(AssertionError, match="erp/system-admin-web: wrong executable/action/target"):
        assert_command_meanings("erp", rows)


def test_meaning_guard_rejects_swapped_erp_application_commands(subjects):
    rows = source_command_rows(subjects, "erp")
    rows[0]["commands"], rows[1]["commands"] = rows[1]["commands"], rows[0]["commands"]
    with pytest.raises(AssertionError, match="erp/planning-workspace-web: wrong executable/action/target"):
        assert_command_meanings("erp", rows)


@pytest.mark.parametrize("name", ["poise-op", "stride", "workspace-recover"])
def test_meaning_guard_rejects_another_consumers_target(subjects, name):
    rows = source_command_rows(subjects, name)
    argv = rows[0]["commands"][-1]["argv"]
    if name == "workspace-recover":
        argv[-2] = "${repository}/bin/other-application.mjs"
    else:
        argv[-1] = "${profile_root}/other-instance.json"
    with pytest.raises(AssertionError, match="wrong executable/action/target"):
        assert_command_meanings(name, rows)


@pytest.mark.parametrize("name", ["erp", "poise-op", "stride", "workspace-recover"])
@pytest.mark.parametrize("defect", ["cwd", "environment"])
def test_meaning_guard_rejects_wrong_launch_context(subjects, name, defect):
    rows = source_command_rows(subjects, name)
    command = rows[0]["commands"][-1]
    if defect == "cwd":
        command["cwd"] = "${other_repository}"
    else:
        key = "DISPLAY" if name == "erp" else "PATH" if name == "workspace-recover" else "PYTHONPATH"
        del command["env"][key]
    with pytest.raises(AssertionError, match="wrong working directory|wrong environment"):
        assert_command_meanings(name, rows)


def test_meaning_guard_rejects_another_erp_apps_logs(subjects):
    rows = source_command_rows(subjects, "erp")
    argv = rows[0]["commands"][-1]["argv"]
    argv[argv.index("--stdout-log") + 1] = "${console_log_directory}/system-admin-web.stdout"
    with pytest.raises(AssertionError, match="erp/planning-workspace-web: wrong --stdout-log"):
        assert_command_meanings("erp", rows)


@pytest.mark.parametrize("name", ["erp", "poise-op", "stride", "workspace-recover"])
def test_actual_published_profile_preserves_selection_and_works_with_run_stop(subjects, tmp_path, name):
    output = tmp_path / "published"
    completed = subject_call(subjects, name, "publish", output)
    assert completed.returncode == 0, completed.stderr
    main_path = output / subjects[1][name]["main"]
    main = json.loads(main_path.read_text())
    assert set(main["operations"]) >= {"infra", "deps", "check", "run"}
    assert "requirements" not in main.get("invocation", {})
    for operation, expected in fixture("consumer-selections.json")[name].items():
        document = json.loads((output / main["operations"][operation]).read_text())
        assert [row["id"] for row in document["requirements"]] == expected
    run_path = output / main["operations"]["run"]
    assert run_path.resolve().is_relative_to(output.resolve())
    run = json.loads(run_path.read_text())
    assert "requirements" not in run
    ids = fixture("consumer-ids.json")[name]
    assert [row["id"] for row in run["applications"]] == ids
    assert_command_meanings(name, run["applications"])
    interpreted = subject_call(subjects, name, "interpret", output)
    assert interpreted.returncode == 0, interpreted.stderr
    assert interpreted.stdout.strip() == b"Declared final interpreters accept submitted groups"
    lab = Lab(tmp_path / "effects")
    try:
        # Preserve actual published mappings, document metadata and IDs. Replace
        # only serviced commands and interpreter binding with safe fixture work.
        for row in run["applications"]:
            row["commands"] = application(row["id"])["commands"]
        write(run_path, run)
        main["interpreters"] = fixture("main.json")["interpreters"]
        main["invocation"] = {"parameters": str(lab.values), "base_dir": str(lab.root)}
        write(main_path, main)
        before = run_path.read_bytes()
        chosen = ids[0]
        result = lab.answer("run", "--config", main_path, "--env", name, "--app", chosen)
        group = lab.started(chosen)["pgid"]
        assert result["applications"][0]["pgid"] == group and living_group(group)
        assert result["planned"] == result["received_pgids"] == 1
        final = lab.answer("stop", "--env", name, "--app", chosen)
        assert final["stopped"] == [{"environment": name, "id": chosen, "pgid": group}]
        lab.dead(group)
        assert run_path.read_bytes() == before
    finally:
        lab.close()


@pytest.mark.parametrize("name", ["poise-op", "stride"])
def test_actual_maintenance_forwarder_preserves_new_argv_and_result(subjects, tmp_path, name):
    lab = Lab(tmp_path)
    try:
        row = subjects[1][name]
        pythonpath = os.pathsep.join([str(ROOT / "src"), str(FIXTURES), row["module_path"]])
        result = subject_call(subjects, name, "forward", lab.root,
            "run", "list", "--config", lab.main, "--parameters", lab.values,
            "--base-dir", lab.root, pythonpath=pythonpath)
        assert result.returncode == 0, result.stderr
        actual = json.loads(result.stdout)
        assert actual["operation"] == "run-list" and actual["applications"] == {"A": {"pgid": None}, "B": {"pgid": None}, "C": {"pgid": None}}
        assert lab.labels() == [] and not lab.store.exists()
    finally:
        lab.close()
