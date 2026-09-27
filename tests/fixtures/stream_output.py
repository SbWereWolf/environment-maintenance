import os
from pathlib import Path
import sys

marker = Path(sys.argv[1])
while True:
    marker.write_text("writer-alive", encoding="utf-8")
    os.write(1, b"x" * 4096)
    os.write(2, b"y" * 4096)
