"""S8: packed/installed npm entry, its own Python and actual launch snapshots."""
import json
import os
from pathlib import Path

import pytest

from application_resources_support import (
    arrange_resources, environment_record, expected_list, expected_started, stored_applications,
)
from npm_delivery_support import PackageLab, living_group
from run_stop_support import Lab, FIXTURES, ROOT


@pytest.fixture(scope="module")
def package():
    instance = PackageLab()
    try:
        instance.require_package()
        consumer = instance.install("application-resources")
        instance.require_consumer(consumer)
        yield instance, consumer
    finally:
        instance.close()


def identity(package, lab):
    owner, consumer = package
    answer = owner.capture("resource-installed-identity", [consumer.python, "-I", "-B",
        ROOT / "tests/fixtures/cli-output/installed_identity.py"], lab.root)
    assert answer.returncode == 0 and answer.stderr == b""
    observed = json.loads(answer.stdout)
    assert Path(observed["origin"]).is_relative_to(consumer.prefix)
    assert Path(observed["prefix"]) == consumer.python.parent.parent
    assert observed["module_version"] == observed["distribution_version"] == owner.metadata["version"]
    return observed


def installed_call(package, lab, *argv):
    owner, consumer = package
    env = dict(owner.env, TMPDIR=str(lab.tmp), PYTHONPATH=str(FIXTURES))
    env["PATH"] = str(consumer.entry.parent) + os.pathsep + owner.env["PATH"]
    assert str(ROOT / "src") not in env["PYTHONPATH"]
    answer = lab.call(*argv, entry=consumer.entry, env=env)
    assert answer.returncode == 0 and answer.stderr == b"", (answer.stdout, answer.stderr)
    return json.loads(answer.stdout)


def test_installed_package_origin_is_independent(package, tmp_path):
    lab = Lab(tmp_path)
    try:
        identity(package, lab)
    finally:
        lab.close()


def test_installed_delivery_has_new_major_metadata(package, tmp_path):
    lab = Lab(tmp_path)
    try:
        observed = identity(package, lab)
        assert int(observed["module_version"].split(".")[0]) >= 5, "RESOURCE_RELEASE_VERSION: incompatible CLI"
    finally:
        lab.close()


def test_installed_package_lists_required_resources(package, tmp_path):
    lab = Lab(tmp_path)
    try:
        arrange_resources(lab)
        identity(package, lab)
        actual = installed_call(package, lab, "run", "list", "--output")
        assert lab.labels() == [] and not lab.store.exists()
        assert actual == expected_list(lab), "RESOURCE_NPM_REQUIRED: installed producer"
    finally:
        lab.close()


def test_installed_package_retains_launch_facts_without_config(package, tmp_path):
    lab = Lab(tmp_path)
    try:
        arrange_resources(lab)
        identity(package, lab)
        run = installed_call(package, lab, "run", "--env", "installed", "--app", "worker-a")
        group = lab.started("worker-a")["pgid"]
        assert run["applications"][0]["pgid"] == group and living_group(group)
        saved = stored_applications(lab, "installed")
        for path in (lab.main, lab.values, lab.root / "run.json"):
            path.unlink()
        listed = environment_record(installed_call(package, lab, "stop", "list", "--output"), "installed")
        stopped = installed_call(package, lab, "stop", "--env", "installed", "--app", "worker-a")
        assert stopped["stopped"][0]["pgid"] == group and stopped["errors"] == []
        lab.dead(group)
        assert not lab.state_path("installed").exists()
        expected = expected_started(lab, ["worker-a"])
        assert saved["worker-a"]["pgid"] == group
        assert listed["applications"] == expected, "RESOURCE_NPM_SNAPSHOT: original facts"
    finally:
        lab.close()
