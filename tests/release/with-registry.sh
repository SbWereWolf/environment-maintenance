#!/usr/bin/env bash
# Run a checked command against a single loopback-only test registry.
set -euo pipefail

if [[ ${1-} != --inside ]]; then
  if [[ $# -lt 4 || ${3-} != -- ]]; then
    printf 'Usage: bash with-registry.sh npm|pypi NEW_DIRECTORY -- COMMAND [ARG...]\n' >&2
    exit 2
  fi
  kind=$1
  case "$kind" in npm|pypi) ;; *) exit 2 ;; esac
  mkdir -m 700 -- "$2"
  directory=$(realpath -- "$2")
  shift 3
  if [[ ${GITHUB_ACTIONS-} == true && ${RUNNER_ENVIRONMENT-} == github-hosted ]]; then
    # The hosted runner restricts uid_map for unprivileged user namespaces.
    environment=()
    for name in PATH HOME RUNNER_TEMP RELEASE_MODE RELEASE_PACKAGE RELEASE_REF_NAME RELEASE_SHA RELEASE_PYTHON \
      GITHUB_REF_NAME GITHUB_REF GITHUB_SHA GITHUB_RUN_ID GITHUB_RUN_ATTEMPT GITHUB_JOB \
      CE_PYTHON CE_SDK_FIXTURE CE_CAPTURE_RELEASE CE_REGISTRY_UNAVAILABLE CE_NODE24_BIN_DIR CE_VERDACCIO \
      CE_DEVPI_INIT CE_DEVPI_SERVER CE_TWINE CE_PYPI_BUILD_INPUTS \
      EM_PYTHON EM_SDK_ORACLE_WHEEL EM_NODE22_BIN EM_QUALIFICATION_INPUTS EM_PYPI_BUILD_INPUTS; do
      if [[ -v $name ]]; then environment+=("$name=${!name}"); fi
    done
    exec sudo -n -- /usr/bin/unshare --net -- /bin/bash -c '
      set -e
      /usr/sbin/ip link set lo up
      uid=$1 gid=$2
      shift 2
      exec /usr/bin/setpriv --reuid "$uid" --regid "$gid" --init-groups \
        --no-new-privs --bounding-set=-all --inh-caps=-all --ambient-caps=-all -- "$@"
    ' qualification-network "$(id -u)" "$(id -g)" \
      /usr/bin/env -i "${environment[@]}" /bin/bash "$0" --inside "$kind" "$directory" "$@"
  fi
  exec unshare --user --map-root-user --net bash "$0" --inside "$kind" "$directory" "$@"
fi

shift
kind=$1
directory=$2
shift 2
umask 077
if [[ $EUID == 0 ]]; then ip link set lo up; fi
test -n "$(ip -o link show up dev lo)"
test -z "$(ip route show default)"
{
  printf 'qualification uid=%s\n' "$EUID"
  printf "default route absent\n"
  ip -br address
} > "$directory/network.log"
for host in pypi.org files.pythonhosted.org registry.npmjs.org; do
  if curl -q --noproxy '*' --max-time 3 --silent --show-error --fail "https://$host/" >/dev/null 2>>"$directory/network.log"; then
    printf 'External endpoint unexpectedly reachable: %s\n' "$host" >&2
    exit 1
  fi
  printf 'unreachable %s\n' "$host" >> "$directory/network.log"
done

export HOME="$directory/home"
mkdir -p "$HOME"
export NPM_CONFIG_USERCONFIG="$HOME/npmrc"
export NPM_CONFIG_GLOBALCONFIG=/dev/null
export NPM_CONFIG_CACHE="$directory/npm-cache"
export PIP_CONFIG_FILE=/dev/null
export PIP_NO_CACHE_DIR=1
unset PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_FIND_LINKS PIP_NO_INDEX
export CE_CHECK_ROOT="$directory"
export NO_PROXY=127.0.0.1,localhost
export no_proxy="$NO_PROXY"

