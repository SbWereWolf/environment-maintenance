"""Independent selected-version and npm release admission expectations.

SourceContract observes the current source without a future producer. The
future gate class is selected only once its interface exists; missing imports
are never evidence of behavioral RED.
"""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/release-contract"
EXPECTED = json.loads((FIXTURES / "expected.json").read_text())


def checked_reply(*, payload=None, failure=None):
    """Observe exact read-only version query before supplying any response."""
    def reply(target, data=None, **kwargs):
        url = target.full_url if isinstance(target, Request) else target
        method = target.get_method() if isinstance(target, Request) else "GET"
        if data is not None and (not isinstance(target, Request) or target.method is None):
            method = "POST"
        if (url, method) != (EXPECTED["url"], "GET"):
            raise AssertionError(f"Unexpected registry request: {method} {url}")
        if failure is not None:
            raise failure
        return io.BytesIO(json.dumps(payload).encode())
    return reply


class SourceContract(unittest.TestCase):
    def test_selected_source_keeps_em_own_version(self):
        npm = json.loads((ROOT / "package.json").read_text())
        python = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        self.assertEqual((npm["name"], npm["version"]),
                         (EXPECTED["name"], EXPECTED["version"]))
        self.assertEqual(python["version"], EXPECTED["version"])

    def test_selected_source_requires_library_first_release(self):
        python = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        self.assertIn(EXPECTED["library_requirement"], python["dependencies"])


class TransportContract(unittest.TestCase):
    def test_exact_get_receives_fixture(self):
        with checked_reply(payload={"approved": True})(Request(EXPECTED["url"], method="GET")) as response:
            self.assertEqual(json.load(response), {"approved": True})

    def test_wrong_target_or_method_fails_before_404(self):
        missing = HTTPError(EXPECTED["url"], 404, "Not Found", None, None)
        for target in ("https://registry.npmjs.org/another-package/5.1.0",
                       "https://registry.npmjs.org/environment-maintenance/9.9.9",
                       "https://registry.npmjs.org/environment-maintenance",
                       Request(EXPECTED["url"], method="POST")):
            with self.subTest(target=target):
                with self.assertRaisesRegex(AssertionError, "registry request"):
                    checked_reply(failure=missing)(target)


class ReleaseGateContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("em_release_gate", ROOT / ".github/scripts/release.py")
        cls.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gate)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        shutil.copytree(FIXTURES / "project", self.project)
        self.tarball = self.root / "candidate.tgz"
        self.tarball.write_text(EXPECTED["tarball_text"])

    def validate(self, tag=None):
        return self.gate.validate_release(self.project, tag or EXPECTED["tag"])

    def registry(self):
        return self.gate.check_registry(EXPECTED["name"], EXPECTED["version"], self.tarball)

    def test_matching_tag_accepts_both_metadata_versions(self):
        self.assertEqual(self.validate(), ("environment-maintenance", "5.1.0"))

    def test_different_tag_or_branch_ref_is_refused(self):
        for tag in ("v9.9.9", "master"):
            with self.subTest(tag=tag):
                with self.assertRaisesRegex(ValueError, "tag"):
                    self.validate(tag)

    def test_disagreeing_python_and_npm_versions_are_refused(self):
        path = self.project / "pyproject.toml"
        path.write_text(path.read_text().replace('version = "5.1.0"', 'version = "5.0.0"'))
        with self.assertRaisesRegex(ValueError, "version"):
            self.validate()

    def test_old_library_dependency_is_refused(self):
        path = self.project / "pyproject.toml"
        path.write_text(path.read_text().replace("command-execution==1.0.0", "command-execution==0.1.0"))
        with self.assertRaisesRegex(ValueError, "dependency"):
            self.validate()

    def test_absent_exact_version_permits_publication(self):
        absent = HTTPError(EXPECTED["url"], 404, "Not Found", None, None)
        with patch.object(self.gate, "urlopen", side_effect=checked_reply(failure=absent)):
            self.assertEqual(self.registry(), "publish")

    def test_exact_integrity_is_an_unchanged_repeat(self):
        response = {"dist": {"integrity": EXPECTED["integrity"]}}
        before = self.tarball.read_bytes()
        with patch.object(self.gate, "urlopen", side_effect=checked_reply(payload=response)):
            self.assertEqual([self.registry(), self.registry()], ["already-published"] * 2)
        self.assertEqual(self.tarball.read_bytes(), before)

    def test_different_published_bytes_refuse_upload(self):
        self.tarball.write_bytes(b"different candidate\n")
        response = {"dist": {"integrity": EXPECTED["integrity"]}}
        with patch.object(self.gate, "urlopen", side_effect=checked_reply(payload=response)):
            with self.assertRaisesRegex(ValueError, "published"):
                self.registry()

    def test_missing_integrity_is_not_a_completed_repeat(self):
        with patch.object(self.gate, "urlopen", side_effect=checked_reply(payload={"dist": {}})):
            with self.assertRaisesRegex(ValueError, "registry|published"):
                self.registry()

    def test_network_or_permission_failure_refuses_upload(self):
        denied = HTTPError(EXPECTED["url"], 403, "Forbidden", None, None)
        for failure in (denied, URLError("offline")):
            with self.subTest(failure=failure):
                with patch.object(self.gate, "urlopen", side_effect=checked_reply(failure=failure)):
                    with self.assertRaisesRegex(ValueError, "registry"):
                        self.registry()


if __name__ == "__main__":
    unittest.main()
