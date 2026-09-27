import json
import os

import pytest

from environment_maintenance.catalogue import ContractError, load_catalog
from environment_maintenance.parameters import expand, resolve
from v2_helpers import action, catalog, requirement


def manifest(root):
    return root / "catalog.json"


def rewrite(root, transform):
    path = manifest(root)
    raw = json.loads(path.read_text(encoding="utf-8"))
    transform(raw)
    path.write_text(json.dumps(raw), encoding="utf-8")


def test_selected_input_is_a_catalog_v2_directory(tmp_path):
    root = catalog(tmp_path)
    loaded = load_catalog(root)
    assert loaded.root == root.resolve()
    assert loaded.manifest_path == (root / "catalog.json").resolve()
    with pytest.raises(ContractError, match="directory"):
        load_catalog(root / "catalog.json")
    with pytest.raises(ContractError, match="directory"):
        load_catalog(tmp_path / "absent")


def test_selected_catalog_symlink_loop_is_contract_error(tmp_path):
    loop = tmp_path / "loop"
    os.symlink("loop", loop)

    with pytest.raises(ContractError, match="catalog directory"):
        load_catalog(loop)


def test_catalog_requires_exact_v2_topology(tmp_path):
    root = catalog(tmp_path)
    manifest = root / "catalog.json"
    raw = json.loads(manifest.read_text())
    raw["unknown"] = True
    manifest.write_text(json.dumps(raw))
    with pytest.raises(ContractError, match="catalog fields"):
        load_catalog(root)


@pytest.mark.parametrize("field", ["schema", "parameters", "inherit_env", "requirements"])
def test_catalog_requires_every_top_level_field(tmp_path, field):
    root = catalog(tmp_path)
    rewrite(root, lambda raw: raw.pop(field))
    with pytest.raises(ContractError, match=field):
        load_catalog(root)


def test_catalog_file_must_exist_and_be_valid_unique_key_json(tmp_path):
    root = tmp_path / "catalog-v2"
    root.mkdir()
    with pytest.raises(ContractError, match="Cannot read"):
        load_catalog(root)
    manifest(root).write_text("not-json", encoding="utf-8")
    with pytest.raises(ContractError, match="Cannot read"):
        load_catalog(root)
    manifest(root).write_text('{"schema":"one","schema":"two"}', encoding="utf-8")
    with pytest.raises(ContractError, match="Duplicate JSON key"):
        load_catalog(root)


@pytest.mark.parametrize("raw", ["null", "[]", '"catalog"', "1", "true"])
def test_catalog_json_top_level_must_be_an_object(tmp_path, raw):
    root = catalog(tmp_path)
    manifest(root).write_text(raw, encoding="utf-8")
    with pytest.raises(ContractError, match="object"):
        load_catalog(root)


def test_catalog_manifest_must_be_a_readable_utf8_file(tmp_path):
    root = tmp_path / "catalog-directory"
    root.mkdir()
    manifest(root).mkdir()
    with pytest.raises(ContractError, match="Cannot read"):
        load_catalog(root)
    manifest(root).rmdir()
    manifest(root).write_bytes(b"\xff\xfe")
    with pytest.raises(ContractError, match="Cannot read"):
        load_catalog(root)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", "environment-maintenance/catalog/v3"),
        ("parameters", []),
        ("inherit_env", {}),
        ("requirements", {}),
    ],
)
def test_catalog_rejects_wrong_schema_and_container_types(tmp_path, field, value):
    root = catalog(tmp_path)
    rewrite(root, lambda raw: raw.__setitem__(field, value))
    with pytest.raises(ContractError):
        load_catalog(root)


@pytest.mark.parametrize(
    "value",
    [[1], [""], ["BAD=NAME"], ["DUP", "DUP"], ["bad\0name"]],
)
def test_inherited_environment_names_are_explicit_and_unique(tmp_path, value):
    root = catalog(tmp_path)
    rewrite(root, lambda raw: raw.__setitem__("inherit_env", value))
    with pytest.raises(ContractError, match="inherit_env"):
        load_catalog(root)


@pytest.mark.parametrize(
    "declaration",
    [
        [],
        {},
        {"type": "unknown"},
        {"type": "string", "default": 1},
        {"type": "number", "default": float("inf")},
        {"type": "string", "env": 1},
        {"type": "string", "env": ""},
        {"type": "string", "env": "BAD=NAME"},
        {"type": "string", "env": "BAD\0NAME"},
        {"type": "string", "secret": "yes"},
        {"type": "string", "extra": True},
    ],
)
def test_parameter_declarations_are_exact_and_typed(tmp_path, declaration):
    root = catalog(tmp_path, parameters={"value": declaration})
    with pytest.raises(ContractError, match="value"):
        load_catalog(root)


@pytest.mark.parametrize("name", ["", "1bad", "bad name", "bad\0name"])
def test_parameter_names_are_valid(tmp_path, name):
    root = catalog(tmp_path, parameters={name: {"type": "string", "default": "x"}})
    with pytest.raises(ContractError, match="parameter"):
        load_catalog(root)


