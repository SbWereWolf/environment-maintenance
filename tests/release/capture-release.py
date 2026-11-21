"""Capture one test-registry publication and its actual subprocess status."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import re
from urllib.parse import urlsplit

TAG = re.compile(r"qualify-em-v(\d+\.\d+\.\d+)(?:-r[1-9]\d*)?-(npm|pypi)-outage")
START_MARKER = "CE_RELEASE_START "
EXIT_MARKER = "CE_RELEASE_EXIT "


def require(condition, message):
    if not condition:
        raise ValueError(message)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("channel", choices=("npm", "pypi"))
parser.add_argument("endpoint")
parser.add_argument("log", type=Path)
parser.add_argument("command", nargs=argparse.REMAINDER)
args = parser.parse_args()
try:
    argv = args.command[1:] if args.command[:1] == ["--"] else args.command
    tag = os.environ["GITHUB_REF_NAME"]
    match = TAG.fullmatch(tag)
    require(match and os.environ["GITHUB_REF"] == "refs/tags/" + tag, "expected EM qualification tag")
    version = match[1]
    filename = (f"environment-maintenance-{version}.tgz" if args.channel == "npm"
                else f"environment_maintenance-{version}-py3-none-any.whl")
    record = {"run_id": int(os.environ["GITHUB_RUN_ID"]), "attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
              "tag": tag, "sha": os.environ["GITHUB_SHA"], "job_key": os.environ["GITHUB_JOB"],
              "release_step": "Qualify release", "endpoint": args.endpoint,
              "release_command": {"argv": argv}}
    endpoint = urlsplit(args.endpoint)
    require(endpoint.scheme == "http" and endpoint.hostname == "127.0.0.1"
            and endpoint.port and endpoint.username is None and endpoint.password is None,
            "publication must use a loopback test endpoint")
    client, operation, option = (("npm", "publish", "--registry") if args.channel == "npm"
                                 else ("twine", "upload", "--repository-url"))
    require(len(argv) >= 4 and (Path(argv[0]).name, argv[1]) == (client, operation)
            and argv.count(option) == 1 and argv[argv.index(option) + 1] == args.endpoint
            and any(Path(arg).name == filename for arg in argv[2:]), "invalid qualification publish command")
    header = {key: value for key, value in record.items() if key != "release_command"}
    header.update(channel=args.channel, operation="upload", argv=argv)
    with args.log.open("xb", buffering=0) as log:
        log.write((START_MARKER + json.dumps(header) + "\n").encode())
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=False)
        require(result.returncode >= 0, "publish stopped by signal")
        log.write(("\n" + EXIT_MARKER + json.dumps({"exit": result.returncode}) + "\n").encode())
except (ValueError, KeyError, OSError, IndexError) as error:
    parser.exit(1, f"capture: {error}\n")
parser.exit(result.returncode)