if [[ ${CE_REGISTRY_UNAVAILABLE-} == "$kind" ]]; then
  if [[ $kind == npm ]]; then
    export PATH="${CE_NODE24_BIN_DIR:?Select a Node 24 bin directory}:$PATH"
    export CE_NPM_REGISTRY=http://127.0.0.1:4873/
    printf '//127.0.0.1:4873/:_authToken=qualification-local-only\n' > "$NPM_CONFIG_USERCONFIG"
  else
    export CE_PYPI_UPLOAD=http://127.0.0.1:3141/root/qualification/
    export TWINE_USERNAME=qualification TWINE_PASSWORD=qualification-local-only TWINE_NON_INTERACTIVE=1
  fi
  exec "$@"
fi

wait_for_registry() {
  local endpoint=$1
  for ((attempt=0; attempt<60; attempt++)); do
    if curl -q --fail --silent --max-time 1 "$endpoint" > "$directory/health.json"; then
      return
    fi
    if ! kill -0 "$server" 2>/dev/null; then
      cat "$directory/registry.log" >&2
      return 1
    fi
    sleep 0.5
  done
  cat "$directory/registry.log" >&2
  return 1
}

if [[ $kind == npm ]]; then
  export PATH="${CE_NODE24_BIN_DIR:?Select a Node 24 bin directory}:$PATH"
  export CE_NPM_REGISTRY=http://127.0.0.1:4873/
  export NPM_CONFIG_REGISTRY="$CE_NPM_REGISTRY"
  cat > "$directory/verdaccio.yaml" <<'YAML'
storage: ./storage
auth:
  htpasswd:
    file: ./htpasswd
uplinks: {}
packages:
  '**':
    access: $all
    publish: $authenticated
YAML
  "${CE_VERDACCIO:?Select the test Verdaccio executable}" --config "$directory/verdaccio.yaml" --listen 127.0.0.1:4873 > "$directory/registry.log" 2>&1 &
  server=$!
  health="${CE_NPM_REGISTRY}-/ping"
else
  export CE_PYPI_UPLOAD=http://127.0.0.1:3141/root/qualification/
  export CE_PYPI_SIMPLE="${CE_PYPI_UPLOAD}+simple/"
  "${CE_DEVPI_INIT:?Select devpi-init}" --serverdir "$directory/server" --no-root-pypi --root-passwd qualification-local-only > "$directory/init.log" 2>&1
  "${CE_DEVPI_SERVER:?Select devpi-server}" --serverdir "$directory/server" --host 127.0.0.1 --port 3141 > "$directory/registry.log" 2>&1 &
  server=$!
  health=http://127.0.0.1:3141/+api
fi
trap 'kill "$server" 2>/dev/null || true; wait "$server" 2>/dev/null || true' EXIT
wait_for_registry "$health"

if [[ $kind == npm ]]; then
  # Verdaccio creates a sandbox-only account and returns a token.
  token=$(curl -q --fail --silent --show-error -X PUT -H 'Content-Type: application/json'     --data '{"name":"qualification","password":"qualification-local-only","email":"local@example.invalid","type":"user","roles":[]}'     "${CE_NPM_REGISTRY}-/user/org.couchdb.user:qualification" | jq -er '.token')
  printf '//127.0.0.1:4873/:_authToken=%s\n' "$token" > "$NPM_CONFIG_USERCONFIG"
else
  token=$(curl -q --fail --silent --show-error -H 'Content-Type: application/json'     --data '{"user":"root","password":"qualification-local-only"}' http://127.0.0.1:3141/+login | jq -er '.result.password')
  auth=$(printf 'root:%s' "$token" | base64 -w0)
  curl -q --fail --silent --show-error -X PUT -H "X-Devpi-Auth: $auth" -H 'Content-Type: application/json'     --data '{"type":"stage","bases":[],"volatile":false}' "$CE_PYPI_UPLOAD" > "$directory/index.json"
  export TWINE_USERNAME=root TWINE_PASSWORD="$token" TWINE_NON_INTERACTIVE=1
fi
"$@"
