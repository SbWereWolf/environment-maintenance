"""Build one distribution from the selected EM checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

from release import validate_release

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "npm/wheelhouse.lock.json"
BUILD_TOOLS = ("setuptools==84.2.1", "wheel==0.48.0", "packaging==26.3")


def checked_npm_wheels():
    wheelhouse = LOCK.parent / "wheelhouse"
    entries = json.loads(LOCK.read_text())
    if set(entries) != {path.name for path in wheelhouse.iterdir()}:
        raise ValueError("npm build wheel inventory differs from lock")
    if {f"{name.split('-')[0]}=={data['version']}" for name, data in entries.items()} != set(BUILD_TOOLS):
        raise ValueError("unexpected npm build tools")
    for name, data in entries.items():
        source = urlsplit(data["origin"])
        wheel = wheelhouse / name
        if (source.scheme, source.hostname, Path(source.path).name) != ("https", "files.pythonhosted.org", name):
            raise ValueError(f"invalid build wheel origin: {name}")
        if name.split("-")[1] != data["version"] or hashlib.sha256(wheel.read_bytes()).hexdigest() != data["sha256"]:
            raise ValueError(f"npm build wheel differs from lock: {name}")
    return [wheelhouse / name for name in entries]


def checkout_files(destination, paths):
    # Copy only the project's tracked supply, including changes under local development.
    files = subprocess.check_output(["git", "ls-files", "-z", "--", *paths], cwd=ROOT)
    for name in files.decode().split("\0"):
        if not name:
            continue
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)


def build(channel, tag, out):
    name, version = validate_release(ROOT, tag)
    epoch = subprocess.check_output(["git", "log", "-1", "--format=%ct"], cwd=ROOT, text=True).strip()
    env = {**os.environ, "SOURCE_DATE_EPOCH": epoch, "PIP_CONFIG_FILE": os.devnull}
    qualification = os.environ.get("RELEASE_MODE") == "qualification"
    python_inputs = os.environ.get("EM_PYPI_BUILD_INPUTS")
    with tempfile.TemporaryDirectory(prefix="em-build-") as temporary:
        work = Path(temporary)
        source = work / "source"
        source.mkdir()
        checkout_files(source, ["pyproject.toml", "MANIFEST.in", "README.md", "start-app", "src"])
        subprocess.run([sys.executable, "-m", "venv", work / "venv"], check=True)
        python = work / "venv/bin/python"
        pip = [python, "-I", "-m", "pip", "--isolated", "--no-cache-dir", "--disable-pip-version-check"]

        if channel == "npm":
            inputs = checked_npm_wheels()
        elif qualification:
            if not python_inputs:
                raise ValueError("qualification requires separate Python build inputs")
            inputs = [Path(python_inputs) / f"{tool.replace('==', '-')}-py3-none-any.whl" for tool in BUILD_TOOLS]
        else:
            inputs = ["--index-url", "https://pypi.org/simple", *BUILD_TOOLS]

        local_only = ["--no-index", "--no-deps"] if channel == "npm" or qualification else []
        subprocess.run([*pip, "install", *local_only, *inputs], env=env, check=True, stdout=sys.stderr)
        wheel_dir = out if channel == "pypi" else work / "wheel"
        wheel_dir.mkdir(exist_ok=True)
        subprocess.run([*pip, "wheel", "--no-index", "--no-deps", "--no-build-isolation",
                        "--wheel-dir", wheel_dir, source], env=env, check=True, stdout=sys.stderr)
        wheel = wheel_dir / f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
        if not wheel.is_file():
            raise ValueError(f"expected wheel missing: {wheel.name}")
        if channel == "pypi":
            if not qualification:
                (work / "smoke").mkdir()
                subprocess.run([*pip, "install", "--index-url", "https://pypi.org/simple", wheel],
                               env=env, check=True, stdout=sys.stderr)
                subprocess.run([*pip, "check"], env=env, check=True, stdout=sys.stderr)
                cli = subprocess.check_output([work / "venv/bin/start-app", "--version"], env=env, text=True)
                if cli.strip() != f"{name} {version}":
                    raise ValueError("installed Python CLI version differs")
                subprocess.run([python, "-I", "-B", ROOT / "tests/release/installed-sdk.py",
                                version, work / "smoke"], env=env, check=True, stdout=sys.stderr)
            return

        staged = work / "npm"
        checkout_files(staged, ["package.json", "pyproject.toml", "MANIFEST.in", "README.md",
                                "start-app", "src", "docs", "examples", "tests",
                                ".agents/skills/environment-maintenance/SKILL.md"])
        vendor = staged / "vendor"
        vendor.mkdir()
        shutil.copyfile(wheel, vendor / wheel.name)
        (vendor / "SHA256SUMS").write_text(f"{hashlib.sha256(wheel.read_bytes()).hexdigest()}  {wheel.name}\n")
        subprocess.run(["npm", "pack", "--json", "--ignore-scripts", "--pack-destination", out],
                       cwd=staged, env=env, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("channel", choices=("npm", "pypi"))
    parser.add_argument("tag")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        build(args.channel, args.tag, args.output.resolve())
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"release build: {error}\n")
