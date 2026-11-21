#!/usr/bin/env bash
# Qualification publishes only to isolated, disposable loopback registries.
set -euo pipefail

repo=$(git rev-parse --show-toplevel)
cd "$repo"
helpers="$repo/tests/release"
driver="$repo/.github/scripts/release-channel.sh"
stage=${1:?qualification stage}
channel=${2:?release channel}
out=${3:?output directory}
tag=${4:?version tag}
artifact=${5:?filename}
version=${tag#v}
ce_tarball=command-execution-2.0.10.tgz
ce_wheel=command_execution-2.0.10-py3-none-any.whl
oracle=packaging-26.3-py3-none-any.whl
node_archive=node-v22.0.0-linux-x64.tar.xz
node_hash=9122e50f2642afd5f6078cafd1f52ede60fc464284384f05c18a04d13d07ae5a

capture() {
  "$EM_PYTHON" -B "$helpers/capture-release.py" "$channel" "$1" "$out/report/operation.log" -- "${@:2}"
}

if [[ $stage == inside ]]; then
  candidate=$(bash "$driver" artifact "$channel" "$out/candidate")
  test "$candidate" = "$out/candidate/$artifact"
  report="$out/report"
  mkdir "$report/download"
  if [[ $channel == npm ]]; then
    endpoint="$CE_NPM_REGISTRY"
    if [[ -z $CE_REGISTRY_UNAVAILABLE ]]; then
      npm publish "$EM_QUALIFICATION_INPUTS/$ce_tarball" --registry "$endpoint" --ignore-scripts --access public
    fi
    capture "$endpoint" npm publish "$candidate" --registry "$endpoint" --ignore-scripts --access public \
      --fetch-retries=0 --fetch-timeout=5000
    curl -fsS "${endpoint}environment-maintenance/$version" > "$report/dist.json"
    address=$(jq -er '.dist.tarball' "$report/dist.json")
    [[ $address == "$endpoint"* ]]
    curl -fsS "$address" > "$report/download/$artifact"
    cmp "$candidate" "$report/download/$artifact"
    jq -er '.dist.integrity' "$report/dist.json" > "$report/registry-digest.txt"
    for scope in local global; do
      PATH="$EM_NODE22_BIN:$PATH" bash "$helpers/strict-install.sh" "$scope" "$version" "$endpoint" "$out/strict-$scope"
      mkdir "$report/$scope"
      cp "$out/strict-$scope/"{install.json,install.log,pip-check.log,cli.log,sdk.log,python.json} "$report/$scope/"
    done
    cp "$out/strict-local/prefix/package-lock.json" "$report/local/"
    "$EM_PYTHON" -B .github/scripts/verify-distribution.py registry npm "$RELEASE_PACKAGE" "$version" "$candidate" \
      --registry "$endpoint" | tee "$report/registry-replay.log"
    grep -qx already-published "$report/registry-replay.log"
    mkdir "$out/conflict"
    cp "$candidate" "$out/conflict/$artifact"
    printf 'conflicting bytes\n' >> "$out/conflict/$artifact"
    if "$EM_PYTHON" -B .github/scripts/verify-distribution.py registry npm "$RELEASE_PACKAGE" "$version" \
        "$out/conflict/$artifact" --registry "$endpoint" > "$report/registry-conflict.log" 2>&1; then
      exit 1
    fi
    grep -F 'published bytes differ' "$report/registry-conflict.log"
  else
    endpoint="$CE_PYPI_UPLOAD"
    if [[ -z $CE_REGISTRY_UNAVAILABLE ]]; then
      "$CE_TWINE" upload --repository-url "$endpoint" --disable-progress-bar \
        "$EM_QUALIFICATION_INPUTS/$ce_wheel" "$EM_QUALIFICATION_INPUTS"/json{patch,pointer}-*.whl
    fi
    capture "$endpoint" "$CE_TWINE" upload --repository-url "$endpoint" --disable-progress-bar "$candidate"
    EM_SDK_ORACLE_WHEEL="$EM_QUALIFICATION_INPUTS/$oracle" \
      bash "$helpers/python-install.sh" "$version" "$CE_PYPI_SIMPLE" "$out/python-install"
    mkdir "$report/python"
    cp "$out/python-install/"{install.json,install.log,pip-check.log,cli.log,sdk.log,python.json,resolution.json} "$report/python/"
    address=$(jq -er '.install[] | select(.metadata.name == "environment-maintenance") | .download_info.url' \
      "$report/python/resolution.json")
    [[ $address == "$endpoint"* ]]
    curl -fsS "$address" > "$report/download/$artifact"
    cmp "$candidate" "$report/download/$artifact"
    jq -er '.install[] | select(.metadata.name == "environment-maintenance") | .download_info.archive_info.hashes.sha256' \
      "$report/python/resolution.json" > "$report/registry-digest.txt"
  fi
  exit
fi

mkdir -p "$out"
export EM_PYTHON EM_QUALIFICATION_INPUTS EM_PYPI_BUILD_INPUTS CE_REGISTRY_UNAVAILABLE
EM_PYTHON=$(command -v "${RELEASE_PYTHON:-python3}")
EM_QUALIFICATION_INPUTS="$out/locked-inputs"
EM_PYPI_BUILD_INPUTS="$EM_QUALIFICATION_INPUTS"
mkdir "$EM_QUALIFICATION_INPUTS"
CE_REGISTRY_UNAVAILABLE=
if [[ $stage == build || $RELEASE_REF_NAME == *-"$channel"-outage ]]; then
  CE_REGISTRY_UNAVAILABLE=$channel
fi

if [[ $channel == npm ]]; then
  export CE_NODE24_BIN_DIR CE_VERDACCIO EM_NODE22_BIN
  CE_NODE24_BIN_DIR=${CE_NODE24_BIN_DIR:-$(dirname "$(command -v node)")}
  cp npm/wheelhouse.lock.json "$out/input-lock.json"
  cp npm/wheelhouse/*.whl "$EM_QUALIFICATION_INPUTS/"
  if [[ $stage == publish && -z $CE_REGISTRY_UNAVAILABLE ]]; then
    if [[ -z ${CE_VERDACCIO-} ]]; then
      npm install --prefix "$out/npm-tools" --cache "$out/bootstrap-npm-cache" --registry https://registry.npmjs.org/ \
        --ignore-scripts --no-audit --no-fund verdaccio@7.1.2 > "$out/bootstrap-npm.log" 2>&1
      CE_VERDACCIO="$out/npm-tools/node_modules/.bin/verdaccio"
      cp "$out/npm-tools/package-lock.json" "$out/test-tools-lock.json"
    fi
    if [[ -z ${EM_NODE22_BIN-} ]]; then
      curl -fsS "https://nodejs.org/dist/v22.0.0/$node_archive" > "$out/$node_archive"
      printf '%s  %s\n' "$node_hash" "$out/$node_archive" | sha256sum --check
      tar -xJf "$out/$node_archive" -C "$out"
      EM_NODE22_BIN="$out/node-v22.0.0-linux-x64/bin"
    fi
    curl -fsS https://registry.npmjs.org/command-execution/2.0.10 > "$out/ce-npm.json"
    address=$(jq -er '.dist.tarball' "$out/ce-npm.json")
    test "$address" = "https://registry.npmjs.org/command-execution/-/$ce_tarball"
    curl -fsS "$address" > "$EM_QUALIFICATION_INPUTS/$ce_tarball"
    integrity="sha512-$(openssl dgst -sha512 -binary "$EM_QUALIFICATION_INPUTS/$ce_tarball" | openssl base64 -A)"
    test "$integrity" = "$(jq -er '.dist.integrity' "$out/ce-npm.json")"
    tar -xOf "$EM_QUALIFICATION_INPUTS/$ce_tarball" "package/vendor/$ce_wheel" > "$EM_QUALIFICATION_INPUTS/$ce_wheel"
  fi
else
  export CE_TWINE CE_DEVPI_INIT CE_DEVPI_SERVER
  cp "$helpers/python-inputs.json" "$out/input-lock.json"
  jq -er 'to_entries[] | [.key, .value.origin, .value.sha256] | @tsv' "$out/input-lock.json" > "$out/python-inputs.tsv"
  while IFS=$'\t' read -r filename source digest; do
    curl -fsS "$source" > "$EM_QUALIFICATION_INPUTS/$filename"
    printf '%s  %s\n' "$digest" "$EM_QUALIFICATION_INPUTS/$filename" | sha256sum --check
  done < "$out/python-inputs.tsv"
  if [[ $stage == publish ]]; then
    if [[ -z ${CE_TWINE-} ]]; then
      "$EM_PYTHON" -m venv "$out/python-tools"
      "$out/python-tools/bin/python" -m pip --isolated --disable-pip-version-check --no-cache-dir install \
        --index-url https://pypi.org/simple devpi-server==6.21.0 twine==7.0.0 > "$out/bootstrap-python.log" 2>&1
      CE_TWINE="$out/python-tools/bin/twine"
      CE_DEVPI_INIT="$out/python-tools/bin/devpi-init"
      CE_DEVPI_SERVER="$out/python-tools/bin/devpi-server"
      "$out/python-tools/bin/python" -m pip freeze --all > "$out/test-tools-lock.txt"
    fi
    curl -fsS https://pypi.org/pypi/command-execution/2.0.10/json > "$out/ce-pypi.json"
  fi
fi

(cd "$EM_QUALIFICATION_INPUTS" && sha256sum ./*) > "$out/inputs.sha256"
zone="$out/isolation"
if [[ $stage == build ]]; then
  bash "$helpers/with-registry.sh" "$channel" "$zone" -- \
    bash "$driver" prepare "$channel" "$out/build" > "$out/build.log" 2>&1 ||
    { cat "$out/build.log"; exit 1; }
  cat "$out/build.log"
  cp "$out/build/$artifact" "$out/build/manifest.json" "$out/"
  cp "$zone/network.log" "$out/build-network.log"
  exit
fi

test "$stage" = publish
build=${6:?downloaded build}
bash "$driver" artifact "$channel" "$build" >/dev/null
mkdir "$out/candidate" "$out/report"
cp "$build/$artifact" "$build/manifest.json" "$out/candidate/"
cp "$build/build.log" "$build/build-network.log" "$out/"
code=0
bash "$helpers/with-registry.sh" "$channel" "$zone" -- \
  bash "$helpers/qualify.sh" inside "$channel" "$out" "$tag" "$artifact" || code=$?
cp "$zone/network.log" "$out/report/"
printf '%s\n' "$code" > "$out/report/exit"
if [[ -f $out/report/operation.log ]]; then cat "$out/report/operation.log"; fi
exit "$code"
