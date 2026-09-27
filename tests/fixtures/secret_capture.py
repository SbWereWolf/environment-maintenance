import json
import os
from pathlib import Path
import sys


observation = Path(sys.argv[1])
action = sys.argv[2]
secret = sys.argv[3]
observation.write_text(
    json.dumps({
        "argv": sys.argv[3:],
        "cwd": str(Path.cwd()),
        "token": os.environ["TOKEN"],
    }),
    encoding="utf-8",
)
print(f"safe-diagnostic:{secret}", file=sys.stderr)
print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": action,
    **({"state": "satisfied"} if action == "check" else {"outcome": "completed"}),
}))
