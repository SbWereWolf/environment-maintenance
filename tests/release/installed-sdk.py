"""Observe the installed EM/CE facade with a real command and configuration."""
from importlib.metadata import version
import json
from pathlib import Path
import sys
import sysconfig

import command_execution as ce
import environment_maintenance as em
from environment_maintenance.actions.interpreters import exit_result

expected, scratch = sys.argv[1:]
scratch = Path(scratch).absolute()
installed = Path(sysconfig.get_path("purelib"))
assert version("environment-maintenance") == expected
assert version("command-execution") == "2.0.10"
assert all(Path(module.__file__).is_relative_to(installed) for module in (ce, em))
command = {"commands": [{"argv": [sys.executable, "-I", "-c", "print('installed EM')"],
                          "cwd": str(scratch), "env": {}, "interpreter": {"name": "exit", "options": {"accept": [0]}}}]}
result = em.execute_action(command, {}, base_dir=scratch, interpreters={"exit": exit_result})
assert result["status"] == "succeeded"
row, = result["commands"]
assert row["exit_code"] == 0 and row["stdout"] == b"installed EM\n"
config = scratch / "main.json"
operation = scratch / "operation.json"
config.write_text(json.dumps({"operations": {"infra": operation.name}}))
operation.write_text(json.dumps({"requirements": [{"id": "first"}]}))
assert em.list_requirement_ids(config, "infra") == ["first"]
em.add_requirement(config, "infra", {"id": "second"})
assert em.list_requirement_ids(config, "infra") == ["first", "second"]
print("em-installed-sdk-ok")
