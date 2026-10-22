# Согласование настроек

[Пошаговая инструкция всех возможностей](#пошаговая-инструкция).

`adjust` выполняет выбранные внешние действия для согласования настроек ресурсов
и приложений. Команды и их предметные правила предоставляет обслуживаемое
приложение. Операция вызывается явно; это не автоматический шаг `infra`, `deps`,
`check` или `run`. Общий исполнитель не знает имён очередей, адресов и портов.

Возможность реализована в исходниках разработки 2.0. Выберите исходный checkout
и Python с [объявленными зависимостями](development.md#подготовка), задайте
`PYTHONPATH=src`. Установленный пакет 1.0.0 и корневой `./start-app` остаются
прежними; изменение исходников не является выпуском или переустановкой пакета.
В выбранном checkout `python -m environment_maintenance` использует ту же
CLI-функцию, на которую указывает пакетное короткое имя `start-app`.

## Входы и результаты

Форма входа выбранных исходников:

```text
python -m environment_maintenance adjust --config MAIN --parameters VALUES --base-dir ABS --requirements SELECTION
```

После отдельной пакетной поставки того же кода форма console entry:

```text
start-app adjust --config MAIN --parameters VALUES --base-dir ABS --requirements all
```

Обозначения MAIN/VALUES/ABS заменяются явными подготовленными путями. Все четыре
рабочих аргумента обязательны:

| Аргумент | Значение |
|---|---|
| `--config PATH` | Главный JSON описания действий с `operations.adjust` и готовыми `interpreters` |
| `--parameters PATH` | Один полный JSON-объект скалярных значений для placeholders |
| `--base-dir ABS` | Абсолютный базовый каталог для относительного cwd команд |
| `--requirements SELECTION` | `all`, JSON-массив выбранных IDs или `[]` |
| `-h`, `--help` | Общая справка без исполнения |
| `--version` | Версия приложения без исполнения; исходное расширение не переименовывает выпущенный пакет |

Относительные пути `--config`/`--parameters` считаются от cwd вызывающего.
Полные общие правила, типы и коды завершения принадлежат
[входу подготовки](resource-preparation.md#команды-и-аргументы) и
[результату](resource-preparation.md#результат-и-диагностика).
`all` сохраняет порядок документа, массив — порядок выбранных IDs.
Пустая выборка проверяет общие входы, но не запускает процессы.

Библиотека не получает нового синонима: используйте прежнюю
`prepare_resources(config, "adjust", selection, parameters, base_dir=..., interpreters=...)`.
Все выбранные цепочки планируются до эффектов, затем исполняются последовательно.
Итог содержит operation/status/requirements/error и только попытанные действия.
API сохраняет полные bytes, CLI кодирует каждый поток обратимым base64.
`0` — подтверждённый успех; `1` — неуспех с доступной частичной работой;
`2` — ошибка входа или подготовки до процессов. Диагностика внешней команды
остаётся внутри результата, а не теряется в общем сообщении.

## Конфигурация примера

Два независимых владельца данных:

| Файл | Назначение |
|---|---|
| [app.example.json](../examples/settings-alignment/app.example.json) | `operations.adjust` выбирает описание действий; `interpreters.result` указывает готовый `module=interpreters`, `attribute=exit_result` |
| [adjust.example.json](../examples/settings-alignment/adjust.example.json) | Требование `queue-agreement`, его последовательность `commands` и явные argv/cwd/env/interpreter |
| [settings.example.json](../examples/settings-alignment/settings.example.json) | Отдельное сопоставление `operations.applications` изменяемому документу |
| [applications.example.json](../examples/settings-alignment/applications.example.json) | Выбранные writer/reader, посторонний cache, дополнительные команды и непрозрачные поля |
| [parameters.example.json](../examples/settings-alignment/parameters.example.json) | Полный обезличенный пример значений подстановки |

Относительное сопоставление операции считается от главного файла. ID требования
в описании действий не обязан совпадать с ID изменяемого приложения. В примере
`queue-agreement` вызывает инструмент для объектов `writer` и `reader`.

Объекты `commands` в applications — изменяемые данные примера. Их здесь не
передают исполнителю действий. В частности, образец хранит только env-позиции,
а не заявляет готовые команды запуска реальных приложений.

Подготовьте собственные рабочие копии; отслеживаемые examples остаются образцами.
Рабочие конфиги исключает из Git владелец их рабочего каталога. Заполните все
значения параметров:

| Параметр | Явное значение |
|---|---|
| `python` | Абсолютный путь к подготовленному Python |
| `tool` | Абсолютный путь к реальному align_queue.py выбранного checkout |
| `settings_config` | Путь к рабочему главному конфигу изменяемых настроек |
| `operation` | Выбранное в нём имя, в образце `applications` |
| `writer`, `reader` | Два выбранных существующих ID |
| `variable` | Существующий env-ключ первой команды обоих выбранных объектов |
| `queue` | Выбранное целевое значение, в образце `billing.jobs` |
| `source_path` | Абсолютный путь к src выбранного checkout для Python внешнего инструмента |

Стандартный `string.Template` подставляет `${name}` однократно в argv/cwd/env;
shell и собственный renderer не используются. Поле `cwd="."` считается от
переданного base_dir. `env` команды явно предоставляет PYTHONPATH/source_path
и PYTHONDONTWRITEBYTECODE; окружение хоста автоматически не наследуется.
`interpreter.name=result` выбирает готовый объект с `options.accept=[0]`.
Его [существующий учебный модуль](../examples/resource-preparation/interpreters.py)
должен быть доступен CLI через обычный Python import path. Все объявления
module/attribute загружаются до процессов. Полный
[договор действий](action-execution.md#публичные-функции-и-аргументы)
и [подключение обработчика](resource-preparation.md#конфигурация-и-подключение-обработчиков)
остаются общими.

## Отдельный инструмент согласования

[align_queue.py](../examples/settings-alignment/align_queue.py) — самостоятельный
внешний процесс примера обслуживаемого приложения, не встроенное правило ядра.
Он использует публичную библиотеку и стандартный JSON Pointer. Все шесть
аргументов обязательны:

| Аргумент | Значение |
|---|---|
| `--config PATH` | Главный конфиг изменяемых настроек, не описание действий |
| `--operation NAME` | Выбранное имя в operations этого конфига |
| `--writer ID` | Первый выбранный объект |
| `--reader ID` | Второй выбранный объект |
| `--queue-variable NAME` | Env-ключ первой команды обоих объектов |
| `--queue VALUE` | Целевое строковое значение |
| `-h`, `--help` | Справка без чтения или изменения настроек |

Инструмент пакетно читает оба ID и обе позиции до первой записи, точечно
заменяет выбранные значения через `update_requirement`, перечитывает их
и подтверждает результат. Остальные поля, команды и объекты сохраняются.
При успехе код `0`, пустой stderr и один JSON+LF с полями
`status="succeeded"`, writer, reader, variable, queue из выбранных входов.
Обычная ошибка чтения/изменения/подтверждения даёт `1`, пустой stdout и причину
в stderr. Форму аргументов обрабатывает стандартный argparse с кодом `2`.

Каждый update публикует один документ по существующему договору библиотеки.
Два обновления не являются общей транзакцией: ошибка второй записи может оставить
первое изменение. Успех появляется только после перечитывания обеих сторон.
Для диагностики прочитайте полный результат команды и текущее сохранённое
состояние; дальнейшее действие выбирает владелец инструмента. Автоматических
повторов, ремонта и отката общего исполнителя здесь нет.

## Пошаговая инструкция

Предусловия: исходный checkout с принятым инструментом, подготовленный Python
и объявленные jsonpatch/jsonpointer. Выполняйте из корня выбранного checkout:

```bash
app_python=/absolute/path/to/environment-maintenance/.venv/bin/python
PYTHONPATH=src "$app_python" -B examples/settings-alignment/walkthrough.py
```

[Walkthrough](../examples/settings-alignment/walkthrough.py) создаёт собственные
TemporaryDirectory, копирует пять JSON, заполняет пути выбранного Python/src/tool,
исполняет реальные API/CLI/инструмент и проверяет итоговый файл. Рабочие копии
удаляются при выходе; исходные примеры проверяются на побайтную сохранность.
Никакие сервисы ERP/Poise, брокер или сеть не требуются.
Ожидаются код `0` и четыре строки:

```text
api adjust: selected values confirmed; other settings preserved
cli adjust: selected requirement; complete result
selection: empty succeeds without writes
tool: selected variable; confirmed values
```

### Согласовать через API

Учебный prepare_demo создаёт только входы, не реализует согласование:

```bash
PYTHONPATH=src:examples/settings-alignment "$app_python" -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from environment_maintenance import prepare_resources
from walkthrough import prepare_demo, assert_result, assert_settings

with TemporaryDirectory() as temporary:
    workspace = Path(temporary)
    config, parameters, registry, before = prepare_demo(workspace)
    result = prepare_resources(config, "adjust", "all", parameters,
                               base_dir=workspace, interpreters=registry)
    assert_result(result, encoded=False)
    assert_settings(workspace, before, "QUEUE_NAME", "billing.jobs")
PY
```

Код `0` подтверждает две целевые QUEUE_NAME, полные потоки и сохранность всего
остального документа, включая cache, вторую команду writer и false/0.

### Выбрать требование через CLI

Вторая часть walkthrough передаёт `'["queue-agreement"]'` через --requirements,
запускает source CLI из постороннего cwd и явно предоставляет import path для
исходников/готового обработчика. Она проверяет код `0`, фактический файл
и декодирует полный JSON/base64 результат команды. Третья часть передаёт `'[]'`,
проверяет пустой успешный итог и побайтную неизменность файла.

Для собственных подготовленных рабочих копий используйте форму:

```text
PYTHONPATH=SOURCE:PLUGIN_DIR PYTHON -B -m environment_maintenance adjust --config MAIN --parameters VALUES --base-dir ABS --requirements '["queue-agreement"]'
```

SOURCE/PLUGIN_DIR/PYTHON/MAIN/VALUES/ABS обозначают выбранные реальные пути;
выполняемый walkthrough уже заполняет их. Переменная PYTHONPATH внешней
команды отдельно объявляется внутри её env, а не наследуется автоматически.

### Запустить инструмент непосредственно

Четвёртая часть walkthrough выполняет шесть аргументов напрямую: выбирает
OTHER_QUEUE и archive.jobs, оставляя QUEUE_NAME и прочие данные прежними.
Для отдельной собственной копии:

```bash
PYTHONPATH=src:examples/settings-alignment "$app_python" -B - <<'PY'
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from walkthrough import ROOT, TOOL, prepare_demo, assert_settings

with TemporaryDirectory() as temporary:
    workspace = Path(temporary)
    _, _, _, before = prepare_demo(workspace)
    process = subprocess.run([sys.executable, "-B", str(TOOL),
        "--config", str(workspace / "settings.example.json"), "--operation", "applications",
        "--writer", "writer", "--reader", "reader", "--queue-variable", "OTHER_QUEUE",
        "--queue", "archive.jobs"],
        env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), capture_output=True)
    assert process.returncode == 0 and process.stderr == b""
    assert_settings(workspace, before, "OTHER_QUEUE", "archive.jobs")
PY
```

Справка обоих входов не меняет конфигурацию:

```bash
PYTHONPATH=src "$app_python" -B -m environment_maintenance --help
PYTHONPATH=src "$app_python" -B examples/settings-alignment/align_queue.py --help
```

## Собственный внешний инструмент

Если существующие инструменты не обеспечивают требуемое поведение, разработайте
свой инструмент обслуживаемого приложения. Используйте
[пакетное чтение](configuration-reading.md#библиотека-чтения),
[точечный CRUD и каждую его операцию](configuration-editing.md#библиотека-записи)
и [действия со сменным интерпретатором](action-execution.md#библиотека-исполнения).
Самостоятельно определите предметную политику и подтверждение фактического
состояния. Пример очередей не задаёт всем инструментам структуру env/commands.
Передайте команду и явные параметры в собственное описание adjust; общий
исполнитель остаётся тем же и не получает кода для вашей инфраструктуры.
