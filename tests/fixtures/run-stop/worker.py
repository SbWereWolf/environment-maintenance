"""Own live/PTY worker with independently observable process and signal facts."""
import json
import os
from pathlib import Path
import signal
import sys

root, label = Path(sys.argv[1]), sys.argv[2]


def save(suffix, record):
    path = root / (label + "." + suffix + ".json")
    temporary = path.with_suffix(".pending")
    temporary.write_text(json.dumps(record), encoding="utf-8")
    temporary.replace(path)


def stop(number, frame):
    save("stopped", {"label": label, "pid": os.getpid(), "signal": number})
    raise SystemExit(0)


for number in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
    signal.signal(number, stop)
save("started", {"label": label, "pid": os.getpid(), "pgid": os.getpgrp(),
                 "tty": os.ttyname(0) if os.isatty(0) else None,
                 "window": os.environ.get("WINDOWID"), "root": str(root)})
if len(sys.argv) > 3 and sys.argv[3] == "exit":
    raise SystemExit(0)
while True:
    signal.pause()
