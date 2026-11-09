#!/usr/bin/env bash
set -euo pipefail
python_executable=${1:?Select the project Python executable}
exec "$python_executable" -B -m pytest -p no:cacheprovider -q \
  tests/test_run_stop.py::test_run_list_stop_roundtrip \
  tests/test_run_stop.py::test_runtime_failure_continues_apps_but_not_the_failed_chain \
  tests/test_run_stop.py::test_stop_one_app_preserves_other_app_and_other_env \
  tests/test_cli_contract.py::test_default_all_does_not_require_invocation_preselection \
  tests/test_resource_checks.py::test_public_check_api_preserves_full_bytes_and_context \
  tests/test_settings_alignment.py::test_public_api_adjust_preserves_bytes_and_real_settings
