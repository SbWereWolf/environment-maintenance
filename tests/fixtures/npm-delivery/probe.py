"""Test-owned external resource action; no product import or result oracle."""
import json
import os
from pathlib import Path
import sys

events, label, token, argument = sys.argv[1:]
profile = json.loads(Path(__file__).with_name('stream-profile.json').read_text())
with Path(events).open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(dict(label=label, cwd=os.getcwd(), token=token,
        argument=argument, only=os.environ.get('ONLY_ENV')), ensure_ascii=False) + '\n')
if label == 'stream':
    output = bytes.fromhex(profile['large_stdout_pattern_hex']) * profile['large_stdout_repetitions']
else:
    output = bytes.fromhex(profile['stdout_hex'])
sys.stdout.buffer.write(output)
sys.stderr.buffer.write(bytes.fromhex(profile['stderr_hex']))
raise SystemExit(7 if label == 'fail' else 0)
