#!/usr/bin/env bash
# Run inside the same loopback-only namespace as the selected devpi index.
set -euo pipefail
version=${1:?EM version}
index=${2:?loopback simple index}
outer=${3:?new evidence directory}
selected=${EM_PYTHON:?absolute Python 3.12}
oracle=${EM_SDK_ORACLE_WHEEL:?verified packaging wheel for the test}
helper=$(cd -- "$(dirname -- "$0")" && pwd)
[[ $index == http://127.0.0.1:*/+simple/ && $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
test -z "$(ip route show default)"
mkdir -m 700 -- "$outer"
out=$(realpath -- "$outer")
prefix="$out/venv"
"$selected" -m venv "$prefix"
venv="$prefix/bin/python"
export PIP_CONFIG_FILE=/dev/null
argv=("$venv" -m pip install --isolated --no-cache-dir --disable-pip-version-check --index-url "$index"
      --report "$out/resolution.json" "environment-maintenance==$version")
code=0
env -i PATH=/usr/bin:/bin HOME="$out" LC_ALL=C PIP_CONFIG_FILE=/dev/null \
  "${argv[@]}" > "$out/install.log" 2>&1 || code=$?
jq -n --arg prefix "$prefix" --argjson exit "$code" \
  '{prefix:$prefix,exit:$exit,fresh_prefix:true,fresh_cache:true,argv:$ARGS.positional}' --args -- "${argv[@]}" > "$out/install.json"
test "$code" -eq 0
"$venv" -I -B -m pip --isolated check > "$out/pip-check.log"
"$venv" -I -B -m pip --isolated install --no-index --no-deps "$oracle" > "$out/oracle.log"
"$prefix/bin/start-app" --version > "$out/cli.log"
mkdir "$out/sdk"
"$venv" -I -B "$helper/installed-sdk.py" "$version" "$out/sdk" > "$out/sdk.log"
"$venv" -I -B - > "$out/python.json" <<'PYTHON'
from importlib.metadata import version
import json
import sys
import command_execution as ce
import environment_maintenance as em
print(json.dumps({"python": sys.executable, "em": version("environment-maintenance"),
                  "ce": version("command-execution"), "em_file": em.__file__, "ce_file": ce.__file__}))
PYTHON
