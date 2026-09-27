import json
import sys

action = sys.argv[1]
schema = sys.argv[2]
print(json.dumps({
    "schema": schema,
    "requirement_id": "sample",
    "action": action,
    **({"state": "satisfied"} if action == "check" else {"outcome": "completed"}),
}))
