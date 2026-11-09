# Постоянный вход выбранной установки

[Пошаговая инструкция](#пошаговая-инструкция).

После однократной настройки из каталога приложения вызываются infra/deps/adjust/check/run. Stop читает общий сохранённый реестр и доступен без main.

## Выбор установки и рабочего файла

Оператор предоставляет собственный `node_modules/.bin/start-app` либо `PREFIX/bin/start-app` через PATH. Python/core принадлежат выбранному пакету; cwd выбирает обслуживаемый проект. Без `--config` main — `CWD/start-app.json`. Абсолютный пакетный entry сохраняет тот же договор. Полный [CLI reference](configuration.md#команды-и-аргументы).

Корневой entry исходного комплекта выбирает соседнюю installed `.venv` с `-I`; npm entry использует свой runtime с `-P -s -B`. Прикладные plugin modules доступны через явно подготовленный import path приложения. Встроенный exit-code interpreter доступен без examples.

## Поля постоянного профиля

[Заполнение](#пошаговая-инструкция).

```json
{
  "operations": {"run": "run.json"},
  "interpreters": {
    "exit": {"module": "environment_maintenance.actions.interpreters", "attribute": "exit_result"}
  },
  "invocation": {"parameters": "parameters.json", "base_dir": "."}
}
```

`operations` сопоставляет имена документов; `interpreters` — готовые объекты. Пути `invocation.parameters` и `invocation.base_dir` непустые и считаются от main. Полностью явный вызов указывает config/parameters/абсолютный base-dir и не требует invocation.

Infra/deps/adjust без CLI selection используют all в порядке документа. Для подмножества выберите уникальные IDs через `--requirements` либо согласованный состав документа. `invocation.requirements` не участвует в выборе. Run использует [APP/ENV формы](process-launch.md#входы-и-аргументы); check выбирает ресурсы по своему договору.

Рабочие конфиги и данные хранятся у приложения в постоянной области; versioned шаблоны и исходники инструментов остаются в Git. Секреты и заполненные локальные значения исключает их владелец. Disposable runtime не должен быть единственным источником конфигурации или реализации.

## Переопределение одного вызова

[Примеры](#необязательные-переопределения).

Явный ключ заменяет соответствующее значение только текущего вызова, не переписывая профиль. Config/parameters CLI paths считаются от cwd; base-dir абсолютный. Scalar parameters подставляются один раз стандартным string.Template. CLI неизвестные IDs предупреждает и пропускает; SDK read остаётся строгим. Повтор ID отвергает запрос до эффектов.

## Пошаговая инструкция

### Однократная подготовка оператором

Выберите `package_root`, его абсолютный `app_python`, собственный пустой `workspace` по [контексту npm](npm-distribution.md#библиотека-и-поставленные-примеры). Следующий блок создаёт учебный профиль в нём, не меняя шаблоны:

```bash
mkdir -p "$workspace/os-temp"
export TMPDIR="$workspace/os-temp"
"$app_python" -I -B - "$package_root" "$workspace" <<'PY'
import json
from pathlib import Path
import shutil
import sys
package, work = map(Path, sys.argv[1:])
source = package / 'examples/persistent-entry'
for name in ['infra', 'deps', 'adjust', 'check', 'run']:
    shutil.copyfile(source / (name + '.example.json'), work / (name + '.json'))
main = json.loads((source / 'start-app.example.json').read_text())
main['interpreters']['result']['module'] = 'environment_maintenance.actions.interpreters'
(work / 'start-app.json').write_text(json.dumps(main))
values = json.loads((source / 'parameters.example.json').read_text())
values.update(python=sys.executable,
    probe=str(package / 'examples/resource-preparation/probe.py'),
    events=str(work / 'events.jsonl'), stdout_log=str(work / 'run.stdout'),
    stderr_log=str(work / 'run.stderr'))
(work / 'parameters.json').write_text(json.dumps(values))
run = json.loads((work / 'run.json').read_text())
command = run['applications'][0]['commands'][0]
command['argv'] = ['${python}', '-I', '-B', '-m',
    'environment_maintenance.running.console', *command['argv'][2:]]
(work / 'run.json').write_text(json.dumps(run))
PY
```

Здесь probe — учебная команда обслуживаемого приложения; launcher и стандартный обработчик приходят из installed package. Production команды и данные предоставляет ваше приложение.

### Шесть обычных команд

Добавьте выбранный package bin в PATH. Из `workspace` с подготовленным main:

```bash
start-app infra
start-app deps
start-app adjust
start-app check
start-app run --env entry-demo
start-app stop --env entry-demo
```

У первых четырёх операций status=succeeded/exit0 и полные command results; `events.jsonl` показывает фактические вызовы probe. Run возвращает PGID переданной команды и файл ENV. Учебная команда быстро завершается: stop может удалить уже устаревшую запись без сигнала и сообщить «Ничего не остановлено.». Для живых HTTP/терминалов используйте [другой пример](process-launch.md#пошаговая-инструкция).

### Необязательные переопределения

Для ID `assets` учебного infra:

```bash
start-app infra --requirements '["assets"]'
start-app run list --config /absolute/path/to/project/start-app.json
```

`--parameters` и `--base-dir` при необходимости задают явные пути одного вызова. Для смены версии следуйте [migration](migration-v4.md#переход-конфигурации).

### Сохранение и новая поставка

Сохраните собственные конфиги/данные. Обновление зависимости само не переписывает их. Версия, lock/archive и выбранный профиль переключаются согласованно; другие экземпляры сохраняются. [Установка](npm-distribution.md#собственная-зависимость-приложения) и [диагностика](#результат-и-диагностика) имеют отдельные процедуры.

## Результат и диагностика

Прочитайте полный JSON и stderr. Известные CLI flags исполняются даже при предупреждении о неизвестных; ошибочный старый флаг не обеспечивает безопасную проверку без эффектов. Ошибку входа исправьте до нового вызова. После частичного запуска продолжайте по фактическим PGID/списку APP и [правилам восстановления](migration-v4.md#ручное-восстановление). Stop использует тот же OS temp, что run.
