---
name: environment-maintenance
description: Use environment-maintenance's released catalogue CLI and its source configuration-reading API through the application's own instructions.
---

# Environment maintenance

Use the selected application's own runtime and explicit configuration paths.
The released 1.0.0 CLI and the source-development 2.0 reading API are distinct;
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
This API reads configuration; later CRUD/execution capabilities have their own delivery.
