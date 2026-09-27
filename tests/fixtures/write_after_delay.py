from pathlib import Path
import sys
import time

time.sleep(float(sys.argv[2]))
Path(sys.argv[1]).write_text("late", encoding="utf-8")
