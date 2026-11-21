"""Identify a new version, exact retry, or conflicting registry artifact."""
import argparse
from pathlib import Path
from time import monotonic, sleep

from release import check_pypi, check_registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("registry", "verify"))
    parser.add_argument("channel", choices=("npm", "pypi"))
    parser.add_argument("package")
    parser.add_argument("version")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--registry")
    args = parser.parse_args()
    check = check_registry if args.channel == "npm" else check_pypi
    endpoint = {"registry": args.registry} if args.registry else {}
    deadline = monotonic() + (25 * 60 if args.channel == "npm" else 60)
    try:
        while True:
            decision = check(args.package, args.version, args.artifact, **endpoint)
            if args.phase == "registry" or decision == "already-published":
                print(decision)
                return
            if monotonic() >= deadline:
                raise ValueError("published version did not become available")
            sleep(5 if args.channel == "pypi" else 30)
    except (ValueError, OSError) as error:
        parser.exit(1, f"release: {error}\n")


if __name__ == "__main__":
    main()
