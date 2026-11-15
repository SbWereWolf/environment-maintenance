# environment-maintenance 5.1.0

English | [Русский](docs/README.ru.md)

Run declared environment maintenance, track application launches by environment, and stop recorded process groups.

One installed `start-app` provides six commands:

```bash
start-app infra
start-app deps
start-app adjust
start-app check
start-app run
start-app stop
```

The consuming application defines paths, parameters, command order, and command interpreters. Operations run when explicitly invoked. Named launches and their process group IDs (PGIDs) are stored in a registry under the selected operating-system temporary directory. `stop` reads that registry without requiring the application's configuration. The package runs independently of ERP, Poise, and their databases.

## Installation and guides

The detailed guides below are in Russian. The bundled AI skill is in English.

- [Installation options and recovery](docs/installation.md).
- [Independent configuration and command library](docs/command-package.md).
- [npm installation as an application-owned dependency](docs/npm-distribution.md#пакетная-поставка-npm).
- [All commands and arguments](docs/configuration.md#команды-и-аргументы).
- [Persistent profile](docs/persistent-entry.md#поля-постоянного-профиля).
- [Launching, listing, and stopping processes](docs/process-launch.md#запуск-процессов).
- [Migration from 4.x to 5 and recovery](docs/migration-v5.md).
- [Development and checks](docs/development.md).
- [Bundled AI skill](.agents/skills/environment-maintenance/SKILL.md).

JSON output uses one line by default. Passing `--output` without a value enables pretty printing. The [JSON output contract](docs/configuration.md#формат-json) describes option values and placement.

## Configuration library 2.0

[Reading](docs/configuration-reading.md#библиотека-чтения) returns IDs or complete objects. [Writing](docs/configuration-editing.md#библиотека-записи) adds, updates, deletes, or clears selected data while preserving other fields. The array for `run` is named `applications`; other operations use `requirements`. Writing configuration does not execute commands.

## Running applications

| Capability | Reference |
|---|---|
| Command chains and replaceable interpreters | [Action API](docs/action-execution.md#библиотека-исполнения) |
| Infrastructure and dependencies | [Resource preparation](docs/resource-preparation.md#подготовка-ресурсов) |
| Command and network settings alignment | [Adjust](docs/settings-alignment.md#согласование-настроек) |
| Presence, availability, and additional conditions | [Check](docs/resource-checking.md#проверка-окружения) |
| Run/list, PGID registry, stop/list/all | [Processes](docs/process-launch.md#запуск-процессов) |

After preparing the profile, run these commands from the application directory:

```bash
start-app run list
start-app run --env dev --app web
start-app stop list --env dev
start-app stop --env dev --app web
```

`run list` returns an application map with `pgid: null` and the declared required resources. `stop list` shows the PGID and saved resources for a particular launch without requiring the current configuration. Missing resource declarations are not inferred.

`web` is an ID in your application's configuration. A standalone example is available in the [launch guide](docs/process-launch.md#пошаговая-инструкция).

## Versioning

This source revision describes environment-maintenance 5.1.0 and its independent dependency, `command-execution` 1.0.0. [Tag-based releases and installation from npm](docs/npm-distribution.md#автоматический-выпуск-и-установка-из-реестра) define the standard distribution route. The installed version, lockfile, and its own Python environment identify the selected installation. Changing source or checking a release candidate does not publish a package or update consumers. Earlier releases 1.0.0, 2.0.0, 2.1.0, 3.0.0, and 3.1.0 retain their original contents and contracts.

Version 4.0.0 introduced a breaking change to the CLI and launch format; [migration](docs/migration-v4.md) requires coordinated updates. The removed directory-based interface is not part of this revision. Use the documentation bundled with an older release when working with that release. In 5.0.0, the `run list` entry map replaced the previous array of IDs, which is a breaking CLI change. Compact output by default, SDK contracts, and the launch-attempt array in `run` results remain unchanged. Statements that an API is available since 4.0.0 remain valid.

## Supported platform and checks

The supported platform is Linux with Node.js 22+, npm 10+, and Python 3.11+ with venv and pip. This revision has been checked on Ubuntu 24.04.4 WSL2 x86_64 with Node.js 22.23.2, npm 10.9.8, and Python 3.12.3. This does not imply verification of every platform and Python combination.

Regular development uses [targeted checks and the maintained smoke suite](docs/development.md#проверки). Publication and adoption require their respective delivery owner's authorization.
