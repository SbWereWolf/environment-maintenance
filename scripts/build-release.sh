#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python=${RELEASE_PYTHON:-python3}
channel=${1:-both}
output=$(realpath -m -- "${2:-$repo/dist}")
cd "$repo"
ref=${RELEASE_REF:-$("$python" -I -c 'import tomllib; print("v" + tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')}
mkdir -p -- "$output"
case "$channel" in
  npm|pypi) "$python" -B .github/scripts/build-distribution.py "$channel" "$ref" "$output" ;;
  both)
    "$python" -B .github/scripts/build-distribution.py pypi "$ref" "$output"
    "$python" -B .github/scripts/build-distribution.py npm "$ref" "$output"
    ;;
  *) exit 2 ;;
esac
