# environment-maintenance 0.2.0

Самостоятельное приложение для проверки и обслуживания окружения по каталогу
`environment-maintenance/catalog/v2`. Пакет не импортирует `ai-poise`, не читает его
базу и не меняет его конфигурацию. Оператор явно выбирает один каталог v2 для каждого
запуска.

Требуется Python 3.11 или новее. Runtime-зависимостей нет.

## Запуск

Из корня исходников:

```bash
PYTHONPATH=src python3 -B -m environment_maintenance check \
  --catalog-dir examples/catalog-v2

PYTHONPATH=src python3 -B -m environment_maintenance run \
  --catalog-dir examples/catalog-v2

PYTHONPATH=src python3 -B -m environment_maintenance run \
  --catalog-dir examples/catalog-v2 \
  --dry-run
```

После установки дистрибутива те же операции доступны через команду
`environment-maintenance`. Поддерживаются только подкоманды `check` и `run`, а также
аргументы `--catalog-dir`, повторяемый `--values`, повторяемый `--set` и `--dry-run`.

`check` и `run --dry-run` никогда не вызывают `install` или `repair`. Обычный `run`
может выполнить ровно действие, выбранное состоянием проверки, после чего всегда
повторяет тот же `check`.

## Каталог v2

`--catalog-dir` указывает на существующий каталог, содержащий единственный манифест
`catalog.json`. Его верхний уровень имеет точные поля:

```json
{
  "schema": "environment-maintenance/catalog/v2",
  "parameters": {},
  "inherit_env": ["PATH"],
  "requirements": []
}
```

Неизвестные или отсутствующие поля, повторяющиеся JSON-ключи, неизвестная schema и
неверные типы отклоняются до запуска действий. Каждый элемент `requirements`
содержит уникальный `id` и три обязательных действия: `check`, `install`, `repair`.
Порядок массива является порядком выполнения.

Каждое действие задаётся всеми следующими полями:

```json
{
  "argv": ["python3", "probe.py", "check"],
  "cwd": ".",
  "env": {},
  "output": {
    "schema": "environment-maintenance/action-result/v2"
  },
  "max_output_bytes": 4096,
  "execution_bound_seconds": 5
}
```

`argv` передаётся процессу напрямую: shell не запускается и строка команды не
интерпретируется. Относительный `cwd` считается от выбранного каталога v2. Дочерний
процесс получает только переменные из `inherit_env`; значения из `action.env`
добавляются после allowlist и заменяют одноимённые унаследованные значения.

`max_output_bytes` ограничивает сохраняемый объём каждого потока stdout/stderr.
`execution_bound_seconds` ограничивает время действия. При превышении ограничения
процесс и его группа завершаются, а результат остаётся ошибкой протокола. Ограничение
вывода не является дисковой квотой и не превращает частичный вывод в успех.

## Параметры

Параметры имеют тип `string`, `integer`, `number` или `boolean`. Декларация может
содержать `default`, имя переменной `env` и флаг `secret`. Значения выбираются в
следующем порядке приоритета:

1. `default` из `catalog.json`;
2. JSON-объекты из повторяемых `--values` слева направо;
3. явно объявленная переменная `env`;
4. повторяемые `--set name=value`.

Неизвестные имена, дубли одного имени в `--set` и значения неверного типа
отклоняются до действий. Подстановка `${name}` выполняется один раз во всех полях
требований; полученное значение повторно как шаблон не интерпретируется.
`secret: true` скрывает значение параметра в публичном JSON-результате. Секреты не
следует передавать через CLI, поскольку argv процесса доступен операционной системе.

## Состояния и действия

Успешный `check` возвращает одно из четырёх состояний:

| Состояние | `check` и `run --dry-run` | `run` |
|---|---|---|
| `satisfied` | Итог `ready`, изменений нет | Итог `ready`, изменений нет |
| `missing` | Итог `action_required`, планируется `install` | `install`, затем тот же `check` |
| `invalid` | Итог `action_required`, планируется `repair` | `repair`, затем тот же `check` |
| `unavailable` | Причина и конкретные `recommendations`, изменений нет | Причина и конкретные `recommendations`, изменений нет |

Повторный `check` выполняется после каждой попытки `install` или `repair`, включая
неуспешную попытку. Успешное mutation-действие без последующего `satisfied` не
считается готовым окружением. Автоматических повторов, повышения привилегий и
необъявленных действий нет.

## Протокол действия

При exit code 0 stdout должен содержать ровно один UTF-8 JSON-объект заявленной
schema. Ответ `check` содержит точные поля `schema`, `requirement_id`, `action`,
`state`; для `unavailable` дополнительно обязательны непустая `cause` и непустой
массив непустых строк `recommendations`. Ответ `install` или `repair` содержит
`schema`, `requirement_id`, `action`, `outcome`, причём `outcome` равен `completed`.

Неверный exit code, лишние или пропущенные поля, несовпадающие ID/action/schema,
невалидный UTF-8/JSON, timeout и усечённый вывод дают `protocol_failure`. Запись
результата сохраняет `invocation`, exit code, stdout/stderr, `capture_complete`,
`timed_out` и диагностическое `error`; такой результат никогда не считается
доменным состоянием.

Итоговые коды процесса:

| Код | Результат |
|---|---|
| 0 | `ready` |
| 2 | `action_required` либо ошибка входного контракта |
| 3 | `unavailable` |
| 4 | `failed` |

Ошибка входного контракта печатается в stderr без запуска дочернего процесса.
Остальные итоги печатаются одним JSON-объектом в stdout.

## Отказ и восстановление

При `unavailable` оператор устраняет указанную `cause` по сохранённым
`recommendations` и повторяет команду. При `protocol_failure` нужно проверить
сохранённые `invocation`, `error`, `timed_out`, `capture_complete`, stdout/stderr и
исправить само объявленное действие или его протокол. Runner не угадывает исправление
и не повторяет побочный эффект автоматически.

Рабочий пример находится в `examples/catalog-v2`: один каталог, один `catalog.json`
и самостоятельный `probe.py`. Он всегда сообщает `satisfied` и не является профилем
развёртывания `ai-poise`.

## Проверки

Узкий исполняемый набор для catalog/v2:

```bash
PYTHONPATH=src python3 -B -m pytest -p no:cacheprovider -q \
  tests/test_v2_contract.py \
  tests/test_v2_engine.py \
  tests/test_v2_boundaries.py
```

Проверка документационного контракта:

```bash
PYTHONPATH=src python3 -B -m pytest -p no:cacheprovider -q \
  tests/test_v2_documentation.py
```

Форматы `requirements.json`, `repairs.json`, флаг `--repairs`, вторичный файл
маршрутизации и поле/режим `apply` не входят в v2 и не распознаются приложением.
