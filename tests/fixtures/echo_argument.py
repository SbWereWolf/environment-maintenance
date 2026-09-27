import json
from pathlib import Path
import sys

Path(sys.argv[1]).write_text(sys.argv[2], encoding="utf-8")
action = sys.argv[3]
print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": action,
    **({"state": "satisfied"} if action == "check" else {"outcome": "completed"}),
}))
