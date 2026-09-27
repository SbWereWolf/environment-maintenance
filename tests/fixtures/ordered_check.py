import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
identifier = sys.argv[2]
previous = path.read_text(encoding="utf-8") if path.exists() else ""
path.write_text(previous + identifier + "\n", encoding="utf-8")
print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": identifier,
    "action": "check",
    "state": "satisfied",
}))
