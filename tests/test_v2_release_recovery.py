"""Observe the exact independently installable wheel, plus provenance."""
import pytest

from v2_recovery_helpers import CASES, make_supply, observe_case, prove_supply


@pytest.fixture(scope="session")
def supply():
    return make_supply()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_installed_failure_recovery(tmp_path, supply, case):
    observe_case(tmp_path, supply["cli"], case)


def test_release_identity_and_provenance(supply):
    prove_supply(supply)
