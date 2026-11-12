# Пакетная поставка npm

[Пошаговая инструкция установки и всех CLI-операций](#пошаговая-инструкция).

## Договор экземпляра

Версия 4.1.0 поставляется самостоятельным пакетом. Приложение устанавливает
выбранный tgz своей локальной npm-зависимостью и получает
`node_modules/.bin/start-app`. Отдельная глобальная установка в выбранный prefix
также поддерживается и предоставляет `bin/start-app`.
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
явно подготовленный import path. Оператор предоставляет собственный
`node_modules/.bin` либо выбранный `PREFIX/bin` через `PATH`.
Пользователь вызывает пакетную команду из каталога проекта. Другие экземпляры сохраняются.
[Постоянный профиль](persistent-entry.md#выбор-установки-и-рабочего-файла)
объясняет точное расположение `start-app.json` для обоих входов.

## Команды и полные аргументы

| Обычный вызов | Полный справочник и инструкция |
|---|---|
| `start-app --version`, `--help` | Версия/справка выбранной установки без действий |
| `start-app infra`, `deps` | [Подготовка ресурсов](resource-preparation.md#команды-и-аргументы) |
| `start-app adjust` | [Согласование](settings-alignment.md#входы-и-результаты) |
| `start-app check` | [Проверки](resource-checking.md#команды-и-аргументы) |
| `start-app run` | [Запуск процессов](process-launch.md#входы-и-аргументы) |
| `start-app stop`, `stop list`, `stop all` | [Сохранённые группы](process-launch.md#входы-и-аргументы) |

Пути, значения и выбор ресурсов берутся из постоянного профиля.
`--config`, `--parameters`, `--base-dir` и применимый `--requirements` доступны
как [необязательные переопределения](persistent-entry.md#переопределение-одного-вызова).
Полностью явная прежняя форма сохраняется. Npm-вход передаёт полные argv,
env/stdin/stdout/stderr и обычные/сигнальные исходы выбранного CLI.

[Общая опция `--output`](configuration.md#формат-json) выбирает компактный или форматированный JSON ответа. [Предупреждения аргументов](configuration.md#предупреждения-аргументов) выводятся в stderr сразу после разбора; неверный формат не отменяет допустимую операцию. Npm-вход сохраняет этот договор CLI.

Команды вызываются отдельно: `run` исполняет только объявленный запуск,
`check` — объявленные наблюдения. Команды, цепочки, шаблоны `string.Template`
и интерпретаторы принадлежат приложению; один читатель разрешает его документы.

## Библиотека и поставленные примеры

[Контекст и правильная подготовка](#пошаговая-инструкция).

Следующие технические API-примеры используют один подготовленный пакет.
Оператор задаёт значения один раз: `package_root` — установленный пакет,
`app_python` — его `.venv/bin/python`, `workspace` — существующий собственный
каталог данных; `prefix`, `archive`, `prerequisite_python` нужны для обслуживания
самой установки. Это контекст примеров API, а не обязательные параметры запуска.
Для локальной зависимости возьмите `package_root` и `app_python` из
[собственного npm-проекта](#собственная-зависимость-приложения).
Следующий блок показывает расположение именно глобального prefix-варианта.

```bash
package_root=/absolute/path/to/prefix/lib/node_modules/environment-maintenance
app_python="$package_root/.venv/bin/python"
workspace=/absolute/path/to/private-workspace
prefix=/absolute/path/to/prefix
archive=/absolute/path/to/environment-maintenance-4.1.0.tgz
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

### Собственная зависимость приложения

У каждого независимого приложения свой npm-проект инструментов, установленный
пакет и Python-окружение. Для приложения без корневого npm-проекта подходит
собственный `.tools/environment-maintenance` с сохранёнными manifest/lock/archive.
Installed node_modules/venv восстанавливаются из этой supply; каталог задачи или соседний checkout производителя
не заменяет её. Несколько регистраций одного приложения используют его экземпляр.

Подготовьте выбранный неизменяемый архив и перейдите в приложение:

```bash
cd /absolute/path/to/application
tools="$PWD/.tools/environment-maintenance"
mkdir -p "$tools/vendor"
cp /absolute/path/to/issued/environment-maintenance-4.1.0.tgz "$tools/vendor/"
sha256sum "$tools/vendor/environment-maintenance-4.1.0.tgz"
cd "$tools"
cat > package.json <<'JSON'
{
  "name": "application-environment-tools",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "environment-maintenance": "file:vendor/environment-maintenance-4.1.0.tgz"
  }
}
JSON
npm install --package-lock-only --ignore-scripts --offline --no-audit --no-fund
ENVIRONMENT_MAINTENANCE_PYTHON=/absolute/path/to/python3 npm ci --ignore-scripts=false --foreground-scripts --offline --no-audit --no-fund
npm ls --depth=0 --json
./node_modules/.bin/start-app --version
```

Перед установкой сравните SHA-256 с переданным владельцем выпуска. Digest относится к конкретному архиву и хранится в отдельной квитанции, а не внутри описываемого архива.
Сохраните `package.json`, созданный npm `package-lock.json` и выбранный архив
вместе с зависимостью приложения. Lock фиксирует `version: "4.1.0"`, локальный
`resolved` и `integrity` архива. Локальный `file:` нужен для выданного tgz;
публикация этой версии в реестре npm здесь не заявляется. Общий кеш загрузок
допустим, установленный пакет и его `.venv` принадлежат отдельному приложению.

`--offline` относится к npm. Pip отдельно получает зависимости из выбранного
индекса либо подготовленных колёс. Для автономной установки приложение выбирает доступный retained wheelhouse; при установке и восстановлении
передаются `PIP_NO_INDEX=1` и абсолютный `PIP_FIND_LINKS` этого каталога.

Проверьте собственный runtime, сохраняя основной Python приложения:

```bash
package_root="$tools/node_modules/environment-maintenance"
app_python="$package_root/.venv/bin/python"
"$app_python" -I -B -c 'import sys, importlib.metadata, environment_maintenance as em; assert em.__version__ == importlib.metadata.version("environment-maintenance") == "4.1.0"; print(sys.executable, sys.prefix, em.__file__)'
```

Python, sys.prefix и импортированный модуль должны находиться в собственном installed пакете приложения. Для обычного exit-code результата связывайте module `environment_maintenance.actions.interpreters` и attribute `exit_result` с явным options.accept. Production launcher — этот Python с `-I -B -m environment_maintenance.running.console`; Python payload приложения может быть другим. [Полный договор](process-launch.md#внешний-инструмент).

Примеры не копируются в site-packages как реализация. Custom callbacks хранит versioned приложение и предоставляет их import path. Предоставьте свой tools/node_modules/.bin в PATH; абсолютный entry сохраняет выбор main по cwd. Npm-проект инструментов и обслуживаемый проект могут находиться в разных каталогах.

Для восстановления выполните тот же `npm ci` из инструментального npm-проекта
с теми же входами и настройками pip. Он восстанавливает только его `node_modules`;
восстановите зависимости/import path своих versioned application handlers. При обновлении
сначала установите и проверьте выбранные байты, затем переключайте рабочие
указатели приложения. Проверьте его реальные вызовы и сохранность других
приложений. До успешной проверки сохраняйте прежнюю пригодную установку для
согласованного возврата. Одного изменения пути к общему экземпляру недостаточно
для поставки независимых зависимостей.

### Собрать и установить выбранный кандидат

Оператор выбирает точный source commit и каталог результата сборки:

```bash
npm pack --json --pack-destination /absolute/path/to/candidate
```

Передайте архив и его SHA-256. Установка выбранных байтов в отдельный prefix:

```bash
ENVIRONMENT_MAINTENANCE_PYTHON=/absolute/path/to/python3 npm install --global --prefix /absolute/path/to/prefix --ignore-scripts=false --no-audit --no-fund /absolute/path/to/environment-maintenance-4.1.0.tgz
/absolute/path/to/prefix/bin/start-app --version
npm root --global --prefix /absolute/path/to/prefix
```

Ожидаемая версия — `environment-maintenance 4.1.0`. Последняя команда показывает
корень npm-модулей; добавьте `environment-maintenance` для каталога пакета.
Предоставьте `PREFIX/bin` через `PATH` установленного окружения.
Идентифицируйте реальный source/tree/tgz digest, runtime и результаты проверки.
Публикация в реестре — отдельное действие, эта инструкция её не выполняет.

При offline-установке оператор предоставляет стандартные `PIP_NO_INDEX=1`
и `PIP_FIND_LINKS` с выбранными build/runtime колёсами. Проверочный wheelhouse
не является встроенным источником зависимостей продукта.

### Подготовить собственные конфиги

Следуйте [инструкции постоянного входа](persistent-entry.md#пошаговая-инструкция).
Приложение или настроенный владелец развёртывания создаёт рабочие main/parameters
и отдельные документы операций через свой конфиг. Примеры остаются в пакете;
рабочие копии хранятся в постоянной области приложения; секретные локальные значения исключает их владелец. Один и тот же пакетный вход используется во всех
проектах; их программные обёртки
не требуются. Подготовка готового обработчика в собственном runtime SDK — часть
однократной настройки; стандартный обработчик уже находится в установленном пакете.

### Исполнить шесть выбранных команд через короткий вход

В каталоге проекта с подготовленным `start-app.json`:

```bash
start-app infra
start-app deps
start-app adjust
start-app check
start-app run --env npm-demo
start-app stop --env npm-demo
```

Ожидаются успешные результаты объявленных приложением команд.
Учебный профиль и его точные события описаны у
[постоянного входа](persistent-entry.md#шесть-обычных-команд).
Из постороннего cwd укажите main проекта через необязательный `--config`.
Абсолютный пакетный вход выбирает runtime; обычный main по-прежнему определяется cwd.
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

Версия снова4.1.0, digest архива прежний. Аналогично обновление устанавливает
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

Для configured операций успех возвращает exit0, runtime failure — exit1, ошибка входа — exit2. Run при допустимом ENV сохраняет JSON с адресом/ошибками; исходы stop/list описаны [здесь](process-launch.md#результат-и-продолжение). Отказ собственной Python-обёртки и npm lifecycle имеют свою причину; читайте полные stdout/stderr. После partial effects продолжение определяет владелец [по receipt](migration-v4.md#ручное-восстановление).

Npm installation имеет
собственный ненулевой исход при ошибке lifecycle. Сигнальный исход Python
сохраняется как завершение тем же сигналом, включая PIPE/USR1; способ числового
представления оболочки определяется самой оболочкой. Обёртка не включает
отладчик вместо передачи USR1 и не подменяет PIPE обычным кодом2.

Перед осознанным продолжением смотрите полные результаты и уже совершённые
действия; внешние инструменты и оператор владеют предметным исправлением.
Публикация npm, Git tag/push и обновление существующих потребителей — отдельные
действия. Наличие локального кандидата их не выполняет.
