"""Public reading contract against real, independently specified JSON files."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest

import environment_maintenance as public_api


FIXTURES = Path(__file__).parent / "fixtures" / "config-reading"


def reader(name):
    function = getattr(public_api, name, None)
    assert callable(function), f"Missing configuration reader API: {name}"
    return function


def expected(name):
    return json.loads((FIXTURES / "expected" / name).read_text(encoding="utf-8"))


@pytest.fixture
def config(tmp_path):
    root = tmp_path / "workspace with spaces"
    shutil.copytree(FIXTURES / "project", root)
    return root / "setup.json"


def read(config, selection="all", operation="infra"):
    return reader("read_requirements")(config, operation, selection)


def ids(config, operation="infra"):
    return reader("list_requirement_ids")(config, operation)


def replace_document(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


def test_ids_only_in_declared_order(config):
    assert ids(config) == ["database", "queue"]


def test_batch_preserves_requested_order_and_full_objects(config):
    assert read(config, ["queue", "database"]) == expected("infra-batch.json")


def test_repeated_selected_id_is_rejected(config):
    with pytest.raises(ValueError, match="queue"):
        read(config, ["queue", "database", "queue"])


def test_batch_can_select_a_proper_subset(config):
    assert read(config, ["queue"], "infra") == expected("infra-subset.json")


def test_empty_batch_returns_empty_list(config):
    assert read(config, []) == []


def test_unknown_id_reports_error_instead_of_partial_batch(config):
    with pytest.raises(ValueError, match="absent-resource"):
        read(config, ["database", "absent-resource"])


def test_all_returns_complete_objects_in_document_order(config):
    assert read(config) == expected("infra-all.json")


def test_empty_requirements_support_ids_batch_and_all(config):
    replace_document(config.parent / "requirements" / "infra.json", {"requirements": []})
    assert ids(config) == []
    assert read(config) == []
    assert read(config, []) == []


@pytest.mark.parametrize(
    ("operation", "expected_ids", "expected_file"),
    [
        ("infra", ["database", "queue"], "infra-all.json"),
        ("deps", ["composer"], "deps-all.json"),
        ("inspect-custom", ["composer"], "deps-all.json"),
    ],
)
def test_operations_share_the_same_reading_contract(
    config, operation, expected_ids, expected_file
):
    assert ids(config, operation) == expected_ids
    assert read(config, "all", operation) == expected(expected_file)


def test_relative_paths_are_based_on_main_file_not_callers_cwd(config, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert ids(str(config), "deps") == ["composer"]
    assert read(str(config), "all", "deps") == expected("deps-all.json")


def test_explicit_absolute_mapping_works_for_both_read_operations(config):
    document = json.loads(config.read_text(encoding="utf-8"))
    document["operations"]["absolute-custom"] = str(
        config.parent / "requirements" / "deps.json"
    )
    replace_document(config, document)
    assert ids(config, "absolute-custom") == ["composer"]
    assert read(config, "all", "absolute-custom") == expected("deps-all.json")


def test_returned_nested_objects_do_not_change_subsequent_reads(config):
    result = read(config)
    result[0]["payload"]["port"] = 1
    result[1]["payload"]["options"]["durable"] = False
    assert read(config) == expected("infra-all.json")


def test_each_call_reads_current_requirement_file(config):
    assert ids(config) == ["database", "queue"]
    assert read(config) == expected("infra-all.json")
    replace_document(
        config.parent / "requirements" / "infra.json",
        {"requirements": [{"id": "fresh", "payload": {"port": 6655}}]},
    )
    assert ids(config) == ["fresh"]
    assert read(config) == [{"id": "fresh", "payload": {"port": 6655}}]


def test_each_call_reads_current_operation_mapping(config):
    assert ids(config) == ["database", "queue"]
    assert read(config) == expected("infra-all.json")
    document = json.loads(config.read_text(encoding="utf-8"))
    document["operations"]["infra"] = "requirements/deps.json"
    replace_document(config, document)
    assert ids(config) == ["composer"]
    assert read(config) == expected("deps-all.json")


def test_reading_preserves_files_and_literal_payloads_without_processes(config, monkeypatch):
    def unexpected_process(*args, **kwargs):
        pytest.fail("Configuration reading started an external process")

    monkeypatch.setattr(subprocess, "Popen", unexpected_process)
    files = [config, *(config.parent / "requirements").glob("*.json")]
    before = {path: path.read_bytes() for path in files}
    assert ids(config) == ["database", "queue"]
    assert read(config) == expected("infra-all.json")
    assert read(config, "all", "deps") == expected("deps-all.json")
    assert {path: path.read_bytes() for path in files} == before


@pytest.mark.parametrize("operation", ["list_requirement_ids", "read_requirements"])
def test_unknown_operation_is_diagnosed(config, operation):
    function = reader(operation)
    arguments = (config, "unknown-operation")
    if operation == "read_requirements":
        arguments += ("all",)
    with pytest.raises(ValueError, match="unknown-operation"):
        function(*arguments)


@pytest.mark.parametrize("api", ["list_requirement_ids", "read_requirements"])
def test_missing_selected_file_is_diagnosed(config, api):
    function = reader(api)
    document = json.loads(config.read_text(encoding="utf-8"))
    document["operations"]["infra"] = "missing-requirements.json"
    replace_document(config, document)
    arguments = (config, "infra") + (("all",) if api == "read_requirements" else ())
    with pytest.raises(ValueError, match="missing-requirements.json"):
        function(*arguments)


@pytest.mark.parametrize("api", ["list_requirement_ids", "read_requirements"])
def test_invalid_selected_json_is_diagnosed(config, api):
    function = reader(api)
    (config.parent / "requirements" / "infra.json").write_text("not-json", encoding="utf-8")
    arguments = (config, "infra") + (("all",) if api == "read_requirements" else ())
    with pytest.raises(ValueError, match="infra.json"):
        function(*arguments)


@pytest.mark.parametrize("document", [{}, {"operations": []}, {"operations": {"infra": None}}])
def test_invalid_operation_mapping_is_diagnosed(config, document):
    function = reader("list_requirement_ids")
    replace_document(config, document)
    with pytest.raises(ValueError, match="operations|infra"):
        function(config, "infra")


@pytest.mark.parametrize(
    ("document", "context"),
    [
        ({}, "requirements"),
        ({"requirements": {}}, "requirements"),
        ({"requirements": [{}]}, "id"),
        ({"requirements": [{"id": ""}]}, "id"),
        ({"requirements": [{"id": "same"}, {"id": "same"}]}, "same"),
    ],
)
def test_invalid_requirement_shape_and_duplicate_ids_are_diagnosed(config, document, context):
    function = reader("read_requirements")
    replace_document(config.parent / "requirements" / "infra.json", document)
    with pytest.raises(ValueError, match=context):
        function(config, "infra", "all")
