# Запуск процессов

[Пошаговая инструкция всех возможностей](#пошаговая-инструкция).

Исходники разработки 2.0 выполняют выбранные действия запуска через тот же
читатель конфигурации, стандартный `string.Template` и исполнитель, что
`infra`/`deps`/`adjust`. `run` только запускает выбранные команды. Подготовку,
проверку ресурсов и согласование настроек оператор вызывает отдельно.

Это исходниковая возможность. Короткий пакетный `start-app` вызывает тот же
CLI после поставки соответствующих исходников. Корневой `./start-app` запускает
установленный пакет своей `.venv` с `-I`: установка `PYTHONPATH` не превращает
его в исходниковый launcher. В проверенной рабочей установке сохранён 1.0.0;
данный раздел не означает выпуска или переустановки 2.0. Для исходников выберите
подготовленный Python по [инструкции разработчика](development.md#подготовка).

## Входы и аргументы

Из выбранного исходного checkout с `PYTHONPATH=src`:

```text
python -m environment_maintenance run --config MAIN --parameters VALUES --base-dir ABS --requirements SELECTION
```

| Аргумент | Обязательное значение |
|---|---|
| `--config MAIN` | Главный UTF-8 JSON с `operations` и `interpreters` |
| `--parameters VALUES` | Один JSON-объект явных скалярных значений |
| `--base-dir ABS` | Абсолютная база для относительных cwd команд |
| `--requirements SELECTION` | `all` либо JSON-массив IDs, включая `[]` |
| `-h`, `--help` | Справка без запуска |
| `--version` | Версия выбранных исходников/пакета без запуска |

`MAIN` и `VALUES` разрешаются относительно caller cwd. Путь документа операции
разрешается относительно главного файла. Относительный `commands[].cwd` считается
от `ABS`. `all` сохраняет порядок документа; массив сохраняет выбранный порядок
и повторы. Пустой массив даёт успех без команд при корректных общих входах.
Полные правила выборки принадлежат [чтению конфигурации](configuration-reading.md#публичный-договор).

Прежний явный `run --catalog-dir` имеет отдельный
[каталоговый договор](configuration.md#команды-и-аргументы). Для configured `run`
используются четыре рабочих аргумента из таблицы, а для catalogue — его аргументы.
Каждый запуск явно выбирает один источник.

Публичный API — существующая функция с `operation="run"`:

```python
prepare_resources(config_path, "run", selection, parameters,
                  base_dir=base_dir, interpreters=interpreters)
```

Её [шесть аргументов и результаты](resource-preparation.md#библиотечный-вход)
сохраняют общий договор. API передаёт готовые объекты обработчиков и возвращает
полные bytes/непрозрачные значения; CLI загружает объявленные готовые объекты,
проверяет обычную JSON-представимость и кодирует raw-потоки в base64.

## Конфигурация

Примеры: [главный файл](../examples/process-launch/app.example.json),
[требования запуска](../examples/process-launch/run.example.json),
[значения](../examples/process-launch/parameters.example.json).
Сначала материализуйте их по инструкции ниже; рабочий `app.json` читает `run.json`.

`operations.run` выбирает документ требований. Каждый объект имеет уникальный `id`
и непустой массив `commands`. Поля `argv`, `cwd`, `env`, `interpreter.name/options`
и однократная подстановка `${name}` описаны в
[общем договоре команд](action-execution.md#поля-команды). `env` — полное окружение
внешней команды; нужные переменные задаются явно. Renderer — стандартный
`string.Template`, shell между элементами argv не появляется.

`interpreters.result` в главном файле выбирает существующий модуль `interpreters`
и готовый объект `exit_result` из
[учебного поставщика](../examples/resource-preparation/interpreters.py).
Он принимает `options.accept=[0]`; обычный Python import path должен включать
его каталог. Это проверка результата непосредственного инструмента, а не HTTP-health.
Другие объекты подключаются через тот же
[интерфейс обработчика](action-execution.md#интерфейс-интерпретатора).

Все значения файла параметров — скаляры:

| Поле примера | Назначение |
|---|---|
| `python` | Абсолютный путь выбранного Python |
| `starter` | Абсолютный путь принятого внешнего `start_console.py` |
| `terminal` | Исполняемый терминал, здесь выбранный Zutty |
| `font`, `font_path` | Установленный шрифт и каталог для выбранного терминала |
| `content_dir` | Каталог обезличенных файлов примера для HTTP |
| `display` | Доступный X11 display |
| `bind_address` | Адрес двух серверов, здесь loopback `127.0.0.1` |
| `first_port`, `second_port` | Два выбранных свободных разных порта |
| `first_stdout`, `first_stderr` | Разные файлы диагностики первого терминала |
| `second_stdout`, `second_stderr` | Разные файлы диагностики второго терминала |

В примере log names относительны к рабочему cwd команды, то есть `--base-dir`.
Пути, терминал и порты являются данными примера, а не встроенными значениями ядра.
Рабочие заполненные конфиги принадлежат оператору и исключены из Git;
обезличенные `*.example.json` отслеживаются.

## Внешний инструмент

`examples/process-launch/start_console.py` — отдельная внешняя команда из
исходной поставки; ядро её не импортирует. При прямом вызове:

```text
python start_console.py --stdout-log FILE --stderr-log OTHER_FILE -- COMMAND ARG...
```

| Аргумент | Назначение |
|---|---|
| `--stdout-log FILE` | Обязательный файл полного stdout непосредственной команды |
| `--stderr-log OTHER_FILE` | Обязательный другой файл полного stderr |
| `--` и `COMMAND ARG...` | Непустой argv выбранного исполняемого инструмента |
| `-h`, `--help` | Справка без открытия логов/процесса |

Инструмент наследует выбранные caller cwd/env. Он открывает два binary append-файла,
передаёт argv в `Popen` с `stdin=DEVNULL` и новой сессией, закрывает свои handles
и возвращает управление, не ожидая долгоживущего ребёнка. Child пишет в файлы,
а не удерживает capture pipes caller: завершающийся launcher даёт EOF.
Родительские каталоги логов предоставляет вызывающий.

Успех — exit0, пустой stderr и один JSON+LF с полями
`status="submitted"`, `pid=положительный int`. PID принадлежит непосредственному
`COMMAND`, обычно терминалу, а не его HTTP-worker. Это подтверждение передачи
запуска; фактическую готовность сервиса подтверждают отдельные условия/запросы.

Exit1 означает ошибку открытия файла или spawn: stdout пуст, stderr содержит
доступную причину. Exit2 относится к форме аргументов, в том числе одинаковым
дословным log paths, и предшествует open/spawn. Старые разные log bytes сохраняются;
при частичной ошибке другой новый log может быть пустым или отсутствующим.
Пара файлов не является общей транзакцией. Filesystem aliases не анализируются.

Диагностические stdout/stderr терминала и интерактивный вывод worker в его PTY —
разные данные. HTTP-запросы и сообщения сервера видны в консоли. Log file может
остаться пустым, если непосредственная команда ничего туда не вывела. Повторное
исполнение дописывает только фактически полученные новые bytes, сохраняя старые.

## Результат и продолжение

Все выбранные цепочки планируются до первого эффекта. При неуспехе сохраняются
только попытанные требования/команды, их invocation, raw-потоки, exit code,
interpretation и контекст причины; хвост не запускается. Ранее переданная
консоль продолжает работать и остаётся под управлением пользователя.

CLI возвращает один JSON+LF: exit0/`succeeded` или exit1/`failed` с доступной
частичной работой; stderr команды находится внутри записи результата.
Raw stdout/stderr представлены как `{"encoding":"base64","data":"..."}`.
Ошибка явных входов/плана/загрузки обработчика даёт exit2, пустой stdout и
диагностику stderr до команд. Полная форма результата —
[общая форма подготовки](resource-preparation.md#результат-и-диагностика).

Для продолжения прочитайте причину, полные записи и фактическое состояние уже
переданных процессов. Владелец внешнего инструмента исправляет входы/среду и
выбирает следующее действие. Запуск команды и управление её временем жизни
разделены: пользователь завершает каждую видимую консоль самостоятельно.

## Пошаговая инструкция

Условия этого примера: Bash/Linux/POSIX, доступный X11 `DISPLAY`, `/usr/bin/zutty`,
DejaVuSansMono в `/usr/share/fonts/truetype/dejavu` и подготовленный Python
с зависимостями приложения. Проверенная среда — Ubuntu WSL2/Python3.12.3.
Другие терминалы/ОС требуют собственных выбранных команд и проверки, а не
выводятся из Python metadata. HTTP-сервер — стандартный модуль Python.

Откройте корень выбранных исходников. Задайте `app_python` абсолютным путём
подготовленного интерпретатора. Выберите два свободных разных порта; ниже
это `44181` и `44182`. Последующие сценарии выполняются последовательно,
с закрытием своих предыдущих серверов перед следующим запуском.

### Подготовить собственные рабочие файлы

```bash
: "${app_python:?Задайте абсолютный путь подготовленного Python}"
: "${DISPLAY:?Выберите доступный X11 display}"
source_root="$(pwd -P)"
terminal=/usr/bin/zutty
first_port=44181
second_port=44182
mkdir -p "$source_root/build"
workspace="$(mktemp -d "$source_root/build/process-launch-demo.XXXXXX")"
cp examples/process-launch/app.example.json "$workspace/app.json"
cp examples/process-launch/run.example.json "$workspace/run.json"
cp examples/process-launch/parameters.example.json "$workspace/parameters.json"
export PYTHONPATH="$source_root/src:$source_root/examples/resource-preparation"
"$app_python" -B - "$workspace" "$source_root" "$app_python" "$terminal" "$DISPLAY" "$first_port" "$second_port" <<'PY'
import json
from pathlib import Path
import sys
work, source, python, terminal, display, first, second = sys.argv[1:]
path = Path(work) / 'parameters.json'
values = json.loads(path.read_text())
values.update(python=python, terminal=terminal, display=display,
              starter=str(Path(source) / 'examples/process-launch/start_console.py'),
              content_dir=str(Path(source) / 'examples/process-launch'),
              first_port=int(first), second_port=int(second))
path.write_text(json.dumps(values, indent=2) + '\n')
print(work)
PY
```

Рабочий каталог напечатан; все три файла находятся внутри уже игнорируемого
`build`. Отслеживаемые шаблоны сохранены. Перед запуском доступны выбранные
пути/шрифт/display и свободны оба порта. Нужные изменения значений делайте
в своих рабочих файлах, согласованно с выбранными переменными оболочки.

### CLI: запустить обе консоли

```bash
"$app_python" -B -m environment_maintenance run \
  --config "$workspace/app.json" --parameters "$workspace/parameters.json" \
  --base-dir "$workspace" --requirements all > "$workspace/cli-result.json"
"$app_python" -B - "$workspace/cli-result.json" <<'PY'
import base64
import json
from pathlib import Path
import sys
value = json.loads(Path(sys.argv[1]).read_text())
assert value['status'] == 'succeeded'
assert [row['id'] for row in value['requirements']] == ['web-one', 'web-two']
for row in value['requirements']:
    raw = row['result']['commands'][0]['stdout']
    submitted = json.loads(base64.b64decode(raw['data'], validate=True))
    print(row['id'], submitted['status'], submitted['pid'])
PY
```

Caller завершается при живых консолях; напечатаны два `submitted` с разными
фактическими PID. Дождитесь сообщения `Serving HTTP` в каждом окне. Это отдельное
наблюдение готовности, а не обещание результата launcher. Затем проверьте оба:

```bash
"$app_python" -B - "$workspace" "$source_root" first_port second_port <<'PY'
import json
from pathlib import Path
import sys
from urllib.request import urlopen
work, source, *names = sys.argv[1:]
values = json.loads((Path(work) / 'parameters.json').read_text())
expected = (Path(source) / 'examples/process-launch/README.md').read_bytes()
for name in names:
    url = f"http://{values['bind_address']}:{values[name]}/README.md"
    with urlopen(url, timeout=3) as response:
        assert response.status == 200 and response.read() == expected
    print(name, 'HTTP200; expected example bytes')
PY
```

В окне `ENV2-example-web-one` нажмите Ctrl+C. Окно второго процесса остаётся
рабочим. Для нового HTTP-запроса соседу повторите тот же фрагмент с одним
последним аргументом `second_port` вместо пары `first_port second_port`.
Он снова даёт `HTTP200; expected example bytes`. Завершите второй сервер
его собственным Ctrl+C. Перед следующим сценарием оба порта освобождены.

### API: запустить выбранное подмножество

```bash
"$app_python" -B - "$workspace" <<'PY'
import json
from pathlib import Path
import sys
from environment_maintenance import prepare_resources
from interpreters import exit_result
work = Path(sys.argv[1])
values = json.loads((work / 'parameters.json').read_text())
result = prepare_resources(work / 'app.json', 'run', ['web-two'], values,
                           base_dir=work, interpreters={'result': exit_result})
assert result['status'] == 'succeeded'
assert [row['id'] for row in result['requirements']] == ['web-two']
assert type(result['requirements'][0]['result']['commands'][0]['stdout']) is bytes
print(result)
PY
```

Возвращён полный Python-результат с bytes, запускается только `web-two`.
После `Serving HTTP` выполните предыдущую HTTP-проверку только `second_port`.
Завершите эту консоль Ctrl+C. Порядок массива IDs управляет выборкой; `all`
берёт порядок документа, как в CLI-сценарии.

### CLI: выполнить пустую выборку

```bash
"$app_python" -B -m environment_maintenance run \
  --config "$workspace/app.json" --parameters "$workspace/parameters.json" \
  --base-dir "$workspace" --requirements '[]' > "$workspace/empty-result.json"
"$app_python" -B -m json.tool "$workspace/empty-result.json"
```

Ожидаются exit0, `status="succeeded"`, `requirements=[]`, `error=null`;
новой консоли нет. Общие входы и объявленные обработчики остаются корректными.

### Прямой вызов внешнего инструмента

```bash
direct_result="$(mktemp "$workspace/direct-result.XXXXXX.json")"
"$app_python" -B "$source_root/examples/process-launch/start_console.py" \
  --stdout-log "$workspace/direct.stdout.log" \
  --stderr-log "$workspace/direct.stderr.log" -- \
  "$terminal" -font DejaVuSansMono -fontpath /usr/share/fonts/truetype/dejavu \
  -title ENV2-example-direct -e "$app_python" -B -m http.server "$second_port" \
  --bind 127.0.0.1 --directory "$source_root/examples/process-launch" > "$direct_result"
cat "$direct_result"
```

Ожидается один JSON с `submitted` и actual terminal PID, exit0/EOF caller.
После `Serving HTTP` проверьте `second_port` предыдущим HTTP-фрагментом и
закройте консоль её Ctrl+C. Повторите блок прямого вызова после освобождения
порта: результат сохранится в новом файле, а два log paths останутся теми же.
Старые bytes логов сохраняются как префиксы; добавляется только действительная
новая диагностика терминала. Оба файла могут оставаться пустыми при отсутствии
вывода. HTTP-ответы/консольные сообщения не выдаются за bytes этих логов.
Проверьте второй прямой запуск и завершите его собственной консолью.

### Условия достоверного наблюдения

Видимые окна/PTY, submitted PID, HTTP-готовность и независимый stop наблюдаются
отдельно. Для автоматического точного ввода нужен контроль входных событий
своих окон: собственный private display сам по себе не доказывает исключительность
ввода. Дополнительные события ограничивают доказательство такого опыта;
их источник устанавливается по данным, а не приписывается пользователю или ОС.
Продукт не обещает исключать ввод пользователя. Работайте со своими окнами
и завершайте свои процессы; исходные данные/полные результаты сохраняйте
до очистки рабочих файлов. В проверках проекта используется собственный
видимый Xephyr; обычный пользователь выбирает доступную ему реальную среду.

## Собственный внешний инструмент

Когда готовых средств недостаточно, разработайте инструмент обслуживаемого
приложения. Получайте [IDs и пакет объектов/all](configuration-reading.md#публичный-договор),
меняйте [один объект/удаление/очистку через CRUD](configuration-editing.md#библиотека-записи),
объявляйте команды и подключайте выбранный
[ResultInterpreter](action-execution.md#интерфейс-интерпретатора).
Полные аргументы/правильные примеры каждой операции принадлежат этим руководствам.
Общий исполнитель остаётся общим; правило запуска/диагностики конкретного
приложения принадлежит вашему внешнему инструменту и его конфигурации.
