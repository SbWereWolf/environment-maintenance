"""Validate the selected npm release and observe registry admission."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import tomllib
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def validate_release(root, tag):
    """Check the release source before packaging."""
    root = Path(root)
    npm = json.loads((root / "package.json").read_text())
    python = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    name, version = npm["name"], npm["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or tag != "v" + version:
        raise ValueError("tag must select the stable npm version")
    if python["version"] != version or python["name"] != name:
        raise ValueError("Python and npm package name/version differ")
    if "command-execution==1.0.0" not in python.get("dependencies", []):
        raise ValueError("dependency must select command-execution==1.0.0")
    return name, version


def check_registry(name, version, tarball):
    """Allow a new version or recognize identical published bytes."""
    tarball = Path(tarball)
    if not tarball.is_file() or not tarball.stat().st_size:
        raise ValueError("distribution tarball is missing or empty")
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(tarball.read_bytes()).digest()).decode()
    url = f"https://registry.npmjs.org/{quote(name, safe='')}/{quote(version, safe='')}"
    try:
        with urlopen(Request(url, method="GET"), timeout=30) as response:
            document = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return "publish"
        raise ValueError(f"registry refused the release query: HTTP {error.code}") from error
    except (URLError, OSError, ValueError) as error:
        raise ValueError(f"registry query failed: {error}") from error
    try:
        published = document["dist"]["integrity"]
    except (KeyError, TypeError) as error:
        raise ValueError("registry returned no published integrity") from error
    if published != integrity:
        raise ValueError("published bytes differ from the candidate; use a new version")
    return "already-published"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("validate", "registry"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--tarball", type=Path)
    args = parser.parse_args()
    if args.phase == "registry" and args.tarball is None:
        parser.error("registry requires --tarball")
    try:
        name, version = validate_release(args.root, args.tag)
        decision = (check_registry(name, version, args.tarball)
                    if args.phase == "registry" else "validated")
    except (ValueError, OSError) as error:
        parser.exit(1, f"release: {error}\n")
    print(json.dumps({"name": name, "version": version, "decision": decision}))
    if args.phase == "registry" and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"decision={decision}\n")


if __name__ == "__main__":
    main()
