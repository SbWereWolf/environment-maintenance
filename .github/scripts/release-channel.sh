#!/usr/bin/env bash
set -euo pipefail

phase=${1:?Select release phase}
channel=${2:?Select release channel}
out=${3:?Select output directory}
mode=${RELEASE_MODE:?Select release mode}
ref=${RELEASE_REF_NAME:?Select release ref}
sha=${RELEASE_SHA:?Select source commit}
python=${RELEASE_PYTHON:-python3}
package=${RELEASE_PACKAGE:?Select package name}
repo=$(git rev-parse --show-toplevel)
cd "$repo"
test "$(git rev-parse HEAD)" = "$sha"
case "$channel" in npm|pypi) ;; *) exit 2 ;; esac
case "$mode" in
  production) [[ $ref =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]] ;;
  qualification) [[ $ref =~ ^qualify-em-v([0-9]+\.[0-9]+\.[0-9]+)(-r[1-9][0-9]*)?-(npm|pypi)-outage$ ]] ;;
  *) exit 2 ;;
esac
version=${BASH_REMATCH[1]}
tag="v$version"
actual=$("$python" -I -B .github/scripts/release.py validate --tag "$tag")
test "$(jq -r .name <<<"$actual")" = "$package"
test "$(jq -r .version <<<"$actual")" = "$version"
export SOURCE_DATE_EPOCH
SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)

if [[ $channel == npm ]]; then
  artifact="$package-$version.tgz"
else
  artifact="${package//-/_}-$version-py3-none-any.whl"
fi

seal_artifact() {
  local hash
  hash=$(sha256sum "$out/$artifact" | cut -d' ' -f1)
  jq -n --arg sha "$sha" --arg ref "$ref" --arg channel "$channel" --arg name "$package" \
    --arg version "$version" --arg artifact "$artifact" --arg digest "$hash" \
    '{source_sha:$sha, ref:$ref, channel:$channel, package:$name, version:$version, artifact:$artifact, sha256:$digest}' \
    > "$out/manifest.json"
}

verify_artifact() {
  local hash
  hash=$(sha256sum "$out/$artifact" | cut -d' ' -f1)
  jq -e --arg sha "$sha" --arg ref "$ref" --arg channel "$channel" --arg name "$package" \
    --arg version "$version" --arg artifact "$artifact" --arg digest "$hash" \
    '.=={source_sha:$sha,ref:$ref,channel:$channel,package:$name,version:$version,artifact:$artifact,sha256:$digest}' \
    "$out/manifest.json" >/dev/null
}

case "$phase" in
  identity)
    printf '%s\n' "$actual"
    ;;
  prepare)
    mkdir -- "$out"
    RELEASE_REF="$tag" RELEASE_PYTHON="$python" bash scripts/build-release.sh "$channel" "$out" > "$out/pack.log"
    if [[ $channel == npm && $mode == production ]]; then
      scratch=$(mktemp -d)
      trap 'rm -rf -- "$scratch"' EXIT
      ENVIRONMENT_MAINTENANCE_PYTHON=$(command -v "$python") npm install \
        --registry https://registry.npmjs.org/ --prefix "$scratch" --no-audit --no-fund --foreground-scripts "$out/$artifact"
      test "$("$scratch/node_modules/.bin/start-app" --version)" = "$package $version"
    fi
    seal_artifact
    ;;
  artifact)
    verify_artifact
    printf '%s\n' "$out/$artifact"
    ;;
  registry|verify)
    test "$mode" = production
    verify_artifact
    "$python" -B .github/scripts/verify-distribution.py "$phase" "$channel" "$package" "$version" "$out/$artifact"
    ;;
  qualify-build)
    test "$mode" = qualification
    exec bash tests/release/qualify.sh build "$channel" "$out" "$tag" "$artifact"
    ;;
  qualify)
    test "$mode" = qualification
    exec bash tests/release/qualify.sh publish "$channel" "$out" "$tag" "$artifact" "${4:?Select the downloaded distribution}"
    ;;
  *) exit 2 ;;
esac
