---
name: environment-maintenance
description: Use a selected environment-maintenance instance for configured servicing, named run/list/stop and public configuration APIs.
---

# Environment maintenance

Use the selected package entry and its own installed Python. Read the [CLI contract](../../../docs/configuration.md#команды-и-аргументы), [persistent profile](../../../docs/persistent-entry.md#пошаговая-инструкция) and [installation walkthrough](../../../docs/npm-distribution.md#пошаговая-инструкция) for the actual scenario. This instruction describes version5; retained earlier supplies keep their own contracts. Source capability, candidate validation and live installation readiness are separate facts.

## Select and restore an instance

Each independent application owns its selected archive/npm manifest/generated lock and installed package/.venv. Use its node_modules/.bin/start-app or selected PREFIX/bin/start-app. Multiple registrations of that application may use its same copy. Retained supply belongs outside disposable Task roots; the package manager restores installed bytes. Do not make a disposable runtime the sole source of required code or configuration.

Follow [application-owned installation](../../../docs/npm-distribution.md#собственная-зависимость-приложения) and [migration](../../../docs/migration-v5.md#переход-конфигурации) before updating a selected instance. Use external EM for initial deployment and complete system removal; use the system's own installed EM for subsequent servicing. Applications and tests use system-owned infrastructure without depending on external EM. Follow the [deployment lifecycle](../../../docs/installation.md#первоначальное-развёртывание-системы-приложений). This skill grants no publication, integration or live-upgrade authority. Keep application Python/dependencies distinct from the maintenance runtime.

Identify exact version/prefix/module paths and archive/lock bytes. npm entry preserves caller cwd and chooses its own Python; root source entry uses its neighbouring installed .venv. Main defaults to CWD/start-app.json. From another cwd select --config explicitly. See the [override contract](../../../docs/persistent-entry.md#переопределение-одного-вызова).

## Service declared resources

Read [preparation](../../../docs/resource-preparation.md#подготовка-ресурсов), [adjust](../../../docs/settings-alignment.md#согласование-настроек) or [check](../../../docs/resource-checking.md#проверка-окружения) as needed.

```bash
start-app infra
start-app deps
start-app adjust
start-app check
```

These ordinary calls use application-owned operation documents/parameters. Infra/deps/adjust default to all; select unique IDs with --requirements where applicable. CLI missing IDs warn/skip; repeated selection or source IDs reject the whole request before effects. The strict read SDK rejects unknown IDs. Check has its own full-resource policy. Unknown CLI arguments warn/skip, so an obsolete flag does not provide preview or suppress effects.

For network adjust read the [declaration](../../../docs/settings-alignment.md#декларация-сетевого-согласования), [two-server instructions](../../../docs/settings-alignment.md#два-http-сервера) and [failure contract](../../../docs/settings-alignment.md#результат-и-отказ-сетевого-режима). Select network and command requirements in separate calls; the dictionary preparation API does not invent an output-file path.

## Run, list and stop applications

Read the [complete run/stop contract](../../../docs/process-launch.md#запуск-процессов) and [owned process walkthrough](../../../docs/process-launch.md#пошаговая-инструкция).

```text
start-app run list
start-app run --env ENV --app APP
start-app run list --env ENV
start-app stop list --env ENV
start-app stop --env ENV --app APP
```

Run without ENV generates UUID; without APP selects all applications. Existing nonempty ENV accepts one new APP, not full relaunch or duplicate registration. APP all is literal. Run list returns an application-name map of pgid:null and declared required resources; a missing ENV returns an empty map. Stop without arguments lists records; stop all addresses all readable ENV; selecting APP requires ENV. Stop needs no application main/parameters and uses saved PGID and the launch resource snapshot in the same OS-temp registry. Legacy PGID-only records remain readable; never infer their missing resource history from current configuration.

Follow the canonical [resource declaration and output contract](../../../docs/process-launch.md#ресурсы-приложения). Any resources key, including an empty or literal object, makes run list use the selected invocation/parameters/base-dir context. Metadata describes application resources; it does not measure health or exclusive ownership. Check owns availability. The new map changes CLI run list, not SDK ID lists or the run-result attempt array.

Only run documents use applications; other operations use requirements. Default selection no longer comes from invocation.requirements. Production last-command submission uses the installed maintenance Python:

```text
MAINTENANCE_PYTHON -I -B -m environment_maintenance.running.console --stdout-log OUT --stderr-log ERR -- COMMAND ARG...
```

The module creates a session/group and returns raw submitted/pgid. The optional standard interpreter is environment_maintenance.actions.interpreters:exit_result with explicit accept codes. Application-specific commands, options, interpreters and value contracts remain application-owned; do not move ERP/Poise behavior into the package to fix an import. Production bindings do not load/copy examples as implementation.

Read complete partial results. Received PGID remains visible on save/interpreter failure; later independent APP continue. There is no automatic health/retry/process rollback. Stop sends SIGTERM, removes successful/ESRCH mappings and retains failed targets. Preserve other records. Use [manual recovery](../../../docs/migration-v4.md#ручное-восстановление) for write/cleanup failure, missing records or uncertain effects; never guess PGID or purge the shared temp directory.

## Public read, CRUD and command APIs

Read the [read contract](../../../docs/configuration-reading.md#библиотека-чтения), [CRUD](../../../docs/configuration-editing.md#библиотека-записи), [actions](../../../docs/action-execution.md#библиотека-исполнения) and their linked walkthroughs for actual arguments. Use the selected own Python. List returns IDs, batch/all reads return full copied objects; writes preserve other data and return None. Stored commands remain data until explicitly executed.

plan_action/execute_action and prepare_resources/check_resources retain their explicit base_dir/interpreters contracts, full bytes and opaque Python values. CLI transport has its own JSON/base64 boundary. Generic run chain execution through the library does not manage named CLI registry state. Keep permanent procedures in canonical Russian documentation; this skill routes to those owners.
