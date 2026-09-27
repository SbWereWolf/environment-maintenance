import json
import os
from pathlib import Path
import sys


observation = Path(sys.argv[1])
observation.write_text(os.environ["TOKEN"], encoding="utf-8")
print(json.dumps({
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": "check",
    "state": "unavailable",
    "cause": "package unavailable",
    "recommendations": ["install package manually"],
}))
