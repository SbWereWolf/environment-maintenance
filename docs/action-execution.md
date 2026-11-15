# Подготовка и исполнение действий

## Библиотека исполнения

[Пошаговая инструкция прежних действий](#пошаговая-инструкция).
[Цепочки с JSON-входом, sync/async и dry-run](#цепочки-с-передачей-данных).

API доступен собственному Python npm-поставки 4.0.0.
[Общий контекст](npm-distribution.md#библиотека-и-поставленные-примеры) объясняет
выбор runtime и поставленного набора примеров. Примеры с `PYTHONPATH=src`
явно используют выбранный исходный набор внутри пакета либо development checkout.
[CLI reference](configuration.md#команды-и-аргументы) описывает действующие шесть команд.
Поверх этого API доступна
[подготовка ресурсов через API и CLI infra/deps/adjust](resource-preparation.md#подготовка-ресурсов),
которая выбирает требования из отдельных конфигов и агрегирует их результаты.
Тот же владелец исполняет [configured run и внешний инструмент передачи запуска](process-launch.md#запуск-процессов).
Синхронный сбор полного результата команды и передача долгоживущего процесса
внешним инструментом имеют разные явно описанные границы.

## Публичные функции и аргументы

[Пошаговые примеры функций](#пошаговая-инструкция).

Импортируйте из `environment_maintenance`:

```python
plan_action(action, parameters, *, base_dir, interpreters)
execute_action(action, parameters, *, base_dir, interpreters)
```

| Аргумент | Обязательное значение |
|---|---|
| `action` | Объект с непустым массивом `commands`; можно передать полный объект из `read_requirements` |
| `parameters` | Карта строковых имён к строкам, числам и bool; неиспользованные значения допустимы |
| `base_dir` | Явный абсолютный `str` или `pathlib.Path`, база относительных cwd |
| `interpreters` | Карта имён к предоставленным вызывающим объектам с callable `interpret(result, options)` |

Последние два аргумента передаются по имени. Вызов получает значения, а не пути
конфигов. Чтение файлов остаётся у [библиотеки конфигурации](configuration-reading.md#библиотека-чтения):
получите IDs, прочитайте нужные полные объекты одним массивом IDs либо `all`,
затем передайте выбранное действие. Чтение и CRUD сами не запускают команды.

### Поля команды

| Поле | Значение |
|---|---|
| `argv` | Непустой массив строк; executable в первом элементе непустой, остальные аргументы могут быть пустыми |
| `cwd` | Непустая строка: абсолютная либо относительно явно переданного `base_dir` |
| `env` | Полная карта строковых имён и значений окружения; пустая карта допустима |
| `interpreter.name` | Непустое имя выбранного объекта из `interpreters` |
| `interpreter.options` | Объект настроек, передаваемый выбранному интерпретатору |

Отслеживаемые примеры:
[главный файл](../examples/action-execution/app.example.json) и
[полное действие](../examples/action-execution/infra.example.json).
Имя `infra` выбрано в данных примера: чтение для других объявленных операций
применяет тот же механизм. Рабочие конфиги выбирает и исключает из Git их
владелец; `*.example.json` содержат только учебные значения.

`argv` передаётся процессу отдельно от shell. `env` не дополняется окружением
хоста; нужные значения, включая PATH для требующих его команд, задаёт вызывающий.
Завершение процесса предоставляет фактический код и полные потоки. Стандартный
захват читает оба pipe; библиотека не декодирует и не усекает bytes.
Запускаемые инструменты предоставляет обслуживаемое приложение или оператор.

### Параметры и план

Стандартный `string.Template.substitute` выполняет однократную подстановку
в каждом элементе `argv`, `cwd` и значении `env`. Поддерживаются `$name`,
`${name}` и `$$` для буквального доллара. Скаляры преобразуются стандартным
`str`, включая `False` для bool. Вставленный текст повторно не раскрывается;
пробелы и пустые обычные аргументы сохраняют границы массива.
Ключи `env`, имя/настройки интерпретатора и непрозрачные данные не шаблонизируются.

Обязательные executable/cwd сохраняют непустоту после подстановки. Все команды
подготавливаются до первого процесса; ошибка даже поздней команды даёт
контекстный `ValueError` без внешнего запуска. Относительный cwd соединяется
с `base_dir`; абсолютный используется напрямую. Планирование допускает
ещё отсутствующие executable/каталоги: их может подготовить предыдущая команда.

`plan_action` возвращает объект `commands` с конкретными `argv`, абсолютным
`cwd`, `env` и выбранным `interpreter` в исходном порядке. Процессы и `interpret`
не вызываются. Входные action/parameters/options и файлы конфигурации сохраняются.

## Интерфейс интерпретатора

[Пошаговый пример смены обработчика](#пошаговая-инструкция).

Структурный `ResultInterpreter` объявлен в
`environment_maintenance.actions.application`. Подходит обычный объект с методом
`interpret(result, options)`; наследование от протокола не требуется.
Вызывающий предоставляет объекты, а `interpreter.name` в конфиге выбирает нужный.
Замена объекта под тем же именем меняет обработку через тот же интерфейс.

`result` — отдельная копия сырого результата:

| Поле | Тип и источник |
|---|---|
| `invocation` | Объект `argv/cwd/env` фактического подготовленного вызова |
| `exit_code` | Фактический int завершившегося процесса |
| `stdout`, `stderr` | Полные bytes каждого потока; пустой поток — `b""` |

`options` — отдельная копия настроек из конфигурации. Интерпретатор возвращает
объект с обязательными полями:

| Поле | Договор |
|---|---|
| `success` | Строго bool: предметный успех либо неуспех |
| `value` | Непрозрачное значение вызывающего инструмента |
| `error` | `None` при успехе, непустая строка при неуспехе |

Дополнительные поля ответа сохраняются. Фактический код не переписывается:
выбранный обработчик может признать ненулевой код корректным предметным ответом.
При отказе самого запуска интерпретатор не вызывается.
Реальные разные реализации показаны в
[walkthrough.py](../examples/action-execution/walkthrough.py).

### Стандартный интерпретатор кода завершения

Пакет предоставляет `environment_maintenance.actions.interpreters.ExitCodeInterpreter` и готовый `exit_result`. В main задаются module `environment_maintenance.actions.interpreters` и attribute `exit_result`; команда выбирает это binding по имени и явно передаёт `options.accept`, например `[0]`.

`success` означает вхождение raw exit_code в accept, `value` сохраняет исходный код, `error` равен None либо непустой строке `command exit code is not accepted`. Это общий опциональный обработчик; прикладной анализ и другие value contracts остаются у приложения. Он работает из установленного пакета без examples.

## Итог исполнения

`execute_action` возвращает `status`, `commands`, `error`.
Успех всей цепочки — `status="succeeded"`, `error=None`. При отказе —
`status="failed"`, `error` последней попытанной команды. `commands` содержит
только попытанные команды в порядке исполнения. Каждая запись:

| Поле | Содержание |
|---|---|
| `invocation` | Конкретные `argv`, `cwd`, `env` |
| `interpreter` | Выбранные имя и настройки |
| `exit_code` | Реальный int либо `None`, если процесс не запущен |
| `stdout`, `stderr` | Полные bytes, в том числе произвольные не-UTF8 байты |
| `interpretation` | Полный пригодный ответ обработчика либо `None` при его исключении/непригодном ответе/отказе запуска |
| `error` | Контекстный текст отказа либо `None` |

При отказе запуска запись имеет пустые bytes и `exit_code=None`.
Исключение интерпретатора или непригодный ответ сохраняет фактическое сырьё.
После первого отказа поздние команды не выполняются, прежние результаты
сохраняются. Библиотека не откатывает внешние эффекты и не повторяет их.
Это Python-результат с bytes, а не JSON-ответ прежнего CLI; представление
потоков пользователю выбирает внешний потребитель без потери исходных данных.

## Пошаговая инструкция

Предусловия: исходный checkout с этим API, Python 3.11+ и подготовленные
зависимости по [инструкции разработчика](development.md#подготовка).
Выберите фактический Python своего приложения; переустановка wheel не нужна:

```bash
: "${app_python:?Выберите Python по npm-инструкции или подготовке разработчика}"
PYTHONPATH=src "$app_python" -B examples/action-execution/walkthrough.py
```

Выполняйте из корня выбранного checkout. Примеру нужен доступ записи внутри
`examples/action-execution`: там создаётся собственный временный каталог,
удаляемый при завершении. Исходные JSON остаются побайтно прежними.
Не требуются работающие ERP, Poise, базы, Redis или Composer.

### Получить план

Начальные данные — два указанных `*.example.json`. В `example_inputs(workspace)`
прочитан полный `demo`, заданы выбранный Python, абсолютный workspace/маркер,
состояние ресурса, значение окружения и registry двух обработчиков.
`plan_action` вызывается с этими четырьмя явными входами. Проверяются две
конкретные команды, argv/cwd/env, отсутствие маркера и вызовов обработчиков.
Ожидаемая первая строка: `plan: 2 commands; no effects`.

### Исполнить последовательность

Те же входы передаются `execute_action`. Первая команда пишет `first` и JSON,
вторая добавляет `second`, выводит bytes с `0xff/0x00` и отдельный stderr.
Выбраны разные JSON/exit обработчики. Пример проверяет полный порядок маркеров,
вызовы плана, фактические коды, все bytes обоих потоков и успех.
Ожидается `execute: succeeded; full bytes retained`.

### Заменить обработчик

В том же registry имя `json` связывается с `SummaryInterpreter`.
Объявленные команды и интерфейс остаются прежними. После исполнения
проверяются непрозрачный список `value`, различие False/0 и поле `source`.
Ожидается `replace: same configured name; another implementation`.

### Обработать предметный неуспех

Корректный запрос с состоянием ресурса `busy` обрабатывается выбранным
`JsonInterpreter`. Он сообщает предметную неготовность при реальном коде0.
Пример проверяет `failed`, полный ответ/поток первой команды и отсутствие
второй команды/вызова её обработчика. Это обычный результат проверки ресурса,
не ошибка формы API. Ожидается `outcome: failed; later command not started`.

Один запуск выполняет все четыре части и проверяет исходные JSON. Код0,
четыре строки и отсутствие assertion ошибок подтверждают результат.
`example_inputs` — учебный helper, а не новая библиотечная функция или appCLI.

## Диагностика и осознанное продолжение

Для `ValueError` прочитайте имя поля, параметра или индекс команды: весь вызов
ещё находится на подготовке. Подготовьте корректные явные данные и повторите
вызов. Для `failed` изучите сохранённые invocation, коды, bytes и интерпретации:
предыдущие эффекты могли состояться. Владелец инструмента проверяет фактическое
состояние и выбирает дальнейшее действие; библиотека сама его не угадывает.

## Собственный внешний инструмент

[Пошаговые примеры публичного исполнителя](#пошаговая-инструкция).

Если готовые средства не обеспечивают нужного поведения, разработайте отдельный
инструмент. Используйте [CRUD конфигурации](configuration-editing.md#библиотека-записи)
для точечных изменений, чтение IDs/пакета объектов для выбора, затем этот API
для объявленного действия. Предметный анализ оформляйте своим `interpret` и
выбирайте имя/настройки в конфиге. Внешний инструмент владеет своими командами,
доменной трактовкой результата и осознанным продолжением после ошибки.

## Цепочки с передачей данных

Начиная с `command-execution` 0.2.0 и совместимых импортов
`environment-maintenance` 5.2.0 доступны отдельные Python API:

```python
plan_chain(action, parameters, *, input_data, base_dir, interpreters)
execute_chain(action, parameters, *, input_data, base_dir, interpreters,
              run_command=None, on_result=None)
```

Импорт: `from command_execution import plan_chain, execute_chain` либо те же имена
из `environment_maintenance`. [Установите выбранную библиотеку](command-package.md#установка-выбранной-версии).
Прежние `plan_action`/`execute_action` сохраняют описанный выше договор.
Новые функции вызываются приложением явно; новые CLI-флаги или перенос hooks
из одного обновления библиотеки не следуют.

`action`, `parameters`, `base_dir`, `interpreters` и поля `argv/cwd/env/interpreter`
имеют [общий договор подготовки](#публичные-функции-и-аргументы).
`input_data` — отдельное JSON-совместимое значение; его явная передача обязательна.
`None`, bool, числа, строки, массивы и объекты допустимы, неконечные числа
отвергаются. Все команды и дополнительные параметры проверяются до запуска.
JSON-вход и дальнейшие снимки глубоко копируются.

| Дополнительное поле команды | Читаемое значение по умолчанию | Значения |
|---|---|---|
| `mode` | `"sync"` | `"sync"`, `"async"` |
| `enabled` | `True` | Строго bool |
| `on_error` | `"stop"` | `"continue"`, `"stop"` |

Это defaults **исполнения читаемой конфигурации**. Редактор списка команд и его
правила создания записей данным API не предоставляются.

Подготовленные `argv/cwd/env` используют исходную карту `parameters` и её
[однократные подстановки](#параметры-и-план). Текущий вход кодируется JSON в bytes
`invocation.stdin` и поступает процессу через stdin. Он не раскрывает заново уже
подготовленные аргументы. Отдельный `run_command` при необходимости принимает
такой invocation и возвращает полные `invocation/exit_code/stdout/stderr` по
[договору интерпретатора](#интерфейс-интерпретатора). По умолчанию используется
обычный process adapter; полный `env` задаёт вызывающее приложение.

`plan_chain` — dry-run: возвращает все подготовленные `commands` в исходном
порядке с конкретными `argv/cwd/env/interpreter/mode/enabled/on_error`.
Процессы, интерпретаторы и фоновые потоки не запускаются. Отключённая запись
остаётся в плане; `execute_chain` её пропускает.

### Изменение данных и ошибки

Интерпретатор возвращает прежние обязательные `success/value/error` и может
добавить `next_input`. `value` остаётся непрозрачным результатом, а наличие
JSON-пригодного `next_input` явно задаёт новые данные. `False`, `0`, пустая строка,
пустой список/объект и `None` передаются как значения; отсутствие ключа сохраняет
прежний вход.

Синхронная команда передаёт следующей изменённые либо сохранённые данные.
Успех определяет `interpretation.success`; ненулевой код процесса может быть
принят прикладным интерпретатором. При неуспехе `on_error="stop"` останавливает
дальнейший проход, `"continue"` продолжает его. При продолжении допустимый явно
заданный `next_input` передаётся даже от предметно неуспешного результата.
Ошибка запуска, интерпретации или некорректный `next_input` сохраняют последний
допустимый вход. Итог после sync-ошибки остаётся `status="failed"` с первой
ошибкой, даже если следующие команды успешны. Внешние эффекты не откатываются.

Асинхронная команда получает глубокий снимок текущих данных. Цепочка немедленно
передаёт следующему звену тот же вход. Поздние `next_input`, ошибки и исключения
async не меняют `data/status/error` продолжающейся цепочки. `on_error` у async
не превращает её в прерывающее звено, включая отказ создания/запуска потока.

## Результаты и фоновое завершение

`execute_chain` возвращает `status`, `data`, `commands`, `error` синхронного
прохода. `commands` содержит записи достигнутых включённых команд, включая
попытки dispatch без запуска процесса. Отключённые записи и недостигнутые
после sync stop команды в результат не входят. Запись содержит подготовленный
`invocation`, `interpreter`, исходный `index`, глубокий `input_data`, `state`,
`exit_code`, `stdout/stderr`, `interpretation`, `error`, `exception`.

| Состояние попытки | Представление результата |
|---|---|
| Async ещё выполняется | `state="running"`; `stdout/stderr/exit_code/interpretation=None` |
| Процесс завершён, интерпретация обработана | `state="completed"`; полные bytes потоков, фактический exit code, ответ интерпретатора либо его ошибка |
| Ошибка запуска процесса | `state="completed"`; пустые bytes потоков, `exit_code=None`, `interpretation=None`, launch error/exception |
| Исключение создания/запуска фонового потока | Уже добавленная запись `completed`; процесс не запускается, `stdout/stderr/exit_code/interpretation=None`, dispatch error и exception |

`exception` — `None` либо объект `type/message` фактического исключения.
Предметный отказ `success=False` имеет ошибку интерпретации, но не выдуманное
исключение. Непригодный `next_input` сохраняет реальные потоки и код, отмечая
ошибку и исключение проверки. `state="completed"` само по себе не гарантирует
наличие bytes или запущенного процесса. Перед `.hex()` различайте `None` и bytes;
сырой результат с bytes не является готовым JSON. Представление для человека
принадлежит consumer, исходные потоки сохраняются полностью.

`on_result` — необязательный callable с одним аргументом: отдельной глубокой
копией завершённой записи. Для sync он вызывается в вызывающем потоке, при
обычном завершении async — в worker. Если создание/запуск фонового потока
выбросило исключение, callback с dispatch-error записью вызывается непосредственно
в вызывающем потоке. Обработчик consumer должен быть пригоден к обоим контекстам,
коротким и не выбрасывающим исключений; при необходимости он передаёт запись
в собственную очередь для асинхронного журнала. Библиотека предоставляет полную
запись, хранение/журналирование организует consumer.

Фоновое завершение обновляет только собственную запись `commands` и вызывает
callback. Недемонический поток не требует join внутри `execute_chain`, но может
удерживать завершение Python-процесса. Consumer владеет временем жизни runtime и
ожиданием нужных завершений. Принудительная остановка процесса не имеет обещанной
гарантии доставки журналов. Готовность callback и runtime не заменяются сохранением
ссылки на ещё выполняющуюся запись.

## Пример цепочки

### Dry-run и два синхронных звена

Выберите `LIBRARY_PYTHON` установленной библиотеки по
[инструкции установки](command-package.md#установка-выбранной-версии).
Пример не меняет рабочие конфиги, каждый дочерний процесс только возвращает stdin.

Подсказка: `input_data` — стартовые JSON-данные; `base_dir` — абсолютная база cwd;
`interpreters` связывает имя с объектом. Без `mode` команда синхронна.
`plan_chain` готовит вызовы без запуска. [Все аргументы и defaults](#цепочки-с-передачей-данных).

```bash
"${LIBRARY_PYTHON:?Выберите Python установленной библиотеки 0.2.0}" -I -B - <<'PY'
import json
from pathlib import Path
import sys
from command_execution import plan_chain, execute_chain

class Increment:
    def interpret(self, raw, options):
        received = json.loads(raw["stdout"])
        return {"success": True, "value": "separate-value", "error": None,
                "next_input": {"number": received["number"] + 1}}

command = {
    "argv": [sys.executable, "-B", "-c",
             "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"],
    "cwd": ".", "env": {},
    "interpreter": {"name": "increment", "options": {}}
}
action = {"commands": [command, command]}
arguments = dict(input_data={"number": 3}, base_dir=Path.cwd(),
                 interpreters={"increment": Increment()})
plan = plan_chain(action, {}, **arguments)  # dry-run: no child starts
assert [row["mode"] for row in plan["commands"]] == ["sync", "sync"]
records = []
result = execute_chain(action, {}, on_result=records.append, **arguments)
assert result["status"] == "succeeded"
assert result["data"] == {"number": 5}
assert [json.loads(row["stdout"]) for row in records] == [{"number": 3}, {"number": 4}]
assert [row["exit_code"] for row in records] == [0, 0]
print(json.dumps({"data": result["data"],
                  "stdout_hex": [row["stdout"].hex() for row in records]}))
PY
```

Ожидаются `data={"number": 5}` и два полных stdout, представляющих входы
`{"number": 3}` и `{"number": 4}`. Значение `"separate-value"` не заменяет данные.

### Асинхронный снимок и поздний результат

Подсказка: `mode="async"` передаёт снимок без ожидания; `on_result` получает
завершённую запись. Очередь и ожидание результата принадлежат consumer.
Пример освобождает свой барьер в `finally` и ограничивает собственное ожидание.
[Контексты callback и ошибки dispatch](#результаты-и-фоновое-завершение).

```bash
"${LIBRARY_PYTHON:?Выберите Python установленной библиотеки 0.2.0}" -I -B - <<'PY'
import json
from pathlib import Path
from queue import Queue
import sys
from threading import Event
from command_execution import execute_chain

started, release, delivered = Event(), Event(), Event()
completed = Queue()  # thread-safe consumer-owned result sink

class Answer:
    def interpret(self, raw, options):
        if options["background"]:
            started.set()
            if not release.wait(10):
                raise RuntimeError("consumer did not release background")
            next_input = {"step": "late-background"}
        else:
            if not started.wait(10):
                raise RuntimeError("background did not start")
            next_input = {"step": "sync"}
        return {"success": True, "value": json.loads(raw["stdout"]),
                "error": None, "next_input": next_input}

def command(background):
    return {
        "argv": [sys.executable, "-B", "-c",
                 "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"],
        "cwd": ".", "env": {}, "mode": "async" if background else "sync",
        "interpreter": {"name": "answer", "options": {"background": background}}
    }

def observe(record):
    completed.put(record)
    if record["index"] == 0:
        delivered.set()

try:
    result = execute_chain(
        {"commands": [command(True), command(False)]}, {},
        input_data={"step": "initial"}, base_dir=Path.cwd(),
        interpreters={"answer": Answer()}, on_result=observe,
    )
    assert result["data"] == {"step": "sync"}
finally:
    release.set()  # consumer, not execute_chain, releases its background barrier
assert delivered.wait(10), "consumer did not receive background result"
records = {}
for _ in range(2):
    record = completed.get(timeout=10)
    records[record["index"]] = record
assert all(record["error"] is None for record in records.values())
assert json.loads(records[0]["stdout"]) == {"step": "initial"}
assert json.loads(records[1]["stdout"]) == {"step": "initial"}
assert records[0]["interpretation"]["next_input"] == {"step": "late-background"}
assert result["data"] == {"step": "sync"}  # unchanged after actual late delivery
assert result["status"] == "succeeded"
print(json.dumps({"data": result["data"], "background_received": True,
                  "background_next_input": records[0]["interpretation"]["next_input"]}))
PY
```

Оба дочерних процесса получают `{"step": "initial"}`. Sync-результат становится
`{"step": "sync"}` ещё до освобождения фонового интерпретатора. После получения
реального позднего `{"step": "late-background"}` итог остаётся sync, а callback
уже доставил отдельную запись. Это ожидание принадлежит примеру consumer;
`execute_chain` не ждёт фонового завершения внутри себя.
