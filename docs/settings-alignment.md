# Согласование настроек

[Инструкция командного режима](#пошаговая-инструкция).
[Полный сетевой пример](#два-http-сервера).

`adjust` автоматически согласует объявленные порты и зависимые адреса либо
выполняет выбранные внешние действия согласования. Сетевое согласование принадлежит
общему EM; команды и их предметные правила предоставляет обслуживаемое приложение.
Операция вызывается явно; это не автоматический шаг `infra`, `deps`,
`check` или `run`. Правила очередей остаются во внешнем инструменте приложения;
[сетевой режим](#автоматический-подбор-портов) имеет явный общий договор.

Командный режим доступен в npm-поставке 4.0.0 через `start-app adjust`.
[Установка и пример короткого входа](npm-distribution.md#пошаговая-инструкция)
отделены от примеров ниже с явно выбранными Python и `PYTHONPATH=src`.
Их исходный набор может находиться внутри установленного пакета;
[общая подготовка](npm-distribution.md#библиотека-и-поставленные-примеры) задаёт
контекст. Установленный 1.0.0 остаётся отдельным экземпляром.

## Входы и результаты

Обычный вызов с [постоянным профилем](persistent-entry.md#поля-постоянного-профиля):

```bash
./start-app adjust
```

Следующие ключи доступны как необязательные переопределения одного вызова.
Полностью явная форма `python -m environment_maintenance adjust` с этими
значениями сохраняет прежний договор.

| Аргумент | Значение |
|---|---|
| `--config PATH` | Главный JSON описания действий с `operations.adjust` и готовыми `interpreters` |
| `--parameters PATH` | Один полный JSON-объект скалярных значений для placeholders |
| `--base-dir ABS` | Абсолютный базовый каталог для относительного cwd команд |
| `--requirements SELECTION` | `all`, JSON-массив выбранных IDs или `[]` |
| `-h`, `--help` | Общая справка без исполнения |
| `--version` | Версия выбранной установки без исполнения |

Относительные пути `--config`/`--parameters` считаются от cwd вызывающего.
Полные общие правила, типы и коды завершения принадлежат
[входу подготовки](resource-preparation.md#команды-и-аргументы) и
[результату](resource-preparation.md#результат-и-диагностика).
`all` сохраняет порядок документа, массив — порядок выбранных IDs.
Пустая выборка проверяет общие входы, но не запускает процессы. CLI default — all; повтор IDs отвергает весь запрос, missing IDs предупреждаются/пропускаются. SDK selection остаётся строгой. Полные правила — [здесь](configuration-reading.md#публичный-договор).

Библиотека не получает нового синонима: используйте прежнюю
`prepare_resources(config, "adjust", selection, parameters, base_dir=..., interpreters=...)`.
В командном режиме все выбранные цепочки планируются до эффектов, затем
исполняются последовательно.
Итог содержит operation/status/requirements/error и только попытанные действия.
Командный API сохраняет полные bytes, CLI кодирует каждый поток обратимым base64.
Сетевой CLI использует [свой атомарный итог](#результат-и-отказ-сетевого-режима).
В командном режиме `0` — подтверждённый успех; `1` — неуспех с доступной частичной работой;
`2` — ошибка входа или подготовки до процессов. Диагностика внешней команды
остаётся внутри результата, а не теряется в общем сообщении.

## Автоматический подбор портов

[Полная инструкция с двумя HTTP-серверами](#два-http-сервера).

Сетевой режим реализован в исходниках общего EM. Пример ниже явно выбирает эти
исходники. Ранее выпущенные пакеты сохраняют свои байты; доступность возможности
в конкретной установке подтверждает её владелец поставки.

### Декларация сетевого согласования

Главный файл по-прежнему содержит `operations.adjust` с путём к документу
требований и объект `interpreters` (для сетевого примера достаточно `{}`).
Выбранное требование включает `network` с двумя обязательными полями:

| Поле | Договор |
|---|---|
| `ports` | Непустой массив объявлений в заданном порядке |
| `ports[].parameter` | Имя существующего параметра; идентификатор стандартного `string.Template`: ASCII-буква или `_`, затем ASCII-буквы, цифры или `_` |
| `ports[].host` | Явный числовой локальный IPv4-адрес для TCP, например `127.0.0.1` |
| `ports[].owner` | Необязательный объект владельца; отсутствие означает, что принадлежность процесса не заявлена |
| `owner.pid` | Строго положительное целое число, не boolean |
| `owner.start_ticks` | Каноническая ASCII-десятичная строка времени старта Linux-процесса: `0` либо цифры без ведущего нуля |
| `addresses` | Объект `имя выходного параметра → строковый рецепт`; `{}` допустим |

Значение каждого объявленного порта в выбранном файле параметров — целое
`0..65535`, не boolean, строка или дробь. `0` запрашивает назначение ОС.
Пригодный положительный порт сохраняется; занятый посторонним экземпляром
автоматически заменяется свободным. Недоступный локальный адрес или ресурсы
сокетов дают отказ с фактической причиной.

Рецепты адресов используют однократную подстановку `string.Template` по конечным
портам и неизменённым входным скалярам. Например, `http://127.0.0.1:${HTTP_PORT}`
и `http://127.0.0.1:${HTTP_PORT}/callback` объявляются каждый полностью.
Явно объявленный новый выходной ключ создаётся; прежнее значение адресного ключа
должно быть строкой. Имена выходов имеют ту же форму идентификатора.
Повторяющиеся портовые/выходные ключи во всей выборке, пересечение их имён,
ссылка рецепта на любой адресный выход, отсутствующая переменная и неверный
шаблон отклоняются до эффектов. Старое значение производного адреса не становится
входом другого рецепта. Непрозрачные метаданные объявлений не интерпретируются.

Файловый CLI получает точный существующий файл из `--parameters` или
`invocation.parameters`. Он сохраняет в нём все выбранные порты и адреса одной
заменой JSON; посторонние скалярные значения, их типы и режим файла сохраняются.
Все временные резервирования удерживаются до этой записи. Когда произведённые
значения уже совпадают, запись пропускается. Во время согласования у файла один
владелец записи. Несколько файлов, `.env`, Docker и межпроцессная аренда портов
в этот договор не входят.

Отсутствие `network` выбирает прежние `commands`. Присутствующие `network: null`
или значение другого типа не переключают требование в командный режим.
`network` вместе с `commands` в одном требовании и смешанная выборка двух режимов
отклоняются до команд, резервирования и записи. Вызывайте группы отдельно через
`--requirements`. Публичный `prepare_resources` с картой значений остаётся
командным API: карта не предоставляет права угадать и переписать файл.

### Результат и отказ сетевого режима

CLI печатает один JSON+LF, сохраняет корневые `operation`, `status`,
`requirements`, `error`. При успехе код `0`, `operation="adjust"`,
`status="succeeded"`, `error=null`. В каждой выбранной записи `{id,result}`:

| Поле `result` | Значение при успехе |
|---|---|
| `status`, `commands`, `error` | `"succeeded"`, `[]`, `null` |
| `network.ports` | Карта объявленных имён к фактически назначенным положительным целым портам |
| `network.addresses` | Имена объявленных адресных выходов в порядке декларации, включая неизменённые |
| `network.changed` | Boolean изменения произведённых значений именно этого требования |
| `network.error_code` | `null` |

Порядок требований следует выборке. Неизменённое требование может иметь
`changed=false`, пока соседнее изменяется в той же единственной публикации.
Пустая выборка после общей проверки входов даёт успешный итог с `requirements=[]`.

При runtime-отказе код `1`, корневой `status="failed"`; **все выбранные сетевые
записи** имеют `status="failed"`, `commands=[]`, тот же `error` и
`network.ports={}`, `network.addresses=[]`, `network.changed=false` и
`network.error_code=CODE`.
Предыдущие байты/режим файла сохраняются, собственные временные сокеты освобождаются.
Зарезервированный кандидат не показывается как сохранённое назначение.

| `CODE` | Причина и продолжение |
|---|---|
| `allocation_failed` | Устраните указанную проблему локального адреса/ресурсов сокетов |
| `ownership_mismatch` | Проверьте, какой собственный экземпляр работает, и обновите его фактические PID/start_ticks и объявление listener |
| `ownership_unavailable` | Восстановите доступ к необходимым данным процесса и его сокетов |
| `write_failed` | Восстановите доступ к выбранному файлу и каталогу для записи |

Диагностика содержит причину, параметр либо путь и команду повторного запуска с
фактически разрешёнными config/parameters/base-dir/selection. Посторонняя карта
значений в сообщение не выводится. Сначала устраните причину, затем выполните
предложенную команду. Ошибка схемы или смешанная выборка дают код `2`, пустой
stdout и объяснение поля/исправления в stderr до эффектов.

Это атомарный сетевой итог. Прежний командный режим сохраняет свою доступную
частичную работу и полные потоки по [общему договору](resource-preparation.md#результат-и-диагностика).

### Два HTTP-сервера

Сетевой режим, введённый в 3.1.0, сохраняется в 4.0.0. Исходниковый пример ниже использует выбранный
checkout; для проверки установленного ядра выберите собственный Python пакета и
очистите `PYTHONPATH`, сохранив явные пути конфигурации и параметров. Обычный
пользовательский вызов — пакетный `start-app adjust` из обслуживаемого проекта.

Предусловия: Linux, исходники с этой возможностью, Python 3.12+ и зависимости по
[подготовке разработчика](development.md#подготовка). Из корня выбранного checkout
задайте `app_python` абсолютным путём к его подготовленному Python и выполните весь
блок. Он использует отдельные временные файлы и только собственные процессы.
Первый сервер занимает назначенный ОС порт; повторный запуск на нём подтверждает
конфликт. После `adjust` второй отвечает на сохранённом новом порту, первый — на
исходном. Затем проверяется повтор с подтверждённым владельцем второго экземпляра.

```bash
: "${app_python:?Выберите абсолютный путь к подготовленному Python}"
PYTHONPATH="$PWD/src" "$app_python" -B - <<'PY'
# em-network-walkthrough
from contextlib import contextmanager
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.request import urlopen

SERVER = '''from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
import sys
server = HTTPServer(("127.0.0.1", int(sys.argv[1])),
                    partial(SimpleHTTPRequestHandler, directory=sys.argv[2]))
print(server.server_port, flush=True)
server.serve_forever()
'''
commands, children, responses = [], [], []

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

@contextmanager
def server(port, directory):
    argv = [sys.executable, '-u', '-B', '-c', SERVER, str(port), str(directory)]
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ready = b''
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(5), 'Сервер не сообщил готовность'
        ready = process.stdout.readline()
        assert ready and process.poll() is None
        yield process, int(ready)
    finally:
        if process.poll() is None:
            process.terminate()
        output, errors = process.communicate(timeout=5)
        children.append(dict(pid=process.pid, exit_code=process.returncode,
            stdout=(ready + output).decode(), stderr=errors.decode(), reaped=process.poll() is not None))

def marker(port):
    with urlopen(f'http://127.0.0.1:{port}/', timeout=5) as response:
        assert response.status == 200
        body = response.read()
        responses.append(dict(port=port, status=response.status, body=body.decode()))
        return body

with TemporaryDirectory(prefix='em-network-') as temporary:
    work = Path(temporary)
    first_dir, second_dir = work / 'first', work / 'second'
    for directory, text in ((first_dir, 'first\n'), (second_dir, 'second\n')):
        directory.mkdir()
        (directory / 'index.html').write_text(text, encoding='utf-8')
    values = work / 'selected settings' / 'parameters.json'
    values.parent.mkdir()
    main, profile, default = work / 'main.json', work / 'adjust.json', work / 'default.json'
    write(main, dict(operations={'adjust': 'adjust.json'}, interpreters={},
        invocation=dict(parameters='default.json', base_dir='.', requirements={'adjust': ['http']})))
    write(default, dict(HTTP_PORT=999, NOTE='другой экземпляр'))
    inputs = {path: path.read_bytes() for path in (main, default)}
    network = dict(ports=[dict(parameter='HTTP_PORT', host='127.0.0.1')], addresses={
        'BASE_URL': 'http://127.0.0.1:${HTTP_PORT}',
        'CALLBACK_URL': 'http://127.0.0.1:${HTTP_PORT}/callback'})
    write(profile, dict(requirements=[dict(id='http', network=network)]))

    def adjust():
        argv = [sys.executable, '-B', '-m', 'environment_maintenance', 'adjust',
            '--config', str(main), '--parameters', str(values), '--base-dir', str(work),
            '--requirements', '["http"]']
        process = subprocess.run(argv, cwd=work, env=os.environ.copy(), capture_output=True, timeout=15)
        commands.append(dict(argv=argv, exit_code=process.returncode,
                             stdout=process.stdout.decode(), stderr=process.stderr.decode()))
        assert process.returncode == 0 and process.stderr == b''
        answer = json.loads(process.stdout)
        assert answer['status'] == 'succeeded'
        return answer['requirements'][0]['result']['network']

    with server(0, first_dir) as (first, occupied):
        assert marker(occupied) == b'first\n'
        conflict = subprocess.run([sys.executable, '-B', '-c', SERVER, str(occupied), str(second_dir)],
                                  capture_output=True, timeout=5)
        commands.append(dict(kind='occupied-bind', exit_code=conflict.returncode,
                             stdout=conflict.stdout.decode(), stderr=conflict.stderr.decode()))
        assert conflict.returncode != 0 and b'Address already in use' in conflict.stderr
        assert marker(occupied) == b'first\n'
        write(values, dict(HTTP_PORT=occupied, BASE_URL='http://127.0.0.1:0',
                          CALLBACK_URL='http://127.0.0.1:0/callback', KEEP=False, ZERO=0))
        values.chmod(0o640)
        result = adjust()
        saved = json.loads(values.read_text(encoding='utf-8'))
        assigned = saved['HTTP_PORT']
        assert type(assigned) is int and 0 < assigned <= 65535 and assigned != occupied
        assert saved == dict(HTTP_PORT=assigned, BASE_URL=f'http://127.0.0.1:{assigned}',
            CALLBACK_URL=f'http://127.0.0.1:{assigned}/callback', KEEP=False, ZERO=0)
        assert saved['KEEP'] is False and type(saved['ZERO']) is int
        assert result == dict(ports={'HTTP_PORT': assigned},
            addresses=['BASE_URL', 'CALLBACK_URL'], changed=True, error_code=None)
        before = values.read_bytes()
        assert adjust()['changed'] is False and values.read_bytes() == before
        with server(assigned, second_dir) as (second, actual):
            assert actual == assigned and marker(actual) == b'second\n'
            assert marker(occupied) == b'first\n'
            fields = Path(f'/proc/{second.pid}/stat').read_text().rsplit(')', 1)[1].split()
            network['ports'][0]['owner'] = dict(pid=second.pid, start_ticks=fields[19])
            write(profile, dict(requirements=[dict(id='http', network=network)]))
            declared = profile.read_bytes()
            assert adjust()['changed'] is False and values.read_bytes() == before
            assert marker(actual) == b'second\n' and marker(occupied) == b'first\n'
            assert first.poll() is None and second.poll() is None
            assert profile.read_bytes() == declared
        assert stat.S_IMODE(values.stat().st_mode) == 0o640
        assert all(path.read_bytes() == content for path, content in inputs.items())
assert all(child['reaped'] for child in children)
print(json.dumps(dict(status='succeeded', occupied=occupied, assigned=assigned,
    parameters=saved, file_mode='0640', inputs_preserved=True,
    commands=commands, children=children, http=responses,
    owner=network['ports'][0]['owner']), ensure_ascii=False))
PY
```

Ожидаются код `0` и JSON с `status="succeeded"`, разными `occupied`/`assigned`,
согласованными `parameters`, сохранённым режимом и `reaped=true` обоих серверов.
Поле `http` содержит фактические HTTP-маркеры, `owner` — наблюдённые PID/start_ticks.
Массив `commands` сохраняет полные результаты: отказ второй привязки ожидаем,
три вызова `adjust` успешны. Серверы завершаются, временные файлы удаляются.
В рабочем проекте вызывайте `run` или свой запуск отдельно после согласования.

### Собственный работающий экземпляр

До запуска повтор сохраняет пригодный свободный порт. После запуска объявите
в `ports[].owner` реальный PID именно назначенного экземпляра и его `start_ticks`
из поля 22 `/proc/PID/stat`; пример получает их от собственного `Popen` и ядра.
Для owner нужен положительный существующий порт. Совпадение PID и времени старта
подтверждается принадлежностью этому процессу слушающего TCP-сокета на объявленном
адресе/порту, включая подходящий IPv4 wildcard listener. Успешный HTTP-ответ,
имя экземпляра или один PID этого не доказывают.

Без owner работающий listener считается посторонним и вызывает подбор другого
порта. Завершившийся процесс, другое время старта или отсутствие его listener
дают `ownership_mismatch`; недоступные данные — `ownership_unavailable`.
Не подставляйте сведения другого экземпляра. Операция не получает эти сведения
за владельца, не останавливает процессы и не усыновляет их.
После завершения `adjust` свободный порт не арендован: запускайте сервис отдельно
и проверяйте фактическую доступность; сторонний процесс может занять порт позже.

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

[Пошаговая инструкция инструмента](#пошаговая-инструкция).

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
: "${app_python:?Выберите Python по npm-инструкции или подготовке разработчика}"
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
