# Запуск процессов

[Пошаговая инструкция](#пошаговая-инструкция).

CLI run передаёт выбранные команды и регистрирует их PGID по ENV/APP. Stop отправляет SIGTERM сохранённым группам. Команды, терминал, параметры и готовность сервиса принадлежат приложению; передача запуска сама не доказывает его готовность.

## Входы и аргументы

Полный [справочник форм](configuration.md#именованные-run-и-stop) содержит четыре run формы и stop/list/all. Run без ENV создаёт UUID; без APP выбирает все applications. ENV должна быть непустым shell-safe именем, отличным от `all`; используйте буквы/цифры, `_`, `-`, `.`, например `dev-1`. APP — буквальный ID, включая `all`.

`run list` возвращает IDs конфигурации без effects. С ENV — только ещё не зарегистрированные IDs найденной среды; для отсутствующей ENV ответ пустой и found=false. Список не создаёт ENV. Полный run занятой непустой ENV отвергается. `--app` позволяет добавить один ещё не зарегистрированный APP, сохранив остальные. Дубликат уже зарегистрированного APP отвергается.

Run принимает необязательные config/parameters/base-dir из [профиля](persistent-entry.md#поля-постоянного-профиля). Stop не читает эти файлы: без аргументов выводит реестр, с ENV останавливает её группы, с ENV/APP — одну, `stop all` — все читаемые среды. Выбор APP для stop требует ENV.

## Конфигурация

Документ `operations.run` содержит `applications`, массив объектов с уникальным непустым `id` и `commands`. Другие операции сохраняют `requirements`. Все выбранные цепочки проходят preflight до резервирования/процессов. Неизвестный CLI APP предупреждается/пропускается; пустой план возвращает адрес и удаляет пустой итоговый файл.

Команда задаёт argv/cwd/env/interpreter по [общему договору](action-execution.md#поля-команды). Последняя достигнутая команда полной цепочки должна вернуть в сыром stdout JSON `{"status":"submitted","pgid":23456}` с положительным integer PGID, не boolean/строкой. Это PGID именно переданной группы. Интерпретатор отдельно определяет предметный успех; полученный PGID сохраняется и при его отказе. Неполная цепочка не даёт PGID последней объявленной команды.

Ошибки одной APP не запускают оставшийся хвост её цепочки, остальные APP продолжаются. Health, retry и rollback процессов не добавляются. Библиотечный `prepare_resources(..., 'run', selection, ...)` остаётся исполнителем цепочек; регистрацию именованных запусков предоставляет CLI run.

## Внешний инструмент

Рабочий launcher находится в установленном пакете:

```bash
"$maintenance_python" -I -B -m environment_maintenance.running.console \
  --stdout-log /absolute/path/to/own/stdout.log \
  --stderr-log /absolute/path/to/own/stderr.log -- COMMAND ARG
```

| Вход | Договор |
|---|---|
| `maintenance_python` | Python выбранной установки EM; Python payload приложения может быть другим |
| `--stdout-log`, `--stderr-log` | Обязательные разные пути; parent directories подготовлены владельцем |
| `-- COMMAND ARG...` | Явный executable и argv без shell-пересборки |

Launcher открывает два файла в append, запускает Popen с новой сессией и DEVNULL stdin, затем выводит submitted/pgid. Exit0 означает передачу, exit1 — OSError, неправильные аргументы — exit2. Результат не зависит от того, успела ли команда завершиться. Он не проверяет здоровье сервиса. Example `start_console.py` только делегирует этому модулю.

Для видимого окна payload выбирает установленный терминал и передаёт ему команду приложения. Сохраняются её argv/cwd/env. Логи немедленной команды и вывод приложения внутри PTY терминала — разные наблюдения.

## Реестр окружений

OS temp определяется штатным tempfile, в том числе явно выбранным TMPDIR. Общий каталог — `environment-maintenance`, новый файл — `env-ENV.json`. Две установки с тем же OS temp видят один реестр.

```json
{"format-version":1,"environment-title":"dev-1","applications":{"web":{"pgid":23456}}}
```

Имя среды читается из payload, фактический путь используется для записи/удаления. `format-version` сохраняется, но не служит проверкой равенства1; требуется читаемая известная структура. Перед APP создаётся пустая запись: только проверка доступности/новое exclusive создание выполняются под коротким flock. Lock снимается до команд при любом исходе. Append/removal не получают дополнительную lock.

Ошибка начальной записи/close удаляет только собственный новый файл. При отказавшем cleanup остаётся правдивая ошибка с обеими причинами. Ошибка open не даёт владения чужим файлом. [Ручное восстановление](migration-v4.md#ручное-восстановление) сохраняет остальные данные.

## Результат и продолжение

Run JSON содержит operation/status/environment/file/file_exists/planned/received_pgids/applications/errors. Каждая APP имеет id, фактический pgid либо null и полный result команд; [raw streams](action-execution.md#итог-исполнения) кодируются в base64. Полученный PGID остаётся в ответе, даже если его сохранение не удалось. Пустой файл после обработки удаляется.

Stop JSON содержит stopped/errors; сигнал посылается один раз. ESRCH тихо удаляет stale mapping, ошибка сигнала сохраняет его; остальные цели продолжаются. Удаление последнего APP удаляет файл. Ошибки чтения/записи возвращаются явно, читаемые другие ENV обрабатываются. При отсутствии отправленных сигналов message дословно «Ничего не остановлено.». Успех stop подтверждает отправку SIGTERM, а не ожидание завершения процесса.

Exit0 означает успешный результат, exit1 — runtime/storage отказ, входная ошибка — exit2. Сначала изучите полный результат; затем осознанно продолжайте конкретную APP или [восстановление](migration-v4.md#ручное-восстановление).

## Пошаговая инструкция

### Подготовить собственные рабочие файлы

Выберите installed `package_root`/`app_python` по [общему контексту](npm-distribution.md#библиотека-и-поставленные-примеры), отдельный пустой `workspace`, доступный DISPLAY, Zutty/DejaVuSansMono и два свободных порта. Это явные prerequisites примера. Для его собственного реестра:

```bash
first_port=44181
second_port=44182
mkdir -p "$workspace/os-temp"
export TMPDIR="$workspace/os-temp"
"$app_python" -I -B - "$package_root" "$workspace" "$DISPLAY" "$first_port" "$second_port" <<'PY'
import json
from pathlib import Path
import sys
package, work = map(Path, sys.argv[1:3])
display, first, second = sys.argv[3:]
source = package / 'examples/process-launch'
main = json.loads((source / 'app.example.json').read_text())
main['interpreters']['result']['module'] = 'environment_maintenance.actions.interpreters'
main['invocation'] = dict(parameters='parameters.json', base_dir='.')
(work / 'start-app.json').write_text(json.dumps(main))
run = json.loads((source / 'run.example.json').read_text())
for row in run['applications']:
    command = row['commands'][-1]
    command['argv'] = ['${maintenance_python}', '-I', '-B', '-m',
        'environment_maintenance.running.console', *command['argv'][3:]]
(work / 'run.json').write_text(json.dumps(run))
values = json.loads((source / 'parameters.example.json').read_text())
values.update(python=sys.executable, maintenance_python=sys.executable,
    display=display, content_dir=str(source), first_port=int(first), second_port=int(second),
    first_stdout=str(work / 'one.stdout'), first_stderr=str(work / 'one.stderr'),
    second_stdout=str(work / 'two.stdout'), second_stderr=str(work / 'two.stderr'))
(work / 'parameters.json').write_text(json.dumps(values))
PY
```

Выбранные порты должны быть свободны. Production launch получает параметры от своего владельца; при необходимости [сетевое согласование](settings-alignment.md#автоматический-подбор-портов) вызывается отдельно.

### CLI: запустить обе консоли

Добавьте выбранный package bin в PATH. Из workspace:

```bash
start-app run list
start-app run --env consoles --app web-one
start-app run --env consoles --app web-two
start-app run list --env consoles
start-app stop list --env consoles
```

Видны два собственных окна. Каждый run возвращает один PGID, последний run list пуст: оба APP зарегистрированы. Следующий блок отдельно наблюдает HTTP-сервисы, не добавляя health gate в продукт:

```bash
"$app_python" -I -B - "$first_port" "$second_port" <<'PY'
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
for port in sys.argv[1:]:
    for attempt in range(50):
        try:
            with urlopen('http://127.0.0.1:' + port, timeout=1) as reply:
                assert reply.status == 200
                assert reply.read()
            print('HTTP ready:', port)
            break
        except URLError:
            if attempt == 49:
                raise
            time.sleep(.1)
PY
start-app stop --env consoles --app web-one
start-app stop --env consoles
start-app stop list --env consoles
```

После stop своей группы соответствующий сервер завершается; остановка первого сохраняет второй до его отдельной остановки. Последний список не содержит ENV. Собственные рабочие файлы/logs можно удалить после проверки closure. Другие ENV/реестр OS temp не очищаются.

### API: запустить выбранное подмножество

Для библиотечных chains используйте [публичный prepare_resources](resource-preparation.md#библиотечный-вход) с operation run, выбранными IDs и явными parameters/base_dir/interpreters. Он возвращает полные bytes/opaque values и не создаёт именованный CLI registry. Когда нужен stop по ENV/APP, используйте описанный CLI путь.

### CLI: выполнить пустую выборку

Пустой applications document или отсутствующий запрошенный APP дают planned0; пустой итоговый файл удаляется. Для обычного полного запуска заполните applications и опустите APP. У SDK выбор `[]` остаётся явной пустой chain selection.

### Прямой вызов внешнего инструмента

С подготовленным writable workspace:

```bash
"$app_python" -I -B -m environment_maintenance.running.console \
  --stdout-log "$workspace/direct.stdout" --stderr-log "$workspace/direct.stderr" \
  -- /usr/bin/printf 'direct example\n'
```

Submitted PGID относится к короткой команде printf; она может уже завершиться. Файл stdout получает её байты, stderr пуст. Прямой launcher не регистрирует ENV: регистрацию выполняет вызывающий CLI run.

### Условия достоверного наблюдения

Фактические PGID/registry/logs, наличие собственных окон, HTTP и закрытие процессов — разные наблюдения. Прикладывайте их в нужном объёме. Встроенный launcher не проверяет оконную готовность или endpoint и не ждёт закрытия консоли.

## Собственный внешний инструмент

Приложение предоставляет свои launch commands/cwd/env и сменный интерпретатор. Для стандартной передачи группы используйте module launcher и [общий exit interpreter](action-execution.md#интерфейс-интерпретатора). Сложный прикладной анализ остаётся у приложения; пакет не импортирует ERP/Poise и не копирует core из examples.
