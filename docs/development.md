# Разработка и выпуск

## Подготовка

Выберите source revision и подготовленное окружение приложения. Первоначальное развёртывание, в том числе worktree, выполняет внешний EM через декларации владельца системы с установкой внутреннего EM. Дальнейшее обслуживание выполняет внутренний EM; полное удаление — внешний. [Разделение установок по этапам](installation.md#первоначальное-развёртывание-системы-приложений) определяет этот порядок. Самостоятельную установку описывает [инструкция](installation.md#установка-из-исходников). `app_python` ниже — абсолютный Python выбранного экземпляра; installed `.py` должны совпадать с source.

## Ответственность модулей

| Owner | Ответственность |
|---|---|
| `command_execution.configuration` | Operations mapping, ordered unique selection, CRUD, JSON reader/atomic writer |
| `environment_maintenance.configuration` | Совместимые импорты; собственная execution-политика пропущенных ID |
| `cli` | Стандартный argparse для всех аргументов, ранние предупреждения и композиция шести команд |
| `invocation` | Пути/defaults и декодирование CLI selection с общей проверкой формы/уникальности из `configuration` |
| `output` | Чистое форматирование подготовленных JSON-данных: pretty/one-line без IO и решений об исполнении |
| `command_execution.actions` | Plan/execute, ResultInterpreter, полный transport, optional exit-code interpreter |
| `environment_maintenance.actions` | Совместимые пути импортов установленной общей реализации |
| `preparation`, `checking`, `network` | Подготовка, presence/availability, командное/сетевое согласование |
| `running` | Именованные use cases, raw submitted PGID, presentation, SIGTERM и module launcher |
| `application_resources` | Чистое разрешение декларации ресурсов/шаблонов, проверка формы без IO и измерения доступности |
| `registry` | Полные строки PGID/снимка, shared OS temp, exclusive empty creation под коротким flock, публикация/удаление |

Представление результатов и exit status остаются у CLI-входов операций; они передают готовые данные в `output`, затем печатают результат. [Общий договор формата и предупреждений](configuration.md#формат-json) принадлежит CLI.

[Run/list/stop](process-launch.md#запуск-процессов) использует прежний ActionExecutor. Файловая граница не владеет командами приложения. `environment_maintenance.running.console` имеет одну реализацию; example делегирует. [Seed источники](requirements/README.md) не являются runtime dependency.

## Проверки

Обычная Task выбирает адресные tests по изменённой границе; full/release suite принадлежит отдельной проверке выпуска. Сохраняйте source/tree, argv/cwd, полные streams/exit, actual package digest и closure собственных ресурсов.

Формат/аргументы/порядок диагностик проверяет `tests/test_cli_output.py`, настоящую npm-установку и её CLI — `tests/test_cli_output_package.py`. Затронутые прежние договоры покрывают `test_run_stop`, `test_cli_contract`, `test_run_stop_consumers`, `test_runtime_components`, `test_reservation_failure`; SDK/servicing/network/npm controls выбираются адресно. Перед npm checks подготовьте свои `ENV2_PACKAGE_TEST_ROOT`, `ENV2_PACKAGE_WHEELHOUSE` с настоящими build/runtime wheels и абсолютный `ENVIRONMENT_MAINTENANCE_PYTHON`. Это arrangement тестов, не настройки продукта.

Схему required map, снимок конкретного запуска, legacy, диагностику и форматирование проверяет `tests/test_application_resources.py`; `tests/test_application_resources_package.py` проверяет реальную новую npm-установку, её origin/version и CLI. Примеры HTTP/очередей/планировщика здесь описывают метаданные, а не измеряют внешний backend или GUI.

После всех применимых исправлений/refactoring/docs и адресных checks:

```bash
PYTHONPATH=src bash tests/smoke.sh "$app_python"
```

Шесть pytest selectors дают девять случаев. Это maintained smoke с реальными command/registry effects. `test_run_stop` требует Linux, DISPLAY, Zutty и DejaVuSansMono. [Дополнительный interactive arrangement](../tests/fixtures/process-launch/README.md) использует собственный видимый Xephyr для своего GUI-сценария. Неподготовленная GUI-среда не является продуктовым RED.

### Реальные консоли и документация запуска

[Правильный пример](process-launch.md#пошаговая-инструкция) исполняется на своих конфигах/OS temp/logs и группах, с реальными HTTP и stop outcomes. Импорт или endpoint сами не подтверждают остальные контракты. Полный output сохраняет его владелец до передачи результатов и уборки Task.

Существующий read-only checker проверяет локальные ссылки/точные заголовки и incoming links изменённых/удалённых страниц:

```bash
PYTHONPATH="$poise_root/src:$poise_root" "$poise_python" -P -s -B \
  "$poise_root/tools/check_documentation.py" --checkout "$PWD" \
  --changed README.md --changed docs/process-launch.md
```

Добавляйте paths повторяемым `--changed`. Это development tool выбранной установки; у поставляемого EM нет зависимости от Poise. Один AI-навык проверяется штатным `skill-creator/scripts/quick_validate.py` в AI-среде. Смысл и исполнимые примеры проверяются отдельно.

## Локальный npm-кандидат

После изменения docs/skill нужен свежий [pack/install](npm-distribution.md#пошаговая-инструкция): текущие source/docs/examples/tests и ровно один skill. Существующие `test_archive_contains_owned_material_bytes` и `test_installed_core_libraries_and_metadata_belong_to_instance` наблюдают actual архив/установку; installed run/list/stop проверяется своими npm entry cases. Старый tgz не является новым proof. После изменения документации повторите адресные проверки на точном новом commit и сравните изменённые Markdown-файлы с байтами внутри свежего архива; записывайте digest именно этого архива.

`tests/test_command_package_extraction.py` проверяет самостоятельную библиотеку и её применение установленным EM. Для проверки потребителя задайте `ENV2_PACKAGE_WHEELHOUSE` с опубликованным `command-execution==1.1.0` и его runtime-зависимостями: тест устанавливает их через pip с `--no-index`, собирает EM и проверяет фактические вызовы через выбранную библиотеку.

## Сборка и поставка

Корень сборки библиотеки `command-execution` 1.1.0 — корень отдельного checkout репозитория `command-execution` с его `pyproject.toml`; environment-maintenance 5.2.0 выбирает её точной зависимостью. Вложенный `environment-maintenance/packages/command-execution` — исторический bootstrap 0.1.0, его не используют для сборки 1.1.0. [Руководство пакета](command-package.md#самостоятельный-пакет) определяет установку, совместимые импорты и обновление потребителей. Сборка environment-maintenance не подменяет отдельный выпуск библиотеки.

Source commit/tree, version, actual digest, runtime/tool identity, полные проверки и независимая приёмка принадлежат квитанции вне архива, чей digest она описывает. Python build выполняйте в подготовленной среде из корня именно собираемого проекта: самостоятельного `command-execution` для библиотеки либо `environment-maintenance` для SDK. Команда без аргумента исходника собирает текущий проект:

```bash
"$app_python" -m build --no-isolation --outdir /absolute/path/to/owned-output
```

Wheel/sdist/npm — разные артефакты. Исполняйте и передавайте выбранные байты. Изменение source/docs после сборки требует нового соответствующего артефакта и актуального proof. Интеграция, runtime delivery, tag/publish/push и обновление consumers имеют своих владельцев и полномочия. Task working material удаляется после доставки/интеграции и завершения обязательных consumers; отдельный архив по умолчанию не создаётся.

## Узкая проверка сетевого согласования

`test_network_adjustment` и выбранные settings controls сохраняют [сетевой договор](settings-alignment.md#автоматический-подбор-портов). Его `owner.pid/start_ticks` описывают владельца порта; PGID launch registry имеет другого владельца. Выбирайте конкретные затронутые случаи и prerequisites.

## Проверки цепочки данных

Для принятого изменения API адресные проверки запускаются собственным подготовленным
Python текущего checkout с установленной соответствующей библиотекой:

```bash
: "${COMMAND_EXECUTION_SOURCE:?Выберите абсолютный checkout command-execution 1.1.0}"
: "${ENV2_PACKAGE_WHEELHOUSE:?Выберите wheelhouse с принятым wheel 1.1.0 и зависимостями}"
export COMMAND_EXECUTION_SOURCE ENV2_PACKAGE_WHEELHOUSE
"${app_python:?Выберите Python подготовленного checkout}" -I -B -m pytest \
  -p no:cacheprovider -q tests/test_command_chain.py tests/test_command_package_extraction.py
```

Проверки различают фиксированные подстановки и текущий JSON-вход, явный `next_input`,
sync stop/continue, полные bytes и реальные процессы. Асинхронный сценарий использует
причинные барьеры: следующее звено исполняется до фонового завершения, получает
исходный снимок, а поздний результат не заменяет итог цепочки. Проверка wheel
использует отдельную установленную библиотеку и совместимые импорты SDK.
Это адресные проверки API, а не подтверждение внедрения каждого потребителя.
[Границы callback и времени жизни](action-execution.md#результаты-и-фоновое-завершение)
остаются частью договора вызывающего приложения.
