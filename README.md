# environment-maintenance 5.1.1

English | [Русский](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/README.ru.md)

Prepare an application's runtime directory, install its declared dependencies, check resources, and manage its running processes using commands described in JSON. Your application defines what to run; `start-app` executes those declarations and returns structured results with exit codes and output.

Use it to give developers and automation the same explicit commands for preparing and running an application.

## Install

Requires Linux, Node.js 22+, npm 10+, and Python 3.11+ with venv and pip. In your application's npm project:

```bash
ENVIRONMENT_MAINTENANCE_PYTHON="$(command -v python3)" \
npm install --save-dev --save-exact --ignore-scripts=false environment-maintenance@5.1.1
```

npm creates the tool's own Python environment. Keep the dependency and generated lockfile with your application. See [installation options](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/installation.md) for prerequisites and offline installation.

## Quick example

This example ensures your application's `var` directory exists. Run it from the same directory where you installed the package:

```bash
cat > em.json <<'JSON'
{
  "operations": {"infra": "infra.json"},
  "interpreters": {
    "exit": {"module": "command_execution.actions.interpreters", "attribute": "exit_result"}
  }
}
JSON
cat > infra.json <<'JSON'
{
  "requirements": [{
    "id": "runtime-dir",
    "commands": [{
      "argv": ["mkdir", "-p", "var"],
      "cwd": ".",
      "env": {},
      "interpreter": {"name": "exit", "options": {"accept": [0]}}
    }]
  }]
}
JSON
printf '{}\n' > parameters.json
./node_modules/.bin/start-app infra --config em.json --parameters parameters.json \
  --base-dir "$PWD" --requirements '["runtime-dir"]'
test -d var && printf 'runtime directory ready\n'
```

The command returns JSON with `status: "succeeded"` and prints `runtime directory ready`. The directory is created by the declared `mkdir` command. You can run the operation again because `mkdir -p` accepts an existing directory.

Replace the command with your application's maintenance command; add named requirements to select individual resources. The [resource preparation guide](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/resource-preparation.md#%D0%BF%D0%BE%D0%B4%D0%B3%D0%BE%D1%82%D0%BE%D0%B2%D0%BA%D0%B0-%D1%80%D0%B5%D1%81%D1%83%D1%80%D1%81%D0%BE%D0%B2) explains checks, parameters, interpreters, and failure results.

## Commands

| Command | Purpose |
|---|---|
| `start-app infra` | Prepare declared infrastructure resources. |
| `start-app deps` | Prepare declared application dependencies. |
| `start-app adjust` | Apply declared command or network settings changes. |
| `start-app check` | Observe declared resource conditions. |
| `start-app run` | Launch selected named applications and record their process groups. |
| `start-app stop` | Stop recorded application process groups. |

Each operation is explicit. An application supplies its tools, parameters, working directories, and result interpreters. Named launches are recorded in the selected operating-system temporary directory; `stop` uses the saved registry without needing the current application configuration.

## Detailed documentation

The guides are in Russian; the bundled AI skill is in English.

- [All CLI commands and arguments](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/configuration.md#%D0%BA%D0%BE%D0%BC%D0%B0%D0%BD%D0%B4%D1%8B-%D0%B8-%D0%B0%D1%80%D0%B3%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D1%8B).
- [Persistent profile and one-call overrides](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/persistent-entry.md#%D0%BF%D0%BE%D0%BB%D1%8F-%D0%BF%D0%BE%D1%81%D1%82%D0%BE%D1%8F%D0%BD%D0%BD%D0%BE%D0%B3%D0%BE-%D0%BF%D1%80%D0%BE%D1%84%D0%B8%D0%BB%D1%8F).
- [Launching, listing, and stopping applications](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/process-launch.md#%D0%BF%D0%BE%D1%88%D0%B0%D0%B3%D0%BE%D0%B2%D0%B0%D1%8F-%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BA%D1%86%D0%B8%D1%8F).
- [Command planning, execution, and result interpreters](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/action-execution.md#%D0%BF%D1%83%D0%B1%D0%BB%D0%B8%D1%87%D0%BD%D1%8B%D0%B5-%D1%84%D1%83%D0%BD%D0%BA%D1%86%D0%B8%D0%B8-%D0%B8-%D0%B0%D1%80%D0%B3%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D1%8B).
- [Configuration reading](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/configuration-reading.md#%D0%BF%D1%83%D0%B1%D0%BB%D0%B8%D1%87%D0%BD%D1%8B%D0%B9-%D0%B4%D0%BE%D0%B3%D0%BE%D0%B2%D0%BE%D1%80) and [editing](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/configuration-editing.md#%D0%BF%D1%83%D0%B1%D0%BB%D0%B8%D1%87%D0%BD%D1%8B%D0%B9-%D0%B4%D0%BE%D0%B3%D0%BE%D0%B2%D0%BE%D1%80).
- [Dependency selection and compatible Python imports](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/command-package.md#%D1%81%D0%BE%D0%B2%D0%BC%D0%B5%D1%81%D1%82%D0%B8%D0%BC%D1%8B%D0%B5-%D0%B8%D0%BC%D0%BF%D0%BE%D1%80%D1%82%D1%8B).
- [npm installation, updating, and recovery](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/npm-distribution.md#%D0%BF%D0%B0%D0%BA%D0%B5%D1%82%D0%BD%D0%B0%D1%8F-%D0%BF%D0%BE%D1%81%D1%82%D0%B0%D0%B2%D0%BA%D0%B0-npm).
- [Configuration migration](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/migration-v5.md#%D0%BF%D0%B5%D1%80%D0%B5%D1%85%D0%BE%D0%B4-%D0%BA%D0%BE%D0%BD%D1%84%D0%B8%D0%B3%D1%83%D1%80%D0%B0%D1%86%D0%B8%D0%B8).
- [Bundled AI skill](https://github.com/SbWereWolf/environment-maintenance/blob/master/.agents/skills/environment-maintenance/SKILL.md).

JSON output is one line by default. Passing `--output` without a value enables pretty printing; see the [output reference](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/configuration.md#%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%82-json).

## Supported platform and checks

The supported platform is Linux with Node.js 22+, npm 10+, and Python 3.11+ with venv and pip. Each application pins and updates its own installation. [Development checks](https://github.com/SbWereWolf/environment-maintenance/blob/master/docs/development.md#%D0%BF%D1%80%D0%BE%D0%B2%D0%B5%D1%80%D0%BA%D0%B8) cover the CLI, installed npm package, and process lifecycle.
