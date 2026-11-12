"""F08: the actual packed/installed npm CLI, with no source import fallback."""
import os
from pathlib import Path

import pytest

from npm_delivery_support import PackageLab
from run_stop_support import Lab, ROOT, FIXTURES as RUN_FIXTURES
from test_cli_output import (
    assert_golden, assert_inputs_unchanged, assert_no_resources,
    assert_warning, cases, input_snapshot,
)


@pytest.fixture(scope="module")
def package():
    instance = PackageLab()
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture(scope="module")
def consumer(package):
    installed = package.install("output-contract")
    package.require_consumer(installed)
    return installed


@pytest.mark.parametrize("row", cases("F08"), ids=["default", "bare", "pretty", "one-line", "invalid"])
def test_installed_npm_entry_uses_output_contract(package, consumer, tmp_path, row):
    lab = Lab(tmp_path)
    try:
        identity = package.capture("output-runtime-origin", [consumer.python, "-I", "-B", "-c",
            "import environment_maintenance; print(environment_maintenance.__file__)"], lab.root)
        assert identity.returncode == 0 and identity.stderr == b""
        assert Path(identity.stdout.decode().strip()).is_relative_to(consumer.prefix)
        environment = dict(package.env, TMPDIR=str(lab.tmp), PYTHONPATH=str(RUN_FIXTURES))
        environment["PATH"] = str(consumer.entry.parent) + os.pathsep + package.env["PATH"]
        assert str(ROOT / "src") not in environment["PYTHONPATH"]
        before = input_snapshot(lab)
        completed = lab.call(*row["argv"], entry=consumer.entry, env=environment)
        assert_golden(completed, lab, "run-list", row["format"])
        if row["warning"]:
            assert_warning(completed, "--output", "wide", known_output=True)
        else:
            assert completed.stderr == b""
        assert lab.labels() == []
        assert_inputs_unchanged(before)
        assert_no_resources(lab)
    finally:
        lab.close()