@pytest.mark.parametrize(
    "items",
    [
        [None],
        [{"id": "", "check": {}, "install": {}, "repair": {}}],
        [{"id": 1, "check": {}, "install": {}, "repair": {}}],
        [{"id": "bad id", "check": {}, "install": {}, "repair": {}}],
        [{"id": "bad\0id", "check": {}, "install": {}, "repair": {}}],
        [requirement("same"), requirement("same")],
    ],
)
def test_requirements_are_objects_with_unique_nonempty_ids(tmp_path, items):
    with pytest.raises(ContractError, match="requirement"):
        load_catalog(catalog(tmp_path, items))


def test_requirement_rejects_unknown_nested_fields(tmp_path):
    item = requirement()
    item["legacy"] = True
    with pytest.raises(ContractError, match="requirement fields"):
        load_catalog(catalog(tmp_path, [item]))


@pytest.mark.parametrize("missing", ["check", "install", "repair"])
def test_each_requirement_declares_all_actions(tmp_path, missing):
    item = requirement()
    del item[missing]
    with pytest.raises(ContractError, match=missing):
        load_catalog(catalog(tmp_path, [item]))


@pytest.mark.parametrize("role", ["check", "install", "repair"])
@pytest.mark.parametrize("value", [None, [], "command"])
def test_each_action_must_be_an_object(tmp_path, role, value):
    item = requirement()
    item[role] = value
    with pytest.raises(ContractError, match=role):
        load_catalog(catalog(tmp_path, [item]))


@pytest.mark.parametrize("role", ["check", "install", "repair"])
@pytest.mark.parametrize(
    "missing",
    ["argv", "cwd", "env", "output", "max_output_bytes", "execution_bound_seconds"],
)
def test_each_action_declares_every_execution_boundary(tmp_path, role, missing):
    item = requirement()
    del item[role][missing]
    with pytest.raises(ContractError, match=missing):
        load_catalog(catalog(tmp_path, [item]))


@pytest.mark.parametrize("role", ["check", "install", "repair"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("argv", []),
        ("argv", "echo"),
        ("argv", [""]),
        ("argv", [1]),
        ("argv", ["bad\0command"]),
        ("cwd", 1),
        ("cwd", ""),
        ("cwd", "bad\0cwd"),
        ("env", []),
        ("env", {"": "x"}),
        ("env", {"BAD=NAME": "x"}),
        ("env", {"BAD\0NAME": "x"}),
        ("env", {"NAME": 1}),
        ("env", {"NAME": "bad\0value"}),
        ("output", {}),
        ("output", []),
        ("output", {"schema": ""}),
        ("output", {"schema": "bad\0schema"}),
        ("output", {"schema": 1}),
        ("output", {"schema": "x", "extra": True}),
        ("max_output_bytes", True),
        ("max_output_bytes", "32"),
        ("max_output_bytes", 1.5),
        ("max_output_bytes", -1),
        ("max_output_bytes", float("inf")),
        ("max_output_bytes", 0),
        ("max_output_bytes", 16_777_217),
        ("execution_bound_seconds", True),
        ("execution_bound_seconds", "1"),
        ("execution_bound_seconds", -1),
        ("execution_bound_seconds", float("inf")),
        ("execution_bound_seconds", float("nan")),
        ("execution_bound_seconds", 0),
        ("execution_bound_seconds", 3601),
    ],
)
def test_action_field_types_and_bounds_are_rejected(tmp_path, role, field, value):
    item = requirement()
    item[role][field] = value
    with pytest.raises(ContractError, match=field):
        load_catalog(catalog(tmp_path, [item]))


@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_action_rejects_unknown_nested_field(tmp_path, role):
    item = requirement()
    item[role]["extra"] = True
    with pytest.raises(ContractError, match="action fields"):
        load_catalog(catalog(tmp_path, [item]))


@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_command_is_argv_not_shell_text(tmp_path, role):
    item = requirement()
    item[role] = {
        "command": "echo unsafe",
        "cwd": ".",
        "env": {},
        "output": {"schema": "environment-maintenance/action-result/v2"},
        "max_output_bytes": 100,
        "execution_bound_seconds": 1,
    }
    with pytest.raises(ContractError, match="action fields"):
        load_catalog(catalog(tmp_path, [item]))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_output_bytes", 1),
        ("max_output_bytes", 16_777_216),
        ("execution_bound_seconds", 0.001),
        ("execution_bound_seconds", 3600),
    ],
)
@pytest.mark.parametrize("role", ["check", "install", "repair"])
def test_action_numeric_boundaries_are_accepted(tmp_path, role, field, value):
    item = requirement()
    item[role][field] = value
    assert load_catalog(catalog(tmp_path, [item])).data["requirements"][0][role][field] == value


