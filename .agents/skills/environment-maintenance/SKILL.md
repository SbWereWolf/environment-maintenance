---
name: environment-maintenance
description: Use environment-maintenance's released catalogue CLI and source configuration, actions, preparation, alignment, checking and configured process launch through canonical contracts and correct examples.
---

# Environment maintenance

Use the selected application's own runtime and explicit configuration paths.
The released 1.0.0 CLI and source-development 2.0 APIs/configured CLI are distinct;
see the [capability boundary](../../../docs/configuration-reading.md#библиотека-чтения).
Source development integrates into master; this skill does not publish or install a release.

## Released catalogue CLI

Read the [complete argument reference and walkthrough link](../../../docs/configuration.md#команды-и-аргументы).
Activate the installed application environment before these commands.

| Capability | Example |
|---|---|
| Version | `start-app --version` |
| Argument help | `start-app --help` |
| Observe resources | `start-app check --catalog-dir examples/catalog-v2` |
| Observe and plan | `start-app run --catalog-dir examples/catalog-v2 --dry-run` |
| Service resources | `start-app run --catalog-dir examples/catalog-v2` |

The reference describes every argument, including repeatable `--values` and `--set`.
Released catalogue `run` services its explicit catalogue. Source configured `run`
launches selected processes through the separate contract below.

## Read configuration from another tool

Read the [public contract and immediate walkthrough link](../../../docs/configuration-reading.md#библиотека-чтения)
and the [complete executable examples](../../../docs/configuration-reading.md#пошаговая-инструкция).
Use an explicitly selected Python with `PYTHONPATH=src` from the chosen source checkout;
the working installed 1.0.0 package stays unchanged.

```python
from environment_maintenance import list_requirement_ids, read_requirements

config = "examples/configuration-reading/app.example.json"
identifiers = list_requirement_ids(config, "infra")
selected = read_requirements(config, "infra", ["redis"])
complete = read_requirements(config, "infra", "all")
dependencies = read_requirements(config, "deps", "all")
```

List reading returns IDs only; batch reading returns complete selected objects.
Use the documented ordering, all mode, file freshness and error semantics.
Operation-to-file mapping comes from the main config, not a fixed operation list.
The [custom-tool instruction](../../../docs/configuration-reading.md#собственный-внешний-инструмент)
explains developing an external tool when existing tools cannot provide the required behavior.

## Change configuration from another tool

Read the [write contract and immediate walkthrough link](../../../docs/configuration-editing.md#библиотека-записи)
and [executable instructions for every operation](../../../docs/configuration-editing.md#пошаговая-инструкция).
Prepare the declared dependencies using the selected Python and the documented
external package-manager command; retain `PYTHONPATH=src` for source-development use.
The instructions use owned temporary copies, not tracked examples or live configs.

```python
from environment_maintenance import (
    add_requirement, update_requirement, delete_requirement, clear_requirements,
)

# config points to the main file of an owned writable example copy.
add_requirement(config, "infra", {"id": "assets", "commands": []})
update_requirement(config, "infra", "assets", [
    {"op": "add", "path": "/label", "value": "Assets"},
])
delete_requirement(config, "infra", "assets")
clear_requirements(config, "infra")  # Explicit request to empty this selected list.
```

Add appends one complete requirement; update patches one existing requirement;
delete removes one ID; clear empties the list while preserving other document data.
All four return `None` after saving; confirm results with batch reading or `all`.
Use only the documented `add`/`replace`/`remove` patch subset and pointer semantics.
Commands and placeholders remain opaque data; this API does not execute them.
For errors follow the [diagnostic procedure](../../../docs/configuration-editing.md#диагностика-и-повторный-вызов).
When existing tools cannot provide the needed behavior, develop an external tool
using the [documented library integration](../../../docs/configuration-editing.md#собственный-внешний-инструмент).
The [action execution library](../../../docs/action-execution.md#библиотека-исполнения)
is available in source development. Source infra/deps/adjust are described below;
a new packaged release remains separate work.

## Plan and execute declared actions

Read the [complete API and immediate walkthrough link](../../../docs/action-execution.md#библиотека-исполнения)
and [correct examples for each capability](../../../docs/action-execution.md#пошаговая-инструкция).
Use source `PYTHONPATH=src` and a prepared Python; retain the installed 1.0.0 package.
The example helper below supplies only documented demonstration data and interpreters.

```python
import runpy
from pathlib import Path
from tempfile import TemporaryDirectory
from environment_maintenance import plan_action, execute_action

demo = runpy.run_path("examples/action-execution/walkthrough.py")
with TemporaryDirectory(dir="examples/action-execution") as temporary:
    workspace = Path(temporary).absolute()
    action, parameters, interpreters = demo["example_inputs"](workspace)
    plan = plan_action(action, parameters, base_dir=workspace, interpreters=interpreters)
    result = execute_action(action, parameters, base_dir=workspace, interpreters=interpreters)
    assert len(plan["commands"]) == 2 and result["status"] == "succeeded"
```

Configuration selects each interpreter name/options; the caller supplies objects through
the [structural interface](../../../docs/action-execution.md#интерфейс-интерпретатора).
Plan has no process/interpreter effects. Execution preserves full bytes/actual codes and
stops after the first failure; inspect saved partial results before an intentional next action.
Prepared executable/cwd remain nonempty after standard Template substitution.
Use the [documented diagnostic procedure](../../../docs/action-execution.md#диагностика-и-осознанное-продолжение).
When needed, develop a [custom external tool](../../../docs/action-execution.md#собственный-внешний-инструмент)
using configuration CRUD and this action API; do not reimplement the library contract.

## Prepare infrastructure and dependencies

Read the [canonical preparation contract and immediate instruction link](../../../docs/resource-preparation.md#подготовка-ресурсов),
the [complete arguments](../../../docs/resource-preparation.md#команды-и-аргументы)
and [executed walkthrough](../../../docs/resource-preparation.md#пошаговая-инструкция).
From the selected source checkout use its explicit Python and import path:

```bash
PYTHONPATH=src "$app_python" -B examples/resource-preparation/walkthrough.py
```

The walkthrough executes source CLI infra/deps through real subprocesses with
--config, --parameters, --base-dir and --requirements. It prepares owned temporary
files, checks effects and decodes complete streams. The root ./start-app still uses
installed 1.0.0; source invocation does not update that installation.
The short packaged start-app entry uses the same CLI after a separate package delivery.

For the public API, use the owned demonstration input helper, not live configs:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from environment_maintenance import prepare_resources
from walkthrough import prepare_demo, assert_result

# Run with PYTHONPATH=src:examples/resource-preparation in the source checkout.
with TemporaryDirectory() as temporary:
    workspace = Path(temporary)
    config, parameters, registry = prepare_demo(workspace)
    result = prepare_resources(config, "deps", "all", parameters,
                               base_dir=workspace, interpreters=registry)
    assert_result(result, ["packages"], ["dependencies"], workspace)
```

All selected chains are planned before effects; execution stops at the first failure.
Empty selection still validates declared common inputs. API keeps opaque values/bytes.
CLI requires ordinary JSON interpreter answers and validates selected reflected metadata
before effects; command streams use reversible base64. Inspect complete partial results
before deciding continuation. The [configured plugin reference](../../../docs/resource-preparation.md#конфигурация-и-подключение-обработчиков)
explains ready module/attribute objects and the ordinary Python import path.
Use the [custom-tool instruction](../../../docs/resource-preparation.md#собственный-внешний-инструмент)
when existing external tools do not provide the needed behavior.

## Align related settings

Read the [canonical contract and immediate instruction link](../../../docs/settings-alignment.md#согласование-настроек),
[all CLI arguments](../../../docs/settings-alignment.md#входы-и-результаты),
[all external-tool arguments](../../../docs/settings-alignment.md#отдельный-инструмент-согласования)
and [correct executable scenarios](../../../docs/settings-alignment.md#пошаговая-инструкция).
Use the chosen source checkout and its explicit prepared Python:

```bash
PYTHONPATH=src "$app_python" -B examples/settings-alignment/walkthrough.py
```

The four scenarios exercise API all, source CLI selection, empty selection and the
real external tool with another chosen variable/value. They use only owned temporary
copies and check saved settings, preserved data and complete command results.
For prepared source inputs, the existing CLI composition accepts:

```text
python -m environment_maintenance adjust --config MAIN --parameters VALUES --base-dir ABS --requirements all
```

Set the source and configured plugin import paths as documented. The main action config
and the mutable target config have different owners. The generic runner does not own
queue policy or invoke adjustment automatically. Inspect complete partial results and
saved state before deciding a subsequent action; multiple updates are not one transaction.
When existing tools cannot provide the behavior, develop a
[custom external tool using the public library](../../../docs/settings-alignment.md#собственный-внешний-инструмент).
Retain the installed 1.0.0 package; no new release or installation is implied.

## Check resources and related settings

Read the [canonical contract and immediate walkthrough link](../../../docs/resource-checking.md#проверка-окружения),
[all CLI arguments](../../../docs/resource-checking.md#команды-и-аргументы),
[external-tool arguments](../../../docs/resource-checking.md#внешний-инструмент-примера)
and [correct executable instructions](../../../docs/resource-checking.md#пошаговая-инструкция).
Use the prepared Python and selected source checkout, not an update of installed 1.0.0:

```bash
PYTHONPATH=src "$app_python" -B examples/resource-checking/walkthrough.py
```

The seven scenarios demonstrate public API, configured CLI, optional availability,
empty documents and each real external-tool mode on owned copies with preserved inputs.
Configured checking uses this CLI shape; paths and values are explicit:

```text
python -m environment_maintenance check --config MAIN --parameters VALUES --base-dir ABS
```

For a prepared owned example, use the public API:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from environment_maintenance import check_resources
from walkthrough import prepare_demo, assert_result, snapshot

# Run with PYTHONPATH=src:examples/resource-checking in the selected checkout.
with TemporaryDirectory() as temporary:
    workspace = Path(temporary)
    config, parameters, registry = prepare_demo(workspace)
    before = snapshot(workspace)
    result = check_resources(config, parameters, base_dir=workspace, interpreters=registry)
    assert_result(result, encoded=False)
    assert snapshot(workspace) == before
```

All infra/deps/check documents and declared plans are validated before effects.
Presence is mandatory; provided availability follows successful presence.
Independent checks continue after failure. Inspect individual attempted results,
not_configured/not_attempted and complete raw streams; overall success confirms
applicable actions, not omitted conditions. API retains bytes/opaque; CLI encodes
raw streams only. Configured check and explicit catalogue check remain separate.
The external example supports presence --path, availability --path and consistency
with --config/--operation/--writer/--reader/--queue-variable; its queue policy stays
outside the generic core. Use the [diagnostic procedure](../../../docs/resource-checking.md#диагностика-и-осознанное-продолжение).
When existing tools cannot provide a required check, develop a
[custom external tool with the public configuration library](../../../docs/resource-checking.md#собственный-внешний-инструмент).

## Launch configured processes

Read the [canonical launch contract and immediate instruction link](../../../docs/process-launch.md#запуск-процессов),
[all source CLI arguments](../../../docs/process-launch.md#входы-и-аргументы),
[all external-tool arguments](../../../docs/process-launch.md#внешний-инструмент)
and [the four correct executable scenarios](../../../docs/process-launch.md#пошаговая-инструкция).
Use the selected prepared Python and the checkout's source and configured plugin
import paths. The root launcher uses its own installed runtime with `-I`; setting
PYTHONPATH does not turn it into a source launcher. Retain the prepared installed release.

After the documented owned-working-copy preparation:

```bash
"$app_python" -B -m environment_maintenance run \
  --config "$workspace/app.json" --parameters "$workspace/parameters.json" \
  --base-dir "$workspace" --requirements all
```

The same public API supports this operation:

```text
prepare_resources(config, "run", selection, parameters, base_dir=work, interpreters=registry)
```

Its [six arguments and result](../../../docs/resource-preparation.md#библиотечный-вход)
and [working API subset example](../../../docs/process-launch.md#api-запустить-выбранное-подмножество)
preserve bytes/opaque values. CLI encodes full streams as base64. All plans precede
effects; only attempted actions appear in the fail-fast result. Empty selection
still validates the common inputs and declared plugins.

For a direct supplied external tool, select its explicit command and two distinct logs:

```text
python examples/process-launch/start_console.py --stdout-log FILE --stderr-log OTHER_FILE -- COMMAND ARG...
```

Submitted/PID/EOF acknowledge the immediate command, not worker health. The chosen
terminal owns its PTY; users stop each console independently. Binary append logs
contain the immediate command's diagnostics, not automatically the worker PTY output.
Use owned ports/windows and finish previous processes before the next scenario.
A private display alone does not prove exclusive input during automated checking.
Inspect full partial results before continuation. When existing tools are insufficient,
develop a [custom external tool using configuration read/CRUD and the interpreter port](../../../docs/process-launch.md#собственный-внешний-инструмент).
