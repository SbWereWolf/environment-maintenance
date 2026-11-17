#!/usr/bin/env bash
set -euo pipefail
cd -- "$1"
count=$2
shift 2
environment=()
for (( index=0; index<count; index++ )); do
    environment+=("$1")
    shift
done
exec env -i -- "${environment[@]}" "$@"
