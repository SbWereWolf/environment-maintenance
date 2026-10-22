"""Public write contract: real files, independent expectations, no product patcher."""

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

import pytest

import environment_maintenance as public_api


FIXTURES = Path(__file__).parent / "fixtures" / "config-editing"
WRITERS = (
    "add_requirement",
    "update_requirement",
    "delete_requirement",
    "clear_requirements",
)


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def writer(name):
    function = getattr(public_api, name, None)
    assert callable(function), f"Missing configuration writer API: {name}"
    return function


@pytest.fixture
def config(tmp_path, monkeypatch):
    root = tmp_path / "workspace with spaces"
    shutil.copytree(FIXTURES / "project", root)

    def unexpected_process(*args, **kwargs):
        pytest.fail("Configuration editing started an external process")

    monkeypatch.setattr(subprocess, "Popen", unexpected_process)
    return root / "app.json"


def selected(config, operation="infra"):
    return config.parent / "documents" / (
        "infra.json" if operation == "infra" else "deps.json"
    )


def snapshots(config):
    return {p: p.read_bytes() for p in [config, *sorted((config.parent / "documents").glob("*.json"))]}


def expected_infra(*objects):
    # Assemble separately authored literals, never apply the tested patch to an input.
    document = fixture("expected-frame.json")
    document["requirements"] = list(objects)
    return document


def assert_json_equal(actual, expected):
    # JSON types matter: Python equality alone equates False with 0 and True with 1.
    assert json.dumps(actual, ensure_ascii=False, sort_keys=True) == json.dumps(
        expected, ensure_ascii=False, sort_keys=True
    )


def assert_error_context(error, *references):
    message = str(error).casefold()
    assert any(
        reference and re.search(
            r"(?<!\w)" + re.escape(reference.casefold()) + r"(?!\w)", message
        )
        for reference in references
    ), f"Diagnostic has no input-related context: {str(error)!r}"


def assert_saved(config, expected, before, operation="infra"):
    path = selected(config, operation)
    assert_json_equal(json.loads(path.read_text(encoding="utf-8")), expected)
    assert_json_equal(public_api.read_requirements(config, operation, "all"), expected["requirements"])
    assert public_api.list_requirement_ids(config, operation) == [x["id"] for x in expected["requirements"]]
    assert {p: p.read_bytes() for p in before if p != path} == {
        p: value for p, value in before.items() if p != path
    }


