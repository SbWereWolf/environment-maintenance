import json
from pathlib import Path
import sys

state = Path(sys.argv[1])
log = Path(sys.argv[2])
previous = log.read_text(encoding="utf-8") if log.exists() else ""
log.write_text(previous + "check\n", encoding="utf-8")
value = state.read_text(encoding="utf-8") if state.exists() else "missing"
print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": "check",
    "state": value,
}))
