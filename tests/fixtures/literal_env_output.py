import json
import os
from pathlib import Path
import sys


observation = Path(sys.argv[1])
secret = os.environ["TOKEN"]
observation.write_text(json.dumps({"token": secret}), encoding="utf-8")
print("prefix" + secret + "suffix")
