"""Emit known complete streams and an independent completion marker after flush."""
import json
import os
from pathlib import Path
import sys

directory, label, stdout, stderr, code = sys.argv[1:]
with (Path(directory) / 'trace.jsonl').open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(dict(label=label, pid=os.getpid(), parent=os.getppid(),
        argv=sys.argv[1:], cwd=os.getcwd(), token=os.environ.get('LAUNCH_TOKEN'))) + '\n')
sys.stdout.buffer.write(bytes.fromhex(Path(stdout).read_text()))
sys.stdout.buffer.flush()
sys.stderr.buffer.write(bytes.fromhex(Path(stderr).read_text()))
sys.stderr.buffer.flush()
(Path(directory) / (label + '.done')).write_text('flushed', encoding='utf-8')
raise SystemExit(int(code))
