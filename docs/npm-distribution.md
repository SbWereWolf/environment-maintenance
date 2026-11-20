<a id="пакетная-поставка-npm"></a>
# npm installation and application dependency

<a id="договор-экземпляра"></a>
## Installation contract

Use Linux, Node.js22+, npm10+, and an absolute Python3.11+ with venv/pip.
`ENVIRONMENT_MAINTENANCE_PYTHON` selects the installation interpreter.
npm lifecycle creates the package's private `.venv`; pip resolves its exact
declared CE dependency and build/runtime requirements. Provide a suitable index
or complete offline wheelhouse. Installation does not prepare external app resources.

The selected package supplies source, docs, examples and its AI skill.
Application config, working values and tools remain caller-owned.
A package command uses its own private Python and preserves caller cwd;
[profile selection](persistent-entry.md#выбор-установки-и-рабочего-файла)
determines default config paths.

<a id="команды-и-полные-аргументы"></a>
## Commands

| Command | Reference |
|---|---|
| infra, deps | [Resource preparation](resource-preparation.md#команды-и-аргументы) |
| adjust | [Settings](settings-alignment.md#входы-и-результаты) |
| check | [Resource checks](resource-checking.md#команды-и-аргументы) |
| run, run list | [Launch](process-launch.md#входы-и-аргументы) |
| stop, stop list, stop all | [Recorded groups](process-launch.md#входы-и-аргументы) |

The [CLI reference](configuration.md#команды-и-аргументы) describes full arguments
and output. Config/parameters/base-dir overrides are explicit; ordinary calls
may use a [persistent profile](persistent-entry.md).
[Application action/chain functions](action-execution.md#цепочки-с-передачей-данных)
are imported from environment_maintenance; generic CE2 classes are separate.

<a id="библиотека-и-поставленные-примеры"></a>
## Installed Python and examples

For a local npm dependency, `package_root` is your tools project's
`node_modules/environment-maintenance`; `app_python` is
`$package_root/.venv/bin/python`. A global prefix normally uses
`PREFIX/lib/node_modules/environment-maintenance`.

[Shared-core/current imports](command-package.md#current-imports) and
[action examples](action-execution.md#пошаговая-инструкция) specify the actual
API. Use the selected installed environment, not a sibling source checkout.
Examples explicitly using PYTHONPATH select their packaged source and do not
prove an unrelated installed origin.

<a id="пошаговая-инструкция"></a>
## Installation procedure

<a id="собственная-зависимость-приложения"></a>
### Own application dependency

Select an available release in `EM_VERSION`. From your application's directory:

```bash
tools="$PWD/.tools/environment-maintenance"
mkdir -p "$tools"
cd "$tools"
npm init --yes
ENVIRONMENT_MAINTENANCE_PYTHON=/usr/bin/python3.12 \
  npm install --save-exact "environment-maintenance@${EM_VERSION:?Select an available release}"
./node_modules/.bin/start-app --version
```

Keep package.json and the npm-generated lock under your application's version
control. Restore with npm ci and the same installation Python/dependency supply.
Do not commit node_modules or private environments.
Several registrations can share one tool installation; independent copies
are selected/updated independently.

For offline pip, set PIP_NO_INDEX=1 and PIP_FIND_LINKS to the complete wheelhouse
for the selected package. npm still needs its own selected package supply/cache.

<a id="собрать-и-установить-выбранный-кандидат"></a>
### Isolated local candidate

To check source before release, the delivery owner can npm pack into its own
output directory and install that exact tgz in an isolated prefix with lifecycle
enabled. Inspect source/archive/installed bytes and hashes. This is verification,
not registry publication or deployment. Never overwrite an occupied artifact
version with changed bytes. See [development](development.md#локальный-npm-кандидат).

<a id="подготовить-собственные-конфиги"></a>
### Own configuration

Copy appropriate packaged examples into your application's permanent configuration
area, choose real paths/parameters/interpreters and keep local secrets out of Git.
The [README quickstart](../README.md#quickstart) creates complete temporary check
files. A configured [profile](persistent-entry.md#поля-постоянного-профиля)
supports ordinary calls without repeated path arguments.

<a id="исполнить-шесть-выбранных-команд-через-короткий-вход"></a>
### Execute declared operations

From the app with its profile:

```bash
start-app infra
start-app deps
start-app adjust
start-app check
start-app run --env dev
start-app stop --env dev
```

These are separate explicit actions, using your declared resources/environment.
The [profile example](persistent-entry.md#шесть-обычных-команд) supplies a complete
demonstration. A check does not silently run repair; a run does not invent tests.

<a id="прочитать-и-изменить-конфиг-через-установленную-библиотеку"></a>
### Read/edit through the installed API

The [configuration and bytes example](command-package.md#пример-конфигурации-и-команды)
creates its own files and exercises actual read/add/update APIs. Full
[reading](configuration-reading.md#пошаговая-инструкция) and
[editing](configuration-editing.md#пошаговая-инструкция) references cover IDs,
batch selection, delete and clear. No declared command runs during a file edit.

<a id="удалить-и-повторно-установить-те-же-байты"></a>
### Restore an installation

Keep the selected manifest/lock and dependency supply. In the same tools project,
use npm ci with the selected Python and available exact CE dependency to recreate
node_modules/private runtime. Preserve application data/config first.
[Runtime recovery](installation.md#пути-и-обновление) describes the owner boundary.

<a id="публичная-версия-и-обновление-потребителей"></a>
## Publication and consumer update

GitHub Actions publishes the Python wheel and the npm package from an
annotated `vMAJOR.MINOR.PATCH` tag. Its version must match `package.json` and
`pyproject.toml`. Configure Trusted Publishers for `publish.yml` with the
`pypi` and `npm` GitHub environments. Publish the pinned CE version to PyPI
before releasing EM.

From the approved release branch, push the branch and tag in one operation:

```bash
tag=v5.3.9
branch=$(git symbolic-ref --short HEAD)
commit="${APPROVED_COMMIT:?Set the approved commit}"
git tag -a "$tag" "$commit" -m "Release $tag" &&
git push --atomic origin "$commit:refs/heads/$branch" "refs/tags/$tag:refs/tags/$tag"
npm view environment-maintenance@5.3.9 version dist.integrity
```

The workflow runs the release checks and verifies the PyPI wheel hash and npm
integrity against the built artifacts. It waits up to 25 minutes for npm to
make a new upload public. An identical published npm archive is accepted
without a second upload.

Application owners update only from the npm registry. Select the published
version with `npm install --save-exact "environment-maintenance@$VERSION"`,
commit the manifest and npm-generated lock together, then restore that selection
with `npm ci`. The install hook resolves CE from PyPI. Local archives and Git
checkouts are inputs for development and isolated candidate checks.

Intermediate bugfix versions remain distinct verification artifacts. Perform
final consumer dependency update/integration once after shared-core readiness.
Validate the actual installed version/origin/private Python and a nonempty
declared operation for each independent installation.

<a id="диагностика-и-правильное-продолжение"></a>
## Errors and continuation

Read actual npm/venv/pip stdout/stderr. Supply a valid Python, writable prefix and
available declared dependencies, then intentionally retry installation.
Runtime preparation belongs to install, not an implicit repair inside an ordinary
start-app operation.

Configured operations exit0 on success,1 on runtime failure,2 on invalid input;
[run/stop outcomes](process-launch.md#результат-и-продолжение) keep their specific
contracts. Python signal completion remains a signal at the npm boundary.
Preserve partial effects and observe actual state before a retry; publication,
source delivery and adoption remain separately observed operations.
