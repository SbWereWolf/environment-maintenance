from pathlib import Path
import sys

print(Path(sys.argv[1]).read_text(encoding="utf-8"), end="")
raise SystemExit(int(sys.argv[2]))
