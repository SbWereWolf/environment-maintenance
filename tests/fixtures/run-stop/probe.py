"""Independent fixture commands, genuine groups and finite arrangement controls."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

root, label, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
with (root / "events.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({"label": label, "mode": mode, "cwd": os.getcwd(),
                             "token": os.environ.get("PROBE_TOKEN")}) + "\n")
if mode == "marker":
    sys.stdout.buffer.write(b"WARNING fixture\xff\x00\n")
    sys.stderr.buffer.write(b"fixture diagnostic\x00\n")
    raise SystemExit(0)
if mode == "fail":
    sys.stderr.write("fixture selected failure\n")
    raise SystemExit(7)
if mode == "bad-pgid":
    print(json.dumps({"status": "submitted", "pgid": "invalid"}))
    raise SystemExit(0)
if mode == "reservation":
    directory = Path(tempfile.gettempdir()) / "environment-maintenance"
    files = list(directory.glob("env-*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text())["applications"] == {}
    locks = [path for path in directory.iterdir() if path not in files]
    assert len(locks) == 1
    with locks[0].open("r+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.lockf(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.lockf(stream, fcntl.LOCK_UN)
        fcntl.flock(stream, fcntl.LOCK_UN)
    (root / "reservation-observed.json").write_text(json.dumps(
        {"reserved": True, "launch_outside_lock": True}))

argv = [sys.executable, "-B", str(Path(__file__).with_name("worker.py")), str(root), label]
if mode == "dead":
    argv.append("exit")
worker = subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
deadline = time.monotonic() + 5
while not (root / (label + ".started.json")).exists():
    assert worker.poll() is None and time.monotonic() < deadline, "fixture worker did not start"
    time.sleep(.01)
if mode == "dead":
    assert worker.wait(timeout=5) == 0
if mode == "no-save":
    directory = Path(tempfile.gettempdir()) / "environment-maintenance"
    for path in directory.glob("env-*.json"):
        path.chmod(0o400)
    directory.chmod(0o500)
print(json.dumps({"status": "submitted", "pgid": worker.pid}))
