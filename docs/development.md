# Разработка и выпуск

## Подготовка

Выберите source revision и подготовленное окружение приложения. Первоначальное развёртывание, в том числе worktree, выполняет внешний EM через декларации владельца системы с установкой внутреннего EM. Дальнейшее обслуживание выполняет внутренний EM; полное удаление — внешний. [Разделение установок по этапам](installation.md#первоначальное-развёртывание-системы-приложений) определяет этот порядок. Самостоятельную установку описывает [инструкция](installation.md#установка-из-исходников). `app_python` ниже — абсолютный Python выбранного экземпляра; installed `.py` должны совпадать с source.

## Ответственность модулей

| Owner | Ответственность |
|---|---|
| `command_execution` pure JSON/collection classes | Detached values, ordered selection, nested JSON edits and profiles |
| `environment_maintenance.configuration` | Operations mapping, file-based facades/Bash IO; собственная execution-политика пропущенных ID |
| `cli` | Стандартный argparse для всех аргументов, ранние предупреждения и композиция шести команд |
| `invocation` | Пути/defaults и декодирование CLI selection с общей проверкой формы/уникальности из `configuration` |
| `output` | Чистое форматирование подготовленных JSON-данных: pretty/one-line без IO и решений об исполнении |
| `command_execution.configuration/execution` | Generic CommandPlanner/ChainCoordinator, raw outcomes, stop/continue and output delivery |
| `environment_maintenance.actions` | App plan/action/chain facade, named interpreters and caller-owned Bash cwd/env policy |
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

Для проверки выбранного CE2 используйте актуальный публичный API из
[руководства общей библиотеки](command-package.md#current-imports) и его
[примеров](https://github.com/SbWereWolf/command-execution/blob/master/docs/usage.md).
Выбирайте package/contract checks, соответствующие конкретным metadata/API и
входным данным. Имя файла теста само по себе не доказывает применимость к другой
major-версии; ожидаемые результаты не ослабляют ради успешного запуска.

## Сборка и поставка

Корень сборки CE — выбранный checkout `command-execution` с его `pyproject.toml`.
EM собирается отдельно и выбирает точную зависимость через metadata.
[Руководство пакета](command-package.md#самостоятельный-пакет) описывает
актуальные импорты, установку и единовременное итоговое обновление потребителей.

Source commit/tree, version, actual digest, runtime/tool identity, полные проверки и независимая приёмка принадлежат квитанции вне архива, чей digest она описывает. Python build выполняйте в подготовленной среде из корня именно собираемого проекта: самостоятельного `command-execution` для библиотеки либо `environment-maintenance` для SDK. Команда без аргумента исходника собирает текущий проект:

```bash
"$app_python" -m build --no-isolation --outdir /absolute/path/to/owned-output
```

Wheel/sdist/npm — разные артефакты. Исполняйте и передавайте выбранные байты. Изменение source/docs после сборки требует нового соответствующего артефакта и актуального proof. Интеграция, runtime delivery, tag/publish/push и обновление consumers имеют своих владельцев и полномочия. Task working material удаляется после доставки/интеграции и завершения обязательных consumers; отдельный архив по умолчанию не создаётся.

## Узкая проверка сетевого согласования

`test_network_adjustment` и выбранные settings controls сохраняют [сетевой договор](settings-alignment.md#автоматический-подбор-портов). Его `owner.pid/start_ticks` описывают владельца порта; PGID launch registry имеет другого владельца. Выбирайте конкретные затронутые случаи и prerequisites.

## Проверки цепочки данных

Примеры [sync/async и данных](action-execution.md#цепочки-с-передачей-данных)
используют установленный EM и его прикладные функции. CE2 предоставляет
отдельные классы; не импортируйте из него EM-фасады.

Для адресной проверки текущей границы EM/CE выберите подготовленный developer
Python с pytest и точной CE-зависимостью. Из корня выбранного checkout:

```bash
PYTHONPATH=src "${app_python:?Выберите developer Python с pytest и выбранным CE}" -B -m pytest \
  -p no:cacheprovider -q \
  tests/test_resource_checks.py::test_public_check_api_preserves_full_bytes_and_context \
  tests/test_settings_alignment.py::test_public_api_adjust_preserves_bytes_and_real_settings
```

Ожидаются два успешных случая с фактическими байтами/контекстом и изменением
собственных тестовых settings. Они не требуют GUI. Это адресное наблюдение,
а не полная проверка выпуска или внедрение каждой установки. Полные
[SDK-примеры](action-execution.md#пример-цепочки) отдельно показывают snapshots,
next_input и callback; у вызывающего остаётся владение временем жизни runtime.
