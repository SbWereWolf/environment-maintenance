import json
from pathlib import Path
import sys


def initial_environment():
    entries = Path("/proc/self/environ").read_bytes().split(b"\0")
    return {
        key.decode("utf-8"): value.decode("utf-8")
        for entry in entries
        if entry
        for key, value in [entry.split(b"=", 1)]
    }


observation = Path(sys.argv[1])
action = sys.argv[2]
observation.write_text(json.dumps({
    "argv": sys.argv[3:],
    "cwd": str(Path.cwd()),
    "environment": initial_environment(),
}), encoding="utf-8")
print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": action,
    **({"state": "satisfied"} if action == "check" else {"outcome": "completed"}),
}))
