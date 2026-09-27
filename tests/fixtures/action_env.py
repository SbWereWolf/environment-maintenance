import json
import os

print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": "check",
    "state": "satisfied",
    "seen": [os.getenv("ALLOWED"), os.getenv("DECLARED"), os.getenv("SECRET", "absent")],
}))
