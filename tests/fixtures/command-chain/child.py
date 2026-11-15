"""Independent wire consumer: echo stdin bytes, emit chosen bytes and exit."""
import json
from pathlib import Path
import sys

payload = sys.stdin.buffer.read()
Path(sys.argv[1]).write_bytes(payload)
if sys.argv[2] == 'echo':
    value = json.loads(payload)
    value['step'] = 'child-changed'
    sys.stdout.buffer.write(json.dumps(value).encode('utf-8'))
else:
    sys.stdout.buffer.write(b'out\x00\xff' * 32768)
sys.stderr.buffer.write(b'err\x00\xfe' * 32768)
sys.exit(int(sys.argv[3]))
