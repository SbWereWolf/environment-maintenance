import json
import os
from pathlib import Path
import sys


observation = Path(sys.argv[1])
secret = sys.argv[2]
observation.write_text(
    json.dumps({
        "argument": secret,
        "cwd": str(Path.cwd()),
        "token": os.environ["TOKEN"],
    }),
    encoding="utf-8",
)
print(secret)
print(f"safe-diagnostic:{secret}", file=sys.stderr)
