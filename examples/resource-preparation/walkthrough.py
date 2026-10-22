"""Корректные API/CLI вызовы с собственными временными конфигами и эффектами."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from environment_maintenance import prepare_resources
from interpreters import ExitResult, OpaqueResult

EXAMPLES = Path(__file__).resolve().parent
SOURCE = EXAMPLES.parents[1]


def prepare_demo(workspace):
    """Материалы инструкции; не дополнительный публичный API приложения."""
    workspace = Path(workspace).absolute()
    for name in ("app", "infra", "deps"):
        shutil.copyfile(EXAMPLES / (name + ".example.json"),
                        workspace / (name + ".example.json"))
    parameters = dict(python=sys.executable, probe=str(EXAMPLES / "probe.py"),
                      events=str(workspace / "events.jsonl"),
                      token="demo value", state="ready")
    (workspace / "values.json").write_text(json.dumps(parameters), encoding="utf-8")
    return workspace / "app.example.json", parameters, {"result": ExitResult()}


def cli(config, workspace, operation, selection):
    command = [sys.executable, "-B", "-m", "environment_maintenance", operation,
               "--config", str(config), "--parameters", str(workspace / "values.json"),
               "--base-dir", str(workspace), "--requirements", selection]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(SOURCE / "src"), str(EXAMPLES))))
    return subprocess.run(command, cwd=SOURCE, env=env, capture_output=True, check=False)


def assert_events(workspace, labels):
    path = workspace / "events.jsonl"
    actual = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    assert actual == [dict(label=label, value="demo value") for label in labels]


def clear_events(workspace):
    (workspace / "events.jsonl").unlink(missing_ok=True)


def assert_result(result, identifiers, labels, workspace, *, encoded=False):
    assert result["status"] == "succeeded" and result["error"] is None
    assert [row["id"] for row in result["requirements"]] == identifiers
    commands = [command for row in result["requirements"] for command in row["result"]["commands"]]
    assert len(commands) == len(labels)
    for command, label in zip(commands, labels, strict=True):
        assert command["invocation"] == dict(
            argv=[sys.executable, str(EXAMPLES / "probe.py"), str(workspace / "events.jsonl"), label, "ready"],
            cwd=str(workspace), env={"VALUE": "demo value"})
        assert command["exit_code"] == 0 and command["error"] is None
        for field, expected in (("stdout", b"\xff" + label.encode() + b"\x00\n"),
                                ("stderr", b"diagnostic:" + label.encode() + b"\n")):
            value = command[field]
            if encoded:
                assert value["encoding"] == "base64"
                value = base64.b64decode(value["data"], validate=True)
            assert type(value) is bytes and value == expected
    assert_events(workspace, labels)


def main():
    originals = {path: path.read_bytes() for path in EXAMPLES.glob("*.example.json")}
    with TemporaryDirectory(prefix="preparation example ") as temporary:
        workspace = Path(temporary)
        config, parameters, registry = prepare_demo(workspace)
        result = prepare_resources(config, "infra", "all", parameters,
                                   base_dir=workspace, interpreters=registry)
        assert_result(result, ["assets", "later"], ["install", "configure", "later"], workspace)
        print("api infra: install, configure, later; full bytes")
        clear_events(workspace)
        result = prepare_resources(config, "deps", "all", parameters,
                                   base_dir=workspace, interpreters=registry)
        assert_result(result, ["packages"], ["dependencies"], workspace)
        print("api deps: separate configuration")
        clear_events(workspace)
        result = prepare_resources(config, "infra", ["later", "assets", "later"], parameters,
                                   base_dir=workspace, interpreters=registry)
        assert_result(result, ["later", "assets", "later"], ["later", "install", "configure", "later"], workspace)
        clear_events(workspace)
        result = prepare_resources(config, "infra", [], parameters,
                                   base_dir=workspace, interpreters=registry)
        assert_result(result, [], [], workspace)
        print("selection: ordered IDs, repeats, empty without effects")
        registry["result"] = OpaqueResult()
        result = prepare_resources(config, "deps", "all", parameters,
                                   base_dir=workspace, interpreters=registry)
        assert result["requirements"][0]["result"]["commands"][0]["interpretation"]["value"] == b"\xffdependencies\x00\n"
        assert_events(workspace, ["dependencies"])
        print("plugin: same name; opaque API value")
        for operation, identifiers, labels in (
            ("infra", ["assets", "later"], ["install", "configure", "later"]),
            ("deps", ["packages"], ["dependencies"]),
        ):
            clear_events(workspace)
            process = cli(config, workspace, operation, "all")
            assert process.returncode == 0 and process.stderr == b""
            assert process.stdout.endswith(b"\n") and len(process.stdout.splitlines()) == 1
            assert_result(json.loads(process.stdout), identifiers, labels, workspace, encoded=True)
            print("cli " + operation + ": exit0; full streams decoded")
        clear_events(workspace)
        busy = dict(parameters, state="busy")
        (workspace / "values.json").write_text(json.dumps(busy), encoding="utf-8")
        process = cli(config, workspace, "infra", "all")
        assert process.returncode == 1 and process.stderr == b""
        result = json.loads(process.stdout)
        assert result["operation"] == "infra" and result["status"] == "failed"
        assert [row["id"] for row in result["requirements"]] == ["assets"]
        commands = result["requirements"][0]["result"]["commands"]
        assert len(commands) == 1 and commands[0]["exit_code"] == 3
        assert commands[0]["interpretation"]["error"] == "resource is not ready"
        assert base64.b64decode(commands[0]["stdout"]["data"]) == b"\xffinstall\x00\n"
        assert base64.b64decode(commands[0]["stderr"]["data"]) == b"diagnostic:install\n"
        assert_events(workspace, ["install"])
        print("outcome: exit1; partial work retained; later not started")
    assert all(path.read_bytes() == raw for path, raw in originals.items())


if __name__ == "__main__":
    main()
