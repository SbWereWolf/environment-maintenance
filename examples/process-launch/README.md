# Пример запуска процессов

[Каноническая инструкция](../../docs/process-launch.md#пошаговая-инструкция) показывает рабочие копии, named run/list/stop и наблюдение двух HTTP-сервисов.

- `app.example.json` — mapping run и учебного обработчика.
- `run.example.json` — applications с двумя командами терминала/HTTP.
- `parameters.example.json` — значения для заполнения в своей копии.
- `start_console.py` — тонкая example delegation к установленному `environment_maintenance.running.console`; [аргументы и результат](../../docs/process-launch.md#внешний-инструмент).

Рабочая инструкция материализует main со стандартным package interpreter и module entry. Шаблоны остаются неизменными. Собственные logs, временный registry и процессы принадлежат эксперименту и убираются после подтверждения closure. PGID/передача запуска, видимость окна и HTTP готовность наблюдаются отдельно.
