#!/usr/bin/env bash
set -euo pipefail
python_executable=${1:?Select the project Python executable}
exec "$python_executable" -B -m pytest -p no:cacheprovider -q \
  tests/test_v2_engine.py::test_satisfied_runs_only_check \
  tests/test_v2_engine.py::test_mutation_is_selected_by_state_and_followed_by_same_check \
  tests/test_v2_engine.py::test_check_and_dry_run_never_mutate \
  tests/test_v2_engine.py::test_unavailable_preserves_cause_and_recommendations_without_mutation \
  tests/test_v2_engine.py::test_failed_mutation_is_still_followed_by_check \
  tests/test_v2_contract.py::test_typed_parameters_and_one_pass_expansion \
  tests/test_v2_boundaries.py::test_action_environment_uses_only_allowlist_plus_declared_values \
  tests/test_v2_boundaries.py::test_cli_never_serializes_known_secret_values \
  tests/test_v2_contract.py::test_action_numeric_boundaries_are_accepted