def write_input(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


def arguments(name):
    if name == "add_requirement":
        return [fixture("new-requirement.json")]
    if name == "update_requirement":
        return ["subject", [{"op": "replace", "path": "/data/port", "value": 6655}]]
    if name == "delete_requirement":
        return ["subject"]
    return []


def test_add_appends_complete_object_and_keeps_input(config):
    function = writer("add_requirement")
    new = fixture("new-requirement.json")
    original_argument = deepcopy(new)
    before = snapshots(config)
    assert function(config, "infra", new) is None
    assert new == original_argument
    originals = fixture("expected-original-objects.json")
    assert_saved(config, expected_infra(*originals, fixture("new-requirement.json")), before)
    assert public_api.read_requirements(config, "infra", ["added"]) == [fixture("new-requirement.json")]


def test_add_to_empty_document(config):
    function = writer("add_requirement")
    write_input(selected(config), fixture("expected-frame.json"))
    before = snapshots(config)
    assert function(config, "infra", fixture("new-requirement.json")) is None
    assert_saved(config, expected_infra(fixture("new-requirement.json")), before)


@pytest.mark.parametrize("case", fixture("update-cases.json"), ids=lambda c: c["name"])
def test_update_selected_data_and_commands(config, case):
    function = writer("update_requirement")
    changes = deepcopy(case["changes"])
    before_argument = deepcopy(changes)
    before = snapshots(config)
    assert function(config, "infra", "subject", changes) is None
    assert_json_equal(changes, before_argument)
    sibling = fixture("expected-original-objects.json")[1]
    assert_saved(config, expected_infra(case["expected"], sibling), before)
    assert public_api.read_requirements(config, "infra", [case["expected"]["id"]]) == [case["expected"]]
    if case["expected"]["id"] != "subject":
        with pytest.raises(ValueError, match="subject"):
            public_api.read_requirements(config, "infra", ["subject"])


@pytest.mark.parametrize("identifier", ["subject", "sibling"])
def test_delete_only_selected_requirement(config, identifier):
    function = writer("delete_requirement")
    before = snapshots(config)
    assert function(config, "infra", identifier) is None
    originals = fixture("expected-original-objects.json")
    survivor = originals[1] if identifier == "subject" else originals[0]
    assert_saved(config, expected_infra(survivor), before)
    with pytest.raises(ValueError, match=identifier):
        public_api.read_requirements(config, "infra", [identifier])


def test_clear_keeps_document_metadata_and_can_repeat(config):
    function = writer("clear_requirements")
    before = snapshots(config)
    assert function(config, "infra") is None
    assert_saved(config, fixture("expected-frame.json"), before)
    assert function(config, "infra") is None
    assert_saved(config, fixture("expected-frame.json"), before)


@pytest.mark.parametrize("operation", ["deps", "custom", "absolute"])
@pytest.mark.parametrize("name", WRITERS)
def test_each_writer_uses_selected_configuration_from_other_cwd(config, operation, name, tmp_path, monkeypatch):
    function = writer(name)
    if operation == "absolute":
        main = json.loads(config.read_text(encoding="utf-8"))
        main["operations"]["absolute"] = str(selected(config, "deps"))
        write_input(config, main)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    before = snapshots(config)
    expected = {"requirements": [], "metadata": {"owner": "dependencies", "keep": True}}
    composer = fixture("project/documents/deps.json")["requirements"][0]
    if name == "add_requirement":
        args = [fixture("new-requirement.json")]
        expected["requirements"] = [composer, fixture("new-requirement.json")]
    elif name == "update_requirement":
        args = ["composer", [{"op": "replace", "path": "", "value": {"id": "renewed", "only": True}}]]
        expected["requirements"] = [{"id": "renewed", "only": True}]
    elif name == "delete_requirement":
        args = ["composer"]
    else:
        args = []
    assert function(str(config), operation, *args) is None
    assert_saved(config, expected, before, operation)


def test_writer_reads_current_selected_document(config):
    function = writer("add_requirement")
    assert function(config, "infra", fixture("new-requirement.json")) is None
    write_input(selected(config), fixture("expected-frame.json"))
    before = snapshots(config)
    # A cached pre-write list would still contain this ID and incorrectly reject it.
    assert function(config, "infra", fixture("new-requirement.json")) is None
    assert_saved(config, expected_infra(fixture("new-requirement.json")), before)


def test_writer_reads_current_main_mapping(config):
    function = writer("clear_requirements")
    assert function(config, "infra") is None
    write_input(selected(config), fixture("project/documents/infra.json"))
    main = json.loads(config.read_text(encoding="utf-8"))
    main["operations"]["infra"] = "documents/deps.json"
    write_input(config, main)
    before = snapshots(config)
    assert function(config, "infra") is None
    assert json.loads(selected(config, "deps").read_text()) == {
        "requirements": [], "metadata": {"owner": "dependencies", "keep": True}
    }
    assert selected(config).read_bytes() == before[selected(config)]
    assert config.read_bytes() == before[config]


@pytest.mark.parametrize("case", fixture("invalid-changes.json"), ids=lambda c: c["name"])
def test_invalid_update_and_late_failure_preserve_all_files(config, case):
    function = writer("update_requirement")
    changes = deepcopy(case["changes"])
    original_argument = deepcopy(changes)
    before = snapshots(config)
    with pytest.raises(ValueError) as error:
        function(config, "infra", "subject", changes)
    references = [selected(config).name, "subject", "infra", "update_requirement",
                  "changes", "op", "path", "value", "id"]
    if isinstance(changes, list):
        for change in changes:
            if isinstance(change, dict):
                references.extend(change[key] for key in ("op", "path")
                                  if isinstance(change.get(key), str) and change[key])
    assert_error_context(error.value, *references)
    assert_json_equal(changes, original_argument)
    assert snapshots(config) == before


@pytest.mark.parametrize("name", ["update_requirement", "delete_requirement"])
def test_unknown_selected_id_is_diagnosed_without_changes(config, name):
    function = writer(name)
    args = ["absent", []] if name == "update_requirement" else ["absent"]
    before = snapshots(config)
    with pytest.raises(ValueError, match="absent"):
        function(config, "infra", *args)
    assert snapshots(config) == before


@pytest.mark.parametrize("requirement", [None, [], {}, {"id": ""}, {"id": 7}, {"id": "subject"}])
def test_invalid_or_duplicate_added_requirement_preserves_files(config, requirement):
    function = writer("add_requirement")
    original_argument = deepcopy(requirement)
    before = snapshots(config)
    with pytest.raises(ValueError) as error:
        function(config, "infra", requirement)
    assert_error_context(error.value, selected(config).name, "infra",
                         "add_requirement", "requirement", "id")
    assert_json_equal(requirement, original_argument)
    assert snapshots(config) == before


@pytest.mark.parametrize("name", WRITERS)
def test_unknown_operation_preserves_files(config, name):
    function = writer(name)
    before = snapshots(config)
    with pytest.raises(ValueError, match="absent-operation"):
        function(config, "absent-operation", *arguments(name))
    assert snapshots(config) == before


@pytest.mark.parametrize("document", [{}, {"requirements": {}}, {"requirements": [None]}, {"requirements": [{"id": "same"}, {"id": "same"}]}])
@pytest.mark.parametrize("name", WRITERS)
def test_invalid_selected_document_preserves_all_bytes(config, name, document):
    function = writer(name)
    write_input(selected(config), document)
    before = snapshots(config)
    with pytest.raises(ValueError) as error:
        function(config, "infra", *arguments(name))
    references = [selected(config).name, "infra", name, "requirements"]
    if isinstance(document.get("requirements"), list):
        references.extend(item["id"] for item in document["requirements"]
                          if isinstance(item, dict) and isinstance(item.get("id"), str))
    assert_error_context(error.value, *references)
    assert snapshots(config) == before


@pytest.mark.parametrize("name", WRITERS)
def test_invalid_json_preserves_bytes(config, name):
    function = writer(name)
    selected(config).write_text("{", encoding="utf-8")
    before = snapshots(config)
    with pytest.raises(ValueError, match="infra.json"):
        function(config, "infra", *arguments(name))
    assert snapshots(config) == before


@pytest.mark.parametrize("name", WRITERS)
def test_invalid_main_mapping_preserves_files(config, name):
    function = writer(name)
    write_input(config, {"operations": []})
    before = snapshots(config)
    with pytest.raises(ValueError, match="operations"):
        function(config, "infra", *arguments(name))
    assert snapshots(config) == before


@pytest.mark.parametrize("name", WRITERS)
def test_missing_selected_file_is_diagnosed(config, name):
    function = writer(name)
    selected(config).unlink()
    before = snapshots(config)
    with pytest.raises(ValueError, match="infra.json"):
        function(config, "infra", *arguments(name))
    assert snapshots(config) == before
    assert not selected(config).exists()


@pytest.mark.skipif(os.name != "posix" or getattr(os, "geteuid", lambda: 0)() == 0,
                    reason="Requires ordinary POSIX non-root file/directory permissions")
@pytest.mark.parametrize("name", WRITERS)
def test_save_refusal_after_readable_valid_input_preserves_bytes(config, name):
    function = writer(name)
    path = selected(config)
    parent = path.parent
    old_file_mode = stat.S_IMODE(path.stat().st_mode)
    old_dir_mode = stat.S_IMODE(parent.stat().st_mode)
    before = snapshots(config)
    try:
        path.chmod(0o444)
        parent.chmod(0o555)
        assert json.loads(path.read_text(encoding="utf-8"))["requirements"][0]["id"] == "subject"
        assert not os.access(path, os.W_OK)
        assert not os.access(parent, os.W_OK)
        with pytest.raises(ValueError, match="infra.json"):
            function(config, "infra", *arguments(name))
        assert snapshots(config) == before
    finally:
        parent.chmod(old_dir_mode)
        path.chmod(old_file_mode)
