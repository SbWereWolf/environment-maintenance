# environment-maintenance

[Руководство на русском](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/README.ru.md)

Run the maintenance commands declared by an application: prepare infrastructure
and dependencies, align settings, check resources, start applications and stop
their recorded process groups. Configuration supplies the commands, paths,
parameters and result interpreters.

`start-app` provides `infra`, `deps`, `adjust`, `check`, `run` and
`stop`. It works independently of ERP, Poise and their databases.
Requires Linux, Node.js 22+, npm 10+, and Python 3.11+ with venv/pip.

## Install

Select an available release and provide its exact Python dependencies:

```bash
ENVIRONMENT_MAINTENANCE_PYTHON=/usr/bin/python3.12 \
  npm install --global "environment-maintenance@${EM_VERSION:?Select an available release}"
```

npm prepares the package's private Python environment.
See [installation](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/installation.md)
for local dependencies, offline packages and runtime selection.

<a id="quickstart"></a>
## Quickstart: check a declared condition

This complete example uses a temporary configuration. It starts no service.

```bash
em_demo_dir="$(mktemp -d -t em-demo-XXXXXX)"
cat > "$em_demo_dir/app.json" <<'JSON'
{
  "operations": {"infra":"empty.json","deps":"empty.json","check":"check.json"},
  "interpreters": {"exit":{"module":"environment_maintenance.actions.interpreters","attribute":"exit_result"}}
}
JSON
printf '%s\n' '{"requirements":[]}' > "$em_demo_dir/empty.json"
printf '%s\n' '{}' > "$em_demo_dir/values.json"
cat > "$em_demo_dir/check.json" <<'JSON'
{"requirements":[{"id":"ready","commands":[{
  "argv":["printf","ready"],"cwd":".","env":{},
  "interpreter":{"name":"exit","options":{"accept":[0]}}
}]}]}
JSON
start-app check --config "$em_demo_dir/app.json" \
  --parameters "$em_demo_dir/values.json" --base-dir "$em_demo_dir"
```

Expect exit 0 and JSON with `operation: "check"`, `status: "succeeded"`,
and a successful `ready` entry in `checks`. Its command retains the actual
exit code and encoded stdout. Change the declared command or interpreter to
check your own condition. `check` reports observations; it does not repair them.

<a id="usage"></a>
## Use your application's configuration

A persistent profile selects config/parameters/base paths. Fully explicit flags
as above override that selection. Start/stop use the IDs declared by your app:

```bash
start-app run list
start-app run --env dev --app web
start-app stop list --env dev
start-app stop --env dev --app web
```

These commands require your configured `dev`/`web` entries.
The [complete launch example](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/process-launch.md#пошаговая-инструкция)
provides its own configuration. Stop reads recorded process groups; it does not
guess a target from the current directory.

<a id="documentation"></a>
## Documentation

- [CLI configuration and arguments (Russian)](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/configuration.md#команды-и-аргументы)
- [Shared core and current Python imports](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/command-package.md#current-imports)
- [Actions and data-flow chains (Russian)](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/action-execution.md#библиотека-исполнения)
- [Persistent profile (Russian)](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/persistent-entry.md)
- [Preparation and checks (Russian)](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/resource-checking.md)
- [npm dependency installation](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/npm-distribution.md)
- [Development and verification (Russian)](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/development.md)

<a id="проверки"></a>
## Verification

Use the selected installed package and its own Python. JSON defaults to one line;
`--output` selects formatting. Configuration-file operations do not run declared
commands. Generic JSON/list/parameter/command mechanics come from the exact
`command-execution` dependency; EM owns application configuration and Unix
scripts. See the shared-core guide for the distinction between these APIs.
