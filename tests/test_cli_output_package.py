"""F08: the actual packed/installed npm CLI, with no source import fallback."""
import os
import json
from pathlib import Path

import pytest

from npm_delivery_support import PackageLab
from run_stop_support import Lab, ROOT, FIXTURES as RUN_FIXTURES
from test_cli_output import (
    assert_golden, assert_inputs_unchanged, assert_no_resources,
    assert_warning, cases, input_snapshot, OUTPUT_FIXTURES,
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
        identity = package.capture("output-runtime-origin", [consumer.python, "-I", "-B",
            OUTPUT_FIXTURES / "installed_identity.py"], lab.root)
        assert identity.returncode == 0 and identity.stderr == b""
        observed = json.loads(identity.stdout)
        assert Path(observed["origin"]).is_relative_to(consumer.prefix)
        assert Path(observed["prefix"]) == consumer.python.parent.parent
        assert observed["module_version"] == observed["distribution_version"] == package.metadata["version"]
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
