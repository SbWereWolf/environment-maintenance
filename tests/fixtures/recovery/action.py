"""Test-owned action: direct effects and raw response, no product imports."""
import json
import os
from pathlib import Path
import sys

role, state_name, log_name, response_name, observed_name = sys.argv[1:6]
state, log = Path(state_name), Path(log_name)
with log.open("a", encoding="utf-8") as stream:
    stream.write(role + "\n")
if observed_name != "-":
    with Path(observed_name).open("a", encoding="ascii") as stream:
        stream.write(json.dumps({
            "role": role,
            "argv": sys.argv[6:],
            "cwd": os.getcwd(),
            "env": dict(os.environ),
        }, ensure_ascii=True) + "\n")
if role in ("install", "repair"):
    state.write_bytes(b"satisfied")
if response_name != "-":
    sys.stdout.buffer.write(Path(response_name).read_bytes())
else:
    response = {
        "schema": "environment-maintenance/action-result/v2",
        "requirement_id": "sample",
        "action": role,
    }
    if role == "check":
        response["state"] = state.read_text(encoding="utf-8")
    else:
        response["outcome"] = "completed"
    print(json.dumps(response, ensure_ascii=True))
