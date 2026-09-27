"""Minimal runnable catalog/v2 example action."""

import json
import sys

role = sys.argv[1]
print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "example",
    "action": role,
    **({"state": "satisfied"} if role == "check" else {"outcome": "completed"}),
}))
