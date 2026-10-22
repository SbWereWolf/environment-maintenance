"""Controlled external command: report observation, emit fixed bytes, exit."""
import json
import os
from pathlib import Path
import sys


def payload(path):
    source = Path(path)
    if source.suffix == '.hex':
        return bytes.fromhex(source.read_text(encoding='utf-8'))
    return source.read_bytes()


events, token, stdout, stderr, code = sys.argv[1:6]
observation = {
    'token': token,
    'argv': sys.argv[6:],
    'cwd': os.getcwd(),
    'visible': os.environ.get('VISIBLE'),
    'host_only': os.environ.get('ENV2_HOST_ONLY'),
}
with Path(events).open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(observation, ensure_ascii=False) + '\n')
sys.stdout.buffer.write(payload(stdout))
sys.stdout.buffer.flush()
sys.stderr.buffer.write(payload(stderr))
sys.stderr.buffer.flush()
raise SystemExit(int(code))
