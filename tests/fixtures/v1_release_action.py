"""Independent process fixture for installed-consumer release assertions."""

import json
import sys


mode = sys.argv[1]
if mode == "mutation-fails":
    print("fixture mutation failed", file=sys.stderr)
    raise SystemExit(7)
if mode == "malformed":
    print("not-json")
    raise SystemExit(0)

response = {
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": "check",
    "state": "satisfied",
}
if mode == "unavailable":
    response.update(
        state="unavailable",
        cause="fixture resource unavailable",
        recommendations=["Prepare the fixture resource"],
    )
elif mode == "echo-marker":
    assert len(sys.argv) == 3
    print("fixture note: " + sys.argv[2], file=sys.stderr)
else:
    raise ValueError(mode)
print(json.dumps(response))
