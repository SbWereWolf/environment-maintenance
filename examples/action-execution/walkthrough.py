"""Корректные вызовы API на собственных временных данных."""

from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from environment_maintenance import execute_action, plan_action, read_requirements


class JsonInterpreter:
    def __init__(self):
        self.calls = 0

    def interpret(self, raw, options):
        self.calls += 1
        data = json.loads(raw["stdout"])
        success = data["state"] == options["expected"]
        return dict(success=success, value=data,
                    error=None if success else "resource is not ready", source="json")


class ExitInterpreter:
    def __init__(self):
        self.calls = 0

    def interpret(self, raw, options):
        self.calls += 1
        success = raw["exit_code"] in options["accept"]
        return dict(success=success, value=raw["exit_code"],
                    error=None if success else "process failed", source="exit")


class SummaryInterpreter:
    def interpret(self, raw, options):
        data = json.loads(raw["stdout"])
        success = data["state"] == options["expected"]
        return dict(success=success, value=[data["state"], False, 0],
                    error=None if success else "resource is not ready", source="summary")


def example_inputs(workspace):
    """Учебные входы; это не дополнительный API библиотеки."""
    config = Path(__file__).absolute().parent / "app.example.json"
    action = read_requirements(config, "infra", ["demo"])[0]
    parameters = dict(python=sys.executable, workspace=str(workspace),
                      marker=str(workspace / "steps.txt"), state="ready", value="demo")
    return action, parameters, {"json": JsonInterpreter(), "exit": ExitInterpreter()}


def main():
    examples = Path(__file__).absolute().parent
    configs = [examples / name for name in ("app.example.json", "infra.example.json")]
    original_files = [path.read_bytes() for path in configs]
    # Временный каталог принадлежит примеру и удаляется при выходе.
    with TemporaryDirectory(prefix="action example ", dir=examples) as temporary:
        workspace = Path(temporary)
        action, parameters, interpreters = example_inputs(workspace)
        original_inputs = deepcopy((action, parameters))
        marker = workspace / "steps.txt"
        plan = plan_action(action, parameters, base_dir=workspace, interpreters=interpreters)
        assert len(plan["commands"]) == 2 and not marker.exists()
        assert all(item.calls == 0 for item in interpreters.values())
        assert plan["commands"][0]["argv"][0] == sys.executable
        assert plan["commands"][0]["cwd"] == str(workspace)
        assert plan["commands"][0]["env"] == {"VALUE": "demo"}
        print("plan: 2 commands; no effects")

        result = execute_action(action, parameters, base_dir=workspace, interpreters=interpreters)
        assert result["status"] == "succeeded" and result["error"] is None
        assert marker.read_text(encoding="utf-8") == "first\nsecond\n"
        assert len(result["commands"]) == 2
        for prepared, record in zip(plan["commands"], result["commands"], strict=True):
            assert record["invocation"] == {key: prepared[key] for key in ("argv", "cwd", "env")}
            assert type(record["exit_code"]) is int and record["exit_code"] == 0
            assert record["interpreter"] == prepared["interpreter"]
        assert result["commands"][0]["stdout"] == b'{"state": "ready", "value": "demo"}\n'
        assert result["commands"][0]["stderr"] == b""
        assert result["commands"][1]["stdout"] == b"\xffready\x00\n"
        assert result["commands"][1]["stderr"] == b"diagnostic\n"
        print("execute: succeeded; full bytes retained")

        interpreters["json"] = SummaryInterpreter()
        replaced = execute_action(action, parameters, base_dir=workspace, interpreters=interpreters)
        assert replaced["status"] == "succeeded"
        answer = replaced["commands"][0]["interpretation"]
        assert answer["value"] == ["ready", False, 0] and answer["source"] == "summary"
        assert type(answer["value"][1]) is bool and type(answer["value"][2]) is int
        assert replaced["commands"][0]["interpreter"]["name"] == "json"
        print("replace: same configured name; another implementation")

        # Корректная проверка сообщает обычную предметную неготовность ресурса.
        busy = dict(parameters, state="busy")
        interpreters["json"] = JsonInterpreter()
        exit_calls = interpreters["exit"].calls
        failed = execute_action(action, busy, base_dir=workspace, interpreters=interpreters)
        assert failed["status"] == "failed" and len(failed["commands"]) == 1
        assert failed["error"] == failed["commands"][0]["error"]
        assert failed["commands"][0]["exit_code"] == 0
        assert failed["commands"][0]["stdout"] == b'{"state": "busy", "value": "demo"}\n'
        assert failed["commands"][0]["interpretation"]["success"] is False
        assert marker.read_text(encoding="utf-8") == "first\n"
        assert interpreters["exit"].calls == exit_calls
        assert (action, parameters) == original_inputs
        print("outcome: failed; later command not started")
    assert [path.read_bytes() for path in configs] == original_files


if __name__ == "__main__":
    main()
