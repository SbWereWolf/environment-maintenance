# Shared configuration and command core

<a id="самостоятельный-пакет"></a>
## Shared package

`command-execution` supplies pure JSON/collection/parameter APIs and generic
command coordination. EM imports the selected installed package through its
declared exact dependency. No sibling checkout, ERP, Poise or database is needed.
Application schemas, named interpreters and Unix scripts belong to EM/the caller.

<a id="установка-выбранной-версии"></a>
<a id="installation"></a>
## Select an installation

Use the dependency declared by the chosen EM package. Do not independently
upgrade CE underneath a deployed consumer. Pip resolves the exact dependency
from your selected index or complete offline wheelhouse, including jsonpatch
and jsonpointer. [Install EM](installation.md#установка-готового-wheel) into the
chosen prepared Python; [npm lifecycle](npm-distribution.md) owns its private
environment. Set `MAINTENANCE_LIBRARY_PYTHON` to that installed EM Python for the
examples below.

<a id="совместимые-импорты"></a>
<a id="current-imports"></a>
## Current imports

| Purpose | Import owner |
|---|---|
| File-based configuration read/CRUD | `environment_maintenance` |
| Application plan/action/chain facades | `environment_maintenance` |
| Named exit-code interpreter | `environment_maintenance.actions.interpreters` |
| Interpreter protocol | `environment_maintenance.actions.application` |
| Detached collection/JSON edits | `command_execution.DocumentCollection`, `JSONPathEditor`, `JSONMerger` |
| Generic command plan/execution | `command_execution.CommandPlanner`, `ChainCoordinator` |
| Typed parameter profiles | `command_execution.TemplateRenderer`, `ParameterLookup`, `DeferredResolver` |

Do not import EM's file/action facades from CE2. The [CE guide](https://github.com/SbWereWolf/command-execution/blob/master/docs/usage.md)
describes its public class API. EM retains its own required arguments, dict
result shape and consumer interpretation policy:
[read](configuration-reading.md#публичный-договор),
[edit](configuration-editing.md#публичный-договор),
[actions](action-execution.md#публичные-функции-и-аргументы),
[chains](action-execution.md#цепочки-с-передачей-данных).

```bash
"${MAINTENANCE_LIBRARY_PYTHON:?Select installed EM Python}" -I -B - <<'PY'
from environment_maintenance import plan_action, read_requirements
from environment_maintenance.actions.interpreters import exit_result
assert callable(plan_action) and callable(read_requirements)
assert callable(exit_result.interpret)
print("compatible-imports-ok")
PY
```

<a id="пример-конфигурации-и-команды"></a>
## Configuration and interpreted bytes

This example creates only temporary files. Exit 7 is explicitly accepted.
The command's real exit code and arbitrary bytes remain available.

```bash
"${MAINTENANCE_LIBRARY_PYTHON:?Select installed EM Python}" -I -B - <<'PY'
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from environment_maintenance import (
    add_requirement, read_requirements, update_requirement, plan_action, execute_action)
from environment_maintenance.actions.interpreters import exit_result

with TemporaryDirectory() as directory:
    root = Path(directory)
    main, selected = root / "main.json", root / "operation.json"
    main.write_text(json.dumps({"operations": {"example": "operation.json"}}))
    selected.write_text(json.dumps({"requirements": [], "metadata": "kept"}))
    add_requirement(main, "example", {"id": "sample", "value": 1})
    update_requirement(main, "example", "sample", [
        {"op": "replace", "path": "/value", "value": 9}])
    objects = read_requirements(main, "example", "all")
    action = {"commands": [{
        "argv": [sys.executable, "-B", "-c",
                 "import sys;sys.stdout.buffer.write(bytes.fromhex('00ff'));"
                 "sys.stderr.buffer.write(bytes.fromhex('fe'));sys.exit(7)"],
        "cwd": directory, "env": {},
        "interpreter": {"name": "exit", "options": {"accept": [7]}}
    }]}
    options = dict(base_dir=root, interpreters={"exit": exit_result})
    plan = plan_action(action, {}, **options)
    result = execute_action(action, {}, **options)
    command = result["commands"][0]
    assert plan["commands"][0]["cwd"] == directory
    assert objects == [{"id": "sample", "value": 9}]
    assert json.loads(selected.read_text())["metadata"] == "kept"
    assert result["status"] == "succeeded"
    assert command["exit_code"] == 7
    assert command["stdout"].hex() == "00ff" and command["stderr"].hex() == "fe"
    print(json.dumps({"objects": objects, "status": result["status"],
        "exit_code": command["exit_code"], "stdout_hex": command["stdout"].hex(),
        "stderr_hex": command["stderr"].hex()}))
PY
```

Expect `sample.value=9`, succeeded, exit_code 7, stdout_hex `00ff` and
stderr_hex `fe`. An accept list of [0] rejects the same raw result.
File creation/atomic replacement/mode preservation belong to EM's Bash scripts;
CE transforms JSON values and coordinates commands.

<a id="обновление-обслуживания-окружения"></a>
<a id="поставка-и-совместимость-потребителей"></a>
<a id="consumer-update"></a>
## Consumer update and verification

Choose one immutable compatible core build and record version/origin/hash.
Intermediate bugfix builds are verified in isolated environments; update the
final consumer dependency and integration once, after implementation readiness.
A local test is not registry publication or deployment.

For every independent installation, use its actual package manager, private
runtime and nonempty configured operation. Preserve manifest/lock and compare
observed results with the application's contract. Several registrations can
share an installation; distinct copies need distinct verification. Unknown
effects require observation before an intentional retry.

[Runtime selection and recovery](installation.md#пути-и-обновление) and
[npm delivery](npm-distribution.md#собственная-зависимость-приложения) describe
the corresponding installation owner. Source, build, publication and adoption
are separate observable actions.
