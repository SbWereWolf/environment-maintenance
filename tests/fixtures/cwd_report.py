import json
from pathlib import Path

print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": "check",
    "state": "satisfied",
    "cwd": str(Path.cwd()),
}))
