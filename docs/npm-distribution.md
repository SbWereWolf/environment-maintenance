# Пакетная поставка npm

[Пошаговая инструкция установки и всех CLI-операций](#пошаговая-инструкция).

## Договор экземпляра

2.0.0 — локальный кандидат самостоятельного инструмента. Стандартный npm
устанавливает tgz в выбранный отдельный prefix и предоставляет `start-app`.
Lifecycle создаёт `.venv` внутри пакета и поручает pip установить Python-проект,
`jsonpatch` и `jsonpointer`. Core, зависимости, исходники, docs/tests/examples
и единственный AI-скилл находятся в этом экземпляре. Обслуживаемые конфиги,
ресурсы и инструменты — явные внешние входы.

Поддерживается Linux/POSIX, требуются Node22+, npm10+, Python3.11+ с venv/pip.
Фактически проверены Ubuntu24.04.4 WSL2 x86_64, Node22.23.2, npm10.9.8 и
Python3.12.3. Metadata engines объявляет поддержку; строгую проверку engines
определяет npm. Python с его стандартной библиотекой, Node и ОС являются
внешними prerequisites. Готовое окружение создаётся в конечном месте установки.
Доступ к выбранному Python-индексу/средствам сборки обеспечивает оператор.

| Вход | Назначение |
|---|---|
| `ENVIRONMENT_MAINTENANCE_PYTHON` | Обязательный выбранный executable Python при установке; используйте абсолютный путь |
| npm `--prefix` | Самостоятельный корень экземпляра; короткий вход находится в его `bin` |
| npm `--ignore-scripts=false` | Разрешить требуемый lifecycle подготовки runtime |
| `PATH` | Включите `prefix/bin` для короткой команды в своей текущей оболочке |
| `PYTHONPATH` | Явные каталоги plugins обслуживаемого приложения при рабочем вызове |
| стандартные настройки pip | Выбранный индекс/колёса/cache; зависимости разрешает pip |

Root `./start-app` исходного комплекта выбирает соседнюю установленную `.venv`
с `-I`. Npm bin использует свой Python с `-P -s -B`, сохраняя явно настроенный
plugin import path. В следующих шагах используется npm bin. Остальные экземпляры,
включая выпущенный1.0.0, сохраняются до отдельного явного обновления.

## Команды и полные аргументы

| Вход | Полный справочник и инструкция |
|---|---|
| `start-app --version`, `--help` | Версия/справка без действий |
| `start-app infra`, `deps` | [Подготовка ресурсов и все аргументы](resource-preparation.md#команды-и-аргументы) |
| `start-app adjust` | [Согласование настроек](settings-alignment.md#входы-и-результаты) |
| `start-app check --config` | [Проверки presence/availability/связанных условий](resource-checking.md#команды-и-аргументы) |
| `start-app run --config` | [Запуск выбранных процессов](process-launch.md#входы-и-аргументы) |
| `check/run --catalog-dir` | [Отдельный каталоговый контракт, включая --values/--set/--dry-run](configuration.md#команды-и-аргументы) |

Для infra/deps/adjust/run обязательны `--config`, `--parameters`, абсолютный
`--base-dir` и `--requirements` (`all` или JSON-массив IDs, включая `[]`).
Configured check использует первые три аргумента. Значения путей config/parameters
считаются от cwd caller; база cwd команд задаётся явно. Npm bin сохраняет cwd,
argv/env/stdin/stdout/stderr и обычные коды выбранного CLI. JSON и binary-потоки
не обрезаются обёрткой. Внутренние результаты принадлежат выбранному договору;
например, каталоговый контракт имеет собственные явные ограничения вывода.

`infra`/`deps`/`adjust`/`check`/`run` — отдельные операции. Полный рабочий путь
оператор задаёт их явной последовательностью; `run` только запускает выбранные
команды. Команды, цепочки, шаблоны `string.Template` и интерпретаторы предоставляет
обслуживаемое приложение. Общий читатель одинаково разрешает отдельные конфиги.

## Библиотека и поставленные примеры

[Подготовка собственного экземпляра и рабочего каталога](#пошаговая-инструкция).

После установки ниже `package_root` получается штатным `npm root`, а `app_python`
обозначает собственный Python экземпляра. Публичный API импортируется этим Python
обычно из site-packages. Для использования поставленных руководств:

```bash
cd "$package_root"
```

Руководства [чтения](configuration-reading.md#пошаговая-инструкция),
[записи](configuration-editing.md#пошаговая-инструкция),
[действий](action-execution.md#пошаговая-инструкция),
[подготовки](resource-preparation.md#пошаговая-инструкция),
[согласования](settings-alignment.md#пошаговая-инструкция),
[проверок](resource-checking.md#пошаговая-инструкция) и
[консолей](process-launch.md#пошаговая-инструкция) содержат все операции API,
аргументы, исходные файлы и ожидаемые результаты. Их `PYTHONPATH=src` явно
выбирает поставленный source-набор внутри этого экземпляра. Такой пример
проверяет API/выбранный source CLI; настоящий npm bin проверяется отдельно ниже.
Для development checkout действуют те же примеры с его подготовленным Python.

Полные функции: list_requirement_ids/read_requirements (IDs, batch, all),
add_requirement/update_requirement/delete_requirement/clear_requirements,
plan_action/execute_action, prepare_resources/check_resources. Если готового
поведения недостаточно, разработайте внешний инструмент обслуживаемого приложения
через [публичные read/CRUD](configuration-editing.md#собственный-внешний-инструмент)
и [интерфейс ResultInterpreter](action-execution.md#интерфейс-интерпретатора).

## Пошаговая инструкция

### Собрать и установить выбранный кандидат

Начальные условия: открыт исходный корень выбранной ревизии2.0.0, в текущей
оболочке активирован выбранный Node/npm и доступен Python с venv/pip.
Подготовьте runtime штатным менеджером своей среды. Задайте ENVIRONMENT_MAINTENANCE_PYTHON его
реальным абсолютным путём. Для переданного готового tgz используйте его путь
и контрольную сумму вместо шага pack. Сумма должна совпасть с квитанцией поставки.

```bash
: "${ENVIRONMENT_MAINTENANCE_PYTHON:?Выберите абсолютный путь Python с venv/pip}"
source_root="$(pwd -P)"
demo_dir="$(mktemp -d "${TMPDIR:-/tmp}/environment-maintenance-demo.XXXXXX")"
artifact_dir="$demo_dir/artifacts"
prefix="$demo_dir/independent prefix Ω"
workspace="$demo_dir/serviced cwd Ω"
mkdir -p "$artifact_dir" "$workspace"
npm pack --json --pack-destination "$artifact_dir" > "$artifact_dir/pack.json"
archive="$artifact_dir/environment-maintenance-2.0.0.tgz"
sha256sum "$archive"
npm install --global --prefix "$prefix" --ignore-scripts=false --no-audit --no-fund "$archive"
export PATH="$prefix/bin:$PATH"
package_root="$(npm root --global --prefix "$prefix")/environment-maintenance"
app_python="$package_root/.venv/bin/python"
export package_root app_python workspace
cd "$workspace"
start-app --version
start-app --help
```

Версия — `environment-maintenance 2.0.0`, help перечисляет пять операций.
Вы находитесь вне исходного checkout. npm/pip выполняют свою стандартную
установку; флаги no-audit/no-fund относятся к выводу/сетевым действиям npm,
а не к семантике инструмента. Тестовый стенд может заранее предоставить реальные
колёса через стандартные PIP_NO_INDEX/PIP_FIND_LINKS; это не обязательный
продуктовый wheelhouse и не поставка Python внутри архива.

### Подготовить собственные конфиги

Демонстрации используют поставленные инструменты на собственных копиях.
Infra/deps/run имеют общий набор, adjust/check — свои готовые демонстрационные
данные. Это примеры входов отдельных операций, а не профиль ERP/Poise.
Каждое реальное обслуживаемое приложение предоставляет свой согласованный набор.

```bash
export PYTHONPATH="$package_root/examples/resource-preparation"
"$app_python" -P -s -B - <<'PY'
import json
import os
from pathlib import Path
import runpy
root, work = Path(os.environ['package_root']), Path(os.environ['workspace'])
for name in ('prep', 'alignment', 'checking'):
    (work / name).mkdir()
prep = runpy.run_path(str(root / 'examples/resource-preparation/walkthrough.py'))
prep['prepare_demo'](work / 'prep')
main_path = work / 'prep/app.example.json'
main = json.loads(main_path.read_text())
main['operations']['run'] = 'run.example.json'
main_path.write_text(json.dumps(main))
run = json.loads((work / 'prep/infra.example.json').read_text())
run['requirements'] = [run['requirements'][0]]
run['requirements'][0]['id'] = 'launcher'
run['requirements'][0]['commands'] = [run['requirements'][0]['commands'][0]]
run['requirements'][0]['commands'][0]['argv'][3] = 'run'
(work / 'prep/run.example.json').write_text(json.dumps(run))
alignment = runpy.run_path(str(root / 'examples/settings-alignment/walkthrough.py'))
_, _, _, before = alignment['prepare_demo'](work / 'alignment')
(work / 'alignment/before.json').write_text(json.dumps(before))
checking = runpy.run_path(str(root / 'examples/resource-checking/walkthrough.py'))
checking['prepare_demo'](work / 'checking')
PY
```

Главные/операционные/параметрические файлы находятся в workspace; исходные
*.example.json сохранены. `source_path` учебных внешних инструментов указывает
на поставленный src внутри prefix. Обычный bin всё ещё импортирует своё ядро
из собственного установленного runtime, а PYTHONPATH здесь предоставляет plugin.

### Исполнить пять выбранных операций через короткий вход

```bash
start-app infra --config "$workspace/prep/app.example.json" \
  --parameters "$workspace/prep/values.json" --base-dir "$workspace/prep" \
  --requirements '["assets"]' > "$workspace/infra-result.json"
start-app deps --config "$workspace/prep/app.example.json" \
  --parameters "$workspace/prep/values.json" --base-dir "$workspace/prep" \
  --requirements all > "$workspace/deps-result.json"
start-app adjust --config "$workspace/alignment/app.example.json" \
  --parameters "$workspace/alignment/parameters.example.json" --base-dir "$workspace/alignment" \
  --requirements all > "$workspace/adjust-result.json"
start-app check --config "$workspace/checking/app.example.json" \
  --parameters "$workspace/checking/parameters.example.json" --base-dir "$workspace/checking" \
  > "$workspace/check-result.json"
start-app run --config "$workspace/prep/app.example.json" \
  --parameters "$workspace/prep/values.json" --base-dir "$workspace/prep" \
  --requirements all > "$workspace/run-result.json"
"$app_python" -P -s -B - <<'PY'
import json
import os
from pathlib import Path
import runpy
root, work = Path(os.environ['package_root']), Path(os.environ['workspace'])
for name in ('infra', 'deps', 'adjust', 'check', 'run'):
    answer = json.loads((work / (name + '-result.json')).read_text())
    assert answer['operation'] == name and answer['status'] == 'succeeded'
events = [json.loads(line)['label'] for line in (work / 'prep/events.jsonl').read_text().splitlines()]
assert events == ['install', 'configure', 'dependencies', 'run']
demo = runpy.run_path(str(root / 'examples/settings-alignment/walkthrough.py'))
demo['assert_settings'](work / 'alignment', json.loads((work / 'alignment/before.json').read_text()),
                        'QUEUE_NAME', 'billing.jobs')
checks = json.loads((work / 'check-result.json').read_text())
assert len(checks['resources']) == 2 and checks['checks'][0]['id'] == 'queue-agreement'
print('five installed operations: results, effects and settings confirmed')
PY
```

Каждая команда имеет код0, выбранный operation и полный JSON результата.
Run здесь запускает короткий внешний probe с наблюдаемым событием `run`.
Для долгоживущих приложений используйте [полную инструкцию видимых консолей](process-launch.md#пошаговая-инструкция):
две отдельные консоли, HTTP-проверка и независимая остановка каждого процесса.
Факт submitted/PID означает передачу команды, пригодность сервиса проверяется отдельно.

### Прочитать и изменить конфиг через установленную библиотеку

Здесь import выполняется из собственного site-packages без source PYTHONPATH.
Изменяется только отдельная копия демонстрационного документа:

```bash
env -u PYTHONPATH "$app_python" -P -s -B - <<'PY'
import os
from pathlib import Path
from shutil import copy2
from environment_maintenance import (list_requirement_ids, read_requirements,
    add_requirement, update_requirement, delete_requirement, clear_requirements)
root, work = Path(os.environ['package_root']), Path(os.environ['workspace']) / 'library'
work.mkdir()
for path in (root / 'examples/configuration-reading').glob('*.example.json'):
    copy2(path, work / path.name)
config = work / 'app.example.json'
assert list_requirement_ids(config, 'infra') == ['postgres', 'redis']
assert read_requirements(config, 'infra', ['redis'])[0]['id'] == 'redis'
assert len(read_requirements(config, 'infra', 'all')) == 2
add_requirement(config, 'infra', {'id': 'demo', 'commands': []})
update_requirement(config, 'infra', 'demo', [{'op': 'add', 'path': '/label', 'value': 'Демонстрация'}])
assert read_requirements(config, 'infra', ['demo'])[0]['label'] == 'Демонстрация'
delete_requirement(config, 'infra', 'demo')
assert list_requirement_ids(config, 'infra') == ['postgres', 'redis']
clear_requirements(config, 'infra')
assert read_requirements(config, 'infra', 'all') == []
print('installed library: IDs, batch, all, add, update, delete, clear confirmed')
PY
```

Для остальных API выполните уже поставленные правильные walkthrough:

```bash
cd "$package_root"
PYTHONPATH=src "$app_python" -B examples/action-execution/walkthrough.py
PYTHONPATH=src "$app_python" -B examples/resource-preparation/walkthrough.py
PYTHONPATH=src "$app_python" -B examples/settings-alignment/walkthrough.py
PYTHONPATH=src "$app_python" -B examples/resource-checking/walkthrough.py
```

Ожидается код0 и подтверждения собственных проверок каждого walkthrough. Их
source CLI явно использует поставленный src; эти результаты дополняют предыдущие
настоящие short-bin вызовы, а не заменяют их. Временные файлы walkthrough
закрываются их владельцами; исходные шаблоны сохраняются.

### Удалить и повторно установить те же байты

После сохранения нужных результатов примера завершите свои процессы/консоли.
Обычная команда удаления и повторной установки:

```bash
cd "$workspace"
npm uninstall --global --prefix "$prefix" --no-audit --no-fund environment-maintenance
npm install --global --prefix "$prefix" --ignore-scripts=false --no-audit --no-fund "$archive"
"$prefix/bin/start-app" --version
sha256sum "$archive"
```

Версия снова2.0.0, digest архива прежний. Аналогично обновление устанавливает
новый отдельно выбранный проверенный пакет в свой prefix. Полученные результаты
и tgz передаются получателю до удаления демонстрационных рабочих материалов.
Рабочие конфиги/журналы не помещаются в историю версий.

## Диагностика и правильное продолжение

[Правильная установка и проверка экземпляра](#пошаговая-инструкция).

При установке сначала прочитайте исходную причину npm/venv/pip. Предоставьте
доступный Python с venv/pip, writable отдельный prefix и доступ к выбранному
индексу/колёсам; затем повторите стандартную установку выбранного tgz. При
неуспехе venv следующий pip не выполняется. Неподготовленный runtime диагностируется
рабочим входом; подготовка повторяется явно через npm, не внутри обычного вызова.

Для операций с `--config` успех возвращает0; предметный отказ —1 с полным
результатом; ошибка входа/создания процесса —2 с доступной причиной.
Каталоговые `check/run --catalog-dir` используют отдельный
[договор результата](configuration.md#результат-и-повторный-запуск):
0 — `ready`, 2 — `action_required`, 3 — `unavailable`, 4 — `failed`.
Эти предметные результаты приходят полным JSON в stdout. Ошибка входа каталога
также имеет код2, но передаёт причину в stderr при пустом stdout; результат
`action_required` означает необходимость обслуживания ресурса.

Npm installation имеет
собственный ненулевой исход при ошибке lifecycle. Сигнальный исход Python
сохраняется как завершение тем же сигналом, включая PIPE/USR1; способ числового
представления оболочки определяется самой оболочкой. Обёртка не включает
отладчик вместо передачи USR1 и не подменяет PIPE обычным кодом2.

Перед осознанным продолжением смотрите полные результаты и уже совершённые
действия; внешние инструменты и оператор владеют предметным исправлением.
Публикация npm, Git tag/push и обновление существующих потребителей — отдельные
действия. Наличие локального кандидата их не выполняет.
