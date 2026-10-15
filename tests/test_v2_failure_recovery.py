"""Real source CLI observations; no production oracle imports."""
import pytest

from v2_recovery_helpers import CASES, observe_case, source_cli


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_source_failure_recovery(tmp_path, case):
    observe_case(tmp_path, source_cli(), case)
