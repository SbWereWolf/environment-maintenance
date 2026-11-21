#!/usr/bin/env bash
# Run with only loopback connectivity and an already seeded test npm registry.
set -euo pipefail
scope=${1:?local or global}
version=${2:?EM version}
endpoint=${3:?loopback npm URL}
outer=${4:?new evidence directory}
selected=${EM_PYTHON:?absolute Python 3.12}
helper=$(cd -- "$(dirname -- "$0")" && pwd)
[[ $endpoint == http://127.0.0.1:* && $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
test -z "$(ip route show default)"
mkdir -m 700 -- "$outer"
out=$(realpath -- "$outer")
prefix="$out/prefix"
cache="$out/npm-cache"
test ! -e "$prefix"
test ! -e "$cache"
test "$(node --version)" = v22.0.0
test "$(npm --cache "$out/version-cache" --version)" = 10.5.1
python_version=$("$selected" -I -B -c 'import platform; print(platform.python_version())')
[[ $python_version =~ ^3\.12\. ]]
export ENVIRONMENT_MAINTENANCE_PYTHON="$selected"
export PIP_CONFIG_FILE=/dev/null PIP_NO_CACHE_DIR=1
unset PIP_FIND_LINKS PIP_EXTRA_INDEX_URL PIP_INDEX_URL PIP_NO_INDEX PYTHONPATH PYTHONHOME
argv=(npm install --engine-strict --registry "$endpoint" --prefix "$prefix" --cache "$cache"
      --foreground-scripts --no-audit --no-fund --loglevel=http "environment-maintenance@$version")
case "$scope" in
  local) module_root="$prefix/node_modules"; cli="$module_root/.bin/start-app" ;;
  global) argv+=(--global); module_root="$prefix/lib/node_modules"; cli="$prefix/bin/start-app" ;;
  *) exit 2 ;;
esac
code=0
"${argv[@]}" > "$out/install.log" 2>&1 || code=$?
jq -n --arg node v22.0.0 --arg npm 10.5.1 --arg python "$python_version" --arg scope "$scope" \
  --argjson exit "$code" '{node:$node,npm:$npm,python:$python,scope:$scope,exit:$exit,
                         fresh_prefix:true,fresh_cache:true,argv:$ARGS.positional}' --args -- "${argv[@]}" > "$out/install.json"
test "$code" -eq 0
em="$module_root/environment-maintenance"
ce=$(node -p 'require.resolve("command-execution/package.json", {paths: [process.argv[1]]})' "$em")
ce="$(dirname -- "$ce")"
wheel="$ce/vendor/command_execution-2.0.10-py3-none-any.whl"
digest=$(sha256sum "$wheel" | cut -d' ' -f1)
venv="$em/.venv/bin/python"
"$venv" -I -B -m pip --isolated check > "$out/pip-check.log"
"$cli" --version > "$out/cli.log"
mkdir "$out/sdk"
"$venv" -I -B "$helper/installed-sdk.py" "$version" "$out/sdk" > "$out/sdk.log"
"$venv" -I -B - "$digest" > "$out/python.json" <<'PYTHON'
from importlib.metadata import version
import json
import sys
import command_execution as ce
import environment_maintenance as em

print(json.dumps({"python": sys.executable, "ce": version("command-execution"),
                  "em": version("environment-maintenance"), "ce_file": ce.__file__,
                  "em_file": em.__file__, "ce_wheel_sha256": sys.argv[1]}))
PYTHON
