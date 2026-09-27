import json
from pathlib import Path
import sys


RESULT_SCHEMA = "environment-maintenance/action-result/v2"
FIXTURES = Path(__file__).parent / "fixtures"


def action(script, *args, cwd=".", env=None, limit=4096, bound=3, output_schema=RESULT_SCHEMA):
    if len(script) > 99:
        raise AssertionError("Canonical inline command exceeds 99 characters; use a UTF-8 fixture")
    return {
        "argv": [sys.executable, "-S", "-c", script, *map(str, args)],
        "cwd": cwd,
        "env": env or {},
        "output": {"schema": output_schema},
        "max_output_bytes": limit,
        "execution_bound_seconds": bound,
    }


def fixture_action(name, *args, **kwargs):
    selected = action("pass", *args, **kwargs)
    selected["argv"] = [sys.executable, "-S", str(FIXTURES / name), *map(str, args)]
    return selected


def result_action(name, **kwargs):
    return fixture_action("emit_result.py", FIXTURES / "results" / name, **kwargs)


def requirement(identifier="sample", *, check=None, install=None, repair=None):
    return {
        "id": identifier,
        "check": check or result_action("check-satisfied.json"),
        "install": install or result_action("install-completed.json"),
        "repair": repair or result_action("repair-completed.json"),
    }


def catalog(tmp_path, requirements=None, parameters=None, inherit_env=None):
    root = tmp_path / "catalog-v2"
    root.mkdir()
    manifest = {
        "schema": "environment-maintenance/catalog/v2",
        "parameters": parameters or {},
        "inherit_env": inherit_env or [],
        "requirements": requirements or [],
    }
    (root / "catalog.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def stateful_requirement(tmp_path, initial):
    state = tmp_path / "state.txt"
    log = tmp_path / "actions.log"
    if initial is not None:
        state.write_text(initial, encoding="utf-8")
    check = fixture_action("state_check.py", state, log)
    install = fixture_action("state_install.py", state, log)
    repair = fixture_action("state_repair.py", state, log)
    return requirement(check=check, install=install, repair=repair), state, log