def test_long_canonical_commands_must_be_utf8_fixtures():
    with pytest.raises(AssertionError, match="UTF-8 fixture"):
        action("x" * 100)


def test_order_is_preserved(tmp_path):
    loaded = load_catalog(catalog(tmp_path, [requirement("first"), requirement("second")]))
    assert [item["id"] for item in loaded.data["requirements"]] == ["first", "second"]


def test_typed_parameters_and_one_pass_expansion():
    spec = {
        "root": {"type": "string", "default": "default", "env": "ROOT"},
        "count": {"type": "integer"},
        "ratio": {"type": "number", "default": 1.5},
        "enabled": {"type": "boolean", "default": True},
    }
    values, origins = resolve(spec, {"count": 1}, {"ROOT": "environment"}, ["count=2"])
    assert values == {"root": "environment", "count": 2, "ratio": 1.5, "enabled": True}
    assert origins == {
        "root": "environment",
        "count": "cli",
        "ratio": "default",
        "enabled": "default",
    }
    assert expand(["${root}", "${literal}"], {"root": "${literal}", "literal": "done"}) == [
        "${literal}",
        "done",
    ]


@pytest.mark.parametrize(
    ("spec", "values", "overrides"),
    [
        ({"x": {"type": "integer"}}, {"x": True}, []),
        ({"x": {"type": "number"}}, {"x": float("inf")}, []),
        ({"x": {"type": "string"}}, {"x": "bad\0value"}, []),
        ({"x": {"type": "integer"}}, {}, ["x=not-json"]),
        ({"x": {"type": "integer"}}, {}, ["broken"]),
        ({"x": {"type": "integer", "env": "X"}}, {}, []),
        ({"x": {"type": "string"}}, {}, []),
        ({}, {"unknown": 1}, []),
        ({}, {}, ["unknown=1"]),
    ],
)
def test_invalid_values_and_overrides_are_rejected(spec, values, overrides):
    environ = {"X": "not-json"} if spec.get("x", {}).get("env") else {}
    with pytest.raises(ContractError):
        resolve(spec, values, environ, overrides)


def test_unknown_parameter_fails_before_execution(tmp_path):
    item = requirement()
    item["install"]["argv"].append("${missing}")
    loaded = load_catalog(catalog(tmp_path, [item]))
    from environment_maintenance.engine import execute

    with pytest.raises(ContractError, match="Unknown placeholder"):
        execute(loaded, "run", environ={})


@pytest.mark.parametrize("role", ["check", "install", "repair"])
@pytest.mark.parametrize("location", ["argv", "cwd", "env"])
def test_complete_catalog_is_expanded_before_first_command(tmp_path, role, location):
    sentinel = tmp_path / "executed"
    first = requirement(
        "first",
        check=action(
            "import pathlib;pathlib.Path('${sentinel}').write_text('ran')",
        ),
    )
    second = requirement("second")
    if location == "argv":
        second[role]["argv"].append("${missing}")
    elif location == "cwd":
        second[role]["cwd"] = "${missing}"
    else:
        second[role]["env"]["VALUE"] = "${missing}"
    root = catalog(
        tmp_path,
        [first, second],
        parameters={"sentinel": {"type": "string", "default": str(sentinel)}},
    )
    with pytest.raises(ContractError, match="Unknown placeholder"):
        from environment_maintenance.engine import execute

        execute(load_catalog(root), "run", environ={})
    assert not sentinel.exists()


def test_typed_parameters_expand_into_argv_cwd_and_env_at_execution(tmp_path):
    from environment_maintenance.engine import execute
    from v2_helpers import fixture_action

    observed = tmp_path / "observed.json"
    execution_root = tmp_path / "execution-root"
    execution_root.mkdir()
    selected = fixture_action(
        "capture_execution.py",
        observed,
        "check",
        "${text}",
        "${integer}",
        "${number}",
        "${boolean}",
        cwd="${workdir}",
        env={"DECLARED": "${text}", "COLLISION": "declared"},
    )
    root = catalog(
        tmp_path,
        [requirement(check=selected)],
        parameters={
            "text": {"type": "string", "default": "default", "env": "TEXT"},
            "integer": {"type": "integer"},
            "number": {"type": "number", "default": 1.25},
            "boolean": {"type": "boolean", "default": False},
            "workdir": {"type": "string", "default": str(execution_root)},
        },
        inherit_env=["ALLOWED", "COLLISION"],
    )
    result = execute(
        load_catalog(root),
        "check",
        values={"integer": 7},
        overrides=["text=\"cli\"", "boolean=true"],
        environ={"TEXT": "environment", "ALLOWED": "host", "COLLISION": "host"},
    )
    assert result["status"] == "ready"
    payload = json.loads(observed.read_text(encoding="utf-8"))
    assert payload == {
        "argv": ["cli", "7", "1.25", "true"],
        "cwd": str(execution_root),
        "environment": {
            "ALLOWED": "host",
            "COLLISION": "declared",
            "DECLARED": "cli",
        },
    }
