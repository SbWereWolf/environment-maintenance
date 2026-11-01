# Пакетная поставка npm

[Пошаговая инструкция установки и всех CLI-операций](#пошаговая-инструкция).

## Договор экземпляра

Версия 2.1.0 поставляется самостоятельным пакетом. Стандартный npm устанавливает
выбранный tgz в отдельный prefix и предоставляет его `bin/start-app`.
Lifecycle создаёт `.venv` внутри пакета; pip устанавливает Python-проект,
`jsonpatch` и `jsonpointer`. Исходники, docs/tests/examples и один AI-скилл
находятся в этом экземпляре. Конфиги и инструменты обслуживаемого приложения
задаёт его владелец.

Поддерживается Linux/POSIX: Node 22+, npm 10+, Python 3.11+ с venv/pip.
Проверенный контекст — Ubuntu/WSL, Node 22.23.2, npm 10.9.8, Python 3.12.3.
Зависимости разрешают пакетные менеджеры. Metadata engines объявляет поддержку;
строгую проверку engines определяет npm. Готовая среда создаётся на месте.

| Настройка установки | Значение |
|---|---|
| `ENVIRONMENT_MAINTENANCE_PYTHON` | Абсолютный выбранный Python с venv/pip; нужен при установке |
| npm `--prefix` | Самостоятельный корень выбранного экземпляра |
| npm `--ignore-scripts=false` | Выполнить необходимую подготовку runtime |
| Настройки pip | Выбранный индекс/колёса/cache, включая стандартный offline-режим |
| Приложение | Предоставляет доступные своему runtime внешние инструменты и готовые обработчики |

Корневой `./start-app` комплекта выбирает `ROOT/.venv` с `-I`.
Npm-вход выбирает `PACKAGE_ROOT/.venv` с `-P -s -B`, сохраняя cwd и обычный
явно подготовленный import path. После подготовки используйте локальный вход
конкретной установки либо его абсолютный путь. Другие экземпляры сохраняются.
[Постоянный профиль](persistent-entry.md#выбор-установки-и-рабочего-файла)
объясняет точное расположение `start-app.json` для обоих входов.

## Команды и полные аргументы

| Обычный вызов | Полный справочник и инструкция |
|---|---|
| `./start-app --version`, `--help` | Версия/справка выбранной установки без действий |
| `./start-app infra`, `deps` | [Подготовка ресурсов](resource-preparation.md#команды-и-аргументы) |
| `./start-app adjust` | [Согласование](settings-alignment.md#входы-и-результаты) |
| `./start-app check` | [Проверки](resource-checking.md#команды-и-аргументы) |
| `./start-app run` | [Запуск процессов](process-launch.md#входы-и-аргументы) |
| Явные `check/run --catalog-dir` | [Отдельный каталоговый договор](configuration.md#команды-и-аргументы) |

Пути, значения и выбор ресурсов берутся из постоянного профиля.
`--config`, `--parameters`, `--base-dir` и применимый `--requirements` доступны
как [необязательные переопределения](persistent-entry.md#переопределение-одного-вызова).
Полностью явная прежняя форма сохраняется. Npm-вход передаёт полные argv,
env/stdin/stdout/stderr и обычные/сигнальные исходы выбранного CLI.

Все пять операций отдельны: `run` исполняет только объявленный запуск,
`check` — объявленные наблюдения. Команды, цепочки, шаблоны `string.Template`
и интерпретаторы принадлежат приложению; один читатель разрешает его документы.

## Библиотека и поставленные примеры

[Контекст и правильная подготовка](#пошаговая-инструкция).

Следующие технические API-примеры используют один подготовленный пакет.
Оператор задаёт значения один раз: `package_root` — установленный пакет,
`app_python` — его `.venv/bin/python`, `workspace` — существующий собственный
каталог данных; `prefix`, `archive`, `prerequisite_python` нужны для обслуживания
самой установки. Это контекст примеров API, а не обязательные параметры запуска.

```bash
package_root=/absolute/path/to/prefix/lib/node_modules/environment-maintenance
app_python="$package_root/.venv/bin/python"
workspace=/absolute/path/to/private-workspace
prefix=/absolute/path/to/prefix
archive=/absolute/path/to/environment-maintenance-2.1.0.tgz
prerequisite_python=/absolute/path/to/python3
export package_root app_python workspace
```

[Чтение](configuration-reading.md#пошаговая-инструкция),
[CRUD](configuration-editing.md#пошаговая-инструкция),
[исполнение](action-execution.md#пошаговая-инструкция),
[подготовка](resource-preparation.md#пошаговая-инструкция),
[согласование](settings-alignment.md#пошаговая-инструкция),
[проверка](resource-checking.md#пошаговая-инструкция) и
[запуск](process-launch.md#пошаговая-инструкция) имеют собственные полные инструкции.
Примеры с `PYTHONPATH=src` явно выбирают поставленный исходный набор; обычный
npm-вход использует собственный установленный core. Наблюдения этих способов
фиксируются отдельно.

## Пошаговая инструкция

### Собрать и установить выбранный кандидат

Оператор выбирает точный source commit и каталог результата сборки:

```bash
npm pack --json --pack-destination /absolute/path/to/candidate
```

Передайте архив и его SHA-256. Установка выбранных байтов в отдельный prefix:

```bash
ENVIRONMENT_MAINTENANCE_PYTHON=/absolute/path/to/python3 npm install --global --prefix /absolute/path/to/prefix --ignore-scripts=false --no-audit --no-fund /absolute/path/to/environment-maintenance-2.1.0.tgz
/absolute/path/to/prefix/bin/start-app --version
npm root --global --prefix /absolute/path/to/prefix
```

Ожидаемая версия — `environment-maintenance 2.1.0`. Последняя команда показывает
корень npm-модулей; добавьте `environment-maintenance` для каталога пакета.
Идентифицируйте реальный source/tree/tgz digest, runtime и результаты проверки.
Публикация в реестре — отдельное действие, эта инструкция её не выполняет.

При offline-установке оператор предоставляет стандартные `PIP_NO_INDEX=1`
и `PIP_FIND_LINKS` с выбранными build/runtime колёсами. Проверочный wheelhouse
не является встроенным источником зависимостей продукта.

### Подготовить собственные конфиги

Следуйте [инструкции постоянного входа](persistent-entry.md#пошаговая-инструкция).
Приложение или настроенный владелец развёртывания создаёт рабочие main/parameters
и отдельные документы операций через свой конфиг. Примеры остаются в пакете;
рабочие копии хранятся вне `.runtime` и Git. Подготовка готового обработчика
в собственной среде — часть этой однократной настройки.

### Исполнить пять выбранных операций через короткий вход

В каталоге выбранного локального входа:

```bash
./start-app infra
./start-app deps
./start-app adjust
./start-app check
./start-app run
```

Ожидаются успешные результаты объявленных приложением команд.
Учебный профиль и его точные события описаны у
[постоянного входа](persistent-entry.md#пять-обычных-операций).
Работа из постороннего cwd использует абсолютный вход той же установки.
Дополнительные ключи нужны только для осознанных переопределений одного вызова.

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
ENVIRONMENT_MAINTENANCE_PYTHON="$prerequisite_python" npm install --global --prefix "$prefix" --ignore-scripts=false --no-audit --no-fund "$archive"
"$prefix/bin/start-app" --version
sha256sum "$archive"
```

Версия снова2.1.0, digest архива прежний. Аналогично обновление устанавливает
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
