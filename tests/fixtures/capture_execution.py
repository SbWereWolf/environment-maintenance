import json
import os
from pathlib import Path
import sys

observation = Path(sys.argv[1])
action = sys.argv[2]
observation.write_text(json.dumps({
    "argv": sys.argv[3:],
    "cwd": str(Path.cwd()),
    "environment": dict(os.environ),
}), encoding="utf-8")
print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": action,
    **({"state": "satisfied"} if action == "check" else {"outcome": "completed"}),
}))
