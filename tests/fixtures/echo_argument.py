import json
import sys

print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": "check",
    "state": "satisfied",
    "value": sys.argv[1],
}))
