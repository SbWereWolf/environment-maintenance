# Подготовка инфраструктуры и зависимостей

## Подготовка ресурсов

[Пошаговая инструкция всех возможностей](#пошаговая-инструкция).

Эта возможность доступна в npm-поставке 4.0.0 и её исходниках. Подготовка
исполняет объявленные внешние инструменты: сами установщики, конфиги и обработчики
предоставляет обслуживаемое приложение или его оператор. Это не встроенный
установщик ERP, Poise, Composer или инфраструктурных сервисов.

Установленный npm-вход `start-app` вызывает тот же CLI собственным Python.
[Правильная npm-инструкция](npm-distribution.md#пошаговая-инструкция) отдельно
проверяет короткий bin из постороннего cwd. Примеры ниже с `PYTHONPATH=src`
выбирают исходный набор; он может находиться внутри установленного пакета по
[общей инструкции](npm-distribution.md#библиотека-и-поставленные-примеры).
Корневой `./start-app` выбирает установленную рядом `.venv`.
[Постоянный вход](persistent-entry.md#постоянный-вход-выбранной-установки)
задаёт короткие команды и необязательные переопределения для объявленных операций.
Существующие экземпляры 1.0.0 обновляются только отдельной явной установкой.

## Библиотечный вход

```python
from environment_maintenance import prepare_resources

prepare_resources(config_path, operation, selection, parameters,
                  base_dir=base_dir, interpreters=interpreters)
```

Все шесть аргументов обязательны; последние два передаются по имени.

| Аргумент | Значение |
|---|---|
| `config_path` | Строка или `Path` главного JSON-файла |
| `operation` | Имя выбранной операции в `operations` главного файла |
| `selection` | Строка `"all"` либо массив строковых IDs |
| `parameters` | Карта строковых имён и значений `str`, `int`, `float`, `bool` |
| `base_dir` | Явный абсолютный путь `str` или `Path` для относительных cwd команд |
| `interpreters` | Карта имени → готовый объект с методом `interpret(result, options)` |

`all` выбирает порядок документа; массив уникальных IDs сохраняет свой порядок. Повторы IDs в документе или selection отвергаются до эффектов. SDK неизвестный ID отвергает, CLI предупреждает и пропускает.
`["all"]` выбирает обычное требование с таким ID. Пустой массив и пустой документ
требований дают успешный результат без процессов. Общие входы `parameters`,
`base_dir`, `interpreters` проверяются независимо от размера выборки. API требует
карту интерпретаторов; пригодность выбранных объектов проверяется при планировании.
Полные правила выбора принадлежат [библиотеке чтения](configuration-reading.md#публичный-договор).

В командном режиме сначала читается вся выборка и подготавливаются все её цепочки;
только затем последовательно исполняются требования и их команды. Ошибка подготовки позднего
выбранного требования имеет контекст операции/ID и возникает до первого процесса.
Будущие cwd или executable могут быть созданы ранней командой: их существование
не является условием построения плана. Сам библиотечный исполнитель читает
декларации; эффекты объявленных команд принадлежат внешним инструментам. Файловый сетевой `adjust` обновляет выбранные
параметры по [собственному договору](settings-alignment.md#автоматический-подбор-портов).

При первом `failed` исполнение останавливается с сохранением уже попытанной работы.
Библиотека не откатывает её и не повторяет команды. Подтверждение предметного
успеха принадлежит интерпретатору; он может принять ненулевой код внешнего процесса.

## Конфигурация и подключение обработчиков

Отслеживаемые обезличенные примеры:
[главный файл](../examples/resource-preparation/app.example.json),
[инфраструктура](../examples/resource-preparation/infra.example.json),
[зависимости](../examples/resource-preparation/deps.example.json).

В главном файле `operations` сопоставляет имя операции пути к документу.
Относительный путь считается от каталога главного файла, абсолютный используется
непосредственно. Документ run содержит applications, остальные операции — массив полных `requirements` с
уникальными IDs. У каждого командного требования есть непустой `commands`.
Сетевые требования `adjust` используют [явную декларацию network](settings-alignment.md#декларация-сетевого-согласования);
для них нужен файловый CLI, а не карта значений библиотечного API.
Общее чтение документов и командная ветвь используются для infra/deps и
отдельного [согласования adjust](settings-alignment.md#согласование-настроек).

Полный справочник `argv`, `cwd`, `env`, `interpreter.name/options`, однократной
подстановки стандартным `string.Template` и интерфейса ответа находится в
[договоре действий](action-execution.md#публичные-функции-и-аргументы).
Окружение команды задаётся полностью; окружение хоста автоматически не добавляется.
Параметры подставляются в argv/cwd/значения env, а не в настройки обработчика.
Необходимые исполняемые инструменты выбираются в конфиге, а не в коде приложения.

Для CLI главный файл дополнительно содержит обязательный объект `interpreters`:

| Поле | Назначение |
|---|---|
| Ключ в `interpreters` | Непустое имя, используемое командой |
| `module` | Непустое имя Python-модуля для стандартного `importlib.import_module` |
| `attribute` | Непустое имя готового объекта в этом модуле |

Все объявленные объекты загружаются до процессов, включая пустую выборку. У каждого
должен быть вызываемый `interpret`. Это готовый объект, не класс или фабрика.
Обеспечьте доступность модуля обычным Python import path выбранной среды.
В [учебном модуле](../examples/resource-preparation/interpreters.py) объект
`exit_result` доступен как `module: "interpreters"`, `attribute: "exit_result"`.
В API реестр готовых объектов передаёт вызывающий; эти CLI-декларации его не заменяют.
Рабочие конфиги создаёт и исключает из Git их владелец; примеры остаются в Git.

## Команды и аргументы

[Пошаговая инструкция](#пошаговая-инструкция).

CLI предоставляет `infra`, `deps`, `adjust` и отдельный
[запуск процессов `run`](process-launch.md#запуск-процессов).
Обычные вызовы — `./start-app infra` и `./start-app deps`. Нужные значения
задаёт [постоянный профиль](persistent-entry.md#поля-постоянного-профиля);
следующие ключи необязательно переопределяют их для одного вызова:

| Аргумент | Назначение |
|---|---|
| `--config PATH` | Главный UTF-8 JSON-файл с `operations` и `interpreters` |
| `--parameters PATH` | Один существующий UTF-8 JSON-объект скаляров; для сетевого `adjust` также выбранный выходной файл |
| `--base-dir ABSOLUTE_PATH` | Абсолютный базовый путь для cwd внешних команд |
| `--requirements SELECTION` | Буквальное `all` или JSON-массив строковых IDs, например `'["assets"]'` или `'[]'` |
| `-h`, `--help` | Справка без исполнения |
| `--version` | Версия выбранного экземпляра без исполнения |

Значения этих ключей действуют только на текущий вызов. При полностью явном
вызове блок `invocation` не требуется. `--config` и `--parameters` могут быть относительны к cwd вызывающего процесса;
`--base-dir` должен быть абсолютным. Для значений нет объединения нескольких файлов,
чтения параметров из окружения или CLI-переопределений: передаётся один полный объект.
Выбирайте JSON-скаляры, пригодные для требуемых подстановок.

Применимость флагов определяет [общий CLI справочник](configuration.md#команды-и-аргументы). Infra/deps/adjust по умолчанию выбирают all без invocation.requirements. Run использует [APP/ENV](process-launch.md#входы-и-аргументы), check — свой [договор](resource-checking.md#команды-и-аргументы). Неизвестные аргументы предупреждаются/пропускаются.

## Результат и диагностика

Командный API возвращает объект:

| Поле | Содержание |
|---|---|
| `operation` | Выбранное имя операции |
| `status` | `succeeded` или `failed` |
| `requirements` | Только попытанные записи в порядке исполнения: `{id, result}` |
| `error` | `None` при успехе, контекст операции/ID и причины при неуспехе |

Каждый `result` содержит `status`, `commands`, `error` и полные
[записи команд](action-execution.md#итог-исполнения): invocation, выбранный interpreter,
реальный exit_code, stdout/stderr, interpretation и error. Непопытанные требования
не добавляются как успешные. При пустой выборке `requirements=[]`, `error=None`.
API сохраняет полные bytes потоков и непрозрачные значения/метаданные обработчика.

CLI печатает один JSON-объект и LF; код `0` означает подтверждённый успех, `1` —
неуспех с полным доступным частичным результатом. Оба сырых потока каждой команды
кодируются отдельно как `{"encoding":"base64","data":"..."}`; для пустого потока
`data=""`. `base64.b64decode(data, validate=True)` восстанавливает точные bytes.
Диагностика stderr внешней команды остаётся внутри этого результата.

Выбранные метаданные подготовленных команд, отражаемые в CLI-ответе, проверяются
на обычную JSON-представимость до процессов. Ответ `interpret` проверяется после
соответствующего процесса: JSON-скаляры, массивы и объекты со строковыми ключами,
конечные числа; дополнительные пригодные поля сохраняются. Непригодный ответ даёт
`failed` с сырыми потоками. Эти транспортные ограничения CLI не распространяются
на opaque Python-значения библиотечного API. Невыбранные цепочки не планируются.

Ошибка входных файлов/выбора/параметров/подготовки или загрузки обработчика даёт
`ValueError` API либо CLI-код `2`, диагностику в stderr и пустой stdout до процессов.
Прочитайте причину и подготовьте корректные явные входы. Для `failed` сначала
изучите фактические эффекты и записи: владелец внешнего инструмента решает,
как продолжить. Автоматический ремонт и счётчик попыток здесь не добавлены.

Сетевой `adjust` CLI согласует всю выбранную сетевую транзакцию и сохраняет
параметры одной публикацией. Его `commands=[]`, коды отказа, порядок и сохранность
файла описаны в [сетевом результате](settings-alignment.md#результат-и-отказ-сетевого-режима).
Командные и сетевые требования выбираются отдельными вызовами.

## Пошаговая инструкция

Предусловия: выбранный исходный checkout, Python 3.11+ и зависимости по
[подготовке](development.md#подготовка). Выполняйте из корня checkout:

```bash
: "${app_python:?Выберите Python по npm-инструкции или подготовке разработчика}"
PYTHONPATH=src "$app_python" -B examples/resource-preparation/walkthrough.py
```

Скрипт использует только собственный `TemporaryDirectory`, рабочие копии трёх
JSON и локальный [probe](../examples/resource-preparation/probe.py). Сервисы ERP,
Poise, Redis, Composer не нужны. Копии и эффекты удаляются при выходе, исходные
примеры проверяются на побайтную сохранность. Ожидаются код0 и семь строк:

```text
api infra: install, configure, later; full bytes
api deps: separate configuration
selection: unique ordered IDs, empty without effects
plugin: same name; opaque API value
cli infra: exit0; full streams decoded
cli deps: exit0; full streams decoded
outcome: exit1; partial work retained; later not started
```

### Подготовить инфраструктуру и зависимости через API

`prepare_demo(workspace)` из walkthrough — учебный helper, не дополнительный API.
Он копирует конфиги и создаёт `values.json` с выбранными абсолютными путями Python,
probe, маркера, явным `token="demo value"` и `state="ready"`.

```bash
PYTHONPATH=src:examples/resource-preparation "$app_python" -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from walkthrough import prepare_demo, assert_result, clear_events
from environment_maintenance import prepare_resources

with TemporaryDirectory() as temporary:
    workspace = Path(temporary)
    config, parameters, registry = prepare_demo(workspace)
    result = prepare_resources(config, "infra", "all", parameters,
                               base_dir=workspace, interpreters=registry)
    assert_result(result, ["assets", "later"], ["install", "configure", "later"], workspace)
    clear_events(workspace)
    result = prepare_resources(config, "deps", "all", parameters,
                               base_dir=workspace, interpreters=registry)
    assert_result(result, ["packages"], ["dependencies"], workspace)
PY
```

Первый вызов подтверждает последовательность установки/настройки и позднего
ресурса, второй — независимый конфиг зависимостей. Проверяются реальные маркеры,
полные invocation/env и bytes обоих потоков. Успешный snippet завершается кодом0.

### Выбрать требования и заменить интерпретатор

В walkthrough выбор `["later", "assets"]` даёт две записи и три команды. Корректный `[]` даёт пустой успешный итог без маркеров.
Под тем же именем `result` затем передаётся `OpaqueResult`: значение интерпретации
становится исходными bytes, а интерфейс и конфиги остаются прежними.
Соответствующие третья и четвёртая строки подтверждаются assertions эффекта и типа.
Для собственного инструмента используйте тот же
[структурный интерфейс](action-execution.md#интерфейс-интерпретатора).

### Выполнить CLI с явными файлами

Следующий корректный сценарий создаёт собственные рабочие файлы и запускает CLI
реальным subprocess, не вызывая его Python-функцию напрямую:

```bash
PYTHONPATH=src:examples/resource-preparation "$app_python" -B - <<'PY'
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from walkthrough import prepare_demo, assert_result, clear_events

with TemporaryDirectory() as temporary:
    workspace = Path(temporary)
    config, _, _ = prepare_demo(workspace)
    for operation, ids, labels in (
        ("infra", ["assets", "later"], ["install", "configure", "later"]),
        ("deps", ["packages"], ["dependencies"]),
    ):
        clear_events(workspace)
        process = subprocess.run([
            sys.executable, "-B", "-m", "environment_maintenance", operation,
            "--config", str(config), "--parameters", str(workspace / "values.json"),
            "--base-dir", str(workspace), "--requirements", "all",
        ], env=os.environ.copy(), capture_output=True)
        assert process.returncode == 0 and process.stderr == b""
        assert_result(json.loads(process.stdout), ids, labels, workspace, encoded=True)
PY
```

`PYTHONPATH` предоставляет исходники и учебный модуль `interpreters`; он не
попадает автоматически в env команд ресурса. После отдельной пакетной поставки
того же кода console entry позволяет короткий вызов с подготовленными файлами:

```text
./start-app infra --config MAIN --parameters VALUES --base-dir ABSOLUTE_BASE --requirements all
./start-app deps --config MAIN --parameters VALUES --base-dir ABSOLUTE_BASE --requirements '["packages"]'
```

Здесь MAIN/VALUES/ABSOLUTE_BASE — обозначения явных путей, не готовые локальные файлы.
Этот walkthrough явно проверяет выбранный source-модуль; установленный npm bin
отдельно проверяется в [npm-инструкции](npm-distribution.md#пошаговая-инструкция).

### Получить обычный предметный неуспех

Последняя часть walkthrough задаёт корректное состояние ресурса `busy`.
Учебный probe выполняет первую команду и сообщает код3; настроенный обработчик
возвращает `command exit code is not accepted`. CLI имеет код1 и полный JSON с одной попытанной
командой `install`, реальными потоками и маркером. `configure` и требование `later`
не запускались. Итоговая седьмая строка подтверждает эти факты; это правильное
использование диагностирующего инструмента, а не ошибка формы запроса.

## Собственный внешний инструмент

Если готовые инструменты не обеспечивают требуемого поведения, разработайте
собственный. Для получения IDs/объектов используйте [чтение](configuration-reading.md#библиотека-чтения),
для точечных изменений — [CRUD](configuration-editing.md#библиотека-записи),
для исполнения — этот API или CLI с вашим готовым `interpret`.
Команды и предметный анализ принадлежат обслуживаемому приложению; универсальный
исполнитель не угадывает правила установки и восстановления его ресурсов.
