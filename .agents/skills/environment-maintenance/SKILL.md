---
name: environment-maintenance
description: Use a selected environment-maintenance instance for persistent short operation commands and public configuration-library operations.
---

# Environment maintenance

Use the selected instance's own runtime and application-owned persistent profile.
Read the [normal entry contract and immediate instruction link](../../../docs/persistent-entry.md#постоянный-вход-выбранной-установки)
and [complete setup/verification instructions](../../../docs/persistent-entry.md#пошаговая-инструкция).
Read the [npm contract and immediate walkthrough link](../../../docs/npm-distribution.md#пакетная-поставка-npm)
and [installation choices](../../../docs/installation.md#npm-поставка-210).
The current 2.1.0 source and retained issued 1.0.0/2.0.0 supplies are distinct.
This skill grants no publication or live-consumer update authority.

## Install and identify an instance

Follow the [complete correct installation walkthrough](../../../docs/npm-distribution.md#пошаговая-инструкция).
Select the source/archive, absolute prerequisite Python and independent prefix first.
These are command shapes; the walkthrough supplies actual owned paths and checks:

| Purpose | Command |
|---|---|
| Build selected source | `npm pack --json --pack-destination DIR` |
| Install selected bytes | `ENVIRONMENT_MAINTENANCE_PYTHON=PYTHON npm install --global --prefix PREFIX --ignore-scripts=false ARCHIVE` |
| Locate installed materials | `npm root --global --prefix PREFIX` |
| Read version | `./start-app --version` |
| Read all argument help | `./start-app --help` |
| Remove own instance | `npm uninstall --global --prefix PREFIX environment-maintenance` |

Npm creates the short bin; venv/pip install the own Python core and dependencies.
Select the actual PREFIX/bin/start-app, or enter its bin directory for ./start-app.
Default main belongs to the selected runtime's parent, not the caller directory.
For library/examples, obtain package_root
and app_python through the [common setup](../../../docs/npm-distribution.md#библиотека-и-поставленные-примеры).
Packaged source examples and actual npm bin observations are distinct; identify which ran.
The root ./start-app selects its neighbouring installed .venv with -I.

## Run configured operations

Read the [preparation owner and immediate instructions](../../../docs/resource-preparation.md#подготовка-ресурсов),
[all shared CLI arguments](../../../docs/resource-preparation.md#команды-и-аргументы),
[checking arguments](../../../docs/resource-checking.md#команды-и-аргументы)
and [the actual installed-bin walkthrough](../../../docs/npm-distribution.md#пошаговая-инструкция).

| Purpose | Command shape |
|---|---|
| Prepare infrastructure | `./start-app infra` |
| Prepare dependencies | `./start-app deps` |
| Align declared settings | `./start-app adjust` |
| Observe resources/settings | `./start-app check` |
| Launch declared processes | `./start-app run` |

These are complete ordinary calls after one-time operator setup. Paths, parameters,
IDs and order belong to the permanent main/operation files. Use an absolute selected
entry from a foreign cwd. Optional overrides apply only to that call; see the
[path/override reference and immediate examples](../../../docs/persistent-entry.md#переопределение-одного-вызова).
A shared-SDK consumer's local entry internally binds its own permanent main before
caller arguments; actual consumer readiness must be verified by its delivery owner.

Choose all, an ID array or [] using each operation's contract. Main config maps operations
to separate requirement documents. Commands/templates/plugins belong to the serviced app.
Invoke preparation, adjustment, checking and launch explicitly. Run launches only its selection.
Caller cwd/argv/env/stdin/full streams and ordinary/signal outcomes are preserved.
Inspect complete partial results before intentional continuation; the external tool owns repair.
Use the [installation diagnostic procedure](../../../docs/npm-distribution.md#диагностика-и-правильное-продолжение)
for missing runtime or package-manager failures.

## Read requirement configuration

Read the [public read contract and immediate instruction link](../../../docs/configuration-reading.md#библиотека-чтения)
and [every correct read example](../../../docs/configuration-reading.md#пошаговая-инструкция).
Using the selected own Python and the documented example context:

```python
from environment_maintenance import list_requirement_ids, read_requirements
config = "examples/configuration-reading/app.example.json"
identifiers = list_requirement_ids(config, "infra")
selected = read_requirements(config, "infra", ["redis"])
complete = read_requirements(config, "infra", "all")
```

Listing returns IDs only. Batch reads return complete objects in the requested order.
Read the current operation mapping rather than assuming fixed config filenames.

## Change configuration

Read the [public write contract and immediate instruction link](../../../docs/configuration-editing.md#библиотека-записи)
and [instructions covering every operation](../../../docs/configuration-editing.md#пошаговая-инструкция).
Use an owned writable copy of the demonstrated main/operation files:

```python
from environment_maintenance import (
    add_requirement, update_requirement, delete_requirement, clear_requirements,
)
add_requirement(config, "infra", {"id": "demo", "commands": []})
update_requirement(config, "infra", "demo", [{"op": "add", "path": "/label", "value": "Demo"}])
delete_requirement(config, "infra", "demo")
clear_requirements(config, "infra")
```

Writes preserve other data and return None; confirm with read_requirements.
Clear explicitly empties only the selected list. Commands remain data until execution.
Follow the documented patch subset, pointer semantics and [diagnostics](../../../docs/configuration-editing.md#диагностика-и-повторный-вызов).

## Plan and execute actions

Read the [action API and immediate walkthrough](../../../docs/action-execution.md#библиотека-исполнения),
[complete functions/arguments](../../../docs/action-execution.md#публичные-функции-и-аргументы)
and [interpreter interface](../../../docs/action-execution.md#интерфейс-интерпретатора).
For actual supplied action/parameters/objects:

```text
plan_action(action, parameters, base_dir=work, interpreters=registry)
execute_action(action, parameters, base_dir=work, interpreters=registry)
```

Plan has no process/interpreter effects. Execution preserves bytes and stops on failure.
Standard Template handles scalar substitutions; configured names/options select injected
interpreter objects. CLI module/attribute uses the documented explicit plugin import path.

## Prepare, align and check through the library

Read [preparation and its immediate instruction](../../../docs/resource-preparation.md#подготовка-ресурсов),
[alignment and its immediate instruction](../../../docs/settings-alignment.md#согласование-настроек)
and [checking and its immediate instruction](../../../docs/resource-checking.md#проверка-окружения).
Their references describe all arguments, config fields, result data and external tools.

```text
prepare_resources(config, "infra", "all", values, base_dir=work, interpreters=registry)
prepare_resources(config, "deps", ["packages"], values, base_dir=work, interpreters=registry)
prepare_resources(config, "adjust", "all", values, base_dir=work, interpreters=registry)
check_resources(config, values, base_dir=work, interpreters=registry)
prepare_resources(config, "run", "all", values, base_dir=work, interpreters=registry)
```

All declared selected plans precede effects. Check runs presence, provided availability
and additional conditions, continuing independent checks. Inspect not_configured/not_attempted.
Library keeps bytes/opaque values; CLI uses JSON/base64 for full command streams.

## Launch visible processes and supplied tools

Read the [launch contract and immediate instruction](../../../docs/process-launch.md#запуск-процессов),
[all CLI arguments](../../../docs/process-launch.md#входы-и-аргументы),
[all external starter arguments](../../../docs/process-launch.md#внешний-инструмент)
and [the four actual scenarios](../../../docs/process-launch.md#пошаговая-инструкция).

```text
python examples/process-launch/start_console.py --stdout-log FILE --stderr-log OTHER_FILE -- COMMAND ARG...
```

Choose the actual terminal/display/ports in owned configs. Submitted/PID/EOF prove transfer,
not worker readiness. Each visible console owns its PTY; stop each independently.
Two immediate-command append logs and worker PTY output are different observations.
Use the [alignment tool argument reference](../../../docs/settings-alignment.md#отдельный-инструмент-согласования)
and [check tool argument reference](../../../docs/resource-checking.md#внешний-инструмент-примера)
when invoking those supplied examples directly; their complete executable commands are linked there.

## Catalogue operations

Read the [complete catalogue argument reference and immediate instruction](../../../docs/configuration.md#команды-и-аргументы).
In the installed example context:

```bash
./start-app check --catalog-dir "$package_root/examples/catalog-v2"
./start-app run --catalog-dir "$package_root/examples/catalog-v2" --dry-run
./start-app run --catalog-dir "$package_root/examples/catalog-v2"
```

The reference defines repeatable --values/--set and catalogue action limits/results.
Catalogue run services resources; configured run launches its selected processes.

## Extend the serviced app

When existing tools cannot provide required behavior, develop the serviced app's own
external tool using [public read/CRUD integration](../../../docs/configuration-editing.md#собственный-внешний-инструмент)
and [the action/interpreter boundary](../../../docs/action-execution.md#собственный-внешний-инструмент).
Keep infrastructure-specific policy there. Canonical Russian documentation owns details;
this single skill routes to the appropriate complete instructions.
