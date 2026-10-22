---
name: environment-maintenance
description: Use environment-maintenance's released catalogue CLI and source configuration CRUD API through its own documented contracts and executable examples.
---

# Environment maintenance

Use the selected application's own runtime and explicit configuration paths.
The released 1.0.0 CLI and the source-development 2.0 configuration APIs are distinct;
see the [capability boundary](../../../docs/configuration-reading.md#библиотека-чтения).
Source development integrates into master; this skill does not publish or install a release.

## Current CLI

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
The current CLI `run` services a catalogue; it is not the future application launcher.

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
The future universal executor, new CLI operations and a new release remain separate work.
