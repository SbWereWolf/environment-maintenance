"""Transparent CLI arrangement and direct independent observations."""
from functools import cache
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "recovery"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
TEXT = {"d800": "\ud800", "dc80": "\udc80", "astral": "\U00010000"}


def call(argv, *, cwd=ROOT, env=None):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=120)


def successful(argv, *, cwd=ROOT, env=None):
    result = call(argv, cwd=cwd, env=env)
    assert result.returncode == 0, (argv, result.stdout, result.stderr)
    return result.stdout


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@cache
def source_cli():
    env = {"PATH": os.defpath, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"}
    origin = successful(
        [sys.executable, "-B", "-c", "import environment_maintenance; print(environment_maintenance.__file__)"],
        env=env,
    ).decode("utf-8").strip()
    assert Path(origin).resolve() == ROOT / "src/environment_maintenance/__init__.py"
    return {"argv": [sys.executable, "-B", "-m", "environment_maintenance"], "env": env}


def render(raw, replacements):
    # Replace complete JSON string tokens, preserving raw deep fixture structure.
    for name, value in replacements.items():
        raw = raw.replace(json.dumps(name), json.dumps(value, ensure_ascii=True))
    return raw


def observe_case(tmp_path, cli, case):
    family = case["family"]
    state, log, observed = (tmp_path / name for name in ("state", "actions.log", "observed.jsonl"))
    initial = case.get("state", "invalid" if case.get("role") == "repair" else "missing")
    state.write_bytes(initial.encode("ascii"))
    parent = tmp_path
    if family == "posix-path":
        parent = tmp_path / os.fsdecode(b"parent-\xff")
        parent.mkdir()
    root = parent / "catalog"
    root.mkdir()
    replacements = {"@PYTHON@": sys.executable, "@ACTION@": str(FIXTURES / "action.py"),
                    "@STATE@": str(state), "@LOG@": str(log)}
    raw = render((FIXTURES / "catalog.json").read_text(encoding="utf-8"), replacements)
    catalog = json.loads(raw)
    item = catalog["requirements"][0]
    args = ["run", "--catalog-dir", "catalog"]
    env = dict(cli["env"])
    selected = TEXT.get(case.get("text"), "\ud800")
    if family in ("unused", "used", "unrepresentable", "diagnostic"):
        declaration = {"type": "string"}
        origin = case.get("origin", "default")
        if origin == "default":
            declaration["default"] = selected
        elif origin == "values":
            values = tmp_path / "values.json"
            values.write_text(json.dumps({"text": selected}), encoding="utf-8")
            args += ["--values", str(values)]
        elif origin == "environment":
            declaration["env"] = "RECOVERY_TEXT"
            env["RECOVERY_TEXT"] = selected
        else:
            args += ["--set", "text=" + json.dumps(selected)]
        catalog["parameters"]["text"] = declaration
    if family == "typed-input":
        declaration = {"type": case["parameter_type"]}
        raw_typed = (
            (FIXTURES / "typed-depth-12000.json").read_text(encoding="utf-8")
            if case["mode"] == "deep" else case["raw"]
        )
        if case["origin"] == "cli":
            args += ["--set", "value=" + raw_typed]
        else:
            declaration["env"] = "RECOVERY_TYPED"
            env["RECOVERY_TYPED"] = raw_typed
        catalog["parameters"]["value"] = declaration
    if family in ("used", "unrepresentable"):
        field = case["field"]
        action = item["install"]
        if field == "argv":
            action["argv"].append("${text}")
        elif field == "env":
            action["env"] = {"VALUE": "${text}"}
        else:
            action["cwd"] = str(tmp_path) + "/used-${text}"
            if family == "used":
                (tmp_path / ("used-" + selected)).mkdir()
        if family == "used":
            action["argv"][7] = str(observed)
    if family == "huge-bound":
        item[case["role"]]["execution_bound_seconds"] = json.loads(
            (FIXTURES / "huge-bound.json").read_text(encoding="utf-8")
        )
    if family in ("deep-mutation", "deep-initial", "action-text"):
        role = case.get("role", "check")
        filename = (f"unavailable-{case['text']}.json" if family == "action-text"
                    else f"{role}-depth-{case['depth']}.json")
        item[role]["argv"][6] = str(FIXTURES / filename)
    if family == "diagnostic":
        if case["operation"] == "check":
            args[0] = "check"
        else:
            args.append("--dry-run")
    if family == "deep-input":
        args[0] = case["operation"]
        location = case["location"]
        raw_deep = render((FIXTURES / f"{location}-depth-{case['depth']}.json").read_text(encoding="utf-8"), replacements)
        if location == "catalog":
            (root / "catalog.json").write_text(raw_deep, encoding="utf-8")
        else:
            values = tmp_path / "values.json"
            values.write_text(raw_deep, encoding="utf-8")
            args += ["--values", str(values)]
    if not (family == "deep-input" and case["location"] == "catalog"):
        (root / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    process = call([*cli["argv"], *args], cwd=parent, env=env)
    # Read all effects before assertions, including on expected failure routes.
    after = state.read_bytes()
    actions = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    observations = [json.loads(line) for line in observed.read_text(encoding="ascii").splitlines()] if observed.exists() else []
    (tmp_path / "cli.stdout").write_bytes(process.stdout)
    (tmp_path / "cli.stderr").write_bytes(process.stderr)
    (tmp_path / "observation.json").write_text(json.dumps({
        "returncode": process.returncode, "resource": after.decode("ascii"),
        "actions": actions, "child_observations": observations,
    }, ensure_ascii=True, indent=2), encoding="ascii")
    if family in ("unrepresentable", "deep-input", "huge-bound") or (
        family == "typed-input" and case["mode"] == "deep"
    ):
        assert after == initial.encode("ascii")
        assert actions == []
        assert not log.exists()
        assert process.returncode == 2, process.stderr
        assert process.stdout == b""
        diagnostic = process.stderr.decode("utf-8", errors="strict")
        assert diagnostic.strip() and "Traceback" not in diagnostic
        return
    readonly = family in ("action-text", "diagnostic", "deep-initial")
    expected_actions = ["check"] if readonly else ["check", case.get("role", "install"), "check"]
    assert actions == expected_actions
    assert after == (initial.encode("ascii") if readonly else b"satisfied")
    if family == "used":
        assert len(observations) == 1
        child = observations[0]
        assert child["role"] == "install"
        assert child["argv"] == ([selected] if case["field"] == "argv" else [])
        assert child["cwd"] == (str(tmp_path / ("used-" + selected)) if case["field"] == "cwd" else str(root))
        assert child["env"].get("VALUE") == (selected if case["field"] == "env" else None)
        assert set(child["env"]) <= {"VALUE", "LC_CTYPE"}
    expected_code = (4 if family in ("deep-mutation", "deep-initial") else
                     3 if family == "action-text" else 2 if family == "diagnostic" else 0)
    assert process.returncode == expected_code, process.stderr
    assert process.stderr == b""
    result = json.loads(process.stdout.decode("utf-8", errors="strict"))
    assert result["schema"] == "environment-maintenance/result/v2"
    assert result["exit_code"] == expected_code
    assert result["status"] == {0: "ready", 2: "action_required", 3: "unavailable", 4: "failed"}[expected_code]
    assert len(result["requirements"]) == 1
    row = result["requirements"][0]
    if family == "typed-input":
        assert result["parameters"]["value"] == case["expected"]
        assert type(result["parameters"]["value"]) is type(case["expected"])
        assert result["parameter_sources"]["value"] == case["origin"]
    if family in ("unused", "used", "diagnostic"):
        assert result["parameters"]["text"] == selected
        assert result["parameter_sources"]["text"] == case.get("origin", "default")
    if family == "posix-path":
        assert row["initial_check"]["invocation"]["cwd"] == str(root)
        assert row["final_check"]["invocation"]["cwd"] == str(root)
    if family in ("deep-mutation", "deep-initial"):
        failure = row["mutation"] if family == "deep-mutation" else row["initial_check"]
        assert failure["status"] == "protocol_failure"
        assert failure["error"]
        assert failure["exit_code"] == 0
        assert failure["capture_complete"] is True
        assert failure["timed_out"] is False
        if family == "deep-initial":
            assert "mutation" not in row and "final_check" not in row
        else:
            assert row["final_check"]["status"] == "passed"
            assert row["final_check"]["response"]["state"] == "satisfied"
            original_argv = [sys.executable, "-S", str(FIXTURES / "action.py"), "check", str(state), str(log), "-", "-"]
            for key in ("initial_check", "final_check"):
                assert row[key]["invocation"] == {"argv": original_argv, "cwd": str(root), "env": {}}
    if family == "action-text":
        assert row["cause"] == selected
        assert row["recommendations"] == ["Use configured source."]
        assert "mutation" not in row
    if family == "diagnostic":
        assert row["planned_action"] == ("install" if initial == "missing" else "repair")
        assert "mutation" not in row


def make_supply():
    mode = os.environ["ENV_MAINT_SUPPLY_MODE"]
    if mode == "build":
        output = Path(os.environ["ENV_MAINT_RELEASE_OUTPUT"])
        output.mkdir(parents=True, exist_ok=True)
        release = Path(tempfile.mkdtemp(prefix="candidate-", dir=output))
        commit = successful(["git", "rev-parse", "HEAD"]).decode().strip()
        successful(["git", "bundle", "create", str(release / "source.bundle"), "HEAD"])
        build_source = release / "build-source"
        successful(["git", "clone", "--quiet", str(release / "source.bundle"), str(build_source)])
        successful(["git", "checkout", "--quiet", "--detach", commit], cwd=build_source)
        argv = [sys.executable, "-I", "-B", str(FIXTURES / "build_wheel.py"), str(release)]
        build = call(argv, cwd=build_source)
        (release / "build.stdout").write_bytes(build.stdout)
        (release / "build.stderr").write_bytes(build.stderr)
        assert build.returncode == 0, (build.stdout, build.stderr)
        wheels = list(release.glob("*.whl"))
        assert len(wheels) == 1
        wheel = wheels[0]
        with zipfile.ZipFile(wheel) as archive:
            metadata = archive.read(next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))).decode()
        version = next(line.removeprefix("Version: ") for line in metadata.splitlines() if line.startswith("Version: "))
        record = {"purpose": "Versioned standalone maintenance supply", "source_commit": commit,
                  "source_bundle_sha256": digest(release / "source.bundle"), "wheel": wheel.name,
                  "wheel_sha256": digest(wheel), "backend_python": sys.version,
                  "backend": "setuptools" + importlib.metadata.version("setuptools"),
                  "argv": argv, "exit_code": build.returncode,
                  "stdout_sha256": digest(release / "build.stdout"), "stderr_sha256": digest(release / "build.stderr")}
        (release / "build-record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        manifest = {"distribution": "environment-maintenance", "version": version, "requires_python": ">=3.11",
                    "source_commit": commit, "source_bundle_sha256": record["source_bundle_sha256"],
                    "wheel": wheel.name, "wheel_sha256": record["wheel_sha256"], "build": record}
        manifest_path = release / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    elif mode == "consume":
        manifest_path = Path(os.environ["ENV_MAINT_SUPPLY_MANIFEST"])
        release = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        raise AssertionError("Explicit supply mode must be build or consume")
    # Integrity and source identity are setup prerequisites, never expected RED.
    wheel = release / manifest["wheel"]
    assert wheel.parent == release and wheel.name == manifest["wheel"]
    assert digest(wheel) == manifest["wheel_sha256"]
    assert digest(release / "source.bundle") == manifest["source_bundle_sha256"]
    bundle_heads = successful(["git", "bundle", "list-heads", str(release / "source.bundle")]).decode()
    assert bundle_heads.strip() == manifest["source_commit"] + " HEAD"
    record = json.loads((release / "build-record.json").read_text(encoding="utf-8"))
    assert record == manifest["build"]
    assert digest(release / "build.stdout") == record["stdout_sha256"]
    assert digest(release / "build.stderr") == record["stderr_sha256"]
    install_root = Path(tempfile.mkdtemp(prefix="installed-", dir=os.environ["ENV_MAINT_RELEASE_OUTPUT"]))
    venv = install_root / "venv"
    successful([sys.executable, "-I", "-B", "-m", "venv", str(venv)])
    python = venv / "bin/python"
    successful([str(python), "-I", "-B", "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)])
    origin = successful([str(python), "-I", "-B", "-c", "import environment_maintenance; print(environment_maintenance.__file__)"]).decode().strip()
    assert Path(origin).is_relative_to(venv) and not Path(origin).is_relative_to(ROOT)
    entry = venv / "bin/environment-maintenance"
    assert entry.is_file()
    print("ENV_MAINT_SUPPLY_MANIFEST=" + str(manifest_path), flush=True)
    return {"manifest_path": manifest_path, "manifest": manifest, "release": release,
            "cli": {"argv": [str(entry)], "env": {"PATH": os.defpath, "PYTHONUTF8": "1"}}}


def prove_supply(supply):
    manifest = supply["manifest"]
    release = supply["release"]
    contract = json.loads((FIXTURES / "release-contract.json").read_text(encoding="utf-8"))
    assert set(manifest) == set(contract["manifest_fields"])
    assert set(manifest["build"]) == set(contract["build_fields"])
    assert manifest["distribution"] == "environment-maintenance"
    assert manifest["requires_python"] == ">=3.11"
    assert manifest["build"]["exit_code"] == 0
    assert manifest["build"]["source_commit"] == manifest["source_commit"]
    assert manifest["build"]["source_bundle_sha256"] == manifest["source_bundle_sha256"]
    assert manifest["build"]["wheel"] == manifest["wheel"]
    assert manifest["build"]["wheel_sha256"] == manifest["wheel_sha256"]
    assert manifest["build"]["backend"] == "setuptools84.0.0"
    assert manifest["build"]["argv"][1:4] == ["-I", "-B", str(FIXTURES / "build_wheel.py")]
    with zipfile.ZipFile(release / manifest["wheel"]) as archive:
        names = archive.namelist()
        package = sorted(n.removeprefix("environment_maintenance/") for n in names if n.startswith("environment_maintenance/") and n.endswith(".py"))
        assert package == sorted(contract["package_files"])
        for name in contract["package_files"]:
            expected = successful(["git", "show", manifest["source_commit"] + ":src/environment_maintenance/" + name])
            assert archive.read("environment_maintenance/" + name) == expected
        metadata = archive.read(next(n for n in names if n.endswith(".dist-info/METADATA"))).decode("utf-8")
        assert "Name: environment-maintenance\n" in metadata
        assert "Requires-Python: >=3.11\n" in metadata
        assert not any(line.startswith("Requires-Dist:") for line in metadata.splitlines())
        entrypoints = archive.read(next(n for n in names if n.endswith(".dist-info/entry_points.txt"))).decode("utf-8")
        assert "environment-maintenance = environment_maintenance.cli:main" in entrypoints
        # Version is a behavior assertion after all arrangement/provenance checks.
        assert "Version: 0.2.1\n" in metadata
    assert manifest["version"] == "0.2.1"
