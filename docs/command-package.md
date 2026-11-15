# Самостоятельная библиотека конфигурации и команд

## Самостоятельный пакет

`command-execution` 0.2.0 предоставляет Python API `command_execution`: чтение и изменение конфигурации, подготовку аргументов, исполнение команд и интерпретацию результата. Требуется Python 3.11+; зависимости пакета — `jsonpatch>=1.36` и `jsonpointer>=3.4`.

Пакет имеет собственный `packages/command-execution/pyproject.toml` и собирается отдельно от environment-maintenance. Установленный потребитель использует выбранную версию через пакетный менеджер. Каталог исходников environment-maintenance, его CLI, базы данных и настройки приложений библиотеке не требуются.

## Установка выбранной версии

Владелец поставки предоставляет принятый wheel и полный набор необходимых зависимостей в постоянном wheelhouse либо выбранном индексе. Версия, digest и источник выбранных байтов сохраняются в квитанции поставки. Временный каталог проверки не становится постоянной поставкой.

Для следующего вызова задайте `LIBRARY_PYTHON` — абсолютный Python собственного подготовленного окружения; `COMMAND_WHEELHOUSE` — каталог принятых колёс. `--no-index` выбирает установку из указанного набора, `--find-links` задаёт его путь. [Контекст установки wheel](installation.md#установка-готового-wheel).

```bash
"${LIBRARY_PYTHON:?Set LIBRARY_PYTHON}" -I -B -m pip install \
  --no-index --find-links "${COMMAND_WHEELHOUSE:?Set COMMAND_WHEELHOUSE}" \
  command-execution==0.2.0
```

Pip разрешает объявленные зависимости. Для нового окружения wheelhouse должен содержать и нужные зависимые пакеты. Установка завершается ошибкой, если выбранного совместимого набора нет; владелец дополняет набор или выбирает разрешённый индекс.

## Совместимые импорты

| Назначение | Самостоятельный пакет | Совместимый вход environment-maintenance 5.2.0 |
|---|---|---|
| Чтение и CRUD | `command_execution` | `environment_maintenance` |
| План и исполнение | `command_execution.plan_action`, `execute_action` | `environment_maintenance.plan_action`, `execute_action` |
| Цепочка данных и dry-run | `command_execution.plan_chain`, `execute_chain` | `environment_maintenance.plan_chain`, `execute_chain` |
| Стандартный интерпретатор | `command_execution.actions.interpreters.exit_result` | `environment_maintenance.actions.interpreters.exit_result` |
| Структурный протокол | `command_execution.actions.application.ResultInterpreter` | `environment_maintenance.actions.application.ResultInterpreter` |

Прежние пути импортов сохраняются как фасады установленной общей реализации. Подробные действующие договоры остаются в разделах [чтения](configuration-reading.md#публичный-договор), [записи](configuration-editing.md#публичный-договор), [плана](action-execution.md#параметры-и-план), [интерпретатора](action-execution.md#интерфейс-интерпретатора) и [результата](action-execution.md#итог-исполнения). Их аргументы, порядок объектов, отказы и полные bytes сохраняются.

Для проверки совместимого импорта выберите Python установленного environment-maintenance через `MAINTENANCE_LIBRARY_PYTHON`. [Выбор собственного runtime](installation.md#пути-и-обновление).

```bash
"${MAINTENANCE_LIBRARY_PYTHON:?Set MAINTENANCE_LIBRARY_PYTHON}" -I -B - <<'PY'
from environment_maintenance import plan_action, read_requirements
from environment_maintenance.actions.interpreters import exit_result
assert callable(plan_action) and callable(read_requirements)
assert callable(exit_result.interpret)
print("compatible-imports-ok")
PY
```

## Пример конфигурации и команды

Используйте установленную библиотеку и `LIBRARY_PYTHON` из [шага установки](#установка-выбранной-версии). Пример создаёт только временные файлы. Все обязательные аргументы заданы; интерпретатор явно принимает код 7. Полные потоки представлены в hex для произвольных bytes.

```bash
"${LIBRARY_PYTHON:?Set LIBRARY_PYTHON}" -I -B - <<'PY'
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from command_execution import (
    add_requirement, read_requirements, update_requirement,
    plan_action, execute_action,
)
from command_execution.actions.interpreters import exit_result

with TemporaryDirectory() as directory:
    root = Path(directory)
    main = root / "main.json"
    selected = root / "operation.json"
    main.write_text(json.dumps({"operations": {"example": "operation.json"}}))
    selected.write_text(json.dumps({"requirements": [], "metadata": "kept"}))
    add_requirement(main, "example", {"id": "sample", "value": 1})
    update_requirement(main, "example", "sample", [
        {"op": "replace", "path": "/value", "value": 9}
    ])
    objects = read_requirements(main, "example", "all")
    action = {"commands": [{
        "argv": [sys.executable, "-B", "-c",
                 "import sys; sys.stdout.buffer.write(bytes.fromhex('00ff')); "
                 "sys.stderr.buffer.write(bytes.fromhex('fe')); sys.exit(7)"],
        "cwd": "${directory}", "env": {},
        "interpreter": {"name": "exit", "options": {"accept": [7]}}
    }]}
    parameters = {"directory": directory}
    interpreters = {"exit": exit_result}
    plan = plan_action(action, parameters, base_dir=root, interpreters=interpreters)
    result = execute_action(action, parameters, base_dir=root, interpreters=interpreters)
    command = result["commands"][0]
    assert plan["commands"][0]["cwd"] == directory
    assert json.loads(selected.read_text())["metadata"] == "kept"
    print(json.dumps({
        "objects": objects, "status": result["status"],
        "exit_code": command["exit_code"],
        "stdout_hex": command["stdout"].hex(),
        "stderr_hex": command["stderr"].hex(),
        "success": command["interpretation"]["success"]
    }))
PY
```

Ожидаются объект `sample` со значением 9, `status="succeeded"`, `exit_code=7`, `stdout_hex="00ff"`, `stderr_hex="fe"`, `success=true`. При выборе `accept: [0]` та же команда даст `status="failed"`, сохранив фактические код и потоки. В этом примере `plan_action` готовит весь порядок без исполнения, а `execute_action` прекращает исполнение после первого неуспешного результата. Прикладные интерпретаторы предоставляются вызывающим приложением.

Новые `plan_chain`/`execute_chain` предоставляют отдельный [договор передачи данных, sync/async и dry-run](action-execution.md#цепочки-с-передачей-данных). Прежние `plan_action`/`execute_action` сохраняют свои аргументы и поведение. Выбор нового API не происходит автоматически при обновлении зависимости.

## Обновление обслуживания окружения

Environment-maintenance 5.2.0 объявляет точную зависимость `command-execution==0.2.0`. Операции обслуживания, пути конфигурации и прикладные интерпретаторы остаются у исходного потребителя; общие API вызывает установленный пакет. Политику предупреждения о пропущенных ID исполнения сохраняет environment-maintenance, строгий библиотечный выбор ID сохраняет свой отказ.

Для npm-потребителя выберите принятый архив 5.2.0, собственный prefix и полный wheelhouse, включая библиотеку и зависимости сборки/runtime. Сохраните выбранные manifest и generated lock по [инструкции собственной зависимости](npm-distribution.md#собственная-зависимость-приложения). Исторические примеры 5.0.0 в том руководстве принадлежат указанному выпуску.

В следующем вызове `MAINTENANCE_PYTHON` — абсолютный Python с venv/pip; `MAINTENANCE_PREFIX` — собственный корень установки; `MAINTENANCE_ARCHIVE` — выбранный tgz; `COMMAND_WHEELHOUSE` — полный набор колёс. `NPM_EXE` при необходимости выбирает executable npm. [Параметры установки](npm-distribution.md#договор-экземпляра).

```bash
ENVIRONMENT_MAINTENANCE_PYTHON="${MAINTENANCE_PYTHON:?Set MAINTENANCE_PYTHON}" \
PIP_NO_INDEX=1 PIP_FIND_LINKS="${COMMAND_WHEELHOUSE:?Set COMMAND_WHEELHOUSE}" \
"${NPM_EXE:-npm}" install \
  --prefix "${MAINTENANCE_PREFIX:?Set MAINTENANCE_PREFIX}" \
  --ignore-scripts=false "${MAINTENANCE_ARCHIVE:?Set MAINTENANCE_ARCHIVE}"
```

Lifecycle создаёт собственный Python установленного npm-пакета; pip получает выбранную библиотеку из wheelhouse. Python обслуживаемого приложения задаётся отдельно. Для wheel-потребителя используйте [установку готового wheel](installation.md#установка-готового-wheel) с тем же выбранным набором зависимостей. Постоянная поставка и каждое применение имеют собственные результаты и квитанции.

## Поставка и совместимость потребителей

Каждый принятый выпуск общей библиотеки получает собственную версию. Владелец развёртывания устанавливает актуальный зарегистрированный состав и самостоятельные установки. Несколько регистраций могут использовать одну копию; отдельные копии обновляются и проверяются отдельно. Исходный потребитель также применяет выбранную версию.

Для каждой установки сохраните выбранные версии, origins, digest архивов и lock, затем результат непустой поддерживаемой операции через её действующие конфигурацию, интерпретатор и рабочий вход. Ожидание берётся из договора приложения и независимого корректного примера/фикстуры исходного поведения. Если такие сведения или допустимое окружение отсутствуют, совместимость остаётся неподтверждённой.

Корректные метаданные и пустой check не подтверждают работоспособность. Отказ рабочего входа, несовместимый конфиг или неверный результат интерпретатора оставляют соответствующую установку непроверенной либо несовместимой. Успех исходного runtime не закрывает другую самостоятельную установку. Ранее полученное достаточное доказательство применимо только к тому же кандидату и соответствующей границе поведения.

При ошибке установки или операции владелец сохраняет полный исход и проверяет фактическую выбранную версию/эффект до повтора. Для возврата применяются прежние согласованные архивы/lock и соответствующая конфигурация по [правилам восстановления](installation.md#пути-и-обновление). Исходники, локальная проверка, публикация и применение фиксируются отдельно.
