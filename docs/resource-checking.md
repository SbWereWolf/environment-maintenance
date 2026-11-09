# Проверка окружения

[Пошаговая инструкция всех возможностей](#пошаговая-инструкция).

Проверка доступна в npm-поставке 4.0.0 через `./start-app check` и API.
Она проверяет наличие ресурсов инфраструктуры и зависимостей, предоставленные
условия пригодности и дополнительные связанные настройки. Она не устанавливает
ресурсы, не вызывает `adjust` и не запускает обслуживаемое приложение.
[Установка и короткий вход](npm-distribution.md#пошаговая-инструкция) используют
собственный runtime. [Контекст API-примеров](npm-distribution.md#библиотека-и-поставленные-примеры)
позволяет выбрать bundled source внутри пакета. 1.0.0 остаётся отдельной
поставкой; фактически проверенные платформы перечислены в npm-договоре.

## Библиотечный вход

```python
from environment_maintenance import check_resources

result = check_resources(config_path, parameters, base_dir=base_dir, interpreters=interpreters)
```

Все четыре аргумента обязательны, последние два — именованные.

| Аргумент | Значение |
|---|---|
| `config_path` | Строка или `Path` главного UTF-8 JSON-файла |
| `parameters` | Карта строковых имён к скалярам `str`, `int`, `float`, `bool` |
| `base_dir` | Явный абсолютный `str` или `Path`, база относительных cwd команд |
| `interpreters` | Карта имён к готовым объектам с вызываемым `interpret(result, options)` |

Проверяются все требования из `infra`, `deps` и `check`; аргумента выборки здесь
нет. Для чтения выбранных объектов другим инструментом используется
[публичное пакетное чтение](configuration-reading.md#публичный-договор).
Относительный главный путь считается от cwd вызывающего, сопоставленный путь
документа — от каталога главного файла; абсолютные пути используются прямо.
Конфигурация и файлы обслуживаемого приложения проверкой не изменяются.

## Конфигурация проверок

Отслеживаемые обезличенные образцы:
[главный](../examples/resource-checking/app.example.json),
[инфраструктура](../examples/resource-checking/infra.example.json),
[зависимости](../examples/resource-checking/deps.example.json),
[дополнительные проверки](../examples/resource-checking/check.example.json),
[явные параметры](../examples/resource-checking/parameters.example.json).
Рабочие конфиги создаёт их внешний владелец и исключает из Git; примеры сохраняются.
Перед использованием заполните параметры фактическими путями своего экземпляра.
Walkthrough делает это только в собственных временных копиях.

Главный `operations` обязательно сопоставляет все три имени `infra`, `deps`,
`check` отдельным документам общей [схемы чтения](configuration-reading.md#формат-конфигов).
В каждом документе `requirements` — массив объектов с уникальным непустым `id`.
Явный пустой массив допустим. Одинаковый ID разных документов сохраняется
разными записями с указанием операции.

| Поле ресурса `infra`/`deps` | Значение |
|---|---|
| `id` | Идентификатор внутри документа |
| `checks` | Объект объявленных условий |
| `checks.presence` | Обязательное действие наличия с непустым `commands` |
| `checks.availability` | Необязательное действие пригодности с непустым `commands` |
| Остальные поля | Данные владельца ресурса, сохраняемые читателем |

Отсутствующий ключ `availability` означает непредоставленную проверку;
предоставленный ключ обязан содержать действие, а не `null`.
Команды установки из `requirements[].commands`, если объявлены, здесь остаются
данными и не вызываются. Проверочные образцы выше акцентируют `checks` и не
объявляются профилем установки инфраструктуры. Дополнительный `check`-документ
содержит обычные действия `id`/`commands`, например проверку выбранной очереди.

Поля `argv`, `cwd`, `env`, `interpreter.name/options`, стандартная однократная
подстановка `string.Template` и ответ обработчика имеют
[единый договор действий](action-execution.md#публичные-функции-и-аргументы).
Окружение дочернего процесса задаётся полностью в `env`.
Существование будущих executable/cwd не проверяется планировщиком.
Для CLI главный файл также предоставляет готовые объекты по
[договору module/attribute](resource-preparation.md#конфигурация-и-подключение-обработчиков).
Пример переиспользует `exit_result` из `examples/resource-preparation/interpreters.py`;
его модуль доступен через обычный Python import path. API получает объекты
через свой аргумент и не заменяет их декларациями CLI.

## Команды и аргументы

[Пошаговая инструкция](#пошаговая-инструкция).

Обычный вход — `./start-app check` с [постоянным профилем](persistent-entry.md#поля-постоянного-профиля).
Следующая полностью явная форма остаётся доступна для необязательных переопределений:

```text
python -m environment_maintenance check --config MAIN --parameters VALUES --base-dir ABS
```

| Аргумент | Значение |
|---|---|
| `check` | Проверить ресурсы и дополнительные условия |
| `--config MAIN` | Необязательный выбор главного файла с `operations` и `interpreters` |
| `--parameters VALUES` | Необязательный путь к одному JSON-объекту полных явных скалярных значений |
| `--base-dir ABS` | Необязательное переопределение абсолютной базы cwd команд |
| `-h`, `--help` | Справка без рабочих аргументов и действий |
| `--version` | Версия выбранного экземпляра без действий |

MAIN/VALUES могут быть относительны к cwd вызывающего. Применяются постоянный профиль и явные overrides. Неизвестные аргументы предупреждаются/пропускаются; check всегда проверяет свой полный состав. CLI selection через requirements ему не задаёт фильтр. Run/stop имеют [собственный договор](process-launch.md#запуск-процессов).

## Порядок и результат

До первого процесса проверяются общие входы, все три документа и все объявленные
планы, включая условную availability и отражаемые CLI JSON-данные. Это верно
и для пустых списков. Затем проверяются ресурсы `infra`, ресурсы `deps` и
дополнительные проверки `check` — в порядке своих документов.

Для ресурса сначала выполняется presence. При её успехе выполняется объявленная
availability. При неуспехе presence она пропускается; независимые ресурсы и
дополнительные проверки продолжаются. Внутри каждого действия первая ошибка
останавливает только его цепочку. Отсутствующая availability остаётся
непредоставленной даже после неуспеха presence.

| Верхнее поле | Содержание |
|---|---|
| `operation` | `"check"` |
| `status` | `succeeded`, если все применимые действия успешны, иначе `failed` |
| `resources` | Попытанные ресурсы с `operation`, `id`, `presence`, `availability` |
| `checks` | Дополнительные записи `id`, `result` |
| `error` | `None` либо первая фактическая причина с источником/ID/видом проверки |

`presence` и попытанный дополнительный `result` — результат действия:
`status`, список `commands`, `error`. Команда содержит `invocation` (`argv`,
`cwd`, `env`), `interpreter` (`name`, `options`), фактический `exit_code`, полные
`stdout`, `stderr`, `interpretation` и `error`. Интерпретация содержит `success`,
`value`, `error`; при её отказе может быть `None`. Код запуска может быть `None`
при неудаче запуска. Все полученные причины остаются в индивидуальных результатах.

`availability` всегда содержит только `status`, `result`, `reason`:

| `status` | `result` | `reason` |
|---|---|---|
| `not_configured` | `None` | `None` |
| `not_attempted` | `None` | `presence_failed` |
| `succeeded` или `failed` | Фактический результат действия | `None` |

Отсутствующая проверка не подтверждает пригодность ресурса. Общий succeeded
означает успех применимых действий, не проверенность непредоставленных условий.
При трёх пустых списках результат — succeeded, пустые resources/checks, error=None.

API сохраняет полные bytes и допустимые непрозрачные Python-значения обработчика.
CLI требует обычные JSON-ответы; только raw stdout/stderr кодируются объектом
`{"encoding":"base64","data":"..."}` стандартным обратимым base64.
Интерпретированное значение не преобразуется этим кодеком. Непригодный ответ
обработчика после процесса сохраняет raw данные и даёт неуспешное действие.
CLI проверяет пригодность отражаемых планов до процессов, включая конечность чисел.

| Код CLI | Доставка |
|---|---|
| `0` | Один JSON+LF succeeded в stdout, пустой stderr |
| `1` | Один JSON+LF failed с фактическими попытками, пустой stderr |
| `2` | Ошибка входов: пустой stdout, причина в stderr, процессов нет |

API сообщает ошибки входов через `ValueError`. Предметный успех определяет
выбранный интерпретатор: он может принять фактический ненулевой код процесса.
Проверка не вводит усечение потоков, автоматические повторы, ремонт или откат.

## Внешний инструмент примера

[Пошаговые вызовы инструмента](#пошаговая-инструкция).

[check_settings.py](../examples/resource-checking/check_settings.py) — инструмент
обслуживаемого примера, не универсальная политика ядра.

| Режим/аргумент | Значение |
|---|---|
| `presence --path FILE` | FILE существует как обычный файл |
| `availability --path FILE` | FILE читается как UTF-8 JSON object |
| `consistency` | Сравнить два фактических строковых значения очереди |
| `consistency --config MAIN` | Обязательный главный конфиг обслуживаемых настроек |
| `--operation NAME` | Обязательное имя документа в этом MAIN |
| `--writer ID`, `--reader ID` | Два обязательных выбранных объекта |
| `--queue-variable NAME` | Обязательный env-ключ в первой команде обоих объектов |
| `-h`, `--help` | Справка инструмента или выбранной подкоманды |

У consistency обязательны все пять именованных аргументов. Пакетное чтение
получает два объекта через публичную библиотеку; стандартный JsonPointer выбирает
`commands[0].env[NAME]`. Оба значения должны быть непустыми строками и совпадать.
Этот пример пригодности файла не обещает проверку сети, сервиса или брокера.
Владелец приложения предоставляет команды с нужным предметным смыслом.

Успех инструмента: код0, пустой stderr и JSON+LF с `status="succeeded"`, `check`
равным режиму. Consistency добавляет `writer`, `reader`, `variable`, `value`
из фактических входов/данных. Обычная ошибка: код1, пустой stdout, причина
с путём или ID/VARIABLE в stderr. Argparse обрабатывает форму запуска кодом2.
Инструмент не изменяет файлы и не выполняет согласование настроек вместо проверки.

## Пошаговая инструкция

Из выбранного исходного checkout задайте фактический подготовленный интерпретатор:

```bash
: "${app_python:?Выберите Python по npm-инструкции или подготовке разработчика}"
PYTHONPATH=src "$app_python" -B examples/resource-checking/walkthrough.py
```

Семь строк подтверждают API, CLI, optional, empty и tool presence/availability/
consistency. Первые четыре имеют форму `api: confirmed checks; input files preserved`
с соответствующим именем; последние три —
`tool presence: actual condition confirmed; input files preserved` и другие режимы.
Walkthrough создаёт собственные копии семи JSON, заполняет фактические пути,
выполняет настоящие процессы, проверяет результаты и сохранность файлов.
Он не требует ERP, брокера или настройки рабочей установки1.0.0.

### API и подтверждение результата

```bash
PYTHONPATH=src:examples/resource-checking "$app_python" -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from environment_maintenance import check_resources
from walkthrough import prepare_demo, assert_result, snapshot
with TemporaryDirectory() as temporary:
    root = Path(temporary)
    config, values, registry = prepare_demo(root)
    before = snapshot(root)
    result = check_resources(config, values, base_dir=root, interpreters=registry)
    assert_result(result, encoded=False)
    assert snapshot(root) == before
    print(result['status'])
PY
```

Ожидается `succeeded`: два ресурса и queue-agreement, значения producer/consumer
совпадают с `reports.jobs`. У manifest availability не предоставлена и остаётся
not_configured. Полные данные команды доступны через её stdout/stderr.

### CLI с теми же конфигами

```bash
PYTHONPATH=src:examples/resource-checking "$app_python" -B - <<'PY'
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from walkthrough import prepare_demo, run_cli, assert_result, snapshot
with TemporaryDirectory() as temporary:
    root = Path(temporary)
    prepare_demo(root)
    before = snapshot(root)
    process = run_cli(root)
    assert process.returncode == 0 and process.stderr == b''
    assert_result(json.loads(process.stdout), encoded=True)
    assert snapshot(root) == before
    print('cli: succeeded')
PY
```

Ожидается `cli: succeeded`. `run_cli` вызывает полный source check с тремя
обязательными аргументами, явным cwd и import path, без переустановки пакета.
Результат stdout — один JSON+LF; assert_result декодирует полные rawstreams.

### Каждая возможность внешнего инструмента

```bash
PYTHONPATH=src:examples/resource-checking "$app_python" -B - <<'PY'
import json, os, subprocess, sys
from pathlib import Path
from tempfile import TemporaryDirectory
from walkthrough import prepare_demo, snapshot
with TemporaryDirectory() as temporary:
    root = Path(temporary)
    _, values, _ = prepare_demo(root)
    before = snapshot(root)
    for mode in ('presence', 'availability', 'consistency'):
        args = ['--path', values['infra_file']]
        if mode == 'consistency':
            args = ['--config', values['settings_config'], '--operation', values['operation'],
                    '--writer', values['writer'], '--reader', values['reader'],
                    '--queue-variable', values['variable']]
        process = subprocess.run([sys.executable, '-B', values['tool'], mode, *args],
            env=dict(os.environ, PYTHONPATH=values['source_path']), capture_output=True)
        assert process.returncode == 0 and process.stderr == b''
        answer = json.loads(process.stdout)
        assert answer['status'] == 'succeeded' and answer['check'] == mode
        if mode == 'consistency':
            assert answer['value'] == 'reports.jobs'
        print(mode + ': succeeded')
    assert snapshot(root) == before
PY
```

Ожидаются `presence: succeeded`, `availability: succeeded`, `consistency: succeeded`.
Корректные варианты отсутствующей availability и явно пустых документов
исполняются walkthrough через public update/clear только собственных копий;
сама проверка их не изменяет.

## Диагностика и осознанное продолжение

Прочитайте полный итог, отдельное условие, invocation и rawstreams. Входная
ошибка указывает документ/поле; процессная — попытанный вызов; предметная —
неподтверждённое состояние. Проверьте реально выбранные файлы и значения.
Следующее действие выполняет владелец инструмента по фактической причине.
Повторный вызов читает текущую конфигурацию; автоматического исправления нет.

## Собственный внешний инструмент

Когда готовые инструменты не обеспечивают требуемую предметную проверку,
разработайте отдельный инструмент обслуживаемого приложения. Для его конфигов
используйте [чтение с примерами](configuration-reading.md#пошаговая-инструкция) и
[CRUD с примерами каждой операции](configuration-editing.md#пошаговая-инструкция).
Список выдаёт IDs, полные объекты читаются пакетом IDs либо all; изменения —
через точечные операции. Команды и выбранный обработчик подчиняются
[общему интерфейсу](action-execution.md#интерфейс-интерпретатора).
Предметную пригодность и доступность определяет такой инструмент, не ядро.
