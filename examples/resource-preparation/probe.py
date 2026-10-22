"""Внешний учебный инструмент с наблюдаемым эффектом и полными потоками."""
import json
import os
from pathlib import Path
import sys


def main():
    events, label, state = sys.argv[1:]
    with Path(events).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(label=label, value=os.environ["VALUE"])) + "\n")
    sys.stdout.buffer.write(b"\xff" + label.encode("ascii") + b"\x00\n")
    sys.stderr.buffer.write(b"diagnostic:" + label.encode("ascii") + b"\n")
    return 0 if state == "ready" else 3


if __name__ == "__main__":
    raise SystemExit(main())
