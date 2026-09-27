import json
from pathlib import Path
import sys

state = Path(sys.argv[1])
log = Path(sys.argv[2])
log.write_text(log.read_text(encoding="utf-8") + "repair\n", encoding="utf-8")
state.write_text("satisfied", encoding="utf-8")
print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": "repair",
    "outcome": "completed",
}))
