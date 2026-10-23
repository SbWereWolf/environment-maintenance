"""Observe actual process order/context and emit fixed test-owned binary streams."""
import json
import os
from pathlib import Path
import sys

events, tag, resource, stdout_file, stderr_file, code = sys.argv[1:]
exists = Path(resource).is_file()
record = dict(tag=tag, cwd=os.getcwd(), token=os.environ.get('RESOURCE_TOKEN'),
              number=os.environ.get('NUMBER'), host=os.environ.get('ENV2_HOST_ONLY'), exists=exists)
with Path(events).open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(record) + '\n')
sys.stdout.buffer.write(bytes.fromhex(Path(stdout_file).read_text()))
sys.stderr.buffer.write(bytes.fromhex(Path(stderr_file).read_text()))
exit_code = int(code)
if exit_code == 3 and not exists:
    exit_code = 1
raise SystemExit(exit_code)
