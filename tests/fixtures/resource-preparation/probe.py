"""Independent finite external tool: records effects and emits supplied bytes."""
import json
import os
from pathlib import Path
import sys

events, tag, token, stdout_path, stderr_path, code = sys.argv[1:]
event = dict(tag=tag, token=token, cwd=os.getcwd(),
             value=os.environ.get('RESOURCE_VALUE'), scalar=os.environ.get('SCALAR'),
             host_only=os.environ.get('ENV2_HOST_ONLY'))
with Path(events).open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(event, ensure_ascii=False) + '\n')
sys.stdout.buffer.write(bytes.fromhex(Path(stdout_path).read_text(encoding='utf-8')))
sys.stderr.buffer.write(bytes.fromhex(Path(stderr_path).read_text(encoding='utf-8')))
raise SystemExit(int(code))
