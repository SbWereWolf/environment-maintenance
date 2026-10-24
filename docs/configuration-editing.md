# Изменение требований конфигурации

## Библиотека записи

[Пошаговая инструкция всех операций](#пошаговая-инструкция).

Интерфейс доступен собственному Python npm-поставки 2.0.0. Зависимости
устанавливает её pip. [Общий контекст примеров](npm-distribution.md#библиотека-и-поставленные-примеры)
позволяет использовать поставленные исходники и примеры внутри того же экземпляра.
Ни установка кандидата, ни вызовы API не обновляют другие экземпляры 1.0.0.

Библиотека изменяет конфиги внешних инструментов. Содержимое команд является
непрозрачными данными: сохранение команд не выполняет их и не рендерит placeholders.
Действующий [CLI обслуживания каталога](configuration.md#команды-и-аргументы)
и реализованная [библиотека исполнения](action-execution.md#библиотека-исполнения)
имеют отдельные договоры. [Инструкция исполнителя](action-execution.md#пошаговая-инструкция)
показывает явный вызов после чтения данных; сама запись команд их не запускает.

## Публичный договор

Импортируйте функции из `environment_maintenance`:

| Функция | Действие |
|---|---|
| `add_requirement(config_path, operation, requirement)` | Добавляет один полный объект в конец списка |
| `update_requirement(config_path, operation, identifier, changes)` | Меняет выбранные сведения одного существующего объекта |
| `delete_requirement(config_path, operation, identifier)` | Удаляет объект с выбранным ID |
| `clear_requirements(config_path, operation)` | Явно очищает весь список требований |

Все четыре функции возвращают `None` после успешного сохранения. Для получения
объектов используйте [пакетное чтение](configuration-reading.md#публичный-договор):
список выдаёт только IDs, массив IDs выбирает полные объекты, `"all"` — весь список.

Аргументы:

- `config_path`: строка либо `pathlib.Path` главного JSON-файла.
- `operation`: имя из `operations` главного файла. Для `infra`, `deps` и любого
  другого объявленного имени применяется одна схема и один механизм выбора.
- `requirement`: полный JSON-совместимый `dict`, включая непустой уникальный
  строковый `id`; остальные поля принадлежат внешнему инструменту.
- `identifier`: существующий строковый ID изменяемого или удаляемого объекта.
- `changes`: список объектов изменения по описанным ниже правилам.

Общая [схема файлов](configuration-reading.md#формат-конфигов) остаётся единой.
Относительный путь выбранного документа считается от каталога главного файла;
абсолютный путь используется непосредственно. Каждый вызов заново читает оба
файла. Главный файл и выбранный документ уже существуют. Для записи подготовьте
доступ к выбранному файлу и его каталогу: публикация создаёт временный файл рядом.
Рабочие конфиги исключаются из Git их владельцем, примеры заполнения отслеживаются.

### Изменения выбранных сведений

`changes` — последовательность операций стандартного JSON Patch (RFC 6902),
в данном API поддержаны `add`, `replace`, `remove`. Поля операции:

| Поле | Смысл |
|---|---|
| `op` | Одно из трёх поддержанных имён |
| `path` | JSON Pointer (RFC 6901) относительно выбранного требования |
| `value` | JSON-значение для `add` и `replace`, включая явный `null` |

`add` задаёт поле объекта либо вставляет элемент массива; `replace` заменяет
существующее значение; `remove` удаляет существующее поле или элемент массива.
Применяется готовый стандартный обработчик `jsonpatch`/`jsonpointer`.
Дополнительные члены объекта операции игнорируются по стандартному договору.

Указатель `/commands/0/argv/1` обращается к аргументу первой команды.
`/commands/-` добавляет в конец массива; числовой индекс при `add` вставляет
перед элементом, а индекс, равный длине, добавляет в конец. В ключах `/`
записывается как `~1`, `~` — как `~0`. Путь `/` выбирает пустой ключ;
пустой путь `""` выбирает весь объект требования.

Изменения применяются последовательно к локальной копии. В конце проверяется
полный объект и уникальность его ID среди остальных требований. Поэтому можно
переименовать ID, заменить весь объект или удалить и вновь добавить `id` в одном
запросе, сохранив конечный корректный объект. Позиция требования остаётся прежней;
после переименования последующие обращения используют новый ID.
Пустой `changes` сохраняет те же данные. Переданные объекты не изменяются.

### Сохранение данных

Добавление, изменение, удаление и очистка сохраняют все данные за пределами
запроса, включая дополнительные поля документа и неизвестные поля требований.
Порядок оставшихся требований и элементов массивов сохраняется. Очистка оставляет
пустой `requirements`, а не удаляет документ; повторная очистка допустима.
JSON `null`, удалённое поле, `false` и `0` сохраняют свои различные значения.

Сохранность выбранного JSON означает сохранность данных, а не форматирования
или порядка ключей объектов. Главный и соседние файлы остаются побайтно прежними.
Файловый адаптер сначала готовит полный JSON, затем публикует его заменой одного
файла из того же каталога, сохраняя обычные права доступа. Согласуйте одного
владельца записи: это не многодокументная или конкурентная транзакция.

## Пошаговая инструкция

Из корня выбранного checkout с этим API задайте фактический подготовленный Python:

```bash
: "${app_python:?Выберите Python по npm-инструкции или подготовке разработчика}"
```

Это runtime-зависимости текущего `pyproject.toml`; их разрешает пакетный менеджер
`pip`. Команда не переустанавливает приложение. Подготовка нового dev-окружения
описана в [руководстве разработчика](development.md#подготовка).
Каждая команда ниже явно использует `src` текущей рабочей копии через `PYTHONPATH`.
PostgreSQL, Redis и Composer для примеров не запускаются.

### Добавить, изменить, удалить и очистить

Сценарий копирует отслеживаемые примеры в собственный временный каталог, добавляет
демонстрационные metadata и проверяет каждую операцию. Исходные примеры и рабочие
конфиги остаются неизменными. Все действия выполняются одним вызовом:

```bash
PYTHONPATH=src "$app_python" -B - <<'PY'
import json
from copy import deepcopy
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory
from environment_maintenance import (
    add_requirement, update_requirement, delete_requirement, clear_requirements,
    list_requirement_ids, read_requirements,
)

with TemporaryDirectory(prefix="editing-example-", dir=".") as temporary:
    root = Path(temporary)
    for source in Path("examples/configuration-reading").glob("*.example.json"):
        copy2(source, root / source.name)
    main = root / "app.example.json"
    selected = root / "infra.example.json"
    original = json.loads(selected.read_text(encoding="utf-8"))
    original["metadata"] = {"owner": "example", "enabled": False, "attempts": 0}
    selected.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    main_before = main.read_bytes()
    deps_before = (root / "deps.example.json").read_bytes()

    # Добавление полного объекта с цепочкой непрозрачных команд.
    added = {"id": "assets", "label": "Сборка", "commands": [["composer", "install"]]}
    input_before = deepcopy(added)
    assert add_requirement(main, "infra", added) is None
    assert added == input_before
    assert list_requirement_ids(main, "infra") == ["postgres", "redis", "assets"]
    assert read_requirements(main, "infra", ["assets"]) == [input_before]
    print("add: postgres, redis, assets; полный объект сохранён")

    # Точечная замена, вставка команды, append, null и удаление поля.
    changes = [{"op": "replace", "path": "/commands/0/1", "value": "update"}]
    changes_before = deepcopy(changes)
    assert update_requirement(main, "infra", "assets", changes) is None
    assert changes == changes_before
    update_requirement(main, "infra", "assets", [
        {"op": "add", "path": "/commands/1", "value": ["composer", "dump-autoload"]},
    ])
    update_requirement(main, "infra", "assets", [
        {"op": "add", "path": "/commands/-", "value": ["echo", "${mode}"]},
    ])
    update_requirement(main, "infra", "assets", [{"op": "add", "path": "/note", "value": None}])
    update_requirement(main, "infra", "assets", [{"op": "remove", "path": "/label"}])
    changed = read_requirements(main, "infra", ["assets"])[0]
    assert set(changed) == {"id", "commands", "note"}
    assert changed["id"] == "assets"
    assert changed["commands"] == [
        ["composer", "update"], ["composer", "dump-autoload"], ["echo", "${mode}"],
    ]
    assert changed["note"] is None
    assert read_requirements(main, "infra", ["postgres", "redis"]) == original["requirements"]
    print("update: команды изменены, note=null, label удалён; остальные данные прежние")

    assert delete_requirement(main, "infra", "assets") is None
    assert list_requirement_ids(main, "infra") == ["postgres", "redis"]
    assert read_requirements(main, "infra", "all") == original["requirements"]
    print("delete: postgres, redis")

    assert clear_requirements(main, "infra") is None
    assert clear_requirements(main, "infra") is None
    assert list_requirement_ids(main, "infra") == []
    assert read_requirements(main, "infra", "all") == []
    final = json.loads(selected.read_text(encoding="utf-8"))
    assert final == {"requirements": [], "metadata": original["metadata"]}
    assert final["metadata"]["enabled"] is False
    assert type(final["metadata"]["attempts"]) is int
    assert main.read_bytes() == main_before
    assert (root / "deps.example.json").read_bytes() == deps_before
    print("clear: []; metadata, главный и соседний файлы сохранены")
PY
```

Ожидаются четыре напечатанные строки `add`, `update`, `delete`, `clear`, код 0
и отсутствие ошибок assertions. Временный каталог удаляется при выходе из блока.
Для записи в `deps` передайте это имя операции с той же схемой вызова;
пример выбора другого документа есть в
[инструкции чтения](configuration-reading.md#выбрать-другой-конфиг).

### Указатели, переименование и замена полного объекта

Самостоятельный пример использует копии тех же файлов. Он показывает экранированные
ключи, пустой ключ, различие удаления и null, переименование с проверкой конечного
объекта, пустой список изменений и замену корня требования:

```bash
PYTHONPATH=src "$app_python" -B - <<'PY'
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory
from environment_maintenance import add_requirement, update_requirement, read_requirements

with TemporaryDirectory(prefix="pointer-example-", dir=".") as temporary:
    root = Path(temporary)
    for source in Path("examples/configuration-reading").glob("*.example.json"):
        copy2(source, root / source.name)
    main = root / "app.example.json"
    add_requirement(main, "deps", {"id": "keys", "a/b": {"~": 1}, "": False})
    update_requirement(main, "deps", "keys", [
        {"op": "replace", "path": "/a~1b/~0", "value": 2, "comment": "ignored"},
    ])
    update_requirement(main, "deps", "keys", [{"op": "replace", "path": "/", "value": 0}])
    update_requirement(main, "deps", "keys", [{"op": "add", "path": "/note", "value": None}])
    update_requirement(main, "deps", "keys", [
        {"op": "remove", "path": "/id"}, {"op": "add", "path": "/id", "value": "renamed"},
    ])
    renamed = read_requirements(main, "deps", ["renamed"])[0]
    assert renamed == {"id": "renamed", "a/b": {"~": 2}, "": 0, "note": None}
    assert type(renamed[""]) is int
    update_requirement(main, "deps", "renamed", [{"op": "remove", "path": "/note"}])
    assert "note" not in read_requirements(main, "deps", ["renamed"])[0]
    before_noop = read_requirements(main, "deps", ["renamed"])
    update_requirement(main, "deps", "renamed", [])
    assert read_requirements(main, "deps", ["renamed"]) == before_noop
    replacement = {"id": "final", "commands": [], "enabled": False}
    update_requirement(main, "deps", "renamed", [
        {"op": "replace", "path": "", "value": replacement},
    ])
    assert read_requirements(main, "deps", ["final"]) == [replacement]
    print("pointers: escape, пустой ключ, rename, remove/null, no-op, root — проверены")
PY
```

Ожидается строка `pointers: ...`, код 0. Новый ID становится адресом последующих
вызовов; пустой ключ и корень были двумя разными адресами.

## Диагностика и повторный вызов

[Правильные пошаговые операции](#пошаговая-инструкция).

Обычные ошибки входа, JSON, выбранного документа, ID, изменения или файловой
публикации представлены `ValueError` с контекстом пути/операции/ID/элемента
`changes`. Исходное исключение сохраняется причиной. Некорректное изменение,
включая ошибку поздней операции, не сохраняет частичный результат.

Прочитайте диагностику, сверьте указанные данные с договором и обеспечьте нужный
доступ к файлу и каталогу внешним инструментом. Сохраните корректный вход и
осознанно повторите вызов: библиотека заново читает документы. Сама библиотека
не исправляет среду и не повторяет запись автоматически.

## Собственный внешний инструмент

[Пошаговые примеры публичной библиотеки](#пошаговая-инструкция).

[Полный корректный сценарий](#добавить-изменить-удалить-и-очистить) показывает
использование библиотеки внутри внешнего инструмента.
Если существующие инструменты не обеспечивают требуемого поведения, разработайте
собственный. Получайте IDs, читайте нужные полные объекты пакетно, передавайте
выбранный объект или точечный `changes` и подтверждайте результат новым чтением.
Полный конфиг для точечного изменения передавать не требуется.
