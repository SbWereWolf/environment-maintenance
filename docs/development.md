# Разработка и выпуск

## Подготовка

Выберите source revision и подготовленное окружение приложения. Infra/deps/adjust/check выполняет настроенный внешний environment-maintenance через декларации владельца, в том числе для worktree. Самостоятельную установку описывает [инструкция](installation.md#установка-из-исходников). `app_python` ниже — абсолютный Python выбранного экземпляра; installed `.py` должны совпадать с source.

## Ответственность модулей

| Owner | Ответственность |
|---|---|
| `configuration` | Operations mapping, ordered unique selection, CRUD, JSON reader/atomic writer |
| `cli` | Стандартный argparse для всех аргументов, ранние предупреждения и композиция шести команд |
| `invocation` | Пути/defaults и декодирование CLI selection с общей проверкой формы/уникальности из `configuration` |
| `output` | Чистое форматирование уже закодированного JSON: pretty/one-line без IO и решений об исполнении |
| `actions` | Plan/execute, ResultInterpreter, полный transport, optional exit-code interpreter |
| `preparation`, `checking`, `network` | Подготовка, presence/availability, командное/сетевое согласование |
| `running` | Именованные use cases, raw submitted PGID, presentation, SIGTERM и module launcher |
| `registry` | Payload, shared OS temp, exclusive empty creation под коротким flock, публикация/удаление |

Представление результатов и exit status остаются у CLI-входов операций; они передают готовые данные в `output`, затем печатают результат. [Общий договор формата и предупреждений](configuration.md#формат-json) принадлежит CLI.

[Run/list/stop](process-launch.md#запуск-процессов) использует прежний ActionExecutor. Файловая граница не владеет командами приложения. `environment_maintenance.running.console` имеет одну реализацию; example делегирует. [Seed источники](requirements/README.md) не являются runtime dependency.

## Проверки

Обычная Task выбирает адресные tests по изменённой границе; full/release suite принадлежит отдельной проверке выпуска. Сохраняйте source/tree, argv/cwd, полные streams/exit, actual package digest и closure собственных ресурсов.

Формат/аргументы/порядок диагностик проверяет `tests/test_cli_output.py`, настоящую npm-установку и её CLI — `tests/test_cli_output_package.py`. Затронутые прежние договоры покрывают `test_run_stop`, `test_cli_contract`, `test_run_stop_consumers`, `test_runtime_components`, `test_reservation_failure`; SDK/servicing/network/npm controls выбираются адресно. Перед npm checks подготовьте свои `ENV2_PACKAGE_TEST_ROOT`, `ENV2_PACKAGE_WHEELHOUSE` с настоящими build/runtime wheels и абсолютный `ENVIRONMENT_MAINTENANCE_PYTHON`. Это arrangement тестов, не настройки продукта.

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

## Сборка и поставка

Source commit/tree, version, actual digest, runtime/tool identity, полные проверки и независимая приёмка принадлежат квитанции вне архива, чей digest она описывает. Python build в подготовленной среде:

```bash
"$app_python" -m build --no-isolation --outdir /absolute/path/to/owned-output
```

Wheel/sdist/npm — разные артефакты. Исполняйте и передавайте выбранные байты. Изменение source/docs после сборки требует нового соответствующего артефакта и актуального proof. Интеграция, runtime delivery, tag/publish/push и обновление consumers имеют своих владельцев и полномочия. Task working material удаляется после доставки/интеграции и завершения обязательных consumers; отдельный архив по умолчанию не создаётся.

## Узкая проверка сетевого согласования

`test_network_adjustment` и выбранные settings controls сохраняют [сетевой договор](settings-alignment.md#автоматический-подбор-портов). Его `owner.pid/start_ticks` описывают владельца порта; PGID launch registry имеет другого владельца. Выбирайте конкретные затронутые случаи и prerequisites.
